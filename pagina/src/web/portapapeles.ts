// El portapapeles de la persona: todo lo que la página copia pasa por aquí. Las reglas de los navegadores, medidas en
// Chrome y en WebKit (pruebas/copiar-webkit.mjs):
//
// · `navigator.clipboard` existe solo en un contexto seguro (https, o localhost). Por http se copia como ⌘C, con
//   `document.execCommand('copy')`.
// · Las dos formas piden un gesto de la persona (un clic, una tecla). Chrome da unos segundos desde el último; Safari solo
//   lo que corre en ese evento o sale de él (sus promesas, un fetch, un setTimeout de menos de un segundo). Un mensaje del
//   WebSocket no sale de ningún gesto: lo que vuelve del servidor por OSC 52 (lo seleccionado en el tmux de otra máquina)
//   Safari no lo deja copiar al llegar…
// · …salvo con una escritura que empezó en el gesto (`armar`): `navigator.clipboard.write` con un ClipboardItem que recibe
//   una promesa, y la promesa se cumple cuando llega el texto. Solo en contexto seguro; por http, Safari necesita un clic
//   después de que llegó, y ese clic copia en su mismo evento (`copiarEnElGesto`).

/** Copia `texto` sin salir del evento que la llama: lo que corre dentro de un clic o una tecla copia en cualquier
 *  navegador, también por http. Primero ⌘C de mentira (un campo escondido con el texto seleccionado, y el evento `copy`
 *  que pone el texto tal cual); si el navegador no lo deja y hay `navigator.clipboard`, se le pide a él, empezado aquí
 *  mismo. La promesa dice si quedó copiado. */
export function copiarEnElGesto(texto: string): Promise<boolean> {
    if (porElCampo(texto)) return Promise.resolve(true);
    if (!seguro()) return Promise.resolve(false);
    try { return navigator.clipboard.writeText(texto).then(() => true, () => false); } catch { return Promise.resolve(false); }
}

/** Copiar desde lo que no es un evento (lo que llega del servidor, lo que sigue a un `await`). En Chrome anda unos
 *  segundos después del último clic; en Safari, solo si eso sigue saliendo del gesto. False: hay que pedir un clic. */
export const copiar = copiarEnElGesto;

/** Una escritura empezada en el gesto, que espera su texto: `dar` lo entrega (y dice si quedó copiado); `soltar` la
 *  deja sin escribir nada (el portapapeles queda como estaba). */
export interface Armada { dar(texto: string): Promise<boolean>; soltar(): void }

/** Empieza, en el gesto que la llama, una escritura cuyo texto todavía no llega (Safari la acepta así; Chrome y Firefox
 *  también). Si nada llega en `ms`, se suelta sola. Undefined donde no se puede (por http, o sin ClipboardItem). */
export function armar(ms = 5000): Armada | undefined {
    if (!seguro() || typeof ClipboardItem === 'undefined' || typeof navigator.clipboard?.write !== 'function') return undefined;
    let cumplir: (b: Blob) => void = () => {}, fallar: (e: Error) => void = () => {};
    const contenido = new Promise<Blob>((ok, no) => { cumplir = ok; fallar = no; });
    contenido.catch(() => {});
    let escrito: Promise<boolean>;
    try { escrito = navigator.clipboard.write([new ClipboardItem({ 'text/plain': contenido })]).then(() => true, () => false); } catch { return undefined; }
    const soltar = () => { clearTimeout(plazo); fallar(new Error('nada que copiar')); };
    const plazo = setTimeout(soltar, ms);
    return {
        dar(texto) { clearTimeout(plazo); cumplir(new Blob([texto], { type: 'text/plain' })); return escrito; },
        soltar,
    };
}

/** Lo que llega sin gesto (OSC 52): por la escritura armada en el gesto, si la hay; si no (o no resultó), como se pueda.
 *  False: hay que pedir un clic (`copiarEnElGesto` en el evento de un botón). */
export async function copiarLoQueLlega(texto: string, armada?: Armada): Promise<boolean> {
    if (armada && await armada.dar(texto)) return true;
    return copiar(texto);
}

const seguro = () => window.isSecureContext && typeof navigator.clipboard?.writeText === 'function';

/** ⌘C sobre un campo escondido con el texto. El evento `copy` pone el texto exacto (sin lo que el campo le cambie);
 *  la selección del campo es por si un navegador no lo escucha. Vuelve el foco adonde estaba. */
function porElCampo(texto: string): boolean {
    const antes = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const campo = document.createElement('textarea');
    campo.value = texto;
    campo.setAttribute('readonly', '');
    campo.setAttribute('aria-hidden', 'true');
    campo.style.cssText = 'position:fixed;top:0;left:-9999px;opacity:0';
    const poner = (e: ClipboardEvent) => {
        if (!e.clipboardData) return;
        e.clipboardData.setData('text/plain', texto);
        e.preventDefault();
    };
    document.addEventListener('copy', poner, true);
    document.body.appendChild(campo);
    campo.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch { ok = false; }
    document.removeEventListener('copy', poner, true);
    campo.remove();
    antes?.focus({ preventScroll: true });
    return ok;
}
