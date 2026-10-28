// Los modos de la página (docs/propuestas/modos.md, telar.modos): un nombre con valores para la disposición (la
// barra de hilos, la ficha de un agente, la cabecera…), la terminal (ancho, posición, fondo) y los avisos. Las
// definiciones vienen de la API (las de fábrica y las de `[modos]`); cuál está puesto, y los cambios a mano que se
// hicieron estando en él, son de este navegador. Cambiar de modo descarta esos cambios; ⚙ modos los guarda.
//
// Lo que aplica se ve en `body`: un `data-<ajuste>` por cada ajuste de disposición y de avisos, que el CSS lee
// (media/css/marco.css). La barra, la ficha y la terminal escuchan `alCambiar` y se redibujan.

import * as cli from '../cli';

export type Valor = string | number;
export interface Ajuste { clave: string; grupo: string; nombre: string; opciones: string[]; ayuda: string }
export interface Modo { clave: string; nombre: string; valores: Record<string, Valor>; de_fabrica: boolean; cambiado: boolean }

const CLAVE_ACTIVO = 'telar.modo', CLAVE_ANTERIOR = 'telar.modo.anterior', CLAVE_CAMBIOS = 'telar.modo.cambios';
/** lo que se aplica como atributo de `body`, para el CSS */
const EN_BODY = ['barra', 'lado', 'cabecera', 'acciones', 'escribir', 'avisos', 'aviso_version'];

// hasta que conteste la API, los de fábrica (los mismos de telar.modos.DE_FABRICA, sin la terminal)
let modos: Modo[] = [
    { clave: 'estandar', nombre: 'estándar', de_fabrica: true, cambiado: false, valores: {
        barra: 'abierta', lado: 'abierto', cabecera: 'visible', acciones: 'visible', escribir: 'oculta',
        pantalla_completa: 'no', avisos: 'todos', aviso_version: 'visible' } },
    { clave: 'foco', nombre: 'foco', de_fabrica: true, cambiado: false, valores: {
        barra: 'oculta', lado: 'oculto', cabecera: 'oculta', acciones: 'oculta', escribir: 'oculta', pantalla_completa: 'no',
        columnas: 110, posicion: 'centro', fondo: 'ninguno', avisos: 'urgentes', aviso_version: 'oculto' } },
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

let activo: string = leerLocal(CLAVE_ACTIVO, 'estandar');
let anterior: string = leerLocal(CLAVE_ANTERIOR, 'estandar');
/** los cambios a mano en el modo puesto: valen hasta cambiar de modo */
let cambios: Record<string, Valor> = leerLocal<{ modo?: string; valores?: Record<string, Valor> }>(CLAVE_CAMBIOS, {}).modo === activo
    ? leerLocal<{ valores: Record<string, Valor> }>(CLAVE_CAMBIOS, { valores: {} }).valores ?? {} : {};

// lo que se plegaba antes de haber modos (la barra y la ficha), como cambios de este modo: no se pierde al actualizar
for (const [vieja, clave, valor] of [['telar.barra.plegada', 'barra', 'plegada'], ['telar.lado.plegado', 'lado', 'plegado']] as const) {
    try {
        if (localStorage.getItem(vieja) === '1' && !(clave in cambios)) cambios[clave] = valor;
        localStorage.removeItem(vieja);
    } catch { /* sin almacén */ }
}

export const lista = (): Modo[] => modos;
export const ajustes = (): Ajuste[] => catalogo;
export const puesto = (): Modo => modos.find(m => m.clave === activo) ?? modos[0];
export const cambiosAMano = (): Record<string, Valor> => ({ ...cambios });

/** El valor de un ajuste ahora: el cambio a mano, o el del modo puesto, o el de «estándar». */
export function valor(clave: string): Valor | undefined {
    if (clave in cambios) return cambios[clave];
    return puesto().valores[clave] ?? modos.find(m => m.clave === 'estandar')?.valores[clave];
}

/** Si ya llegaron de la API (antes, la terminal no tiene valores de modo: usa los suyos). */
export const listos = (): boolean => leidos;

export function alCambiar(f: () => void): () => void {
    oyentes.add(f);
    return () => oyentes.delete(f);
}

function aplicar(gesto = false): void {
    for (const k of EN_BODY) {
        const v = valor(k);
        if (v === undefined) delete document.body.dataset[k];
        else document.body.dataset[k] = String(v);
    }
    // la pantalla completa la deja pedir el navegador solo tras un clic o una tecla: al cambiar de modo, no al cargar
    if (gesto) {
        const quiere = valor('pantalla_completa') === 'si';
        if (quiere && !document.fullscreenElement) void document.documentElement.requestFullscreen?.().catch(() => undefined);
        if (!quiere && document.fullscreenElement) void document.exitFullscreen?.().catch(() => undefined);
    }
    salida();
    for (const f of oyentes) f();
}

/** El ◧ arriba a la derecha cuando la cabecera está oculta: vuelve al modo de antes. */
function salida(): void {
    let b = document.getElementById('salir-modo');
    if (!b) {
        b = document.createElement('a');
        b.id = 'salir-modo';
        b.textContent = '◧';
        b.addEventListener('click', () => alternarFoco());
        document.body.appendChild(b);
    }
    b.title = `salir de «${puesto().nombre}» (⌥⇧F): vuelve a «${modos.find(m => m.clave === anterior)?.nombre ?? 'estándar'}»`;
}

/** Poner un modo: sus valores, sin los cambios a mano del anterior. */
export function cambiar(clave: string): void {
    if (!modos.some(m => m.clave === clave)) return;
    if (clave !== activo) { anterior = activo; guardarLocal(CLAVE_ANTERIOR, anterior); }
    activo = clave;
    cambios = {};
    guardarLocal(CLAVE_ACTIVO, activo);
    guardarLocal(CLAVE_CAMBIOS, { modo: activo, valores: cambios });
    aplicar(true);
}

/** Un cambio a mano en el modo puesto (plegar la barra, otro fondo): vale hasta cambiar de modo. */
export function poner(clave: string, v: Valor): void {
    if (puesto().valores[clave] === v) delete cambios[clave];
    else cambios[clave] = v;
    guardarLocal(CLAVE_CAMBIOS, { modo: activo, valores: cambios });
    aplicar(clave === 'pantalla_completa');
}

/** Foco, y de vuelta al de antes (⌥⇧F, y el ◧). */
export function alternarFoco(): void {
    cambiar(activo === 'foco' ? (anterior !== 'foco' ? anterior : 'estandar') : 'foco');
}

/** El que sigue en la lista (⌥⇧M). */
export function siguiente(): void {
    const i = modos.findIndex(m => m.clave === activo);
    cambiar(modos[(i + 1) % modos.length].clave);
}

/** Los modos de la API (de fábrica, los de `[modos]`, y la terminal de «estándar»). */
export async function leer(): Promise<void> {
    const r = await cli.modos();
    if (!r.datos) return;
    modos = r.datos.modos;
    catalogo = r.datos.catalogo;
    leidos = true;
    if (!modos.some(m => m.clave === activo)) { activo = 'estandar'; cambios = {}; }
    aplicar();
}

/** Lo que devolvió la API al guardar o borrar un modo. */
export function recibir(nuevos: Modo[]): void {
    modos = nuevos;
    if (!modos.some(m => m.clave === activo)) { activo = 'estandar'; guardarLocal(CLAVE_ACTIVO, activo); }
    aplicar();
}

/** Guardar en el modo puesto lo que se cambió a mano (y queda sin cambios). */
export async function guardarCambios(): Promise<string> {
    const m = puesto();
    const r = await cli.guardarModo(m.clave, { ...m.valores, ...cambios }, m.nombre);
    if (!r.datos) return r.error ?? 'no se pudo';
    cambios = {};
    guardarLocal(CLAVE_CAMBIOS, { modo: activo, valores: cambios });
    recibir(r.datos.modos);
    return '';
}

/** Arrancar: aplicar lo de este navegador, el ◧, las teclas, y leer los de la API. */
export function montar(): void {
    aplicar();
    window.addEventListener('keydown', e => {
        if (!e.altKey || !e.shiftKey || e.metaKey || e.ctrlKey) return;
        if (e.code === 'KeyF') { e.preventDefault(); e.stopPropagation(); alternarFoco(); }
        else if (e.code === 'KeyM') { e.preventDefault(); e.stopPropagation(); siguiente(); }
    }, true);
    void leer();
}
