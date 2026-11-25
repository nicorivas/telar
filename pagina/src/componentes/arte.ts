// El arte de un mundo: un dibujo de letras, animado, que va dentro de su tarjeta en la ventana de mundos
// (componentes/mundos-ventana.ts; la abre ⌘M o un clic en el mundo de la banda). Cada arte es un módulo aparte y se
// registra con su clave; un mundo elige el suyo con `[mundos.<n>] arte = "<clave>"` en la configuración. Agregar uno no
// toca la ventana: docs/arte.md dice cómo.
//
// Dos maneras de hacer uno:
//
//   en el código   un archivo en componentes/arte/ que llama `registrarArte` (y una línea en arte/index.ts). Sus cuadros
//                  son una lista de textos, o una función del tiempo que da el cuadro de ese instante:
//
//                    registrarArte('faro', { nombre: 'faro', fps: 8, cuadros: (t, ancho, alto) => '…' });
//
//   en un archivo  `<raiz>/.telar/arte/<clave>.txt`, que telar lee solo (`GET /arte`) y la página registra al abrir la
//                  ventana: los cuadros separados por una línea `---`; arriba, si se quiere, `fps: 6`, `hover: 18`,
//                  `nombre: …`, `que: …`, `para: trabajo` (leerArteTexto, abajo). Sin compilar nada.
//
// El lienzo mide siempre ANCHO × ALTO letras: un cuadro más chico se centra (todos sus cuadros juntos, para que no salten),
// uno más grande se recorta. El color es el del mundo (lo pone el CSS); el arte es solo el dibujo. Al pasar el mouse (o
// con el foco) el arte se acelera (`alHover.fps`, o el triple) o cambia de escena (`alHover.cuadros`), y una ola de
// letras lo cruza una vez: un **efecto** de hover (`registrarEfecto`), que el módulo pone sobre cualquier arte sin que
// el arte lo programe. Un arte que declara el suyo (`alHover.efecto`, o su escena de hover) usa el suyo. Con «reducir
// movimiento», el primer cuadro, quieto, y ningún efecto.
//
// Qué arte lleva un mundo (`arteDeMundo`): el que dice su `arte`, si existe; si no, el que se llama como el mundo; si
// no, uno de fábrica que lo sugiere (`para`: el telar para «trabajo», el cielo para «personal»); si no, la órbita.
// «Ambos» lleva la binaria. Todo aquí es puro (sin DOM): lo anima web/arte-vivo.ts, y lo prueba
// pruebas/mundos-ventana.mjs.

/** El lienzo: cuántas letras de ancho y cuántas líneas de alto mide el arte de una tarjeta. */
export const ANCHO = 30;
export const ALTO = 9;
/** Los cuadros por segundo de un arte que no lo dice, y cuánto se acelera al pasar el mouse si no dice a cuánto. */
export const FPS = 6;
export const ACELERA = 3;
/** El de un mundo sin arte, y el de ambos. */
export const POR_DEFECTO = 'orbita';
export const DE_AMBOS = 'binaria';

/** Un cuadro en un instante: `t`, los segundos del reloj del arte (corre más rápido mientras se acelera); `ancho` y
 *  `alto`, el lienzo; `hover`, si tiene el mouse o el foco encima. */
export type Dibujo = (t: number, ancho: number, alto: number, o: { hover: boolean }) => string;
export type Cuadros = readonly string[] | Dibujo;

export interface DefArte {
    /** cómo se llama en el catálogo y en ⚙ mundos (sin él, su clave) */
    nombre?: string;
    /** qué es, en una línea */
    que?: string;
    /** sus cuadros: una lista (se repiten en orden) o una función del tiempo */
    cuadros: Cuadros;
    /** cuántos cuadros por segundo (de fábrica, FPS); una función se dibuja a ese ritmo */
    fps?: number;
    /** al pasar el mouse: otro ritmo (`fps`; de fábrica, ACELERA veces el suyo) u otra escena (`cuadros`), y el efecto
     *  que lo cruza al entrar (`efecto`: la clave de uno registrado, uno propio, o 'ninguno'; de fábrica, la ola, salvo
     *  que tenga escena propia) */
    alHover?: { fps?: number; cuadros?: Cuadros; efecto?: string | Efecto };
    /** los mundos que lo llevan sin decir `arte` (por su nombre): «trabajo», «personal» */
    para?: readonly string[];
    /** de dónde viene: de fábrica (este código) o de un archivo de la raíz */
    origen?: 'fabrica' | 'archivo';
}

export interface Arte extends Required<Pick<DefArte, 'fps' | 'cuadros'>> {
    clave: string;
    nombre: string;
    que: string;
    alHover: { fps: number; cuadros?: Cuadros; efecto?: string | Efecto };
    para: readonly string[];
    origen: 'fabrica' | 'archivo';
}

const registro = new Map<string, Arte>();
/** los de fábrica que tapó uno de archivo con su misma clave: vuelven si el archivo se va */
const tapados = new Map<string, Arte>();
const oyentes = new Set<() => void>();

/** Una clave de arte: minúsculas, números y guiones (como el nombre de su archivo). */
export const CLAVE = /^[a-z0-9][a-z0-9-]{0,31}$/;

/** Registrar un arte (o reemplazar el que tenía esa clave). Error si la clave o los cuadros no sirven. */
export function registrarArte(clave: string, def: DefArte): Arte {
    if (!CLAVE.test(clave)) throw new Error(`«${clave}»: la clave de un arte va en minúsculas, números y guiones`);
    if (typeof def.cuadros !== 'function' && !def.cuadros.length) throw new Error(`«${clave}»: un arte necesita al menos un cuadro`);
    const fps = acotar(def.fps ?? FPS);
    const arte: Arte = {
        clave, nombre: def.nombre ?? clave, que: def.que ?? '', cuadros: def.cuadros, fps,
        alHover: { fps: acotar(def.alHover?.fps ?? fps * ACELERA), cuadros: def.alHover?.cuadros, efecto: def.alHover?.efecto },
        para: def.para ?? [], origen: def.origen ?? 'fabrica',
    };
    const antes = registro.get(clave);
    if (antes?.origen === 'fabrica' && arte.origen === 'archivo') tapados.set(clave, antes);
    registro.set(clave, arte);
    for (const f of oyentes) f();
    return arte;
}

/** Quitar uno (los de un archivo que ya no está): si tapaba uno de fábrica, vuelve ese. */
export function olvidarArte(clave: string): void {
    const tapado = tapados.get(clave);
    tapados.delete(clave);
    if (tapado) registro.set(clave, tapado);
    else if (!registro.delete(clave)) return;
    for (const f of oyentes) f();
}

/** Cuando llega o se va uno: quien los muestra los vuelve a pintar. */
export function alRegistrar(f: () => void): () => void {
    oyentes.add(f);
    return () => oyentes.delete(f);
}

const acotar = (fps: number) => (Number.isFinite(fps) ? Math.max(.5, Math.min(30, fps)) : FPS);

/** Un arte por su clave. */
export const arte = (clave: string | undefined): Arte | undefined => (clave ? registro.get(clave) : undefined);
/** Todos, en el orden en que se registraron (los de fábrica primero). */
export const artes = (): Arte[] => [...registro.values()];

/** El arte de un mundo (`clave` "" es ambos): el que dice su `arte` si existe; si no, el que se llama como él; si no, uno
 *  de fábrica que lo sugiere (`para`); si no, la órbita. */
export function arteDeMundo(m: { clave: string; arte?: string } | undefined): Arte {
    const deFabrica = () => arte(POR_DEFECTO) ?? artes()[0] ?? VACIO;
    if (!m || !m.clave) return arte(DE_AMBOS) ?? deFabrica();
    return arte(m.arte) ?? arte(m.clave) ?? artes().find(a => a.para.includes(m.clave)) ?? deFabrica();
}

/** Lo que se dibuja si no hay ningún arte registrado (componentes/arte/index.ts no se importó). */
const VACIO: Arte = { clave: '', nombre: '', que: '', cuadros: ['·'], fps: FPS, alHover: { fps: FPS }, para: [], origen: 'fabrica' };

// ── un cuadro ──

/** El cuadro de un arte en el instante `t` (segundos de su reloj), del tamaño del lienzo: cada línea de `ancho` letras,
 *  `alto` líneas. Una lista de cuadros: el que toca a su ritmo; una función: lo que dibuje. Con `efecto` (los segundos
 *  desde que entró el mouse, mientras dura su pasada), el efecto de hover que le toca, encima. */
export function cuadro(a: Arte, t: number, o: { hover?: boolean; ancho?: number; alto?: number; efecto?: number } = {}): string {
    const base = cuadroSolo(a, t, o);
    const ef = o.efecto === undefined ? undefined : efectoDe(a);
    if (!ef || !(o.efecto! >= 0 && o.efecto! < ef.dura)) return base;
    const ancho = o.ancho ?? ANCHO, alto = o.alto ?? ALTO;
    let texto = base;
    try { texto = ef.aplicar(base, o.efecto!, ancho, alto); } catch { return base; }
    return ajustar(String(texto ?? '').split('\n'), ancho, alto);
}

function cuadroSolo(a: Arte, t: number, o: { hover?: boolean; ancho?: number; alto?: number }): string {
    const ancho = o.ancho ?? ANCHO, alto = o.alto ?? ALTO;
    const hover = !!o.hover;
    const cs = hover && a.alHover.cuadros ? a.alHover.cuadros : a.cuadros;
    if (typeof cs === 'function') {
        let texto = '';
        try { texto = cs(t, ancho, alto, { hover }); } catch { texto = ''; }
        return ajustar(String(texto ?? '').split('\n'), ancho, alto);
    }
    const i = indice(a, t, hover);
    return encuadrar(cs, ancho, alto)[i % cs.length];
}

/** Qué número de cuadro va en el instante `t`: con él se sabe si hay que redibujar (solo cuando cambia). */
export const indice = (a: Arte, t: number, hover = false): number =>
    Math.max(0, Math.floor(t * (hover && a.alHover.cuadros ? a.alHover.fps : a.fps)));

/** Cuánto más rápido corre su reloj con el mouse encima: el ritmo de hover sobre el suyo (una escena aparte corre a su
 *  ritmo propio, sin acelerar el reloj). */
export const aceleracion = (a: Arte): number => (a.alHover.cuadros ? 1 : a.alHover.fps / a.fps);

/** Una lista de líneas, en el lienzo: cada una recortada o rellenada a `ancho`, y `alto` líneas. */
function ajustar(lineas: string[], ancho: number, alto: number): string {
    const fila = (l: string) => { const c = [...(l ?? '')]; return c.length >= ancho ? c.slice(0, ancho).join('') : c.join('') + ' '.repeat(ancho - c.length); };
    const salida: string[] = [];
    for (let i = 0; i < alto; i++) salida.push(fila(lineas[i] ?? ''));
    return salida.join('\n');
}

const enCache = new WeakMap<readonly string[], Map<string, string[]>>();

/** Los cuadros de una lista, centrados juntos en el lienzo (la caja que los contiene a todos va al medio; cada uno, arriba
 *  a la izquierda de esa caja: así no saltan de un cuadro al otro), y recortados si no caben. */
export function encuadrar(cs: readonly string[], ancho = ANCHO, alto = ALTO): string[] {
    const k = `${ancho}×${alto}`;
    const ya = enCache.get(cs)?.get(k);
    if (ya) return ya;
    const partidos = cs.map(c => c.replace(/\t/g, '    ').split('\n').map(l => l.replace(/\s+$/, '')));
    const caja = { w: Math.max(0, ...partidos.flat().map(l => [...l].length)), h: Math.max(0, ...partidos.map(p => p.length)) };
    const x = Math.max(0, Math.floor((ancho - caja.w) / 2)), y = Math.max(0, Math.floor((alto - caja.h) / 2));
    const listos = partidos.map(p => ajustar([...Array<string>(y).fill(''), ...p.map(l => ' '.repeat(x) + l)], ancho, alto));
    if (!enCache.has(cs)) enCache.set(cs, new Map());
    enCache.get(cs)!.set(k, listos);
    return listos;
}

// ── los efectos de hover: lo que cruza el arte cuando entra el mouse o el foco ──

/** Un efecto de hover: lo que le pasa al cuadro cuando el mouse (o el foco) entra en su tarjeta. Pasa una vez, en `dura`
 *  segundos, y deja el cuadro como estaba. `aplicar` recibe el cuadro del arte (ya del lienzo) y los segundos desde que
 *  entró (los de la pared, no el reloj del arte, que se acelera), y da el cuadro con el efecto encima; tiene que ser
 *  pura, como un arte: el mismo cuadro y el mismo instante dan lo mismo. Se redibuja a `fps` mientras pasa. */
export interface Efecto {
    nombre?: string;
    que?: string;
    /** cuánto dura una pasada, en segundos */
    dura: number;
    /** a qué ritmo se redibuja mientras pasa (de fábrica, 30) */
    fps?: number;
    aplicar: (cuadro: string, t: number, ancho: number, alto: number) => string;
}

const efectos = new Map<string, Efecto>();

/** El efecto de un arte que no dice otro (y no tiene escena de hover propia). */
export const EFECTO = 'ola';
/** Lo que dice un arte que no quiere ninguno. */
export const SIN_EFECTO = 'ninguno';

/** Registrar un efecto de hover (o reemplazar el que tenía esa clave). */
export function registrarEfecto(clave: string, def: Efecto): Efecto {
    if (!CLAVE.test(clave) || clave === SIN_EFECTO) throw new Error(`«${clave}»: la clave de un efecto va en minúsculas, números y guiones`);
    if (!(def.dura > 0)) throw new Error(`«${clave}»: un efecto dura algo`);
    const e: Efecto = { ...def, nombre: def.nombre ?? clave, fps: acotarEfecto(def.fps ?? 30) };
    efectos.set(clave, e);
    for (const f of oyentes) f();
    return e;
}

const acotarEfecto = (fps: number) => (Number.isFinite(fps) ? Math.max(1, Math.min(60, fps)) : 30);

/** Un efecto por su clave. */
export const efecto = (clave: string): Efecto | undefined => efectos.get(clave);

/** El efecto de hover de un arte: el que dice (`alHover.efecto`: uno registrado, uno propio, o ninguno); si no dice y
 *  tiene escena de hover propia, ninguno (manda su escena); si no, la ola. Una clave que no hay: la ola. */
export function efectoDe(a: Arte): Efecto | undefined {
    const e = a.alHover.efecto;
    if (e === SIN_EFECTO) return undefined;
    if (e && typeof e === 'object') return e.dura > 0 ? e : undefined;
    if (e) return efectos.get(e) ?? efectos.get(EFECTO);
    return a.alHover.cuadros ? undefined : efectos.get(EFECTO);
}

/** El número de cuadro del efecto a los `t` segundos (para saber si redibujar), o -1 si ya pasó. */
export const indiceEfecto = (ef: Efecto, t: number): number => (t >= 0 && t < ef.dura ? Math.floor(t * (ef.fps ?? 30)) : -1);

// ── un arte escrito en un archivo (`<raiz>/.telar/arte/<clave>.txt`) ──

/** Lo que se lee de un archivo de arte: sus cuadros y lo que dice arriba. */
export interface ArteTexto { def: DefArte; avisos: string[] }

const AJUSTE = /^\s*(fps|hover|nombre|que|para|efecto)\s*[:=]\s*(.*?)\s*$/i;

/** Lee un arte escrito como texto: los cuadros separados por una línea que dice solo `---`; desde una que dice
 *  `--- hover`, los que siguen son la escena de cuando el mouse está encima. Si la primera parte son solo líneas
 *  `clave: valor` (fps, hover, nombre, que, para, efecto), es la cabecera. Error si no queda ningún cuadro; lo que no se
 *  entiende de la cabecera, en `avisos`. */
export function leerArteTexto(texto: string): ArteTexto {
    const lineas = texto.replace(/\r\n?/g, '\n').replace(/^﻿/, '').split('\n');
    const partes: { hover: boolean; lineas: string[] }[] = [{ hover: false, lineas: [] }];
    let enHover = false;
    for (const l of lineas) {
        const sep = /^---\s*(hover)?\s*$/i.exec(l.trimEnd());
        if (sep) {
            if (sep[1]) enHover = true;
            partes.push({ hover: enHover, lineas: [] });
            continue;
        }
        partes[partes.length - 1].lineas.push(l);
    }
    const avisos: string[] = [];
    const def: DefArte = { cuadros: [], origen: 'archivo' };
    const primera = partes[0].lineas.filter(l => l.trim());
    if (partes.length > 1 && primera.length && primera.every(l => AJUSTE.test(l))) {
        for (const l of primera) {
            const [, k, v] = AJUSTE.exec(l)!;
            const clave = k.toLowerCase();
            if (clave === 'fps' || clave === 'hover') {
                const n = Number(v.replace(',', '.'));
                if (!Number.isFinite(n) || n <= 0) { avisos.push(`«${l.trim()}»: se esperaba un número de cuadros por segundo`); continue; }
                if (clave === 'fps') def.fps = n; else def.alHover = { ...def.alHover, fps: n };
            } else if (clave === 'efecto') {
                const k = v.toLowerCase();
                if (k !== SIN_EFECTO && !CLAVE.test(k)) { avisos.push(`«${l.trim()}»: un efecto es «${EFECTO}», «${SIN_EFECTO}» u otra clave`); continue; }
                def.alHover = { ...def.alHover, efecto: k };
            } else if (clave === 'nombre') def.nombre = v;
            else if (clave === 'que') def.que = v;
            else def.para = v.split(',').map(x => x.trim()).filter(Boolean);
        }
        partes.shift();
    }
    // las líneas en blanco de arriba y de abajo de cada cuadro no son del dibujo (el lienzo lo centra)
    const limpio = (ls: string[]) => {
        let a = 0, b = ls.length;
        while (a < b && !ls[a].trim()) a++;
        while (b > a && !ls[b - 1].trim()) b--;
        return ls.slice(a, b).join('\n');
    };
    const base = partes.filter(p => !p.hover).map(p => limpio(p.lineas)).filter(Boolean);
    const hover = partes.filter(p => p.hover).map(p => limpio(p.lineas)).filter(Boolean);
    if (!base.length) throw new Error(hover.length ? 'tiene escena de hover pero ningún cuadro antes de «--- hover»' : 'no tiene ningún cuadro');
    def.cuadros = base;
    if (hover.length) def.alHover = { ...def.alHover, cuadros: hover };
    return { def, avisos };
}

/** Registra los artes de los archivos de la raíz (lo que da `GET /arte`): los que no se leen quedan fuera, con su porqué;
 *  los que ya no están se olvidan. Uno de archivo con la clave de uno de fábrica lo reemplaza. */
export function registrarDeArchivos(lista: readonly { nombre: string; texto: string }[]): { registrados: string[]; errores: Record<string, string> } {
    const registrados: string[] = [], errores: Record<string, string> = {};
    const vienen = new Set(lista.map(x => x.nombre));
    for (const a of artes()) if (a.origen === 'archivo' && !vienen.has(a.clave)) olvidarArte(a.clave);
    for (const { nombre, texto } of lista) {
        try {
            const { def } = leerArteTexto(texto);
            registrarArte(nombre, def);
            registrados.push(nombre);
        } catch (e) { errores[nombre] = (e as Error).message; }
    }
    return { registrados, errores };
}
