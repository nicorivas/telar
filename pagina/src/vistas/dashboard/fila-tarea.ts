// La fila de una tarea, la misma en todas las listas que muestran tareas: la pestaña «tareas», las de un correo, el
// detalle de un proyecto, «ahora» y la pestaña de un proveedor. Es un ítem (componentes/item.ts), como un hilo en la
// barra, y dice lo suyo con las mismas piezas (componentes/senales.ts, componentes/gramatica.ts):
//
//   ┌ inicio ──────────────────────────────┬ texto ─────────────────────────────┬ fin ──────────────────────┐
//   │ prioridad · estado · código · proyecto│ [lo que dejó] [→ otra persona] texto│ [estrella] fecha [│ … ⋯] │
//   └───────────────────────────────────────┴────────────────────────────────────┴───────────────────────────┘
//
// · la prioridad, un círculo chico (la urgente, lleno en rojo); el estado, uno grande: en curso (un hilo la trabaja),
//   lleno como un hilo trabajando; te espera (un agente dejó algo para decidir), un aro. Sin estado, la ranura vacía.
// · el código y el proyecto, en ranuras de texto (alinean como columnas); el proyecto, un clic lo abre en proyectos.
// · el texto en una línea, cortado con «…» (entero al pasar el mouse); antes, la palabra de lo que dejó el agente
//   («pregunta», «preparado») y el responsable si no es la persona.
// · al final, la estrella (un aro con un punto: señalada) y la fecha, en rojo si venció; al pasar el mouse, lo de
//   todos los días (la estrella, otra fecha, compartir, la instrucción, hecha) y el ⋯ con todo lo demás.
//
// Las piezas (piezasTarea) son las mismas en la tarjeta de una tarea en foco (foco.ts, componentes/tarjeta.ts).
//
// Un clic en la fila abre su ficha (o la lleva a su hilo, si no tiene); ⌘-clic, a su hilo. Las acciones las atiende
// PantallaTareas (tareas.ts); los filtros y el orden de «tareas», vista.ts, con los `data-*` que lleva la fila.

import { item, type Accion, type Pieza, type Tono } from '../../componentes/item';
import * as S from '../../componentes/senales';
import { esc, limpiarMd, normalizar } from '../../estilo';
import { modelo } from '../../modelo';
import { I } from '../../web/iconos';
import { type Pendiente, delaPersona, duenoDe, esMia, yo } from './dia';

/** El proyecto de una tarea, para su columna: su nombre entero (el globo), el corto (la columna) y su ruta. */
export interface ProyectoDeFila { nombre: string; corto: string; ruta: string }

export interface OpcionesFila {
    /** la columna del proyecto: `undefined`, la lista no la lleva (la de un proyecto); `null`, no tiene */
    proyecto?: ProyectoDeFila | null;
    /** espera una decisión (lo que dejó un agente, con ficha) */
    rev?: boolean;
    /** va en «esta semana» (para el filtro de «tareas») */
    semana?: boolean;
    /** el color de la palabra de lo que dejó (las pestañas de un proveedor traen el suyo) */
    color?: string;
    /** un ítem de la pestaña de un proveedor (un feed): se lee en su ficha y nada más; sin código ni acciones */
    lectura?: boolean;
    /** en un feed: la lista dice prioridad o quién dejó algo (`de`), y cada fila lleva sus dos ranuras: la prioridad (el
     *  círculo de siempre, en su color) y «tuya» (lo que se mandó la persona, el ícono de persona en el acento) */
    marcas?: boolean;
    /** sin la ranura del código: ninguna fila de la lista lo tiene (las casillas de un documento, en el detalle de un
     *  proyecto), y su lugar vacío corría el texto */
    sinCodigo?: boolean;
}

const tonoAvance: Record<string, Tono> = { preparado: 'exito', cerrar: 'acento', pregunta: 'atencion', choca: 'peligro' };
export const NOMBRE_PRI = ['urgente', 'alta', 'media', 'baja'];

/** La fecha de una tarea, como la meta de su fila: lo vencido en rojo, hoy y mañana en el color de cuidado. */
export function fecha(dias: number | null): Pieza | undefined {
    if (dias === null) return undefined;
    if (dias < 0) return { texto: `${dias}d`, tono: 'peligro', ayuda: `venció hace ${-dias} día${dias === -1 ? '' : 's'}` };
    if (dias === 0) return { texto: 'hoy', tono: 'atencion', ayuda: 'vence hoy' };
    if (dias === 1) return { texto: 'mañana', tono: 'atencion', ayuda: 'vence mañana' };
    return { texto: `${dias}d`, ayuda: `vence en ${dias} días` };
}

/** AAAA-MM-DD de un día, en la hora de aquí. */
export const iso = (d: Date): string => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

/** Las fechas de siempre para mover una tarea, contadas desde `ahora`: hoy, mañana, pasado mañana, el próximo lunes (el
 *  de la semana que viene, si hoy es lunes), en una semana y fin de mes. Las ofrecen elegirFecha (tareas.ts) y foco. Al
 *  mediodía, para que un cambio de hora no las corra de día. */
export function fechasDeSiempre(ahora = Date.now()) {
    const hoy = new Date(ahora); hoy.setHours(12, 0, 0, 0);
    const en = (n: number) => { const d = new Date(hoy); d.setDate(d.getDate() + n); return d; };
    return {
        hoy, manana: en(1), pasado: en(2), lunes: en(((8 - hoy.getDay()) % 7) || 7), semana: en(7),
        finDeMes: new Date(hoy.getFullYear(), hoy.getMonth() + 1, 0, 12),
    };
}

/** Lo que lleva cada acción de la fila de una tarea (`data-valor`): [proveedor, id, ref], en JSON. */
export const valorDe = (p: Pendiente): string => JSON.stringify([p.fila.proveedor, p.fila.id || p.ref, p.ref]);

/** Otra fecha para una tarea, al pasar el mouse: el ícono de fecha, que corre `reagendar` (tareas.ts) con su `valor`.
 *  El mismo en las listas de tareas y en las filas de Táctica (que lo atiende como `tactica-fecha`: relee también lo que
 *  espera, y en un ensayo no toca nada). */
export function accionFecha(valor: string, sinFecha: boolean, accion = 'reagendar'): Accion {
    return { accion, icono: I.fecha, datos: { valor }, ayuda: sinFecha ? 'ponerle fecha' : 'otra fecha' };
}

/** Las dos ranuras de un ítem de un feed (`marcas`): su prioridad, en el círculo y el color de la de una tarea (sin
 *  prioridad, la ranura vacía), y si lo dejó la persona misma, el ícono de persona en el acento. Las mismas en la ficha
 *  de lectura (leer.ts). */
export function marcasLectura(f: { prioridad?: number | null; de?: string }): [Pieza | null, Pieza | null] {
    const n = typeof f.prioridad === 'number' ? f.prioridad : null;
    return [
        n === null ? null : prioridadTarea(n),
        delaPersona(f.de) ? { icono: I.persona, tono: 'acento', ayuda: 'tuya: te la mandaste tú' } : null,
    ];
}

/** La prioridad de una tarea en su círculo chico (la urgente, P0, lleno en rojo), con su globo: «P1 · alta» y, si se
 *  puede cambiar desde su ⋯ (`cambiar`: tiene ficha), cómo. La misma en «te esperan» (esperas.ts). */
export function prioridadTarea(n: number | null, cambiar = false): Pieza {
    const como = cambiar ? '\ncambiarla: ⋯' : '';
    return n === 0 ? S.urgente(`P0 · urgente${como}`)
        : S.prioridad(n, false, n === null ? 'sin prioridad' : `P${n} · ${NOMBRE_PRI[n] ?? ''}${como}`);
}

/** Lo que dice una tarea, en piezas, lo mismo en una fila y en una tarjeta (foco): su prioridad y su estado (círculos),
 *  lo que va antes del título (lo que dejó un agente, el responsable si no es la persona), lo de todos los días al pasar
 *  el mouse y el ⋯, la estrella y la fecha. */
export function piezasTarea(p: Pendiente, o: { rev?: boolean; color?: string } = {}) {
    const f = p.fila;
    const ficha = !!f.ficha;
    const valor = valorDe(p);
    const dueno = f.dueno ?? '';
    const [palabra] = (f.avance ?? '').split(' ');
    const rev = o.rev ?? (!!p.avance && ficha);

    const n = f.prioridad ?? null;
    const prioridad = prioridadTarea(n, ficha);
    const estado = p.enCurso ? S.atencion('trabajando', false, 'en curso: un hilo la está trabajando')
        : rev ? S.atencion('espera', false, `te espera: ${palabra || 'un agente dejó algo'} para decidir`) : null;

    const prefijo: Pieza[] = [];
    if (rev && palabra) {
        prefijo.push(o.color ? { html: `<span style="color: var(--${esc(o.color)})">${esc(palabra)}</span>` }
            : { texto: palabra.replace(':', ' '), tono: tonoAvance[palabra.replace(/:.*/, '')] ?? 'tenue' });
    }
    if (dueno && !esMia(dueno)) prefijo.push({ texto: `→ ${dueno}`, tono: 'remoto', ayuda: `responsable: ${dueno}${ficha ? '\ncambiarlo: ⋯' : ''}` });

    // lo de todos los días, al pasar el mouse; lo demás (prioridad, responsable, acciones del proveedor), en el ⋯
    const v = { valor };
    const acciones: Accion[] = [];
    if (ficha) {
        acciones.push({ accion: 'estrella-tarea', icono: f.estrella ? I.estrella : I.sinEstrella, datos: v,
            ayuda: f.estrella ? 'quitarle la estrella' : 'ponerle estrella: va siempre en «esta semana»' });
        acciones.push(accionFecha(valor, p.dias === null));
        if (modelo.equipoRemoto) {
            const compartida = !!f.etiquetas?.includes('equipo');
            acciones.push({ accion: 'equipo-tarea', icono: I.compartir, tono: compartida ? 'acento' : undefined, datos: v,
                ayuda: compartida ? 'compartida con el equipo: dejar de compartirla' : 'compartirla con el equipo (verán título, estado y prioridad)' });
        }
    }
    acciones.push({ accion: 'instruccion-fila', icono: I.instruccion, tono: 'agente', datos: v,
        ayuda: 'instrucción: mandársela a su hilo, a uno nuevo, a otro o a un agente' });
    if (ficha) acciones.push({ accion: 'hecha-fila', icono: I.hecha, datos: v, ayuda: 'marcarla hecha' });
    else if (!f.proveedor) acciones.push({ accion: 'hecha-vineta', icono: I.hecha, datos: { valor: JSON.stringify([p.ref, p.texto]) }, ayuda: 'marcarla hecha: [ ] → [x] en su documento' });
    const menu: Accion = ficha ? { accion: 'menu-tarea', icono: I.menu, datos: v, ayuda: 'más: prioridad, responsable, lo que trae su proveedor' }
        : { accion: 'menu-vineta', icono: I.menu, datos: { valor: JSON.stringify([p.ref, p.texto, p.hilo, dueno]) }, ayuda: 'más' };

    return {
        valor, rev, texto: limpiarMd(p.texto), prioridad, estado, prefijo, acciones, menu,
        aviso: f.estrella ? S.estrella('con estrella: va siempre en «esta semana»') : undefined,
        meta: fecha(p.dias),
    };
}

/** La fila de una tarea, en HTML. */
export function filaTarea(p: Pendiente, o: OpcionesFila = {}): string {
    const f = p.fila;
    const ficha = !!f.ficha;
    const dueno = f.dueno ?? '';
    const persona = yo.persona ? yo.persona[0].toUpperCase() + yo.persona.slice(1) : 'tú';
    const { valor, rev, texto, prioridad, estado, prefijo, acciones, menu, aviso, meta } = piezasTarea(p, o);

    // con ficha, el clic la abre; sin ella, la lleva al hilo de su proyecto (o abre uno)
    const accion = ficha || o.lectura ? 'tarea' : 'pendiente';
    const ayudaClic = o.lectura ? 'clic: leerlo' : ficha ? 'clic: leerla y decidir' : p.hilo ? `clic: llevarla a «${p.hilo}»` : 'clic: abrir un hilo donde trabajarla';

    const codigo: Pieza = { texto: ficha || f.proveedor ? p.ref : '', ancho: 5, tono: 'tenue' };
    const inicio: (Pieza | null)[] = [prioridad, estado, ...o.sinCodigo ? [] : [codigo]];
    if (o.proyecto !== undefined) {
        const pr = o.proyecto;
        inicio.push(pr ? { html: `<span data-accion="proy-ir" data-valor="${esc(pr.ruta)}">${esc(pr.corto)}</span>`, ancho: 14, tono: 'acento',
            ayuda: `${pr.nombre}\nclic: verlo en proyectos` } : { texto: '', ancho: 14 });
    }

    const proy = o.proyecto ? o.proyecto.corto : '';
    const buscable = normalizar([p.ref, p.texto, p.hilo, f.ruta ?? '', f.proyecto ?? '', o.proyecto?.nombre ?? '', f.avance ?? '', dueno].join(' '));
    if (o.lectura) {
        return item({ clases: ['tarea'], accion, datos: { valor }, ayuda: `${texto}\n${ayudaClic}`, prefijo, titulo: texto, meta,
            ...(o.marcas ? { inicio: marcasLectura(f) } : {}) });
    }
    return item({
        clases: ['tarea', ...(p.enCurso ? ['encurso'] : [])],
        accion,
        datos: {
            valor: ficha ? valor : p.ref, area: f.area ?? '', ...duenoDe(dueno, ficha || !!f.proveedor),
            rev: rev ? '1' : '0', dias: p.dias === null ? '' : String(p.dias), encurso: p.enCurso ? '1' : '0', texto: buscable,
            pri: f.prioridad === undefined || f.prioridad === null ? '' : String(f.prioridad), sem: o.semana ? '1' : '0',
            estrella: f.estrella ? '1' : '0', est: f.estrella ? 'a' : '', orden: String(p.urgencia), ref: p.ref,
            alfa: normalizar(texto), proy: normalizar(proy), resp: normalizar(dueno || (ficha ? persona : '')),
        },
        ayuda: `${p.ref} · ${texto}\n${ayudaClic}\n⌘-clic: ${ficha ? 'a su hilo' : 'un hilo nuevo para ella'}`,
        inicio,
        prefijo,
        titulo: texto,
        aviso,
        meta,
        acciones,
        menu,
    });
}
