// El ancho de la barra de hilos (#barra, a la izquierda) y de la ficha de un hilo (#lado, a la derecha), a mano: en la
// línea entre cada una y el centro hay una franja de agarre de 6 px, invisible (la línea sigue siendo la de siempre, de un
// píxel), con el cursor col-resize. Arrastrarla cambia el ancho en vivo; mientras se arrastra, la línea va con el acento.
// Un doble clic vuelve al ancho de fábrica (la barra, `minmax(240px, 22vw)`; la ficha, `min(46ch, 40vw)`: media/css/marco.css).
//
// Cada ancho tiene topes: la barra entre 200 px y el 45% de la ventana, la ficha entre 240 px y el 45%, y el centro nunca
// queda con menos de 480 px. Lo elegido se recuerda en este navegador y por pantalla (su tamaño, `screen.width` ×
// `screen.height`): el laptop y el monitor de 27" tienen cada uno el suyo, y al mover la ventana de una a la otra se
// pone el de esa. Sin almacén (o sin nada recordado para esa pantalla), el de fábrica.
//
// Plegar la barra o la ficha (el ‹ de la franja de avisos, la flecha de la ficha) no lo toca: al desplegarla vuelve el
// ancho elegido. Plegada, oculta, o en el teléfono (`body.angosto`, donde la barra es su propia pantalla), no hay franja.
//
// Lo que mide su ancho se ajusta al soltar, no en cada píxel: mientras se arrastra, `arrastrando()` es true (la terminal
// no se mide: un resize a tmux por movimiento), y al soltar (o con el doble clic) la ventana recibe una sola vez
// `EVENTO` (web/terminal.ts lo escucha).
//
// La barra de la derecha del visor de un documento (web/documento-lado.ts) usa el mismo agarre (`agarre`) y guarda su ancho
// aquí mismo, por pantalla (`documento`).
//
// La terminal del centro (web/terminal.ts) se arrastra igual, por su borde (`montarTerminal`): el derecho, o el izquierdo
// si va a la derecha (`[terminal] posicion`). Su ancho se cuenta en columnas: el de fábrica es el de ⚙ terminal (`[terminal]
// columnas`, o el del modo puesto), y arrastrar lo pisa en este navegador y en esta pantalla. Mientras se arrastra el
// marco sigue al puntero de columna en columna (centrada, crece hacia los dos lados) sin tocar la terminal; al soltar,
// la terminal se mide una vez y le manda a tmux el tamaño nuevo. Topes: `COLUMNAS_MINIMAS` y lo que cabe en el centro
// (llegar al tope guarda «todo»). Doble clic: el de ⚙ terminal. Cambiar el ancho en ⚙ terminal olvida lo arrastrado
// (`olvidarTerminal`): lo último que se eligió es lo que se ve.

export type Cual = 'barra' | 'lado';
/** lo que se arrastra: la barra, la ficha, la terminal o la barra de un documento (web/documento-lado.ts) */
export type Arrastrable = Cual | 'terminal' | 'documento';
export interface Topes { min: number; max: number }
/** lo recordado: por pantalla, el ancho de la barra y de la ficha en px, y el de la terminal en columnas (0: todo) */
export type Recordados = Record<string, Partial<Record<Arrastrable, number>>>;

export const CLAVE = 'telar.anchos';
/** lo que recibe la ventana al soltar, una vez, con el ancho ya puesto */
export const EVENTO = 'telar:anchos';
export const MINIMO: Record<Cual, number> = { barra: 200, lado: 240 };
/** el centro (la terminal, el dashboard) nunca con menos que esto */
export const CENTRO_MINIMO = 480;
/** ni una ni la otra más que esta parte de la ventana */
export const FRACCION_MAXIMA = 0.45;
/** la variable de body que lleva cada ancho (marco.css) */
const VARIABLE: Record<Cual, string> = { barra: '--barra-ancho', lado: '--lado-ancho' };

/** Los topes de una, con la ventana de `vista` px y la otra de `otra` px (0 si no se ve). El máximo nunca baja del
 *  mínimo: en una ventana chica gana el mínimo, y el centro se aprieta. */
export function topes(cual: Cual, vista: number, otra: number): Topes {
    const min = MINIMO[cual];
    const max = Math.floor(Math.min(vista * FRACCION_MAXIMA, vista - otra - CENTRO_MINIMO));
    return { min, max: Math.max(min, max) };
}

export const acotar = (x: number, t: Topes): number => Math.round(Math.min(t.max, Math.max(t.min, x)));

/** La pantalla, como clave de lo recordado: «1440x900», «3008x1692». */
export const clavePantalla = (p: { width: number; height: number }): string => `${Math.round(p.width)}x${Math.round(p.height)}`;

/** Lo recordado en el almacén; si no hay, no se lee o no se entiende, nada. */
export function leer(almacen: Pick<Storage, 'getItem'> | null): Recordados {
    try {
        const v = JSON.parse(almacen?.getItem(CLAVE) ?? 'null');
        return v && typeof v === 'object' && !Array.isArray(v) ? v as Recordados : {};
    } catch { return {}; }
}

function guardar(almacen: Pick<Storage, 'setItem'> | null, r: Recordados): void {
    try { almacen?.setItem(CLAVE, JSON.stringify(r)); } catch { /* sin almacén: vale hasta recargar */ }
}

/** Recordar (o, sin valor, olvidar) el ancho de una en una pantalla; la pantalla sin nada se va de lo recordado. */
export function recordar(almacen: Pick<Storage, 'getItem' | 'setItem'> | null, pantalla: string, cual: Arrastrable, valor: number | undefined): void {
    const todo = leer(almacen);
    const suyos = { ...(todo[pantalla] ?? {}) };
    if (valor === undefined) delete suyos[cual]; else suyos[cual] = valor;
    if (Object.keys(suyos).length) todo[pantalla] = suyos; else delete todo[pantalla];
    guardar(almacen, todo);
}

let enCurso: Arrastrable | null = null;
/** Si se está arrastrando una franja: lo que mide su ancho espera a `EVENTO`. */
export const arrastrando = (): boolean => enCurso !== null;

/** Lo que hace una franja al arrastrarla; lo común (el puntero, la captura, la línea marcada) lo pone `agarre`. */
export interface Manejo {
    /** si ahora se puede (se ve, no está plegada, no es el teléfono) */
    puede(): boolean;
    empezar(): void;
    /** cuánto se movió el puntero desde que empezó, en px */
    mover(dx: number): void;
    /** al soltar; `movida`: si llegó a cambiar algo */
    soltar(movida: boolean): void;
    /** el doble clic */
    fabrica(): void;
}

/** Lo que tienen en común las franjas: el pointerdown (sin seleccionar texto, con la captura del puntero), el arrastre
 *  con su umbral de un píxel, el soltar una sola vez (pointerup, pointercancel o la captura perdida) y el doble clic. */
export function agarre(f: HTMLElement, cual: Arrastrable, body: HTMLElement, m: Manejo): void {
    f.setAttribute('role', 'separator');
    f.setAttribute('aria-orientation', 'vertical');
    let desde = 0, movida = false, puntero = -1;
    const terminar = () => {
        if (enCurso !== cual) return;
        enCurso = null;
        delete body.dataset.arrastra;
        try { if (puntero >= 0) f.releasePointerCapture(puntero); } catch { /* ya soltado */ }
        puntero = -1;
        m.soltar(movida);
    };
    f.addEventListener('pointerdown', (ev: PointerEvent) => {
        if (ev.button !== 0 || enCurso || !m.puede()) return;
        ev.preventDefault();   // que no seleccione texto ni le quite el foco a la terminal
        enCurso = cual;
        body.dataset.arrastra = cual;
        desde = ev.clientX; movida = false;
        puntero = ev.pointerId;
        m.empezar();
        try { f.setPointerCapture(ev.pointerId); } catch { /* sin captura: el movimiento llega igual mientras esté encima */ }
    });
    f.addEventListener('pointermove', (ev: PointerEvent) => {
        if (enCurso !== cual) return;
        const dx = ev.clientX - desde;
        if (!movida && Math.abs(dx) < 1) return;
        movida = true;
        m.mover(dx);
    });
    f.addEventListener('pointerup', terminar);
    f.addEventListener('pointercancel', terminar);
    f.addEventListener('lostpointercapture', terminar);
    f.addEventListener('dblclick', () => { if (m.puede()) m.fabrica(); });
}

export interface Entorno {
    body: HTMLElement;
    barra: HTMLElement;
    lado: HTMLElement;
    /** donde va la franja de la barra (#marcos: su borde izquierdo es la línea) */
    marcos: HTMLElement;
    ventana: Pick<Window, 'addEventListener' | 'dispatchEvent' | 'innerWidth'>;
    pantalla: () => { width: number; height: number };
    almacen: (Pick<Storage, 'getItem' | 'setItem'>) | null;
    crear: (tag: string) => HTMLElement;
    /** el evento que recibe la ventana al soltar (en Node no hay `Event`) */
    evento?: () => Event;
}

/** Si una se ve con su ancho (ni plegada ni oculta, ni en el teléfono): solo entonces tiene franja y cuenta. */
function abierta(e: Entorno, cual: Cual): boolean {
    if (e.body.classList.contains('angosto') || e.body.classList.contains('solo')) return false;
    if (cual === 'barra') return !['plegada', 'oculta'].includes(e.body.dataset.barra ?? '');
    return !e.lado.hidden && !e.lado.classList.contains('plegado') && e.body.dataset.lado !== 'oculto';
}

const anchoDe = (el: HTMLElement): number => el.getBoundingClientRect().width;

/** Pone las dos franjas y lo recordado para esta pantalla. Devuelve cómo volver a poner lo recordado (al cambiar de
 *  pantalla lo hace solo, con el `resize` de la ventana). */
export function montar(e: Entorno): { aplicar(): void } {
    let pantalla = clavePantalla(e.pantalla());
    const recordados = () => leer(e.almacen)[pantalla] ?? {};

    /** El ancho de la otra, para los topes: el que tiene si se ve; si no, lo recordado (0 si no hay: es de fábrica, y
     *  la de fábrica se aguanta sola). */
    const otra = (cual: Cual): number => {
        const o: Cual = cual === 'barra' ? 'lado' : 'barra';
        if (abierta(e, o)) return anchoDe(o === 'barra' ? e.barra : e.lado);
        return recordados()[o] ?? 0;
    };
    const poner = (cual: Cual, px: number | undefined) => {
        if (px === undefined) e.body.style.removeProperty(VARIABLE[cual]);
        else e.body.style.setProperty(VARIABLE[cual], `${px}px`);
    };
    const aplicar = () => {
        const r = recordados();
        for (const cual of ['barra', 'lado'] as Cual[]) {
            const px = r[cual];
            poner(cual, px === undefined ? undefined : acotar(px, topes(cual, e.ventana.innerWidth, otra(cual))));
        }
    };
    const avisar = () => e.ventana.dispatchEvent(e.evento ? e.evento() : new Event(EVENTO));

    const franja = (cual: Cual): HTMLElement => {
        const f = e.crear('div');
        f.className = 'tirador';
        f.id = `tirador-${cual}`;
        f.title = `arrastrar: el ancho de ${cual === 'barra' ? 'la barra de hilos' : 'la ficha'} · doble clic: el de fábrica`;
        const el = cual === 'barra' ? e.barra : e.lado;
        let inicial = 0;
        agarre(f, cual, e.body, {
            puede: () => abierta(e, cual),
            empezar: () => { inicial = anchoDe(el); },
            mover: dx => poner(cual, acotar(cual === 'barra' ? inicial + dx : inicial - dx, topes(cual, e.ventana.innerWidth, otra(cual)))),
            soltar: movida => {
                if (!movida) return;
                const px = parseFloat(e.body.style.getPropertyValue(VARIABLE[cual]));
                if (Number.isFinite(px)) recordar(e.almacen, pantalla, cual, px);
                avisar();
            },
            fabrica: () => { recordar(e.almacen, pantalla, cual, undefined); poner(cual, undefined); avisar(); },
        });
        return f;
    };

    e.marcos.appendChild(franja('barra'));
    // la de la ficha, justo después de ella: el CSS la esconde con la ficha (`#lado[hidden] + .tirador`)
    const deLado = franja('lado');
    e.lado.insertAdjacentElement('afterend', deLado);
    aplicar();
    e.ventana.addEventListener('resize', () => {
        // otra pantalla (la ventana se movió al monitor): lo de esa; la misma, lo recordado dentro de los topes de ahora
        pantalla = clavePantalla(e.pantalla());
        if (!enCurso) aplicar();
    });
    return { aplicar };
}

// ── la terminal del centro ──

/** la terminal nunca más angosta que esto arrastrándola (Claude Code se lee mal con menos); si el centro no da, lo que
 *  quepa */
export const COLUMNAS_MINIMAS = 80;

/** Cuántas columnas caben en una caja de `caja` px, con columnas de `celda` px y la barra de desplazamiento de `barra`:
 *  lo mismo que mide la terminal (deja una columna de aire a cada lado). */
export const caben = (caja: number, celda: number, barra: number): number => Math.floor((caja - barra - 2 * celda) / celda);

/** Los topes de la terminal, en columnas: de `COLUMNAS_MINIMAS` (o lo que quepa, si es menos) a lo que cabe. */
export function topesTerminal(caja: number, celda: number, barra: number): Topes {
    const max = Math.max(20, caben(caja, celda, barra));
    return { min: Math.min(COLUMNAS_MINIMAS, max), max };
}

/** Las columnas de la terminal que se eligieron arrastrando, en esta pantalla (0: todo); sin nada, `undefined` (las de
 *  ⚙ terminal). */
export function columnasRecordadas(almacen: Pick<Storage, 'getItem'> | null, pantalla: { width: number; height: number }): number | undefined {
    const v = leer(almacen)[clavePantalla(pantalla)]?.terminal;
    return typeof v === 'number' && Number.isFinite(v) && v >= 0 ? Math.round(v) : undefined;
}

/** Olvidar lo arrastrado de la terminal en todas las pantallas: lo pide ⚙ terminal al cambiar su ancho. */
export function olvidarTerminal(almacen: Pick<Storage, 'getItem' | 'setItem'> | null): void {
    for (const p of Object.keys(leer(almacen))) recordar(almacen, p, 'terminal', undefined);
}

export type Posicion = 'izquierda' | 'centro' | 'derecha';

export interface EntornoTerminal {
    body: HTMLElement;
    /** la caja de la terminal: su ancho es el del centro */
    caja: HTMLElement;
    /** el marco de la terminal (.t), del ancho de sus columnas: la franja va en él, sobre su borde */
    marco: HTMLElement;
    ventana: Pick<Window, 'dispatchEvent'>;
    pantalla: () => { width: number; height: number };
    almacen: (Pick<Storage, 'getItem' | 'setItem'>) | null;
    crear: (tag: string) => HTMLElement;
    evento?: () => Event;
    /** el ancho de una columna, en px (null si todavía no se sabe) */
    celda: () => number | null;
    /** la barra de desplazamiento de la terminal, en px: va dentro del marco */
    barra: number;
    posicion: () => Posicion;
}

/** La franja del borde de la terminal. Devuelve las columnas elegidas arrastrando en esta pantalla (las lee la terminal
 *  al medirse) y cómo ponerla en el borde que toca cuando cambia su posición. */
export function montarTerminal(t: EntornoTerminal): { columnas(): number | undefined; colocar(): void } {
    const f = t.crear('div');
    f.className = 'tirador';
    f.id = 'tirador-terminal';
    f.title = 'arrastrar: el ancho de la terminal · doble clic: el de ⚙ terminal';
    const lado = () => (t.posicion() === 'derecha' ? 'izq' : 'der');
    const colocar = () => { f.dataset.borde = lado(); };
    const avisar = () => t.ventana.dispatchEvent(t.evento ? t.evento() : new Event(EVENTO));
    let inicial = 0, celda = 0, factor = 1, cols = 0, tope: Topes = { min: 0, max: 0 };
    agarre(f, 'terminal', t.body, {
        puede: () => !t.body.classList.contains('angosto') && !!t.celda() && t.caja.clientWidth > 0,
        empezar: () => {
            celda = t.celda() ?? 8;
            inicial = parseFloat(t.marco.style.width) || t.marco.getBoundingClientRect().width;
            cols = Math.round((inicial - t.barra) / celda);
            tope = topesTerminal(t.caja.clientWidth, celda, t.barra);
            // centrada crece hacia los dos lados: el borde sigue al puntero si el ancho cambia el doble
            factor = { izquierda: 1, centro: 2, derecha: -1 }[t.posicion()] ?? 2;
            colocar();
            t.marco.dataset.estira = lado();
        },
        mover: dx => {
            cols = acotar((inicial - t.barra + factor * dx) / celda, tope);
            t.marco.style.width = `${Math.ceil(cols * celda + t.barra)}px`;
        },
        soltar: movida => {
            delete t.marco.dataset.estira;
            if (!movida) return;
            recordar(t.almacen, clavePantalla(t.pantalla()), 'terminal', cols >= tope.max ? 0 : cols);
            avisar();
        },
        fabrica: () => { recordar(t.almacen, clavePantalla(t.pantalla()), 'terminal', undefined); avisar(); },
    });
    t.marco.appendChild(f);
    colocar();
    return { columnas: () => columnasRecordadas(t.almacen, t.pantalla()), colocar };
}

/** Lo de la página que usan las franjas: el almacén (si el navegador lo da) y la pantalla. */
export function dePagina(): Pick<Entorno, 'body' | 'ventana' | 'almacen' | 'pantalla' | 'crear'> {
    let almacen: Storage | null = null;
    try { almacen = window.localStorage; } catch { almacen = null; }
    return { body: document.body, ventana: window, almacen, crear: tag => document.createElement(tag),
        pantalla: () => ({ width: window.screen?.width ?? window.innerWidth, height: window.screen?.height ?? window.innerHeight }) };
}

/** En la página: con el documento de verdad. */
export function montarEnPagina(): void {
    const id = (x: string) => document.getElementById(x);
    const barra = id('barra'), lado = id('lado'), marcos = id('marcos');
    if (!barra || !lado || !marcos) return;
    montar({ ...dePagina(), barra, lado, marcos });
}
