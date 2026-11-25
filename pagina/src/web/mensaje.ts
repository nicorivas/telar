// Lo que hace la barra de mensaje (componentes/mensaje.ts) en cualquier lugar de la página: escribirle a un hilo o a un
// agente sobre la cosa que se mira, sin abrir una ventana. Por dentro es la instrucción de siempre (web/instruccion.ts,
// docs/propuestas/instruccion.md): adónde iría «su hilo» lo dice telar (`POST /actuar/adonde`) y lo escrito sale por
// `telar actuar` (`POST /actuar`) con el contexto de la cosa (su dirección, o la fila que la pantalla ya tiene) o un
// contexto libre. La diferencia es la forma: una fila, sin skill ni «dejarla escrita»; lo escrito llega tal cual (un
// «/tarea revisa…» empieza con la skill, como la escribiría la ventana).
//
// Cómo se usa: la vista pone `barra({ direccion, fila, sobre: 'T84' })` donde quiere la fila (su HTML), y nada más: el
// estado de cada barra (el destino elegido, lo último que pasó) vive aquí por su llave (la dirección de la cosa), y lo
// escrito y no mandado, en el borrador de esa cosa, el mismo de la ventana de la instrucción (abrirla trae lo que se
// escribió aquí, y al revés). Repintar la vista no pierde nada: la barra sale igual, con lo escrito; el foco y el cursor
// los devuelve `alPintar` (el dashboard lo llama al pintar).
//
// · el destino de fábrica: el de la instrucción. Con una cosa, «su hilo» (el de su proyecto, que dice telar); si no tiene,
//   el de `[instruccion] destino` y si no, el primer agente. Sin cosa (un contexto libre), `[instruccion] destino` o uno
//   nuevo. La vista puede pedir otro (`a`).
// · elegir otro: un clic en el destino abre la lista junto a él (ui.menu: un filtro y filas `item()`): su hilo, uno nuevo
//   y, como en ⌘K y en su orden (web/buscador-hilos.ts), los hilos y después los agentes, con sus íconos. Solo los del
//   mundo puesto: ni hilos ni agentes de otro mundo, ni los de un agente que pide esconderse (`esconder`), tampoco en
//   el modo todo.
// · las teclas: ⏎ envía, ⇧⏎ es una línea nueva (la regla de una caja en una fila, como la de la terminal y la de la
//   conversación; ⌘⏎ también envía), ⎋ suelta el campo. Solo mientras se escribe en ella: no toma el foco sola, ni al
//   pintarse ni al llegar su hilo, así que no le quita teclas a la terminal ni a otra caja; y las letras escritas en ella
//   no llegan a los atajos del dashboard.
// · después de enviar: arriba del campo, a quién fue (su nombre abre su hilo) y cómo le llegó; si falló, por qué, y lo
//   escrito vuelve al campo.

import * as cli from '../cli';
import { modelo } from '../modelo';
import { barraMensaje, dijoMensaje, type DestinoMensaje, type DijoMensaje } from '../componentes/mensaje';
import { leer as leerEscrito, guardar as guardarEscrito } from './guardado';
import { agentesNombrados, hilosNombrados, porPeso } from './buscador-hilos';
import { C, I } from './iconos';
import * as ui from './ui';

/** El valor de «un hilo nuevo» (el mismo de la ventana de la instrucción: un hilo no se puede llamar así). */
export const NUEVO = '+nuevo';

/** Lo que pone la vista: de qué se habla y lo que viene pedido. */
export interface ContextoMensaje {
    /** la cosa de la que se habla (`tarea:T84`): su contexto va con lo escrito */
    direccion?: string;
    /** la fila de un pendiente que la pantalla ya tiene: ahorra buscarla, y nombra uno sin dirección */
    fila?: cli.FilaConocida;
    /** un texto del que se habla que no es una cosa (un chat): va entero debajo de lo escrito */
    contexto?: cli.ContextoLibre;
    /** cómo se nombra la cosa en el campo vacío («T84»); sin esto, su dirección */
    sobre?: string;
    /** el destino de entrada: '' su hilo, `NUEVO`, o el nombre de un hilo o un agente (lo elegido a mano gana) */
    a?: string;
    /** sin cosa, con un hilo nuevo: cómo se llama */
    nombre?: string;
    /** de qué es la barra, si no es la dirección de la cosa (ni su ref) */
    llave?: string;
    /** al llegar: lo que la vista quiera hacer (foco olvida la ficha guardada: su historia cambió) */
    alEnviar?: (r: cli.JsonActuado) => void;
}

/** Lo que se sabe de una barra, por su llave. */
export interface Estado {
    c: ContextoMensaje;
    llave: string;
    /** adónde iría «su hilo» (telar); `leyendo` mientras se pregunta */
    adonde?: cli.JsonAdonde;
    leyendo?: Promise<void>;
    /** lo que pasó con lo último que se mandó */
    dijo?: DijoMensaje;
    enviando?: boolean;
}

/** Lo escrito y no mandado de una cosa, con a quién: el borrador de la ventana de la instrucción (la skill es suya; aquí
 *  se deja como estaba). */
interface Borrador { texto: string; a: string; skill: string }
const borrador = (llave: string) => leerEscrito<Borrador>(`instruccion:${llave}`);
function guardarBorrador(llave: string, cambios: Partial<Borrador>): void {
    const antes = borrador(llave) ?? { texto: '', a: '', skill: '' };
    const b = { ...antes, ...cambios };
    // sin nada escrito no hay borrador: lo elegido vive igual en el estado de la barra mientras dure la página
    guardarEscrito(`instruccion:${llave}`, b.texto.trim() ? b : undefined);
}

const barras = new Map<string, Estado>();
/** lo elegido a mano en cada barra (sobrevive a que se escriba y se borre todo) */
const elegidos = new Map<string, string>();
/** Adónde iría «su hilo» de cada cosa, por unos minutos (como la ventana de la instrucción). */
const adondes = new Map<string, { hora: number; r: cli.JsonAdonde }>();

const llaveDe = (c: ContextoMensaje): string =>
    c.llave || c.direccion || c.fila?.direccion || c.fila?.ref || (c.contexto ? `contexto:${c.contexto.origen ?? ''}|${c.contexto.titulo ?? ''}` : 'mensaje');
const conCosa = (c: ContextoMensaje): boolean => !!(c.direccion || c.fila);

/** La dirección de un hilo para abrirlo (con su máquina, si es de otra). */
const direccionHilo = (nombre: string, maquina = '') => `hilo:${encodeURIComponent(nombre)}${maquina ? `@${maquina}` : ''}`;

/** Lo que se le puede elegir, en el mundo puesto (web/buscador-hilos.ts, `puesto`): los hilos y los agentes. Uno de otra
 *  máquina, solo con bus (le llega por él). */
export function elegibles(): { hilos: ReturnType<typeof hilosNombrados>; agentes: ReturnType<typeof agentesNombrados> } {
    return {
        hilos: porPeso(hilosNombrados('puesto').filter(h => !h.hilo.remoto || modelo.hayBus)),
        agentes: porPeso(agentesNombrados('puesto')),
    };
}

/** Cómo le llega a un hilo de la lista, en pocas palabras (como la ventana de la instrucción). */
function comoLlega(h: cli.JsonHilo): string {
    if (h.vivo) return h.remoto ? `en ${h.remoto}: por el bus` : 'abierto: se le escribe';
    return `${h.archivado ? 'archivado' : 'cerrado'}: se retoma${h.remoto ? ` en ${h.remoto}` : ''}`;
}

/** Un hilo como destino: su nombre, el ícono que le pone ⌘K y su azul. */
function deHilo(h: cli.JsonHilo, valor = h.nombre, detalle = comoLlega(h)): DestinoMensaje {
    return { valor, nombre: cli.nombreVisible(h), icono: h.archivado ? I.archivar : h.vivo ? I.lleno : I.vacio, color: C.ir, detalle };
}

/** «su hilo», cuando telar dijo cuál: un hilo, uno que se le abre, o un agente que se lo encarga. */
function suHilo(a: cli.JsonAdonde): DestinoMensaje {
    const detalle = ({ hilo: 'su hilo: se le escribe', dormido: 'su hilo: se retoma con su conversación', abrir: `su hilo: se le abre uno en ${a.carpeta || 'la raíz'}`,
        agente: 'agente: se le encarga, en un hilo hijo', bus: `su hilo, en ${a.maquina}: le llega por el bus` } as Record<string, string>)[a.como] ?? 'su hilo';
    if (a.como === 'agente') return { valor: '', nombre: a.destino, icono: I.agente, color: C.agente, detalle };
    if (a.como === 'abrir' && !a.propio) return { valor: '', nombre: a.destino || 'hilo nuevo', icono: I.nuevo, color: C.hecho, detalle };
    const h = modelo.hilos.find(x => x.nombre === a.destino);
    return h ? deHilo(h, '', detalle) : { valor: '', nombre: a.destino, icono: I.lleno, color: C.ir, detalle };
}

/** Un nombre (de un hilo o de un agente) como destino; undefined si no se le puede mandar desde aquí (otro mundo). */
function porNombre(nombre: string): DestinoMensaje | undefined {
    const { hilos, agentes } = elegibles();
    const ag = agentes.find(x => x.nombre === nombre);
    if (ag) return { valor: nombre, nombre, icono: I.agente, color: C.agente, detalle: 'agente: se le encarga' };
    const h = hilos.find(x => x.nombre === nombre)?.hilo;
    return h ? deHilo(h) : undefined;
}

const NUEVO_DESTINO = (e: Estado): DestinoMensaje => ({ valor: NUEVO, nombre: 'hilo nuevo', icono: I.nuevo, color: C.hecho,
    detalle: conCosa(e.c) ? `uno nuevo para esto, en ${e.adonde?.carpeta || 'la raíz'}` : e.c.nombre ? `«${e.c.nombre}», en la raíz` : 'en la raíz' });

/** El destino de una barra: lo elegido a mano (o lo pedido, o lo del borrador), y si no, el de fábrica. */
export function destinoDe(e: Estado): { destino: DestinoMensaje; buscando: boolean } {
    // (un borrador sin destino, «», es el de fábrica: no pide nada)
    const querido = elegidos.get(e.llave) ?? (borrador(e.llave)?.a || undefined) ?? e.c.a;
    if (querido === NUEVO) return { destino: NUEVO_DESTINO(e), buscando: false };
    // sin los hilos leídos todavía (la página recién abierta), no se sabe quién se ve: se espera, en vez de caer en otro
    // (un pedido que no se encuentra caería en uno nuevo)
    if (!modelo.leido) return { destino: { valor: querido ?? '', nombre: querido || 'su hilo', icono: I.lleno, color: C.ir, detalle: 'leyendo los hilos…' }, buscando: true };
    if (querido) {
        const d = porNombre(querido);
        if (d) return { destino: d, buscando: false };
        // uno pedido que no está en ninguna parte (todavía: la lista se relee) no cae en otro sin decirlo: se espera, y si no
        // aparece, se pide elegir; uno de otro mundo, sí, al de fábrica (no se le manda nada a lo que no se ve)
        const existe = modelo.hilos.some(h => h.nombre === querido) || modelo.secciones.some(x => x.grupo === 'agentes' && x.nombre === querido);
        if (!existe) return { destino: { valor: querido, nombre: querido, icono: I.vacio, color: C.quitar, detalle: 'no lo encuentro: elige a quién' }, buscando: true };
    }
    if (conCosa(e.c)) {
        if (!e.adonde) return { destino: { valor: '', nombre: 'su hilo', icono: I.lleno, color: C.ir, detalle: 'buscando cuál…' }, buscando: true };
        if (!e.adonde.falta) return { destino: suHilo(e.adonde), buscando: false };
    }
    // sin su hilo, como la ventana: el primer agente (de los del mundo puesto), y la barra dice por qué
    if (conCosa(e.c)) {
        const primero = agentesNombrados('puesto')[0];
        if (primero) return { destino: { valor: primero.nombre, nombre: primero.nombre, icono: I.agente, color: C.agente,
            detalle: `agente: se le encarga (${e.adonde?.falta || 'no tiene hilo propio'})` }, buscando: false };
        return { destino: NUEVO_DESTINO(e), buscando: false };
    }
    // sin cosa (un contexto libre): el de `[instruccion] destino`, o uno nuevo
    const deFabrica = modelo.instruccionA ? porNombre(modelo.instruccionA) : undefined;
    return { destino: deFabrica ?? NUEVO_DESTINO(e), buscando: false };
}

function placeholder(e: Estado, d: DestinoMensaje): string {
    const sobre = e.c.sobre || e.c.direccion || e.c.fila?.ref || e.c.contexto?.titulo || '';
    const a = d.valor === NUEVO ? 'a un hilo nuevo' : d.nombre === 'su hilo' ? 'a su hilo' : d.nombre;
    return `escríbele ${d.valor === NUEVO || d.nombre === 'su hilo' ? a : `a ${a}`}${sobre ? ` sobre ${sobre}` : ''} · ⏎ envía, ⇧⏎ línea nueva`;
}

/** Las props de la barra, de su estado. */
function props(e: Estado): Parameters<typeof barraMensaje>[0] {
    const { destino, buscando } = destinoDe(e);
    return { llave: e.llave, destino, buscando, texto: borrador(e.llave)?.texto ?? '', placeholder: placeholder(e, destino), dijo: e.dijo };
}

/** Preguntarle a telar adónde iría «su hilo» (una vez cada unos minutos por cosa); al llegar, la barra lo dice. */
function preguntar(e: Estado): void {
    if (!conCosa(e.c) || e.adonde || e.leyendo) return;
    const llave = e.c.direccion || e.c.fila?.ref || '';
    const g = adondes.get(llave);
    if (g && Date.now() - g.hora < 5 * 60_000) { e.adonde = g.r; return; }
    e.leyendo = cli.adonde(e.c.direccion ?? e.c.fila?.direccion ?? '', e.c.fila).then(r => {
        e.adonde = r.datos ?? { destino: '', como: '', maquina: '', carpeta: '', nuevo: false, contexto: '', titulo: '', propio: false, falta: r.error ?? 'no sé cuál es su hilo' };
        if (r.datos) adondes.set(llave, { hora: Date.now(), r: r.datos });
        e.leyendo = undefined;
        refrescar(e.llave);
    });
}

/** La barra de mensaje de una cosa, en HTML (componentes/mensaje.ts), con lo que se sabe de ella. La vista la pone donde
 *  quiere; lo demás lo atiende `atender`. */
export function barra(c: ContextoMensaje): string {
    const llave = llaveDe(c);
    let e = barras.get(llave);
    if (!e) { e = { c, llave }; barras.set(llave, e); } else e.c = c;
    preguntar(e);
    return barraMensaje(props(e));
}

/** Las barras de esa llave en la página (puede haber más de una: el catálogo). */
const enLaPagina = (llave: string, raiz: ParentNode = document): HTMLElement[] =>
    [...raiz.querySelectorAll<HTMLElement>('.mensaje[data-mensaje]')].filter(x => x.dataset.mensaje === llave);

/** Poner al día lo que se ve de una barra sin tocar su campo (lo escrito, el foco y el cursor siguen): el destino, lo
 *  último que pasó, enviar y lo que dice el campo vacío. */
export function refrescar(llave: string): void {
    const e = barras.get(llave);
    if (!e) return;
    const t = document.createElement('template');
    t.innerHTML = barraMensaje(props(e));
    const nueva = t.content.firstElementChild as HTMLElement;
    for (const el of enLaPagina(llave)) {
        el.className = nueva.className;
        el.classList.toggle('ocupada', !!e.enviando);
        el.querySelector('.mensaje-destino')?.replaceWith(nueva.querySelector('.mensaje-destino')!.cloneNode(true));
        const campo = el.querySelector<HTMLTextAreaElement>('.mensaje-campo');
        if (campo) { campo.placeholder = nueva.querySelector<HTMLTextAreaElement>('.mensaje-campo')!.placeholder; campo.setAttribute('aria-label', campo.placeholder); }
        el.querySelector('.mensaje-enviar')?.classList.toggle('listo', !!campo?.value.trim());
        const dijo = el.querySelector('.mensaje-dijo');
        if (e.dijo) {
            const t2 = document.createElement('template');
            t2.innerHTML = dijoMensaje(e.dijo);
            if (dijo) dijo.replaceWith(t2.content.firstElementChild!); else el.prepend(t2.content.firstElementChild!);
        } else dijo?.remove();
    }
}

/** El campo crece con lo escrito, hasta su tope (mensaje.css): después corre por dentro. */
function crecer(campo: HTMLTextAreaElement): void {
    campo.style.height = 'auto';
    campo.style.height = `${campo.scrollHeight}px`;
}

/** Cómo le llegó, en palabras: lo que dice telar (sin repetir «enviado», que ya dice la línea). */
function comoFue(r: cli.JsonActuado): string {
    return [r.maquina ? `en ${r.maquina}` : '', r.como === 'enviado' ? '' : r.como, r.aviso].filter(Boolean).join(' · ');
}

/** Mandar lo escrito en la barra `llave`. Devuelve lo que pasó (undefined si no salió). */
export async function enviar(llave: string): Promise<cli.JsonActuado | undefined> {
    const e = barras.get(llave);
    const el = enLaPagina(llave)[0];
    const campo = el?.querySelector<HTMLTextAreaElement>('.mensaje-campo');
    if (!e || !campo || e.enviando) return undefined;
    const texto = campo.value.trim();
    if (!texto) { campo.focus(); return undefined; }
    // mientras se sabe a quién (su hilo, que dice telar; los hilos, recién abierta la página), se espera un poco
    if (e.leyendo) await e.leyendo;
    for (let i = 0; i < 40 && destinoDe(e).buscando; i++) await new Promise(r => setTimeout(r, 250));
    const { destino, buscando } = destinoDe(e);
    if (buscando) {
        e.dijo = { estado: 'error', texto: modelo.leido && destino.valor ? `no encuentro a «${destino.valor}»: elige a quién` : 'todavía no sé a quién: prueba en un momento' };
        refrescar(llave);
        return undefined;
    }
    if (destino.valor === '' && e.adonde?.falta) {
        e.dijo = { estado: 'error', texto: e.adonde.falta };
        refrescar(llave);
        return undefined;
    }
    const pedido: cli.PedidoInstruccion = {
        nota: texto,
        ...(e.c.direccion ? { direccion: e.c.direccion } : {}), ...(e.c.fila ? { fila: e.c.fila } : {}),
        ...(destino.valor === NUEVO ? { nuevo: true } : destino.valor ? { a: destino.valor } : {}),
        ...(destino.valor === NUEVO && !conCosa(e.c) && e.c.nombre ? { nombre: e.c.nombre } : {}),
        ...(e.c.contexto ? { contexto: e.c.contexto } : {}),
    };
    // lo escrito sale del campo al tiro (y del borrador); si no llega, vuelve
    e.enviando = true;
    e.dijo = { estado: 'enviando', destino: destino.valor === NUEVO ? 'un hilo nuevo' : destino.nombre, texto: '' };
    for (const x of enLaPagina(llave)) { const c = x.querySelector<HTMLTextAreaElement>('.mensaje-campo'); if (c) { c.value = ''; crecer(c); } }
    guardarBorrador(llave, { texto: '' });
    refrescar(llave);
    const r = await cli.actuar(pedido);
    e.enviando = false;
    if (!r.datos) {
        e.dijo = { estado: 'error', destino: e.dijo.destino, texto: r.error ?? 'no se pudo' };
        for (const x of enLaPagina(llave)) {
            const c = x.querySelector<HTMLTextAreaElement>('.mensaje-campo');
            if (c && !c.value.trim()) { c.value = texto; crecer(c); }
        }
        guardarBorrador(llave, { texto });
        refrescar(llave);
        return undefined;
    }
    e.dijo = { estado: 'llego', destino: r.datos.destino, direccion: direccionHilo(r.datos.destino, r.datos.maquina), texto: comoFue(r.datos) };
    // su hilo pudo cambiar (se abrió, se retomó): la próxima vez se pregunta de nuevo
    adondes.delete(e.c.direccion || e.c.fila?.ref || '');
    if (destino.valor === '') { e.adonde = undefined; preguntar(e); }
    refrescar(llave);
    e.c.alEnviar?.(r.datos);
    void modelo.sondear();
    return r.datos;
}

/** Las opciones de la lista de destinos (ui.menu): su hilo, uno nuevo, los hilos y los agentes del mundo puesto, en el
 *  orden y con los íconos de ⌘K. Cada una con el valor que se elige. */
export function opciones(e: Estado): (ui.Opcion & { valor: string })[] {
    const r: (ui.Opcion & { valor: string })[] = [];
    if (conCosa(e.c) && e.adonde && !e.adonde.falta) {
        const s = suHilo(e.adonde);
        r.push({ valor: '', label: `su hilo · ${s.nombre}`, description: s.detalle, icono: s.icono, color: s.color });
    }
    // uno nuevo: para la cosa, si telar dice que se le puede abrir uno; sin cosa, siempre (en la raíz)
    if (!conCosa(e.c) || e.adonde?.nuevo) { const n = NUEVO_DESTINO(e); r.push({ valor: NUEVO, label: 'hilo nuevo', description: n.detalle, icono: n.icono, color: n.color }); }
    const { hilos, agentes } = elegibles();
    const suyo = e.adonde && !e.adonde.falta ? e.adonde.destino : '';
    const otros = hilos.filter(h => h.nombre !== suyo);
    if (otros.length) {
        r.push({ valor: '', label: 'hilos', separador: true });
        for (const h of otros) r.push({ valor: h.nombre, label: h.titulo, description: h.detalle || comoLlega(h.hilo), icono: h.icono, color: C.ir });
    }
    const ags = agentes.filter(a => a.nombre !== suyo || e.adonde?.como !== 'agente');
    if (ags.length) {
        r.push({ valor: '', label: 'agentes', separador: true });
        for (const a of ags) r.push({ valor: a.nombre, label: a.titulo, description: 'agente: se le encarga', icono: a.icono, color: C.agente });
    }
    return r;
}

/** Elegir a quién, en la lista junto al destino; lo elegido queda para esa barra (y en su borrador). */
export async function elegirDestino(llave: string, junto?: Element): Promise<string | undefined> {
    const e = barras.get(llave);
    if (!e) return undefined;
    if (e.leyendo) await e.leyendo;
    const ops = opciones(e);
    // junto al destino: debajo, o encima si no cabe (la barra suele ir al pie)
    const elegida = await ui.menu(ops, junto, 'a quién');
    if (!elegida) return undefined;
    elegidos.set(llave, elegida.valor);
    const b = borrador(llave);
    if (b) guardarBorrador(llave, { a: elegida.valor });
    refrescar(llave);
    return elegida.valor;
}

/** Antes de repintar una vista: si se está escribiendo en una barra suya, cuál y dónde está el cursor. */
export function foco(raiz: ParentNode): { llave: string; desde: number; hasta: number } | undefined {
    const a = document.activeElement;
    if (!(a instanceof HTMLTextAreaElement) || !a.classList.contains('mensaje-campo') || !(raiz as Node).contains(a)) return undefined;
    const llave = a.closest<HTMLElement>('.mensaje')?.dataset.mensaje;
    return llave === undefined ? undefined : { llave, desde: a.selectionStart, hasta: a.selectionEnd };
}

/** Después de pintar: cada campo, de su alto; y el foco y el cursor de vuelta donde estaban (solo si estaban ahí: la barra
 *  nunca toma el foco sola). */
export function alPintar(raiz: ParentNode, antes?: { llave: string; desde: number; hasta: number }): void {
    for (const c of raiz.querySelectorAll<HTMLTextAreaElement>('.mensaje-campo')) if (c.value) crecer(c);
    if (!antes) return;
    const c = enLaPagina(antes.llave, raiz)[0]?.querySelector<HTMLTextAreaElement>('.mensaje-campo');
    if (!c) return;
    c.focus();
    c.setSelectionRange(antes.desde, antes.hasta);
}

let atendiendo = false;

/** Atiende las barras de toda la página (una vez, al arrancar): escribir, enviar, elegir a quién y abrir a quién fue. */
export function atender(doc: Document = document): void {
    if (atendiendo) return;
    atendiendo = true;
    // cuando cambian los hilos o los agentes (se abrió uno, se leyeron), el destino de cada barra a la vista, al día
    modelo.cambio.event(() => { for (const llave of barras.keys()) if (enLaPagina(llave).length) refrescar(llave); });
    const de = (t: EventTarget | null) => (t as Element | null)?.closest?.<HTMLElement>('.mensaje[data-mensaje]');
    doc.addEventListener('input', ev => {
        const c = ev.target as HTMLTextAreaElement;
        if (!c.classList?.contains('mensaje-campo')) return;
        const llave = de(c)?.dataset.mensaje;
        if (llave === undefined) return;
        crecer(c);
        // con a quién va (el elegido, o el que se ve): abrir la ventana de la instrucción sobre lo mismo lo trae igual
        const e = barras.get(llave);
        const a = elegidos.get(llave) ?? (e && !destinoDe(e).buscando ? destinoDe(e).destino.valor : undefined);
        guardarBorrador(llave, { texto: c.value, ...(a !== undefined ? { a } : {}) });
        de(c)?.querySelector('.mensaje-enviar')?.classList.toggle('listo', !!c.value.trim());
    });
    doc.addEventListener('keydown', ev => {
        const el = de(ev.target);
        if (!el) return;
        const llave = el.dataset.mensaje!;
        const enCampo = (ev.target as Element).classList.contains('mensaje-campo');
        // ⏎ envía (y ⌘⏎); ⇧⏎ es una línea nueva; mientras se compone una letra con acento, ⏎ es de la composición
        if (enCampo && ev.key === 'Enter' && !ev.shiftKey && !ev.isComposing) { ev.preventDefault(); ev.stopPropagation(); void enviar(llave); return; }
        if (ev.key === 'Escape' && enCampo) { ev.preventDefault(); ev.stopPropagation(); (ev.target as HTMLElement).blur(); return; }
        // en el destino o en enviar, con el teclado: ⏎ y espacio los aprietan
        if (!enCampo && (ev.key === 'Enter' || ev.key === ' ')) { ev.preventDefault(); ev.stopPropagation(); (ev.target as HTMLElement).click(); return; }
        // lo demás que se escribe aquí es del campo: no llega a los atajos de una letra del dashboard (con ⌘, ⌃ o ⌥, sí:
        // ⌘K y los de la página valen desde donde sea)
        if (enCampo && !ev.metaKey && !ev.ctrlKey && !ev.altKey) ev.stopPropagation();
    });
    doc.addEventListener('click', ev => {
        const t = ev.target as Element | null;
        const el = de(t);
        if (!el) return;
        const llave = el.dataset.mensaje!;
        const destino = t?.closest('[data-mensaje-destino]');
        if (destino) {
            ev.preventDefault(); ev.stopPropagation();
            void elegirDestino(llave, destino).then(v => { if (v !== undefined) enLaPagina(llave)[0]?.querySelector<HTMLTextAreaElement>('.mensaje-campo')?.focus(); });
            return;
        }
        if (t?.closest('[data-mensaje-enviar]')) { ev.preventDefault(); ev.stopPropagation(); void enviar(llave); return; }
        const abrir = t?.closest<HTMLElement>('[data-mensaje-abrir]');
        if (abrir?.dataset.mensajeAbrir) { ev.preventDefault(); ev.stopPropagation(); void ui.abrirDireccion(abrir.dataset.mensajeAbrir); }
    });
}

/** Lo que se sabe de la barra `llave` (las pruebas, y quien quiera su lista: `opciones(estado(llave))`). */
export const estado = (llave: string): Estado | undefined => barras.get(llave);

/** Para las pruebas: olvidar lo de cada barra. */
export function olvidar(): void { barras.clear(); elegidos.clear(); adondes.clear(); }
