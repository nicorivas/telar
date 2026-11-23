// Lo que quedó detenido esperando a la persona sin que nada lo diga, como avisos de la franja (web/avisos.ts):
// - un mensaje entre hilos que el freno de cadenas retuvo, que no llega hasta que ella lo suelte y que quien lo mandó da
//   por entregado (lo lee dashboard/esperas.ts);
// - un hilo detenido en la pregunta de Claude Code de confiar en una carpeta, antes de arrancar: mientras nadie la
//   conteste no hace nada, y sin ganchos no avisaba (telar.confiar lo marca; lo lee web/vigia.ts con los hilos).
// Lo que espera a la persona tiene su lugar («te esperan»), pero ahí solo se ve si se va a mirar: un «listo» retenido
// dejó horas a un hijo y a su padre esperándose, y un hijo esperó tres horas una pregunta que nadie veía. Por eso esto
// sí va en la franja, y lleva ahí.
//
// Sin DOM ni red: arma los avisos con lo que ya se leyó. Lo prueba `npm run prueba:avisos`.

import type { JsonEspera, JsonHilo } from '../cli';
import type { Aviso } from './avisos';
import { I } from './iconos';

/** Cuánto se dice en la franja un mensaje retenido (ms): pasado eso, queda solo en «te esperan». */
export const RETENIDO_RECIENTE = 24 * 3600 * 1000;

/** El aviso de los mensajes retenidos de las últimas horas (uno para todos: el más nuevo, y cuántos), o `null` si no
 *  hay. `ir` abre «te esperan». */
export function avisoRetenidos(lista: readonly JsonEspera[], ir: () => void, ahora = Date.now()): Aviso | null {
    const recientes = lista.filter(e => e.clase === 'retenido' && ahora - Date.parse(e.desde) < RETENIDO_RECIENTE)
        .sort((a, b) => Date.parse(b.desde) - Date.parse(a.desde));
    const ultimo = recientes[0];
    if (!ultimo) return null;
    const motivo = String(ultimo.campos?.motivo ?? '').trim();
    const cual = recientes.length === 1 ? `el mensaje de ${ultimo.titulo}` : `${recientes.length} mensajes entre hilos; el último, de ${ultimo.titulo}`;
    return {
        clave: 'retenidos', nivel: 'aviso', icono: I.pausa, conConexion: true, cuando: 'hace', desde: Date.parse(ultimo.desde),
        texto: recientes.length === 1 ? `retenido: ${ultimo.titulo}` : `${recientes.length} mensajes retenidos`,
        detalle: `El freno de cadenas retuvo ${cual}${motivo ? ` (${motivo})` : ''}. No llegó, y quien lo mandó cree que sí.`,
        hacer: 'Míralo en «te esperan»: suéltalo si está bien (o `telar mensaje --soltar <id>`); si no, descártalo, y a quien lo mandó le llega un aviso de que no se entregó (o `telar mensaje --descartar <id>`).',
        ir: { texto: 'te esperan', hacer: ir },
    };
}

/** Los avisos de los hilos de aquí detenidos en la pregunta de confiar en una carpeta (`espera.clase` «confiar»), uno
 *  por hilo: cuál, qué pide y qué hacer. `ir` lleva al hilo. Nunca la contesta: es de la persona. */
export function avisosConfiar(hilos: readonly JsonHilo[], ir: (hilo: string) => void): Aviso[] {
    return hilos.filter(h => h.vivo && !h.remoto && h.atencion === 'espera' && h.espera?.clase === 'confiar').map(h => {
        const desde = h.atencion_desde ? Date.parse(h.atencion_desde) : NaN;
        return {
            clave: `confiar:${h.nombre}`, nivel: 'aviso' as const, icono: I.carpeta, conConexion: true, cuando: 'hace' as const,
            desde: Number.isNaN(desde) ? undefined : desde,
            texto: `«${h.nombre}» espera que confíes en una carpeta`,
            detalle: `${(h.espera?.pide || 'Claude Code pregunta si confías en una carpeta antes de arrancar').replace(/[.]?$/, '.')} `
                + 'Mientras nadie la conteste, el hilo no hace nada.',
            hacer: 'Ve al hilo y contesta la pregunta de Claude Code (si es el worktree de su rama, «Yes, add it»). telar no la contesta: es tuya.',
            ir: { texto: `el hilo ${h.nombre}`, hacer: () => ir(h.nombre) },
        };
    });
}
