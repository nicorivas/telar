// El estado efectivo de un proyecto y lo que dice su plazo, como los muestra la fila de la pestaña de proyectos
// (proyectos.ts, `filaProyecto`): en qué sección va (en ejecución, por partir, en cierre, pausado, terminado, cerrado),
// de dónde sale eso, el círculo de su fase y la fecha que se ve («→ 22-dic», «venció 8-nov»). Puro, sin la página: lo
// usa la pestaña de proyectos, y lo prueba npm run prueba:componentes.

import type * as cli from '../../cli';
import type { Pieza } from '../../componentes/item';
import * as S from '../../componentes/senales';
import { normalizar } from '../../estilo';

const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
/** «2026-10-22» → «22-oct». */
export const diaCorto = (iso: string): string => {
    const [, m, d] = iso.split('-').map(Number);
    return d && m ? `${d}-${MESES[m - 1]}` : iso;
};
/** Hoy, en AAAA-MM-DD de esta máquina. */
export const hoyIso = (): string => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };

/** Las secciones de la lista, en su orden: una por estado efectivo. Las dos primeras piden atención directa; en
 *  cierre, el proyecto todavía corre pero ya se está entregando y cerrando, y va debajo. */
export type Seccion = 'curso' | 'partir' | 'cierre' | 'pausado' | 'terminado' | 'cerrado';
export const SECCIONES: [Seccion, string][] = [['curso', 'en ejecución'], ['partir', 'por partir'], ['cierre', 'en cierre'],
    ['pausado', 'pausados'], ['terminado', 'terminados'], ['cerrado', 'cerrados']];
/** Cada estado efectivo en singular: la columna estado y el detalle. */
export const NOMBRE_SECCION: Record<Seccion, string> = { curso: 'en ejecución', partir: 'por partir', cierre: 'en cierre', pausado: 'pausado', terminado: 'terminado', cerrado: 'cerrado' };

/** Si la fase de un plazo es la de cierre («cierre», «en cierre», «cerrando»). */
export const enCierre = (etapa: string | undefined): boolean => /^(en )?(cierre|cerrando)/.test(normalizar(etapa ?? ''));

/** Una unidad se da por cerrada por su arquetipo («proyecto cerrado»): se esconde salvo que se pidan. */
export const esCerrado = (p: cli.JsonProyecto): boolean => /cerrad/i.test(p.arquetipo);

/** El estado efectivo que dice el documento (su fila Estado, la que escribe el gestor de proyectos o una persona),
 *  como sección; "" si no dice uno conocido. */
export function efectivo(estado: string): Seccion | '' {
    const e = normalizar(estado);
    if (/^por partir/.test(e)) return 'partir';
    if (/^(activo|en curso|en ejecucion)/.test(e)) return 'curso';
    if (/^(en cierre|cerrando)/.test(e)) return 'cierre';
    if (/^(pausad|en pausa)/.test(e)) return 'pausado';
    if (/^(terminad|entregad)/.test(e)) return 'terminado';
    if (/^(cerrad|perdid|finalizad)/.test(e)) return 'cerrado';
    return '';
}

/** En qué sección va un proyecto, por su estado efectivo. Una corrección a mano (la fila Estado dice «a mano», con
 *  desde cuándo y por qué) manda. Si no, su plazo, el de su gestor de proyectos: terminado (hecho o cancelado), cerrado;
 *  uno que parte después de hoy, por partir; uno en su fase de cierre, en cierre; los demás, en ejecución, diga lo que
 *  diga su fase (la de un gestor se atrasa: un proyecto que ya se ejecuta puede seguir en preparación). No depende de
 *  que la copia del documento esté al día. Sin plazo, lo que dice la fila. */
export function seccionDe(p: cli.JsonProyecto, hoy = hoyIso()): Seccion {
    if (esCerrado(p)) return 'cerrado';
    const ef = efectivo(p.estado ?? '');
    if (ef && /a mano/.test(p.estado_completo ?? '')) return ef;
    const pl = p.plazo;
    if (pl) return pl.estado === 'hecho' || pl.estado === 'cancelado' ? 'cerrado' : pl.inicio > hoy ? 'partir' : enCierre(pl.etapa) ? 'cierre' : 'curso';
    return ef || 'curso';
}

/** De dónde sale el estado efectivo de un proyecto, para decirlo al pasar sobre él; y si nadie lo confirma (sin plazo
 *  ni un estado que se entienda: se da por en ejecución). */
export function porQue(p: cli.JsonProyecto, sec: Seccion, hoy: string): { ayuda: string; supuesto: boolean } {
    if (esCerrado(p)) return { ayuda: `cerrado: su tipo es «${p.arquetipo}»`, supuesto: false };
    const ef = efectivo(p.estado ?? '');
    if (ef && /a mano/.test(p.estado_completo ?? '')) return { ayuda: `a mano: ${/a mano[^·]*/.exec(p.estado_completo ?? '')?.[0]?.trim() ?? ''}`, supuesto: false };
    const pl = p.plazo;
    if (pl) {
        const como = pl.estado === 'hecho' || pl.estado === 'cancelado' ? `${pl.estado} en ${pl.fuente || 'su fuente'}`
            : pl.inicio > hoy ? `parte el ${diaCorto(pl.inicio)}`
                : sec === 'cierre' ? `partió el ${diaCorto(pl.inicio)} y está en su fase de cierre` : `partió el ${diaCorto(pl.inicio)}`;
        return { ayuda: `por su plazo (${pl.fuente || 'su fuente'}): ${como}${pl.etapa && sec !== 'cierre' ? `; su fase dice ${pl.etapa}` : ''}`, supuesto: false };
    }
    if (ef) return { ayuda: `sin plazo; su documento dice: ${p.estado_completo || p.estado}`, supuesto: false };
    return { ayuda: `sin plazo ni un estado que se entienda${p.estado_completo ? ` (su documento dice: ${p.estado_completo})` : ''}: se da por ${NOMBRE_SECCION[sec]}`, supuesto: true };
}

/** «a mano desde 2026-09-09» de la fila Estado: desde cuándo vale una corrección a mano; "" si no hay. */
export const aManoDesde = (p: cli.JsonProyecto): string => /a mano desde (\d{4}-\d{2}-\d{2})/.exec(p.estado_completo ?? '')?.[1] ?? '';

/** Lo que se usa de un plazo: de cuándo a cuándo (un plazo sin fin conocido llega con el fin igual al inicio), su fase,
 *  cuánto avanzó y lo que no cuadra. */
export interface PlazoVisto { inicio: string; fin: string; etapa?: string; avance?: number | null; aviso?: string }

/** El círculo de su fase, en la ranura de la fila: pausado, un aro tenue; terminado, lleno; cerrado, lleno y tenue; los
 *  demás, la fase de su plazo de a cuartos (con lo que no cuadra, en el color de cuidado). Sin plazo, ninguno. `estado`,
 *  lo que dice su documento: va al pasar sobre un pausado o un terminado. */
export function senalFase(sec: Seccion, pl: PlazoVisto | null | undefined, estado?: string): Pieza | null {
    const aviso = pl?.aviso ?? '';
    const ayudaFase = pl ? [pl.etapa, aviso].filter(Boolean).join(' · ') : '';
    return sec === 'pausado' ? S.pausado(estado) : sec === 'terminado' ? S.terminado(estado)
        : sec === 'cerrado' ? S.fase(1, '', ayudaFase || undefined)
            : typeof pl?.avance === 'number' ? S.fase(pl.avance, aviso, ayudaFase) : null;
}

/** La fecha que se ve en la columna plazo: desde cuándo está pausado o terminado (si es a mano), cuándo parte, cuándo
 *  cerró, o hasta cuándo va («→ 22-dic»; «venció 8-nov», en el color de cuidado, si ya pasó y sigue). `iso`, la que
 *  ordena; `ayuda`, de cuándo a cuándo y lo que no cuadra. */
export function cuandoDe(sec: Seccion, pl: PlazoVisto | null | undefined, desde: string, hoy: string): { texto: string; iso: string; vencido: boolean; ayuda: string } {
    const ayuda = pl ? `${diaCorto(pl.inicio)} → ${diaCorto(pl.fin)}${pl.aviso ? `\n${pl.aviso}` : ''}` : 'sin plazo';
    if ((sec === 'pausado' || sec === 'terminado') && desde) return { texto: `desde ${diaCorto(desde)}`, iso: desde, vencido: false, ayuda };
    if (!pl) return { texto: '', iso: '', vencido: false, ayuda };
    if (sec === 'partir') return { texto: `parte ${diaCorto(pl.inicio)}`, iso: pl.inicio, vencido: false, ayuda };
    if (sec === 'cerrado') return { texto: `cerró ${diaCorto(pl.fin)}`, iso: pl.fin, vencido: false, ayuda };
    // un plazo sin fin conocido llega con el fin igual al inicio: no se da por vencido
    const vencido = pl.fin < hoy && pl.fin > pl.inicio;
    return { texto: vencido ? `venció ${diaCorto(pl.fin)}` : pl.fin > pl.inicio ? `→ ${diaCorto(pl.fin)}` : `desde ${diaCorto(pl.inicio)}`,
        iso: pl.fin > pl.inicio ? pl.fin : pl.inicio, vencido, ayuda };
}

/** El orden dentro de cada sección: en curso, lo que termina antes primero (lo vencido arriba) y los sin plazo al
 *  final; por partir, lo que parte antes; cerrados, lo último que cerró. Empatados, por nombre. */
export function ordenarSeccion<T>(sec: Seccion, xs: readonly T[], plazo: (x: T) => { inicio: string; fin: string } | null | undefined,
    nombre: (x: T) => string): T[] {
    const clave = (x: T) => { const pl = plazo(x); return !pl ? '9' : sec === 'partir' ? pl.inicio : pl.fin; };
    return [...xs].sort((a, b) => {
        const x = clave(a), y = clave(b);
        if (x !== y) return sec === 'cerrado' ? (x === '9' ? 1 : y === '9' ? -1 : y.localeCompare(x)) : x.localeCompare(y);
        return nombre(a).localeCompare(nombre(b));
    });
}
