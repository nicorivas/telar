// Cómo se ve la terminal de un hilo (`[terminal]` de la configuración): hasta cuántas columnas de ancho (0: todo lo
// que quepa), dónde va dentro de su vista (izquierda, centro, derecha) y qué hay alrededor (el telar tenue de
// siempre, nada, un color, una imagen o un módulo con `[fondo]`). Se lee una vez de la configuración; ⚙ terminal lo
// cambia y avisa, y cada terminal abierta lo vuelve a aplicar sin cerrarse.

import * as cli from '../cli';
import * as modos from './modos';

export interface Aspecto { columnas: number; posicion: 'izquierda' | 'centro' | 'derecha'; fondo: string }

const DE_FABRICA: Aspecto = { columnas: 130, posicion: 'centro', fondo: 'telar' };
let actual: Aspecto = { ...DE_FABRICA };
let leido: Promise<void> | undefined;
const oyentes = new Set<() => void>();

/** Lo de ahora: lo del modo puesto (telar.modos, que para «estándar» trae `[terminal]`), o mientras no llegan los
 *  modos, lo de la configuración (de fábrica hasta que se lea). */
export function aspecto(): Aspecto {
    if (!modos.listos()) return actual;
    const c = modos.valor('columnas'), p = modos.valor('posicion'), f = modos.valor('fondo');
    return {
        columnas: typeof c === 'number' ? c : actual.columnas,
        posicion: (p === 'izquierda' || p === 'centro' || p === 'derecha') ? p : actual.posicion,
        fondo: typeof f === 'string' && f ? f : actual.fondo,
    };
}

// cambiar de modo (o un cambio a mano) también cambia la terminal
modos.alCambiar(() => { for (const f of oyentes) f(); });

/** Leerlo de la configuración, una vez; avisa a las terminales cuando llega. */
export function leer(): Promise<void> {
    leido ??= cli.config().then(r => {
        const t = (r.datos as { terminal?: Partial<Aspecto> } | undefined)?.terminal;
        if (t) cambiar({ ...actual, ...t });
    }).catch(() => undefined);
    return leido;
}

/** Cambiarlo aquí (lo que se acaba de escribir en la configuración) y avisar a las terminales abiertas. */
export function cambiar(nuevo: Aspecto): void {
    actual = nuevo;
    for (const f of oyentes) f();
}

/** Que una terminal se entere de los cambios; devuelve cómo dejar de escuchar. */
export function alCambiar(f: () => void): () => void {
    oyentes.add(f);
    return () => oyentes.delete(f);
}

/** El fondo, en piezas que la terminal sabe dibujar. */
export function fondoDe(a: Aspecto): { tipo: 'telar' | 'ninguno' | 'color' | 'imagen' | 'modulo'; valor: string } {
    const f = a.fondo || 'telar';
    if (f === 'telar' || f === 'ninguno') return { tipo: f, valor: '' };
    if (f.startsWith('#')) return { tipo: 'color', valor: f };
    if (f.startsWith('imagen:')) {
        const v = f.slice('imagen:'.length);
        // una de internet tal cual; una de la máquina, la sirve la API
        return { tipo: 'imagen', valor: /^https?:\/\//.test(v) ? v : `/api/terminal/imagen?v=${encodeURIComponent(v)}` };
    }
    return { tipo: 'modulo', valor: `/api/terminal/fondo/?m=${encodeURIComponent(f)}` };
}
