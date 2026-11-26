// Táctica: la vista de partida, la que contesta «¿qué hago ahora?» (docs/propuestas/orden-por-modos.md, paso 3). Se ve
// en el catálogo (/componentes#tactica) con datos inventados, y en la página como la pestaña «táctica» con lo de
// verdad. Absorbe «ahora», el foco de tareas y «te esperan»:
//
//   TÁCTICA  12 por decidir                                             ≡ ↻   ← el único número de la página
//   AHORA                                                                      el bloque en curso: una reunión con su
//   ● Revisión de diseño                                        quedan 45min    ficha, un bloque del plan con su paso,
//     se decide: la paleta del sitio · preparación · 4 personas                 o lo libre y lo que cabe en ello
//   EN VIVO                                    │ HACER · 2 te piden       4  ← un hilo detenido en su turno
//     pregunta ¿Qué foto va en la vitrina?     │ Colegio del Valle · 1          a la derecha, Hacer: primero lo que un
//   DECIDIR · 2                            1   │ ● rápida Firmar la cotización   agente pide que hagas (destraba a alguien),
//   Colegio del Valle · 1                      │ hoy · hasta 3                   por cuenta y por peso; después lo de hoy
//   ● ¿Aceptamos el 12% o un 8%?  el colegio…  │ ▢ 15:00 Comité · prepararla     (la reunión si hay algo que preparar, el
//     ○ el 12%  ● un 8% recomendada            │   rápida Mandar el pedido       plan, lo que vence), con su tamaño
//   APROBAR · 1                            2   │                              ← a la izquierda, lo que un agente espera de
//   Feria del Libro · 1                        │                                la persona en tres vías (VIAS, cada una con
//   ● el stand doble ($2,4M)      vence el jue │                                su tecla: la recorre en «Contestar»), por
//     ▤ presupuesto.md · enviar · editar · descartar                            cuenta y por peso: decidir, con sus
//   CERRAR · 2                             3   │                                opciones; aprobar, con lo que dejó hecho;
//   SIN CLASIFICAR · 3                         │                                cerrar, con su prueba. Lo que el agente no
//   CONTESTADAS · 2 esperando   pasada 15:00   │                                dijo qué pide, sin clasificar, al final; y
//   ○ El boletín · el lunes 1         11:20 ▷  │                                lo que contestaste y espera al agente (sale
//   ◐ Papel de regalo  encargada 11:42 ▷       │                                de cada tarea), con «revisar ya» (▷)
//   todo lo demás: 2 mensajes entre hilos retenidos · 54 tareas · ver todo
//
// El orden de las vías y de Hacer lo da la urgencia (vistas/dashboard/urgencia.ts), y cada fila dice por qué está donde
// está («espera el colegio», «vence el vie», «venció el 14-nov»): el componente no ordena, solo pone los topes. El color de
// ese porqué lo dicen solo una fecha dura y una persona que espera hoy. Cada fila dice lo que hay que decidir, no el título
// de la tarea (ese va en el globo); su peso, si el agente lo declaró, es el círculo de su primera ranura (alto lleno, medio
// a medias, bajo un aro). Lo que no cabe en un tope queda en «+N más»; el pie lleva a todo lo demás.
//
// Tres disposiciones para elegir (DISPOSICIONES): en columna; con las vías y Hacer lado a lado donde caben; y con Ahora en
// una franja de una línea. Lo que se ve es de los componentes de siempre: el ítem (cada fila; la cabecera de una cuenta,
// un submenú), la tarjeta (la ficha de ahora), las señales (los círculos), y la barra de la pantalla; lo que va bajo una
// fila (las opciones, lo que dejó hecho, la prueba), una línea propia (`tac-detalle`). Da HTML; los
// clics llevan `data-accion` (`tactica-…`) y `data-valor`, como las filas del dashboard (las de fábrica, `tactica-…`, las
// atiende quien la usa; una fila puede traer las suyas: la de una tarea, las de su fila de siempre). Cómo se ve:
// media/css/tactica.css. En la página la dibuja vistas/dashboard/tactica.ts, con lo que espera de verdad, el día y el plan.

import { esc } from '../estilo';
import { I } from '../web/iconos';
import { circulo } from './circulo';
import { item, type Accion, type Pieza, type Tono } from './item';
import type { Barra } from './pantalla';
import { tarjeta } from './tarjeta';

/** Cómo se reparten los tres bloques. */
export type Disposicion = 'columna' | 'lado' | 'franja';
export const DISPOSICIONES: readonly { clave: Disposicion; nombre: string; que: string }[] = [
    { clave: 'columna', nombre: 'en columna', que: 'Ahora, las vías y Hacer uno debajo del otro, en todos los anchos' },
    { clave: 'lado', nombre: 'lado a lado', que: 'Ahora arriba, de borde a borde, con su ficha; las vías y Hacer lado a lado donde caben (en el teléfono, en columna)' },
    { clave: 'franja', nombre: 'Ahora en una franja', que: 'Ahora en una sola línea: qué es, lo que se decide o lo que cabe, y cuánto queda (la ficha se abre con un clic); las vías y Hacer lado a lado donde caben' },
];

/** Cuántas cuentas se ven en cada vía y cuántas filas en Hacer; lo demás, en «+N más». */
export const TOPE_DECIDIR = 3;
export const TOPE_HACER = 3;

/** Las vías de lo que espera a la persona, en su orden: qué le pide cada una y su tecla (recorrerla en «Contestar»). La
 *  clave es el valor de `pide=` que declara el agente (urgencia.ts, CAMPOS). Lo que pide hacer (`hacer-tu`) no es una vía:
 *  va primero en Hacer, con la suya (VIA_HACER). */
export type Via = 'decidir' | 'aprobar' | 'cerrar' | 'hacer-tu';
export const VIAS: readonly { clave: Via; nombre: string; tecla: string; que: string }[] = [
    { clave: 'decidir', nombre: 'decidir', tecla: '1', que: 'elegir entre opciones' },
    { clave: 'aprobar', nombre: 'aprobar', tecla: '2', que: 'lo que el agente dejó hecho: enviarlo, editarlo o descartarlo' },
    { clave: 'cerrar', nombre: 'cerrar', tecla: '3', que: 'lo que ya pasó: confirmarlo con su prueba' },
];
/** Lo que un agente pide que haga la persona (un pago, una firma, una llamada, estar): primero en Hacer, con su tecla. */
export const VIA_HACER = { clave: 'hacer-tu', nombre: 'hacer', tecla: '4', que: 'lo que solo tú puedes, y lo de hoy' } as const;
/** Lo que el agente no dijo qué pide: va aparte, al final, sin adivinar. */
export const SIN_CLASIFICAR = 'sin-clasificar';

/** Una vía armada: sus cuentas, ya en su orden. */
export interface Carril { clave: Via | typeof SIN_CLASIFICAR; cuentas: Cuenta[] }

/** Por qué una fila está donde está (lo da la urgencia: `porque`, vistas/dashboard/urgencia.ts): va al final de la fila. */
export interface Porque { texto: string; tono?: Tono }

/** Algo que un agente espera de la persona: una espera de `telar esperas`. */
export interface Decision {
    /** su dirección (`pregunta:…`, `tarea:T12`, `permiso:Hilo`): lo que abre «Contestar» */
    id: string;
    /** de un hilo detenido, su clase (permiso, pregunta) y su color; en una vía no va: la vía ya lo dice */
    palabra?: string;
    tono?: Tono;
    /** lo que hay que decidir: la pregunta o la propuesta del agente (no el título de la tarea: ese, en `ayuda`); de un
     *  cierre, la tarea */
    titulo: string;
    /** de otra máquina */
    maquina?: string;
    /** cuánto pesa, si el agente lo declaró, y por qué */
    peso?: { nivel: 'alto' | 'medio' | 'bajo'; porque?: string };
    porque?: Porque;
    /** cuánto lleva esperando (de un hilo detenido): «4m» */
    edad?: string;
    /** lo que dice al pasar el mouse: el título, el peso, lo que dejó el agente */
    ayuda?: string;
    /** decidir: las opciones cerradas, si vienen (una pregunta del módulo), con la recomendada */
    opciones?: { id: string; texto: string; recomendada?: boolean }[];
    /** aprobar: lo que dejó hecho (un archivo, un enlace) y dónde se abre */
    artefacto?: { nombre: string; direccion: string };
    /** lo que pide hacer: cuánto toma (el tamaño de su tarea) */
    tamano?: '' | 'rapida' | 'larga';
    /** cerrar: cómo se cierra (hecha, caduca, descartada) y su prueba (lo que dice el agente) */
    como?: string;
    prueba?: string;
    /** de una tarea: lo de su fila de siempre al pasar el mouse (otra fecha), antes de «abrirla donde vive» */
    acciones?: Accion[];
}

/** Una tarea que contestaste y que espera al agente (`telar esperas`, `contestadas`: sale de su historia, así que
 *  sobrevive a recargar): lo que contestaste y cuándo, y si se la encargaste ya («hazte cargo ya» en «Contestar», o
 *  «revisar ya» aquí). Cuando el agente pasa por ella, sale sola. */
export interface Contestada {
    /** su dirección (`tarea:T512`) */
    id: string;
    /** el de la tarea */
    titulo: string;
    /** lo que contestaste, corto (entero, en el globo) */
    respuesta: string;
    /** cuándo: «18:27», «ayer 18:27», «14-nov» */
    cuando: string;
    /** se le avisó al agente que la atendiera ya: a qué hora (y ya no se le encarga de nuevo) */
    encargada?: string;
    /** «revisar ya» en camino */
    encargando?: boolean;
    /** «revisar ya» no salió: por qué (se puede volver a apretar) */
    fallo?: string;
    /** lo que dice al pasar el mouse: la tarea y lo contestado, enteros */
    ayuda?: string;
}

/** Cuándo pasa el agente por lo contestado (el periódico que lo revisa): lo que dice la cabecera de las contestadas, con
 *  su color si importa (pasando ahora; pausada o sin pasada, un cuidado) y lo demás en su globo. */
export interface Pasada { texto: string; tono?: Tono; ayuda: string }

/** Las decisiones de una cuenta (un cliente o un proyecto), ya en su orden: la primera se ve, las demás al desplegar. La
 *  clave vacía es «sin cuenta». */
export interface Cuenta { clave: string; nombre: string; decisiones: Decision[] }

/** Lo que hace un clic en una fila: su acción y su valor (`data-accion`, `data-valor`). */
export interface Clic { accion: string; valor?: string }

/** Algo que hacer hoy: una reunión o un bloque del plan (con su hora), o una tarea. */
export interface Quehacer {
    tipo: 'reunion' | 'bloque' | 'tarea';
    /** su dirección (`tarea:T40`) o el id del evento */
    id: string;
    titulo: string;
    /** de una reunión o un bloque: cuándo empieza, «15:00» */
    hora?: string;
    /** su proyecto, corto */
    donde?: string;
    /** de una tarea: cuánto toma */
    tamano?: '' | 'rapida' | 'larga';
    /** lo que pide antes, en pocas letras (va al final de la fila): «prepararla», «el foco del día» */
    nota?: string;
    porque?: Porque;
    /** lo que dice al pasar el mouse (si no, el título y la nota) */
    ayuda?: string;
    /** lo que hace un clic en ella, si no es lo de fábrica (`tactica-tarea`, `tactica-evento` con su id) */
    clic?: Clic;
    /** las de su fila de siempre (una tarea: la instrucción, hecha) y su ⋯; sin ellas, «hecha» de fábrica */
    acciones?: Accion[];
    menu?: Accion;
}

/** El bloque en curso. */
export interface Ahora {
    /** en una reunión, en un bloque del plan, libre hasta la próxima reunión, o libre el resto del día */
    tipo: 'reunion' | 'bloque' | 'libre' | 'fin';
    /** la reunión o el bloque */
    titulo?: string;
    /** «11:30–12:30» */
    cuando?: string;
    /** cuánto queda, en minutos: de la reunión, del bloque, o lo libre */
    queda: number;
    /** lo que viene: «15:00 Comité» */
    luego?: string;
    /** su ficha: lo que se decide en la reunión, el paso del bloque */
    que?: string;
    /** sus datos (en el pie de la ficha): la preparación, la minuta anterior, el proyecto, cuántas personas */
    datos?: Pieza[];
    /** lo que se le hace: entrar, ver la preparación */
    acciones?: Accion[];
    /** lo que hace un clic en la ficha (de fábrica, `tactica-ahora`) */
    clic?: Clic;
    /** en lo libre: lo que cabe, ya dicho (`queCabe`) */
    caben?: string;
}

/** Todo lo demás, que no es de ahora: cada fuente con su cuenta (o lo que dice de sí: «3 chats sin leer»), y lleva a
 *  Todo (o a su pestaña: `clic`). Sin cuenta ni texto, va su nombre. */
export interface Resto { clave: string; nombre: string; cuenta?: number; texto?: string; clic?: Clic }

export interface Tactica {
    ahora: Ahora;
    /** lo que espera de la persona, en sus vías (VIAS, y al final lo sin clasificar), cada una por cuenta y ya en su orden */
    vias: Carril[];
    /** lo que un agente pide que haga la persona, por cuenta y en su orden: primero en Hacer */
    hacerTu?: Cuenta[];
    /** los hilos detenidos en su turno (un permiso, una pregunta en vivo): arriba de las vías */
    vivo?: Decision[];
    /** las cuentas desplegadas (`<vía>|<cuenta>`) */
    abiertas?: readonly string[];
    /** lo que contestaste y espera al agente, lo más reciente primero; cuándo pasa; y quién es (para los globos) */
    contestadas?: Contestada[];
    pasada?: Pasada;
    agente?: string;
    /** lo de hoy, ya en su orden */
    hacer: Quehacer[];
    /** el día no tiene plan: Hacer es solo lo que vence hoy y las reuniones */
    sinPlan?: boolean;
    resto: Resto[];
    disposicion?: Disposicion;
    /** con Ahora en una franja: la franja abierta, con la ficha */
    abierta?: boolean;
}

/** Cuánto toma decidir una espera, en minutos (para decir qué cabe en lo libre). */
export const MIN_POR_DECISION = 2;
/** Cuánto toma una tarea rápida: media hora o menos. */
export const MIN_RAPIDA = 30;

/** Cuántas decisiones tiene una vía (o unas cuentas). */
export const cuantas = (cuentas: readonly Cuenta[]): number => cuentas.reduce((n, c) => n + c.decisiones.length, 0);

/** Cuántas cosas esperan a la persona: el único número de la página. Todas las de todas las vías, y los hilos detenidos. */
export const porDecidir = (vias: readonly Carril[], vivo: readonly Decision[] = []): number =>
    vias.reduce((n, v) => n + cuantas(v.cuentas), vivo.length);

/** «45min», «1h», «1h 20». */
export function minutos(m: number): string {
    const n = Math.max(1, Math.round(m));
    if (n < 60) return `${n}min`;
    const h = Math.floor(n / 60), r = n % 60;
    return r ? `${h}h ${String(r).padStart(2, '0')}` : `${h}h`;
}

/** Lo que cabe en un rato libre, dicho en una línea: primero decidir (lo que se pueda de las `n` que esperan, a
 *  MIN_POR_DECISION cada una) y, con lo que sobre, las tareas rápidas de Hacer, en su orden. Vacío si no cabe nada. */
export function queCabe(libre: number, n: number, hacer: readonly Quehacer[]): string {
    const cuantas = Math.min(n, Math.floor(libre / MIN_POR_DECISION));
    let sobra = libre - cuantas * MIN_POR_DECISION;
    const partes: string[] = [];
    if (cuantas) partes.push(`${cuantas === n ? (n === 1 ? 'la decisión' : `las ${n} decisiones`) : `${cuantas} de las ${n} decisiones`} (≈${minutos(cuantas * MIN_POR_DECISION)})`);
    for (const t of hacer) {
        if (t.tipo !== 'tarea' || t.tamano !== 'rapida' || sobra < MIN_RAPIDA) continue;
        partes.push(`«${t.titulo}» (rápida)`);
        sobra -= MIN_RAPIDA;
    }
    return partes.length > 1 ? `${partes.slice(0, -1).join(', ')} y ${partes[partes.length - 1]}` : partes[0] ?? '';
}

// ───────────────────────── el dibujo ─────────────────────────

/** La cabecera de un bloque: su nombre y, a la derecha, su tope. */
const cabecera = (nombre: string, tope = ''): string =>
    `<div class="tac-cab"><span class="tac-nombre">${esc(nombre)}</span>${tope ? `<span class="tac-tope">${esc(tope)}</span>` : ''}</div>`;

/** Lo que va al final de una fila: por qué está ahí (en su tono, si lo tiene: una fecha dura, una persona que espera
 *  hoy; si no, el de siempre), y (si un hilo espera) hace cuánto. */
function meta(p?: Porque, edad = ''): Pieza | undefined {
    if (!p) return edad ? { texto: edad } : undefined;
    const porque = `<span class="tac-porque${p.tono ? ` tono-${p.tono}` : ''}">${esc(p.texto)}</span>`;
    return { html: edad && p.tono === 'espera' ? `${porque}<span class="tac-edad"> · ${esc(edad)}</span>` : porque };
}

/** El llenado del círculo de un peso: alto lleno, medio a medias, bajo un aro (como la prioridad: cuánto importa). */
export const LLENO_PESO = { alto: 1, medio: .5, bajo: 0 } as const;

/** El peso de una decisión, en su ranura: un círculo chico en el color del texto (el color es para la urgencia); sin
 *  peso declarado, nada. */
export function piezaPeso(p: Decision['peso']): Pieza | null {
    return p ? { circulo: { tam: 'chico', lleno: LLENO_PESO[p.nivel] }, ayuda: `peso ${p.nivel}${p.porque ? `: ${p.porque}` : ''}` } : null;
}

/** Lo que va bajo una fila de una vía, en una línea: de decidir, sus opciones (la recomendada marcada; un clic la abre
 *  en «Contestar»); de aprobar, lo que dejó hecho y enviar, editar o descartar; de cerrar, su prueba y confirmarlo. */
function detalle(d: Decision, via: Carril['clave']): string {
    const enlace = (accion: string, valor: string, html: string, ayuda: string, clase = '') =>
        `<a class="tac-accion${clase ? ` ${clase}` : ''}" data-accion="${esc(accion)}" data-valor="${esc(valor)}" title="${esc(ayuda)}">${html}</a>`;
    if (via === 'decidir' && d.opciones?.length) {
        return `<div class="tac-detalle tac-opciones">${d.opciones.map(o => enlace('tactica-opcion', JSON.stringify([d.id, o.id]),
            `${circulo({ tam: 'chico', lleno: o.recomendada ? 1 : 0 })} ${esc(o.texto)}${o.recomendada ? ' <span class="tac-reco">recomendada</span>' : ''}`,
            `elegir «${o.texto}»${o.recomendada ? ' (la recomienda el agente)' : ''}`, o.recomendada ? 'recomendada' : '')).join('')}</div>`;
    }
    if (via === 'aprobar') {
        const hecho = d.artefacto ? enlace('tactica-ver', d.artefacto.direccion, `<span class="i">${I.documento}</span> ${esc(d.artefacto.nombre)}`,
            `abrir lo que dejó hecho: ${d.artefacto.direccion}`, 'tac-artefacto') : '';
        const que = ([['enviar', 'aprobarlo: el agente lo manda'], ['editar', 'cambiarlo antes: dile qué'], ['descartar', 'no va: el agente lo deja']] as const)
            .map(([k, ayuda]) => enlace('tactica-aprobar', JSON.stringify([d.id, k]), k, ayuda, `tac-${k}`)).join('');
        return `<div class="tac-detalle tac-aprobar">${hecho}${que}</div>`;
    }
    if (via === 'cerrar') {
        return `<div class="tac-detalle tac-cerrar">${d.prueba ? `<span class="tac-prueba" title="${esc(d.prueba)}">${esc(d.prueba)}</span>` : ''}`
            + `${enlace('tactica-cerrar', d.id, 'confirmar', `cerrarla${d.como ? ` como ${d.como}` : ''}`, 'tac-confirmar')}</div>`;
    }
    return '';
}

/** Una fila de lo que espera: su peso (si lo tiene), lo que hay que decidir y por qué está ahí; delante, de un hilo
 *  detenido su clase, de lo que pide hacer el tamaño y de cerrar cómo; y debajo, lo de su vía (`detalle`). Un clic abre
 *  «Contestar». */
export function filaDecision(d: Decision, via: Carril['clave'] | 'vivo' = 'vivo'): string {
    const prefijo: Pieza[] = d.palabra ? [{ texto: d.palabra, tono: d.tono }]
        : via === 'hacer-tu' && d.tamano ? [{ texto: d.tamano === 'rapida' ? 'rápida' : 'larga', tono: 'tenue' }]
            : via === 'cerrar' && d.como ? [{ texto: d.como, tono: 'tenue' }] : [];
    return item({
        accion: 'tactica-contestar', datos: { valor: d.id }, clases: ['tac-decision'],
        ayuda: `${d.ayuda ?? d.titulo}\n\nclic: contestar`,
        inicio: [piezaPeso(d.peso), d.maquina ? { circulo: { figura: 'satelite' }, tono: 'remoto', ayuda: `en ${d.maquina}` } : null],
        prefijo,
        titulo: d.titulo,
        meta: meta(d.porque, d.edad),
        acciones: [...d.acciones ?? [], { accion: 'tactica-ver', datos: { valor: d.id }, icono: I.ver, ayuda: 'abrirla donde vive' }],
    }) + (via === 'vivo' ? '' : detalle(d, via));
}

/** La cabecera de una cuenta, un submenú: su nombre y cuántas tiene. Con más de una, la flecha (un clic la despliega o la
 *  pliega) y, al pasar el mouse, contestarlas una tras otra; con una, un clic la contesta. `via`: de qué vía es (sus
 *  claves de desplegar y de contestar son `<vía>|<cuenta>`). */
export function filaCuenta(c: Cuenta, abierta = false, via = ''): string {
    const n = c.decisiones.length;
    const varias = n > 1;
    const clave = `${via}|${c.clave}`;
    return item({
        variante: 'submenu', clases: ['tac-cuenta', ...c.clave ? [] : ['sin-cuenta']],
        accion: varias ? 'tactica-cuenta' : 'tactica-contestar', datos: { valor: varias ? clave : c.decisiones[0]?.id ?? '' },
        ayuda: varias ? `${c.nombre}: ${n}\n\nclic: ${abierta ? 'plegarla' : 'ver todas'}` : `${c.nombre}\n\nclic: contestar`,
        inicio: [varias ? { icono: abierta ? I.abierto : I.plegado, tono: 'tenue' } : null],
        titulo: c.nombre,
        sufijo: [{ texto: `· ${n}`, tono: 'tenue' }],
        acciones: varias ? [{ accion: 'tactica-contestar', datos: { valor: `cuenta:${clave}` }, icono: I.adelante, ayuda: `contestar las ${n}, una tras otra` }] : [],
    });
}

/** Cuántas contestadas se ven; las demás, al desplegar («+N más»). */
export const TOPE_CONTESTADAS = 5;
/** La clave con que se despliegan las contestadas (como una cuenta: `tactica-cuenta`). */
export const CONTESTADAS = 'contestadas';

/** Una contestada: su estado (un aro violeta: le toca al agente; girando, encargándosela; a medias, encargada; un aro
 *  rojo, no salió), la tarea, lo que contestaste y cuándo (o desde cuándo la tiene el agente). Al final, «revisar ya»:
 *  encargársela ahora al agente que escribe los avances, sin esperar la pasada; encargada (o en camino), apagado y no
 *  la encarga dos veces seguidas. Un clic en la fila la abre donde vive. */
export function filaContestada(c: Contestada, agente = ''): string {
    const quien = agente || 'el agente';
    const puede = !c.encargada && !c.encargando;
    const estado: Pieza = c.encargando ? { circulo: { mov: 'gira' }, tono: 'agente', ayuda: `encargándosela a ${quien}` }
        : c.fallo ? { circulo: { lleno: 0 }, tono: 'peligro', ayuda: `«revisar ya» no salió: ${c.fallo}` }
            : c.encargada ? { circulo: { lleno: .5 }, tono: 'agente', ayuda: `encargada a las ${c.encargada}: ${quien} la tiene` }
                : { circulo: { lleno: 0 }, tono: 'agente', ayuda: 'contestada: le toca al agente' };
    const meta: Pieza = c.encargando ? { texto: 'encargando', tono: 'tenue' }
        : c.fallo ? { texto: 'no salió', tono: 'peligro', ayuda: c.fallo }
            : c.encargada ? { texto: `encargada ${c.encargada}`, tono: 'agente', ayuda: `se la encargaste a ${quien} a las ${c.encargada}` }
                : { texto: c.cuando, ayuda: `la contestaste: ${c.cuando}` };
    return item({
        accion: 'tactica-ver', datos: { valor: c.id }, clases: ['tac-contestada'],
        ayuda: `${c.ayuda ?? `${c.titulo}\n\ncontestaste (${c.cuando}): ${c.respuesta}`}\n\nclic: abrirla`,
        inicio: [estado, null],
        titulo: c.titulo,
        sufijo: c.respuesta ? [{ texto: `· ${c.respuesta}`, tono: 'tenue' }] : [],
        meta,
        fijas: [{ accion: 'tactica-revisar', datos: { valor: c.id }, icono: I.instruccion, tono: puede ? 'agente' : 'tenue',
            ayuda: puede ? `revisar ya: encargársela a ${quien} ahora, sin esperar la próxima pasada${c.fallo ? ' (otra vez: la anterior no salió)' : ''}`
                : c.encargando ? 'encargándosela…' : `ya se la encargaste a las ${c.encargada}: no se encarga dos veces seguidas` }],
    });
}

/** Lo que contestaste y espera al agente: su cabecera (cuántas y, a la derecha, cuándo pasa), y hasta el tope (las
 *  demás, al desplegar). Sin contestadas, nada. */
function contestadas(t: Tactica, abiertas: ReadonlySet<string>): string {
    const cs = t.contestadas ?? [];
    if (!cs.length) return '';
    const abierta = abiertas.has(CONTESTADAS);
    const vistas = abierta ? cs : cs.slice(0, TOPE_CONTESTADAS);
    const p = t.pasada;
    const cab = `<div class="tac-cab tac-contestadas-cab" title="${esc('lo que contestaste y todavía no revisa el agente: sale de cada tarea cuando pasa por ella')}">`
        + `<span class="tac-nombre">contestadas</span><span class="tac-cuantas">· ${cs.length} esperando al agente</span>`
        + `${p ? `<span class="tac-tope tac-pasada${p.tono ? ` tono-${p.tono}` : ''}" title="${esc(p.ayuda)}">${esc(p.texto)}</span>` : ''}</div>`;
    const resto = cs.length - TOPE_CONTESTADAS;
    const pie = resto > 0 ? item({ accion: 'tactica-cuenta', datos: { valor: CONTESTADAS }, clases: ['tac-mas'], inicio: [null],
        titulo: abierta ? 'menos' : `+${resto} más`, ayuda: abierta ? `ver solo las ${TOPE_CONTESTADAS} más recientes` : 'verlas todas' }) : '';
    return `<section class="tac-bloque tac-contestadas">${cab}${vistas.map(c => filaContestada(c, t.agente)).join('')}${pie}</section>`;
}

/** Lo que es un quehacer, en su ranura: una reunión (con otras personas, en el azul de las reuniones), un bloque del plan
 *  (lo propio) o una tarea (nada: es lo de siempre). */
const RANURA: Record<Quehacer['tipo'], Pieza | null> = {
    reunion: { icono: I.persona, tono: 'acento', ayuda: 'una reunión' },
    bloque: { icono: I.foco, tono: 'agente', ayuda: 'un bloque del plan' },
    tarea: null,
};

/** Una fila de Hacer: qué es, su hora si la tiene, el título, lo que pide antes, y por qué está ahí. */
export function filaQuehacer(q: Quehacer): string {
    return item({
        accion: q.clic?.accion ?? (q.tipo === 'tarea' ? 'tactica-tarea' : 'tactica-evento'), datos: { valor: q.clic ? q.clic.valor ?? '' : q.id },
        clases: ['tac-quehacer'],
        ayuda: q.ayuda ?? `${q.titulo}${q.nota ? `\n${q.nota}` : ''}`,
        inicio: [RANURA[q.tipo]],
        // la hora de una reunión o un bloque; el tamaño de una tarea, delante: se ve aunque el título se corte
        prefijo: q.hora ? [{ texto: q.hora, tono: 'acento' }] : q.tamano ? [{ texto: q.tamano === 'rapida' ? 'rápida' : 'larga', tono: 'tenue' }] : [],
        titulo: q.titulo,
        sufijo: q.donde ? [{ texto: `· ${q.donde}`, tono: 'tenue' }] : [],
        meta: q.nota && !q.porque ? { texto: q.nota, tono: 'atencion' } : meta(q.porque),
        acciones: q.acciones ?? (q.tipo === 'tarea' ? [{ accion: 'tactica-hecha', datos: { valor: q.id }, icono: I.hecha, tono: 'exito', ayuda: 'hecha' }] : []),
        menu: q.menu,
    });
}

/** «+N más»: lo que no cabe en el tope, que lleva a Todo con ese bloque. */
const mas = (n: number, de: string, que: string, cuantos = `+${n} más`): string => (n > 0
    ? item({ accion: 'tactica-todo', datos: { valor: de }, clases: ['tac-mas'], inicio: [null], titulo: cuantos, sufijo: [{ texto: que, tono: 'tenue' }],
        ayuda: `verlas todas, en Todo (sin tope)` })
    : '');

/** Una fila que dice que no hay nada. */
const nada = (texto: string): string => item({ clases: ['tac-nada'], inicio: [null], titulo: texto, apagada: true });

/** Una vía: su cabecera (su nombre, cuántas, y su tecla: un clic o la tecla la recorren en «Contestar»), y sus cuentas
 *  hasta el tope, cada una con su cabecera y su primera (o todas, desplegada); las demás cuentas, en «+N más». Vacía, solo
 *  su cabecera. Lo sin clasificar, sin tecla. */
function carril(c: Carril, abiertas: ReadonlySet<string>): string {
    const v = VIAS.find(x => x.clave === c.clave);
    const n = cuantas(c.cuentas);
    const nombre = v?.nombre ?? 'sin clasificar';
    const que = v?.que ?? 'el agente no dijo qué pide: falta que lo declare';
    const cab = `<div class="tac-cab tac-via-cab"${n ? ` data-accion="tactica-via" data-valor="${esc(c.clave)}"` : ''} title="${esc(`${nombre}: ${que}${n ? '\n\nclic: recorrerlas en «Contestar»' : ''}`)}">`
        + `<span class="tac-nombre">${esc(nombre)}</span><span class="tac-cuantas">${n ? `· ${n}` : '· nada'}</span>`
        + `${v ? `<span class="tac-tope tac-tecla">${esc(v.tecla)}</span>` : ''}</div>`;
    return `<section class="tac-bloque tac-via tac-via-${esc(c.clave)}${n ? '' : ' vacia'}">${cab}${cuentasDe(c.clave, c.cuentas, abiertas)}</section>`;
}

/** Lo que espera a la persona: los hilos detenidos (en vivo), las tres vías y lo sin clasificar; y al final, lo que
 *  contestaste y espera al agente. */
function vias(t: Tactica): string {
    const abiertas = new Set(t.abiertas ?? []);
    const vivo = t.vivo?.length ? `<section class="tac-bloque tac-vivo">${cabecera('en vivo', 'un hilo espera en su turno')}${t.vivo.map(d => filaDecision(d)).join('')}</section>` : '';
    const carriles = t.vias.filter(c => c.clave !== SIN_CLASIFICAR || cuantas(c.cuentas)).map(c => carril(c, abiertas));
    const nadaHay = !t.vivo?.length && !porDecidir(t.vias);
    return `<div class="tac-vias">${vivo}${nadaHay ? `<section class="tac-bloque tac-via">${cabecera('decidir')}${nada('nada por decidir')}</section>` : carriles.join('')}`
        + `${contestadas(t, abiertas)}</div>`;
}

/** Las cuentas de una vía hasta el tope, cada una con su cabecera y su primera (o todas, desplegada), y las demás en
 *  «+N cuentas más». */
function cuentasDe(via: Carril['clave'], cuentas: readonly Cuenta[], abiertas: ReadonlySet<string>): string {
    const vistas = cuentas.slice(0, TOPE_DECIDIR).map(cu => {
        const abierta = abiertas.has(`${via}|${cu.clave}`);
        return `<div class="tac-grupo">${filaCuenta(cu, abierta, via)}${(abierta ? cu.decisiones : cu.decisiones.slice(0, 1)).map(d => filaDecision(d, via)).join('')}</div>`;
    });
    const resto = cuentas.length - vistas.length;
    return vistas.join('') + mas(resto, 'decidir', 'en «te esperan»', `+${resto} ${resto === 1 ? 'cuenta' : 'cuentas'} más`);
}

/** Hacer: primero lo que un agente pide que haga la persona (destraba a alguien), por cuenta y por peso, con su tecla
 *  (la recorre en «Contestar»); después lo de hoy (la reunión si hay algo que preparar, el bloque del plan, las tareas),
 *  hasta el tope y con su tamaño delante; sin plan, lo dice. */
function hacer(t: Tactica): string {
    const tu = t.hacerTu ?? [];
    const n = cuantas(tu);
    const cab = n
        ? `<div class="tac-cab tac-via-cab" data-accion="tactica-via" data-valor="${VIA_HACER.clave}" title="${esc(`lo que un agente pide que hagas: ${n}\n\nclic: recorrerlo en «Contestar»`)}">`
            + `<span class="tac-nombre">${esc(VIA_HACER.nombre)}</span><span class="tac-cuantas">· ${n} te piden</span><span class="tac-tope tac-tecla">${VIA_HACER.tecla}</span></div>`
        : cabecera('hacer', `hasta ${TOPE_HACER}`);
    const filas = t.hacer.slice(0, TOPE_HACER).map(filaQuehacer);
    const resto = t.hacer.length - filas.length;
    const sinPlan = t.sinPlan ? item({ clases: ['tac-sin-plan'], inicio: [{ icono: I.plan, tono: 'tenue' }],
        titulo: 'sin plan de hoy', sufijo: [{ texto: '· solo lo que vence hoy y las reuniones', tono: 'tenue' }],
        ayuda: 'el día no tiene plan: lo arma la skill de planificación, cada noche' }) : '';
    // lo de hoy, bajo lo que te piden: con su propia cabecera de grupo, para que no parezca de la última cuenta
    const hoy = n && filas.length ? item({ variante: 'submenu', clases: ['tac-cuenta', 'tac-hoy'], inicio: [null], titulo: 'hoy',
        sufijo: [{ texto: `· hasta ${TOPE_HACER}`, tono: 'tenue' }] }) : '';
    return `<section class="tac-bloque tac-hacer">${cab}${n ? cuentasDe(VIA_HACER.clave, tu, new Set(t.abiertas ?? [])) : ''}`
        + `${hoy}${filas.length ? filas.join('') : n ? '' : nada('nada para hoy')}${mas(resto, 'hacer', 'en Todo')}${sinPlan}</section>`;
}

/** Lo que dice la línea de ahora (la franja, y el título de la ficha). */
function lineaAhora(a: Ahora): { prefijo: string; titulo: string; meta: string } {
    if (a.tipo === 'reunion' || a.tipo === 'bloque') return { prefijo: a.tipo === 'reunion' ? 'en' : 'bloque', titulo: a.titulo ?? '', meta: `quedan ${minutos(a.queda)}` };
    if (a.tipo === 'fin') return { prefijo: 'libre', titulo: 'el resto del día', meta: minutos(a.queda) };
    return { prefijo: 'libre', titulo: `${minutos(a.queda)}${a.luego ? ` → ${a.luego}` : ''}`, meta: '' };
}

/** El círculo de ahora: lleno en una reunión o un bloque (algo pasa), en su color; lo libre, un aro verde (por usar). */
const circuloAhora = (a: Ahora): Pieza => (a.tipo === 'reunion' ? { circulo: {}, tono: 'acento', ayuda: 'en una reunión' }
    : a.tipo === 'bloque' ? { circulo: {}, tono: 'agente', ayuda: 'en un bloque del plan' }
        : { circulo: { lleno: 0 }, tono: 'exito', ayuda: 'tiempo libre' });

/** La ficha de ahora, en una tarjeta: la reunión o el bloque con lo que se decide y sus datos; o lo libre y lo que cabe. */
function ficha(a: Ahora): string {
    const l = lineaAhora(a);
    const libre = a.tipo === 'libre' || a.tipo === 'fin';
    return tarjeta({
        accion: a.clic?.accion ?? 'tactica-ahora', datosHtml: { valor: a.clic ? a.clic.valor ?? '' : a.titulo ?? a.tipo }, clases: ['tac-ficha'],
        inicio: [circuloAhora(a)],
        prefijo: [{ texto: l.prefijo, tono: libre ? 'exito' : a.tipo === 'reunion' ? 'acento' : 'agente' }],
        titulo: l.titulo,
        acciones: a.acciones,
        cuerpoHtml: libre ? (a.caben ? `<span class="tono-exito">caben</span> ${esc(a.caben)}` : esc('no cabe nada de lo que espera'))
            : a.que ? esc(a.que) : '',
        datos: [...a.cuando ? [{ texto: a.cuando }] : [], ...a.datos ?? []],
        meta: libre ? undefined : { texto: l.meta, tono: 'acento' },
    });
}

/** Ahora en una franja: una línea con lo que la cabecera no dice (de una reunión, qué se decide; de lo libre, lo que
 *  cabe), y la ficha abajo si está abierta. */
function franja(a: Ahora, abierta: boolean): string {
    const l = lineaAhora(a);
    const libre = a.tipo === 'libre' || a.tipo === 'fin';
    const dice = libre ? (a.caben ? `caben ${a.caben}` : 'no cabe nada de lo que espera') : a.que ?? '';
    return item({
        accion: 'tactica-franja', datos: { valor: abierta ? 'cerrar' : 'abrir' }, clases: ['tac-franja'], ayuda: abierta ? 'cerrar la ficha' : 'abrir la ficha',
        inicio: [circuloAhora(a)],
        prefijo: [{ texto: l.prefijo, tono: libre ? 'exito' : a.tipo === 'reunion' ? 'acento' : 'agente' }],
        tituloHtml: `${esc(l.titulo)}${dice ? ` <span class="tac-dice">· ${esc(dice)}</span>` : ''}`,
        meta: libre ? undefined : { texto: l.meta, tono: 'acento' },
        fijas: [{ accion: 'tactica-franja', datos: { valor: abierta ? 'cerrar' : 'abrir' }, icono: abierta ? I.abierto : I.plegado, ayuda: abierta ? 'cerrar la ficha' : 'abrir la ficha' }],
    }) + (abierta ? ficha(a) : '');
}

/** El pie: todo lo demás, con su cuenta, y ver todo. */
function pie(resto: readonly Resto[]): string {
    const enlaces = resto.filter(r => r.cuenta === undefined || r.cuenta > 0).map(r =>
        `<a data-accion="${esc(r.clic?.accion ?? 'tactica-todo')}" data-valor="${esc(r.clic ? r.clic.valor ?? '' : r.clave)}">`
        + `${esc(r.texto ?? (r.cuenta === undefined ? r.nombre : `${r.cuenta} ${r.nombre}`))}</a>`);
    return `<div class="tac-pie"><span class="tac-pie-que">todo lo demás:</span> ${enlaces.join(' · ')}`
        + `${enlaces.length ? ' · ' : ''}<a class="tac-ver-todo" data-accion="tactica-todo" data-valor="" title="Todo: sin filtros ni topes, con un buscador">ver todo</a></div>`;
}

/** Táctica, en HTML: el cuerpo de su pantalla (la barra, `barraTactica`). */
export function tactica(t: Tactica): string {
    const d = t.disposicion ?? 'lado';
    const ahora = d === 'franja'
        ? `<section class="tac-bloque tac-ahora en-franja">${franja(t.ahora, !!t.abierta)}</section>`
        : `<section class="tac-bloque tac-ahora">${cabecera('ahora')}${ficha(t.ahora)}</section>`;
    return `<div class="tactica disp-${d}">${ahora}<div class="tac-par">${vias(t)}${hacer(t)}</div>${pie(t.resto)}</div>`;
}

/** La barra de su pantalla: su nombre y sus acciones. Cuántas decisiones esperan, en el globo del título: a la vista,
 *  cada vía dice las suyas. */
export function barraTactica(t: Tactica): Barra {
    const n = porDecidir(t.vias, t.vivo);
    return {
        nombre: 'táctica', color: 'amarillo',
        ayuda: n ? `${n} por decidir: lo de las tres vías, lo sin clasificar y los hilos detenidos` : 'nada por decidir',
        acciones: [{ accion: 'tactica-todo', valor: '', icono: I.lista, ayuda: 'ver todo: sin filtros ni topes' },
            { accion: 'tactica-releer', icono: I.releer, ayuda: 'volver a leer (r)' }],
    };
}
