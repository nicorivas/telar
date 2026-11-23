// La ficha de un ítem de una pestaña de lectura: un proveedor con `pestana` y `vista = "lectura"` (un feed de cosas
// para leer). Es la misma ficha que la de una tarea (`telar tarea`, el contrato de una página: título, subtítulo,
// bloques y acciones, y cuatro campos más que solo usa esta vista: `temas`, `fuente`, `fecha` y `estado`), dibujada
// para leerla con calma y no para despacharla:
//
// - arriba, tranquilo, el carril (la palabra de `avance` de su fila, en su color) y los temas, el título, de dónde viene
//   y «leer el original» (su acción `tipo: abrir`);
// - el texto con serifa, a un ancho de lectura; lo que el curador anota (el bloque `destacado`) con la raya de su color
//   colgando en el margen;
// - al lado, en el margen, «conexiones» (relaciones.ts): una tarjeta por cada relación que propone la ficha y, debajo,
//   por cada nota de la casa que nombra el texto (una ruta escrita como código: `docs/x.md`, `obra/y/`, o la `nota` de
//   un tema; una carpeta, por su documento). Cada tarjeta se titula con la nota y dice lo que dice la nota, con sus
//   palabras: su documento se lee aquí (`/api/hilos/documento`), sin el frontmatter ni los metadatos, y de él salen su
//   título, su resumen y su comienzo (`deLaNota`); del grafo de conocimiento (el módulo «grafo», si la máquina lo
//   tiene), con qué conecta. Cualquiera se conecta desde ahí, y ninguna entra si no se elige. Un clic en una tarjeta (o
//   en la nota, en el texto) la expande en su lugar, sin que el texto se mueva: la nota para leerla, con sus
//   conexiones, y al final la relación para crearla. Una ruta que no está, o una carpeta sin documento, lo dice: en su
//   tarjeta, y en el texto;
// - en la barra (tareas.ts), además de ← →, el ícono de la instrucción: abre un hilo nuevo con la lectura, con lo que
//   la ficha tiene como contexto (`paraUnHilo`), en la ventana de siempre (web/instruccion.ts);
// - al final, «tu lectura»: una caja para el porqué y las acciones, sin números. Una acción que `pide` texto lleva lo
//   escrito ahí. Al responder la ficha se queda, con lo anotado (`estado`), y abajo «sigue» con el título del próximo.
//
// Angosto (el celular), todo va en una columna: el texto, «conexiones», tu lectura y lo que sigue. Sus estilos, en
// media/css/leer.css.

import * as cli from '../../cli';
import { circulo } from '../../componentes/circulo';
import { pieza } from '../../componentes/item';
import { esc } from '../../estilo';
import { I } from '../../web/iconos';
import * as guardado from '../../web/guardado';
import * as ui from '../../web/ui';
import { mdSimple } from './pagina';
import { NOMBRE_PRI, marcasLectura } from './fila-tarea';
import { deLaNota } from './nota';
import * as relaciones from './relaciones';

/** Lo que la ficha necesita además de la página: la fila del ítem en la lista (su color, sus etiquetas, su avance), el
 *  ítem que sigue y el anterior en la pestaña, y lo que se respondió aquí si la ficha todavía no lo dice. */
export interface Contexto {
    pagina: cli.JsonPagina;
    fila?: cli.JsonFila & { etiquetas?: string[] };
    siguiente?: { titulo: string };
    anterior?: { titulo: string };
    /** lo anotado en esta pasada («✓ me interesa: porque…»), si la ficha releída no trae su `estado` */
    anotado?: string;
    /** la clave donde se guarda el borrador del porqué (web/guardado.ts) */
    clave: string;
}

const llano = (t: string) => t.toLowerCase().normalize('NFD').replace(/[^\p{L}\p{N}]/gu, '');

/** «escribirle a Claude» del proveedor es la instrucción (el ícono de la barra), no una respuesta. */
const esEscribir = (a: cli.JsonAccionPagina) => !!(a.al_hilo && a.mensaje && a.pide);

/** Lo de arriba. Los temas, la fuente y la fecha los dice la ficha; si no los trae, se adivinan: los temas son las
 *  etiquetas de su fila que no son el carril, y lo que queda del subtítulo sin el carril ni los temas es de dónde viene. */
function encabezado(c: Contexto): { carril: string; color: string; temas: { nombre: string; nota: string }[]; procedencia: string } {
    const p = c.pagina;
    const carril = (c.fila?.avance ?? '').split(' ')[0].split(':')[0];
    const temas = p.temas
        ? p.temas.map(t => (typeof t === 'string' ? { nombre: t, nota: '' } : { nombre: t.nombre, nota: t.nota ?? '' }))
        : (c.fila?.etiquetas ?? []).filter(e => llano(e) !== llano(carril) && e !== 'equipo' && e !== 'sin-tema').map(nombre => ({ nombre, nota: '' }));
    let procedencia = [p.fuente, p.fecha].filter(Boolean).join(' · ');
    if (!procedencia) {
        const fuera = new Set([llano(carril), llano(temas.map(t => t.nombre).join(', ')), ...temas.map(t => llano(t.nombre))]);
        procedencia = (p.subtitulo ?? '').split(' · ').filter(s => !fuera.has(llano(s))).join(' · ');
    }
    return { carril, color: c.fila?.color || 'verde', temas, procedencia };
}

/** Lo que necesita la ventana de la instrucción (web/instruccion.ts) para abrir un hilo con esta lectura: un hilo nuevo,
 *  que se llama como ella, con lo que la ficha ya tiene como contexto libre (va entero, debajo de lo pedido). Una
 *  lectura no es una entidad con hilo propio (no hay «su hilo»): por eso no va como fila ni con dirección, que la
 *  llevaría al agente de los pendientes; si la ficha trae su dirección, va escrita en el texto, para que el hilo la
 *  nombre. Lo que va: el título, el enlace al original, de dónde viene y su fecha, los temas, cada bloque (el resumen,
 *  el porqué, de dónde salió, con sus enlaces), lo respondido (`estado`, o lo anotado en esta pasada) y lo escrito en
 *  «tu lectura» sin responder (`escrito`). `pestana`: el nombre de la pestaña, para decir de dónde vino. */
export function paraUnHilo(c: Contexto, escrito = '', pestana = 'leer'): { titulo: string; nombre: string; contexto: cli.ContextoLibre } {
    const p = c.pagina;
    const e = encabezado(c);
    const enlace = (p.acciones ?? []).find(a => a.tipo === 'abrir' && a.enlace)?.enlace ?? c.fila?.url ?? '';
    const una = (t: string) => t.replace(/\s+/g, ' ').trim();
    const lineas: string[] = [`lectura: ${una(p.titulo)}`];
    const direccion = c.fila?.direccion || p.direccion || '';
    if (direccion) lineas.push(`dirección: ${direccion}`);
    if (enlace) lineas.push(`original: ${enlace}`);
    if (e.procedencia) lineas.push(`de dónde viene: ${una(e.procedencia)}`);
    if (e.temas.length) lineas.push(`temas: ${e.temas.map(t => (t.nota ? `${t.nombre} (${t.nota})` : t.nombre)).join(', ')}`);
    if (c.fila?.id) lineas.push(`id en el feed: ${c.fila.id}`);
    for (const b of p.bloques) {
        const items = (b.items ?? []).map(x => `- ${una(x.titulo)}${x.enlace && !x.titulo.includes(x.enlace) ? ` (${x.enlace})` : ''}`);
        if (!b.texto?.trim() && !items.length) continue;
        lineas.push('', `${b.titulo ? una(b.titulo) : 'nota'}:`);
        if (b.texto?.trim()) lineas.push(b.texto.trim());
        lineas.push(...items);
    }
    const estado = (p.estado || c.anotado || '').trim();
    if (estado) lineas.push('', `lo que respondí: ${estado}`);
    if (escrito.trim()) lineas.push('', 'lo que escribí en «tu lectura», sin responder:', escrito.trim());
    const titulo = una(p.titulo);
    return { titulo, nombre: titulo, contexto: { titulo, texto: lineas.join('\n'), origen: `la pestaña «${pestana}»` } };
}

/** El HTML de la ficha. */
export function html(c: Contexto): string {
    const p = c.pagina;
    const e = encabezado(c);
    const acciones = (p.acciones ?? []).map((a, k) => ({ a, k })).filter(({ a }) => !esEscribir(a));
    const original = acciones.find(({ a }) => a.tipo === 'abrir' && a.enlace);
    // las de solo ícono (volver a procesar) van en la barra (tareas.ts)
    const decidir = acciones.filter(x => x !== original && !x.a.solo_icono);
    const tema = (t: { nombre: string; nota: string }) => (t.nota
        ? `<a class="tema" data-nota="${esc(t.nota)}" title="${esc(t.nota)}: abrirla al lado">${esc(t.nombre)}</a>`
        : `<span class="tema">${esc(t.nombre)}</span>`);
    // arriba de todo, lo que la puso adelante en la lista: su prioridad (el círculo y la palabra, en su color) y «tuya»
    // si la dejó la persona misma; sin eso, nada
    const [pri, suya] = marcasLectura(c.fila ?? {});
    const n = typeof c.fila?.prioridad === 'number' ? c.fila.prioridad : null;
    const marcas = (pri && n !== null ? `<span class="marca tono-${pri.tono}" title="${esc(pri.ayuda ?? '')}">${pieza(pri, 'marca-i')} ${esc(NOMBRE_PRI[n] ?? '')}</span>` : '')
        + (suya ? `<span class="marca tono-acento" title="${esc(suya.ayuda ?? '')}"><span class="i">${I.persona}</span> tuya</span>` : '');
    const cab = '<header class="cab-leer">'
        + `<div class="dateline">${marcas}${e.carril ? `<span class="carril" style="color: var(--${esc(e.color)})">${esc(e.carril)}</span>` : ''}`
        + e.temas.map(tema).join('') + '</div>'
        + `<h1>${esc(p.titulo)}</h1>`
        + `<div class="procedencia">${esc(e.procedencia)}`
        + (original ? ` <a class="original" data-accion="accion-tarea" data-valor="${original.k}" title="${esc(original.a.enlace ?? '')}${original.a.principal ? ' (⏎)' : ''}">leer el original <span class="i">${I.externo}</span></a>` : '')
        + '</div></header>';
    // volviendo a procesar: un agente rehace la ficha; esta se relee sola hasta que termina (tareas.ts)
    const procesando = p.procesando ? `<div class="procesando"><span class="tono-trabajando">${circulo({ mov: 'gira' })}</span>`
        + ` volviendo a procesar desde las ${esc(p.procesando)}: la ficha se pone al día sola</div>` : '';
    const bloques = p.bloques.map(b => {
        const items = (b.items ?? []).map(x => `<li>${x.enlace ? `<a data-leer-enlace="${esc(x.enlace)}" title="${esc(x.enlace)}">${esc(x.titulo)}</a>` : esc(x.titulo)}</li>`).join('');
        return `<section class="bloque-leer${b.destacado ? ' anotacion' : ''}"${b.destacado ? ` style="--c: var(--${esc(b.color ?? e.color)})"` : ''}>`
            + (b.titulo ? `<div class="rotulo">${esc(b.titulo)}</div>` : '')
            + (b.texto ? `<div class="prosa">${mdSimple(b.texto)}</div>` : '')
            + (items ? `<ul class="fuentes">${items}</ul>` : '')
            + '</section>';
    }).join('');
    const estado = p.estado || c.anotado || '';
    const respuesta = `<section class="respuesta-leer" style="--c: var(--${esc(e.color)})">`
        + `<div class="rotulo">tu lectura</div>`
        + (estado ? `<div class="anotado"><span class="i">${I.hecha}</span> ${esc(estado)}</div>` : '')
        + `<textarea id="leer-porque" rows="4" placeholder="${estado ? 'si quieres, otra respuesta…' : 'qué te dejó, por qué sí o por qué no…'}"></textarea>`
        + `<div class="decidir">${decidir.map(({ a, k }) => {
            const tono = /^✓/.test(a.nombre) ? ' si' : /^✗/.test(a.nombre) ? ' no' : '';
            // la que guarda las relaciones elegidas dice cuántas van
            const lleva = a.comando?.some(w => w.includes('{conexiones}')) ? ' <span class="lleva-rel" data-lleva-rel></span>' : '';
            return `<a class="decision${tono}" data-leer-accion="${k}" title="${esc(a.pide ? `${a.nombre}, con lo escrito arriba` : a.nombre)}">${esc(a.nombre)}${lleva}</a>`;
        }).join('')}</div>`
        + '</section>';
    const seguir = c.siguiente || c.anterior ? `<nav class="seguir${estado ? ' listo' : ''}">`
        + (c.siguiente ? `<a data-accion="tarea-siguiente" title="el siguiente (→)"><span class="rotulo">sigue</span> <span class="que">${esc(c.siguiente.titulo)}</span> <span class="i">${I.adelante}</span></a>` : '')
        + (c.anterior ? `<a class="antes" data-accion="tarea-anterior" title="el anterior (←)"><span class="i">${I.anterior}</span> el anterior</a>` : '')
        + '</nav>'
        // respondida la última, se dice que no queda más, en vez de nada
        : estado ? '<nav class="seguir listo"><span class="rotulo">no queda nada más para leer</span></nav>' : '';
    // en la grilla: el texto, la respuesta y lo que sigue en la columna de lectura; el margen al lado, quieto. Angosto,
    // una columna en este orden, con el margen entre el texto y la respuesta. En el margen, «conexiones»
    // (relaciones.ts)
    return `<div id="leer" class="leer"><article class="texto-leer">${procesando}${cab}${bloques}</article>`
        + '<aside class="margen-leer"><div class="relaciones-leer"></div></aside>'
        + `${respuesta}${seguir}</div>`;
}

// ── las notas que nombra el texto ────────────────────────────────────────────────

/** Una ruta escrita como código (`docs/x.md`, `obra/ia-empleo/`): con al menos una barra y sin espacios. */
const ES_RUTA = /^~?\/?(?:[\p{L}\p{N}_.@+-]+\/)+(?:[\p{L}\p{N}_.@+-]+)?$/u;

interface Arista {
    origen: string; tipo: string; destino: string; titulo_destino?: string; titulo_origen?: string; porque?: string;
    estado?: string;
}
/** Lo que el grafo sabe de una nota (`/api/modulos/grafo/vecinos`): su nodo y sus aristas. */
interface Vecinos { nodo?: { titulo?: string }; salientes?: Arista[]; entrantes?: Arista[] }
interface Conexion { ruta: string; titulo: string; tipo: string; sale: boolean; porque: string }

/** Lo que se sabe de una nota: su documento, y lo que dice (de él, no del grafo: el resumen del grafo a veces es su
 *  línea de metadatos) y sus conexiones (del grafo). */
interface Nota {
    /** su documento: el de una carpeta, por la regla de nota.ts (`documentoDeCarpeta`) */
    doc: string;
    /** por qué no se puede leer: no está, o es una carpeta sin documento */
    ilegible?: string;
    titulo: string;
    /** lo que dice, en markdown: su resumen (para la tarjeta plegada) y su comienzo (para leerla expandida) */
    resumen: string; comienzo: string;
    /** si el documento sigue después del comienzo */
    sigue: boolean;
    /** sus conexiones en el grafo; undefined sin el grafo, o si no las pudo leer */
    conexiones?: Conexion[];
}

/** Lo que se sabe de cada nota, pedido una vez por página. */
const sabidas = new Map<string, Promise<Nota>>();
/** la máquina no tiene el módulo «grafo»: no se le vuelve a preguntar */
let sinGrafo = false;

const NO_ESTA = 'no está en el repositorio';

const { nombreDe } = relaciones;

// ── de dónde se sabe ─────────────────────────────────────────────────────────────

type Doc = { markdown?: string; texto?: string; archivo?: string; archivos?: { nombre: string }[]; error?: string };

/** Un archivo o una carpeta de la raíz, como lo da `/api/hilos/documento`; undefined si no respondió. */
async function documento(archivo: string): Promise<Doc | undefined> {
    try {
        const r = await fetch(`/api/hilos/documento?hilo=&archivo=${encodeURIComponent(archivo)}`, { cache: 'no-store' });
        return r.ok ? await r.json() as Doc : undefined;
    } catch { return undefined; }
}

/** Lo que el grafo sabe de un documento; undefined sin el módulo, o si no pudo. */
async function vecinosDe(doc: string): Promise<Vecinos | undefined> {
    if (sinGrafo) return undefined;
    try {
        const r = await fetch(`/api/modulos/grafo/vecinos?ruta=${encodeURIComponent(doc)}`, { cache: 'no-store' });
        if (r.status === 404) sinGrafo = true;
        return r.ok ? await r.json() as Vecinos : undefined;
    } catch { return undefined; }
}

/** Lo que se sabe de una nota, por su ruta (como la escribe el texto): de una carpeta, primero cuál es su documento. Lo
 *  que dice, del documento; con qué conecta, del grafo. «no existe» es lo que dice la API de un archivo que no está; de
 *  una carpeta que está, en cambio, da lo que tiene y ningún archivo. */
async function leerNota(ruta: string): Promise<Nota> {
    const vacia: Nota = { doc: '', titulo: '', resumen: '', comienzo: '', sigue: false };
    let doc = ruta;
    if (relaciones.esCarpeta(ruta)) {
        const d = await documento(ruta);
        if (!d) return vacia;
        if (d.error || d.archivo) return { ...vacia, ilegible: NO_ESTA };
        const elegido = relaciones.documentoDeCarpeta((d.archivos ?? []).map(a => a.nombre));
        if (!elegido) return { ...vacia, ilegible: 'una carpeta sin README.md ni un solo .md' };
        doc = ruta + elegido;
    }
    const [d, v] = await Promise.all([documento(doc), vecinosDe(doc)]);
    if (d && (d.error || d.texto === 'no existe')) return { ...vacia, doc, ilegible: NO_ESTA };
    const dice = deLaNota(d?.markdown ?? d?.texto ?? '');
    return { doc, ...dice, titulo: dice.titulo || v?.nodo?.titulo || '', conexiones: v ? conexiones(v) : undefined };
}

function saber(ruta: string): Promise<Nota> {
    let p = sabidas.get(ruta);
    if (!p) { p = leerNota(ruta); sabidas.set(ruta, p); }
    return p;
}

/** Las conexiones de una nota, una por documento (el otro), con su tipo y su porqué; las que salen primero. */
function conexiones(v: Vecinos): Conexion[] {
    const vistos = new Set<string>();
    const todas = [
        ...(v.salientes ?? []).filter(a => a.estado !== 'roto')
            .map(a => ({ ruta: a.destino, titulo: a.titulo_destino || nombreDe(a.destino), tipo: a.tipo, sale: true, porque: a.porque ?? '' })),
        ...(v.entrantes ?? []).map(a => ({ ruta: a.origen, titulo: a.titulo_origen || nombreDe(a.origen), tipo: a.tipo, sale: false, porque: a.porque ?? '' })),
    ];
    return todas.filter(x => !/^https?:/.test(x.ruta) && !vistos.has(x.ruta) && (vistos.add(x.ruta), true));
}

/** Lo de una nota en su tarjeta expandida (relaciones.ts), para leerla: dónde está (un clic la abre entera en el
 *  visor), su comienzo en la letra de la lectura y «seguir leyendo»; después, con qué conecta en el grafo (las primeras
 *  `cuantas`; las demás, a un clic), cada una también al visor, una línea por conexión con su porqué al pasar el mouse. */
function htmlNota(n: Nota, cuantas = 5): string {
    const cs = n.conexiones ?? [];
    const lista = cs.slice(0, cuantas).map(x => `<li title="${esc(x.porque.replace(/`/g, ''))}"><span class="tipo">${x.sale ? '→' : '←'} ${esc(x.tipo)}</span> `
        + `<a data-abrir-nota="${esc(x.ruta)}" title="${esc(x.ruta)}: abrirla en el visor">${esc(x.titulo)}</a></li>`).join('');
    const grafo = n.conexiones === undefined
        ? (sinGrafo ? '<div class="ayuda">sin el grafo de conocimiento no se ven sus conexiones</div>' : '')
        : cs.length ? `<div class="rotulo">conecta con ${cs.length}</div><ul class="conexiones-leer">${lista}</ul>`
            + (cs.length > cuantas ? `<a class="mas-conexiones" data-mas="${esc(n.doc)}">las otras ${cs.length - cuantas}</a>` : '')
        : '<div class="rotulo">todavía sin conexiones en el grafo</div>';
    return '<div class="nota-leer">'
        + `<div class="ruta-nota"><a data-abrir-nota="${esc(n.doc)}" title="abrirla entera en el visor">${esc(n.doc)} <span class="i">${I.externo}</span></a></div>`
        + (n.comienzo ? `<div class="comienzo-nota">${mdSimple(n.comienzo)}</div>` : '<div class="ayuda">la nota no tiene texto todavía</div>')
        + (n.sigue ? `<a class="seguir-leyendo" data-abrir-nota="${esc(n.doc)}" title="abrirla entera en el visor">seguir leyendo <span class="i">${I.externo}</span></a>` : '')
        + (grafo ? `<div class="grafo-nota">${grafo}</div>` : '')
        + '</div>';
}

/** Después de pintar: las rutas del texto como notas, el margen con lo que puede ir al grafo, la caja del porqué con su
 *  borrador (sobrevive a recargar la página), y los clics. `correr(k, texto)`: la acción `k` del proveedor con lo
 *  escrito. */
export function montar(raiz: HTMLElement, c: Contexto, correr: (k: number, texto: string, conexiones?: string) => void): void {
    const leer = raiz.querySelector<HTMLElement>('.leer');
    if (!leer) return;
    // las notas que nombra (como el servidor, que revisa con ellas lo que se conecta: telar.servicios.tareas,
    // `notas_nombradas`): las rutas del texto, que pasan a abrirse al lado, y las de los temas. Una absoluta (`~/x`,
    // `/x/y`) se abre, pero no es de ningún grafo
    const nombradas: relaciones.Nombrada[] = [];
    const nombrar = (ruta: string, enTexto: boolean) => {
        if (!/^[~/]/.test(ruta) && !nombradas.some(n => n.ruta === ruta)) nombradas.push({ ruta, enTexto });
    };
    for (const code of leer.querySelectorAll<HTMLElement>('.texto-leer .prosa code')) {
        const t = code.textContent ?? '';
        if (!ES_RUTA.test(t)) continue;
        const a = document.createElement('a');
        a.className = 'nota'; a.dataset.nota = t; a.textContent = t; a.title = `${t}: abrirla al lado, con sus conexiones`;
        code.replaceWith(a);
        nombrar(t, true);
    }
    for (const t of leer.querySelectorAll<HTMLElement>('.cab-leer .tema[data-nota]')) if (t.dataset.nota) nombrar(t.dataset.nota, false);
    const caja = leer.querySelector<HTMLTextAreaElement>('#leer-porque');
    if (caja) guardado.caja(caja, c.clave);

    // «conexiones» (relaciones.ts): las propuestas y las otras que nombra, cada una con lo que dice su nota (que se va
    // leyendo); la acción que las guarda dice cuántas van. Las nombradas van solo si hay con qué guardarlas (una acción
    // con `{conexiones}`); si no, se abren desde el texto, en el visor
    const contRel = leer.querySelector<HTMLElement>('.relaciones-leer');
    const guarda = (c.pagina.acciones ?? []).some(a => a.comando?.some(w => w.includes('{conexiones}')));
    const rels = relaciones.leer(c.pagina, c.clave, guarda ? nombradas : []);
    const tipos = c.pagina.tipos ?? [];
    /** lo que se sabe de cada nota (por su ruta), cuando llega */
    const sabido = new Map<string, Nota>();
    /** las notas cuyas conexiones se ven todas, no solo las primeras */
    const todas = new Set<string>();
    const fuera = relaciones.fueraDelTexto(leer, rels);
    /** la tarjeta expandida (-1: ninguna); una a la vez */
    let abierta = -1;
    const marcar = (ruta: string) => { for (const x of leer.querySelectorAll<HTMLElement>('a.nota, a.tema')) x.classList.toggle('abierta', !!ruta && x.dataset.nota === ruta); };
    const deSuNota = (r: relaciones.Relacion): relaciones.DeLaNota => {
        const n = sabido.get(r.ruta);
        if (!n) return {};
        return { titulo: n.titulo, resumen: n.resumen ? mdSimple(n.resumen) : '', nota: htmlNota(n, todas.has(n.doc) ? Infinity : 5),
            conexiones: n.conexiones?.length };
    };
    const pintarRel = () => {
        if (!contRel) return;
        // el campo del porqué que se está escribiendo sigue igual después: con el foco y el cursor donde estaban
        const foco = document.activeElement;
        const campo = foco instanceof HTMLTextAreaElement && foco.dataset.relCampo !== undefined && contRel.contains(foco)
            ? { i: foco.dataset.relCampo, a: foco.selectionStart, b: foco.selectionEnd } : undefined;
        contRel.innerHTML = relaciones.html(rels, tipos, deSuNota, fuera, abierta);
        if (campo) {
            const otro = contRel.querySelector<HTMLTextAreaElement>(`[data-rel-campo="${campo.i}"]`);
            otro?.focus({ preventScroll: true });
            otro?.setSelectionRange(campo.a, campo.b);
        }
        marcar(rels[abierta]?.ruta ?? '');
        const n = relaciones.elegidas(rels).length;
        for (const x of leer.querySelectorAll<HTMLElement>('[data-lleva-rel]')) x.textContent = !rels.length ? '' : n ? `· con ${n} ${n === 1 ? 'relación' : 'relaciones'}` : '· sin relaciones';
    };
    /** una carpeta nombrada cuyo documento ya está en otra tarjeta (la propone la ficha, o el texto lo nombra también
     *  por su archivo) sobra: queda la primera */
    const quitarRepetidas = () => {
        const vistas = new Set<string>();
        for (let i = 0; i < rels.length; i++) {
            const nota = rels[i].nota;
            if (!nota || !vistas.has(nota)) { if (nota) vistas.add(nota); continue; }
            rels.splice(i, 1);
            if (abierta === i) abierta = -1; else if (abierta > i) abierta--;
            i--;
        }
    };
    let pendiente = 0;
    const pintarPronto = () => { cancelAnimationFrame(pendiente); pendiente = requestAnimationFrame(() => { if (contRel?.isConnected) pintarRel(); }); };
    pintarRel();
    // cada nota, cuando llega: su documento (el de una carpeta), su título, si se puede leer; la de una ruta que no
    // está se dice también en el texto
    for (const r of [...rels]) {
        void saber(r.ruta).then(n => {
            sabido.set(r.ruta, n);
            if (n.doc && r.nombrada) r.nota = n.doc;
            if (n.titulo) r.titulo = n.titulo;
            if (n.ilegible) {
                r.ilegible = n.ilegible;
                for (const x of leer.querySelectorAll<HTMLElement>('a.nota')) {
                    if (x.dataset.nota === r.ruta) { x.classList.add('ilegible'); x.title = `${r.ruta}: ${n.ilegible}`; }
                }
            }
            quitarRepetidas();
            pintarPronto();
        });
    }
    relaciones.escribir(leer, rels, tipos, c.clave, pintarRel);
    /** si el comienzo de una tarjeta no se ve, se lleva a la vista: ancho, en el margen (que se mueve solo);
     *  angosto, en la página, bajo su barra */
    const aLaVista = (el: HTMLElement | null | undefined) => {
        const cont = getComputedStyle(leer).display === 'grid' ? leer.querySelector<HTMLElement>('.margen-leer') : leer.closest<HTMLElement>('.v-dia');
        if (!el || !cont) return;
        const a = el.getBoundingClientRect(), b = cont.getBoundingClientRect();
        if (a.top < b.top || a.top > b.bottom - 80) cont.scrollBy({ top: a.top - b.top - 60, behavior: 'smooth' });
    };
    /** expande la tarjeta `i` (otra vez, la pliega; `quedarse`: si ya está expandida, la deja), y la trae a la vista. La
     *  de una nota que no se puede leer no se expande: solo se trae a la vista */
    const abrir = (i: number, quedarse = false) => {
        if (rels[i]?.ilegible) { aLaVista(contRel?.querySelector<HTMLElement>(`.rel[data-rel="${i}"]`)); return; }
        abierta = abierta === i && !quedarse ? -1 : i;
        pintarRel();
        if (rels[abierta]) aLaVista(contRel?.querySelector<HTMLElement>(`.rel[data-rel="${abierta}"]`));
    };
    // al pasar por una relación, se ilumina en el texto la frase en que se apoya
    leer.addEventListener('mouseover', e => {
        const li = (e.target as Element).closest<HTMLElement | SVGElement>('.relaciones [data-rel]');
        const r = li ? rels[Number(li.dataset.rel)] : undefined;
        relaciones.iluminar(leer, r?.ancla ?? '', r ? relaciones.colorDe(tipos, r.tipo) : undefined);
    });
    // sin nada que llevar al grafo, no hay margen: el texto solo, al centro
    const aside = leer.querySelector<HTMLElement>('.margen-leer');
    if (!rels.length && aside) { aside.hidden = true; leer.classList.add('sin-notas'); }

    leer.addEventListener('click', e => {
        const t = e.target as HTMLElement;
        const listo = () => { e.preventDefault(); e.stopPropagation(); };
        if (relaciones.clic(e, leer, rels, tipos, c.clave, pintarRel, abrir)) return;
        // una nota en el texto (o un tema): su tarjeta, expandida; si no tiene (una ruta absoluta), al visor
        const n = t.closest<HTMLElement>('[data-nota]');
        if (n) {
            listo();
            const ruta = n.dataset.nota ?? '';
            const i = rels.findIndex(r => r.ruta === ruta || r.nota === ruta);
            // sin tarjeta, al visor: una carpeta, en su documento
            if (i >= 0) abrir(i, true); else void saber(ruta).then(x => ui.abrirArchivo(x.doc || ruta));
            return;
        }
        const mas = t.closest<HTMLElement>('[data-mas]');
        if (mas) { listo(); todas.add(mas.dataset.mas ?? ''); pintarRel(); return; }
        const an = t.closest<HTMLElement>('[data-abrir-nota]');
        if (an) { listo(); void ui.abrirArchivo(an.dataset.abrirNota ?? ''); return; }
        // una tarjeta: un clic la expande; expandida, un clic en su cabecera la pliega (en lo de adentro, se lee)
        const tj = t.closest<HTMLElement>('[data-rel-abrir]');
        if (tj) {
            if (tj.classList.contains('abierta') && !t.closest('.tarjeta-cabecera')) return;
            listo();
            abrir(Number(tj.dataset.relAbrir));
            return;
        }
        const en = t.closest<HTMLElement>('[data-leer-enlace]');
        if (en) {
            listo();
            const x = en.dataset.leerEnlace ?? '';
            if (/^https?:\/\//.test(x)) void ui.abrirExterno(x); else void ui.abrirArchivo(x);
            return;
        }
        const d = t.closest<HTMLElement>('[data-leer-accion]');
        if (d) {
            listo();
            const k = d.dataset.leerAccion ?? '';
            const pide = c.pagina.acciones?.[Number(k)]?.pide;
            // pide un porqué y la caja está vacía: se pide ahí mismo, sin otra ventana; otro clic la manda sin él
            if (pide && caja && !caja.value.trim() && caja.dataset.pidio !== k) {
                caja.dataset.pidio = k;
                caja.placeholder = `${pide}… (o vuelve a apretar «${d.textContent?.replace(/^[✓✗]\s*/, '') ?? ''}»: sin porqué)`;
                caja.focus();
                return;
            }
            const lleva = c.pagina.acciones?.[Number(k)]?.comando?.some(w => w.includes('{conexiones}'));
            correr(Number(k), caja?.value.trim() ?? '', lleva ? JSON.stringify(relaciones.elegidas(rels)) : undefined);
        }
    });
}

/** Lo escrito ya se mandó con una respuesta: el borrador se borra. */
export function olvidarBorrador(clave: string): void { guardado.guardar(clave, ''); guardado.guardar(`${clave}:relaciones`, ''); }
