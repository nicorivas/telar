// Contestar lo que te espera: la ventana que se abre desde «te esperan» (docs/propuestas/lo-que-espera-a-la-persona.md,
// paso 2). Una sola para todas las clases de espera, sobre `ventana()`: arriba el resumen, después lo que se pliega, las
// opciones como filas que se eligen, «Otra cosa…» (texto libre), y abajo «Conversarlo» (la instrucción, con la espera como
// contexto) o «ir al hilo», cancelar y el botón que hace lo elegido. De una tarea o de una pregunta de un módulo, su ficha
// a la izquierda (lo que hace recordar de qué se trata) y lo que se pide a la derecha:
//
//   ┌──────────────────────────────────────────────────────────────────────────────────────────┐
//   │ Colegio del Valle: el pedido del plan lector 2027                                        │  el título
//   │ tarea:T70 · colegio · P1 · vence el 17-nov · hace 1 d                                    │  quién, dónde, desde cuándo
//   │ DE QUÉ SE TRATA                              │ pregunta                                  │
//   │ El colegio compra cada año los libros…       │ el colegio pide 300 ejemplares…           │  lo que propone el agente
//   │ CÓMO LLEGAMOS AQUÍ                           │ ○ aceptar el 12%                          │  una opción: un clic la elige
//   │ 2-oct   reunión · creada  desde la minuta    │ ○ contraofertar un 8%       ★ recomendada │
//   │ ▸ 9 cosas más en el medio                    │ ○ consultarlo con la contadora            │
//   │ 5-nov   tú                hasta un 8%…       │ ○ Otra cosa…                              │  texto libre
//   │ 5-nov   agente · aplicó   le escribí…        │ ▸ para el agente                          │
//   │ QUÉ ESTÁ EN JUEGO · QUÉ HAY RELACIONADO      │                                           │
//   ├──────────────────────────────────────────────┴───────────────────────────────────────────┤
//   │ ◇ conversarlo                                                    cancelar ⎋  responder ⏎ │
//   └──────────────────────────────────────────────────────────────────────────────────────────┘
//
// De una tarea y de una pregunta de un módulo, a la izquierda va su ficha (componentes/ficha-contestar.ts): de qué se trata,
// cómo se llegó aquí, qué está en juego y qué hay relacionado, para recordar sin abrir otra cosa; a la derecha, lo que se
// pide y las opciones, enteras. En el teléfono, una debajo de la otra.
//
// De una tarea, en el encabezado, su barra: la misma de su ficha en la vista tareas (vistas/dashboard/barra-tarea.ts), con
// la estrella y compartir delante del título, y al final lo que se le hace con un ícono, menos lo que la ventana ya hace a
// su manera (FUERA_DE_CONTESTAR). Sin teclas: las de la ventana (⏎, ⎋, lo que se escribe) no se pisan. Llega con la
// ficha de su proveedor, después de abrirla.
//
// En el avance de una tarea, debajo y plegado, «para el agente»: una nota para esta tarea (para la próxima revisión, o
// «hazte cargo ya») y cómo trabajar las de este tipo; cada una sale como una línea [respuesta] de la tarea con su marca
// (MARCAS_AGENTE) y dice a qué agente llega (con «hazte cargo ya», además un aviso: web/contestar.ts). Lo que declara el
// agente en su avance (urgencia.ts) cambia lo que se ofrece: de decidir, sus opciones; de aprobar, enviar, descartar y
// «Editar…»; de lo que pide hacer, «Hecho».
//
// Un clic elige (el círculo pasa de aro a centro) y el botón de abajo dice lo que va a hacer; ⏎ o el botón lo hace. Es
// puro: da el HTML de un estado (lo elegido, lo escrito, si se está enviando, un aviso). Abrirlo, elegir y mandar lo hace
// web/contestar.ts; sus estilos, media/css/contestar.css.
//
// Por clase (`contestable`):
// - `avance:*` de una tarea: la propuesta del agente; si propone cerrarla, la opción de cerrarla así; y la respuesta
//   escrita (`responder`). A la izquierda, su ficha: la tarea entera (llega después de abrirla) y su proyecto.
// - `retenido`: el mensaje entero, «soltarlo» y «descartarlo» (cada uno con su ícono, en el color de lo que hace, y su
//   globo); descartarlo pregunta antes, con el foco en «cancelar» (`confirmar`, `descarte`).
// - `pregunta` (la pregunta en vivo de un hilo): sus preguntas con sus opciones, y otra respuesta por pregunta; se
//   contesta como en la vista conversación (POST /hilos/responder).
// - `decide` (la pregunta de un módulo): sus opciones, con la recomendada marcada y lo que hará cada una; «Otra cosa…». A
//   la izquierda, su ficha: el resumen entero, el porqué, el detalle y su archivo.
// - `permiso` sin pregunta: no se contesta aquí (el diálogo es de la terminal): se muestra y se ofrece ir al hilo.

import type { JsonEspera, JsonPagina } from '../cli';
import { esc } from '../estilo';
import { C, I } from '../web/iconos';
import { circulo } from './circulo';
import { enLinea, parrafos as parrafosEnLinea } from './en-linea';
import { type DeTarea, type Ficha, fichaDePregunta, fichaDeTarea, fichaHtml } from './ficha-contestar';
import { accionDePantalla } from './pantalla';
import { ventana, type PropsVentana } from './ventana';
import { cancelar, pieBotones, type Boton } from './boton';
import { type IconoDeTarea, type IconoDeTitulo, deBarra, deTitulo, iconoDeTitulo } from '../vistas/dashboard/barra-tarea';
import { declaradoDe, viaDe, type Pide } from '../vistas/dashboard/urgencia';

/** De qué clase es lo que se contesta: decide cómo se ve y qué se manda. */
export type ClaseContestar = 'tarea' | 'retenido' | 'en-vivo' | 'decide' | 'permiso' | 'otra';

/** Una opción: lo que se manda (`id`), cómo se llama, lo que hará y el verbo del botón cuando está elegida. */
export interface OpcionContestar {
    id: string;
    texto: string;
    /** lo que hará elegirla, o (en la pregunta en vivo) lo que dice de sí misma: una línea tenue, debajo */
    nota?: string;
    /** corre algo además de contestar (una acción de un objeto, cerrar una tarea): la nota lo dice con su ícono */
    efecto?: string;
    recomendada?: boolean;
    /** el botón de abajo, con esta elegida («responder», «cerrarla», «soltarlo») */
    verbo: string;
    /** el ícono de lo que hace, antes del nombre, en el color de lo que hace (web/iconos.ts, C: `rojo`, lo que quita) */
    icono?: string;
    tono?: string;
    /** su globo: lo que hace, en una línea */
    ayuda?: string;
    /** lo que destruye pregunta antes de hacerlo, con el foco en «cancelar» (web/contestar.ts, `Hacer.confirmar`) */
    confirmar?: Confirmacion;
}

/** Lo que pregunta algo que destruye antes de hacerlo: la pregunta, lo que pasa (debajo) y el botón que lo hace. */
export interface Confirmacion { pregunta: string; detalle: string; boton: string }

/** Un bloque de opciones: una pregunta (la en vivo puede traer varias). Sin enunciado, las opciones de la ventana. */
export interface BloqueContestar {
    enunciado?: string;
    encabezado?: string;
    /** se eligen varias (la pregunta en vivo con `varias`) */
    varias?: boolean;
    opciones: OpcionContestar[];
    /** «Otra cosa…»: texto libre en vez de una opción. null: este bloque no lo lleva */
    otra: { nombre: string; placeholder: string; nota: string; verbo: string } | null;
}

/** Lo que se contesta, armado de una espera: lo que la ventana muestra y ofrece. */
export interface Contestable {
    clase: ClaseContestar;
    direccion: string;
    titulo: string;
    /** quién, dónde, desde cuándo: una línea tenue bajo el título */
    ayuda: string;
    /** una palabra antes del resumen, en el color de su clase («pregunta», «propone cerrarla: hecha») */
    marca?: string;
    /** el resumen, en texto (párrafos separados por una línea en blanco; `código` y **negrita**) */
    resumen: string;
    /** el resumen es un texto que se lee tal cual (un mensaje): con sus saltos de línea */
    literal?: boolean;
    /** lo plegado: cada parte con su título */
    detalle: { titulo: string; texto: string }[];
    /** de una tarea o una pregunta de un módulo: lo que hace recordar de qué se trata (va a la izquierda) */
    ficha?: Ficha;
    bloques: BloqueContestar[];
    /** abajo a la izquierda: conversarlo (la instrucción con la espera como contexto) o ir al hilo */
    conversar: boolean;
    ir?: { direccion: string; texto: string };
    /** lo que se dice cuando no hay nada que contestar aquí (un permiso de la terminal) */
    nota?: string;
    /** de una tarea: a qué agente le llega lo que se le deja (el que la propuso, si se sabe; si no, el que escribe los
     *  avances, `general`, que dice la configuración y se sabe después de abrir) */
    agente?: { a: string; propuso: boolean; general?: boolean };
    /** lo que va delante de lo escrito en «Otra cosa…» (de aprobar, «editar: ») */
    prefijoOtra?: string;
    /** de una tarea, cuando llega la ficha de su proveedor: su barra en el encabezado */
    barra?: { titulo: IconoDeTitulo[]; iconos: IconoDeTarea[] };
}

/** Lo de la barra de una tarea que en Contestar no va, porque la ventana ya lo hace a su manera:
 *
 *    acción            en Contestar         por qué
 *    la fecha          siempre              (la de la tarea: con una fecha dura, el globo dice que esa no se mueve)
 *    prioridad, quién la hace, esperar a, tamaño, la estrella, compartir      siempre: la ventana no los hace de otra forma
 *    hecha             no al cerrar ni en lo que pide hacer: «Cerrarla» y «Hecho» son sus opciones
 *    descartar         no al cerrar: «Cerrarla» como propone u «Otra cosa…»
 *    la instrucción    nunca: «conversarlo», abajo, la abre con la espera como contexto
 *    la nota           nunca (no es de la barra): «para el agente»
 *
 *  Esperar a, hecha y descartar contestan la propuesta (el modelo la borra): la ventana se cierra con lo hecho. */
export function fueraDeContestar(via: Pide | null, marca: string): Set<string> {
    const cerrar = via === 'cerrar' || marca === 'cerrar';
    return new Set([...cerrar ? ['hecha', 'descartar'] : [], ...via === 'hacer-tu' ? ['hecha'] : []]);
}

/** La barra de una tarea en Contestar, de la ficha de su proveedor (`ficha_tarea`): sin ella, ninguna. `dura`: la fecha
 *  dura que declaró el agente, para decirla en el globo de la fecha. */
export function barraDeTarea(ficha: JsonPagina | undefined, fuera: ReadonlySet<string>, dura = ''): Contestable['barra'] {
    const acciones = ficha?.acciones ?? [];
    if (!acciones.length) return undefined;
    return {
        titulo: deTitulo(acciones),
        iconos: deBarra(acciones, fuera).map(x => (x.rol === 'fecha' && dura
            ? { ...x, ayuda: `${x.ayuda} de la tarea · la fecha dura (${dia(dura)}) es externa: esa no se mueve con esto` } : x)),
    };
}

/** Lo que se contesta a algo por aprobar: enviarlo o descartarlo (lo que le llega al agente, en su historia), o
 *  editarlo (lo escrito, con este prefijo). */
export const APROBAR = { enviar: 'aprobado: envíalo', descartar: 'descartado: no va', editar: 'editar: ' } as const;
/** Lo que se contesta a lo que pide hacer, cuando ya se hizo. */
export const HECHO = 'hecho: ya lo hice';

/** Las marcas con que sale lo que se le deja al agente, al principio de una línea [respuesta] de la tarea (las define el
 *  agente que escribe los avances): una nota para su próxima revisión, una para que se haga cargo ya (además, un mensaje
 *  para que la atienda), y cómo trabajar las de este tipo (va a su regla de oficio). */
export const MARCAS_AGENTE = { revision: 'instrucción', ya: 'prompt', meta: 'meta' } as const;

/** Lo que se le deja al agente desde la ventana (plegado): la nota para esta tarea y cuándo la atiende, y cómo trabajar
 *  las de este tipo. */
export interface ParaElAgente { cuando: 'revision' | 'ya'; nota: string; meta: string; abierto: boolean }

/** Las líneas que salen para el agente, con su marca: la nota (instrucción o prompt) y la meta. Vacías, nada. */
export function lineasAgente(p: ParaElAgente | undefined): string[] {
    if (!p) return [];
    return [p.nota.trim() ? `${MARCAS_AGENTE[p.cuando]}: ${p.nota.trim()}` : '', p.meta.trim() ? `${MARCAS_AGENTE.meta}: ${p.meta.trim()}` : ''].filter(Boolean);
}

/** A quién le llega, dicho con su «a»: el agente que la propuso, o (sin saberlo) el que escribe los avances. */
export const aQuien = (a: Contestable['agente']): string =>
    (a?.a ? `a ${a.a}${a.propuso ? ' (la propuso)' : a.general ? ' (escribe los avances)' : ''}` : 'al agente que escribe los avances');

/** Lo que va cambiando mientras está abierta: lo elegido en cada bloque, lo escrito, si se está mandando, un aviso. */
export interface EstadoContestar {
    elegidas: string[][];
    otras: string[];
    /** el «Otra cosa…» que está abierto (su bloque), o -1 */
    abierta: number;
    enviando?: boolean;
    aviso?: { texto: string; tono: 'falla' | 'info' };
    /** lo plegado, abierto */
    detalle?: boolean;
    /** de la ficha: lo del medio de la historia, desplegado */
    historia?: boolean;
    /** una acción de la barra de la tarea, en curso: la barra espera */
    haciendo?: boolean;
    /** lo que se le deja al agente (de una tarea, si quien la abre sabe dejárselo: `Hacer.paraElAgente`) */
    agente?: ParaElAgente;
}

export const estadoInicial = (c: Contestable): EstadoContestar => ({
    elegidas: c.bloques.map(() => []), otras: c.bloques.map(() => ''),
    // sin opciones, el texto es la respuesta: abierto de entrada
    abierta: c.bloques.findIndex(b => !b.opciones.length && b.otra), detalle: false,
});

const texto = (v: unknown): string => typeof v === 'string' ? v : v === undefined || v === null ? '' : String(v);
const corto = (d: string): string => {
    const id = d.replace(/^[a-z-]+:/, '').replace(/@[\w-]+$/, '');
    try { return decodeURIComponent(id).split('/').pop() ?? ''; } catch { return id.split('/').pop() ?? ''; }
};

/** «hace 3 d», «hace 12 min», de `desde` a `ahora`; vacío si no se sabe. */
export function haceCuanto(desde: string, ahora = Date.now()): string {
    if (!desde) return '';
    const t = Date.parse(desde.length === 10 ? `${desde}T00:00:00` : desde);
    if (Number.isNaN(t)) return '';
    const min = Math.max(0, Math.round((ahora - t) / 60000));
    if (min < 60) return `hace ${min} min`;
    if (min < 60 * 24) return `hace ${Math.round(min / 60)} h`;
    const d = Math.floor(min / 1440);
    return d < 14 ? `hace ${d} d` : `hace ${Math.floor(d / 7)} sem`;
}

const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
/** `2026-11-24` → «24-nov». */
const dia = (f: string): string => {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(f);
    return m ? `${Number(m[3])}-${MESES[Number(m[2]) - 1]}` : f;
};
const linea = (...partes: (string | false | undefined)[]): string => partes.filter(Boolean).join(' · ');
/** quien pregunta, sin su tipo: `agente:biblioteca` → «biblioteca» */
const quien = (de: string): string => de.replace(/^(agente|hilo):/, '');

const CIERRE: Record<string, string> = { hecha: 'hecha', caduca: 'caducó', descartada: 'descartada' };

/** Cómo propone cerrarse una tarea: el `como` de su avance (`cerrar:hecha`), o (si declaró `pide=cerrar` en otra
 *  marca) lo que dice su texto: «como hecha», «como caduca», «como descartada». Vacío si no lo dice. */
export function comoCierre(e: JsonEspera): string {
    const c = texto(e.campos?.como);
    if (c) return c;
    return /\bcomo (hecha|caduca|descartada)\b/i.exec(texto(e.campos?.texto) || e.resumen)?.[1]?.toLowerCase() ?? '';
}

/** Lo que la ventana sumó a una tarea después de abrirla (web/contestar.ts, `completar`): la tarea entera, su proyecto y
 *  las otras del proyecto, o por qué no se pudo leer. Sin nada todavía, la ficha dice que la está leyendo. */
export const deTarea = (c: Record<string, unknown>): DeTarea => ({
    ...c.tarea ? { tarea: c.tarea as DeTarea['tarea'] } : {},
    ...c.proyecto_ficha ? { proyecto: c.proyecto_ficha as DeTarea['proyecto'] } : {},
    ...Array.isArray(c.otras) ? { otras: c.otras as DeTarea['otras'] } : {},
    ...c.tarea_falla ? { falla: texto(c.tarea_falla) } : {},
});

/** Una espera, como se contesta. */
export function contestable(e: JsonEspera, ahora = Date.now()): Contestable {
    const c = e.campos ?? {};
    const desde = haceCuanto(e.desde, ahora);
    const base = { direccion: e.direccion, titulo: e.titulo || e.direccion, detalle: [] as Contestable['detalle'], conversar: true };
    const hilo = e.enlaces.find(x => x.startsWith('hilo:'));

    if (e.clase.startsWith('avance:')) {
        const marca = e.clase.slice('avance:'.length);
        const como = comoCierre(e);
        // lo que propone, sin lo que declara el agente delante (la vía, el peso…): eso lo dice la ventana a su manera
        const d = declaradoDe(e);
        const via = viaDe(e, d);
        const propuesta = d.resto || e.resumen;
        const cierre: OpcionContestar[] = (marca === 'cerrar' || via === 'cerrar') && CIERRE[como] ? [{
            id: 'cerrar', texto: `Cerrarla: ${CIERRE[como]}`, verbo: 'cerrarla', efecto: `tarea ${como}`,
            nota: `queda ${CIERRE[como]}, como propone, y la propuesta deja de esperarte`,
        }] : [];
        // de decidir, las opciones que declara (lo que se contesta es su texto), sin nota: la misma bajo cada una era ruido; de aprobar, enviar o descartar
        const opciones: OpcionContestar[] = [...cierre,
            ...via === 'decidir' ? (d.opciones ?? []).map(o => ({ id: o.texto, texto: o.texto, recomendada: !!o.recomendada, verbo: 'responder' })) : [],
            ...via === 'hacer-tu' ? [{ id: HECHO, texto: 'Hecho', verbo: 'responder', nota: 'le dices que ya lo hiciste: lo cierra o sigue con lo que venía' }] : [],
            ...via === 'aprobar' ? [
                { id: APROBAR.enviar, texto: 'Enviar', verbo: 'enviar', nota: 'lo apruebas: el agente lo manda como está' },
                { id: APROBAR.descartar, texto: 'Descartar', verbo: 'descartar', nota: 'no va: el agente lo deja' },
            ] : []];
        const ver = via === 'decidir' ? 'decide' : via === 'aprobar' ? 'aprueba lo que dejó hecho' : via === 'hacer-tu' ? 'hazlo tú'
            : { pregunta: 'pregunta', cerrar: `propone cerrarla: ${CIERRE[como] ?? como}`, preparado: 'dejó preparado', choca: 'choca con otra' }[marca] ?? marca;
        const quien = texto(c.de) || texto(c.agente);
        const aprobar = via === 'aprobar';
        return {
            ...base, clase: 'tarea', marca: ver, resumen: propuesta || '(sin texto)',
            agente: { a: quien.replace(/^(agente|hilo):/, ''), propuso: !!quien },
            ...aprobar ? { prefijoOtra: APROBAR.editar } : {},
            ayuda: linea(e.direccion, e.enlaces[0] ? corto(e.enlaces[0]) : '', typeof c.prioridad === 'number' && c.prioridad ? `P${c.prioridad}` : '',
                c.vence ? `vence el ${dia(texto(c.vence))}` : '', desde),
            ficha: fichaDeTarea(e, deTarea(c), ahora),
            barra: barraDeTarea(c.ficha_tarea as JsonPagina | undefined, fueraDeContestar(via, marca), d.dura),
            bloques: [{ opciones, otra: aprobar ? {
                nombre: 'Editar…', placeholder: 'qué cambiar antes de enviarlo', verbo: 'responder',
                nota: `le llega como «${APROBAR.editar}…» en la historia de la tarea; el agente lo cambia y vuelve a proponerlo`,
            } : {
                nombre: opciones.length ? 'Otra cosa…' : 'tu respuesta',
                placeholder: marca === 'pregunta' ? 'lo que le contestas' : 'lo que le dices (sigue abierta)',
                nota: 'queda en la historia de la tarea y la propuesta deja de esperarte; el agente lo ve al volver a ella',
                verbo: 'responder',
            } }],
        };
    }

    if (e.clase === 'retenido') {
        const para = texto(c.para), de = texto(c.de);
        return {
            ...base, clase: 'retenido', marca: 'retenido', literal: true, resumen: texto(c.texto) || e.resumen,
            ayuda: linea(texto(c.modo) || 'mensaje', desde, c.motivo ? `lo retuvo: ${texto(c.motivo)}` : ''),
            bloques: [{ opciones: [{
                id: 'soltar', texto: 'Soltarlo', verbo: 'soltarlo', efecto: 'sale', icono: I.enviar, tono: C.hecho,
                ayuda: 'soltarlo: sale ahora, como si no lo hubieran retenido',
                nota: `sale ahora a «${para || '?'}», como si no lo hubieran retenido${de ? `; «${de}» no se entera` : ''}`,
            }, {
                id: 'descartar', texto: 'Descartarlo', verbo: 'descartarlo', icono: I.descartar, tono: C.quitar,
                ayuda: 'descartarlo: no sale nunca; queda anotado como descartado · pide confirmación',
                nota: `no sale nunca: queda anotado como descartado${de ? `, y a «${de}» le llega un aviso de que no se entregó (no lo despierta)` : ''}`,
                confirmar: { ...descarte([e]), boton: 'Descartar' },
            }], otra: null }],
        };
    }

    if (e.clase === 'pregunta' && Array.isArray(c.preguntas) && c.preguntas.length && c.pregunta) {
        const preguntas = c.preguntas as { pregunta: string; encabezado?: string; varias?: boolean; opciones?: { etiqueta: string; descripcion?: string }[] }[];
        const varias = preguntas.length > 1;
        return {
            ...base, clase: 'en-vivo', conversar: false,
            titulo: varias ? `«${texto(c.hilo)}» te pregunta ${preguntas.length} cosas` : preguntas[0].pregunta || e.titulo,
            ayuda: linea(`«${texto(c.hilo)}» espera tu respuesta`, desde),
            resumen: texto(c.pide) && texto(c.pide) !== preguntas[0].pregunta ? texto(c.pide) : '',
            ir: hilo ? { direccion: hilo, texto: 'ir al hilo' } : undefined,
            bloques: preguntas.map(q => ({
                enunciado: varias ? q.pregunta : undefined, encabezado: q.encabezado || undefined, varias: !!q.varias,
                opciones: (q.opciones ?? []).map(o => ({ id: o.etiqueta, texto: o.etiqueta, nota: o.descripcion || undefined, verbo: 'responder' })),
                otra: { nombre: 'Otra respuesta…', placeholder: 'lo que le contestas', nota: 'le llega tal cual, como si la escribieras en su terminal', verbo: 'responder' },
            })),
        };
    }

    if (e.clase === 'decide') {
        const de = quien(texto(c.de));
        const sec = (c.secciones ?? {}) as Record<string, string>;
        const opciones = (Array.isArray(c.opciones) ? c.opciones : []) as { id: string; texto: string; accion?: string; recomendada?: boolean; no_corre?: string }[];
        const urg = texto(c.urgencia);
        return {
            ...base, clase: 'decide',
            ayuda: linea(de ? `${de} pregunta` : '', texto(c.repo), desde, c.vence ? `vence el ${dia(texto(c.vence))}` : '',
                urg && urg !== 'baja' ? `urgencia ${urg}` : ''),
            resumen: '', ficha: fichaDePregunta(e, ahora),
            bloques: [{
                opciones: opciones.map(o => ({
                    id: o.id, texto: o.texto, recomendada: !!o.recomendada, verbo: 'responder',
                    efecto: o.accion && !o.no_corre ? o.accion : undefined,
                    // solo lo que distingue a cada una (a quién le avisa es igual para todas: lo dice la ayuda)
                    nota: linea(o.accion && !o.no_corre ? `corre ${o.accion}` : '', o.no_corre) || undefined,
                })),
                otra: { nombre: 'Otra cosa…', placeholder: 'lo que decides, en tus palabras', verbo: 'responder',
                    nota: `ninguna de estas: le llega a ${de || 'quien preguntó'} lo que escribas, y no corre nada` },
            }],
        };
    }

    if (e.clase === 'permiso' || e.clase === 'pregunta') {
        const pide = texto(c.pide);
        return {
            ...base, clase: 'permiso', conversar: false,
            titulo: pide || e.titulo, ayuda: linea(`«${texto(c.hilo) || corto(hilo ?? e.direccion)}» espera en su turno`, e.maquina ? `en ${e.maquina}` : '', desde),
            resumen: '', bloques: [],
            nota: e.maquina
                ? `Es de un hilo de ${e.maquina}: lo que pide se ve y se contesta en su terminal.`
                : 'Un permiso de herramienta se da en la terminal del hilo: desde aquí no se contesta.',
            ir: hilo ? { direccion: hilo, texto: 'ir al hilo' } : undefined,
        };
    }

    // la de un módulo que no es una pregunta: se muestra y se abre donde vive
    return { ...base, clase: 'otra', ayuda: linea(e.clase, desde), resumen: e.resumen, bloques: [], nota: 'Se contesta donde vive: ábrela.',
        ir: { direccion: e.direccion, texto: 'abrirla' } };
}

/** Lo que pregunta descartar mensajes retenidos: uno (desde Contestar o su fila en «te esperan»), de quién a quién; varios
 *  (todos los de su grupo), cuántos y a quiénes les llega el aviso. Lo que pasa, debajo: no salen nunca, quedan anotados
 *  como descartados y a quien mandó cada uno le llega un aviso que no lo despierta. El botón, «Descartar». */
export function descarte(lista: readonly JsonEspera[]): { pregunta: string; detalle: string } {
    const de = [...new Set(lista.map(e => texto(e.campos?.de)).filter(Boolean))];
    if (lista.length === 1) {
        const [e] = lista;
        return { pregunta: `¿Descartar el mensaje de «${de[0] || '?'}» a «${texto(e.campos?.para) || '?'}»?`,
            detalle: `No sale nunca: queda anotado como descartado${de[0] ? `, y a «${de[0]}» le llega un aviso de que no se entregó (no lo despierta)` : ''}.` };
    }
    const quienes = de.map(x => `«${x}»`).join(', ');
    return { pregunta: `¿Descartar los ${lista.length} mensajes retenidos?`,
        detalle: `No sale ninguno: quedan anotados como descartados${quienes ? `, y a quien mandó cada uno (${quienes}) le llega un aviso de que no se entregó (no lo despierta)` : ''}.` };
}

/** El texto de un resumen o un detalle: párrafos con `código`, **negrita** y enlaces (componentes/en-linea.ts: un
 *  [texto](url) o una dirección suelta, en una pestaña nueva); un mensaje (`literal`), tal cual, con sus saltos. */
export function parrafos(t: string, literal = false): string {
    if (literal) return `<div class="contestar-literal">${esc(t.trim())}</div>`;
    return parrafosEnLinea(t);
}

/** Lo elegido y lo escrito, ¿alcanzan para contestar? Cada bloque, con una opción o con texto. */
export function listo(c: Contestable, s: EstadoContestar): boolean {
    return c.bloques.length > 0 && c.bloques.every((b, i) => (s.elegidas[i]?.length ?? 0) > 0 || !!s.otras[i]?.trim());
}

/** ¿Hay algo que mandar? Lo contestado, o (de una tarea) solo lo que se le deja al agente: también es una respuesta. */
export const hayQueMandar = (c: Contestable, s: EstadoContestar): boolean => listo(c, s) || lineasAgente(s.agente).length > 0;

/** El verbo del botón de abajo: el de lo elegido (si es uno solo), o «responder»; sin nada elegido y con algo para el
 *  agente, «dejárselo». */
export function verbo(c: Contestable, s: EstadoContestar): string {
    if (!listo(c, s) && lineasAgente(s.agente).length) return 'dejárselo';
    if (c.bloques.length === 1) {
        const b = c.bloques[0];
        if (s.otras[0]?.trim() && b.otra) return b.otra.verbo;
        const o = b.opciones.find(x => s.elegidas[0]?.includes(x.id));
        if (o) return o.verbo;
        if (b.opciones.length === 1 && !b.otra) return b.opciones[0].verbo;
        // un retenido no se responde: se suelta o se descarta
        if (c.clase === 'retenido') return b.opciones.map(x => x.verbo).join(' o ');
        return 'responder';
    }
    return 'responder';
}

function opcion(o: OpcionContestar, i: number, elegida: boolean, apagada: boolean): string {
    const nota = o.nota ? `<span class="contestar-nota">${o.efecto ? `<span class="i efecto" title="hace algo además de contestar">${I.accion}</span> ` : ''}${esc(o.nota)}</span>` : '';
    const rec = o.recomendada ? `<span class="contestar-rec" title="la que recomienda quien pregunta"><span class="i">${I.estrella}</span> recomendada</span>` : '';
    const icono = o.icono ? `<span class="i contestar-icono${o.tono ? ` tono-${esc(o.tono)}` : ''}">${o.icono}</span>` : '';
    return `<button type="button" class="contestar-op${elegida ? ' si' : ''}${o.recomendada ? ' rec' : ''}" data-bloque="${i}" data-op="${esc(o.id)}" aria-pressed="${elegida}"`
        + `${o.ayuda ? ` title="${esc(o.ayuda)}"` : ''}${apagada ? ' disabled' : ''}>`
        + `<span class="contestar-marca">${circulo(elegida ? { figura: 'centro' } : { lleno: 0 })}</span>`
        + `<span class="contestar-txt"><span class="contestar-nombre"><span>${icono}${icono ? ' ' : ''}${enLinea(o.texto, false)}</span>${rec}</span>${nota}</span></button>`;
}

/** Las opciones elegidas que van a hacerse y piden confirmación antes (lo que destruye: descartar un retenido). */
export function porConfirmar(c: Contestable, s: EstadoContestar): Confirmacion[] {
    return eleccion(c, s).flatMap((b, i) => (c.bloques[i]?.opciones ?? []).filter(o => o.confirmar && b.opciones.includes(o.id)).map(o => o.confirmar!));
}

function otra(b: BloqueContestar, i: number, s: EstadoContestar): string {
    if (!b.otra) return '';
    const escrito = s.otras[i] ?? '';
    const abierta = s.abierta === i || !!escrito.trim();
    const si = !!escrito.trim();
    return `<div class="contestar-otra${abierta ? ' abierta' : ''}${si ? ' si' : ''}" data-bloque="${i}">`
        + `<button type="button" class="contestar-op otra" data-bloque="${i}" data-otra="1" aria-pressed="${si}"${s.enviando ? ' disabled' : ''}>`
        + `<span class="contestar-marca">${circulo(si ? { figura: 'centro' } : { lleno: 0 })}</span>`
        + `<span class="contestar-txt"><span class="contestar-nombre">${esc(b.otra.nombre)}</span>`
        + (abierta ? `<span class="contestar-nota">${esc(b.otra.nota)}</span>` : '') + '</span></button>'
        + (abierta ? `<textarea class="contestar-campo" data-bloque="${i}" rows="2" placeholder="${esc(b.otra.placeholder)}"${s.enviando ? ' disabled' : ''}>${esc(escrito)}</textarea>` : '')
        + '</div>';
}

/** Si lo elegido quita (descartar): el botón de abajo va en el de peligro, con ⌘⌫ en vez de ⏎. */
export function quita(c: Contestable, s: EstadoContestar): boolean {
    return listo(c, s) && eleccion(c, s).some((b, i) => c.bloques[i]?.opciones.some(o => o.tono === C.quitar && b.opciones.includes(o.id)));
}

/** El pie (componentes/boton.ts, «la tecla en el pie»): conversarlo o ir al hilo a la izquierda; a la derecha, en celdas, el
 *  botón que hace lo elegido (⏎; si quita, en el de peligro y con ⌘⌫: ⏎ no lo hace) y cancelar (⎋), al último. Mientras
 *  se manda, el círculo que gira en el lugar de la tecla. */
function pie(c: Contestable, s: EstadoContestar): string {
    const izq = [
        c.conversar ? `<a data-contestar="conversar" title="abrir la instrucción con esto como contexto, para hablarlo con un agente"><span class="i">${I.instruccion}</span> conversarlo</a>` : '',
        c.ir ? `<a data-contestar="ir" data-valor="${esc(c.ir.direccion)}" title="${esc(c.ir.direccion)}"><span class="i">${I.adelante}</span> ${esc(c.ir.texto)}</a>` : '',
    ].join('');
    const puede = hayQueMandar(c, s) && !s.enviando;
    const destruye = quita(c, s);
    const botones: Boton[] = c.bloques.length ? [{
        texto: verbo(c, s), datos: { contestar: 'hacer' }, tono: destruye ? 'peligro' : 'accion', tecla: destruye ? '⌘⌫' : '⏎',
        enCurso: s.enviando ? circulo({ mov: 'gira' }) : undefined, estado: puede || s.enviando ? undefined : 'deshabilitado',
    }] : [];
    botones.push({ ...cancelar(c.bloques.length ? 'cancelar' : 'cerrar', null), datos: { contestar: 'cancelar' } });
    return pieBotones(botones, { izq, clase: 'contestar-pie' });
}

/** El cuerpo: la marca y el resumen, lo plegado, el aviso y los bloques de opciones; con ficha, ella a la izquierda y lo
 *  demás (lo que se pide) a la derecha. */
export function cuerpo(c: Contestable, s: EstadoContestar): string {
    const pedido = loPedido(c, s);
    if (!c.ficha) return pedido;
    return `<div class="contestar-dos">${fichaHtml(c.ficha, { historia: !!s.historia })}<div class="contestar-pedido">${pedido}</div></div>`;
}

/** Lo que se pide: la marca y el resumen, lo plegado, los bloques de opciones, «para el agente» y el aviso. */
function loPedido(c: Contestable, s: EstadoContestar): string {
    const h: string[] = [];
    if (c.marca || c.resumen) {
        h.push(`<div class="contestar-resumen clase-${c.clase}">`
            + (c.marca ? `<span class="contestar-marca-clase">${esc(c.marca)}</span>` : '')
            + (c.resumen ? parrafos(c.resumen, c.literal) : '') + '</div>');
    }
    if (c.detalle.length) {
        h.push(`<details class="contestar-detalle"${s.detalle ? ' open' : ''}><summary><span class="i abierto">${I.abierto}</span><span class="i plegado">${I.plegado}</span> `
            + `${esc(c.detalle.map(d => d.titulo).join(' · '))}</summary>`
            + c.detalle.map(d => `<div class="contestar-parte"><div class="contestar-parte-titulo">${esc(d.titulo)}</div>${parrafos(d.texto)}</div>`).join('')
            + '</details>');
    }
    if (c.nota) h.push(`<p class="contestar-aviso info">${esc(c.nota)}</p>`);
    c.bloques.forEach((b, i) => {
        h.push(`<fieldset class="contestar-bloque" data-bloque="${i}">`);
        if (b.encabezado || b.enunciado) {
            h.push(`<legend>${b.encabezado ? `<span class="contestar-encabezado">${esc(b.encabezado)}</span> ` : ''}`
                + `${b.enunciado ? `<span class="contestar-enunciado">${esc(b.enunciado)}</span>` : ''}`
                + `${b.varias ? '<span class="contestar-como"> · elige una o varias</span>' : ''}</legend>`);
        }
        b.opciones.forEach(o => h.push(opcion(o, i, !!s.elegidas[i]?.includes(o.id), !!s.enviando)));
        h.push(otra(b, i, s));
        h.push('</fieldset>');
    });
    if (s.agente) h.push(paraElAgente(c, s.agente, !!s.enviando));
    h.push(`<p class="contestar-aviso ${s.aviso?.tono ?? 'info'}" role="status"${s.aviso ? '' : ' hidden'}>${esc(s.aviso?.texto ?? '')}</p>`);
    return h.join('');
}

/** «para el agente», plegado: la nota para esta tarea (para la próxima revisión o «hazte cargo ya») y cómo trabajar las
 *  de este tipo, opcionales; a quién le llegan y cómo salen. */
function paraElAgente(c: Contestable, p: ParaElAgente, enviando: boolean): string {
    const cuando = (k: ParaElAgente['cuando'], nombre: string, ayuda: string) =>
        `<button type="button" class="contestar-cuando${p.cuando === k ? ' si' : ''}" data-agente-cuando="${k}" aria-pressed="${p.cuando === k}" title="${esc(ayuda)}"${enviando ? ' disabled' : ''}>`
        + `${circulo(p.cuando === k ? { figura: 'centro' } : { lleno: 0 })} ${esc(nombre)}</button>`;
    const campo = (k: 'nota' | 'meta', placeholder: string) =>
        `<textarea class="contestar-agente-campo" data-agente="${k}" rows="2" placeholder="${esc(placeholder)}"${enviando ? ' disabled' : ''}>${esc(p[k])}</textarea>`;
    const hay = [p.nota, p.meta].filter(x => x.trim()).length;
    return `<details class="contestar-agente"${p.abierto ? ' open' : ''}><summary><span class="i abierto">${I.abierto}</span><span class="i plegado">${I.plegado}</span> `
        + `para el agente${hay ? ` · ${hay === 1 ? '1 nota' : `${hay} notas`}` : ''}</summary>`
        + `<p class="contestar-nota contestar-a">llega ${esc(aQuien(c.agente))}, con la dirección de la tarea</p>`
        + '<div class="contestar-parte"><div class="contestar-parte-titulo">nota para esta tarea</div>'
        + `<div class="contestar-cuandos">${cuando('revision', 'para la próxima revisión', `queda en la tarea como «${MARCAS_AGENTE.revision}: …»: la lee el agente la próxima vez que la revise`)}`
        + `${cuando('ya', 'hazte cargo ya', `queda en la tarea como «${MARCAS_AGENTE.ya}: …» y le llega un mensaje para que la atienda ahora, con lo que decidiste`)}</div>`
        + campo('nota', 'qué hay que hacer para cumplirla')
        + '</div><div class="contestar-parte"><div class="contestar-parte-titulo">cómo trabajar esto</div>'
        + campo('meta', 'cómo se preparó, qué faltó en el resumen: para que las de este tipo lleguen mejor')
        + `<p class="contestar-nota">va a su oficio, no solo a esta tarea: queda como «${MARCAS_AGENTE.meta}: …»</p></div></details>`;
}

/** La barra de una tarea, en el encabezado: la estrella y compartir delante del título (`iconos`), y lo demás al final
 *  (`herramientas`), con los íconos, los colores y los globos de su ficha en la vista tareas. Un clic lleva
 *  `data-contestar="tarea"` y el número de la acción en su ficha; mientras una corre, la barra espera. */
export function barraHtml(c: Contestable, s: EstadoContestar): Pick<PropsVentana, 'iconos' | 'herramientas'> {
    if (!c.barra) return {};
    const titulo = c.barra.titulo.map(x => iconoDeTitulo(x, 'data-contestar="tarea"')).join('');
    const iconos = c.barra.iconos.map(x => accionDePantalla({ accion: 'tarea', valor: String(x.k), icono: x.icono, tono: x.tono, ayuda: x.ayuda }, 'contestar')).join('');
    const espera = s.haciendo ? ' haciendo' : '';
    return {
        ...titulo ? { iconos: `<span class="contestar-iconos${espera}">${titulo}</span>` } : {},
        ...iconos ? { herramientas: `<span class="contestar-barra${espera}">${iconos}${s.haciendo ? `<span class="contestar-haciendo">${circulo({ mov: 'gira' })}</span>` : ''}</span>` } : {},
    };
}

/** Las props de la ventana (`ventana()`), en un estado. */
export function propsContestar(c: Contestable, s: EstadoContestar = estadoInicial(c)): PropsVentana {
    return { lugar: 'centrada', titulo: c.titulo, ayuda: c.ayuda, ...barraHtml(c, s), cuerpo: cuerpo(c, s), pie: pie(c, s),
        clase: `contestar contestar-${c.clase}${c.ficha ? ' con-ficha' : ''}${s.enviando ? ' enviando' : ''}` };
}

/** La ventana entera, en un estado: lo que va dentro del `<dialog>`. */
export const ventanaContestar = (c: Contestable, s: EstadoContestar = estadoInicial(c)): string => ventana(propsContestar(c, s));

/** Lo que se manda, de lo elegido: por bloque, las opciones elegidas y lo escrito (lo escrito gana en una de una sola). */
export function eleccion(c: Contestable, s: EstadoContestar): { opciones: string[]; texto: string }[] {
    return c.bloques.map((b, i) => {
        const escrito = (s.otras[i] ?? '').trim();
        const elegidas = s.elegidas[i] ?? [];
        return b.varias ? { opciones: elegidas, texto: escrito } : escrito ? { opciones: [], texto: escrito } : { opciones: elegidas.slice(0, 1), texto: '' };
    });
}
