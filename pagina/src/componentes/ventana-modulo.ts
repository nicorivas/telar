// La ventana que pide un módulo (`[ventanas]` de su modulo.toml; telar.servicios.ventanas): lo que llegó a un chat de foco,
// para responder o aplazar sin ir a su pestaña. Es la ventana de la casa (componentes/ventana.ts, abierta con
// `abrirVentana`): arriba el título con su ícono y, a la derecha, lo que lleva a otra parte (abrir el chat, mandarlo a un
// agente, quitar el foco); en el cuerpo, las líneas (unas pocas de antes, tenues, y lo nuevo bajo una raya con el punto
// de no leídos) y la caja de responder; abajo, el pie con teclas: ⌘⏎ envía y cada plazo tiene su número; ⎋ hace lo que la
// ventana dice (`escape`: aplazar lo más corto, nunca darlo por visto). Lo obvio va como ícono (enviar, el basurero, abrir
// afuera, aplazar: el `icono` de cada acción, que da el módulo), con su nombre en el title y el aria-label; lo que no, en
// palabras. Lo que muestra lo escribe el módulo y lo dijeron otras personas: todo va escapado. La abre y la atiende web/ventanas.ts; aquí, solo el HTML, para probarlo sin DOM (pruebas/ventanas.mjs).

import { esc } from '../estilo';
import type { PropsVentana } from './ventana';
import { boton, pieBotones, type Boton } from './boton';
import type { JsonAccionVentana, JsonBorradorVentana, JsonLineaVentana, JsonVentana } from '../cli';
import { I } from '../web/iconos';

/** Lo que se respondió desde la ventana y en qué va: enviándose, hecho, o lo que falló. */
export interface Envio { texto: string; estado: 'enviando' | 'hecho' | 'falla'; error?: string }

export interface OpcionesVentanaModulo {
    /** cuántas esperan en total (esta incluida): «2 más esperando» */
    cola?: number;
    /** abierta sin el foco del teclado (alguien escribía en otra parte): lo dice, y un clic la toma */
    quieta?: boolean;
    envio?: Envio;
    /** lo que no se pudo (un botón que falló), en rojo bajo la caja */
    falla?: string;
    /** mientras corre algo: los botones apagados */
    ocupada?: boolean;
    /** la hora de ahora (para decir «hoy» o el día de una línea) */
    ahora?: number;
}

/** Los íconos de la cabecera (los de la letra de la página, web/iconos.ts): el foco, una persona, un grupo, un aviso. */
const ICONO: Record<string, string> = { persona: I.persona, grupo: I.subagentes, aviso: I.campana, '': I.foco };
const FOCO = I.foco;

/** El ícono de una acción por su nombre en web/iconos.ts (`icono = "aplazar"`); "" si no es uno de la casa: entonces va
 *  la palabra. */
export function iconoDeAccion(nombre: string | undefined): string {
    return nombre && Object.prototype.hasOwnProperty.call(I, nombre) ? (I as Record<string, string>)[nombre] : '';
}

/** «10:42» si es de hoy; «22-nov 18:03» si no. */
export function horaDeLinea(ts: string, ahora = Date.now()): string {
    const d = new Date(ts);
    if (Number.isNaN(d.getTime())) return '';
    const hh = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
    if (d.toDateString() === new Date(ahora).toDateString()) return hh;
    const mes = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'][d.getMonth()];
    return `${d.getDate()}-${mes} ${hh}`;
}

function linea(l: JsonLineaVentana, ahora: number): string {
    const clase = `vm-linea${l.nueva ? ' nueva' : ''}${l.mia ? ' mia' : ''}`;
    return `<div class="${clase}"><span class="vm-hora">${esc(horaDeLinea(l.ts, ahora))}</span>`
        + `<span class="vm-texto"><span class="vm-de">${esc(l.de)}:</span> ${l.marca ? `<span class="vm-marca">${esc(l.marca)}</span> ` : ''}`
        + `${esc(l.texto)}</span></div>`;
}

/** La raya donde empieza lo nuevo: una línea con el punto de no leídos al medio. */
const RAYA = `<div class="vm-raya" role="separator" aria-label="lo nuevo" title="lo nuevo"><span class="i">${I.lleno}</span></div>`;

/** Las líneas, con una raya donde empieza lo nuevo. */
export function lineasHtml(v: Pick<JsonVentana, 'lineas'>, ahora = Date.now()): string {
    const i = v.lineas.findIndex(l => l.nueva);
    return v.lineas.map((l, j) => (j === i && i > 0 ? RAYA : '') + linea(l, ahora)).join('');
}

/** Lo respondido, al final de las líneas: «enviando…», «enviado» o por qué no salió. */
function envioHtml(e: Envio | undefined): string {
    if (!e) return '';
    const estado = e.estado === 'enviando' ? 'enviando…' : e.estado === 'hecho' ? 'enviado' : `no salió: ${e.error || 'falló'}`;
    return `<div class="vm-linea mia vm-envio ${e.estado}"><span class="vm-hora">${e.estado === 'hecho' ? '✓' : '···'}</span>`
        + `<span class="vm-texto"><span class="vm-de">yo:</span> ${esc(e.texto)} <span class="vm-estado">(${esc(estado)})</span></span></div>`;
}

/** Los borradores que esperan que la persona los apruebe (los de un agente para este chat): el ícono de borrador (el ⩥ de
 *  la fila en la pestaña) con quién lo pidió y, tenue, por qué; el texto (editable: lo editado va al aprobarlo), y enviar
 *  (el ícono; fuera de su ventana, con la hora a la que sale: «⩥ 08:30») o descartar (el basurero). Cada caja lleva
 *  `data-vb` (su id) y los botones `data-vm` («aprobar:0», «descartar:0»). */
export function borradoresHtml(bs: JsonBorradorVentana[] | undefined, o: Pick<OpcionesVentanaModulo, 'ocupada'> = {}): string {
    if (!bs?.length) return '';
    const apagado = o.ocupada ? { estado: 'deshabilitado' as const } : {};
    return '<div class="vm-borradores">' + bs.map((b, i) => {
        const de = b.de || 'un agente';
        const enviar = b.sale ? `aprobar: sale a las ${b.sale}` : 'enviar';
        return `<div class="vm-borrador" data-vb="${esc(b.id)}">`
            + `<div class="vm-bcab" title="${esc(`borrador de ${de}${b.motivo ? `: ${b.motivo}` : ''}; espera que lo apruebes`)}">`
            + `<span class="i" aria-label="borrador de">${I.enviar}</span> ${esc(de)}${b.motivo ? ` <span class="vm-bmotivo">· ${esc(b.motivo)}</span>` : ''}</div>`
            + (b.editable ? `<textarea class="vm-btexto" rows="2"${o.ocupada ? ' disabled' : ''}>${esc(b.texto)}</textarea>` : `<div class="vm-btexto">${esc(b.texto)}</div>`)
            + '<div class="vm-bacc">'
            + (b.aprobar ? boton({ texto: enviar, simbolo: I.enviar, ...(b.sale ? { corto: b.sale } : {}), color: 'verde', datos: { vm: `aprobar:${i}` },
                ayuda: `${enviar}: lo aprueba con lo escrito y sale como lo dejó quien lo pidió (con su firma, en su horario)`, ...apagado }) : '')
            + (b.descartar ? boton({ texto: 'descartar', simbolo: I.descartar, tono: 'peligro', datos: { vm: `descartar:${i}` },
                ayuda: 'descartar: que no salga', ...apagado }) : '')
            + '</div></div>';
    }).join('') + '</div>';
}

/** Lo que va en lugar de la palabra de una acción con ícono (`icono` de la casa, y su `corto`); nada si no tiene. */
function simboloDe(a: Pick<JsonAccionVentana, 'icono' | 'corto'>): Pick<Boton, 'simbolo' | 'corto'> {
    const simbolo = iconoDeAccion(a.icono);
    return simbolo ? { simbolo, ...(a.corto ? { corto: a.corto } : {}) } : {};
}

/** Los botones del pie: enviar (⌘⏎ y el ícono de enviar, si se puede responder) y los de la ventana que van abajo, con
 *  su tecla (el de ⎋, con ⎋) y su ícono si lo declaran (aplazar: la campana dormida y el plazo, «15m»). Cada uno lleva
 *  `data-vm` (su índice, o «responder»): los atiende web/ventanas.ts, no abrirVentana. */
export function botonesDelPie(v: JsonVentana, o: OpcionesVentanaModulo = {}): Boton[] {
    const apagado = o.ocupada ? { estado: 'deshabilitado' as const } : {};
    const b: Boton[] = [];
    if (v.responder) b.push({ texto: 'enviar', simbolo: I.enviar, tecla: '⌘⏎', color: 'verde', datos: { vm: 'responder' },
        ayuda: 'enviar: responder con lo escrito (⌘⏎)', ...apagado });
    v.acciones.forEach((a, i) => {
        if (a.en !== 'pie') return;
        // el de ⎋ (`escape`) lo dice en su celda: ⎋ lo hace (el <dialog> lo atiende, web/ventanas.ts); los demás, su tecla
        const tecla = i === v.escape ? '⎋' : a.tecla;
        b.push({ texto: a.texto, ...simboloDe(a), ...(tecla ? { tecla } : {}), datos: { vm: String(i) }, tono: 'accion',
            ...(i === v.escape ? { ayuda: `${a.texto} (⎋, o un clic fuera): vuelve a salir entonces` } : {}), ...apagado });
    });
    return b;
}

/** Lo que va de la cabecera: con ícono, el ícono (y su `corto`), con la palabra en el title y el aria-label; sin, la
 *  palabra. Quitar, en rojo al pasar el mouse. */
function herramienta(a: JsonAccionVentana, i: number, ocupada: boolean): string {
    const g = iconoDeAccion(a.icono);
    const clase = `vm-herr${g ? ' con-icono' : ''}${/^quitar/i.test(a.texto) ? ' quitar' : ''}`;
    const dentro = g ? `<span class="i">${g}</span>${a.corto ? esc(a.corto) : ''}` : esc(a.texto);
    return `<a class="${clase}" role="button" data-vm="${i}"${g ? ` title="${esc(a.texto)}" aria-label="${esc(a.texto)}"` : ''}`
        + `${ocupada ? ' aria-disabled="true"' : ''}>${dentro}</a>`;
}

/** Lo que va pegado al título, en íconos con su número y lo que dicen en el title: cuántos nuevos (el punto de no
 *  leídos), cuántas más esperan (las capas) y, si salió quieta, el teclado tachado (no te lo quita; un clic la toma). */
export function juntoHtml(v: Pick<JsonVentana, 'nuevos'>, o: Pick<OpcionesVentanaModulo, 'cola' | 'quieta'> = {}): string {
    const n = typeof v.nuevos === 'number' && v.nuevos > 0 ? v.nuevos : 0;
    const cola = (o.cola ?? 1) - 1;
    return (n ? `<span class="vm-nuevos" title="${n} ${n === 1 ? 'nuevo' : 'nuevos'}"><span class="i">${I.lleno}</span>${n}</span>` : '')
        + (cola > 0 ? `<span class="vm-cola" title="${cola} más ${cola === 1 ? 'espera' : 'esperan'}"><span class="i">${I.capas}</span>${cola}</span>` : '')
        + (o.quieta ? `<span class="vm-quieta i" title="clic para responder: no te quita el teclado" aria-label="no te quita el teclado: un clic para responder">${I.sinTeclado}</span>` : '');
}

/** Lo que va en la ventana (`ventana()` de componentes/ventana.ts). */
export function propsVentanaModulo(v: JsonVentana, o: OpcionesVentanaModulo = {}): PropsVentana {
    const ahora = o.ahora ?? Date.now();
    const herramientas = v.acciones.map((a, i) => (a.en === 'cabecera' ? herramienta(a, i, !!o.ocupada) : '')).join('');
    const r = v.responder;
    const caja = r ? `<div class="vm-responder"><textarea class="vm-caja" rows="2" maxlength="${r.largo}" placeholder="${esc(r.placeholder || 'responder…')}"`
        + ` spellcheck="true"${o.ocupada ? ' disabled' : ''}></textarea></div>` : '';
    return {
        lugar: 'centrada', clase: 'ventana-modulo', titulo: v.titulo,
        iconos: `<span class="i vm-icono" title="de foco">${FOCO}</span>${v.icono ? `<span class="i vm-tipo">${ICONO[v.icono] ?? ''}</span>` : ''}`,
        ...(v.ayuda ? { ayuda: v.ayuda } : {}), junto: juntoHtml(v, o), herramientas: herramientas ? `<span class="vm-herramientas">${herramientas}</span>` : undefined,
        cuerpo: `<div class="vm-lineas">${lineasHtml(v, ahora)}${envioHtml(o.envio)}</div>${borradoresHtml(v.borradores, o)}${caja}`
            + `<div class="vm-falla"${o.falla ? '' : ' hidden'}>${esc(o.falla ?? '')}</div>`,
        pie: pieBotones(botonesDelPie(v, o)),
    };
}
