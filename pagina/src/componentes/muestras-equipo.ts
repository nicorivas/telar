// El equipo de mentira del prototipo de la vista «equipo» (componentes/equipo.ts, /componentes#equipo): cinco personas
// inventadas, con nombres neutros, fechas alrededor del jueves 26-nov-2026 y textos de ejemplo. Nada sale de las fichas de
// nadie, ni del calendario, ni de las tareas, ni de la planilla de horas: telar es público.
//
// Las apreciaciones van aparte, en `apreciacionesDeMuestra`, y no en `Persona`: en la vista de verdad no están en el
// modelo de la página; las trae del Drive un clic, y se olvidan al salir (docs/propuestas/equipo.md, «Privacidad»).

import type { Apreciacion, Persona } from './equipo';

/** El día de las muestras: un jueves, a las 11:40. */
export const HOY = '2026-11-26';
export const AHORA = '2026-11-26T11:40';

export const PERSONAS: Persona[] = [
    {
        clave: 'ana', nombre: 'Ana', rol: 'analista de datos', dedicacion: '100% del área',
        unoAUno: { serie: '1:1 Ana', cadencia: 'quincenal', dias: 14, ultimo: '2026-11-17', proximo: '2026-12-01T10:00' },
        teDebe: [
            { id: 'T901', titulo: 'Enviar la muestra limpia del modelo de demanda', clase: 'espera', desde: '2026-11-19', vence: '2026-11-27',
                ultimo: 'el 24-nov dijo que le faltaba una tabla' },
            { id: 'T902', titulo: 'Armar el tablero de seguimiento del piloto', clase: 'delegada', desde: '2026-11-10', vence: '2026-12-04' },
        ],
        leDebes: [
            { id: 'T903', titulo: 'Revisar su propuesta de curso interno', clase: 'tuya', desde: '2026-11-17', vence: '2026-11-28',
                ultimo: 'salió del 1:1 del 17-nov' },
        ],
        pedidos: [{ id: 'p-ana-1', titulo: 'Darle acceso a la base de pruebas', cuando: '2026-11-25T18:02' }],
        capacidad: { semana: '23 al 27-nov', horas: 40, cargadas: 36, porProyecto: [
            { proyecto: 'Modelo de demanda', horas: 20 }, { proyecto: 'Tablero del piloto', horas: 10 }, { proyecto: 'Capacitación interna', horas: 6 }],
            previas: [95, 88, 102, 90] },
        proyectos: [
            { ruta: 'ejemplo/modelo-demanda', nombre: 'Modelo de demanda', rol: 'lidera', clase: 'curso', plazo: '2026-12-15' },
            { ruta: 'ejemplo/tablero-piloto', nombre: 'Tablero del piloto', rol: 'apoya', clase: 'preparacion', plazo: '2027-01-08' },
            { ruta: 'ejemplo/capacitacion', nombre: 'Capacitación interna', rol: 'apoya', clase: 'curso' },
        ],
    },
    {
        clave: 'bruno', nombre: 'Bruno', rol: 'ingeniero de datos', dedicacion: '50% del área',
        unoAUno: { serie: '1:1 Bruno', cadencia: 'quincenal', dias: 14, ultimo: '2026-10-29' },
        teDebe: [
            { id: 'T911', titulo: 'Documentar la carga nocturna', clase: 'espera', desde: '2026-11-06', vence: '2026-11-20',
                ultimo: 'sin novedad desde el 13-nov' },
        ],
        leDebes: [
            { id: 'T912', titulo: 'Conseguirle acceso al servidor de pruebas', clase: 'tuya', desde: '2026-10-29', ultimo: 'salió del 1:1 del 29-oct' },
        ],
        pedidos: [],
        capacidad: { semana: '23 al 27-nov', horas: 20, cargadas: 26, porProyecto: [
            { proyecto: 'Integración de ventas', horas: 16 }, { proyecto: 'Modelo de demanda', horas: 6 }, { proyecto: 'soporte', horas: 4 }],
            previas: [110, 125, 118, 130] },
        proyectos: [
            { ruta: 'ejemplo/integracion-ventas', nombre: 'Integración de ventas', rol: 'lidera', clase: 'curso', plazo: '2026-12-10' },
            { ruta: 'ejemplo/modelo-demanda', nombre: 'Modelo de demanda', rol: 'apoya', clase: 'curso', plazo: '2026-12-15' },
        ],
    },
    {
        clave: 'carla', nombre: 'Carla', rol: 'diseñadora de servicios', dedicacion: '100% del área',
        unoAUno: { serie: '1:1 Carla', cadencia: 'semanal', dias: 7, ultimo: '2026-11-19', proximo: '2026-11-26T16:00' },
        teDebe: [],
        leDebes: [
            { id: 'T921', titulo: 'Mandarle el ejemplo de entrevista a usuarios', clase: 'tuya', desde: '2026-11-19', vence: '2026-11-26' },
        ],
        pedidos: [],
        capacidad: { semana: '23 al 27-nov', horas: 40, cargadas: 30, porProyecto: [
            { proyecto: 'Portal de clientes', horas: 22 }, { proyecto: 'Capacitación interna', horas: 8 }],
            previas: [80, 85, 78, 75] },
        proyectos: [
            { ruta: 'ejemplo/portal-clientes', nombre: 'Portal de clientes', rol: 'lidera', clase: 'curso', plazo: '2027-02-27' },
            { ruta: 'ejemplo/capacitacion', nombre: 'Capacitación interna', rol: 'lidera', clase: 'curso' },
        ],
    },
    {
        clave: 'diego', nombre: 'Diego', rol: 'desarrollador', dedicacion: '100% del área',
        unoAUno: { serie: '1:1 Diego', cadencia: 'mensual', dias: 30, ultimo: '2026-11-05', proximo: '2026-12-03T15:30' },
        teDebe: [
            { id: 'T931', titulo: 'Subir la versión con el buscador', clase: 'espera', desde: '2026-11-24', vence: '2026-12-01' },
            { id: 'T932', titulo: 'Probar el asistente con cinco usuarios', clase: 'delegada', desde: '2026-11-05', vence: '2026-12-10' },
        ],
        leDebes: [],
        pedidos: [],
        capacidad: { semana: '23 al 27-nov', horas: 40, cargadas: 40, porProyecto: [
            { proyecto: 'Asistente interno', horas: 30 }, { proyecto: 'Portal de clientes', horas: 10 }],
            previas: [100, 98, 104, 100] },
        proyectos: [
            { ruta: 'ejemplo/asistente-interno', nombre: 'Asistente interno', rol: 'lidera', clase: 'curso', plazo: '2027-01-22' },
            { ruta: 'ejemplo/portal-clientes', nombre: 'Portal de clientes', rol: 'apoya', clase: 'curso', plazo: '2027-02-27' },
        ],
    },
    {
        clave: 'eva', nombre: 'Eva', rol: 'practicante', dedicacion: '50% del área', desde: '2026-11-16',
        unoAUno: { serie: '1:1 Eva', cadencia: 'semanal', dias: 7, proximo: '2026-11-27T12:00' },
        teDebe: [], leDebes: [], pedidos: [],
        proyectos: [{ ruta: 'ejemplo/tablero-piloto', nombre: 'Tablero del piloto', rol: 'apoya', clase: 'preparacion', plazo: '2027-01-08' }],
    },
];

/** Lo que traería del Drive el clic en «traer del Drive»: inventado. En la vista de verdad esto no existe en la página
 *  hasta el clic, y deja de existir al salir. */
const APRECIACIONES: Record<string, Apreciacion[]> = {
    ana: [
        { fecha: '2026-11-17', texto: 'Lleva bien la relación con el equipo del piloto. Quiere más espacio para enseñar: lo hablamos con la propuesta de curso.' },
        { fecha: '2026-11-03', texto: 'Le cuesta cortar el alcance cuando el pedido crece. Acordamos que lo diga en el daily antes de aceptar.' },
    ],
    bruno: [
        { fecha: '2026-10-29', texto: 'Está repartido entre dos áreas y se nota. Pide que las prioridades le lleguen por una sola vía.' },
    ],
    carla: [
        { fecha: '2026-11-19', texto: 'Las entrevistas le salen muy bien. Quiere mostrar el método al resto del equipo.' },
        { fecha: '2026-11-12', texto: 'Se siente sola en el portal: revisar si alguien puede acompañarla una tarde por semana.' },
    ],
    diego: [
        { fecha: '2026-11-05', texto: 'Avanza rápido y prueba poco con usuarios. Quedó en probar con cinco antes de la próxima versión.' },
    ],
    eva: [],
};

export const apreciacionesDeMuestra = (clave: string): Apreciacion[] => APRECIACIONES[clave] ?? [];
