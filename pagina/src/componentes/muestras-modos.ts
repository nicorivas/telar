// Lo que muestra el prototipo de los modos y los mundos (/componentes#modos): dos mundos, un horario, de qué mundo es cada
// hilo de la barra de mentira (componentes/muestras.ts), las filas de DASHBOARD de cada modo, lo que hay en Todo y un
// Táctica para cuando el mundo es personal. Inventados: la librería de barrio de las muestras de Táctica (el trabajo) y
// una casa con huerto, bicicleta y un viaje al sur (lo personal). Nada de aquí es de nadie.

import type * as cli from '../cli';
import type { HiloDeFoto, PestanaDashboard } from '../vistas/hilos';
import { I } from '../web/iconos';
import { BARRA, DIA_EJEMPLO } from './muestras';
import { ESTADOS as ESTADOS_TACTICA } from './muestras-tactica';
import type { Tramo } from './jornada';
import type { Carril, Decision, Quehacer, Tactica } from './tactica';
import type { Cosa, Fuente } from './todo';
import { type ClaveModo, type MundoPuesto, type Mundo, SIN_CLASIFICAR, leerHorario, mundoAhora } from './modos-mundos';

// ── los mundos y su horario: el trabajo de lunes a viernes de 9 a 19; fuera de eso, lo personal ──

/** Como se declararían (`[mundos.trabajo] horario = "lun-vie 9:00-19:00"`, `[mundos] fuera = "personal"`). */
export const MUNDOS: Mundo[] = [
    { clave: 'trabajo', nombre: 'trabajo', color: 'cian', horario: leerHorario('lun-vie 9:00-19:00') },
    { clave: 'personal', nombre: 'personal', color: 'magenta' },
];
export const FUERA = 'personal';

/** El día de las muestras, un martes (el de Táctica), a una hora. */
const a = (hh: number, mm = 0) => new Date(2026, 10, 17, hh, mm);
export const AHORA = a(11, 45);

/** Las escenas del mundo: a qué hora y si se eligió a mano. */
export interface Escena { clave: string; nombre: string; nota: string; hora: Date; aMano?: { mundo: string; desde: Date }; sinMundos?: boolean }
export const ESCENAS: Escena[] = [
    { clave: 'trabajo', nombre: 'trabajo, por su horario', hora: AHORA,
        nota: 'martes 11:45: el horario pone trabajo hasta las 19:00. La palabra en su color y hasta cuándo en tenue' },
    { clave: 'noche', nombre: 'personal, fuera del horario', hora: a(20, 30),
        nota: 'martes 20:30: fuera del horario de trabajo, personal (`fuera`) hasta mañana a las 9:00. La línea del día ya terminó: la cabecera tiene más lugar' },
    { clave: 'a-mano', nombre: 'personal, a mano', hora: AHORA, aMano: { mundo: 'personal', desde: a(11, 40) },
        nota: 'martes 11:45: se eligió personal a mano a las 11:40. Dura hasta el próximo cambio del horario (las 19:00), y lo dice; «volver al horario», en su menú' },
    { clave: 'ambos', nombre: 'ambos, a mano', hora: AHORA, aMano: { mundo: '', desde: a(11, 40) },
        nota: 'ambos: no filtra. Las listas van en tandas, una por mundo; la palabra en el color del texto' },
    { clave: 'sin-mundos', nombre: 'sin [mundos]', hora: AHORA, sinMundos: true,
        nota: 'sin `[mundos]` en la configuración no hay mundo que mostrar: no hay control y nada se filtra (como hoy)' },
];
export const escena = (clave: string): Escena => ESCENAS.find(e => e.clave === clave) ?? ESCENAS[0];
export const puestoEn = (e: Escena): MundoPuesto => mundoAhora(MUNDOS, e.hora, { fuera: FUERA, aMano: e.aMano });

// ── de qué mundo es cada hilo de la barra de mentira (lo deriva telar de su carpeta: aquí, a mano) ──

const MUNDO_HILO: Record<string, string> = {
    Archivista: 'personal', 'Archivista › T12 ordenar las fotos': 'personal', Cartero: 'trabajo',
    Faro: 'trabajo', Bitácora: 'trabajo', Molino: 'trabajo', Puente: 'trabajo', Telar: 'trabajo', Borrador: 'trabajo', Viaje: 'personal',
    Huerto: 'personal', Ensayo: 'personal', 'Notas del viaje': 'personal', Cosecha: 'personal', Mudanza: 'personal', Riego: 'personal',
    'Investigación sobre la memoria de los ríos del sur': SIN_CLASIFICAR, Cuaderno: SIN_CLASIFICAR,
};
export const mundoDeHilo = (nombre: string): string => MUNDO_HILO[nombre] ?? SIN_CLASIFICAR;
/** Si se ve con ese mundo puesto: lo suyo, y lo sin clasificar (que se ve en todos); con ambos, todo. */
export const seVe = (mundoDeLaCosa: string, puesto: string): boolean => !puesto || mundoDeLaCosa === puesto || mundoDeLaCosa === SIN_CLASIFICAR;

/** La barra de mentira con un mundo puesto: sus hilos, sus agentes y los de la otra máquina; y cuántos quedan afuera. */
export function barraEn(puesto: string): { hilos: cli.JsonHilo[]; secciones: cli.JsonSeccion[]; otras: typeof BARRA.otras; fuera: number } {
    const hilos = BARRA.hilos.filter(h => seVe(mundoDeHilo(h.nombre), puesto));
    const secciones = BARRA.secciones.filter(s => seVe(mundoDeHilo(s.nombre), puesto));
    const otras = BARRA.otras.map(m => ({ ...m, hilos: m.hilos.filter((x: HiloDeFoto) => seVe(mundoDeHilo(x.nombre), puesto)) }));
    const fuera = BARRA.hilos.filter(h => h.vivo && !h.archivado && !seVe(mundoDeHilo(h.nombre), puesto)).length
        + BARRA.otras.reduce((n, m) => n + m.hilos.filter(x => x.vivo && !seVe(mundoDeHilo(x.nombre), puesto)).length, 0);
    return { hilos, secciones, otras, fuera };
}

// ── las filas de DASHBOARD de cada modo ──

const fila = (clave: string, nombre: string, tecla = '', mas: Partial<PestanaDashboard> = {}): PestanaDashboard =>
    ({ clave, accion: 'pantalla', valor: clave, nombre, tecla, ...mas });

/** Lo que se ve en DASHBOARD en cada modo: Táctica, su vista y el día; Estrategia, lo que se mira con calma (abre en proyectos);
 *  Todo, cada fuente entera. Foco no tiene barra. */
export const FILAS: Record<ClaveModo, PestanaDashboard[]> = {
    tactica: [fila('tactica', 'táctica', 'a'), fila('dia', 'día', 'd')],
    estrategia: [fila('proyectos', 'proyectos', 'p'), fila('tablero', 'tablero'), fila('registro', 'decisiones')],
    foco: [],
    todo: [fila('todo', 'todo', '/'), fila('esperas', 'te esperan'), fila('tareas', 'tareas', 't'), fila('casillas', 'casillas'),
        fila('correo', 'correo', 'm'), fila('mensajes', 'mensajes', 'w'), fila('lecturas', 'lecturas', 'l'), fila('calendario', 'calendario', 'c'),
        fila('proyectos', 'proyectos', 'p'), fila('periodicos', 'periódicos'), fila('tablero', 'tablero'), fila('registro', 'decisiones')],
};

// ── lo que hay en Todo: cada fuente, cuántas cosas tiene en cada mundo, y unas cuantas de ellas ──

export const FUENTES: Fuente[] = [
    { clave: 'esperas', nombre: 'te esperan', icono: I.campana, color: 'amarillo', cuenta: { trabajo: 46, personal: 14, [SIN_CLASIFICAR]: 4 },
        dice: { trabajo: '18 preguntan · la más vieja, hace 6 semanas', personal: '3 preguntan', '': '21 preguntan' } },
    { clave: 'tareas', nombre: 'tareas', icono: I.hecha, color: 'cian', cuenta: { trabajo: 61, personal: 23, [SIN_CLASIFICAR]: 3 },
        dice: { trabajo: '9 vencen esta semana · 14 de deuda', personal: '2 vencen esta semana · 5 de deuda', '': '11 esta semana · 19 de deuda' } },
    { clave: 'casillas', nombre: 'casillas', icono: I.listado, color: 'verde', cuenta: { trabajo: 112, personal: 26, [SIN_CLASIFICAR]: 5 },
        dice: { trabajo: 'en 24 documentos', personal: 'en 7 documentos', '': 'en 33 documentos' } },
    { clave: 'calendario', nombre: 'calendario', icono: I.fecha, color: 'azul', cuenta: { trabajo: 21, personal: 4, [SIN_CLASIFICAR]: 0 },
        dice: { trabajo: 'hoy 5 reuniones · la semana 21', personal: 'la semana 4', '': 'la semana 25' } },
    { clave: 'correo', nombre: 'correo', icono: I.correo, color: 'azul', cuenta: { trabajo: 168, personal: 44, [SIN_CLASIFICAR]: 0 },
        dice: { trabajo: '12 sin procesar', personal: '3 sin procesar', '': '15 sin procesar' } },
    { clave: 'mensajes', nombre: 'mensajes', icono: I.conversacion, color: 'verde', cuenta: { trabajo: 7, personal: 11, [SIN_CLASIFICAR]: 0 },
        dice: { trabajo: '7 chats · 2 sin leer', personal: '11 chats · 1 sin leer', '': '18 chats · 3 sin leer' } },
    { clave: 'lecturas', nombre: 'lecturas', icono: I.libro, color: 'magenta', cuenta: { trabajo: 2, personal: 4, [SIN_CLASIFICAR]: 0 },
        dice: { trabajo: 'para leer', personal: 'para leer', '': 'para leer' } },
    { clave: 'hilos', nombre: 'hilos', icono: I.terminal, color: 'azul', cuenta: { trabajo: 7, personal: 7, [SIN_CLASIFICAR]: 1 },
        dice: { trabajo: '2 te esperan · 18 en el archivo', personal: '1 te espera · 9 en el archivo', '': '3 te esperan · 27 en el archivo' } },
    { clave: 'proyectos', nombre: 'proyectos', icono: I.carpeta, color: 'verde', cuenta: { trabajo: 58, personal: 21, [SIN_CLASIFICAR]: 7 },
        dice: { trabajo: '6 pausados · 2 sin cerrar', personal: '4 pausados', '': '10 pausados · 2 sin cerrar' } },
];

const c = (fuente: string, id: string, titulo: string, mundo: string, mas: Partial<Cosa> = {}): Cosa => ({ fuente, id, titulo, mundo, ...mas });

/** Lo que encuentra «vitrina»: de cada fuente, y algo de lo personal y de lo sin clasificar. */
export const HALLADAS: Cosa[] = [
    c('esperas', 'permiso:Vitrina', '¿Qué foto va en la vitrina de diciembre?', 'trabajo', { antes: 'pregunta', donde: 'Vitrina', meta: 'te espera · 4m', tono: 'espera' }),
    c('esperas', 'mensaje:m-7f3a', '«Vitrina» → «Catálogo»: la lista de los doce libros', 'trabajo', { antes: 'retenido', meta: '2h' }),
    c('tareas', 'tarea:T42', 'Armar la vitrina con la foto elegida', 'trabajo', { antes: 'T42', donde: 'vitrina', meta: 'el plan: hoy', tono: 'acento' }),
    c('tareas', 'tarea:T47', 'Pedir el vidrio nuevo para la vitrina', 'trabajo', { antes: 'T47', donde: 'vitrina', meta: 'vence el viernes' }),
    c('tareas', 'tarea:T51', 'Luces para la vitrina de enero', 'trabajo', { antes: 'T51', donde: 'vitrina', meta: 'sin fecha' }),
    c('tareas', 'tarea:T39', 'Fotografiar la vitrina para el boletín', 'trabajo', { antes: 'T39', donde: 'boletín', meta: 'hecha · 3 nov', pasada: true }),
    c('tareas', 'tarea:T61', 'Vender la vitrina vieja del living', 'personal', { antes: 'T61', donde: 'casa', meta: 'sin fecha' }),
    c('casillas', 'archivo:casa/vitrina/README.md#3', 'Medir el fondo de la vitrina antes de pedir el vidrio', 'trabajo', { donde: 'vitrina/README.md' }),
    c('casillas', 'archivo:casa/vitrina/README.md#5', 'Elegir la paleta de la vitrina', 'trabajo', { donde: 'vitrina/README.md', meta: 'marcada', pasada: true }),
    c('casillas', 'archivo:notas/ideas.md#12', 'Una vitrina con libros usados, a precio fijo', SIN_CLASIFICAR, { donde: 'notas/ideas.md' }),
    c('calendario', 'evento:montaje', 'Montaje de la vitrina', 'trabajo', { antes: 'jue 19 · 9:00', meta: '2h' }),
    c('correo', 'correo:c-91', 'Re: el vidrio para la vitrina', 'trabajo', { antes: 'de la vidriería', meta: 'ayer' }),
    c('correo', 'correo:c-88', 'Fotos de la feria para la vitrina', 'trabajo', { antes: 'del fotógrafo', meta: 'lun' }),
    c('correo', 'correo:c-60', 'Cotización: iluminación de vitrina', 'trabajo', { antes: 'de una tienda de luces', meta: 'hace 2 semanas', pasada: true }),
    c('correo', 'correo:c-77', 'Re: ¿se puede montar la vitrina el jueves?', 'trabajo', { antes: 'del administrador del local', meta: 'vie' }),
    c('correo', 'correo:c-41', 'Tu pedido: repisas de vidrio', 'trabajo', { antes: 'de una tienda', meta: 'hace 3 semanas', pasada: true }),
    c('correo', 'correo:c-12', 'Boletín: vitrinas que venden', 'trabajo', { antes: 'de un boletín de libreros', meta: 'hace 1 mes', pasada: true }),
    c('mensajes', 'chat:feria', '¿La vitrina queda lista el viernes?', 'trabajo', { antes: 'grupo de la feria', meta: 'hoy 10:02' }),
    c('mensajes', 'chat:familia', '¿Alguien quiere la vitrina de la abuela?', 'personal', { antes: 'grupo de la familia', meta: 'dom' }),
    c('hilos', 'hilo:Vitrina', 'Vitrina', 'trabajo', { antes: '', donde: 'casa/vitrina', meta: 'te espera', tono: 'espera' }),
    c('hilos', 'hilo:Catálogo', 'Catálogo', 'trabajo', { donde: 'casa/catalogo', meta: 'trabajando' }),
    c('proyectos', 'proyecto:casa/vitrina', 'Vitrina de diciembre', 'trabajo', { donde: 'casa/vitrina', meta: 'en desarrollo' }),
    c('lecturas', 'leer:vitrinas', 'Lo que se ve desde la vereda: vitrinas de librería', 'trabajo', { antes: 'un artículo', meta: '8 min' }),
];
export const BUSCADO = 'vitrina';

/** Todas las tareas, enteras: lo que muestra «tareas» en Todo, sin filtros ni topes (aquí, las primeras del trabajo). */
export const TAREAS: Cosa[] = [
    c('tareas', 'tarea:T40', 'Mandar el pedido de diciembre a la distribuidora', 'trabajo', { antes: 'T40', donde: 'compras', meta: 'vence hoy', tono: 'atencion' }),
    c('tareas', 'tarea:T42', 'Armar la vitrina con la foto elegida', 'trabajo', { antes: 'T42', donde: 'vitrina', meta: 'el plan: hoy', tono: 'acento' }),
    c('tareas', 'tarea:T44', 'Llamar a la imprenta por el papel', 'trabajo', { antes: 'T44', donde: 'compras', meta: 'el plan: hoy', tono: 'acento' }),
    c('tareas', 'tarea:T47', 'Pedir el vidrio nuevo para la vitrina', 'trabajo', { antes: 'T47', donde: 'vitrina', meta: 'vence el viernes' }),
    c('tareas', 'tarea:T31', '¿Parto el inventario en dos: la bodega y la tienda?', 'trabajo', { antes: 'T31', donde: 'inventario', meta: 'te espera', tono: 'espera' }),
    c('tareas', 'tarea:T25', 'Presupuesto de la feria del libro', 'trabajo', { antes: 'T25', donde: 'feria', meta: 'vence el sábado' }),
    c('tareas', 'tarea:T28', 'Borrador del boletín de diciembre', 'trabajo', { antes: 'T28', donde: 'boletín', meta: 'preparado', tono: 'exito' }),
    c('tareas', 'tarea:T51', 'Luces para la vitrina de enero', 'trabajo', { antes: 'T51', donde: 'vitrina', meta: 'sin fecha' }),
    c('tareas', 'tarea:T53', 'Ordenar la bodega de los usados', 'trabajo', { antes: 'T53', donde: 'tienda', meta: 'sin fecha' }),
    c('tareas', 'tarea:T8', '¿Seguimos con la imprenta del barrio o cotizamos otra?', 'trabajo', { antes: 'T8', donde: 'compras', meta: 'deuda · 43 días' }),
    c('tareas', 'tarea:T3', '¿Archivamos las facturas de 2024?', 'trabajo', { antes: 'T3', donde: 'compras', meta: 'deuda · venció hace 48 días' }),
    c('tareas', 'tarea:T15', 'Revisar el contrato del local', 'trabajo', { antes: 'T15', donde: 'tienda', meta: 'deuda · 2 meses' }),
    c('tareas', 'tarea:T9', 'Una carpeta para los recibos', SIN_CLASIFICAR, { antes: 'T9', meta: 'sin fecha' }),
    c('tareas', 'tarea:T39', 'Fotografiar la vitrina para el boletín', 'trabajo', { antes: 'T39', donde: 'boletín', meta: 'hecha · 3 nov', pasada: true }),
    c('tareas', 'tarea:T36', 'Cotizar estantes nuevos', 'trabajo', { antes: 'T36', donde: 'tienda', meta: 'descartada · 11 nov', pasada: true }),
];

// ── Táctica en lo personal (el contenido es del prototipo de Táctica: aquí, solo para ver que el mundo lo filtra) ──

/** El día personal: después de la jornada, nada en el calendario de trabajo; una cena a las 21:30. */
export const DIA_PERSONAL: Tramo[] = [{ inicio: 21 * 60 + 30, fin: 23 * 60, titulo: 'Cena con amigos', clase: 'reunion' }];
export const DIA_TRABAJO: Tramo[] = DIA_EJEMPLO;

const decision = (id: string, titulo: string, porque: Decision['porque'], mas: Partial<Decision> = {}): Decision => ({ id, titulo, porque, ...mas });
const VIVO_PERSONAL: Decision[] = [
    decision('permiso:Huerto', '¿Riego por goteo o con la manguera de siempre?', { texto: 'te espera', tono: 'espera' }, { palabra: 'pregunta', tono: 'espera', edad: '20m' }),
];
const VIAS_PERSONAL: Carril[] = [
    { clave: 'aprobar', cuentas: [{ clave: 'viaje', nombre: 'viaje', decisiones: [decision('tarea:T64', 'Itinerario del viaje al sur: tres noches en Puerto Varas',
        { texto: 'vence el jue' })] }] },
    { clave: 'cerrar', cuentas: [{ clave: 'casa', nombre: 'casa', decisiones: [decision('tarea:T66', 'Renovar la suscripción del diario',
        { texto: 'venció el 15-nov' }, { como: 'caduca', prueba: 'se renovó sola' })] }] },
];
const HACER_PERSONAL: Quehacer[] = [
    { tipo: 'reunion', id: 'evento:21:30', titulo: 'Cena con amigos', hora: '21:30', nota: 'llevar el vino' },
    { tipo: 'tarea', id: 'tarea:T62', titulo: 'Regar el huerto antes del viaje', donde: 'huerto', tamano: 'rapida', porque: { texto: 'vence hoy' } },
    { tipo: 'tarea', id: 'tarea:T63', titulo: 'Cambiar la cadena de la bicicleta', donde: 'casa', tamano: 'rapida', porque: { texto: 'vence el vie' } },
];

/** Táctica con un mundo puesto: el de trabajo es el de las muestras de Táctica (en la reunión de las 11:45); el personal,
 *  libre hasta la cena; con ambos, los dos juntos en un solo orden. */
export function tacticaEn(puesto: string, hora: Date): Tactica {
    const trabajo = ESTADOS_TACTICA[0].tactica('lado');
    const queda = 21 * 60 + 30 - (hora.getHours() * 60 + hora.getMinutes());
    const personal: Tactica = {
        ahora: { tipo: 'libre', queda, luego: '21:30 Cena con amigos', caben: 'las 3 decisiones (≈6min) y «Regar el huerto antes del viaje» (rápida)' },
        vias: VIAS_PERSONAL, vivo: VIVO_PERSONAL, hacer: HACER_PERSONAL, disposicion: 'lado',
        resto: [{ clave: 'tareas', nombre: 'tareas', cuenta: 21 }, { clave: 'correo', nombre: 'correos', cuenta: 3 }, { clave: 'mensajes', nombre: 'chats', cuenta: 11 }],
    };
    if (puesto === 'personal') return personal;
    if (puesto === 'trabajo') return trabajo;
    // ambos: cada vía con sus cuentas de los dos mundos
    const vias = trabajo.vias.map(v => ({ ...v, cuentas: [...v.cuentas, ...VIAS_PERSONAL.find(x => x.clave === v.clave)?.cuentas ?? []] }));
    return { ...trabajo, vivo: [...trabajo.vivo ?? [], ...VIVO_PERSONAL], vias,
        resto: trabajo.resto.map(r => (r.cuenta === undefined ? r : { ...r, cuenta: r.cuenta + (personal.resto.find(p => p.clave === r.clave)?.cuenta ?? 0) })) };
}
