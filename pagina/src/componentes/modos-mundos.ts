// Los modos y los mundos: los dos ejes de la página (docs/propuestas/orden-por-modos.md, paso 2). Lo usan la página (la
// banda bajo la cabecera, web/modos.ts y web/mundo.ts) y el catálogo (/componentes#modos-mundos, con datos inventados y
// las variantes que se miraron para elegir dónde viven los controles). La cuenta del mundo por horario (`leerHorario`,
// `mundoAhora`) son funciones puras, con su prueba.
//
// · El modo es una actitud, no un día: táctica (decidir y hacer; la vista de partida), estrategia (mirar con calma), foco
//   (solo la terminal) y todo (ver y buscar todo, sin filtros ni topes; nunca es la de partida). Cada uno dice qué filas
//   de DASHBOARD se ven, cómo va la barra de hilos, la terminal y los avisos. Se distinguen por su ícono; el puesto va en
//   violeta, como la vista que se ve en la barra de una pantalla (componentes/pantalla.ts): un modo es una forma de mirar
//   la página entera.
// · El mundo es una parte de la vida (`[mundos]`): trabajo, personal… o ambos. Filtra la página entera (la barra, el
//   número, las listas, el día). Cambia solo con su horario y a mano; a mano dura hasta el próximo cambio del horario.
//   Se distingue por su color (el suyo, o uno por orden) y lo dice una palabra en él; la línea bajo la cabecera es la
//   de siempre (todas las líneas van del mismo color).
//
//   EN UNA BANDA bajo la cabecera (la variante B, la elegida el 17-nov; en el teléfono también, en una línea):
//   telar 0.13.0                 laptop:Faro            ▬▬▬|▬▬ 45min → 12:30                        ▦ ⚙
//   ───────────────────────────────────────────────────────────────────────────────────────────────
//   ▷ táctica  ◈ estrategia  ◎ foco  ≡ todo                                trabajo
//   ───────────────────────────────────────────────────────────────────────────────────────────────
//
// Da HTML; un clic lleva `data-accion` (`modos-modo`, `modos-mundo`) y `data-id`, como el ítem. Cómo se ve:
// media/css/modos.css.

import { esc, normalizar as norm } from '../estilo';
import { I } from '../web/iconos';

// ───────────────────────── los modos ─────────────────────────

export type ClaveModo = 'tactica' | 'estrategia' | 'foco' | 'todo';

export interface Modo {
    clave: ClaveModo;
    nombre: string;
    /** su ícono de la letra: lo que lo distingue de los otros */
    icono: string;
    /** ⌥⇧ y este número lo pone */
    tecla: string;
    /** qué es, en una línea: su ayuda */
    que: string;
}

/** Los cuatro, en su orden: el de las teclas, la cabecera y ⌥⇧M (el siguiente). */
export const MODOS: readonly Modo[] = [
    { clave: 'tactica', nombre: 'táctica', icono: I.correr, tecla: '1', que: 'decidir y hacer: lo de ahora' },
    { clave: 'estrategia', nombre: 'estrategia', icono: I.capas, tecla: '2', que: 'mirar con calma: proyectos, el tablero y las decisiones' },
    { clave: 'foco', nombre: 'foco', icono: I.foco, tecla: '3', que: 'solo la terminal' },
    { clave: 'todo', nombre: 'todo', icono: I.lista, tecla: '4', que: 'ver y buscar todo, sin filtros ni topes' },
];
export const modo = (clave: string): Modo => MODOS.find(m => m.clave === clave) ?? MODOS[0];

/** El modo al abrir la página: el que estaba puesto, salvo Todo, que nunca es la vista de partida (vuelve a Táctica). */
export const alAbrir = (puesto: string): ClaveModo => (puesto === 'todo' || !MODOS.some(m => m.clave === puesto) ? 'tactica' : puesto as ClaveModo);

// ───────────────────────── el horario de un mundo ─────────────────────────

/** Un tramo del horario: los días (0 domingo … 6 sábado) y de qué minuto a qué minuto del día. `hasta` menor que `desde`
 *  pasa la medianoche (de 22:00 a 2:00: la noche de esos días y la madrugada del siguiente). */
export interface TramoHorario { dias: number[]; desde: number; hasta: number }

/** Los días por su nombre entero, desde el domingo (el 0 de `Date.getDay`): un día se escribe con sus tres primeras
 *  letras o más («mié», «miércoles»). */
const DIAS = ['domingo', 'lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado'];

function leerDia(t: string, todo: string): number {
    const n = norm(t.trim());
    const d = n.length >= 3 ? DIAS.findIndex(x => x.startsWith(n)) : -1;
    if (d < 0) throw new Error(`«${todo}»: «${t}» no es un día (lun, mar, mié, jue, vie, sáb, dom)`);
    return d;
}

function leerHora(t: string, todo: string): number {
    const m = /^(\d{1,2})(?::(\d{2}))?$/.exec(t);
    const h = m ? Number(m[1]) : NaN, min = m?.[2] ? Number(m[2]) : 0;
    if (!m || h > 24 || min > 59 || (h === 24 && min > 0)) throw new Error(`«${todo}»: «${t}» no es una hora (9, 9:00, 19:30)`);
    return h * 60 + min;
}

/** Un tramo como se escribe en `[mundos.<n>] horario`: los días y las horas, cualquiera de los dos puede faltar.
 *  «lun-vie 9:00-19:00», «sáb-dom» (el día entero), «lun,mié,vie 8:30-12», «20:00-23:00» (todos los días), «todos».
 *  Error con lo que no se entiende: la configuración lo dice al leerla. */
export function leerTramo(texto: string): TramoHorario {
    const t = texto.trim();
    const m = /^(?:([a-záéíóúñ,\s-]+?))?\s*(\d{1,2}(?::\d{2})?\s*-\s*\d{1,2}(?::\d{2})?)?$/i.exec(t);
    if (!t || !m || (!m[1] && !m[2])) throw new Error(`«${texto}»: se esperaba algo como «lun-vie 9:00-19:00»`);
    let dias = [0, 1, 2, 3, 4, 5, 6];
    const d = (m[1] ?? '').trim();
    if (d && norm(d) !== 'todos') {
        dias = [];
        for (const parte of d.split(',').map(x => x.trim()).filter(Boolean)) {
            const [a, b] = parte.split('-').map(x => x.trim());
            const i = leerDia(a, texto);
            if (b === undefined) { dias.push(i); continue; }
            const f = leerDia(b, texto);
            for (let k = i; ; k = (k + 1) % 7) { dias.push(k); if (k === f) break; }
        }
    }
    let desde = 0, hasta = 24 * 60;
    if (m[2]) {
        const [a, b] = m[2].split('-').map(x => x.trim());
        desde = leerHora(a, texto);
        hasta = leerHora(b, texto);
        if (desde === hasta) throw new Error(`«${texto}»: el tramo empieza y termina a la misma hora`);
    }
    return { dias: [...new Set(dias)].sort(), desde, hasta };
}

/** `horario` de un mundo: un texto (un tramo) o una lista de tramos. */
export const leerHorario = (h: string | string[] | undefined): TramoHorario[] =>
    (h === undefined ? [] : Array.isArray(h) ? h : [h]).map(leerTramo);

/** Si un instante cae en el tramo (en la hora de esta máquina). */
export function enTramo(t: TramoHorario, f: Date): boolean {
    const dia = f.getDay(), min = f.getHours() * 60 + f.getMinutes();
    if (t.desde < t.hasta) return t.dias.includes(dia) && min >= t.desde && min < t.hasta;
    // pasa la medianoche: la noche de uno de sus días, o la madrugada del día siguiente
    return (t.dias.includes(dia) && min >= t.desde) || (t.dias.includes((dia + 6) % 7) && min < t.hasta);
}

/** Un mundo, para lo que se dibuja: su clave, su nombre, su color (una tinta del tema), su horario, su tema (los
 *  colores de la página mientras rige: componentes/temas.ts; vacío, los del modo), sus modos (las claves de los que
 *  tiene, en su orden: el primero es al que entra la página; vacío, todos) y su arte (el dibujo animado de su tarjeta en
 *  la ventana de mundos: componentes/arte.ts; vacío, el que le toca). */
export interface Mundo { clave: string; nombre: string; color: string; horario?: TramoHorario[]; tema?: string; modos?: string[]; arte?: string }

/** Las tintas de los mundos que no declaran la suya, por orden: no son de ningún estado ni de ninguna acción. */
export const COLORES_MUNDO = ['cian', 'magenta', 'verde', 'azul'] as const;
/** Lo que no calza en ningún mundo (la misma clave que entiende `?mundo=`). */
export const SIN_CLASIFICAR = 'sin-clasificar';

/** El mundo puesto y por qué. `mundo` vacío: ambos (no filtra). */
export interface MundoPuesto {
    mundo: string;
    /** por su horario; fuera de todo horario (el de `fuera`, o ambos); elegido a mano; o no hay horarios: solo a mano */
    por: 'horario' | 'fuera' | 'a-mano' | 'sin-horario';
    /** cuándo cambia solo (el próximo cambio del horario), si cambia en la semana que viene */
    hasta?: Date;
    /** a cuál cambia entonces ('' ambos) */
    luego?: string;
}

/** Lo que dice el horario a esa hora: el mundo cuyo horario la contiene; si ninguno (o más de uno), el de `fuera` ('' ambos). */
export function segunHorario(mundos: readonly Mundo[], f: Date, fuera = ''): { mundo: string; por: 'horario' | 'fuera' } {
    const en = mundos.filter(m => m.horario?.some(t => enTramo(t, f)));
    return en.length === 1 ? { mundo: en[0].clave, por: 'horario' } : { mundo: fuera, por: 'fuera' };
}

/** El próximo instante (en la semana que viene) en que el horario pone otro mundo que el de `f`, y cuál. */
export function proximoCambio(mundos: readonly Mundo[], f: Date, fuera = ''): { hasta: Date; luego: string } | undefined {
    const ahora = segunHorario(mundos, f, fuera).mundo;
    // los bordes de cada tramo, día por día, en orden: basta mirar el mundo justo en cada uno
    const bordes: number[] = [];
    for (let d = 0; d <= 8; d++) {
        const base = new Date(f.getFullYear(), f.getMonth(), f.getDate() + d);
        for (const m of mundos) for (const t of m.horario ?? []) {
            for (const min of [t.desde, t.hasta]) bordes.push(new Date(base.getFullYear(), base.getMonth(), base.getDate(), 0, min).getTime());
        }
    }
    for (const b of [...new Set(bordes)].filter(b => b > f.getTime()).sort((a, b) => a - b)) {
        const otro = segunHorario(mundos, new Date(b), fuera).mundo;
        if (otro !== ahora) return { hasta: new Date(b), luego: otro };
    }
    return undefined;
}

/** El mundo puesto a esa hora. Elegido a mano (`aMano`, con la hora en que se eligió), vale hasta el próximo cambio del
 *  horario que había entonces: así un cambio a mano no se olvida puesto. Sin horarios, el de a mano (o ambos). */
export function mundoAhora(mundos: readonly Mundo[], f: Date, o: { fuera?: string; aMano?: { mundo: string; desde: Date } } = {}): MundoPuesto {
    const fuera = o.fuera ?? '';
    const conHorario = mundos.some(m => m.horario?.length);
    if (!conHorario) return { mundo: o.aMano?.mundo ?? fuera, por: o.aMano ? 'a-mano' : 'sin-horario' };
    if (o.aMano) {
        const vence = proximoCambio(mundos, o.aMano.desde, fuera);
        if (!vence || f < vence.hasta) {
            const despues = vence ? segunHorario(mundos, vence.hasta, fuera).mundo : undefined;
            return { mundo: o.aMano.mundo, por: 'a-mano', hasta: vence?.hasta, luego: despues };
        }
    }
    const { mundo, por } = segunHorario(mundos, f, fuera);
    const p = proximoCambio(mundos, f, fuera);
    return { mundo, por, hasta: p?.hasta, luego: p?.luego };
}

/** «19:00», o «mañana 9:00», «el lunes 9:00», según cuán lejos esté. */
export function cuando(hasta: Date, desde: Date): string {
    const hh = `${hasta.getHours()}:${String(hasta.getMinutes()).padStart(2, '0')}`;
    const dias = Math.round((new Date(hasta.getFullYear(), hasta.getMonth(), hasta.getDate()).getTime()
        - new Date(desde.getFullYear(), desde.getMonth(), desde.getDate()).getTime()) / 864e5);
    if (dias <= 0) return `las ${hh}`;
    if (dias === 1) return `mañana a las ${hh}`;
    return `el ${['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'][hasta.getDay()]} a las ${hh}`;
}

/** Un tramo dicho de vuelta: «lun–vie 9:00–19:00». */
export function decirTramo(t: TramoHorario): string {
    const N = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'];
    const h = (m: number) => `${Math.floor(m / 60)}:${String(m % 60).padStart(2, '0')}`;
    const ds = [...t.dias].sort((a, b) => ((a + 6) % 7) - ((b + 6) % 7));
    const seguidos = ds.length > 2 && ds.every((d, i) => i === 0 || d === (ds[i - 1] + 1) % 7);
    const dias = ds.length === 7 ? 'todos los días' : seguidos ? `${N[ds[0]]}–${N[ds[ds.length - 1]]}` : ds.map(d => N[d]).join(', ');
    return t.desde === 0 && t.hasta === 24 * 60 ? dias : `${dias} ${h(t.desde)}–${h(t.hasta)}`;
}

// ───────────────────────── los modos de cada mundo ─────────────────────────
//
// Cada mundo dice qué modos tiene (`[mundos.<n>] modos`; sin decirlo, todos): en personal no hacen falta táctica ni
// estrategia. Mientras rige, la banda muestra solo esos, sus teclas no ponen otros, y si el modo puesto no es de ellos la
// página pasa al que se tuvo ahí la última vez o al primero de su lista; al volver al otro mundo, vuelve el que se tenía
// ahí. Con ambos, los de los dos juntos.

/** Los modos que tiene el mundo puesto (`puesto`; "" ambos): los suyos, en su orden; con ambos, los de todos juntos (en el
 *  orden de los mundos). null: todos (sin mundos, uno que no los declara, o ambos con alguno que no los declara). */
export function modosDelMundo(mundos: readonly Mundo[], puesto: string): string[] | null {
    if (!mundos.length) return null;
    const m = mundos.find(x => x.clave === puesto);
    if (m) return m.modos?.length ? [...m.modos] : null;
    if (mundos.some(x => !x.modos?.length)) return null;
    return [...new Set(mundos.flatMap(x => x.modos ?? []))];
}

/** Si un modo se puede poner con esos modos (null: todos). */
export const tieneModo = (permitidos: readonly string[] | null, clave: string): boolean => !permitidos || permitidos.includes(clave);

/** El modo que va en un mundo, cuando cambia el mundo (`entra`) o lo que tiene (⚙ mundos). Si el puesto no es de los
 *  suyos, el que tuvo ahí la última vez (`recordado`), si todavía lo tiene, o el primero de su lista que exista: el mundo
 *  se lo impuso (`impuesto`), en lugar de `previo` (el que estaba). Si el puesto sí es de los suyos, se queda, salvo que
 *  lo haya impuesto otro mundo: al entrar, vuelve el que se tuvo ahí o, si no se sabe, el que estaba antes de imponerlo.
 *  Así lo que eligió la persona se respeta, y lo que impuso un mundo se deshace al salir de él. `existentes`: las claves
 *  de los modos que hay. */
export function modoAlEntrar(o: { permitidos: readonly string[] | null; existentes: readonly string[]; actual: string;
    recordado?: string; impuesto: boolean; previo?: string; entra: boolean }): { clave: string; impuesto: boolean; previo: string } {
    const vale = (k: string | undefined): k is string => !!k && o.existentes.includes(k) && tieneModo(o.permitidos, k);
    if (!vale(o.actual)) {
        return { clave: vale(o.recordado) ? o.recordado : o.permitidos?.find(vale) ?? o.actual, impuesto: true,
            previo: o.impuesto && o.previo ? o.previo : o.actual };
    }
    if (o.entra && o.impuesto) {
        const vuelta = vale(o.recordado) ? o.recordado : vale(o.previo) ? o.previo : undefined;
        if (vuelta && vuelta !== o.actual) return { clave: vuelta, impuesto: false, previo: '' };
    }
    return { clave: o.actual, impuesto: o.impuesto, previo: o.impuesto ? o.previo ?? '' : '' };
}

// ───────────────────────── el dibujo ─────────────────────────

/** Dónde viven los controles: A, en la cabecera; B, en una banda propia bajo ella (la elegida); C, en la barra de hilos. */
export type Variante = 'a' | 'b' | 'c';
export const VARIANTES: readonly { clave: Variante; nombre: string; que: string }[] = [
    { clave: 'a', nombre: 'A · en la cabecera', que: 'los cuatro modos junto a la marca (en el teléfono, solo sus íconos y la palabra del puesto) y el mundo a la derecha, antes de los botones' },
    { clave: 'b', nombre: 'B · una banda propia', que: 'el segundo nivel de la cabecera, de borde a borde: los modos a la izquierda y el mundo a la derecha (su nombre y su menú); la cabecera queda con la marca, la máquina y lo que se ve, el día y los botones. En el teléfono también va arriba, en una línea: los íconos de los modos con el puesto en palabra, y el mundo, cortado si no cabe' },
    { clave: 'c', nombre: 'C · en la barra de hilos', que: 'arriba de la barra: el mundo, y los modos como la primera fila de DASHBOARD; la cabecera solo dice el modo y el mundo (para cuando la barra no se ve)' },
];

/** El estilo que pone el color de un mundo (`--mundo-c`): el suyo, tenue si es «sin clasificar», nada si es ambos. */
export const tintaMundo = (m: Mundo | undefined): string => (m ? ` style="--mundo-c: var(--${esc(m.color)})"` : '');

/** Los cuatro modos, en una fila: el ícono de cada uno en su celda, el puesto en violeta y con su nombre; los demás, con
 *  su nombre solo si hay lugar (`.txt`, que la cabecera esconde con poco ancho). Ninguno lleva número. Con `solo`, los
 *  que tiene el mundo puesto (el puesto, siempre). */
export function modosEnFila(puesto: ClaveModo, o: { clase?: string; propio?: string; solo?: readonly string[] | null } = {}): string {
    return `<nav class="modos-fila${o.clase ? ` ${o.clase}` : ''}">${modosAdentro(puesto, o)}</nav>`;
}

/** Lo de adentro de la fila (la cabecera de la página lo pone en su `<nav>`). `propio`: el nombre del modo propio que
 *  está puesto, armado sobre `puesto`: va junto a su base. `solo`: los que tiene el mundo puesto (`modosDelMundo`; null,
 *  todos): los demás no van, salvo el puesto. */
export function modosAdentro(puesto: ClaveModo, o: { propio?: string; solo?: readonly string[] | null } = {}): string {
    return MODOS.filter(m => m.clave === puesto || tieneModo(o.solo ?? null, m.clave)).map(m => {
        const si = m.clave === puesto;
        const propio = si && o.propio ? `<span class="modos-propio"> · ${esc(o.propio)}</span>` : '';
        return `<a class="modos-modo${si ? ' si' : ''}" data-accion="modos-modo" data-id="${m.clave}" title="${esc(`${m.nombre}: ${m.que} (⌥⇧${m.tecla})`)}">`
            + `<span class="i">${m.icono}</span><span class="txt">${esc(m.nombre)}</span>${propio}</a>`;
    }).join('');
}

/** Lo que dice el mundo puesto, en una línea: su nombre en su color y, tenue, hasta cuándo (y si fue a mano). */
export function decirMundo(p: MundoPuesto, mundos: readonly Mundo[], ahora: Date): { nombre: string; como: string; ayuda: string } {
    const m = mundos.find(x => x.clave === p.mundo);
    const nombre = m?.nombre ?? 'ambos';
    const luego = p.luego === undefined ? '' : mundos.find(x => x.clave === p.luego)?.nombre ?? 'ambos';
    const hasta = p.hasta ? cuando(p.hasta, ahora) : '';
    const como = p.por === 'a-mano' ? `a mano${hasta ? `, hasta ${hasta}` : ''}` : hasta ? `hasta ${hasta}` : '';
    const horario = mundos.filter(x => x.horario?.length).map(x => `${x.nombre}: ${x.horario!.map(decirTramo).join(', ')}`).join(' · ');
    const ayuda = `${m ? `el mundo: ${nombre}` : 'ambos mundos: todo junto, en tandas'}`
        + `${p.por === 'a-mano' ? ' (elegido a mano)' : p.por === 'horario' ? ' (por su horario)' : p.por === 'fuera' ? ' (fuera de todo horario)' : ''}`
        + `${hasta ? ` · a ${hasta} pasa a ${luego}` : ''}${horario ? `\nhorario: ${horario}` : ''}\nclic o ⌘M: cambiar de mundo · ⌥⇧0 el siguiente`;
    return { nombre, como, ayuda };
}

/** El mundo, como botón: el planeta y su nombre, en su color (ambos, en el del texto), como los modos a su izquierda (el
 *  ícono delante, en su celda); hasta cuándo y si fue a mano, en su ayuda (18-nov: verlo no hacía falta). Un clic abre la
 *  ventana de mundos (componentes/mundos-ventana.ts). */
export function mundoBoton(p: MundoPuesto, mundos: readonly Mundo[], ahora: Date, clase = ''): string {
    const d = decirMundo(p, mundos, ahora);
    const m = mundos.find(x => x.clave === p.mundo);
    return `<a class="mundo-boton${clase ? ` ${clase}` : ''}${m ? '' : ' ambos'}" data-accion="modos-mundo" title="${esc(d.ayuda)}"${tintaMundo(m)}>`
        + `<span class="i mundo-icono">${I.planeta}</span><span class="mundo-nombre">${esc(d.nombre)}</span></a>`;
}

/** Lo que iba en el menú del mundo (web/interfaz.ts `menu`): cada mundo con su horario (el de `fuera`, que rige fuera de
 *  todo horario), ambos, volver al horario si se eligió a mano, y lo sin clasificar. En la página lo reemplazó la ventana
 *  de mundos (componentes/mundos-ventana.ts, 23-nov); queda en el prototipo del catálogo, que muestra cómo era. */
export function opcionesMundo(p: MundoPuesto, mundos: readonly Mundo[], sinClasificar: number, fuera = ''): { id: string; label: string; description?: string; icono?: string; color?: string; separador?: boolean }[] {
    const marca = (k: string) => (p.mundo === k ? I.hecha : ' ');
    return [
        ...mundos.map(m => ({ id: m.clave, label: m.nombre, icono: marca(m.clave), color: m.color,
            description: m.horario?.length ? m.horario.map(decirTramo).join(', ') : m.clave === fuera ? 'fuera de todo horario' : 'sin horario' })),
        { id: '', label: 'ambos', icono: marca(''), description: 'todo junto, en tandas' },
        { id: '', label: '', separador: true },
        ...p.por === 'a-mano' ? [{ id: '__horario', label: 'volver al horario', icono: I.reloj, color: 'azul' }] : [],
        ...sinClasificar ? [{ id: '__sin', label: `${sinClasificar} sin clasificar`, icono: I.etiqueta, description: 'se ven en todos los mundos, al final' }] : [],
        { id: '__editar', label: 'editar los mundos…', icono: I.config, color: 'amarillo', description: 'qué es de cada uno, su horario' },
    ];
}

/** Lo que va en el menú de los modos (el teléfono de la variante A, o la cabecera de la C): los cuatro con su tecla. */
export function opcionesModo(puesto: ClaveModo): { id: string; label: string; description: string; icono: string; color?: string }[] {
    return MODOS.map(m => ({ id: m.clave, label: m.nombre, icono: m.icono, color: m.clave === puesto ? 'violeta' : undefined,
        description: `${m.que} · ⌥⇧${m.tecla}` }));
}
