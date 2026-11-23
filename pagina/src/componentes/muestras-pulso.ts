// Pasadas de pulso de mentira (componentes/pulso.ts), con fecha de hoy: para el ensayo en la página (`window.telar
// .ensayoPulso()`) y la prueba (pruebas/pulso.mjs). Una de recién, con cambios de los dos mundos (trabajo y personal), cada
// uno con su causa, una fuente que falló (sin clasificar), lo que te espera y vencidas sin propuesta (que no se muestran), y
// su resumen neutro y el de cada mundo; una en seco de antes, de trabajo y sin `resumenes` (como las de antes: su resumen
// se ve solo donde no hay nada de otro mundo); una que no cambió nada; y la de anoche, personal. Cada cosa con el mundo que
// resolvió telar, y cada pasada con dónde tiene algo sin ver.

import type { JsonPasada, JsonSinVer } from '../cli';
import { hoyLocal } from './pulso';

/** Las cuatro pasadas sin ver, la más nueva primero, como las da `GET /resultados/pulso/visto`. */
export function pasadasDeMuestra(ahora = Date.now()): JsonSinVer & { pasadas: JsonPasada[]; total: number } {
    const hoy = hoyLocal(ahora);
    const d = new Date(`${hoy}T12:00:00`);
    d.setDate(d.getDate() - 1);
    const ayer = hoyLocal(d.getTime());
    const pasadas: JsonPasada[] = [
        {
            id: `${hoy}T15:00`, termino: `${hoy}T15:09`, modo: 'dia',
            resumen: '1 nueva, 2 avanzadas, 1 cerrada, 1 borrador. WhatsApp no respondió.',
            resumenes: {
                trabajo: 'Llegó la confirmación de Arcilla para el jueves y una pregunta de Molino; dejé un borrador a Inés.',
                personal: 'Llegó la cotización del riego.',
            },
            fuentes: [
                { fuente: 'correo-trabajo', llegaron: 6, archivados: 4, error: '', mundo: 'trabajo' },
                { fuente: 'correo-personal', llegaron: 3, archivados: 2, error: '', mundo: 'personal' },
                { fuente: 'whatsapp', llegaron: 0, archivados: 0, error: 'la sesión de WhatsApp Web se cerró', mundo: '' },
                { fuente: 'minutas', llegaron: 1, archivados: 0, error: '', nota: 'la del comité, encargada a Secretaría', mundo: 'trabajo' },
            ],
            tareas: {
                nuevas: [{ id: 'tarea:T580', linea: 'Arcilla: retrospectiva el jueves 26 a las 16:30 con Carla', mundo: 'trabajo',
                    por: 'correo de Carla Rojas', fuente: 'correo-trabajo', enlace: 'https://mail.google.com/mail/u/0/#inbox/r-580' }],
                avanzadas: [
                    { id: 'tarea:T540', linea: 'Molino: Carla pregunta si se conecta o comparte el Doc', mundo: 'trabajo',
                        por: 'minuta del 17-nov', fuente: 'minutas', enlace: 'archivo:trabajo/minutas/2026-11-17.md' },
                    { id: 'tarea:T588', linea: 'El jardín: llegó la cotización del riego', mundo: 'personal',
                        por: 'correo del vivero', fuente: 'correo-personal' },
                ],
                cerradas: [{ id: 'tarea:T512', como: 'hecha', linea: 'el correo a Tomás salió a las 14:40', mundo: 'trabajo',
                    por: 'respuesta de Ana', fuente: 'persona' }],
            },
            te_esperan: [
                { id: 'tarea:T540', pide: 'decidir', linea: 'Molino: ¿te conectas o compartes el Doc?', peso: 3, vence: hoy, mundo: 'trabajo' },
                { id: 'tarea:T591', pide: 'decidir', linea: 'El auto: ¿lo llevas al taller el sábado?', peso: 1, vence: '', mundo: 'personal' },
            ],
            borradores: [{ para: 'Inés Vega', asunto: 'Informe: revisión de literatura', enlace: '', tarea: 'tarea:T470', mundo: 'trabajo',
                por: 'correo de Inés', fuente: 'correo-trabajo' }],
            vencidas_sin_propuesta: ['tarea:T405', 'tarea:T566'],
            mundos_vencidas: { 'tarea:T405': 'trabajo', 'tarea:T566': 'personal' },
            mundos: ['trabajo', 'personal', ''], mundos_cambios: ['trabajo', 'personal'], sin_ver_en: ['trabajo', 'personal'],
        },
        {
            id: `${hoy}T14:00`, termino: `${hoy}T14:25`, modo: 'dia', seco: true,
            resumen: 'Seco: habría creado 2 tareas y anotado 1; nada escrito fuera de este registro.',
            fuentes: [
                { fuente: 'correo-trabajo', llegaron: 5, archivados: 0, error: '', mundo: 'trabajo' },
                { fuente: 'whatsapp', llegaron: 9, archivados: 2, error: '', mundo: '' },
            ],
            tareas: {
                nuevas: [
                    { id: '', linea: 'Nevada: contestarle a Dani cómo va la renovación', mundo: 'trabajo', por: 'WhatsApp de Dani', fuente: 'whatsapp' },
                    { id: 'HABRIA tarea nueva', linea: 'Arcilla: la información del estudio a Reyes', mundo: 'trabajo', por: 'correo de Reyes', fuente: 'correo-trabajo' },
                ],
                avanzadas: [{ id: 'tarea:T577', linea: 'Grupo Norte: la propuesta, hoy a fin de día', mundo: 'trabajo', por: 'correo de Beto Soto', fuente: 'correo-trabajo' }],
                cerradas: [],
            },
            te_esperan: [{ id: 'tarea:T387', pide: 'aprobar', linea: 'Lumbre: el deck de los tres planes', peso: 3, vence: ayer, mundo: 'trabajo' }],
            borradores: [],
            mundos: ['trabajo', ''], mundos_cambios: ['trabajo'], sin_ver_en: ['trabajo'],
        },
        {
            id: `${hoy}T13:00`, termino: `${hoy}T13:04`, modo: 'dia',
            resumen: 'Nada nuevo.',
            fuentes: [
                { fuente: 'correo-trabajo', llegaron: 2, archivados: 2, error: '', mundo: 'trabajo' },
                { fuente: 'whatsapp', llegaron: 4, archivados: 0, error: '', mundo: '' },
            ],
            tareas: { nuevas: [], avanzadas: [], cerradas: [] }, borradores: [],
            mundos: ['trabajo', ''], mundos_cambios: [], sin_ver_en: [''],
        },
        {
            id: `${ayer}T23:30`, termino: `${hoy}T00:12`, modo: 'noche',
            resumen: '1 nueva.',
            resumenes: { personal: 'Lo que te dictaste: dos encargos, ya en sus tareas.' },
            fuentes: [{ fuente: 'whatsapp', llegaron: 2, archivados: 0, error: '', mundo: 'personal' }],
            tareas: { nuevas: [{ id: 'tarea:T579', linea: 'Llamar al gasfíter y fijar la visita', mundo: 'personal', por: 'lo que te dictaste', fuente: 'dictado' }], avanzadas: [], cerradas: [] },
            borradores: [],
            mundos: ['personal'], mundos_cambios: ['personal'], sin_ver_en: ['personal'],
        },
    ];
    return {
        ok: true, clave: 'pulso', nombre: 'pulso', esquema: 'pulso', visto: { id: `${ayer}T22:00`, dia: ayer }, vistos: {},
        total: pasadas.length, con_cambios: 3, por_mundo: { trabajo: 2, personal: 2 }, pasadas,
    };
}
