// «instrucción»: mandarle a un hilo o a un agente lo que se pide, con el contexto de donde se pidió
// (docs/propuestas/instruccion.md). Una sola ventana para todo lo que se manda a un hilo, desde donde sea: una tarea en
// foco o en su ficha, toda entidad en su menú («instrucción…»), un agente en su hoja («encargar»).
//
// De arriba abajo: de qué se habla (la entidad, que va como contexto), a quién (su hilo, uno nuevo para ella, un agente
// o un hilo que ya existe: abierto, cerrado o, plegados al final, los archivados, que se retoman al mandarles), la skill (opcional: las de quien la recibe) y la instrucción escrita; abajo, lo que le va a
// llegar, tal cual. ⌘⏎ la manda (`telar actuar`, POST /actuar); la casilla de abajo la deja escrita en la entrada del
// hilo, sin mandar. Adónde iría «su hilo» lo dice telar (POST /actuar/adonde), y llega después de abrirse la ventana.
// Lo escrito y no mandado queda como borrador de esa entidad: abrirla otra vez, desde donde sea, lo trae de vuelta.
// En vez de una entidad (o además), lo que se habla puede ser un texto: el contexto libre que manda la pestaña de un
// módulo (`window.lienzo.pedir("instruccion")`, un chat). Va entero al agente, con sus líneas, y la instrucción es
// opcional: vacía, le llega una línea que le pide procesarlo.
// Todo del mismo tamaño: lo que distingue es el color y el ícono (web/iconos.ts).

import * as cli from '../cli';
import { modelo } from '../modelo';
import { barraDeBuscar } from './buscadores';
import { guardar as guardarEscrito, leer as leerEscrito } from './guardado';
import { C, I } from './iconos';
import * as ui from './ui';
import * as mundo from './mundo';
import { boton, cancelar as botonCancelar } from '../componentes/boton';
import { teclasDeBotones } from './botonera';

/** Lo que se le pasa a la ventana: de qué se habla y lo que viene elegido. */
export interface Pedido {
    /** la entidad de la que se habla (`tarea:T84`, `proyecto:…`): su contexto va en lo que se manda */
    direccion?: string;
    /** la fila de un pendiente que la pantalla ya tiene: ahorra buscarlo, y nombra uno que no tiene dirección */
    fila?: cli.FilaConocida;
    /** cómo se nombra mientras llega lo que telar sabe de ella */
    titulo?: string;
    /** la skill sugerida: viene elegida si quien la recibe la tiene */
    skill?: string;
    /** a quién, de entrada: vacío es su hilo; `NUEVO`, uno nuevo para ella; o el nombre de un agente o de un hilo */
    a?: string;
    /** solo a ese destino (encargarle a un agente desde su hoja): no se elige a quién */
    solo?: boolean;
    /** lo que viene escrito en la instrucción (el mensaje que trae un ítem de un bloque); un borrador de la misma
     *  entidad gana */
    texto?: string;
    /** sin entidad, con «un hilo nuevo»: cómo se llama el hilo */
    nombre?: string;
    /** un texto del que se habla, que no es una entidad (lo que mostraba la pestaña de un módulo): va entero, con sus
     *  líneas, debajo de lo pedido; con él, la instrucción es opcional */
    contexto?: cli.ContextoLibre;
}

/** Lo que dice el contexto libre de sí mismo en una línea: cómo se llama, de dónde viene y cuántas líneas trae. */
export function resumenLibre(c: cli.ContextoLibre): { nombre: string; detalle: string; lineas: number } {
    const texto = c.texto.replace(/^\n+|\s+$/g, '');
    const lineas = texto ? texto.split('\n').length : 0;
    const primera = texto.split('\n').find(l => l.trim()) ?? '';
    const nombre = (c.titulo ?? '').trim() || primera.trim();
    const detalle = [`${lineas} línea${lineas === 1 ? '' : 's'}`, c.origen ? `desde ${c.origen}` : ''].filter(Boolean).join(' · ');
    return { nombre, detalle, lineas };
}

/** El valor de «un hilo nuevo» en la lista de a quién (un hilo no se puede llamar así: empieza con +). */
export const NUEVO = '+nuevo';

/** Lo escrito y no mandado, por entidad (su dirección, o la ref de su fila; un agente en su hoja, `a:<nombre>`), con a
 *  quién y la skill que tenía elegidos: vuelve al abrirla otra vez, desde donde sea, y se va al mandarla bien. Vive
 *  mientras viva la pestaña: recargar la página no lo pierde (web/guardado.ts). */
interface Borrador { texto: string; a: string; skill: string }
const borradores = {
    get: (llave: string) => leerEscrito<Borrador>(`instruccion:${llave}`),
    set: (llave: string, b: Borrador) => guardarEscrito(`instruccion:${llave}`, b),
    delete: (llave: string) => guardarEscrito(`instruccion:${llave}`, undefined),
};

function el<K extends keyof HTMLElementTagNameMap>(tag: K, clase = '', texto?: string): HTMLElementTagNameMap[K] {
    const e = document.createElement(tag);
    if (clase) e.className = clase;
    if (texto !== undefined) e.textContent = texto;
    return e;
}

const norm = (t: string | undefined) => (t ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

/** Una lista con un filtro arriba y una opción elegida (la de a quién, la de la skill): ↑ ↓ mueven la elección. Las
 *  opciones `aparte` (los hilos archivados) van al final, plegadas bajo una fila que las cuenta, como ARCHIVO en la
 *  barra: un clic las abre, y buscar las trae sin abrirlas. `extra`: lo que también encuentra el filtro y dice la
 *  ayuda, sin ocupar la fila (la carpeta de un hilo cerrado, que en su lugar dice cómo le llega). */
interface Opcion { valor: string; nombre: string; detalle?: string; extra?: string; icono: string; color: string; aparte?: boolean }
function lista(titulo: string, placeholder: string, alCambiar: (valor: string) => void,
    aparte: { nombre: string; ayuda: string } = { nombre: 'más', ayuda: '' }) {
    const seccion = el('section');
    seccion.appendChild(el('h4', '', titulo));
    // el filtro: la barra de un buscador (componentes/buscador.ts) sobre la lista
    const { barra, campo: filtro } = barraDeBuscar({ placeholder, ayuda: '↑ ↓ elegir' });
    const caja = el('div', 'web-lista');
    seccion.append(barra, caja);
    let opciones: Opcion[] = [], elegida = '', vis: Opcion[] = [], abierto = false;
    const fila = (o: Opcion) => {
        const f = el('div', `web-op${o.valor === elegida ? ' sel' : ''}`);
        f.style.setProperty('--c', `var(--${o.color})`);
        f.append(el('span', 'i ico', o.valor === elegida ? I.hecha : o.icono), el('span', 'l', o.nombre));
        if (o.detalle) f.appendChild(el('span', 'd', o.detalle));
        f.title = [o.nombre, o.detalle, o.extra].filter(Boolean).join('\n');
        f.addEventListener('click', () => elegir(o.valor));
        return f;
    };
    const pintar = () => {
        caja.replaceChildren();
        const q = norm(filtro.value);
        const calzan = opciones.filter(o => !q || norm(`${o.nombre} ${o.detalle ?? ''} ${o.extra ?? ''}`).includes(q));
        const delante = calzan.filter(o => !o.aparte), atras = calzan.filter(o => o.aparte);
        // abiertas si se pidió (o si la elegida es una de ellas, al ponerlas: la de un borrador) o si se está buscando
        const verAtras = abierto || !!q;
        vis = [...delante, ...verAtras ? atras : []];
        caja.append(...delante.map(fila));
        if (atras.length) {
            const cab = el('div', 'web-op aparte');
            cab.append(el('span', 'i ico', verAtras ? I.abierto : I.plegado), el('span', 'l', aparte.nombre),
                el('span', 'd', q ? `${atras.length} que calzan` : String(atras.length)));
            cab.title = q ? aparte.ayuda : `${aparte.ayuda}: un clic ${verAtras ? 'los pliega' : 'los muestra'}`;
            if (!q) cab.addEventListener('click', () => { abierto = !abierto; pintar(); });
            caja.appendChild(cab);
            if (verAtras) caja.append(...atras.map(fila));
        }
        caja.querySelector('.sel')?.scrollIntoView({ block: 'nearest' });
    };
    const elegir = (valor: string) => { if (valor === elegida) return; elegida = valor; pintar(); alCambiar(valor); };
    filtro.addEventListener('input', pintar);
    filtro.addEventListener('keydown', e => {
        if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
        e.preventDefault();
        const i = vis.findIndex(o => o.valor === elegida);
        const j = Math.max(0, Math.min(vis.length - 1, i + (e.key === 'ArrowDown' ? 1 : -1)));
        if (vis[j]) elegir(vis[j].valor);
    });
    return {
        seccion, filtro,
        poner(nuevas: Opcion[], eleccion?: string) {
            opciones = nuevas;
            elegida = eleccion !== undefined && opciones.some(o => o.valor === eleccion) ? eleccion
                : opciones.some(o => o.valor === elegida) ? elegida : opciones[0]?.valor ?? '';
            if (opciones.some(o => o.aparte && o.valor === elegida)) abierto = true;
            pintar();
        },
        get valor() { return elegida; },
        tiene(valor: string) { return opciones.some(o => o.valor === valor); },
    };
}

/** Las skills de cada destino, ya leídas: abrir la ventana otra vez es instantáneo. Se olvidan a los 5 minutos. */
const skillsLeidas = new Map<string, { hora: number; lista: cli.JsonSkill[] }>();

/** Las skills que tiene a mano el agente de un hilo, o las de una carpeta (la de un hilo que todavía no existe; sin
 *  carpeta, la raíz, donde se abriría). */
export async function skillsDe(hilo: string, carpeta: string): Promise<cli.JsonSkill[]> {
    const llave = `${hilo}|${carpeta}`;
    const guardadas = skillsLeidas.get(llave);
    if (guardadas && Date.now() - guardadas.hora < 5 * 60_000) return guardadas.lista;
    const r = hilo ? await cli.skills(hilo) : await cli.skills('', carpeta || '/');
    const lista_ = [...(r?.datos?.skills ?? [])].sort((a, b) => (b.usada ?? 0) - (a.usada ?? 0) || a.nombre.localeCompare(b.nombre));
    if (r?.datos) skillsLeidas.set(llave, { hora: Date.now(), lista: lista_ });
    return lista_;
}

/** Adónde iría «su hilo» de cada entidad, por unos minutos: abrirla otra vez dice al tiro adónde va. */
const adondes = new Map<string, { hora: number; r: cli.JsonAdonde }>();

/** Lo que dijo telar de cada hilo cerrado o archivado al elegirlo (`POST /actuar/adonde`): dónde se retoma al mandarle
 *  algo. Unos minutos, como `adondes`. */
const cerrados = new Map<string, { hora: number; r: cli.JsonAdonde }>();
function deCerrado(nombre: string): cli.JsonAdonde | undefined {
    const g = cerrados.get(nombre);
    return g && Date.now() - g.hora < 5 * 60_000 ? g.r : undefined;
}

/** Un hilo sin ventana (cerrado o archivado), en palabras: dónde se retoma, según telar (lo que hace `telar actuar`):
 *  aquí con su conversación, de nuevo si su conversación ya no está, o en la máquina donde vive, por el bus. */
function retoma(cual: string, a: cli.JsonAdonde): string {
    if (a.falta) return `${cual}: ${a.falta}`;
    if (a.como === 'bus') return `${cual} en ${a.maquina}: por el bus, allá se retoma`;
    if (a.como === 'abrir') return `${cual}: su conversación ya no está, se abre de nuevo`;
    return `${cual}: se retoma con su conversación`;
}

/** «su hilo», en palabras: adónde va y cómo llega. */
function suHilo(d: cli.JsonAdonde): Opcion {
    const nombre = d.destino ? `su hilo · ${d.destino}` : 'su hilo';
    const h = d.destino ? modelo.hilos.find(x => x.nombre === d.destino) : undefined;
    const cual = h?.archivado ? 'archivado' : 'cerrado';
    // el hilo mismo, sin ventana: dónde se retoma (aquí, de nuevo o allá), como en la lista
    const detalle = d.propio && h && !h.vivo && d.como !== 'agente' ? retoma(cual, d) : ({
        hilo: d.carpeta || 'abierto', dormido: `${cual}: se retoma con su conversación`, abrir: `se le abre uno en ${d.carpeta || 'la raíz'}`,
        agente: 'agente: se le encarga, en un hilo hijo', bus: `en ${d.maquina}: le llega a su casilla`,
    } as Record<string, string>)[d.como] ?? '';
    const nuevo = d.como === 'abrir' && !d.propio;
    return { valor: '', nombre, detalle, icono: nuevo ? I.nuevo : I.agente, color: nuevo ? C.hecho : C.ir };
}

/** Cómo le llega una instrucción a un hilo de la lista, en pocas palabras. Abierto aquí, se le escribe; el de otra
 *  máquina, por el bus. Cerrado o archivado, se retoma: dónde, lo dice telar al elegirlo (`retoma`); antes, lo que se
 *  sabe sin preguntar. */
function comoLlega(h: cli.JsonHilo): string {
    const cual = h.archivado ? 'archivado' : 'cerrado';
    if (h.vivo) return h.remoto ? `${h.archivado ? 'archivado, ' : ''}en ${h.remoto}: por el bus`
        : h.archivado ? 'archivado, abierto: se le escribe' : h.relativa || '';
    const dicho = deCerrado(h.nombre);
    if (dicho) return retoma(cual, dicho);
    return [`${cual}${h.remoto ? ` en ${h.remoto}` : ''}`, h.relativa].filter(Boolean).join(' · ');
}

/** La dirección de un hilo de esta lista, sin su máquina: la de uno cerrado la resuelve telar aquí (`adonde`). */
const direccionDe = (h: cli.JsonHilo) => (h.direccion || `hilo:${encodeURIComponent(h.nombre)}`).replace(/@[a-z0-9][\w-]*$/, '');

/** Abre la ventana. `alMandar` corre al tiro cuando la persona la manda (foco saca la tarjeta sin esperar); la promesa
 *  termina con lo que pasó: undefined si se canceló o no se pudo. */
export async function abrir(p: Pedido, alMandar?: () => void): Promise<cli.JsonActuado | undefined> {
    const direccion = p.direccion ?? p.fila?.direccion ?? '';
    const conEntidad = !!direccion || !!p.fila;
    const libre = p.contexto?.texto.trim() ? p.contexto : undefined;
    // lo escrito sobre un contexto libre (un chat) vuelve al abrirlo otra vez desde el mismo lugar
    const llaveBorrador = direccion || p.fila?.ref || (p.solo && p.a ? `a:${p.a}` : '')
        || (libre ? `contexto:${libre.origen ?? ''}|${libre.titulo || resumenLibre(libre).nombre}` : '');
    const guardado = llaveBorrador ? borradores.get(llaveBorrador) : undefined;
    // la skill y el destino que se piden (o que dejó el borrador): pueden no estar todavía en su lista (las skills se
    // leen; su hilo y uno nuevo llegan con lo que dice telar), y se eligen cuando lleguen. Lo que la persona elija, manda
    let skillQuerida = guardado ? guardado.skill : p.skill ?? '';
    let querido = guardado?.a ?? p.a ?? (conEntidad ? '' : undefined);

    const c = el('dialog', 'web-caja web-instruccion');
    document.body.appendChild(c);
    const cab = el('h3');
    const ic = el('span', 'i ico', I.instruccion);
    cab.append(ic, el('span', '', p.solo && p.a ? `instrucción · a ${p.a}` : 'instrucción'));
    c.appendChild(cab);

    // el pie, la banda de botones (componentes/boton.ts): dejarla escrita sin mandar (solo en un hilo de aquí que ya existe)
    // a la izquierda; «⌘⏎ mandar» y «⎋ cancelar», en celdas
    const pie = el('div', 'ventana-pie botonera');
    const izq = el('span', 'botonera-izq');
    const solo = el('label', 'solo');
    const caja = el('input'); caja.type = 'checkbox';
    solo.append(caja, el('span', '', 'dejarla escrita, sin mandar'));
    izq.append(solo);
    pie.append(izq);
    pie.insertAdjacentHTML('beforeend', boton({ texto: 'mandar', tecla: '⌘⏎', datos: { mandar: '' }, ayuda: 'mandarla a quien elegiste' })
        + boton(botonCancelar('cancelar', null)));
    const si = pie.querySelector<HTMLElement>('[data-mandar]')!, no = pie.querySelector<HTMLElement>('[data-tecla="⎋"]')!;

    // de qué se habla: la entidad (su contexto va en lo que se manda)
    const de = el('div', 'web-op de');
    de.style.setProperty('--c', 'var(--azul)');
    const nombre = el('span', 'l', p.titulo || direccion || p.fila?.texto || '');
    // el ícono de la dirección: lo que va como contexto es eso, la dirección de la entidad y lo que telar sabe de ella
    de.append(el('span', 'i ico', I.direccion), nombre, el('span', 'd', direccion));
    if (conEntidad) c.appendChild(de);
    // un contexto libre (un chat): cómo se llama y cuántas líneas trae; un clic lo muestra entero, tal cual le llega
    const dicho = libre ? resumenLibre(libre) : undefined;
    if (libre && dicho) {
        const fila = el('div', 'web-op de libre');
        fila.style.setProperty('--c', 'var(--azul)');
        const ver = el('pre', 'texto-libre');
        ver.textContent = libre.texto.replace(/^\n+|\s+$/g, '');
        ver.hidden = true;
        const plegar = el('span', 'i ico', I.plegado);
        fila.append(el('span', 'i ico', I.compartir), el('span', 'l', dicho.nombre || 'lo compartido'), el('span', 'd', dicho.detalle), plegar);
        fila.title = 'un clic lo muestra entero: le llega así, debajo de la instrucción';
        fila.addEventListener('click', () => { ver.hidden = !ver.hidden; plegar.textContent = ver.hidden ? I.plegado : I.abierto; });
        c.append(fila, ver);
    }

    // a quién y la skill, lado a lado; la skill depende de a quién
    let adonde: cli.JsonAdonde | undefined;
    let pedidas = '';
    const skills = lista('skill · opcional', 'skills', valor => { skillQuerida = valor; pintarLlega(); guardar(); });
    const sinSkill: Opcion = { valor: '', nombre: 'sin skill', detalle: 'solo la instrucción', icono: I.escribir, color: C.otro };
    async function cargarSkills(destino: string): Promise<void> {
        let hilo = destino, carpeta = '';
        if (!conEntidad && destino === NUEVO) {
            hilo = '';  // un hilo nuevo sin entidad: las skills de la raíz, donde se abre
        } else if (destino === '' || destino === NUEVO) {
            if (!adonde) { skills.poner([sinSkill, { valor: '…', nombre: 'leyendo sus skills…', icono: I.accion, color: 'dim' }], ''); return; }
            hilo = destino === '' && adonde.como !== 'abrir' ? adonde.destino : '';
            carpeta = hilo ? '' : adonde.carpeta;
        }
        const llave = `${hilo}|${carpeta}`;
        pedidas = llave;
        const antes = skillQuerida;
        skills.poner([sinSkill, { valor: '…', nombre: 'leyendo sus skills…', icono: I.accion, color: 'dim' }], '');
        const lista_ = await skillsDe(hilo, carpeta);
        if (pedidas !== llave) return;  // ya se eligió otro destino
        skills.poner([sinSkill, ...lista_.map(x => ({ valor: x.nombre, nombre: `/${x.nombre}`,
            detalle: (x.usada ? `${x.usada}× · ` : '') + (x.descripcion ?? ''), icono: I.accion, color: C.agente }))], antes);
        pintarLlega();
    }
    const destinos = lista('a quién', 'hilos y agentes', valor => { querido = valor; pintarLlega(); guardar(); void cargarSkills(valor); mirar(valor); },
        { nombre: 'archivo', ayuda: 'los hilos archivados: el que elijas sale del archivo y se retoma' });
    /** uno cerrado o archivado, elegido: telar dice dónde se retoma (aquí, de nuevo o allá), y la lista y lo que le
     *  llega lo dicen */
    function mirar(valor: string): void {
        const h = modelo.hilos.find(x => x.nombre === valor);
        if (!h || h.vivo || deCerrado(h.nombre)) return;
        void cli.adonde(direccionDe(h)).then(r => {
            const vacio = { destino: h.nombre, como: '', maquina: '', carpeta: '', nuevo: false, contexto: '', titulo: '', propio: true };
            cerrados.set(h.nombre, { hora: Date.now(), r: r.datos ?? { ...vacio, falta: r.error ?? 'no sé dónde se retoma' } });
            if (hecho) return;
            ponerDestinos(destinos.valor);
            pintarLlega();
        });
    }

    // los destinos, de lo que la página ya tiene: su hilo (cuando telar diga cuál), uno nuevo, los agentes y los hilos:
    // los abiertos, los cerrados y, al final y plegados, los archivados (son muchos: buscar los encuentra igual). Uno que
    // vive en otra máquina llega por el bus: sin bus no hay cómo, y no está
    const agentes = modelo.secciones.filter(x => x.grupo === 'agentes');
    const deAgente = (h: cli.JsonHilo) => agentes.some(a => cli.enSeccion(a, h.nombre));
    // a quién se le puede mandar: los agentes del mundo puesto (web/mundo.ts, `seVeAgente`: en todo, los otros, salvo los que se esconden); el
    // destino que ya viene pedido (el de la pestaña, `[instruccion] destino`) se respeta aunque sea de otro
    const seVen = new Set(mundo.agentesQueSeVen(agentes, modelo.hilos));
    const delMundo = agentes.filter(a => a.nombre === p.a || a.nombre === querido || seVen.has(a));
    const delModelo = (): Opcion[] => {
        // ni los hilos de un agente que pide esconderse fuera de su mundo (sus hijos: «Jardín › …»), salvo el pedido
        const hilos = modelo.hilos.filter(h => h.nombre !== adonde?.destino && !deAgente(h) && (!h.remoto || modelo.hayBus)
            && (h.nombre === querido || !mundo.hiloDeAgenteAjeno(h, modelo.hilos)));
        const comoOpcion = (h: cli.JsonHilo): Opcion => ({ valor: h.nombre, nombre: h.nombre, detalle: comoLlega(h),
            extra: h.relativa && h.relativa !== comoLlega(h) ? h.relativa : undefined,
            icono: h.archivado ? I.archivar : h.vivo ? I.ver : I.retomar, color: h.archivado ? 'dim' : C.ir, aparte: h.archivado });
        return [
            ...delMundo.map(a => ({ valor: a.nombre, nombre: a.nombre, detalle: 'agente: se le encarga', icono: I.agente, color: C.agente })),
            ...hilos.filter(h => !h.archivado && h.vivo).map(comoOpcion),
            ...hilos.filter(h => !h.archivado && !h.vivo).map(comoOpcion),
            ...hilos.filter(h => h.archivado).map(comoOpcion),
        ];
    };
    const ponerDestinos = (eleccion?: string) => {
        if (p.solo && p.a) {
            const a = agentes.find(x => x.nombre === p.a);
            destinos.poner([{ valor: p.a, nombre: p.a, detalle: a ? 'agente: se le encarga' : '', icono: I.agente, color: a ? C.agente : C.ir }], p.a);
            return;
        }
        const propios: Opcion[] = [];
        // sin entidad, un hilo nuevo se abre en la raíz y arranca con lo pedido (procesar un ítem de un bloque)
        if (!conEntidad) propios.push({ valor: NUEVO, nombre: 'un hilo nuevo', detalle: p.nombre ? `«${p.nombre}», en la raíz` : 'en la raíz', icono: I.nuevo, color: C.hecho });
        if (conEntidad && !adonde) propios.push({ valor: '', nombre: 'su hilo', detalle: 'buscando cuál…', icono: I.agente, color: C.ir });
        if (adonde && !adonde.falta) propios.push(suHilo(adonde));
        if (adonde?.nuevo) propios.push({ valor: NUEVO, nombre: 'un hilo nuevo', detalle: `para esto, en ${adonde.carpeta || 'la raíz'}`, icono: I.nuevo, color: C.hecho });
        destinos.poner([...propios, ...delModelo()], eleccion);
    };
    ponerDestinos(querido);

    const dos = el('div', 'dos');
    dos.append(destinos.seccion, skills.seccion);
    if (p.solo) { destinos.seccion.hidden = true; dos.classList.add('uno'); }
    c.appendChild(dos);

    // la instrucción, y lo que le va a llegar
    const escrita = el('section');
    escrita.appendChild(el('h4', '', 'instrucción'));
    const nota = el('textarea'); nota.rows = 3;
    nota.placeholder = libre ? 'qué quieres que haga con esto (opcional: vacía, le pide procesarlo)' : 'qué quieres que haga (opcional si eliges una skill)';
    nota.value = guardado?.texto ?? p.texto ?? '';
    escrita.appendChild(nota);
    const llega = el('div', 'llega');
    escrita.appendChild(llega);
    c.appendChild(escrita);
    function pintarLlega(): void {
        const skill = skills.valor && skills.valor !== '…' ? `/${skills.valor}` : '';
        // el contexto va siempre, salvo a la entidad misma (un hilo, un agente): lo arma telar, y llega con «su hilo»
        const d = destinos.valor;
        const propio = adonde?.propio && (d === '' || d === adonde.destino);
        const contexto = !conEntidad || propio ? '' : adonde ? adonde.contexto : '[contexto: …]';
        // con un contexto libre y sin nada pedido, telar le pide procesarlo (la línea es suya: /config la dice)
        const pedido = [skill, nota.value.trim()].filter(Boolean).join(' ') || (libre ? modelo.procesar || 'procesa lo que va abajo' : '');
        // el contexto libre va entero debajo: aquí, cómo se llama y cuántas líneas (un clic arriba lo muestra)
        const debajo = libre && dicho ? `[contexto: ${[dicho.nombre ? `«${dicho.nombre}»` : '', dicho.detalle].filter(Boolean).join(', ')}] ⏎ entero` : '';
        const texto = [pedido, contexto, debajo].filter(Boolean).join(' ').replace(/\s+/g, ' ');
        // uno cerrado o archivado no tiene dónde escribirle: lo pedido es su primer mensaje al retomarlo, aquí o allá
        const h = modelo.hilos.find(x => x.nombre === (d === '' ? adonde?.destino : d));
        const cerrado = !h || h.vivo || d === NUEVO ? undefined : d === '' ? adonde : deCerrado(h.nombre);
        const cuando = d === '' && adonde?.como === 'dormido' ? 'al retomarlo, '
            : !h || h.vivo || d === NUEVO || (d === '' && !adonde?.propio) ? ''
            : cerrado?.como === 'bus' ? `en ${cerrado.maquina}, al retomarlo, ` : cerrado?.como === 'abrir' ? 'al abrirlo de nuevo, ' : 'al retomarlo, ';
        llega.textContent = texto ? `${cuando}le llega: ${texto}` : '';
        llega.title = texto;
        // dejarla escrita sin mandar: solo en un hilo abierto de esta máquina (a uno cerrado, retomarlo ya se lo manda)
        const deAqui = d === '' ? adonde?.como === 'hilo' && !adonde.maquina
            : d !== NUEVO && !agentes.some(a => a.nombre === d) && !!h && h.vivo && !h.remoto;
        // lo que lleva un contexto de varias líneas no se deja escrito: en la entrada de un hilo, un salto es un ↩
        solo.hidden = !deAqui || (!!libre && libre.texto.trim().includes('\n'));
    }
    /** lo escrito, con a quién y la skill (los pedidos: los de la lista pueden estar leyéndose), queda como borrador de
     *  la entidad; sin nada escrito, no hay borrador */
    function guardar(): void {
        if (!llaveBorrador) return;
        if (!nota.value.trim()) { borradores.delete(llaveBorrador); return; }
        borradores.set(llaveBorrador, { texto: nota.value, a: querido ?? destinos.valor, skill: skillQuerida });
    }
    nota.addEventListener('input', () => { pintarLlega(); guardar(); });
    c.appendChild(pie);

    let hecho = false;
    let fin: (r: cli.JsonActuado | undefined) => void = () => {};
    const resultado = new Promise<cli.JsonActuado | undefined>(r => { fin = r; });
    const cerrar = () => { if (hecho) return; hecho = true; c.close(); c.remove(); };
    const cancelar = () => { if (hecho) return; cerrar(); fin(undefined); };
    const mandar = async () => {
        const skill = skills.valor === '…' ? '' : skills.valor;
        if (!skill && !nota.value.trim() && !libre) { nota.focus(); ui.estado('elige una skill, o escribe la instrucción', 4000); return; }
        const d = destinos.valor;
        if (d === '' && adonde?.falta) { ui.estado(adonde.falta, 5000); return; }
        cerrar();
        alMandar?.();
        const pedido: cli.PedidoInstruccion = {
            direccion, skill, nota: nota.value.trim(), escribir: !solo.hidden && caja.checked,
            ...(p.fila ? { fila: p.fila } : {}), ...(d === NUEVO ? { nuevo: true } : d ? { a: d } : {}),
            ...(d === NUEVO && !conEntidad && p.nombre ? { nombre: p.nombre } : {}),
            ...(libre ? { contexto: libre } : {}),
        };
        const quien = d === NUEVO ? 'un hilo nuevo' : d || (adonde?.destino ? `«${adonde.destino}»` : 'su hilo');
        const r = await ui.progreso({ titulo: `telar: instrucción a ${quien}…` }, () => cli.actuar(pedido));
        // si falla, el borrador queda (se guardó al escribir): abrirla otra vez lo trae, con el mismo destino
        if (!r.datos) { void ui.falla(`telar: ${r.error ?? 'no se pudo'}`); fin(undefined); return; }
        if (llaveBorrador) borradores.delete(llaveBorrador);
        ui.estado(`«${r.datos.destino}»${r.datos.maquina ? ` en ${r.datos.maquina}` : ''}: ${r.datos.como}${r.datos.aviso ? ` · ${r.datos.aviso}` : ''}`,
            r.datos.aviso ? 10000 : 6000);
        if (direccion) adondes.delete(direccion);  // su hilo pudo cambiar (se abrió, se retomó)
        await modelo.sondear();
        fin(r.datos);
    };
    si.addEventListener('click', () => void mandar());
    no.addEventListener('click', cancelar);
    c.addEventListener('cancel', e => { e.preventDefault(); cancelar(); });
    // ⌘⏎ manda desde donde sea (también escribiendo); ⏎ en un botón, el del foco (web/botonera.ts)
    teclasDeBotones(c);
    // un clic afuera (en el fondo, que es del <dialog> mismo) la cierra, como a las demás ventanas
    c.addEventListener('mousedown', e => {
        const r = c.getBoundingClientRect();
        if (e.target === c && (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom)) cancelar();
    });

    mirar(destinos.valor);
    c.showModal();
    nota.focus();
    nota.setSelectionRange(nota.value.length, nota.value.length);  // lo que venía escrito, para seguirlo
    pintarLlega();
    void cargarSkills(destinos.valor);

    // adónde iría su hilo y su contexto (guardado unos minutos: abrirla de nuevo es al tiro)
    if (conEntidad) {
        const llave = direccion || p.fila?.ref || '';
        const guardado = adondes.get(llave);
        const pedido = guardado && Date.now() - guardado.hora < 5 * 60_000 ? Promise.resolve({ datos: guardado.r, error: undefined })
            : cli.adonde(direccion, p.fila);
        void pedido.then(r => {
            if (hecho) return;
            if (!r.datos) adonde = { destino: '', como: '', maquina: '', carpeta: '', nuevo: false, contexto: '', titulo: '', propio: false, falta: r.error ?? 'no sé cuál es su hilo' };
            else { adonde = r.datos; adondes.set(llave, { hora: Date.now(), r: r.datos }); }
            if (adonde.titulo) nombre.textContent = adonde.titulo;
            // el que se pidió, si ahora está; sin hilo propio, viene elegido el primer agente: hay que decir a quién
            let eleccion = querido ?? destinos.valor;
            if (eleccion === '' && adonde.falta) eleccion = agentes[0]?.nombre;
            ponerDestinos(eleccion);
            if (adonde.falta && destinos.valor !== '') ui.estado(adonde.falta, 5000);
            void cargarSkills(destinos.valor);
            pintarLlega();
        });
    }
    return resultado;
}
