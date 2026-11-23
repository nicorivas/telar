// Las señales: cómo dice cada vista el estado de una cosa, sacado de la gramática visual (componentes/gramatica.ts,
// «derivadas»). Un solo lugar: la barra de hilos, el dashboard, el catálogo y la lámina del ítem piden aquí la pieza de
// «terminó» o la de una prioridad, y ninguna vista arma la suya. Todas son círculos (componentes/circulo.ts), de los
// tres tamaños: un estado no se dice con un ícono de la letra (esos son para las acciones y las clases de cosas).

import { circulo, type Circulo } from './circulo';
import type { Pieza, Tono } from './item';

export type Atencion = 'trabajando' | 'espera' | 'termino';

/** La atención de un hilo o de un agente, grande porque es lo principal de su fila: trabajando, lleno («hay»: algo pasa
 *  ahora); te espera, un aro («falta» lo tuyo); terminó sin que lo hayas visto, un aro con algo lleno adentro («con
 *  contenido»: dejó algo que ver). Terminó y ya lo viste: nada, no queda nada que decir. */
export const ATENCION: Record<Atencion, Circulo> = { trabajando: {}, espera: { lleno: 0 }, termino: { figura: 'diana' } };

const conAyuda = (p: Pieza, ayuda?: string): Pieza => (ayuda ? { ...p, ayuda } : p);

/** La pieza de una atención; `null` si no hay o si ya se vio lo que dejó (la ranura queda vacía, sin nada que decir). */
export function atencion(at: string, visto = false, ayuda?: string): Pieza | null {
    const c = ATENCION[at as Atencion];
    return c && !visto ? conAyuda({ circulo: c, tono: at as Tono }, ayuda) : null;
}

/** La prioridad, chica porque acompaña al estado; su llenado dice cuánto importa: alta llena, media a medias, baja un
 *  aro. Sin prioridad, un punto: la prioridad siempre se dice. */
export function prioridad(p: number | null | undefined, tenue = false, ayuda?: string): Pieza {
    const n = p === 1 || p === 2 || p === 3 ? p : 0;
    const c: Circulo = n === 0 ? { tam: 'punto' } : { tam: 'chico', lleno: { 1: 1, 2: .5, 3: 0 }[n] };
    return conAyuda({ circulo: c, tono: tenue ? 'tenue' : `p${n}` as Tono }, ayuda);
}

/** La prioridad urgente de una tarea (P0): llena como la alta, en rojo. La de un hilo no llega a urgente. */
export const urgente = (ayuda?: string): Pieza => conAyuda({ circulo: { tam: 'chico' }, tono: 'peligro' }, ayuda);

/** Una tarea con estrella: un aro con un punto al medio («señalado»: la elegiste entre las demás), en el color de
 *  cuidado. */
export const estrella = (ayuda?: string): Pieza => conAyuda({ circulo: { figura: 'centro' }, tono: 'atencion' }, ayuda);

/** La fase de un proyecto: cuánto avanzó, de a cuartos («en parte»: preparación es un aro, cerrado está lleno), grande
 *  porque es lo principal de su fila. Si algo no cuadra (venció sin cerrarse, más horas que las del plan), en el color
 *  de cuidado; cerrado, tenue (ya pasó). */
export function fase(avance: number, aviso = '', ayuda?: string): Pieza {
    const lleno = Math.round(Math.max(0, Math.min(1, avance)) * 4) / 4;
    const tono: Tono | undefined = aviso ? 'atencion' : lleno >= 1 ? 'tenue' : undefined;
    return conAyuda({ circulo: { lleno }, ...(tono ? { tono } : {}) }, ayuda);
}

/** Un proyecto pausado: un aro («falta»: detenido), tenue porque no está vigente. */
export const pausado = (ayuda?: string): Pieza => conAyuda({ circulo: { lleno: 0 }, tono: 'tenue' }, ayuda);
/** Un proyecto terminado al que le falta cerrarse: lleno («hecho»), pleno porque todavía pide algo (el cierre). */
export const terminado = (ayuda?: string): Pieza => conAyuda({ circulo: { lleno: 1 } }, ayuda);

/** Las clases de estado de una iniciativa (telar.iniciativas.CLASES): de la idea a terminada, o en pausa o descartada. */
export type ClaseEstado = 'idea' | 'preparacion' | 'curso' | 'pausa' | 'terminada' | 'descartada';
export const CLASES_ESTADO: readonly ClaseEstado[] = ['idea', 'preparacion', 'curso', 'pausa', 'terminada', 'descartada'];

/** El estado de una iniciativa, chico porque acompaña a su palabra (en su columna; la ranura es de su peso). Cuánto
 *  avanzó y si sigue: una idea, un punto en el acento («está»: todavía nada); en preparación, un cuarto; en curso, a
 *  medias en el color de trabajando (pasa ahora); en pausa, un aro tenue («falta»: detenida, como un proyecto pausado);
 *  terminada, llena en el de lo bueno (hecho); descartada, llena y apagada (ya no aplica). Uno que no está en el
 *  vocabulario, un aro en el color de cuidado; uno del vocabulario sin clase, un punto tenue. */
export const ESTADO_INICIATIVA: Record<ClaseEstado, Pieza> = {
    idea: { circulo: { tam: 'punto' }, tono: 'acento' },
    preparacion: { circulo: { tam: 'chico', lleno: .25 } },
    curso: { circulo: { tam: 'chico', lleno: .5 }, tono: 'trabajando' },
    pausa: { circulo: { tam: 'chico', lleno: 0 }, tono: 'tenue' },
    terminada: { circulo: { tam: 'chico' }, tono: 'exito' },
    descartada: { circulo: { tam: 'chico' }, tono: 'apagado' },
};
export function estadoIniciativa(clase: ClaseEstado | undefined, fuera = false, ayuda?: string): Pieza {
    const p: Pieza = fuera ? { circulo: { tam: 'chico', lleno: 0 }, tono: 'atencion' }
        : clase ? ESTADO_INICIATIVA[clase] : { circulo: { tam: 'punto' }, tono: 'tenue' };
    return conAyuda(p, ayuda);
}

/** Un hilo dormido (telar.dormir): su agente se cerró por estar quieto y su ventana espera, en su lugar; abrirlo o
 *  escribirle lo despierta. Un aro («falta»: detenido, como un proyecto pausado), tenue porque su agente no corre; si
 *  terminó y no lo has visto, su diana («dejó algo que ver»), tenue igual. Grande: es el estado de su fila. */
export const dormido = (sinVer = false, ayuda?: string): Pieza =>
    conAyuda({ circulo: sinVer ? { figura: 'diana' } : { lleno: 0 }, tono: 'tenue' }, ayuda);
/** Un hilo de una máquina fuera de línea (telar.alcance): no se sabe en qué anda, ni si sigue vivo o dormido. Un aro chico
 *  y tenue, el de «sin noticias» (`presente(false)`), en la ranura de su estado: lo que dijo antes de irse no se muestra
 *  como si fuera de ahora. */
export const inalcanzable = (ayuda?: string): Pieza => conAyuda({ circulo: { tam: 'chico', lleno: 0 }, tono: 'tenue' }, ayuda);
/** Vive en otra máquina: un aro chico con un punto afuera («en otra parte»: aquí no, allá sí). */
export const remoto = (ayuda?: string): Pieza => conAyuda({ circulo: { figura: 'satelite' }, tono: 'remoto' }, ayuda);
/** Viaja a otra máquina: el mismo satélite, y el punto da la vuelta («en camino»). */
export const viaja = (ayuda?: string): Pieza => conAyuda({ circulo: { figura: 'satelite', mov: 'gira' }, tono: 'remoto' }, ayuda);
/** Se va (se cierra, se archiva): se vacía, en tenue. */
export const sale = (ayuda?: string): Pieza => conAyuda({ circulo: { mov: 'vacia' }, tono: 'tenue' }, ayuda);
/** Público: dos aros que se cruzan («comparte»: lo ven otros). */
export const publico = (ayuda?: string): Pieza => conAyuda({ circulo: { figura: 'enlace' }, tono: 'tenue' }, ayuda);
/** Algo nuevo: un punto («está»), que no interrumpe. */
export const nuevo = (ayuda?: string): Pieza => conAyuda({ circulo: { tam: 'punto' }, tono: 'exito' }, ayuda);
/** Un aviso del sistema donde la franja de avisos no se ve (el teléfono viendo un hilo, foco): un punto («está») en el
 *  color de su nivel, junto al botón que la muestra. Sin conexión o un problema, rojo; una falla, el de cuidado; un aviso,
 *  el acento (componentes/franja.ts). */
export const avisoSistema = (nivel: 'conexion' | 'problema' | 'falla' | 'aviso' | 'nota', ayuda?: string): Pieza =>
    conAyuda({ circulo: { tam: 'punto' }, tono: ({ conexion: 'peligro', problema: 'peligro', falla: 'atencion', aviso: 'acento', nota: 'tenue' } as const)[nivel] }, ayuda);
/** Alguien que está (al día, vivo) o del que no hay noticias: chico, porque lo principal de su fila es su nombre. */
export const presente = (si: boolean, ayuda?: string): Pieza => conAyuda(si ? { circulo: { tam: 'chico' } } : { circulo: { tam: 'chico', lleno: 0 }, tono: 'tenue' }, ayuda);

/** Una corrida de un proceso periódico, chica y sobre la línea de su proceso («un momento», en el calendario):
 *  lo que ya pasó, lleno y tenue (hecho); lo que viene, un aro (por hacer), en el color de cuidado si llega a la
 *  casilla de un agente junto con otro (`cola`: espera su turno); falló, un aro rojo; le tocaba y no hay rastro, un
 *  aro de cuidado; se saltó, un aro tenue; corriendo ahora, lleno en el color de trabajando; pausado, un aro apagado;
 *  una hora de antes de todo registro, un punto apagado (estaba en el horario, de cómo salió no se sabe). */
export function corrida(estado: string, cola = false, ayuda?: string): Pieza {
    const aro = (tono?: Tono): Pieza => ({ circulo: { tam: 'chico', lleno: 0 }, ...(tono ? { tono } : {}) });
    const p: Pieza = estado === 'bien' || estado === 'corrio' ? { circulo: { tam: 'chico' }, tono: 'tenue' }
        : estado === 'corriendo' ? { circulo: { tam: 'chico' }, tono: 'trabajando' }
        : estado === 'fallo' ? aro('peligro')
        : estado === 'falto' ? aro('atencion')
        : estado === 'saltado' ? aro('tenue')
        : estado === 'pausado' ? aro('apagado')
        : estado === 'sin-registro' ? { circulo: { tam: 'punto' }, tono: 'apagado' }
        : aro(cola ? 'atencion' : undefined);
    return conAyuda(p, ayuda);
}

/** Cómo está un proceso periódico, grande porque es lo principal de su fila: corriendo, lleno (trabajando); pausado,
 *  un aro tenue; su última corrida falló, un aro rojo; salió bien, lleno y tenue (ya pasó); nunca corrió, un punto. */
export function periodico(p: { activo: boolean; ultima: { corriendo?: boolean; codigo?: number; inicio?: string } }, ayuda?: string): Pieza {
    const c: Pieza = p.ultima.corriendo ? { circulo: {}, tono: 'trabajando' }
        : !p.activo ? { circulo: { lleno: 0 }, tono: 'tenue' }
        : p.ultima.codigo !== undefined && p.ultima.codigo !== 0 ? { circulo: { lleno: 0 }, tono: 'peligro' }
        : p.ultima.inicio ? { circulo: {}, tono: 'tenue' }
        : { circulo: { tam: 'punto' }, tono: 'apagado' };
    return conAyuda(c, ayuda);
}

/** Una señal suelta, en HTML, para ponerla en un texto (fuera de un ítem). */
export const enLinea = (p: Pieza | null): string =>
    p?.circulo ? `<span class="senal${p.tono ? ` tono-${p.tono}` : ''}"${p.ayuda ? ` title="${atributo(p.ayuda)}"` : ''}>${circulo(p.circulo)}</span>` : '';
const atributo = (s: string) => s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
