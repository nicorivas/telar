// Las entidades de telar y lo que se puede hacer con cada una (docs/propuestas/acciones.md). Toda entidad tiene una
// dirección (`hilo:Faro`, `proyecto:operacion/faro`, `tarea:T84`); su menú se abre donde está (clic derecho, o su ⋯)
// con `menuDe(direccion, donde)`, y se arma en capas: lo que la página sabe hacer con ese tipo (cada pantalla registra
// lo suyo con `registrar`), o, si la página no sabe nada del tipo (el de un módulo), las acciones que da el servidor
// (`telar objeto`); y abajo, lo de toda entidad (copiar su dirección).

import { C, I } from './iconos';
import * as cli from '../cli';
import type { Opcion } from './ui';
import * as ui from './ui';

/** Una acción del menú de una entidad: lo que se ve (`label`, `description`, o un `separador`) y lo que hace. */
export interface AccionEntidad extends Opcion { hacer?: () => Promise<unknown> | unknown }

/** Lo que la página sabe hacer con una entidad de un tipo: su título y sus acciones. undefined si no la encuentra. */
export type Proveedor = (id: string) => Promise<{ titulo: string; acciones: AccionEntidad[] } | undefined>;

const tipos = new Map<string, Proveedor>();

/** Lo que una pantalla sabe hacer con las entidades de un tipo. Registrar otra vez el mismo tipo lo reemplaza. */
export function registrar(tipo: string, proveedor: Proveedor): void { tipos.set(tipo, proveedor); }

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
                    const v = await ui.campo({ titulo: `${o.titulo} · ${a.nombre}`, ayuda: `${nombre}: ${ayuda}` });
                    if (v === undefined) return;
                    params[nombre] = v;
                }
                const hecho = await cli.accionObjeto(direccion, a.nombre, params, o.version ?? '');
                if (!hecho.datos) void ui.falla(`telar: ${hecho.error ?? `no pude: ${a.nombre}`}`);
                else ui.estado(`${o.titulo}: ${a.nombre}`, 4000);
            },
        })),
    };
}

/** El menú de una entidad, junto a `donde` (sin `donde`, el de siempre, en el centro): sus acciones y, abajo, lo de
 *  toda entidad. Corre la elegida. */
export async function menuDe(direccion: string, donde?: { x: number; y: number }): Promise<void> {
    const [tipo, id] = partir(direccion);
    const propias = await (tipos.get(tipo)?.(id) ?? delServidor(direccion));
    const acciones: AccionEntidad[] = [
        // «Acción…»: pedirle algo a un hilo o a un agente sobre ella, con su contexto (web/actuar.ts)
        { label: 'Acción…', icono: I.accion, color: C.agente, description: 'pedirle algo a un hilo o un agente sobre esto, con su contexto',
          hacer: async () => { const { abrir } = await import('./actuar'); await abrir(direccion); } },
        ...(propias?.acciones ?? []),
        { label: 'esta entidad', separador: true },
        { label: 'copiar su dirección', icono: I.direccion, color: C.otro, description: direccion, hacer: async () => { await ui.copiar(direccion); ui.estado(`copiado ${direccion}`, 3000); } },
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
