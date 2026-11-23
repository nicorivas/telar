// Las confirmaciones de verdad (`ui.aviso` con botones, la ventana de `preguntar` en web/interfaz.ts) con textos de muestra
// copiados de las de la página, para mirarlas y medirlas sin tocar nada: `window.telar.ensayoConfirmar('borrar')` en la consola
// (también `archivar`, `descartar`, `traer`, la de contenido largo que se desplaza, y `permiso`, la de tres botones). Devuelve
// lo que se apretó; no hace nada con eso.

import * as ui from './ui';

const LARGA = Array.from({ length: 40 }, (_, i) => `· ~/casa/proyectos/telar/pagina/src/archivo-${String(i + 1).padStart(2, '0')}.ts (sin subir)`).join('\n');

export const ENSAYOS: Record<string, () => Promise<string | undefined>> = {
    borrar: () => ui.aviso('¿Borrar el estilo «nocturno»? Los modos que lo usen vuelven a «base».', 'Borrar', { destruye: true }),
    archivar: () => ui.aviso('¿Archivar «faro»? Se cierra su ventana; su conversación queda para retomarla.', 'Archivar'),
    descartar: () => ui.aviso('¿Descartar «faro»? Está vivo: se cierra su ventana, sale del archivo y telar lo olvida (su conversación queda en disco).',
        'Descartar', { destruye: true }),
    traer: () => ui.aviso(`La conversación de «faro» viaja, los archivos no. En servidor hay trabajo que aquí no va a estar:\n${LARGA}`, 'Traer igual'),
    permiso: () => ui.aviso('El módulo «whatsapp» pide leer tus chats.', 'Permitir siempre', 'Solo esta vez', 'No',
        { detalle: 'Lo que telar le concede queda anotado; se revoca con: telar modulos permisos whatsapp --quitar leer', foco: 'cancelar' }),
};

/** Abre la de `cual` y dice qué se apretó (sin hacerlo). */
export async function ensayo(cual = 'borrar'): Promise<string> {
    const abrir = ENSAYOS[cual];
    if (!abrir) return `no hay «${cual}»: ${Object.keys(ENSAYOS).join(', ')}`;
    const r = await abrir();
    return r === undefined ? 'cancelada' : `apretó «${r}»`;
}
