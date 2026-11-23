// Los hilos dormidos (telar.dormir) vistos desde la página: decirle a telar qué se muestra, para que lo que se mira no se
// duerma, y despertar al que se abre dormido.
//
// La página guarda abiertas las terminales de los últimos hilos que se miraron (navegador/app.ts, `TOPE`): cada una es
// una terminal enganchada a la ventana de su hilo, y sin más noticias telar las contaría como «a la vista» y no
// dormiría a ninguno de esos. Por eso la página dice qué muestra (`POST /mirando`), al cambiar y cada 30 s mientras se
// ve (oculta, no muestra nada): lo que la página no muestra no se mira, aunque su terminal siga abierta. Si la página se
// cierra, deja de decirlo, y en 90 s telar ya no lo cuenta.
//
// Abrir un hilo es despertarlo. Una terminal nueva lo despierta sola (`telar mirar`, en la máquina del hilo); pero la de
// un hilo que se miró hace poco ya está montada, y mostrarla no le pide nada a telar. Por eso, al mostrar un hilo que la
// lista dice dormido (aquí, o en la foto de otra máquina), se le pide despertarlo (`POST /despertar`). Salvo que su máquina
// no esté en línea: que duerma es lo último que dijo antes de irse, y mirarlo no deja nada en cola (eso es el botón
// «despertar al volver», web/alcance.ts).
//
// Un hilo cerrado no se despierta: se retoma. Salvo el de un agente residente que se abre cuando le llega algo: su
// conversación deja la caja, y escribirle va como mensaje, que su nodo le entrega abriéndolo (`abreAlEscribir`).

import type { JsonHilo, JsonSeccion } from '../cli';
import type { HiloDeFoto } from '../vistas/hilos';

/** Lo que muestra la página, como lo dice `mostrar` (navegador/app.ts): un hilo de aquí por su nombre, uno de otra
 *  máquina como `rem:<máquina>:<hilo>`, y lo demás (el dashboard, un archivo, un objeto) no es un hilo. */
export function hiloDe(que: string): { hilo: string; maquina: string } {
    if (!que || que === 'dashboard' || que === 'compartir' || que === 'config' || /^(doc|arch|obj):/.test(que)) return { hilo: '', maquina: '' };
    if (que.startsWith('rem:')) {
        const resto = que.slice(4), i = resto.indexOf(':');
        return i < 0 ? { hilo: '', maquina: '' } : { hilo: resto.slice(i + 1), maquina: resto.slice(0, i) };
    }
    return { hilo: que, maquina: '' };
}

/** Las otras máquinas, como las lee la página: su foto, y si está en línea (sin decirlo, en línea). */
type Otra = { nombre: string; en_linea?: boolean; hilos: HiloDeFoto[] };

/** Si lo que se muestra es un hilo que duerme, cuál y dónde; null si no. Uno de aquí, por la lista (`dormido`); uno de
 *  otra máquina, por su foto, si esa máquina está en línea. */
export function dormidoEn(que: string, hilos: JsonHilo[], otras: Otra[]): { hilo: string; maquina: string } | null {
    const { hilo, maquina } = hiloDe(que);
    if (!hilo) return null;
    if (!maquina) {
        const h = hilos.find(x => x.nombre === hilo);
        // la ventana de aquí de uno de una máquina fuera de línea: lo que dice es de antes de que se fuera
        return h?.vivo && h.dormido && h.alcanzable !== false ? { hilo, maquina: '' } : null;
    }
    const m = otras.find(y => y.nombre === maquina);
    if (m?.en_linea === false) return null;
    const x = m?.hilos.find(y => y.nombre === hilo);
    return x?.vivo && x.dormido ? { hilo, maquina } : null;
}

/** Cada cuánto se repite lo que se muestra (ms): telar lo da por viejo a los 90 s. */
export const CADA = 30_000;

/** Lo que dice la página a telar: qué muestra y despertar al que se abre dormido. `enviar` y `despertar` son la API
 *  (cli.mirando, cli.despertar); en las pruebas, de mentira. */
export class Mirador {
    /** un id por página abierta: dos pestañas del navegador dicen cada una lo suyo */
    readonly pagina = Math.random().toString(36).slice(2, 10);
    private dicho = '';
    private cuando = 0;
    /** los que se pidió despertar hace poco: no se pide dos veces mientras la lista todavía no se entera */
    private pedidos = new Map<string, number>();

    constructor(private enviar: (pagina: string, hilo: string, maquina: string) => Promise<unknown>,
        private despertarApi: (hilo: string, maquina: string) => Promise<unknown>, private ahora = () => Date.now()) {}

    /** Decir lo que se muestra: al cambiar, o si pasaron CADA ms. `oculta`: la página no se ve (nada se muestra). */
    decir(que: string, oculta = false, forzar = false): boolean {
        const { hilo, maquina } = oculta ? { hilo: '', maquina: '' } : hiloDe(que);
        const clave = `${maquina}|${hilo}`;
        if (!forzar && clave === this.dicho && this.ahora() - this.cuando < CADA) return false;
        this.dicho = clave;
        this.cuando = this.ahora();
        void this.enviar(this.pagina, hilo, maquina).catch(() => undefined);
        return true;
    }

    /** Al mostrar algo: si es un hilo dormido, despertarlo. Devuelve si lo pidió. */
    alMostrar(que: string, hilos: JsonHilo[], otras: Otra[]): boolean {
        const d = dormidoEn(que, hilos, otras);
        if (!d) return false;
        const clave = `${d.maquina}|${d.hilo}`;
        if (this.ahora() - (this.pedidos.get(clave) ?? -Infinity) < CADA) return false;
        this.pedidos.set(clave, this.ahora());
        void this.despertarApi(d.hilo, d.maquina).catch(() => undefined);
        return true;
    }
}

/** Si escribirle a un hilo cerrado (o archivado) de aquí lo abre: es el hilo de siempre de un agente residente que se
 *  abre cuando le llega algo (`residente` siempre o a-pedido en su agente.toml) y hay bus. Lo que se le escribe va
 *  como mensaje (como a uno de otra máquina) y su nodo lo abre con su conversación y se lo entrega: así el teléfono
 *  le escribe a un agente cerrado sin pasar antes por «retomar». Con `presencia = no`, o sin bus, no: lo de siempre. */
export function abreAlEscribir(h: Pick<JsonHilo, 'nombre' | 'vivo' | 'archivado'> | undefined,
    secciones: readonly JsonSeccion[], hayBus: boolean): boolean {
    if (!h || (h.vivo && !h.archivado) || !hayBus) return false;
    const s = secciones.find(x => x.grupo === 'agentes' && x.nombre === h.nombre);
    return !!s && (s.presencia ?? 'a-pedido') !== 'no';
}
