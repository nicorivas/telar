// Lo que muestra el catálogo (/componentes): los estados del ítem, con sus props tal cual (para ver qué pieza pone
// cada cosa), y una barra de hilos de mentira con todo lo que puede tener, para ver la de verdad armada con ellos.
// Los nombres son inventados: nada de aquí sale de la configuración de nadie.

import type * as cli from '../cli';
import type { HiloDeFoto, PestanaDashboard } from '../vistas/hilos';
import { I } from '../web/iconos';
import * as S from './senales';
import * as A from './acciones';
import type { Accion, Item, Pieza } from './item';
import type { Tramo } from './jornada';

export interface Historia { grupo: string; nombre: string; nota?: string; props: Item }

const menu: Accion = { accion: 'menu', id: 'faro', icono: I.menu, ayuda: 'más: renombrar, vincular, prioridad, llevar…' };
const archivar: Accion = { accion: 'archivar', id: 'faro', icono: I.archivar, ayuda: 'archivar' };
const descartar: Accion = { accion: 'cerrar', id: 'faro', icono: I.descartar, peligro: true, ayuda: 'descartar' };
const retomar: Accion = { accion: 'retomar', id: 'faro', icono: I.retomar, ayuda: 'retomar' };
// la casa de un agente: una acción de las que aparecen al pasar el mouse (en el teléfono, en su ⋯)
const casa: Accion = { accion: 'home', id: 'archivista', icono: I.casa, ayuda: 'la casa de Archivista: bitácora, memoria, archivos' };
// lo que se ve siempre en la fila de un agente sin hilo: abrirlo
const abrirAgente: Accion = { accion: 'abrir-agente', id: 'cartero', icono: I.correr, ayuda: 'abrir su hilo' };

/** Un hilo como los de la barra: prioridad · atención · dónde vive, el nombre, hace cuánto, y sus acciones. */
function hilo(nombre: string, o: Partial<Item> & { p?: number; at?: 'trabajando' | 'espera' | 'termino' | 'visto' | ''; lugar?: Pieza | null } = {}): Item {
    const { p = 0, at = '', lugar = null, ...resto } = o;
    return {
        inicio: [resto.hondo ? null : S.prioridad(p), at === 'visto' ? S.atencion('termino', true) : at ? S.atencion(at) : null, lugar],
        titulo: nombre, meta: { texto: '12m' }, menu, acciones: [archivar, descartar], arrastrable: true,
        ...resto,
    };
}

export const HISTORIAS: Historia[] = [
    { grupo: 'anatomía', nombre: 'todas las piezas', nota: 'inicio: tres ranuras · texto: prefijo, título, sufijo · fin: aviso, meta, una fija y, al pasar el mouse, el ⋯ y dos acciones',
        props: hilo('faro', { p: 1, at: 'trabajando', lugar: S.remoto('vive en servidor'),
            prefijo: [{ texto: 'A', tono: 'agente', ayuda: 'de agente:archivista' }], sufijo: [S.publico('público')],
            aviso: S.nuevo('algo nuevo'), meta: { texto: '49m' }, fijas: [abrirAgente], clases: ['hover'] }) },
    { grupo: 'anatomía', nombre: 'solo el título', nota: 'sin inicio ni fin: el texto parte en el borde', props: { titulo: 'una fila sin nada más' } },

    { grupo: 'hilo', nombre: 'trabajando', props: hilo('faro', { p: 1, at: 'trabajando', meta: { texto: '3m' } }) },
    { grupo: 'hilo', nombre: 'te espera', props: hilo('molino', { p: 2, at: 'espera', meta: { texto: '1h' } }) },
    { grupo: 'hilo', nombre: 'terminó, sin ver', props: hilo('puente', { p: 3, at: 'termino', meta: { texto: '20m' } }) },
    { grupo: 'hilo', nombre: 'terminó, ya visto', props: hilo('huerto', { at: 'visto', meta: { texto: '2d' } }) },
    { grupo: 'hilo', nombre: 'sin atención', props: hilo('cuaderno') },
    { grupo: 'hilo', nombre: 'dormido', nota: 'su agente se cerró por estar quieto: un aro tenue; abrirlo lo despierta',
        props: hilo('cuaderno', { p: 2, inicio: [S.prioridad(2), S.dormido(false, 'duerme desde las 14:32: abrirlo lo despierta'), null], meta: { texto: '2h' } }) },
    { grupo: 'hilo', nombre: 'dormido, terminó sin ver', nota: 'lo que dejó se sigue diciendo: su diana, tenue',
        props: hilo('puente', { p: 3, inicio: [S.prioridad(3), S.dormido(true, 'terminó y no lo has visto · duerme'), null], meta: { texto: '1h' } }) },
    { grupo: 'hilo', nombre: 'activo', nota: 'el que se mira a la derecha', props: hilo('faro', { p: 1, at: 'trabajando', activa: true }) },
    { grupo: 'hilo', nombre: 'mouse encima', nota: 'el ⋯ y las acciones flotan sobre la meta, sin correrla', props: hilo('faro', { p: 1, at: 'trabajando', clases: ['hover'] }) },
    { grupo: 'hilo', nombre: 'activo y mouse encima', props: hilo('faro', { p: 1, at: 'trabajando', activa: true, clases: ['hover'] }) },
    { grupo: 'hilo', nombre: 'de otra máquina', props: hilo('cosecha', { at: 'espera', lugar: S.remoto('vive en servidor') }) },
    { grupo: 'hilo', nombre: 'con la máquina a la vista', nota: 'la ranura del lugar, ancha (⇄ junto a buscar)',
        props: hilo('cosecha', { at: 'espera', lugar: { texto: 'servidor', ancho: 8, tono: 'atencion', ayuda: 'vive en servidor' } }) },
    { grupo: 'hilo', nombre: 'inalcanzable', nota: 'su máquina está fuera de línea: el aro chico de «sin noticias», y la fila apagada; lo que dijo antes de irse va en la ayuda',
        props: hilo('catedral', { apagada: true, inicio: [S.prioridad(0), S.inalcanzable('laptop fuera de línea desde 14:02: inalcanzable (cuando se fue, dormía)'), S.remoto('vive en laptop')] }) },
    { grupo: 'hilo', nombre: 'viajando', nota:'se está llevando a otra máquina: el satélite gira', props: hilo('viaje', { at: 'trabajando', lugar: S.viaja('viajando a servidor…'), meta: { texto: '→ servidor' } }) },
    { grupo: 'hilo', nombre: 'abierto en dos máquinas', props: hilo('telar', { at: 'trabajando', aviso: { icono: I.alerta, tono: 'atencion', ayuda: 'también abierto en servidor' } }) },
    { grupo: 'hilo', nombre: 'público', props: hilo('ensayo', { sufijo: [S.publico('público')] }) },
    { grupo: 'hilo', nombre: 'de un agente', props: hilo('fotos del viaje', { at: 'espera', prefijo: [{ texto: 'A', tono: 'agente', ayuda: 'de agente:archivista' }] }) },
    { grupo: 'hilo', nombre: 'hijo', props: hilo('bitácora', { at: 'termino', hondo: 1, prefijo: [{ icono: I.hijo }] }) },
    { grupo: 'hilo', nombre: 'nieto', props: hilo('notas sueltas', { hondo: 2, prefijo: [{ icono: I.hijo }] }) },
    { grupo: 'hilo', nombre: 'nombre largo', nota: 'se corta con «…» antes de pisar el final',
        props: hilo('investigación sobre la memoria de los ríos del sur y sus crecidas', { p: 2, at: 'espera' }) },
    { grupo: 'hilo', nombre: 'cerrándose', nota: 'la atención se vacía; el texto, quieto', props: hilo('borrador', { saliendo: true, inicio: [S.prioridad(0), S.sale('cerrando…'), null], meta: { texto: 'cerrando' }, acciones: [] }) },
    { grupo: 'hilo', nombre: 'archivándose', props: hilo('mudanza', { p: 2, saliendo: true, inicio: [S.prioridad(2), S.sale('archivando…'), null], meta: { texto: 'archivando' }, acciones: [] }) },
    { grupo: 'hilo', nombre: 'arrastrándose', props: hilo('bitácora', { at: 'termino', clases: ['arrastrando'] }) },
    { grupo: 'hilo', nombre: 'donde caería', nota: 'soltarlo ahí lo cuelga de este', props: hilo('faro', { p: 1, at: 'trabajando', clases: ['destino'] }) },
    { grupo: 'hilo', nombre: 'archivado', props: hilo('mudanza', { apagada: true, inicio: [S.prioridad(2, true), null, null], meta: { texto: '5d' }, acciones: [retomar, { ...descartar, accion: 'descartar' }], clases: ['hover'] }) },

    { grupo: 'agente', nombre: 'con su hilo', nota: 'su casa, al pasar el mouse, antes de archivar y descartar',
        props: hilo('Archivista', { variante: 'agente', at: 'trabajando', acciones: [casa, archivar, descartar], clases: ['hover'] }) },
    { grupo: 'agente', nombre: 'sin hilo', nota: '▷ lo abre; al pasar el mouse, su casa y el ▷ (tapan el final); su ⋯, el menú del agente',
        props: { variante: 'agente', apagada: true, inicio: [null, null, null], titulo: 'Cartero', fijas: [abrirAgente],
            acciones: [{ ...casa, id: 'cartero', ayuda: 'la casa de Cartero: bitácora, memoria, archivos' }, abrirAgente],
            menu: { accion: 'menu-agente', id: 'cartero', icono: I.menu, ayuda: 'más: su casa, abrir su hilo' }, clases: ['hover'] } },

    { grupo: 'dashboard', nombre: 'pestaña', props: { variante: 'enlace', inicio: [null], titulo: 'tareas', meta: { texto: 't' } } },
    { grupo: 'dashboard', nombre: 'la que se ve', props: { variante: 'enlace', activa: true, inicio: [null], titulo: 'ahora', meta: { texto: 'a' } } },
    { grupo: 'dashboard', nombre: 'con algo nuevo', props: { variante: 'enlace', inicio: [null], titulo: 'mensajes', aviso: S.nuevo('3 chats sin leer'), meta: { texto: 'w' } } },

    { grupo: 'cabecera', nombre: 'abierta, con cuenta', props: { variante: 'cabecera', inicio: [{ icono: I.abierto }], titulo: 'hilos', sufijo: [{ texto: '6', tono: 'tenue' }],
        fijas: [A.nuevo({ accion: 'cmd', id: 'telar.nuevo' }, 'hilo nuevo')] } },
    { grupo: 'cabecera', nombre: 'plegada', props: { variante: 'cabecera', inicio: [{ icono: I.plegado }], titulo: 'equipo', sufijo: [{ texto: '2', tono: 'tenue' }] } },
    { grupo: 'cabecera', nombre: 'con acciones', props: { variante: 'cabecera', inicio: [{ icono: I.abierto }], titulo: 'agentes',
        fijas: [{ accion: 'cmd', id: 'telar.agentesVer', icono: I.lista, ayuda: 'todos los agentes' }, A.nuevo({ accion: 'cmd', id: 'telar.agenteNuevo' }, 'agente nuevo')] } },

    { grupo: 'submenú', nombre: 'plegado', nota: 'una sección dentro de otra (ARCHIVO dentro de HILOS): una fila más, con la flecha justo antes del nombre',
        props: { variante: 'submenu', inicio: [null, null, { icono: I.plegado }], titulo: 'archivo', sufijo: [{ texto: '14', tono: 'tenue' }] } },
    { grupo: 'submenú', nombre: 'abierto', props: { variante: 'submenu', inicio: [null, null, { icono: I.abierto }], titulo: 'archivo', sufijo: [{ texto: '14', tono: 'tenue' }] } },
    { grupo: 'submenú', nombre: 'con la columna de máquinas', nota: 'la flecha, pegada al nombre aunque la ranura sea ancha',
        props: { variante: 'submenu', inicio: [null, null, { icono: I.plegado, ancho: 7 }], titulo: 'archivo', sufijo: [{ texto: '14', tono: 'tenue' }] } },

    { grupo: 'otros', nombre: 'un pedido del equipo', props: { inicio: [{ icono: I.pedido }], titulo: 'ana · revisar el presupuesto', meta: { texto: '¿ya existe?' } } },
    { grupo: 'otros', nombre: 'una persona sin noticias', props: { apagada: true, inicio: [S.presente(false)], titulo: 'ana', sufijo: [{ texto: '· portátil · sin noticias', tono: 'tenue' }] } },
];

// ── una barra de hilos de mentira, con todo lo que puede tener ──

const AHORA = Date.now();
const hace = (min: number) => new Date(AHORA - min * 60000).toISOString();

function hiloJson(nombre: string, o: Partial<cli.JsonHilo> = {}): cli.JsonHilo {
    return {
        id: `@${nombre.length}`, nombre, vivo: true, activo: false, archivado: false, vinculado: true,
        ruta: `/casa/proyectos/${nombre}`, relativa: `proyectos/${nombre.toLowerCase()}`, arquetipo: 'proyecto',
        prioridad: 0, atencion: 'ninguna', visto: null, tiempo: 0, sesiones: [], actividad: hace(12), ...o,
    };
}

export const BARRA = {
    aqui: 'laptop',
    mostrado: 'Faro',
    secciones: [
        { clave: 'archivista', nombre: 'Archivista', hilos: ['Archivista'], home: true, grupo: 'agentes' },
        { clave: 'cartero', nombre: 'Cartero', hilos: ['Cartero'], home: true, grupo: 'agentes' },
    ] as cli.JsonSeccion[],
    hilos: [
        hiloJson('Archivista', { atencion: 'trabajando', agente: 'archivista', actividad: hace(3) }),
        hiloJson('Archivista › T12 ordenar las fotos', { atencion: 'espera', agente: 'archivista', icono: 'A', actividad: hace(40) }),
        hiloJson('Faro', { prioridad: 1, atencion: 'trabajando', activo: true, actividad: hace(2) }),
        hiloJson('Bitácora', { atencion: 'termino', sin_ver: true, padre: 'Faro', actividad: hace(25) }),
        hiloJson('Molino', { prioridad: 2, atencion: 'espera', actividad: hace(70) }),
        hiloJson('Puente', { prioridad: 3, atencion: 'termino', sin_ver: true, actividad: hace(20) }),
        hiloJson('Huerto', { atencion: 'termino', actividad: hace(60 * 30) }),
        hiloJson('Ensayo', { publico: true, actividad: hace(60 * 5) }),
        hiloJson('Notas del viaje', { atencion: 'espera', padre: 'Archivista', abierto_por: { por: 'Archivista', agente: 'archivista', icono: 'A' }, actividad: hace(9) }),
        hiloJson('Investigación sobre la memoria de los ríos del sur', { prioridad: 2, actividad: hace(60 * 26) }),
        hiloJson('Cosecha', { atencion: 'trabajando', remoto: 'servidor', actividad: hace(1) }),
        hiloJson('Viaje', { atencion: 'trabajando', actividad: hace(4) }),
        hiloJson('Telar', { atencion: 'espera', actividad: hace(15) }),
        hiloJson('Borrador', { actividad: hace(60 * 2) }),
        hiloJson('Mudanza', { archivado: true, vivo: false, prioridad: 2, actividad: hace(60 * 24 * 5) }),
        hiloJson('Cuaderno', { vivo: false, actividad: hace(60 * 24 * 9) }),
    ],
    otras: [{ nombre: 'servidor', en_linea: true, edad: 20, hilos: [
        { nombre: 'Telar', vivo: true, atencion: 'trabajando', relativa: 'proyectos/telar' },
        { nombre: 'Riego', vivo: true, atencion: 'espera', prioridad: 1, relativa: 'proyectos/riego' },
    ] as HiloDeFoto[] }],
    mudando: [['Viaje', 'servidor']] as [string, string][],
    saliendo: [['Borrador', { texto: 'cerrando', hasta: AHORA + 365 * 864e5 }]] as [string, { texto: string; hasta: number }][],
    apps: [{ clave: 'notas', nombre: 'notas', fuente: 'pagina' }] as cli.JsonApp[],
    pestanas: [
        { clave: 'ahora', accion: 'pantalla', valor: 'ahora', nombre: 'ahora', tecla: 'a' },
        { clave: 'esperas', accion: 'esperas', valor: '', nombre: 'te esperan', tecla: '', cuenta: 4, cuentaAyuda: '4 preguntan' },
        { clave: 'tareas', accion: 'pantalla', valor: 'tareas', nombre: 'tareas', tecla: 't' },
        { clave: 'correo', accion: 'pantalla', valor: 'correo', nombre: 'correo', tecla: 'm' },
        { clave: 'mensajes', accion: 'bloque', valor: 'mensajes', nombre: 'mensajes', tecla: 'w', aviso: '3 chats sin leer' },
    ] as PestanaDashboard[],
};

// ── el día en una línea (componentes/jornada.ts): un día inventado, con reuniones, un bloque propio y el almuerzo ──

const hm = (h: number, m = 0) => h * 60 + m;
/** Un día de mentira: lo que tendría un calendario cualquiera. Nada sale del de nadie. */
export const DIA_EJEMPLO: Tramo[] = [
    { inicio: hm(9), fin: hm(9, 30), titulo: 'Daily', clase: 'reunion' },
    { inicio: hm(9, 30), fin: hm(11), titulo: 'Foco: el informe', clase: 'bloque' },
    { inicio: hm(11, 30), fin: hm(12, 30), titulo: 'Revisión de diseño', clase: 'reunion' },
    { inicio: hm(13), fin: hm(14), titulo: 'Almuerzo', clase: 'rutina' },
    { inicio: hm(15), fin: hm(16), titulo: 'Comité', clase: 'reunion' },
    { inicio: hm(16), fin: hm(16, 30), titulo: 'Llamada de soporte', clase: 'reunion' },
    { inicio: hm(17, 15), fin: hm(17, 45), titulo: 'Cierre de la semana', clase: 'reunion' },
];
/** El mismo día con lo que la persona respondió a cada invitación: el Daily aceptado, una revisión del trimestre
 *  rechazada (llegó para estar al tanto), la Revisión de diseño tentativa, una presentación a todo el equipo sin
 *  responder, el Comité que organiza ella (sin respuesta) y la llamada aceptada. */
export const DIA_RESPUESTAS: Tramo[] = [
    { inicio: hm(9), fin: hm(9, 30), titulo: 'Daily', clase: 'reunion', respuesta: 'aceptada' },
    { inicio: hm(10, 30), fin: hm(11), titulo: 'Revisión del trimestre', clase: 'reunion', respuesta: 'rechazada' },
    { inicio: hm(11, 30), fin: hm(12, 30), titulo: 'Revisión de diseño', clase: 'reunion', respuesta: 'tentativa' },
    { inicio: hm(13), fin: hm(14), titulo: 'Almuerzo', clase: 'rutina' },
    { inicio: hm(14), fin: hm(15), titulo: 'Presentación al equipo', clase: 'reunion', respuesta: 'sin_responder' },
    { inicio: hm(15), fin: hm(16), titulo: 'Comité', clase: 'reunion', respuesta: '' },
    { inicio: hm(16), fin: hm(16, 30), titulo: 'Llamada de soporte', clase: 'reunion', respuesta: 'aceptada' },
];
/** La jornada que abarca la barra: de 8:30 a 18:00. */
export const JORNADA_EJEMPLO = { desde: hm(8, 30), hasta: hm(18) };
/** Momentos del día de mentira, cada uno con lo que la línea tendría que decir. */
export const MOMENTOS: { nombre: string; nota: string; ahora: number; tramos?: Tramo[] }[] = [
    { nombre: 'libre', nota: 'entre dos reuniones: cuánto queda y qué viene', ahora: hm(10, 10) },
    { nombre: 'queda poco', nota: 'menos de diez minutos: en el color del cuidado', ahora: hm(11, 24) },
    { nombre: 'en una reunión', nota: 'cuánto le queda, y lo libre que viene después', ahora: hm(11, 45) },
    { nombre: 'dos pegadas', nota: 'cuando termina una empieza la otra: sin libre entre medio', ahora: hm(15, 40) },
    { nombre: 'temprano', nota: 'antes de la jornada: lo libre hasta la primera', ahora: hm(7, 50) },
    { nombre: 'sin más reuniones', nota: 'pasó la última, y la jornada no termina', ahora: hm(17, 50) },
    { nombre: 'terminó el día', nota: 'pasada la jornada y la última reunión: no dice nada', ahora: hm(18, 20) },
    { nombre: 'sin reuniones', nota: 'un día sin reuniones (con un bloque propio): no dice nada', ahora: hm(10, 10),
        tramos: [{ inicio: hm(9, 30), fin: hm(11), titulo: 'Foco: el informe', clase: 'bloque' }] },
    { nombre: 'una rechazada', nota: 'la de las 10:30 se rechazó: no se dibuja, y lo libre llega hasta la de las 11:30', ahora: hm(10, 10),
        tramos: DIA_RESPUESTAS },
    { nombre: 'una tentativa', nota: 'la tentativa cuenta como reunión, igual que la aceptada', ahora: hm(11, 45), tramos: DIA_RESPUESTAS },
    { nombre: 'la próxima sin responder', nota: 'la de las 14:00 no se ha respondido: corta lo libre igual, va solo con su borde y el texto lo dice',
        ahora: hm(13, 40), tramos: DIA_RESPUESTAS },
    { nombre: 'en una sin responder', nota: 'cuánto le queda, como a cualquier reunión, y que no se ha respondido', ahora: hm(14, 20), tramos: DIA_RESPUESTAS },
    { nombre: 'solo rechazadas', nota: 'un día en que todo se rechazó: no dice nada', ahora: hm(10, 10),
        tramos: DIA_RESPUESTAS.map(t => (t.clase === 'reunion' ? { ...t, respuesta: 'rechazada' as const } : t)) },
];
