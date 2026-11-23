// Lo que el lienzo de un módulo pide (`window.lienzo.pedir`) y la página atiende sola, sin llegar al servidor ni pedir
// permiso: lo que solo muestra o lleva a algo, y no cambia nada. `menu` abre el menú de una entidad junto al punto donde
// se hizo clic; `abrir` la abre en la página, como un clic en un enlace a esa dirección (la ficha de una tarea, el
// hilo, la vista de un objeto); `instruccion` abre la ventana de la instrucción con un contexto (un chat): nada sale
// hasta que la persona la manda ahí, y puede cambiar a quién o qué. Lo demás (`fecha`, `idea`, `consulta`) va al
// servidor (telar.servicios.lienzos), que pide permiso para lo que cambia tus documentos. Está aparte, sin la página,
// para probarlo solo (pruebas/lienzo.mjs).

/** Un punto de la página: donde se hizo clic, ya en sus coordenadas. */
export interface Punto { x: number; y: number }

/** Lo que pide un lienzo con `instruccion`, ya leído: de qué se habla (un texto, una entidad o los dos), a quién
 *  (`agente:<nombre>`, `hilo:<nombre>` o un nombre; vacío: el de la configuración) y lo que viene escrito. */
export interface PedidoDeLienzo {
    contexto: { texto: string; titulo: string; direccion: string };
    destino: string;
    texto: string;
}

/** Lo que la página sabe hacer con una dirección: lo da quien la tiene (panel.ts). `instruccion` termina cuando la
 *  ventana se cierra, con lo que se le contesta al lienzo: a quién llegó, o null si se canceló. */
export interface Hacer {
    menu(direccion: string, donde?: Punto): Promise<unknown> | unknown;
    abrir(direccion: string): Promise<unknown> | unknown;
    instruccion(pedido: PedidoDeLienzo): Promise<unknown> | unknown;
}

/** Lo que se le contesta al lienzo: la promesa de `pedir` se cumple con `datos`, o falla con `error`. */
export interface Respuesta { ok: boolean; datos?: unknown; error?: string }

/** Lo que el lienzo pide y la página atiende sola: no pide permiso ni llega al servidor. */
export const LOCALES = ['menu', 'abrir', 'instruccion'] as const;

/** La forma de una dirección (`tipo:id[@máquina]`), como la lee telar.objetos: el tipo en minúsculas y algo de id. */
const DIRECCION = /^[a-z][a-z0-9-]*:\S/;

/** La dirección que trae lo que pidió el lienzo (`{direccion}`), sin espacios en los bordes; '' si no trae. */
export function direccionDe(datos: unknown): string {
    const d = (datos as { direccion?: unknown } | null | undefined)?.direccion;
    return typeof d === 'string' ? d.trim() : '';
}

/** A quién va un destino, como se nombra en la ventana: `agente:<carpeta o nombre>` es el nombre de ese agente (su
 *  sección se llama `agente:<carpeta>`), `hilo:<nombre>` y un nombre suelto, ese nombre. */
export function nombreDeDestino(destino: string, agentes: { clave: string; nombre: string }[]): string {
    const d = destino.trim();
    const [tipo, ...resto] = d.split(':');
    const nombre = resto.join(':').trim();
    if (tipo === 'agente' && nombre) return agentes.find(a => a.clave === `agente:${nombre}` || a.nombre === nombre)?.nombre ?? nombre;
    if (tipo === 'hilo' && nombre) return nombre;
    return d;
}

/** Lo que trae `instruccion`, leído; o por qué no sirve. El contexto es un texto, o `{texto, titulo, direccion}` (una
 *  entidad, si la hay, con la forma de una dirección); hace falta texto o dirección. */
export function pedidoDeInstruccion(datos: unknown): PedidoDeLienzo | string {
    if (!datos || typeof datos !== 'object') return 'falta el contexto: {contexto, destino?, texto?}';
    const d = datos as { contexto?: unknown; destino?: unknown; texto?: unknown };
    const c = typeof d.contexto === 'string' ? { texto: d.contexto } : d.contexto;
    if (!c || typeof c !== 'object') return 'falta el contexto: un texto, o {texto, titulo?, direccion?}';
    const { texto = '', titulo = '', direccion = '' } = c as { texto?: unknown; titulo?: unknown; direccion?: unknown };
    if (typeof texto !== 'string' || typeof titulo !== 'string' || typeof direccion !== 'string')
        return 'el contexto es {texto, titulo?, direccion?}, todos textos';
    if (!texto.trim() && !direccion.trim()) return 'el contexto viene vacío: hace falta su texto o una dirección';
    if (direccion.trim() && !DIRECCION.test(direccion.trim()))
        return `«${direccion.trim()}» no es una dirección: se escribe tipo:id, como tarea:T84`;
    if (d.destino !== undefined && typeof d.destino !== 'string') return 'el destino es un texto: agente:<nombre> o hilo:<nombre>';
    const destino = (d.destino ?? '').trim();
    if (/^[a-z][a-z0-9-]*:/.test(destino) && !/^(agente|hilo):\S/.test(destino))
        return `«${destino}» no es un destino: agente:<nombre> o hilo:<nombre>`;
    if (d.texto !== undefined && typeof d.texto !== 'string') return 'lo escrito (texto) es un texto';
    return { contexto: { texto, titulo: titulo.trim(), direccion: direccion.trim() }, destino, texto: d.texto ?? '' };
}

/** Atiende `orden` si es de las que la página atiende sola, y dice qué contestarle al lienzo; undefined si no es de esas
 *  (va al servidor). La respuesta de `menu` y `abrir` sale antes de hacerlo: el menú espera a que se elija, y el lienzo no
 *  tiene que esperar. La de `instruccion`, al cerrarse la ventana: el lienzo sabe si se mandó y a quién. */
export function atender(orden: string, datos: unknown, donde: Punto | undefined, hacer: Hacer,
    responder: (r: Respuesta) => void): Promise<void> | undefined {
    if (!(LOCALES as readonly string[]).includes(orden)) return undefined;
    if (orden === 'instruccion') {
        const pedido = pedidoDeInstruccion(datos);
        if (typeof pedido === 'string') { responder({ ok: false, error: pedido }); return Promise.resolve(); }
        return Promise.resolve().then(() => hacer.instruccion(pedido)).then(
            r => responder({ ok: true, datos: r ?? null }),
            (e: unknown) => responder({ ok: false, error: e instanceof Error ? e.message : String(e) }));
    }
    const direccion = direccionDe(datos);
    if (orden === 'menu') {
        responder(direccion ? { ok: true } : { ok: false, error: 'falta la dirección' });
        return direccion ? Promise.resolve(hacer.menu(direccion, donde)).then(() => undefined) : Promise.resolve();
    }
    if (!direccion) { responder({ ok: false, error: 'falta la dirección' }); return Promise.resolve(); }
    if (!DIRECCION.test(direccion)) {
        responder({ ok: false, error: `«${direccion}» no es una dirección: se escribe tipo:id, como tarea:T84` });
        return Promise.resolve();
    }
    responder({ ok: true });
    return Promise.resolve(hacer.abrir(direccion)).then(() => undefined);
}
