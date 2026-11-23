// La ventana de mundos: para cambiar de mundo (⌘M, un clic en el mundo de la banda, «cambiar de mundo» en ⌘K). Cada
// mundo de la configuración es una tarjeta, y «ambos» la última: arriba su arte, un dibujo de letras animado
// (componentes/arte.ts), y abajo su nombre en su color, su horario en una línea y si es el de ahora (y por qué: su
// horario, fuera de horario, a mano). Elegir una pone ese mundo como lo hace la banda (web/mundo.ts, `poner`); en el pie,
// volver al horario (si se eligió a mano), editar los mundos (⚙ mundos) y cerrar.
//
//   mundos  lo elegido a mano dura hasta el próximo cambio del horario
//   ──────────────────────────┬──────────────────────────┬──────────────────────────
//     (el telar tejiendo)     │   (el cielo de noche)    │   (los dos que giran)
//   ──────────────────────────┼──────────────────────────┼──────────────────────────
//   1 trabajo        ● ahora  │ 2 personal               │ 3 ambos
//   lun–vie 9:00–19:00        │ fuera de todo horario    │ todo junto, en tandas
//   por su horario, hasta …   │ desde las 19:00          │
//   ──────────────────────────┴───────────┬──────────────┴──────┬────────────────────
//   ← → recorrer · 1–3 elegir · ⏎ poner   │ h volver al horario │ e editar │ ⎋ cerrar
//
// Las líneas van de borde a borde: entre tarjetas, de la cabecera al pie; la que aparta el arte del texto cruza la ventana
// entera (todos los artes miden lo mismo). Sin esquinas redondeadas; cada tarjeta, en el color de su mundo: el arte tenue,
// salvo el del mundo de ahora; con el mouse o el foco encima se ilumina, el arte se acelera, un barrido la cruza y el
// dibujo se inclina apenas hacia el puntero (media/css/mundos.css). En el teléfono, una bajo otra.
//
// Da HTML; lo vivo (abrirla, las teclas, animar el arte, elegir) es web/mundos-ventana.ts. El catálogo la muestra en
// /componentes#mundos, con los artes y un lugar para probar uno nuevo.

import { esc } from '../estilo';
import { I } from '../web/iconos';
import { cancelar, pieBotones, type Boton } from './boton';
import { circulo } from './circulo';
import { cuando, decirTramo, type Mundo, type MundoPuesto } from './modos-mundos';
import { arte, arteDeMundo, cuadro } from './arte';
import { ventana, type PropsVentana } from './ventana';

/** Lo que dice una tarjeta. */
export interface TarjetaMundo {
    /** la clave del mundo ("" ambos) */
    clave: string;
    nombre: string;
    /** su tinta (una de `C`); sin ella, el color del texto (ambos) */
    color?: string;
    /** la clave de su arte */
    arte: string;
    /** cuándo rige, en una línea */
    horario: string;
    /** si es el de ahora: por qué y hasta cuándo; si no, desde cuándo, si es el que viene */
    estado: string;
    /** el de ahora */
    puesto: boolean;
    /** la tecla que lo elige (1…9) */
    tecla?: string;
}

/** Cuántas columnas: todas en una fila hasta cuatro; más, en filas parejas (la última se estira). */
export const columnas = (n: number): number => (n <= 4 ? Math.max(1, n) : Math.ceil(n / Math.ceil(n / 4)));

/** Las tarjetas: cada mundo, en su orden, y ambos al final. */
export function tarjetasDeMundos(p: MundoPuesto, mundos: readonly Mundo[], ahora: Date, fuera = ''): TarjetaMundo[] {
    const conHorario = mundos.some(m => m.horario?.length);
    const estado = (clave: string): string => {
        if (p.mundo === clave) {
            const por = p.por === 'a-mano' ? 'a mano' : p.por === 'horario' ? 'por horario' : p.por === 'fuera' ? 'fuera de horario' : '';
            const hasta = p.hasta ? `hasta ${cuando(p.hasta, ahora)}` : '';
            return [por, hasta].filter(Boolean).join(', ');
        }
        return p.luego === clave && p.hasta ? `desde ${cuando(p.hasta, ahora)}` : '';
    };
    const lista = mundos.map(m => ({
        clave: m.clave, nombre: m.nombre, color: m.color, arte: arteDeMundo(m).clave, puesto: p.mundo === m.clave, estado: estado(m.clave),
        horario: [m.horario?.length ? m.horario.map(decirTramo).join(', ') : '', conHorario && m.clave === fuera ? 'fuera de todo horario' : '']
            .filter(Boolean).join(' · ') || (conHorario ? 'sin horario: solo a mano' : 'a mano'),
    }));
    lista.push({ clave: '', nombre: 'ambos', color: '', arte: arteDeMundo(undefined).clave, puesto: p.mundo === '', estado: estado(''),
        horario: `todo junto, en tandas${conHorario && !fuera ? ' · fuera de todo horario' : ''}` });
    return lista.map((t, i) => ({ ...t, tecla: i < 9 ? String(i + 1) : undefined }));
}

/** Una tarjeta. `estado`: el del catálogo, puesto a mano (en la página lo dan :hover y :focus). `t`: el instante del
 *  cuadro que lleva al dibujarse (lo anima web/arte-vivo.ts). */
export function tarjetaMundo(m: TarjetaMundo, o: { indice?: number; estado?: 'hover' | 'foco'; t?: number; span?: number } = {}): string {
    const a = arte(m.arte) ?? arteDeMundo(m.clave ? { clave: m.clave } : undefined);
    const color = m.color ? ` style="--mundo-c: var(--${esc(m.color)})"` : '';
    const ayuda = `${m.nombre}${m.puesto ? ' (el de ahora)' : ''}\n${m.horario}${m.estado ? `\n${m.estado}` : ''}\nclic${m.tecla ? ` o ${m.tecla}` : ''}: ponerlo`;
    const ahora = m.puesto ? `<span class="mt-ahora">${circulo({ tam: 'chico', lleno: 1 })}<span>ahora</span></span>` : '';
    return `<button type="button" class="mt-tarjeta${m.puesto ? ' puesto' : ''}${m.clave ? '' : ' ambos'}${o.span ? ` span-${o.span}` : ''}${o.estado ? ` es-${o.estado}` : ''}"`
        + ` data-mundo="${esc(m.clave)}"${o.indice !== undefined ? ` data-indice="${o.indice}"` : ''} aria-pressed="${m.puesto}"`
        + ` title="${esc(ayuda)}"${color}>`
        + `<span class="mt-lienzo" aria-hidden="true"><span class="mt-arte" data-arte="${esc(a.clave)}">${esc(cuadro(a, o.t ?? 0))}</span>`
        + '<span class="mt-barrido"></span></span>'
        + '<span class="mt-texto">'
        + `<span class="mt-linea">${m.tecla ? `<span class="mt-tecla">${esc(m.tecla)}</span>` : ''}<span class="mt-nombre">${esc(m.nombre)}</span>${ahora}</span>`
        + `<span class="mt-horario">${esc(m.horario)}</span>`
        + `<span class="mt-estado">${esc(m.estado || ' ')}</span>`
        + '</span></button>';
}

/** Las tarjetas en su grilla: cuántas columnas (`--mt-cols`, y `cols-N` para el ancho de la ventana) y, si la última
 *  fila queda corta, su última tarjeta se estira hasta el borde (`span-N`: así las líneas llegan siempre de borde a
 *  borde). */
export function grillaMundos(ts: readonly TarjetaMundo[], o: { estados?: Record<number, 'hover' | 'foco'>; t?: number } = {}): string {
    const cols = columnas(ts.length);
    const sobra = ts.length % cols;
    return `<div class="mt-grilla cols-${cols}" style="--mt-cols: ${cols}" role="group" aria-label="mundos">`
        + ts.map((m, i) => tarjetaMundo(m, { indice: i, estado: o.estados?.[i], t: o.t,
            span: sobra && i === ts.length - 1 ? cols - sobra + 1 : undefined })).join('')
        + '</div>';
}

/** Los botones del pie: volver al horario (apagado si ya rige), editar los mundos y cerrar. */
export function botonesMundos(aMano: boolean): Boton[] {
    return [
        { texto: 'volver al horario', accion: 'horario', tecla: 'h', color: 'azul', estado: aMano ? 'normal' : 'deshabilitado',
            ayuda: aMano ? 'soltar lo elegido a mano: rige el horario de cada mundo' : 'ya rige el horario' },
        { texto: 'editar', accion: 'editar', tecla: 'e', color: 'amarillo', ayuda: '⚙ mundos: qué es de cada uno, su horario, su color y su arte' },
        cancelar('cerrar'),
    ];
}

/** Lo que lleva la ventana (para `abrirVentana`, web/ventana.ts): el título con el planeta, la grilla y el pie. */
export function propsVentanaMundos(ts: readonly TarjetaMundo[], o: { aMano: boolean; estados?: Record<number, 'hover' | 'foco'>; t?: number }): PropsVentana {
    const n = Math.min(9, ts.length);
    const teclas = `<span class="mt-teclas">← → recorrer · ${n > 1 ? `1–${n}` : '1'} elegir · ⏎ poner</span>`;
    return {
        titulo: 'mundos', iconos: `<span class="i mt-planeta">${I.planeta}</span>`, clase: 'ventana-mundos',
        ayuda: 'lo que se ve en la página; elegido a mano, dura hasta el próximo cambio del horario',
        cuerpo: grillaMundos(ts, o),
        pie: pieBotones(botonesMundos(o.aMano), { izq: teclas }),
    };
}

/** La ventana entera, en HTML (el catálogo). */
export const ventanaMundos = (ts: readonly TarjetaMundo[], o: { aMano: boolean; estados?: Record<number, 'hover' | 'foco'>; t?: number }): string =>
    ventana(propsVentanaMundos(ts, o));
