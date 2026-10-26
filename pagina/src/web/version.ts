// Una versión nueva de telar, arriba a la derecha (#version): «↑ 0.4.8». Un clic la instala y reinicia el servicio
// (telar.actualizar, en un proceso aparte) y la página se recarga sola cuando contesta la nueva. Si esta
// instalación no se actualiza desde aquí (la del repositorio: git pull), el clic lleva a ⚙ versión, que dice qué
// hacer y permite buscar a mano.

import * as cli from '../cli';
import * as ui from './ui';

/** cada cuánto la página pregunta (el servicio le pregunta a PyPI a lo más una vez por hora) */
const CADA = 20 * 60 * 1000;
/** cuánto se espera a que el servicio vuelva con la versión nueva */
const PLAZO = 6 * 60 * 1000;

let ultima: cli.JsonVersion | undefined;
let alAbrirConfig: (() => void) | undefined;

const boton = () => document.getElementById('version') as HTMLAnchorElement | null;

/** Pintar el aviso de arriba con lo último que se supo. */
function pintar(): void {
    const b = boton();
    if (!b) return;
    const v = ultima;
    if (!v?.hay_nueva && v?.puerta?.atras) {
        // la puerta del servidor quedó atrás de telar: se actualiza a mano, con root; el clic dice cómo
        b.hidden = false;
        b.classList.remove('trabajando');
        b.textContent = `↑ puerta ${v.puerta.telar}`;
        b.title = `la puerta del servidor va en la ${v.puerta.version || '?'} y telar en la ${v.puerta.telar}. Clic: cómo actualizarla`;
        return;
    }
    if (!v?.hay_nueva) { b.hidden = true; return; }
    b.hidden = false;
    b.classList.remove('trabajando');
    b.textContent = `↑ ${v.ultima}`;
    b.title = v.puede ? `hay una versión nueva de telar: la ${v.ultima} (corre la ${v.corre}). Clic: instalarla y reiniciar`
        : `hay una versión nueva de telar: la ${v.ultima} (corre la ${v.corre}). ${v.a_mano ?? ''}`;
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
    const b = boton();
    if (b) { b.classList.add('trabajando'); b.textContent = `↻ ${v.ultima}…`; b.title = 'instalando la versión nueva'; }
    void ui.estado(`telar: instalando la ${v.ultima}…`, 8000);
    await esperar(v.ultima);
}

async function esperar(objetivo: string): Promise<void> {
    const hasta = Date.now() + PLAZO;
    while (Date.now() < hasta) {
        await new Promise(r => setTimeout(r, 2500));
        // mientras se reinicia el servicio no contesta: se sigue esperando
        const corre = await cli.versionCorriendo().catch(() => '');
        if (corre === objetivo) { location.reload(); return; }
        const p = await cli.progresoActualizar().catch(() => undefined);
        if (p?.datos?.estado === 'fallo') {
            void ui.falla(`telar: no se pudo instalar la ${objetivo}: ${p.datos.error ?? ''}. Lo que pasó, en ⚙ versión.`);
            pintar();
            return;
        }
    }
    void ui.falla(`telar: la ${objetivo} no contestó en ${PLAZO / 60000} minutos. Mira ⚙ versión, o reinicia el servicio a mano.`);
    pintar();
}

/** Lo último que se supo (para ⚙ versión). */
export const lo = (): cli.JsonVersion | undefined => ultima;

/** Empezar: el clic del aviso, una primera pregunta y después cada `CADA`. `abrirConfig` lleva a ⚙ versión. */
export function vigilar(abrirConfig: () => void): void {
    alAbrirConfig = abrirConfig;
    boton()?.addEventListener('click', e => { e.preventDefault(); void actualizar(); });
    void revisar();
    setInterval(() => void revisar(), CADA);
}
