// El estilo de los glifos que rige: el que dice el modo puesto (`estilo`, web/modos.ts), con los valores de
// `[glifos.<estilo>]` (`GET /glifos`, telar.glifos). Mientras se afina en ⚙ glifos, un borrador: se ve en la página al
// tiro y se guarda (o se descarta) desde ahí. Hasta que contesta la API, los de fábrica.

import * as cli from '../../cli';
import * as modos from '../modos';
import { CAMPO, type ParamCampo } from './campo';
import { GESTOS, type Gesto } from './gestos';
import { ESTADOS, HILO, type ParamEstados, type ParamHilo } from './hilo';
import type { Forma } from './piezas';

export type Valores = Record<string, string | number>;

/** Los de fábrica, por si la API todavía no contesta: los mismos de telar.glifos.BASE. */
const FABRICA: Valores = {
    ...Object.fromEntries(Object.entries(CAMPO).filter(([, v]) => typeof v !== 'object')) as Valores,
    ...Object.fromEntries(Object.entries(GESTOS).map(([k, v]) => [`gesto_${k}`, v])),
    hilo_paleta: HILO.paleta, hilo_capas: HILO.capas, hilo_variedad: HILO.variedad, hilo_mezcla: HILO.mezcla,
    hilo_desregistro: HILO.desregistro, hilo_grano: HILO.grano, hilo_tam: 15, sello_tam: 48,
    trabajando: ESTADOS.trabajando, espera: ESTADOS.espera, tenue: ESTADOS.tenue, ritmo: ESTADOS.ritmo,
};

let catalogo: cli.ParamGlifo[] = [];
let estilos: Record<string, Valores> = { base: FABRICA };
let borrador: { estilo: string; valores: Valores } | null = null;
let version = 0;
const oyentes = new Set<() => void>();

export const lista = (): string[] => Object.keys(estilos);
export const parametros = (): cli.ParamGlifo[] => catalogo;
/** Cambia con cada cambio de valores: para saber si hay que repintar. */
export const firma = (): number => version;
/** El estilo del modo puesto. */
export const puesto = (): string => { const e = String(modos.valor('estilo') ?? 'base'); return estilos[e] ? e : 'base'; };
/** Los valores de un estilo (el del modo puesto, si no se dice), con el borrador encima si es el que se afina. */
export function valores(estilo = puesto()): Valores {
    const v = { ...FABRICA, ...(estilos[estilo] ?? estilos.base) };
    return borrador?.estilo === estilo ? { ...v, ...borrador.valores } : v;
}
export const enBorrador = (): string => (borrador && Object.keys(borrador.valores).length ? borrador.estilo : '');

export function alCambiar(f: () => void): () => void { oyentes.add(f); return () => oyentes.delete(f); }
const avisar = () => { version++; for (const f of oyentes) f(); };

let leidos: Promise<void> | null = null;
/** Los estilos de la API (una vez; `de nuevo`, otra). */
export function leer(deNuevo = false): Promise<void> {
    if (!leidos || deNuevo) {
        leidos = cli.glifos().then(r => {
            if (!r.datos) return;
            catalogo = r.datos.catalogo;
            estilos = r.datos.estilos;
            avisar();
        }).catch(() => undefined);
    }
    return leidos;
}

/** Afinar: un valor de un estilo, que se ve al tiro y no se guarda hasta `guardar`. */
export function probar(estilo: string, clave: string, v: string | number): void {
    if (!borrador || borrador.estilo !== estilo) borrador = { estilo, valores: {} };
    borrador.valores[clave] = v;
    avisar();
}
/** Varios de una vez (volver a los de fábrica, en el borrador). */
export function probarTodos(estilo: string, vs: Valores): void { borrador = { estilo, valores: { ...vs } }; avisar(); }
export function descartar(): void { borrador = null; avisar(); }

/** Escribe el estilo (con su borrador) en la configuración. "" si salió bien; si no, por qué. */
export async function guardar(estilo: string, como = estilo): Promise<string> {
    const r = await cli.guardarEstilo(como, valores(estilo));
    if (!r.datos) return r.error ?? 'no se pudo';
    estilos = r.datos.estilos;
    borrador = null;
    avisar();
    return '';
}
export async function borrar(estilo: string): Promise<string> {
    const r = await cli.borrarEstilo(estilo);
    if (!r.datos) return r.error ?? 'no se pudo';
    estilos = r.datos.estilos;
    if (borrador?.estilo === estilo) borrador = null;
    avisar();
    return '';
}

const num = (v: string | number | undefined, d: number) => (v === undefined || v === '' || Number.isNaN(Number(v)) ? d : Number(v));
const txt = <T extends string>(v: string | number | undefined, d: T): T => (v === undefined ? d : String(v) as T);

/** Los parámetros del campo de un estilo. */
export function campo(v = valores()): ParamCampo {
    const c = CAMPO;
    const gestos = Object.fromEntries(Object.keys(GESTOS).map(k => [k, txt(v[`gesto_${k}`], GESTOS[k as Forma])])) as Record<Forma, Gesto>;
    return {
        paleta: txt(v.paleta, c.paleta), tintas: num(v.tintas, c.tintas), mezcla: txt(v.mezcla, c.mezcla), fondo: txt(v.fondo, c.fondo),
        intensidad: num(v.intensidad, c.intensidad), desregistro: num(v.desregistro, c.desregistro), grano: num(v.grano, c.grano),
        papel: num(v.papel, c.papel), celda: num(v.celda, c.celda), niveles: num(v.niveles, c.niveles), capas: num(v.capas, c.capas),
        variedad: num(v.variedad, c.variedad), huecos: num(v.huecos, c.huecos), onda: num(v.onda, c.onda), ruido: num(v.ruido, c.ruido),
        ciclo: num(v.ciclo, c.ciclo), semilla: num(v.semilla, c.semilla), transicion: txt(v.transicion, c.transicion), corte: num(v.corte, c.corte),
        actividad: num(v.actividad, c.actividad), periodo: num(v.periodo, c.periodo), duracion: num(v.duracion, c.duracion),
        saltos: num(v.saltos, c.saltos), rueda: num(v.rueda, c.rueda), gestos,
    };
}
/** Los del glifo de cada hilo. */
export function hilo(v = valores()): ParamHilo {
    return { paleta: txt(v.hilo_paleta, HILO.paleta), capas: num(v.hilo_capas, HILO.capas), variedad: num(v.hilo_variedad, HILO.variedad),
        mezcla: txt(v.hilo_mezcla, HILO.mezcla), desregistro: num(v.hilo_desregistro, HILO.desregistro), grano: num(v.hilo_grano, HILO.grano) };
}
/** Los de sus estados. */
export function estados(v = valores()): ParamEstados {
    return { trabajando: txt(v.trabajando, ESTADOS.trabajando), espera: txt(v.espera, ESTADOS.espera), tenue: num(v.tenue, ESTADOS.tenue),
        ritmo: num(v.ritmo, ESTADOS.ritmo) };
}
/** Tamaños: el glifo en la barra y el sello en la ficha. */
export const tam = (v = valores()) => ({ barra: num(v.hilo_tam, 15), sello: num(v.sello_tam, 48) });
