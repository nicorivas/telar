// Dónde vive ahora un hilo, para la terminal que lo miraba y ya no abre (web/terminal.ts): se llevó a otra máquina
// (telar hilo llevar), volvió, o su ventana de aquí se está reabriendo. La página lo sigue sola a donde vive, sin decir
// «retómalo» de algo que está abierto en otra parte: la de la máquina de donde salió, la de la que llegó y el teléfono.
//
// Lo que se sabe:
//   1. la lista de aquí (`GET /hilos`): abierto aquí con su propia ventana (no la que mira a otra máquina);
//   2. su registro en el bus (`GET /hilo/registro`, telar.dueno): de qué máquina es, si vive, y si va en camino. Es lo
//      que manda: un hilo tiene un solo dueño, y el traspaso se escribe ahí, así que lo ve cualquier página;
//   3. sin bus (o sin respuesta), las fotos de las otras máquinas (`GET /espejos`): dónde está abierto, suyo.
//
// Solo decide: quien lo usa conecta, espera o muestra. Lo prueba pruebas/llevar.mjs, en Node.

/** El hilo en la lista de aquí, lo que importa. */
export interface HiloAqui { nombre: string; vivo?: boolean; archivado?: boolean; remoto?: string }
/** La foto de otra máquina, lo que importa. */
export interface FotoMaquina { nombre: string; en_linea?: boolean; hilos: { nombre: string; vivo?: boolean; remoto?: string }[] }
/** Su registro en el bus (telar.dueno): su dueño, si vive, y el traspaso en curso. */
export interface Registro { dueno?: string; maquina?: string; vivo?: boolean; cede?: string;
    mudanza?: { a?: string; paso?: string; hora?: number } }

export type Donde =
    /** abierto aquí, con su propia ventana: conectarse aquí */
    | { a: 'aqui' }
    /** vive en `maquina` y su ventana de aquí (la que mira allá) se está reabriendo: esperarla */
    | { a: 'espejo'; maquina: string }
    /** vive en otra máquina: mirarlo allá */
    | { a: 'alla'; maquina: string }
    /** va en camino a `maquina` (una mudanza de aquí, sin terminar): esperar */
    | { a: 'viajando'; maquina: string }
    /** cerrado o archivado aquí, y abierto en ninguna otra: su conversación */
    | { a: 'cerrado' }
    /** no se sabe de él */
    | { a: 'nada' };

/** cuánto vale un traspaso a medias en el registro (en segundos): más viejo, quedó colgado y lo arregla su nodo */
const TRASPASO_VALE = 15 * 60;

/** Las máquinas cuyas fotos lo tienen abierto, suyo (no la ventana que mira a otra), en línea. */
export function abiertoEn(hilo: string, otras: readonly FotoMaquina[]): string[] {
    return otras.filter(m => m.en_linea !== false && m.hilos.some(x => x.nombre === hilo && x.vivo && !x.remoto)).map(m => m.nombre);
}

/** Dónde vive `hilo` ahora. `registro`: el del bus (si se sabe); `mirando`: la máquina cuya terminal se miraba ("" si la de
 *  aquí, que puede ser la ventana que mira a otra). `ahora`, en segundos. */
export function dondeVive(hilo: string, o: { aqui: string; local?: HiloAqui; otras: readonly FotoMaquina[]; registro?: Registro;
    mirando?: string; ahora?: number }): Donde {
    const ahora = o.ahora ?? Date.now() / 1000;
    const h = o.local;
    // 1. abierto aquí con su propia ventana
    if (h && h.vivo && !h.archivado && (!h.remoto || h.remoto === o.aqui)) return { a: 'aqui' };
    // 2. su registro en el bus: su dueño, y si va en camino
    const r = o.registro;
    const dueno = r?.dueno || r?.maquina || '';
    if (r && dueno) {
        const reciente = (r.mudanza?.hora ?? 0) > ahora - TRASPASO_VALE;
        // cediéndose (su agente ya se detuvo) a otra: va en camino; tomado y abriéndose allá: también
        if (r.cede && reciente) return r.cede === o.aqui ? { a: 'cerrado' } : { a: 'viajando', maquina: r.cede };
        if (dueno === o.aqui) return h ? { a: 'cerrado' } : { a: 'nada' };
        if (r.mudanza?.paso === 'abrir' && reciente && !r.vivo) return { a: 'viajando', maquina: dueno };
        // por ssh ([remotos]) aquí queda una ventana que lo mira allá: esa es la de siempre
        if (h && h.vivo && !h.archivado && h.remoto === dueno) return { a: 'espejo', maquina: dueno };
        if (r.vivo) return { a: 'alla', maquina: dueno };
        return h ? { a: 'cerrado' } : { a: 'nada' };
    }
    // 3. sin registro (sin bus, o no contestó): las fotos
    const otras = o.otras.filter(m => m.nombre !== o.aqui);
    const abierto = abiertoEn(hilo, otras);
    // su ventana de aquí mira a otra máquina: si esa todavía lo tiene (o no se sabe), se espera a que se reabra; si ya no
    // lo tiene y otra sí, se fue a esa
    const suya = h && h.remoto && h.remoto !== '?' && h.remoto !== o.aqui && !h.archivado ? h.remoto : '';
    if (suya) {
        const fotoSuya = otras.find(x => x.nombre === suya);
        if (abierto.includes(suya) || !fotoSuya) return { a: 'espejo', maquina: suya };
        const otra = abierto.find(x => x !== suya);
        return otra ? { a: 'alla', maquina: otra } : { a: 'espejo', maquina: suya };
    }
    // lo que se miraba en otra máquina: si sigue allá, ahí; si no, donde esté abierto (aquí ya se vio en 1)
    if (o.mirando) {
        if (abierto.includes(o.mirando)) return { a: 'alla', maquina: o.mirando };
        const otra = abierto.find(x => x !== o.mirando);
        if (otra) return { a: 'alla', maquina: otra };
    }
    // un hilo de aquí, cerrado: que otra máquina tenga abierto uno con el mismo nombre no dice que sea este
    if (h) return { a: 'cerrado' };
    return { a: 'nada' };
}

/** El hilo y la máquina de lo que se mira: «Faro» (aquí) o «rem:laptop:Faro». */
export function partirVista(que: string): { hilo: string; maquina: string } {
    if (!que.startsWith('rem:')) return { hilo: que, maquina: '' };
    const resto = que.slice(4), i = resto.indexOf(':');
    return { hilo: resto.slice(i + 1), maquina: resto.slice(0, i) };
}

/** Lo que se mira, como se muestra: «Faro» si vive aquí, «rem:laptop:Faro» si en otra. */
export const vistaDe = (hilo: string, d: Donde): string => d.a === 'aqui' ? hilo : d.a === 'alla' ? `rem:${d.maquina}:${hilo}` : '';

/** Si lo que se mira sigue abierto donde se lo mira. */
export function abiertoDonde(d: Donde, mirando: string): boolean {
    return mirando ? (d.a === 'alla' || d.a === 'espejo') && d.maquina === mirando : d.a === 'aqui' || d.a === 'espejo' || d.a === 'viajando';
}

/** cuánto se lo busca después de que se fue de donde se lo miraba */
const BUSCA_MS = 3 * 60_000;

/** Seguir lo que se mira a donde vive (src/navegador/app.ts, con cada lectura de la lista y de las fotos): solo si se lo
 *  vio abierto donde se lo mira y se fue de ahí, y por unos minutos. Lo que se abrió cerrado a propósito (uno archivado,
 *  para leerlo) no se mueve. */
export class Seguidor {
    private que = '';
    private vio = false;
    private desde = 0;

    /** Adónde ir ('' para quedarse), con lo que se mira (`que`) y dónde vive ahora (`d`). `ahora`, en ms. */
    mirar(que: string, d: Donde, ahora = Date.now()): string {
        const { hilo, maquina } = partirVista(que);
        if (que !== this.que) { this.que = que; this.vio = false; this.desde = 0; }
        if (abiertoDonde(d, maquina)) { this.vio = true; this.desde = 0; return ''; }
        if (!this.vio) return '';
        this.desde ||= ahora;
        if (ahora - this.desde > BUSCA_MS) return '';
        const ir = vistaDe(hilo, d);
        return ir && ir !== que ? ir : '';
    }

    /** Si lo que se mira se vio abierto y se fue (para pedir lo que falta saber: su registro en el bus). */
    sefue(que: string): boolean { return que === this.que && this.vio && !!this.desde; }
}
