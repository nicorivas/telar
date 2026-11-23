// Lo escrito y todavía no mandado, para que recargar la página no lo pierda (web/recarga.ts): la caja de la conversación
// y la de bajo la terminal de cada hilo, la instrucción de cada entidad (web/instruccion.ts), la otra respuesta de una
// pregunta del agente (web/pregunta.ts). Va al sessionStorage: es de esta pestaña y sobrevive a recargarla, sin pasar a
// otras pestañas ni quedar para otro día. Sin almacén (un navegador que lo niega), como antes: dura lo que dura la página.

const PRE = 'telar.escrito.';

/** Lo guardado con esa clave, o undefined. */
export function leer<T>(clave: string): T | undefined {
    try {
        const v = sessionStorage.getItem(PRE + clave);
        return v === null ? undefined : JSON.parse(v) as T;
    } catch { return undefined; }
}

/** Guardarlo; vacío (nada, '', o una lista de vacíos) lo borra. */
export function guardar(clave: string, valor: unknown): void {
    const vacio = valor === undefined || valor === null || valor === ''
        || (Array.isArray(valor) && valor.every(x => !String(x ?? '').trim()));
    try {
        if (vacio) sessionStorage.removeItem(PRE + clave);
        else sessionStorage.setItem(PRE + clave, JSON.stringify(valor));
    } catch { /* sin almacén: dura lo que dura la página */ }
}

type Campo = HTMLTextAreaElement | HTMLInputElement;
/** Las cajas montadas, por su clave: se guardan de nuevo al irse la página (lo que se les puso sin teclear: vaciarla al
 *  enviar, devolverle lo que no salió). */
const cajas = new Map<string, Campo>();
const valor = (c: Campo) => (c.value.trim() ? c.value : '');

/** Una caja que guarda lo que se escribe en ella: si viene vacía, trae lo guardado; cada tecla lo guarda. `anotar`, después
 *  de cambiarla por código; `soltar`, al desmontarla (lo guardado queda, para cuando vuelva). Marca la caja
 *  (`data-guarda`): lo escrito ahí no cuenta como algo que recargar perdería. */
export function caja(c: Campo, clave: string): { anotar(): void; soltar(): void } {
    const antes = leer<string>(clave);
    if (!c.value && antes) c.value = antes;
    c.dataset.guarda = '';
    const anotar = () => guardar(clave, valor(c));
    c.addEventListener('input', anotar);
    cajas.set(clave, c);
    return {
        anotar,
        soltar: () => { anotar(); c.removeEventListener('input', anotar); if (cajas.get(clave) === c) cajas.delete(clave); },
    };
}

/** Todas las cajas montadas, guardadas ahora. */
export function anotarTodas(): void {
    for (const [clave, c] of cajas) if (c.isConnected) guardar(clave, valor(c));
}

window.addEventListener('pagehide', anotarTodas);
document.addEventListener('visibilitychange', () => { if (document.hidden) anotarTodas(); });
