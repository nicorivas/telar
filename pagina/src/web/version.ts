// Una versión nueva de telar, en la franja de avisos de arriba de la barra (web/avisos.ts): «telar 0.4.8», con
// «instalar», que la instala y reinicia el servicio (telar.actualizar, en un proceso aparte); la página se recarga sola
// cuando contesta la nueva. Si esta instalación no se actualiza desde aquí (la del repositorio: git pull), el aviso lleva
// a ⚙ versión, que dice qué hacer y permite buscar a mano.
// También ahí, una página nueva de la que corre (se desplegó después de abrir esta, y se está mirando: web/recarga.ts):
// «página nueva», y «recargar». Antes los dos iban arriba a la izquierda, junto a la versión que corre.

import * as cli from '../cli';
import { I } from './iconos';
import * as avisos from './avisos';
import * as recarga from './recarga';
import * as ui from './ui';

/** cada cuánto la página pregunta (el servicio le pregunta a PyPI a lo más una vez por hora) */
const CADA = 20 * 60 * 1000;
/** cuánto se espera a que el servicio vuelva con la versión nueva */
const PLAZO = 6 * 60 * 1000;

let ultima: cli.JsonVersion | undefined;
let alAbrirConfig: (() => void) | undefined;
/** instalando la versión nueva: el aviso dice en qué va, y al terminar la página se recarga sola */
let instalando = false;

/** Poner (o quitar) los avisos con lo último que se supo. */
function pintar(): void {
    if (recarga.hayNueva()) {
        avisos.poner({ clave: 'pagina-nueva', nivel: 'aviso', icono: I.releer, texto: 'página nueva',
            detalle: 'Se desplegó después de abrir esta.', hacer: 'Recargarla: lo escrito y lo que miras se quedan.',
            acciones: [{ id: 'recargar', texto: 'recargar', hacer: () => recarga.recargar() }] });
    } else avisos.quitar('pagina-nueva');
    if (instalando) return;
    const v = ultima;
    if (!v?.hay_nueva && v?.puerta?.atras) {
        // la puerta del servidor quedó atrás de telar: se actualiza a mano, con root; el botón dice cómo
        avisos.poner({ clave: 'version', nivel: 'aviso', icono: I.actualizar, texto: `puerta ${v.puerta.telar}`,
            detalle: `La puerta del servidor va en la ${v.puerta.version || '?'} y telar en la ${v.puerta.telar}.`,
            hacer: 'Se actualiza a mano, con root, en el servidor.',
            acciones: [{ id: 'como', texto: 'cómo actualizarla', hacer: () => void actualizar() }] });
        return;
    }
    if (!v?.hay_nueva) { avisos.quitar('version'); return; }
    avisos.poner({ clave: 'version', nivel: 'aviso', icono: I.actualizar, texto: `telar ${v.ultima}`,
        detalle: `Hay una versión nueva de telar (corre la ${v.corre}).`,
        hacer: v.puede ? 'Se instala y se reinicia el servicio: la página vuelve sola y los hilos no se cortan.'
            : v.a_mano ?? 'Esta instalación no se actualiza desde aquí: ⚙ versión dice cómo.',
        acciones: v.puede ? [{ id: 'instalar', texto: 'instalar', hacer: () => void actualizar() }] : [],
        ir: { texto: '⚙ versión', hacer: () => alAbrirConfig?.() } });
}

/** Preguntar ahora (`forzar`: a PyPI, sin esperar la hora). Devuelve lo que se supo. */
export async function revisar(forzar = false): Promise<cli.JsonVersion | undefined> {
    const r = await cli.version(forzar);
    if (r.datos) ultima = r.datos;
    pintar();
    return r.datos ?? undefined;
}

/** Instalar la versión nueva: preguntar, lanzar, mostrar en qué va y recargar cuando conteste la nueva. */
export async function actualizar(): Promise<void> {
    const v = ultima ?? await revisar();
    if (!v?.hay_nueva && v?.puerta?.atras) {
        const orden = v.puerta.actualizar ?? 'sudo sh servidor/telar-puerta-instalar …';
        try { await navigator.clipboard.writeText(orden); } catch { /* sin portapapeles: se lee en el aviso */ }
        void ui.info(`La puerta del servidor va en la ${v.puerta.version || '?'}; telar, en la ${v.puerta.telar}. Se actualiza `
            + `con root, en el servidor, desde la carpeta del repositorio de telar (quedó copiada): ${orden}`);
        return;
    }
    if (!v?.hay_nueva) { void ui.info('telar: ya corre la última versión'); return; }
    if (!v.puede) { alAbrirConfig?.(); return; }
    const si = await ui.aviso(`¿Instalar telar ${v.ultima}? Corre la ${v.corre}. Se instala desde PyPI y se reinicia el `
        + 'servicio: la página se desconecta un momento y vuelve sola. Lo que corre en los hilos no se corta.', 'Instalar');
    if (si !== 'Instalar') return;
    const r = await cli.actualizar(v.ultima);
    if (!r.datos) { void ui.falla(`telar: no pude empezar: ${r.error ?? 'sin respuesta'}`); return; }
    instalando = true;
    // instalándose: lo nuevo llega, un círculo que se llena (componentes/circulo.ts), en el aviso
    avisos.poner({ clave: 'version', nivel: 'aviso', icono: I.actualizar, curso: 'llena', texto: `instalando telar ${v.ultima}…`, desde: Date.now(),
        detalle: `Se instala la ${v.ultima} y se reinicia el servicio: la página se recarga sola cuando conteste la nueva (a lo más ${PLAZO / 60000} minutos).` });
    await esperar(v.ultima);
}

async function esperar(objetivo: string): Promise<void> {
    const hasta = Date.now() + PLAZO;
    while (Date.now() < hasta) {
        await new Promise(r => setTimeout(r, 2500));
        // mientras se reinicia el servicio no contesta: se sigue esperando
        const corre = await cli.versionCorriendo().catch(() => '');
        if (corre === objetivo) { recarga.recargar(); return; }
        const p = await cli.progresoActualizar().catch(() => undefined);
        if (p?.datos?.estado === 'fallo') {
            void ui.falla(`telar: no se pudo instalar la ${objetivo}: ${p.datos.error ?? ''}. Lo que pasó, en ${I.config} versión.`);
            instalando = false;
            pintar();
            return;
        }
    }
    void ui.falla(`telar: la ${objetivo} no contestó en ${PLAZO / 60000} minutos. Mira ${I.config} versión, o reinicia el servicio a mano.`);
    instalando = false;
    pintar();
}

/** Lo último que se supo (para ⚙ versión). */
export const lo = (): cli.JsonVersion | undefined => ultima;

/** Empezar: una primera pregunta y después cada `CADA`. `abrirConfig` lleva a ⚙ versión. */
export function vigilar(abrirConfig: () => void): void {
    alAbrirConfig = abrirConfig;
    recarga.alCambiar(pintar);
    void revisar();
    setInterval(() => void revisar(), CADA);
}
