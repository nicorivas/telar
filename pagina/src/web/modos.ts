// Los modos de la página (docs/propuestas/orden-por-modos.md y modos.md, telar.modos): las cuatro actitudes, táctica
// (decidir y hacer; la de partida), estrategia (mirar con calma), foco (solo la terminal) y todo (ver y buscar todo), y
// los propios, armados sobre una de ellas (su `base`). Cada uno es un nombre con valores para la disposición (la barra
// de hilos, la ficha de un agente, la cabecera…), la terminal (ancho, posición, fondo), los avisos, el tema (los
// colores), la densidad (cuánto aire lleva cada fila) y las filas de DASHBOARD (`filas`). Las definiciones vienen de la
// API (las de fábrica y las de `[modos]`); cuál está puesto, y los cambios a mano que se hicieron estando en él, son de
// este navegador. Cambiar de modo descarta esos cambios; ⚙ modos los guarda.
//
// Lo que aplica se ve en `body`: un `data-<ajuste>` por cada ajuste de disposición y de avisos, que el CSS lee
// (media/css/marco.css), y `data-modo`, la base del puesto. La barra, la ficha y la terminal escuchan `alCambiar` y se
// redibujan; quien muestra la vista de cada modo escucha `alPoner` (solo cuando la persona lo pone). El mundo es otro
// eje (web/mundo.ts): un modo puede ponerlo al ponerse (`mundo`, o una de sus `etiquetas` que se llame como un mundo).
// Qué agentes residentes se ven (`agentes`, web/modos-agentes.ts) no es un cambio a mano: la grilla de ⚙ modos lo guarda
// al tiro en el modo que se toca, sea o no el puesto.
//
// El tema (los colores) es lo único que el mundo le puede ganar al modo: si el mundo puesto declara uno (`[mundos.<n>]
// tema`), ese, y cambia solo cuando el mundo cambia (a su hora, o a mano). Elegido a mano en ⚙ modos, el tema dura hasta
// cambiar de modo o hasta entrar a un mundo con tema (`tema`, y la regla en componentes/temas.ts, `queRige`).
//
// Cada mundo dice además qué modos tiene (`[mundos.<n>] modos`; sin decirlo, todos; con ambos, los de todos juntos):
// mientras rige, solo esos se pueden poner (un clic, una tecla o el siguiente con otro no hace nada), y la banda muestra
// solo esos. Al entrar a un mundo (a su hora o a mano) que no tiene el modo puesto, la página pasa al último que se tuvo
// ahí, o al primero de su lista; y al volver al otro mundo, al que se tenía ahí. Lo que la persona eligió, si el mundo
// lo tiene, se queda (componentes/modos-mundos.ts, `modoAlEntrar`). Lo que se tuvo en cada mundo es de este navegador.
// Un modo que dice su mundo (`mundo`) se queda puesto al entrar a ese mundo, si el mundo lo tiene.

import * as cli from '../cli';
import { I } from './iconos';
import * as temas from '../componentes/temas';
import * as densidades from '../componentes/densidades';
import { MODOS as ACTITUDES, modoAlEntrar, tieneModo } from '../componentes/modos-mundos';
import * as mundo from './mundo';
import * as colores from './colores';
import * as agentesModo from './modos-agentes';
import { partesDeFilas } from './modos-pestanas';

export type Valor = string | number;
export interface Ajuste { clave: string; grupo: string; nombre: string; opciones: string[]; ayuda: string }
export interface Modo {
    clave: string; nombre: string; valores: Record<string, Valor>; de_fabrica: boolean; cambiado: boolean;
    /** sobre cuál de las cuatro actitudes se arma: la suya, si es de fábrica */
    base?: string;
    /** los ajustes que dice su tabla (`[modos.<clave>]`); los demás, de fábrica o de su base */
    propios?: string[];
    /** de esos, lo que diría cada uno sin su línea */
    heredados?: Record<string, Valor>;
    /** de dónde sale sin su línea lo que no es de su fábrica: la clave del modo que lo dice */
    origenes?: Record<string, string>;
}

const CLAVE_ACTIVO = 'telar.modo', CLAVE_ANTERIOR = 'telar.modo.anterior', CLAVE_CAMBIOS = 'telar.modo.cambios';
/** lo que se aplica como atributo de `body`, para el CSS */
const EN_BODY = ['barra', 'lado', 'cabecera', 'acciones', 'escribir', 'avisos', 'aviso_version'];

// hasta que conteste la API, los de fábrica (los mismos de telar.modos.DE_FABRICA, sin la terminal)
let modos: Modo[] = [
    { clave: 'tactica', nombre: 'táctica', base: 'tactica', de_fabrica: true, cambiado: false, valores: {
        barra: 'abierta', lado: 'abierto', cabecera: 'visible', acciones: 'visible', escribir: 'oculta',
        pantalla_completa: 'no', etiquetas: '', sin_etiqueta: 'se-ven', agentes: '', proyectos: '', negocios: '', iniciativas: '', agrupar_iniciativas: '', area: '', glifos: 'no', iconos: 'simbolos', campo: '',
        filas: 'tactica, calendario', mundo: '', avisos: 'todos', aviso_version: 'visible', tema: 'telar', densidad: 'auto' } },
    { clave: 'estrategia', nombre: 'estrategia', base: 'estrategia', de_fabrica: true, cambiado: false, valores: {
        filas: 'proyectos, bloque:tablero, bloque:registro', avisos: 'urgentes' } },
    { clave: 'foco', nombre: 'foco', base: 'foco', de_fabrica: true, cambiado: false, valores: {
        barra: 'oculta', lado: 'oculto', cabecera: 'oculta', acciones: 'oculta', escribir: 'oculta', pantalla_completa: 'no',
        columnas: 110, posicion: 'centro', fondo: 'ninguno', avisos: 'urgentes', aviso_version: 'oculto' } },
    { clave: 'todo', nombre: 'todo', base: 'todo', de_fabrica: true, cambiado: false, valores: { filas: '*' } },
];
let catalogo: Ajuste[] = [];
let leidos = false;
const oyentes = new Set<() => void>();

const leerLocal = <T>(clave: string, defecto: T): T => {
    try { const v = localStorage.getItem(clave); return v === null ? defecto : JSON.parse(v) as T; } catch { return defecto; }
};
const guardarLocal = (clave: string, valor: unknown) => {
    try { localStorage.setItem(clave, JSON.stringify(valor)); } catch { /* sin almacén: solo esta vez */ }
};

/** Los nombres de antes que siguen valiendo (telar.modos.ALIAS): lo que este navegador tenía puesto como «estandar» es
 *  «tactica». */
const ALIAS: Record<string, string> = { estandar: 'tactica' };
const conAlias = (clave: string): string => ALIAS[clave] ?? clave;
let activo: string = conAlias(leerLocal(CLAVE_ACTIVO, 'tactica'));
let anterior: string = conAlias(leerLocal(CLAVE_ANTERIOR, 'tactica'));
/** los cambios a mano en el modo puesto: valen hasta cambiar de modo */
let cambios: Record<string, Valor> = conAlias(leerLocal<{ modo?: string; valores?: Record<string, Valor> }>(CLAVE_CAMBIOS, {}).modo ?? '') === activo
    ? leerLocal<{ valores: Record<string, Valor> }>(CLAVE_CAMBIOS, { valores: {} }).valores ?? {} : {};
/** el mundo en que se eligió a mano el tema ("" ambos): ahí vale aunque el mundo tenga el suyo */
let temaEn: string = leerLocal<{ tema_en?: string }>(CLAVE_CAMBIOS, {}).tema_en ?? '';
/** Guardar en este navegador los cambios a mano del modo puesto (y, si hay un tema, en qué mundo se eligió). */
const recordarCambios = () =>
    guardarLocal(CLAVE_CAMBIOS, { modo: activo, valores: cambios, ...('tema' in cambios ? { tema_en: temaEn } : {}) });

/** el último modo que tuvo cada mundo ("" ambos), en este navegador, y si el puesto lo impuso un mundo (por no tener el
 *  de antes): al volver al otro, vuelve el que se tenía ahí */
const CLAVE_POR_MUNDO = 'telar.modo.por-mundo';
const recordados = leerLocal<{ modos?: Record<string, string>; impuesto?: boolean; previo?: string }>(CLAVE_POR_MUNDO, {});
let porMundo: Record<string, string> = recordados.modos ?? {};
let impuesto = recordados.impuesto === true;
/** el que estaba cuando un mundo impuso el puesto: si no se sabe cuál se tenía en el otro mundo, se vuelve a ese */
let previo = recordados.previo ?? '';
const guardarPorMundo = () => guardarLocal(CLAVE_POR_MUNDO, { modos: porMundo, impuesto, previo });
/** el mundo en que está el modo puesto: undefined hasta que llegan los mundos */
let enMundo: string | undefined;
/** mientras un modo pone su mundo (`mundo`): al entrar a ese mundo, el modo se queda */
let desdeModo = false;

/** el mundo puesto la última vez y su tema: hasta que lleguen los mundos (al abrir la página) se usan esos, para que los
 *  colores no salten del de siempre al del mundo */
const CLAVE_TEMA_MUNDO = 'telar.tema.mundo';
let mundoAntes = leerLocal<{ mundo?: string; tema?: string }>(CLAVE_TEMA_MUNDO, {});

// lo que se plegaba antes de haber modos (la barra y la ficha), como cambios de este modo: no se pierde al actualizar
for (const [vieja, clave, valor] of [['telar.barra.plegada', 'barra', 'plegada'], ['telar.lado.plegado', 'lado', 'plegado']] as const) {
    try {
        if (localStorage.getItem(vieja) === '1' && !(clave in cambios)) cambios[clave] = valor;
        localStorage.removeItem(vieja);
    } catch { /* sin almacén */ }
}

export const lista = (): Modo[] => modos;
/** Los modos que tiene el mundo puesto, por su clave (null: todos). */
export const delMundo = (): string[] | null => mundo.modos();
/** Si un modo se puede poner en el mundo puesto. */
export const permitido = (clave: string): boolean => tieneModo(mundo.modos(), conAlias(clave));
/** Los modos que se pueden poner en el mundo puesto, en el orden de la lista. */
export const permitidos = (): Modo[] => modos.filter(m => permitido(m.clave));
export const ajustes = (): Ajuste[] => catalogo;
export const puesto = (): Modo => modos.find(m => m.clave === activo) ?? modos[0];
export const cambiosAMano = (): Record<string, Valor> => ({ ...cambios });
/** La actitud del puesto (tactica, estrategia, foco o todo): la suya, o sobre la que se arma uno propio. */
export const base = (m: Modo = puesto()): string => m.base ?? (ACTITUDES.some(a => a.clave === m.clave) ? m.clave : 'tactica');

/** Sobre cuál de las cuatro se arma un modo nuevo hecho con lo que se ve ahora («nuevo modo…» de ⚙ modos): la del
 *  puesto, o la suya si es uno propio. "" si es táctica (la de siempre, sin escribirla) o si el nombre es el de uno de
 *  fábrica, que no lleva base. */
export function baseDeNuevo(nombre: string, m: Modo = puesto()): string {
    if (ACTITUDES.some(a => a.clave === nombre) || nombre in ALIAS) return '';
    const b = base(m);
    return b === 'tactica' ? '' : b;
}

/** Las filas de DASHBOARD del modo puesto: las claves de las pestañas, en su orden, o null si son todas (`*`). Las de
 *  una pestaña que se sacó (estrategia, el plan) no cuentan (web/modos-pestanas.ts, `partesDeFilas`). */
export function filas(): string[] | null {
    const v = partesDeFilas(valor('filas') ?? '*');
    return v.length ? v : null;
}

/** El valor de un ajuste ahora: el cambio a mano, o el del modo puesto, o el de «táctica». */
export function valor(clave: string): Valor | undefined {
    if (clave in cambios) return cambios[clave];
    return puesto().valores[clave] ?? modos.find(m => m.clave === 'tactica')?.valores[clave];
}

/** Las etiquetas por las que filtra el modo puesto (vacío: no filtra). */
export const filtro = (): string[] => String(valor('etiquetas') ?? '').split(',').filter(Boolean);

/** Los tipos de unidad (arquetipos) que el modo puesto llama proyectos, negocios o iniciativas: `proyectos`, `negocios`
 *  e `iniciativas`, separados por coma. Vacío: proyectos son todas las unidades (menos las iniciativas); negocios e
 *  iniciativas, ninguna. */
export const tipos = (clave: 'proyectos' | 'negocios' | 'iniciativas'): string[] =>
    String(valor(clave) ?? '').split(',').map(t => t.trim()).filter(Boolean);

/** El campo del frontmatter con que se agrupan las iniciativas (`agrupar_iniciativas`: «{frontmatter:programa}» es
 *  «programa»); "" si no se agrupan. */
export const campoIniciativas = (): string => /^\{?\s*(?:frontmatter\s*:\s*)?([\w-]+)\s*\}?$/.exec(String(valor('agrupar_iniciativas') ?? '').trim())?.[1] ?? '';

/** Si un hilo con estas etiquetas se ve en la lista con el modo puesto: sin filtro, todos; con uno, los que tienen
 *  alguna de sus etiquetas, y los sin ninguna si `sin_etiqueta` es «se-ven». */
export function seVe(etiquetas: readonly string[] | undefined): boolean {
    const f = filtro();
    if (!f.length) return true;
    if (!etiquetas?.length) return valor('sin_etiqueta') !== 'no-se-ven';
    return etiquetas.some(e => f.includes(e));
}

/** Qué agentes se ven en un modo, el puesto u otro: su `agentes` (vacío, todos). No se hereda, así que es el del modo
 *  y no el de «táctica». */
export const agentesDe = (m: Modo = puesto()): string =>
    String((m.clave === activo && 'agentes' in cambios ? cambios.agentes : m.valores.agentes) ?? '');

/** Si un agente residente (su carpeta o su dirección) sale en AGENTES con el modo puesto, o con otro. */
export const seVeAgente = (agente: string, m: Modo = puesto()): boolean => agentesModo.seVe(agentesDe(m), agente);

/** las grabaciones de `agentes` y `filas` que van en camino, una tras otra (dos a la vez escribirían el mismo archivo, y
 *  la que terminara última podría no ser la del último clic): hasta que vuelva la última, lo que se ve es lo que se pidió */
let enCamino = 0;
let cola: Promise<unknown> = Promise.resolve();

/** Un ajuste de un modo que se guarda al tiro, sin pasar por los cambios a mano (`agentes`, `filas`): se ve ya, en el
 *  puesto u otro, y se escribe solo esa línea de `[modos.<clave>]` (`PATCH /modos/<clave>`). null quita la línea: el modo
 *  vuelve a lo de fábrica o de su base (`heredados`). Devuelve el error, o "". */
function guardarAjuste(clave: string, ajuste: string, v: string | null): Promise<string> {
    const m = modos.find(x => x.clave === clave);
    if (!m) return Promise.resolve(`no hay un modo «${clave}»`);
    const heredado = m.heredados?.[ajuste] ?? (ajuste === 'agentes' ? '' : m.valores[ajuste]);
    m.valores = { ...m.valores, [ajuste]: v ?? heredado };
    const propios = (m.propios ?? []).filter(x => x !== ajuste);
    m.propios = v === null ? propios : [...propios, ajuste];
    if (v !== null && !(ajuste in (m.heredados ?? {}))) m.heredados = { ...m.heredados, [ajuste]: heredado };
    if (clave === activo && ajuste in cambios) { delete cambios[ajuste]; recordarCambios(); }
    aplicar();
    enCamino++;
    const hecho = cola.then(async () => {
        const r = await cli.ajustarModo(clave, { [ajuste]: v });
        enCamino--;
        // si falló, lo que se ve vuelve a ser lo guardado
        if (!r.datos) { if (!enCamino) void leer(); return r.error ?? 'no se pudo'; }
        if (!enCamino) recibir(r.datos.modos);
        return '';
    });
    cola = hecho.catch(() => undefined);
    return hecho;
}

/** Qué agentes se ven en un modo (`agentes`, el puesto u otro): se ve al tiro y se guarda en `[modos.<clave>]`, sin
 *  tocar lo demás del modo ni sus cambios a mano. Devuelve el error, o "". */
export const guardarAgentes = (clave: string, v: string): Promise<string> => guardarAjuste(clave, 'agentes', v);

/** Qué pestañas de DASHBOARD ve un modo (`filas`, web/modos-pestanas.ts): como los agentes, al tiro y solo esa línea; null
 *  la quita y el modo vuelve a las de fábrica o de su base. Si es el puesto, la barra cambia sin recargar. */
export const guardarFilas = (clave: string, v: string | null): Promise<string> => guardarAjuste(clave, 'filas', v);

/** Las pestañas de DASHBOARD de un modo, el puesto u otro (su `filas`, sin los cambios a mano). */
export const filasDe = (m: Modo): string => String(m.valores.filas ?? '*');

/** De dónde sale un ajuste de un modo: su tabla («propio»), o lo que tendría sin ella (`heredado`). */
export const deDonde = (m: Modo, ajuste: string): 'propio' | 'heredado' =>
    ((m.propios ?? []).includes(ajuste) ? 'propio' : 'heredado');

/** De dónde sale un ajuste de un modo sin su línea: «fabrica» (lo de fábrica de ese modo; de uno propio, lo de fábrica de
 *  su base) o la clave del modo que lo dice (táctica, o su base). */
export const origen = (m: Modo, ajuste: string): string => m.origenes?.[ajuste] ?? (m.de_fabrica ? 'fabrica' : base(m));

/** Si ya llegaron de la API (antes, la terminal no tiene valores de modo: usa los suyos). */
export const listos = (): boolean => leidos;

export function alCambiar(f: () => void): () => void {
    oyentes.add(f);
    return () => oyentes.delete(f);
}

/** El tema que se ve ahora y de dónde sale: el elegido a mano en este modo (si se eligió en el mundo puesto, o si este
 *  no tiene tema), el del mundo puesto si declara uno, o el del modo. */
export function tema(): { clave: string; por: temas.Origen } {
    const m = mundo.conocidos() ? { mundo: mundo.puesto().mundo, tema: mundo.mundo()?.tema } : mundoAntes;
    const aMano = 'tema' in cambios && (!temas.existe(m.tema) || temaEn === (m.mundo ?? '')) ? String(cambios.tema) : undefined;
    return temas.queRige({ aMano, mundo: m.tema, modo: String(valor('tema') ?? '') });
}

/** mientras se aplica: lo que avise el mundo entretanto (aplicar lo toca) ya queda aplicado */
let aplicando = false;

/** Poner el tema que rige y recordar el que puso el mundo (para la próxima vez que se abra la página). Devuelve si los
 *  colores cambiaron. */
function ponerTema(): boolean {
    const cambio = temas.poner(tema().clave);
    if (mundo.conocidos()) {
        const delMundo = mundo.mundo()?.tema;
        const ahora = { mundo: mundo.puesto().mundo, tema: temas.existe(delMundo) ? delMundo! : '' };
        if (ahora.mundo !== mundoAntes.mundo || ahora.tema !== mundoAntes.tema) { mundoAntes = ahora; guardarLocal(CLAVE_TEMA_MUNDO, ahora); }
    }
    return cambio;
}

/** Cuando cambia el mundo (a su hora o a mano) o lo que dice (⚙ mundos): al entrar a un mundo con tema se olvida el
 *  elegido a mano en otro mundo; si los colores cambian, se avisa a quien escucha (la terminal toma los suyos). */
function alCambiarMundo(): void {
    if (aplicando || !mundo.conocidos()) return;
    if ('tema' in cambios && temas.existe(mundo.mundo()?.tema) && temaEn !== mundo.puesto().mundo) {
        delete cambios.tema;
        recordarCambios();
    }
    if (alModoDelMundo()) return;
    if (ponerTema()) for (const f of oyentes) f();
}

/** El modo que va en el mundo puesto: al entrar a otro mundo, el que tuvo ahí la última vez (o el puesto, o el primero de
 *  su lista); en el mismo mundo, si el puesto dejó de ser de los suyos (⚙ mundos), el primero. Devuelve si lo cambió. */
function alModoDelMundo(): boolean {
    // hasta que lleguen los modos de la API no se sabe si uno propio existe: no se mueve nada
    if (!mundo.conocidos() || !leidos) return false;
    const ahora = mundo.puesto().mundo;
    // la primera vez (la página recién abierta) no se vuelve a nada: el puesto es el de este mundo. Lo que puso un modo
    // con su mundo, tampoco: ese modo se queda
    const entra = enMundo !== undefined && enMundo !== ahora && !desdeModo;
    if (entra) porMundo = { ...porMundo, [enMundo!]: activo };
    enMundo = ahora;
    const r = modoAlEntrar({ permitidos: mundo.modos(), existentes: modos.map(m => m.clave), actual: activo,
        recordado: porMundo[ahora], impuesto, previo, entra });
    impuesto = r.impuesto;
    previo = r.previo;
    if (r.clave === activo) { recordar(); return false; }
    // a la vista del modo nuevo, si se está en el dashboard (quien escucha lo decide: mirando un hilo, no salta)
    poner_(r.clave, { ir: !desdeModo, conMundo: false, porMundo: true });
    return true;
}

/** Recordar el modo puesto como el del mundo en que está (y si lo impuso el mundo). */
function recordar(): void {
    if (!mundo.conocidos()) return;
    porMundo = { ...porMundo, [mundo.puesto().mundo]: activo };
    guardarPorMundo();
}

function aplicar(gesto = false): void {
    aplicando = true;
    try { aplicarYa(gesto); } finally { aplicando = false; }
    for (const f of oyentes) f();
}

function aplicarYa(gesto: boolean): void {
    for (const k of EN_BODY) {
        const v = valor(k);
        if (v === undefined) delete document.body.dataset[k];
        else document.body.dataset[k] = String(v);
    }
    document.body.dataset.modo = base();
    // en todo, el mundo ordena y no esconde
    mundo.ordenarSolo(base() === 'todo');
    // los colores y las medidas: en <html>, donde están los tokens (componentes/temas.ts, densidades.ts)
    ponerTema();
    densidades.poner(String(valor('densidad') ?? densidades.AUTO));
    // la pantalla completa la deja pedir el navegador solo tras un clic o una tecla: al cambiar de modo, no al cargar
    if (gesto) {
        const quiere = valor('pantalla_completa') === 'si';
        if (quiere && !document.fullscreenElement) void document.documentElement.requestFullscreen?.().catch(() => undefined);
        if (!quiere && document.fullscreenElement) void document.exitFullscreen?.().catch(() => undefined);
    }
    salida();
}

/** Arriba a la derecha cuando la cabecera está oculta (foco): el ícono del modo y el mundo, en su color; un clic vuelve
 *  al modo de antes. */
function salida(): void {
    let b = document.getElementById('salir-modo');
    if (!b) {
        b = document.createElement('a');
        b.id = 'salir-modo';
        b.addEventListener('click', () => alternarFoco());
        document.body.appendChild(b);
        mundo.alCambiar(salida);
    }
    const icono = ACTITUDES.find(a => a.clave === base())?.icono ?? I.modo;
    const m = mundo.mundo();
    b.replaceChildren(Object.assign(document.createElement('span'), { className: 'i', textContent: icono }));
    if (m) {
        const n = Object.assign(document.createElement('span'), { className: 'mundo-nombre', textContent: ` ${m.nombre}` });
        n.style.setProperty('--mundo-c', `var(--${m.color})`);
        b.appendChild(n);
    }
    b.title = `salir de «${puesto().nombre}» (⌥⇧F): vuelve a «${modos.find(m => m.clave === anterior)?.nombre ?? 'táctica'}»`;
}

const alPonerse = new Set<(clave: string, o: { porMundo: boolean }) => void>();
/** Cuando la persona pone un modo (no al leerlos ni al cambiar un ajuste): quien muestra su vista va a ella. `porMundo`:
 *  lo puso el mundo, al entrar a él (el que no tiene el modo de antes, o donde se tuvo otro): ahí solo si se está en el
 *  dashboard, sin sacar a nadie de un hilo. */
export function alPoner(f: (clave: string, o: { porMundo: boolean }) => void): () => void {
    alPonerse.add(f);
    return () => alPonerse.delete(f);
}

/** El mundo que pone un modo al ponerse: el de su ajuste `mundo` o, como antes de los mundos, una de sus `etiquetas`
 *  que se llame como uno declarado. Vacío: no lo toca. */
function mundoDelModo(): string {
    const declarados = mundo.declarados().map(m => m.clave);
    const propio = String(valor('mundo') ?? '').trim();
    if (propio && declarados.includes(propio)) return propio;
    return filtro().find(e => declarados.includes(e)) ?? '';
}

/** Poner un modo: sus valores, sin los cambios a mano del anterior; si dice un mundo, ese mundo (a mano). Avisa a
 *  quien muestra su vista, aunque ya estuviera puesto: poner el que está es volver a su vista. Con `ir: false` (entrar
 *  a foco y salir con ⌥⇧F), solo cambia la disposición: lo que se mira sigue a la vista. Uno que el mundo puesto no
 *  tiene (`[mundos.<n>] modos`) no se pone: devuelve false. */
export function cambiar(clave: string, { ir = true } = {}): boolean {
    clave = conAlias(clave);
    if (!modos.some(m => m.clave === clave) || !permitido(clave)) return false;
    impuesto = false;
    previo = '';
    poner_(clave, { ir, conMundo: true, porMundo: false });
    return true;
}

function poner_(clave: string, o: { ir: boolean; conMundo: boolean; porMundo: boolean }): void {
    if (clave !== activo) { anterior = activo; guardarLocal(CLAVE_ANTERIOR, anterior); }
    activo = clave;
    cambios = {};
    guardarLocal(CLAVE_ACTIVO, activo);
    recordarCambios();
    aplicar(true);
    const m = o.conMundo ? mundoDelModo() : '';
    if (m && m !== mundo.puesto().mundo) {
        desdeModo = true;
        try { mundo.poner(m); } finally { desdeModo = false; }
    }
    recordar();
    if (o.ir) for (const f of alPonerse) f(activo, { porMundo: o.porMundo });
}

/** Al abrir la página: el modo que estaba puesto, salvo todo, que nunca es la vista de partida (vuelve a táctica; si el
 *  mundo no tiene táctica, se queda: al llegar los mundos, el de su lista). */
export function deEntrada(): void {
    if (base() === 'todo' && permitido('tactica')) { activo = 'tactica'; cambios = {}; guardarLocal(CLAVE_ACTIVO, activo); aplicar(); }
}

/** Un cambio a mano en el modo puesto (plegar la barra, otro fondo): vale hasta cambiar de modo. El tema, además, hasta
 *  entrar a otro mundo que tenga el suyo; y si el mundo puesto tiene tema, elegir el del modo también es a mano (si no, el
 *  del mundo seguiría ganando). */
export function poner(clave: string, v: Valor): void {
    const esElDelModo = puesto().valores[clave] === v && !(clave === 'tema' && temas.existe(mundo.mundo()?.tema));
    if (esElDelModo) delete cambios[clave];
    else cambios[clave] = v;
    if (clave === 'tema') temaEn = mundo.puesto().mundo;
    recordarCambios();
    aplicar(clave === 'pantalla_completa');
}

/** Foco, y de vuelta al de antes (⌥⇧F, y el ◧): si el mundo no tiene el de antes, al primero de los suyos que no sea
 *  foco. En un mundo sin foco, nada. */
export function alternarFoco(): void {
    if (activo !== 'foco') { cambiar('foco', { ir: false }); return; }
    const vuelta = [anterior, 'tactica', ...permitidos().map(m => m.clave)].find(k => k !== 'foco' && permitido(k) && modos.some(m => m.clave === k));
    if (vuelta) cambiar(vuelta, { ir: false });
}

/** El que sigue en la lista (⌥⇧M): los cuatro y después los propios; solo los que tiene el mundo puesto. */
export function siguiente(): void {
    const lista = permitidos();
    if (!lista.length) return;
    const i = lista.findIndex(m => m.clave === activo);
    cambiar(lista[(i + 1) % lista.length].clave);
}

/** La actitud `n` (1 a 4, ⌥⇧1–4): la de fábrica con esa tecla. */
export function porTecla(n: string): void {
    const a = ACTITUDES.find(x => x.tecla === n);
    if (a) cambiar(a.clave);
}

/** Los modos de la API (de fábrica, los de `[modos]`, y la terminal de «táctica»). */
export async function leer(): Promise<void> {
    const r = await cli.modos();
    if (!r.datos) return;
    modos = r.datos.modos;
    catalogo = r.datos.catalogo;
    leidos = true;
    if (!modos.some(m => m.clave === activo)) { activo = 'tactica'; cambios = {}; }
    aplicar();
    alModoDelMundo();
}

/** Lo que devolvió la API al guardar o borrar un modo. */
export function recibir(nuevos: Modo[]): void {
    modos = nuevos;
    if (!modos.some(m => m.clave === activo)) { activo = 'tactica'; guardarLocal(CLAVE_ACTIVO, activo); }
    aplicar();
    alModoDelMundo();
}

/** Guardar en el modo puesto lo que se cambió a mano (y queda sin cambios). */
export async function guardarCambios(): Promise<string> {
    const m = puesto();
    // la tabla se escribe entera: uno propio guarda también sobre cuál se arma, o volvería a ser de táctica
    const r = await cli.guardarModo(m.clave, { ...m.valores, ...cambios }, m.nombre, m.de_fabrica ? '' : base(m));
    if (!r.datos) return r.error ?? 'no se pudo';
    cambios = {};
    recordarCambios();
    recibir(r.datos.modos);
    return '';
}

/** Arrancar: aplicar lo de este navegador, el ◧, las teclas, y leer los de la API. El tema escucha al mundo y a los colores
 *  propios de cada tema (web/colores.ts). */
export function montar(): void {
    mundo.alCambiar(alCambiarMundo);
    // un color propio (⚙ temas): los tokens cambian solos; la terminal toma los suyos. Un tema propio que llega (o se va)
    // puede ser el que rige: se pone de nuevo
    colores.alCambiar(() => { ponerTema(); for (const f of oyentes) f(); });
    colores.montar();
    aplicar();
    deEntrada();
    // ⌥⇧1–4 las actitudes, ⌥⇧F foco y vuelta, ⌥⇧M el siguiente, ⌥⇧0 el mundo siguiente: antes que nadie (la terminal
    // se las comería)
    window.addEventListener('keydown', e => {
        if (!e.altKey || !e.shiftKey || e.metaKey || e.ctrlKey) return;
        const n = /^Digit([0-4])$/.exec(e.code)?.[1];
        if (e.code === 'KeyF') alternarFoco();
        else if (e.code === 'KeyM') siguiente();
        else if (n === '0') mundo.siguiente();
        else if (n) porTecla(n);
        else return;
        e.preventDefault(); e.stopPropagation();
    }, true);
    void leer();
}
