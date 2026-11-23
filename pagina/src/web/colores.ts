// Los colores propios de cada tema y los temas propios (`[temas.<tema>]`, telar.temas): los fondos, las líneas y las
// tintas de letra de un tema (componentes/temas.ts, `COLORES`) cambiados encima de los de fábrica, y los temas que parten
// de uno de fábrica con otro nombre (`base`). Viven en la raíz (`<raiz>/.telar/temas.toml`, valen en todas las máquinas) y la
// configuración de una máquina puede pisar algunos; `donde` dice qué está dónde. Se eligen en ⚙ temas (vistas/dashboard/config/temas.ts)
// y valen para ese tema dondequiera que se vea (la página, los selectores de tema de ⚙ mundos y ⚙ modos); /componentes
// muestra los de fábrica como vienen y los propios con lo suyo (`montar({ soloPropios: true })`).
//
// Se ponen con una hoja propia (`<style id="temas-propios">`, componentes/temas.ts `css`), que va encima de temas.css:
// cambiar un color no repinta nada, los tokens cambian solos. Un tema propio lleva en esa hoja las reglas de su base
// copiadas con su nombre, leídas de las hojas de la página (`reglas`): si todavía no cargan, se copian cuando cargan.
// Este navegador guarda los últimos que leyó (los colores y las bases), para que al abrir la página no se vean un
// momento los de fábrica, ni se pierda un tema propio puesto. `probar` cambia un color solo en esta página, sin
// escribirlo (mientras se arrastra el selector de color, o se escribe uno): lo que se guarda o se vuelve a leer la
// reemplaza. Quien escucha (`alCambiar`: el tema puesto y la terminal, por web/modos.ts; los selectores) se entera de cada
// cambio, también de un tema propio que aparece o se va.

import * as cli from '../cli';
import * as temas from '../componentes/temas';

const CLAVE = 'telar.temas.propios';
const CLAVE_BASES = 'telar.temas.bases';
function leerLocal<T extends object>(clave: string): T {
    try {
        const v = JSON.parse(localStorage.getItem(clave) ?? '{}') as unknown;
        return (v && typeof v === 'object' ? v : {}) as T;
    } catch { return {} as T; }
}
const guardarLocal = (clave: string, v: unknown) => { try { localStorage.setItem(clave, JSON.stringify(v)); } catch { /* sin almacén */ } };

/** los de la configuración (los últimos leídos) */
let propios: temas.Propios = leerLocal(CLAVE);
/** los temas propios: nombre → el de fábrica del que parte */
let bases: Record<string, string> = leerLocal(CLAVE_BASES);
/** los que se prueban sin escribir: tema → {color: #rrggbb} */
let probando: temas.Propios = {};
/** en /componentes: los de fábrica, como vienen */
let soloPropios = false;
const oyentes = new Set<() => void>();

const registrar = (): boolean => temas.registrar(Object.entries(bases).map(([clave, base]) => ({ clave, base })));
registrar();

/** Dónde vive lo propio de un tema (`GET /temas`): «raiz», en `<raiz>/.telar/temas.toml`, que vale en todas las máquinas;
 *  «maquina», solo en la configuración de esta; «mixto», en la raíz y esta máquina pisa algunos colores (`enMaquina`). */
export interface Donde { vive: '' | 'raiz' | 'maquina' | 'mixto'; enRaiz: string[]; enMaquina: string[] }
let dondes: Record<string, Donde> = {};
/** el archivo de la raíz ("" si la configuración no dice raíz: todo queda en la máquina) */
let archivoRaiz = '';
/** Dónde vive lo propio de un tema. */
export const donde = (tema: string): Donde => dondes[tema] ?? { vive: '', enRaiz: [], enMaquina: [] };
/** El archivo de la raíz donde escribe ⚙ temas ("" sin raíz: en la configuración de la máquina). */
export const raiz = (): string => archivoRaiz;

/** Los colores propios de un tema, de la configuración: color → #rrggbb (vacío: de fábrica). */
export const de = (tema: string): Record<string, string> => ({ ...(propios[tema] ?? {}) });
/** Todos los de la configuración. */
export const todos = (): temas.Propios => JSON.parse(JSON.stringify(propios)) as temas.Propios;

export function alCambiar(f: () => void): () => void {
    oyentes.add(f);
    return () => oyentes.delete(f);
}

/** Lo que se pone ahora: los de la configuración con los que se prueban encima. */
function juntos(): temas.Propios {
    const salida = todos();
    for (const [t, v] of Object.entries(probando)) salida[t] = { ...(salida[t] ?? {}), ...v };
    return salida;
}

/** las reglas de cada tema de fábrica, leídas una vez de las hojas de la página */
const copiadas = new Map<string, readonly string[]>();
/** si ya se espera a que carguen las hojas, para copiar las reglas de la base de un tema propio */
let esperandoHojas = false;

/** Las reglas de un tema de fábrica, de las hojas de la página. Si no hay (la hoja no cargó todavía: app.js no la espera),
 *  se vuelve a aplicar todo cuando carga. */
function reglas(base: string): readonly string[] {
    const ya = copiadas.get(base);
    if (ya) return ya;
    const hojas = typeof document !== 'undefined' && document.styleSheets ? Array.from(document.styleSheets) : [];
    const halladas = temas.reglasDe(hojas, base);
    if (halladas.length) copiadas.set(base, halladas);
    else if (!esperandoHojas && typeof document.querySelectorAll === 'function') {
        const enlaces = Array.from(document.querySelectorAll<HTMLLinkElement>('link[rel="stylesheet"]')).filter(l => !l.sheet);
        if (enlaces.length) {
            esperandoHojas = true;
            for (const l of enlaces) l.addEventListener('load', () => { esperandoHojas = false; aplicar(true); }, { once: true });
        }
    }
    return halladas;
}

/** Escribir la hoja (si cambió) y avisar; con `avisar`, aunque no haya cambiado (un tema propio que apareció). */
function aplicar(avisar = false): void {
    const texto = temas.css(juntos(), { reglas, soloPropios });
    let hoja = document.getElementById('temas-propios');
    if (!hoja && texto) {
        hoja = document.createElement('style');
        hoja.id = 'temas-propios';
        (document.head ?? document.documentElement).appendChild(hoja);
    }
    if (hoja && hoja.textContent !== texto) {
        hoja.textContent = texto;
        avisar = true;
    }
    if (avisar) for (const f of oyentes) f();
}

/** Los de la configuración (lo que dio `GET /temas` o una escritura): los guarda en este navegador y los pone. Lo que se
 *  estaba probando se suelta. */
export function recibir(d: Pick<cli.JsonTemas, 'temas' | 'raiz'> | undefined): void {
    const nuevos: temas.Propios = {};
    const nuevasBases: Record<string, string> = {};
    const nuevosDondes: Record<string, Donde> = {};
    for (const t of d?.temas ?? []) {
        if (t.propios && Object.keys(t.propios).length) nuevos[t.clave] = { ...t.propios };
        if (t.base && t.de_fabrica === false) nuevasBases[t.clave] = t.base;
        if (t.vive) nuevosDondes[t.clave] = { vive: t.vive, enRaiz: [...(t.en_raiz ?? [])], enMaquina: [...(t.en_maquina ?? [])] };
    }
    dondes = nuevosDondes;
    archivoRaiz = d?.raiz ?? '';
    propios = nuevos;
    bases = nuevasBases;
    probando = {};
    guardarLocal(CLAVE, propios);
    guardarLocal(CLAVE_BASES, bases);
    aplicar(registrar());
}

/** Probar un color, solo en esta página (sin escribirlo); `undefined` suelta la prueba. */
export function probar(tema: string, tinta: string, color: string | undefined): void {
    const de = { ...(probando[tema] ?? {}) };
    if (color === undefined) delete de[tinta]; else de[tinta] = color;
    probando = { ...probando, [tema]: de };
    aplicar();
}

/** Soltar todo lo que se prueba. */
export function soltar(): void {
    if (!Object.keys(probando).length) return;
    probando = {};
    aplicar();
}

/** Leer los de la configuración (`GET /temas`). Devuelve el error, o "". */
export async function leer(): Promise<string> {
    const r = await cli.temasPropios();
    if (!r.datos) return r.error ?? 'no se pudo';
    recibir(r.datos);
    return '';
}

/** Lo que devuelve una escritura: si salió, se toma y ""; si no, el porqué, y se vuelve a leer lo que dice el archivo. */
async function escrito(p: Promise<cli.Respuesta<cli.JsonTemas>>): Promise<string> {
    const r = await p;
    if (!r.datos) { probando = {}; void leer(); return r.error ?? 'no se pudo'; }
    recibir(r.datos);
    return '';
}

/** Cambiar algunos colores de un tema en la configuración (solo esas líneas); null vuelve al de fábrica. */
export const ajustar = (tema: string, valores: Record<string, string | null>) => escrito(cli.ajustarTema(tema, valores));

/** Todos los colores de un tema, de vuelta a los de fábrica: de uno de fábrica se quita su tabla; de uno propio, sus
 *  colores (queda el tema, igual a su base). */
export function deFabrica(tema: string): Promise<string> {
    if (temas.esDeFabrica(tema)) return escrito(cli.temaDeFabrica(tema));
    const nulos = Object.fromEntries(Object.keys(propios[tema] ?? {}).map(k => [k, null]));
    return Object.keys(nulos).length ? ajustar(tema, nulos) : Promise.resolve('');
}

/** Un tema propio nuevo, que parte de `base` (uno de fábrica, o uno propio: se copian sus colores). */
export const crear = (nombre: string, base: string) => escrito(cli.crearTema(nombre, base));
/** Borrar un tema propio (lo que un modo o un mundo tiene puesto no se borra: lo dice el error). */
export const borrar = (nombre: string) => escrito(cli.temaDeFabrica(nombre));

/** Los colores de un tema como se ven ahora (con los propios y lo que se prueba) o, con `fabrica`, los de fábrica (de uno
 *  propio, los de su base), en `#rrggbb`: los lee de una sonda escondida con ese tema, así salen de los mismos CSS que
 *  pintan la página. Las líneas y la selección de fábrica son transparentes (salen del texto): se dan como se ven sobre
 *  el fondo. */
export function resueltos(tema: string, fabrica = false): Record<string, string> {
    let sonda = document.getElementById('temas-sonda');
    if (!sonda) {
        sonda = document.createElement('div');
        sonda.id = 'temas-sonda';
        sonda.hidden = true;
        sonda.setAttribute('aria-hidden', 'true');
        sonda.appendChild(document.createElement('span'));
        document.body.appendChild(sonda);
    }
    sonda.dataset.tema = tema;
    if (fabrica) sonda.dataset.fabrica = ''; else delete sonda.dataset.fabrica;
    const css = getComputedStyle(sonda);
    const pinta = sonda.firstElementChild as HTMLElement | null;
    const crudo = Object.fromEntries(temas.PRIMITIVOS.map(k => [k, css.getPropertyValue(`--${k}`).trim()]));
    const fondo = temas.rgb(crudo.bg ?? '');
    const salida: Record<string, string> = {};
    for (const k of temas.PRIMITIVOS) {
        let v = crudo[k] ?? '';
        // lo que no es un color escrito (un color-mix, un rgb con transparencia): como lo resuelve el navegador
        if (v && !/^#[0-9a-f]{6}$/i.test(v) && pinta) {
            pinta.style.color = `var(--${k})`;
            v = getComputedStyle(pinta).color || v;
        }
        const c = fondo ? temas.opaco(v, fondo) : temas.rgb(v);
        salida[k] = c ? temas.hex(c) : v;
    }
    return salida;
}

/** Arrancar: los de este navegador al tiro, y los de la configuración cuando lleguen. En /componentes, `soloPropios`: los
 *  de fábrica se quedan como vienen. */
export function montar(o: { soloPropios?: boolean } = {}): void {
    soloPropios = !!o.soloPropios;
    aplicar();
    void leer();
}
