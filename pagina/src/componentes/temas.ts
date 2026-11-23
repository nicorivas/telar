// Los temas de la página: sus colores (media/css/tokens.css, el de fábrica, y temas.css, los demás). Uno se pone en
// <html data-tema>. Cuál: el que elige el ajuste `tema` del modo puesto (web/modos.ts) o, si el mundo puesto declara uno
// (`[mundos.<n>] tema`, web/mundo.ts), el del mundo, que le gana al del modo (`queRige`). Los mismos nombres que
// `telar.modos.TEMAS`, que valida el ajuste y el tema de un mundo.
//
// Los de la noche (`noche`) son oscuros y cálidos, con poca luz azul: el fondo y el texto tiran a ámbar, y el azul (el
// acento) es una salvia, terrosa como el resto. Cada uno cumple lo que mide `npm run prueba:temas` con las cuentas de abajo
// (las mismas que muestra /componentes › tokens › contraste): el texto y cada tinta, 4,5:1 o más contra los fondos donde
// va; las tintas con significado, distintas entre sí (el peligro, más); el acento, distinto de lo tenue; y menos luz azul
// que el de fábrica.
//
// Cada máquina puede cambiar los colores principales de un tema (`[temas.<tema>]`, telar.temas; ⚙ temas): sus fondos y
// sus líneas (`FONDOS`) y sus tintas de letra (`EDITABLES`). Los pone web/colores.ts encima de este CSS, con `css` de
// abajo; `paleta` da las opciones que combinan con un tema y `avisos` lo que se lee mal o se confunde con otra. Y puede
// tener temas propios (`[temas.<nombre>] base`): uno de fábrica con otro nombre y sus colores encima. Se conocen al
// llegar de la configuración (`registrar`, desde web/colores.ts) y desde ahí valen donde vale uno de fábrica (`todos`,
// `existe`, `queRige`); su CSS es el de su base, copiado con su nombre (`css`, con `reglas`).

export interface Tema {
    clave: string; nombre: string; claro: boolean; descripcion: string;
    /** para la noche: oscuro, cálido y con poca luz azul (lo que la prueba le exige) */
    noche?: boolean;
    /** de uno propio: el de fábrica del que parte (su «de fábrica») */
    base?: string;
}

export const TEMAS: readonly Tema[] = [
    { clave: 'telar', nombre: 'telar', claro: false, descripcion: 'el de fábrica: catppuccin mocha' },
    { clave: 'latte', nombre: 'latte', claro: true, descripcion: 'catppuccin latte, el claro de la misma familia' },
    { clave: 'riso', nombre: 'riso', claro: false, descripcion: 'tintas fluorescentes de risografía sobre papel negro' },
    { clave: 'papel', nombre: 'papel', claro: true, descripcion: 'las tintas de risografía sobre papel claro' },
    { clave: 'brasa', nombre: 'brasa', claro: false, noche: true, descripcion: 'para la noche: café oscuro y crema, el acento en salvia' },
    { clave: 'rescoldo', nombre: 'rescoldo', claro: false, noche: true, descripcion: 'para la noche, más suave: menos contraste y tintas más quietas' },
    { clave: 'ambar', nombre: 'ámbar', claro: false, noche: true, descripcion: 'para la noche, el más cálido: el texto en ámbar, casi sin azul' },
];

export const DE_FABRICA = 'telar';

/** los temas propios de esta máquina, en el orden de la configuración */
let propios: Tema[] = [];

/** Los temas que se pueden elegir: los de fábrica, en su orden, y los propios. */
export const todos = (): readonly Tema[] => [...TEMAS, ...propios];
/** Un tema por su clave (de fábrica o propio). */
export const de = (clave: string | undefined): Tema | undefined => (clave ? todos().find(t => t.clave === clave) : undefined);
/** Si se conoce ese tema. */
export const existe = (clave: string | undefined): boolean => !!de(clave);
/** Si es uno de los de fábrica. */
export const esDeFabrica = (clave: string | undefined): boolean => !!clave && TEMAS.some(t => t.clave === clave);
/** Su nombre como se muestra (ámbar, con su tilde; uno propio, su clave). */
export const nombre = (clave: string): string => de(clave)?.nombre ?? clave;
/** El de fábrica del que sale: él mismo, o la base de uno propio. */
export const baseDe = (clave: string): string => de(clave)?.base ?? clave;

/** Los temas propios que dice la configuración (`[temas.<nombre>] base`): cada uno es su base con otro nombre. Lo que no
 *  es uno (un nombre de fábrica, una base que no existe) se deja fuera. Devuelve si cambió algo. */
export function registrar(lista: readonly { clave: string; base: string }[]): boolean {
    const nuevos: Tema[] = [];
    for (const { clave, base } of lista) {
        const b = TEMAS.find(t => t.clave === base);
        if (!b || esDeFabrica(clave) || !NOMBRE.test(clave) || nuevos.some(t => t.clave === clave)) continue;
        nuevos.push({ clave, nombre: clave, claro: b.claro, noche: b.noche, base: b.clave, descripcion: `propio: parte de ${b.nombre}` });
    }
    const antes = JSON.stringify(propios);
    propios = nuevos;
    return JSON.stringify(propios) !== antes;
}

/** El nombre de un tema propio: minúsculas, números y guiones, hasta 24, empezando por una letra (`telar.temas.NOMBRE`). */
export const NOMBRE = /^[a-z][a-z0-9-]{0,23}$/;

/** Lo escrito, como nombre de un tema: en minúsculas, sin tildes, con guiones por los espacios («Noche Azul» →
 *  «noche-azul»). Lo que no se puede, queda (y `problemaNombre` dice qué). */
export const aNombre = (texto: string): string => texto.trim().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[\s_]+/g, '-').replace(/-+/g, '-');

/** Por qué un nombre no sirve para un tema propio nuevo ("" si sirve): uno de fábrica, uno que ya hay, otra forma. */
export function problemaNombre(clave: string): string {
    if (!clave) return 'un nombre';
    if (esDeFabrica(clave)) return `«${clave}» es un tema de fábrica: uno propio se llama de otra forma`;
    if (existe(clave)) return `ya hay un tema «${clave}»`;
    if (!NOMBRE.test(clave)) return 'minúsculas, números y guiones, hasta 24, empezando por una letra';
    return '';
}

/** De dónde sale el tema que se ve. */
export type Origen = 'a-mano' | 'mundo' | 'modo';

/** El tema que rige: el elegido a mano en el modo puesto (hasta cambiar de modo, o de entrar a un mundo con tema); si
 *  no, el del mundo puesto, si declara uno; si no, el del modo. Uno que no se conoce no cuenta. */
export function queRige(o: { aMano?: string; mundo?: string; modo?: string }): { clave: string; por: Origen } {
    if (existe(o.aMano)) return { clave: o.aMano!, por: 'a-mano' };
    if (existe(o.mundo)) return { clave: o.mundo!, por: 'mundo' };
    return { clave: existe(o.modo) ? o.modo! : DE_FABRICA, por: 'modo' };
}

/** Poner un tema en la página (el de fábrica si no se conoce): los tokens cambian solos; la barra del navegador del
 *  teléfono (`theme-color`) toma el fondo nuevo. Devuelve si cambió. */
export function poner(clave: string): boolean {
    const t = existe(clave) ? clave : DE_FABRICA;
    const raiz = document.documentElement;
    const cambio = raiz.dataset.tema !== t;
    if (cambio) raiz.dataset.tema = t;
    // también si el tema es el mismo: su fondo puede ser otro (un color propio)
    const fondo = getComputedStyle(raiz).getPropertyValue('--bg').trim();
    const meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
    if (meta && fondo && meta.content !== fondo) meta.content = fondo;
    return cambio;
}

/** Los colores de una terminal (xterm) con el tema puesto: de los tokens, los mismos del resto de la página. */
export function coloresTerminal(): Record<string, string> {
    const css = getComputedStyle(document.documentElement);
    const t = (nombre: string) => css.getPropertyValue(`--${nombre}`).trim();
    return {
        background: t('bg'), foreground: t('fg'), cursor: t('cursor'), selectionBackground: t('seleccion') || t('negro'),
        black: t('negro'), red: t('rojo'), green: t('verde'), yellow: t('amarillo'), blue: t('azul'), magenta: t('magenta'),
        cyan: t('cian'), white: t('blanco'), brightBlack: t('dim'), brightRed: t('rojo'), brightGreen: t('verde'),
        brightYellow: t('amarillo'), brightBlue: t('azul'), brightMagenta: t('magenta'), brightCyan: t('cian'), brightWhite: t('blanco-claro'),
    };
}

// ── las cuentas del contraste: sin DOM, para la prueba y para /componentes ──

/** Las tintas con significado: el peligro, la atención, el éxito, el acento, lo remoto, lo de un agente, y las de los
 *  mundos y las acciones, que son estas mismas. */
export const TINTAS = ['rojo', 'amarillo', 'verde', 'azul', 'cian', 'violeta', 'magenta'] as const;
/** Lo que se lee como texto: el texto, el tenue (la meta, lo de al lado), los blancos de la terminal y cada tinta. */
export const TEXTOS = ['fg', 'dim', 'blanco', 'blanco-claro', ...TINTAS] as const;
/** El mínimo de WCAG para el texto normal (AA). */
export const MINIMO = 4.5;

type RGB = [number, number, number];

/** Un color de CSS como lo da un tema: `#rgb`, `#rrggbb` o `rgb(r g b)` / `rgb(r, g, b)`. undefined si no se entiende. */
export function rgb(css: string): RGB | undefined {
    const t = css.trim().toLowerCase();
    let m = /^#([0-9a-f]{3})$/.exec(t);
    if (m) return [...m[1]].map(c => parseInt(c + c, 16) / 255) as RGB;
    m = /^#([0-9a-f]{6})(?:[0-9a-f]{2})?$/.exec(t);
    if (m) return [0, 2, 4].map(i => parseInt(m![1].slice(i, i + 2), 16) / 255) as RGB;
    m = /^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)/.exec(t);
    if (m) return [m[1], m[2], m[3]].map(x => Number(x) / 255) as RGB;
    return undefined;
}

const alfa = (a: string | undefined): number => (a === undefined ? 1 : a.endsWith('%') ? Number(a.slice(0, -1)) / 100 : Number(a));

/** Un color de CSS con su opacidad (de 0 a 1): lo que entiende `rgb`, y además `#rrggbbaa`, `rgb(r g b / a)`,
 *  `rgba(r, g, b, a)` y `color(srgb r g b / a)` (lo que da el navegador de un `color-mix`, como las líneas y la selección
 *  de fábrica). undefined si no se entiende. */
export function rgba(css: string): [number, number, number, number] | undefined {
    const t = css.trim().toLowerCase();
    let m = /^#([0-9a-f]{6})([0-9a-f]{2})$/.exec(t);
    if (m) return [...[0, 2, 4].map(i => parseInt(m![1].slice(i, i + 2), 16) / 255), parseInt(m[2], 16) / 255] as [number, number, number, number];
    m = /^color\(srgb\s+([-\d.e]+)\s+([-\d.e]+)\s+([-\d.e]+)(?:\s*\/\s*([\d.]+%?))?\s*\)$/.exec(t);
    if (m) return [Number(m[1]), Number(m[2]), Number(m[3]), alfa(m[4])];
    m = /^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)(?:\s*[,/]\s*([\d.]+%?))?\s*\)$/.exec(t);
    if (m) return [Number(m[1]) / 255, Number(m[2]) / 255, Number(m[3]) / 255, alfa(m[4])];
    const c = rgb(t);
    return c ? [...c, 1] : undefined;
}

/** Un color con opacidad, puesto sobre un fondo: el que se ve. undefined si no se entiende. */
export function opaco(css: string, sobre: RGB): RGB | undefined {
    const c = rgba(css);
    return c ? mezcla([c[0], c[1], c[2]], sobre, Math.min(1, Math.max(0, c[3]))) : undefined;
}

const lineal = (c: number) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);

/** La luminancia relativa de WCAG. */
export function luminancia(c: RGB): number {
    const [r, g, b] = c.map(lineal);
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** El contraste de WCAG entre dos colores: de 1 a 21. */
export function contraste(a: RGB, b: RGB): number {
    const [x, y] = [luminancia(a), luminancia(b)];
    return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}

/** Un color en OKLab (L de 0 a 1). */
export function oklab(c: RGB): RGB {
    const [r, g, b] = c.map(lineal);
    const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
    const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
    const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
    return [0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
        1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
        0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s];
}

/** Cuán distintos se ven dos colores: la distancia en OKLab, por 100 (bajo 2 no se distinguen; el de fábrica tiene
 *  sus dos tintas más cercanas, el verde y el cian, a 7). */
export function distancia(a: RGB, b: RGB): number {
    const [x, y] = [oklab(a), oklab(b)];
    return 100 * Math.hypot(x[0] - y[0], x[1] - y[1], x[2] - y[2]);
}

/** Cuánto de la luz que da un color es azul: el canal azul lineal sobre la suma de los tres (un gris, un tercio). */
export function luzAzul(c: RGB): number {
    const [r, g, b] = c.map(lineal);
    return r + g + b ? b / (r + g + b) : 0;
}

/** `a` sobre `b` en esa proporción (lo que hace `color-mix(in srgb, a p%, b)`). */
export const mezcla = (a: RGB, b: RGB, p: number): RGB => a.map((x, i) => x * p + b[i] * (1 - p)) as RGB;

/** Un color en OKLCH (claridad de 0 a 1, croma y tono en grados) de vuelta a sRGB, sin recortar: fuera de la gama, un
 *  canal queda bajo 0 o sobre 1. */
export function desdeOklch(l: number, c: number, h: number): RGB {
    const a = c * Math.cos(h * Math.PI / 180), b = c * Math.sin(h * Math.PI / 180);
    const l_ = (l + 0.3963377774 * a + 0.2158037573 * b) ** 3;
    const m_ = (l - 0.1055613458 * a - 0.0638541728 * b) ** 3;
    const s_ = (l - 0.0894841775 * a - 1.2914855480 * b) ** 3;
    const gamma = (x: number) => (x <= 0.0031308 ? 12.92 * x : 1.055 * Math.sign(x) * Math.abs(x) ** (1 / 2.4) - 0.055);
    return [4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
        -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
        -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_].map(gamma) as RGB;
}

/** Un color en OKLCH: [claridad, croma, tono en grados]. */
export function oklch(c: RGB): RGB {
    const [l, a, b] = oklab(c);
    return [l, Math.hypot(a, b), (Math.atan2(b, a) * 180 / Math.PI + 360) % 360];
}

/** `#rrggbb`, con cada canal recortado a la gama. */
export const hex = (c: RGB): string => '#' + c.map(x => Math.round(Math.min(1, Math.max(0, x)) * 255).toString(16).padStart(2, '0')).join('');

/** Lo que se mide de un tema, con sus colores resueltos (`--bg`, `--fg`… sin los guiones): cada texto contra cada fondo
 *  donde va (el de la página, el de las barras y ventanas, y la fila activa: el acento al 16% sobre el fondo,
 *  `--item-fondo-activa`), los pares de tintas, del más cercano al más lejano, y la luz azul del fondo y del texto. */
export interface Medida {
    contrastes: { texto: string; fondo: string; razon: number }[];
    pares: { a: string; b: string; distancia: number }[];
    luzAzul: { fondo: number; texto: number };
}

export function medir(colores: Record<string, string>): Medida {
    const c = (k: string): RGB => {
        const v = rgb(colores[k] ?? '');
        if (!v) throw new Error(`el tema no dice --${k} como un color (${colores[k] ?? 'falta'})`);
        return v;
    };
    const fondos: [string, RGB][] = [['bg', c('bg')], ['bg-barra', c('bg-barra')], ['fila activa', mezcla(c('azul'), c('bg'), 0.16)]];
    const contrastes = TEXTOS.flatMap(t => fondos.map(([fondo, f]) => ({ texto: t, fondo, razon: contraste(c(t), f) })));
    const pares = TINTAS.flatMap((a, i) => TINTAS.slice(i + 1).map(b => ({ a, b, distancia: distancia(c(a), c(b)) })))
        .sort((x, y) => x.distancia - y.distancia);
    return { contrastes, pares, luzAzul: { fondo: luzAzul(c('bg')), texto: luzAzul(c('fg')) } };
}

// ── los colores principales de un tema, cambiados en esta máquina (`[temas.<tema>]`, ⚙ temas) ──

/** Un color que se puede cambiar: su primitivo (`--azul` es `azul`), cómo se llama por lo que hace y dónde se ve. */
export interface Editable { tinta: string; nombre: string; para: string }

/** Los fondos y las líneas que se pueden cambiar: lo mínimo que cambia la cara de un tema (lo demás sale de ellos: la
 *  superficie es el fondo; el hover, el texto apenas; la fila activa, el acento sobre el fondo). Los mismos de
 *  `telar.temas.FONDOS`. El fondo y las barras son primitivos de cada tema; las líneas y la selección, de fábrica, se
 *  derivan del texto (`--linea`, `--sel` en tokens.css): cambiadas, quedan de un color fijo. */
export const FONDOS: readonly Editable[] = [
    { tinta: 'bg', nombre: 'fondo', para: 'la página, la terminal, las filas' },
    { tinta: 'bg-barra', nombre: 'barras', para: 'las barras de arriba, las ventanas, el menú' },
    { tinta: 'linea', nombre: 'líneas', para: 'las que parten filas y secciones, el borde de una ventana' },
    { tinta: 'sel', nombre: 'selección', para: 'lo elegido en un menú o en una lista' },
];

/** Las tintas de texto que se pueden cambiar, la que más se ve primero: las mismas de `telar.temas.TINTAS`. */
export const EDITABLES: readonly Editable[] = [
    { tinta: 'fg', nombre: 'texto', para: 'lo que se lee: los hilos, las tareas, la terminal' },
    { tinta: 'dim', nombre: 'tenue', para: 'la meta, las horas, lo de al lado' },
    { tinta: 'amarillo', nombre: 'títulos', para: 'las cabeceras (HILOS, DECIDIR), los agentes, lo que te espera' },
    { tinta: 'azul', nombre: 'acento', para: 'los enlaces, las pestañas, la fila activa, lo que trabaja, las reuniones' },
    { tinta: 'violeta', nombre: 'agentes', para: 'la letra de un agente, el modo y la vista que se ven' },
    { tinta: 'verde', nombre: 'éxito', para: 'lo que terminó, lo libre' },
    { tinta: 'cian', nombre: 'remoto', para: 'lo de otra máquina, la conversación de un hilo' },
    { tinta: 'magenta', nombre: 'rosa', para: 'un mundo, las decisiones, las carpetas de la carga' },
    { tinta: 'rojo', nombre: 'peligro', para: 'lo que falló, lo que borra' },
];

/** Todo lo que se puede cambiar de un tema, en el orden de ⚙ temas: los fondos y después las tintas. */
export const COLORES: readonly Editable[] = [...FONDOS, ...EDITABLES];
/** Si es un fondo o una línea (y no una tinta de letra). */
export const esFondo = (clave: string): boolean => FONDOS.some(f => f.tinta === clave);

/** Los colores de un tema que hacen falta para medirlo (`medir`, `avisos`, `paleta`) y mostrarlo (⚙ temas). */
export const PRIMITIVOS = ['fg', 'bg', 'dim', 'bg-barra', 'linea', 'sel', 'blanco', 'blanco-claro', ...TINTAS] as const;

/** Los colores propios de una máquina: tema → {color: #rrggbb}. */
export type Propios = Record<string, Record<string, string>>;

/** Lo que `css` necesita además de los colores: las reglas de un tema de fábrica (el cuerpo de cada una: lo que va entre
 *  llaves de `[data-tema="brasa"]`), para copiarlas a uno propio que parte de él; y, en /componentes, `soloPropios`: los
 *  de fábrica se quedan como vienen, y solo los propios llevan sus colores. */
export interface OpcionesCss { reglas?: (base: string) => readonly string[]; soloPropios?: boolean }

/** El CSS que pone los colores propios encima de los de fábrica: un bloque por tema, que gana por ser más específico que
 *  el de temas.css. Lo que lleva `data-fabrica` (la sonda de ⚙ temas) se queda con los de fábrica. Solo colores conocidos y
 *  `#rrggbb`: lo demás no se escribe. Con un fondo propio, `color-scheme` dice si es claro u oscuro (las barras de
 *  desplazamiento, el selector de color). Un tema propio lleva antes las reglas de su base con su nombre (`reglas`): así
 *  es ese tema entero, con lo que dice encima; su «de fábrica» (`data-fabrica`) es el de su base. */
export function css(colores: Propios, o: OpcionesCss = {}): string {
    const bien = /^#[0-9a-f]{6}$/i;
    const bloques: string[] = [];
    for (const t of todos()) {
        if (o.soloPropios && !t.base) continue;
        const v = colores[t.clave] ?? {};
        if (t.base) for (const cuerpo of o.reglas?.(t.base) ?? []) bloques.push(`[data-tema="${t.clave}"] { ${cuerpo} }`);
        const lineas = COLORES.filter(e => bien.test(v[e.tinta] ?? '')).map(e => `--${e.tinta}: ${v[e.tinta].toLowerCase()};`);
        const fondo = bien.test(v.bg ?? '') ? rgb(v.bg) : undefined;
        if (fondo) lineas.push(`color-scheme: ${luminancia(fondo) > 0.18 ? 'light' : 'dark'};`);
        if (lineas.length) bloques.push(`[data-tema="${t.clave}"]:not([data-fabrica]) { ${lineas.join(' ')} }`);
    }
    return bloques.join('\n');
}

/** Las reglas de un tema de fábrica en unas hojas de estilo (las de la página, `document.styleSheets`): el cuerpo de cada
 *  regla cuyo selector es ese tema (`[data-tema="brasa"]`; del de fábrica, `:root, [data-tema="telar"]`), dentro de
 *  capas y medias también. Lo que no se puede leer (una hoja de otro origen, una que no cargó) no está. */
export function reglasDe(hojas: Iterable<{ cssRules?: ArrayLike<unknown> }>, base: string): string[] {
    const buscado = `[data-tema="${base}"]`;
    const salida: string[] = [];
    const recorrer = (reglas: ArrayLike<unknown> | undefined) => {
        for (const r of Array.from(reglas ?? []) as { selectorText?: string; style?: { cssText: string }; cssRules?: ArrayLike<unknown> }[]) {
            if (r.selectorText !== undefined && r.style) {
                if (r.selectorText.split(',').map(x => x.trim().replace(/'/g, '"')).includes(buscado) && r.style.cssText) salida.push(r.style.cssText);
            } else if (r.cssRules) recorrer(r.cssRules);
        }
    };
    for (const h of hojas) {
        let reglas: ArrayLike<unknown> | undefined;
        try { reglas = h.cssRules; } catch { continue; }
        recorrer(reglas);
    }
    return salida;
}

/** Lo que se lee mal o se confunde, de una tinta con los colores de su tema (los resueltos: con los propios). */
export interface Aviso { tipo: 'contraste' | 'parecido'; texto: string; razon?: number; con?: string }

/** Desde qué distancia una tinta elegida se confunde con otra (`distancia`, bajo 2 no se distinguen): las tintas con
 *  significado entre sí, bajo 5 (con el peligro, bajo 8); el tenue y el texto, bajo 10; los títulos y el texto, bajo 6; el
 *  acento y lo tenue, bajo 5. Más holgado que lo que la prueba les pide a los temas de fábrica (8, 11, 14, 8 y 7): eso es
 *  lo que se diseña; esto, lo que ya no se distingue. */
function lejania(a: string, b: string): number {
    const par = new Set([a, b]);
    if (par.has('fg') && par.has('dim')) return 10;
    if (par.has('fg') && par.has('amarillo')) return 6;
    if (par.has('azul') && par.has('dim')) return 5;
    if (par.has('fg') || par.has('dim')) return 0;
    return par.has('rojo') ? 8 : 5;
}

const nombreDe = (clave: string) => COLORES.find(e => e.tinta === clave)?.nombre ?? clave;
const coma = (n: number) => n.toFixed(1).replace('.', ',');
const LETRAS = EDITABLES.map(e => e.tinta);

/** Dónde va cada fondo de `medir`, en palabras. */
const dondeVa = (fondo: string) => (fondo === 'bg' ? 'el fondo' : fondo === 'bg-barra' ? 'las barras' : 'la fila activa');

/** Lo que tiene de malo un color con esos colores. De una tinta de letra: bajo 4,5:1 sobre algún fondo donde va (el de
 *  la página, el de las barras, la fila activa: el peor), y las tintas de las que no se distingue. De un fondo: las letras
 *  que sobre él quedan bajo 4,5:1 (con `fabrica`, solo las que sobre el de fábrica se leían bien: lo demás no es cosa
 *  suya); de la selección, el texto sobre ella; de las líneas, si casi no se ven. Vacío si se lee bien. */
export function avisos(colores: Record<string, string>, tinta: string, fabrica?: Record<string, string>): Aviso[] {
    if (esFondo(tinta)) return avisosFondo(colores, tinta, fabrica);
    const m = medir(colores);
    const salida: Aviso[] = [];
    const peor = m.contrastes.filter(c => c.texto === tinta).sort((x, y) => x.razon - y.razon)[0];
    if (peor && peor.razon < MINIMO) {
        salida.push({ tipo: 'contraste', razon: peor.razon,
            texto: `se lee a ${coma(peor.razon)}:1 sobre ${dondeVa(peor.fondo)} (bien, desde ${MINIMO.toString().replace('.', ',')}:1)` });
    }
    // el acento tiñe la fila activa: lo que se lee bien sobre el fondo y mal sobre ella, lo deja mal él (lo que ya se leía
    // mal sobre el fondo no es cosa suya)
    if (tinta === 'azul') {
        const sobre = (t: string, f: string) => m.contrastes.find(c => c.texto === t && c.fondo === f)?.razon ?? 0;
        const bajos = LETRAS.filter(t => t !== 'azul' && sobre(t, 'bg') >= MINIMO && sobre(t, 'fila activa') < MINIMO);
        if (bajos.length) salida.push({ tipo: 'contraste', texto: `la fila activa, teñida con él, deja mal ${bajos.map(t => `«${nombreDe(t)}»`).join(', ')}` });
    }
    const de = rgb(colores[tinta] ?? '');
    if (de) {
        for (const e of EDITABLES) {
            const minimo = e.tinta === tinta ? 0 : lejania(tinta, e.tinta);
            const otro = rgb(colores[e.tinta] ?? '');
            if (!minimo || !otro) continue;
            const d = distancia(de, otro);
            if (d < minimo) salida.push({ tipo: 'parecido', con: e.tinta, texto: `se confunde con «${e.nombre}» (a ${coma(d)}; distintas, desde ${minimo})` });
        }
    }
    return salida;
}

/** Desde qué contraste una línea se ve sobre el fondo: las de fábrica, a 1,4:1 o más. */
export const LINEA_MINIMA = 1.15;

function avisosFondo(colores: Record<string, string>, fondo: string, fabrica?: Record<string, string>): Aviso[] {
    const c = (k: string, de = colores) => rgb(de[k] ?? '');
    const bg = c('bg');
    if (!bg) return [];
    if (fondo === 'linea') {
        const l = c('linea');
        const r = l ? Math.min(contraste(l, bg), contraste(l, c('bg-barra') ?? bg)) : 0;
        return l && r < LINEA_MINIMA ? [{ tipo: 'contraste', razon: r, texto: `casi no se ve sobre el fondo y las barras (a ${coma(r)}:1)` }] : [];
    }
    if (fondo === 'sel') {
        const sel = c('sel'), fg = c('fg');
        const r = sel && fg ? contraste(fg, sel) : 0;
        return sel && fg && r < MINIMO ? [{ tipo: 'contraste', razon: r, texto: `el texto se lee a ${coma(r)}:1 sobre ella (bien, desde ${MINIMO.toString().replace('.', ',')}:1)` }] : [];
    }
    // el fondo y las barras: las letras que van encima (sobre el fondo, también la fila activa, que es el acento sobre él)
    const lugares = fondo === 'bg' ? ['bg', 'fila activa'] : ['bg-barra'];
    const razones = (de: Record<string, string>) => {
        const m = medir(de);
        return (t: string) => Math.min(...m.contrastes.filter(x => x.texto === t && lugares.includes(x.fondo)).map(x => x.razon));
    };
    // lo que es suyo: las letras como están, sobre el de fábrica y sobre este (una letra cambiada que se lee mal en los dos
    // es cosa de ella, y lo dice su fila)
    let ahora: (t: string) => number, antes: ((t: string) => number) | undefined;
    try {
        ahora = razones(colores);
        antes = fabrica?.[fondo] ? razones({ ...colores, [fondo]: fabrica[fondo] }) : undefined;
    } catch { return []; }
    const bajos = LETRAS.filter(t => ahora(t) < MINIMO && (!antes || antes(t) >= MINIMO));
    if (!bajos.length) return [];
    const peor = Math.min(...bajos.map(ahora));
    return [{ tipo: 'contraste', razon: peor, texto: `sobre ${fondo === 'bg' ? 'él' : 'ellas'} se leen bajo ${MINIMO.toString().replace('.', ',')}:1 `
        + bajos.map(t => `«${nombreDe(t)}» (${coma(ahora(t))}:1)`).join(', ') }];
}

/** Lo que un fondo cambiado le hace a una letra que no se tocó: lo que de fábrica se leía bien y ya no (sus avisos de
 *  contraste, y solo esos). */
export function empeora(colores: Record<string, string>, fabrica: Record<string, string>, tinta: string): Aviso[] {
    const ahora = avisos(colores, tinta).filter(a => a.tipo === 'contraste' && a.razon !== undefined);
    if (!ahora.length) return [];
    const antes = avisos(fabrica, tinta).filter(a => a.tipo === 'contraste' && a.razon !== undefined);
    return antes.length ? [] : ahora;
}

/** Una opción de la paleta: su nombre y su color. */
export interface Opcion { nombre: string; color: string }

/** Las opciones para una tinta: tonos con nombre, a la claridad que esa tinta tiene de fábrica (así cada rol sigue
 *  pesando lo mismo) y con el croma del tema (los de la noche, apagados: terrosos), corridas hasta leerse a 4,5:1 con
 *  holgura sobre el fondo, las barras y la fila activa. Para el texto y lo tenue, neutros con un matiz. Se dejan fuera los
 *  que se confundirían con otra tinta de las de ahora (`ahora`: con los colores propios; sin ellos, los de fábrica): esos
 *  no combinan, dicen otra cosa. Sin la de fábrica (va aparte). */
export function paleta(fabrica: Record<string, string>, tinta: string, noche = false, ahora: Record<string, string> = fabrica): Opcion[] {
    const base = rgb(fabrica[tinta] ?? '');
    const fondo = rgb(fabrica.bg ?? ''), barra = rgb(fabrica['bg-barra'] ?? fabrica.bg ?? '');
    const acento = rgb(ahora.azul ?? fabrica.azul ?? '');
    if (!base || !fondo || !barra || !acento) return [];
    const oscuro = luminancia(fondo) < 0.2;
    const neutro = tinta === 'fg' || tinta === 'dim';
    const cromas = TINTAS.map(t => oklch(rgb(fabrica[t] ?? '') ?? base)[1]).sort((x, y) => x - y);
    const croma = noche ? 0.065 : cromas[Math.floor(cromas.length / 2)];
    const tonos: [string, number, number][] = neutro
        ? [['crema', 85, .035], ['hueso', 95, .018], ['arena', 70, .045], ['piedra', 50, .02], ['rosa', 20, .028],
            ['salvia', 150, .028], ['niebla', 250, .02], ['gris', 0, 0]]
        : [['terracota', 35, croma * 1.2], ['cobre', 58, croma * 1.1], ['ámbar', 80, croma * 1.2], ['oliva', 112, croma],
            ['salvia', 165, croma * .9], ['agua', 200, croma * .85], ['pizarra', 245, croma * .7], ['lavanda', 295, croma * .9],
            ['malva', 330, croma * .85], ['rosa viejo', 12, croma * .8]];
    const [l0] = oklch(base);
    const holgura = MINIMO + 0.4;
    const opciones = tonos.map(([nombre, h, c]) => {
        let l = l0, color = base;
        for (let i = 0; i < 60; i++) {
            // dentro de la gama: con menos croma si no cabe
            let cc = c;
            color = desdeOklch(l, cc, h);
            while (cc > 0 && color.some(x => x < 0 || x > 1)) { cc -= 0.005; color = desdeOklch(l, Math.max(0, cc), h); }
            // la fila activa está teñida con el acento: con el de esta opción, si es el acento
            const fila = mezcla(tinta === 'azul' ? color : acento, fondo, 0.16);
            if (Math.min(contraste(color, fondo), contraste(color, barra), contraste(color, fila)) >= holgura) break;
            l += oscuro ? 0.01 : -0.01;
        }
        return { nombre, color: hex(color) };
    });
    const vistos = new Set<string>();
    return opciones.filter(o => {
        if (vistos.has(o.color)) return false;
        vistos.add(o.color);
        return !avisos({ ...ahora, [tinta]: o.color }, tinta).some(a => a.tipo === 'parecido');
    });
}
