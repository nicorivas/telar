// La barra de mensaje: una fila para escribirle a un hilo o a un agente sobre lo que se está mirando, sin abrir una
// ventana. Es la misma instrucción de siempre (web/instruccion.ts: `telar actuar`, el contexto de la cosa más lo escrito) en
// otra forma: una fila al pie de la pantalla, del alto de las barras, con su línea arriba de borde a borde.
//
//   ┌ mensaje ───────────────────────────────────────────────────────────────────────┐
//   │ ● enviado a «Faro» · se le escribió                       (lo último, si hubo)  │
//   │ [◉ Faro ▾]  escríbele a Faro sobre T84 · ⏎ envía, ⇧⏎ línea nueva          [➤]  │
//   └────────────────────────────────────────────────────────────────────────────────┘
//
// · el destino, a la izquierda: su ícono y su nombre en la tinta de lo que es (un hilo en azul, uno nuevo en verde, un
//   agente en violeta: los de ⌘K), y la flecha que dice que se elige otro. Un clic abre la lista (web/mensaje.ts).
// · el campo: una línea que crece hasta ocho al escribir, sin caja, con su línea abajo que toma el acento mientras se
//   escribe (como el buscador). ⏎ envía y ⇧⏎ es una línea nueva, como la caja de la terminal y la de la conversación (la
//   regla de la casa para lo que se escribe en una fila; en una ventana de varias líneas, ⌘⏎).
// · enviar, a la derecha: un ícono en su celda, tenue; con algo escrito, en el acento.
// · lo último que se mandó, arriba del campo mientras no se mande otra cosa: el círculo de lo que está en curso (gira
//   mientras va, lleno al llegar, un aro rojo si falló), a quién fue (su nombre abre su hilo) y cómo le llegó.
//
// Da HTML, como el resto de la página; lo que hace (el estado de cada barra, la lista de destinos, enviar) es de
// web/mensaje.ts, que la atiende en toda la página. Cómo se ve: media/css/mensaje.css, sobre los tokens --mensaje-…
// (tokens.css). Su página en /componentes, «barra de mensaje».

import { esc } from '../estilo';
import { I } from '../web/iconos';
import { circulo } from './circulo';

/** Adónde va lo escrito: el destino elegido, como se ve en la barra. */
export interface DestinoMensaje {
    /** '' es «su hilo» (el de la cosa, que dice telar); `+nuevo`, uno nuevo para ella; o el nombre de un hilo o un agente */
    valor: string;
    /** lo que se ve: el nombre del hilo o del agente, «hilo nuevo» */
    nombre: string;
    icono: string;
    /** su tinta: azul un hilo, verde uno nuevo, violeta un agente (web/iconos.ts, C) */
    color: string;
    /** cómo le llega, en palabras (va en el globo): «su hilo, el de su proyecto», «agente: se le encarga» */
    detalle?: string;
}

/** Lo que pasó con lo último que se mandó. */
export interface DijoMensaje {
    estado: 'enviando' | 'llego' | 'error';
    /** a quién (su nombre, que abre su hilo) */
    destino?: string;
    /** la dirección que abre (`hilo:Faro`, `hilo:Faro@servidor`) */
    direccion?: string;
    /** cómo le llegó, o por qué no: «se le escribió», «por el bus», «telar no contesta» */
    texto: string;
}

export interface PropsMensaje {
    /** de qué es (la dirección de la cosa, o su ref): con ella se encuentra la barra al repintar y se guarda lo escrito */
    llave: string;
    destino: DestinoMensaje;
    /** lo escrito y no mandado */
    texto?: string;
    placeholder: string;
    dijo?: DijoMensaje;
    /** el destino se está buscando (su hilo, que dice telar): la barra se ve, y enviar espera */
    buscando?: boolean;
}

const VERBO: Record<DijoMensaje['estado'], string> = { enviando: 'enviando a', llego: 'enviado a', error: 'no se envió a' };

/** Lo último que se mandó: el círculo de su estado, a quién (un enlace) y cómo. */
export function dijoMensaje(d: DijoMensaje): string {
    const c = d.estado === 'enviando' ? circulo({ mov: 'gira', tam: 'chico' }) : circulo({ tam: 'chico', lleno: d.estado === 'llego' ? 1 : 0 });
    const quien = !d.destino ? '' : d.direccion
        ? ` <a class="mensaje-a" data-mensaje-abrir="${esc(d.direccion)}" title="${esc(`abrir «${d.destino}»`)}">«${esc(d.destino)}»</a>`
        : ` «${esc(d.destino)}»`;
    return `<div class="mensaje-dijo estado-${d.estado}" role="status"><span class="mensaje-dijo-circulo">${c}</span>`
        + `<span>${d.destino ? VERBO[d.estado] : d.estado === 'error' ? 'no se envió' : VERBO[d.estado].replace(/ a$/, '')}${quien}</span>`
        + (d.texto ? `<span class="mensaje-dijo-como">· ${esc(d.texto)}</span>` : '') + '</div>';
}

/** La barra, en HTML. */
export function barraMensaje(p: PropsMensaje): string {
    const d = p.destino;
    const globo = `a quién: ${d.nombre}${d.detalle ? ` (${d.detalle})` : ''}. Un clic, para elegir otro: su hilo, uno nuevo, otro hilo o un agente`;
    const listo = !!p.texto?.trim();
    return `<div class="mensaje${p.buscando ? ' buscando' : ''}" data-mensaje="${esc(p.llave)}">`
        + (p.dijo ? dijoMensaje(p.dijo) : '')
        + '<div class="mensaje-fila">'
        + `<a class="mensaje-destino" data-mensaje-destino role="button" tabindex="0" aria-haspopup="listbox" title="${esc(globo)}" style="--mensaje-c: var(--${esc(d.color)})">`
        + `<span class="i mensaje-destino-icono">${d.icono}</span><span class="mensaje-destino-nombre">${esc(d.nombre)}</span>`
        + `<span class="i mensaje-destino-mas">${I.abierto}</span></a>`
        + `<textarea class="mensaje-campo" rows="1" aria-label="${esc(p.placeholder)}" placeholder="${esc(p.placeholder)}">${esc(p.texto ?? '')}</textarea>`
        + `<a class="mensaje-enviar${listo ? ' listo' : ''}" data-mensaje-enviar role="button" tabindex="0" aria-label="enviar" title="enviar (⏎)"><span class="i">${I.enviar}</span></a>`
        + '</div></div>';
}
