// Las entidades de telar y lo que se puede hacer con cada una (docs/propuestas/acciones.md). Toda entidad tiene una
// dirección (`hilo:Faro`, `proyecto:operacion/faro`, `tarea:T84`); su menú se abre donde está (clic derecho, o su ⋯)
// con `menuDe(direccion, donde)`, y se arma en capas: lo que la página sabe hacer con ese tipo (cada pantalla registra
// lo suyo con `registrar`), o, si la página no sabe nada del tipo (el de un módulo), las acciones que da el servidor
// (`telar objeto`); un tipo que la página conoce a medias (el agente) pide las dos: las suyas y, después, las del
// servidor. Y abajo, lo de toda entidad (copiar su dirección).

import { C, I } from './iconos';
import * as cli from '../cli';
import type { Opcion } from './ui';
import * as ui from './ui';

/** Una acción del menú de una entidad: lo que se ve (`label`, `description`, o un `separador`) y lo que hace. */
export interface AccionEntidad extends Opcion { hacer?: () => Promise<unknown> | unknown }

/** Lo que la página sabe hacer con una entidad de un tipo: su título y sus acciones. undefined si no la encuentra.
 *  `alFinal` va después de lo que da el servidor (lo que quita, en rojo, cierra el menú). */
export type Proveedor = (id: string) => Promise<{ titulo: string; acciones: AccionEntidad[]; alFinal?: AccionEntidad[] } | undefined>;

const tipos = new Map<string, Proveedor>();
/** los tipos cuyo menú suma, a lo de la página, lo que da el servidor */
const conServidor = new Set<string>();

/** Lo que una pantalla sabe hacer con las entidades de un tipo. Registrar otra vez el mismo tipo lo reemplaza. Con
 *  `conServidor`, su menú lleva además, después, las acciones que el servidor da para ella (`telar objeto`). */
export function registrar(tipo: string, proveedor: Proveedor, o: { conServidor?: boolean } = {}): void {
    tipos.set(tipo, proveedor);
    if (o.conServidor) conServidor.add(tipo); else conServidor.delete(tipo);
}

/** El tipo y el id de una dirección (`proyecto:operacion/faro` → ["proyecto", "operacion/faro"]). */
export function partir(direccion: string): [string, string] {
    const i = direccion.indexOf(':');
    return i < 0 ? ['', direccion] : [direccion.slice(0, i), direccion.slice(i + 1)];
}

/** Las acciones que el servidor da para una entidad de un tipo que la página no conoce (`telar objeto`): cada una
 *  pide sus parámetros y corre en el servidor. */
async function delServidor(direccion: string): Promise<{ titulo: string; acciones: AccionEntidad[] } | undefined> {
    const r = await cli.objeto(direccion);
    if (!r.datos) return undefined;
    const o = r.datos;
    return {
        titulo: o.titulo || direccion,
        acciones: (o.acciones ?? []).map(a => ({
            label: a.nombre, description: a.descripcion ?? '', icono: I.abrir, color: C.otro,
            hacer: async () => {
                const params: Record<string, string> = {};
                for (const [nombre, ayuda] of Object.entries(a.params ?? {})) {
                    // con opciones (los productos, los estados), se elige de una lista; si no, se escribe
                    const opciones = a.opciones?.[nombre];
                    if (opciones?.length) {
                        const elegida = await ui.elegir(opciones.map(x => ({ label: x.nombre, description: x.valor === x.nombre ? '' : x.valor, valor: x.valor })),
                            { titulo: `${o.titulo} · ${a.nombre}: ${nombre}` });
                        if (!elegida) return;
                        params[nombre] = elegida.valor;
                        continue;
                    }
                    const v = await ui.campo({ titulo: `${o.titulo} · ${a.nombre}`, ayuda: `${nombre}: ${ayuda}`, valor: ayuda });
                    if (v === undefined) return;
                    params[nombre] = v;
                }
                const hecho = await cli.accionObjeto(direccion, a.nombre, params, o.version ?? '');
                if (!hecho.datos) void ui.falla(`telar: ${hecho.error ?? `no pude: ${a.nombre}`}`);
                else ui.estado(String((hecho.datos as { resultado?: { texto?: string } }).resultado?.texto ?? `${o.titulo}: ${a.nombre}`), 6000);
            },
        })),
    };
}

/** El menú de una entidad, junto a `donde` (sin `donde`, el de siempre, en el centro): sus acciones y, abajo, lo de
 *  toda entidad. Corre la elegida. */
export async function menuDe(direccion: string, donde?: { x: number; y: number }): Promise<void> {
    const [tipo, id] = partir(direccion);
    const deLaPagina = tipos.get(tipo);
    // las dos a la vez; si el servidor no contesta, queda lo de la página
    const [suyas, servidor] = await Promise.all([deLaPagina?.(id),
        !deLaPagina || conServidor.has(tipo) ? delServidor(direccion).catch(() => undefined) : undefined]);
    const propias = suyas || servidor ? {
        titulo: suyas?.titulo ?? servidor?.titulo ?? direccion,
        acciones: [...suyas?.acciones ?? [], ...servidor?.acciones ?? [], ...suyas?.alFinal ?? []],
    } : undefined;
    const acciones: AccionEntidad[] = [
        // «instrucción…»: mandarle algo a un hilo o a un agente sobre ella, con su contexto (web/instruccion.ts)
        { label: 'instrucción…', icono: I.instruccion, color: C.agente, description: 'mandarle a un hilo o a un agente algo sobre esto, con su contexto',
          hacer: async () => { const { abrir } = await import('./instruccion'); await abrir({ direccion, titulo: propias?.titulo }); } },
        ...(propias?.acciones ?? []),
        { label: 'esta entidad', separador: true },
        { label: 'copiar su dirección', icono: I.direccion, color: C.otro, description: direccion, hacer: async () => { await ui.copiar(direccion, `copiado ${direccion}`); } },
    ];
    const elegida = await ui.menu(acciones, donde, propias?.titulo ?? direccion);
    await elegida?.hacer?.();
}

/** Dónde abrir el menú de lo que se apretó: junto al puntero si fue un clic derecho, o bajo el ⋯ si fue un clic. */
export function dondeDe(e: MouseEvent, elemento?: Element | null): { x: number; y: number } {
    if (e.type !== 'contextmenu' && elemento) {
        const r = elemento.getBoundingClientRect();
        return { x: r.left, y: r.bottom + 2 };
    }
    return { x: e.clientX, y: e.clientY };
}
