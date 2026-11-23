// Lo que el agente le pregunta a la persona con opciones (en Claude Code, la herramienta AskUserQuestion), en la vista
// conversación (web/conversacion.ts): pendiente, como un formulario en el pie de la vista, en el lugar de la caja; ya
// cerrada, como un registro en la conversación de qué se preguntó y qué se respondió.
//
// La pregunta llega en la conversación (`/api/hilos/leer`), en el mensaje de la herramienta (`pregunta`): cada una con
// su encabezado, sus opciones (con su descripción), si se elige una o varias, y lo respondido cuando ya se contestó.
// Siempre se puede escribir otra cosa («otra respuesta»), como en la terminal.
//
// Va de a una pregunta, como el diálogo de la terminal: «1 de 2» y ← → para ir y venir. Elegir en una de una sola opción
// pasa a la siguiente y, en la última (con todo contestado), envía: un toque, como el número en la terminal. Con varias
// opciones, o con lo escrito a mano, envía «responder». Decidido con la persona el 14-nov-2026, entre esto y todas las
// preguntas a la vez dentro de la conversación.
//
// Gramática visual: la opción es un círculo, aro si no está elegida y con un punto al medio (señalado) si lo está, en el
// acento; el encabezado, en la tinta de los títulos; la descripción, tenue. Sin marcos.

import { circulo } from '../componentes/circulo';
import { I } from './iconos';

export interface Opcion { etiqueta: string; descripcion?: string }
export interface UnaPregunta { pregunta: string; encabezado?: string; varias?: boolean; opciones: Opcion[] }
/** Una pregunta del agente: `estado` dice si espera, si se contestó o si se cerró sin contestar. `contestable`: se le
 *  puede mandar la respuesta directo al diálogo (el mod de telar lo tiene abierto). */
export interface Pregunta {
    id: string;
    preguntas: UnaPregunta[];
    estado: 'pendiente' | 'respondida' | 'cancelada';
    respuestas?: Record<string, string>;
    contestable?: boolean;
}

function el<K extends keyof HTMLElementTagNameMap>(tag: K, clase = '', texto?: string): HTMLElementTagNameMap[K] {
    const e = document.createElement(tag);
    if (clase) e.className = clase;
    if (texto !== undefined) e.textContent = texto;
    return e;
}

/** Lo elegido en una pregunta: las opciones marcadas (por su índice) y lo escrito en «otra respuesta». */
export interface Eleccion { marcadas: Set<number>; otra: string }

/** La respuesta de una pregunta como la toma el agente: la etiqueta elegida, las elegidas separadas por coma, o lo
 *  escrito (con varias, lo escrito va al final de las marcadas). Vacía si falta. */
export function respuesta(p: UnaPregunta, e: Eleccion): string {
    const otra = e.otra.trim();
    const marcadas = [...e.marcadas].sort((a, b) => a - b).map(i => p.opciones[i]?.etiqueta ?? '').filter(Boolean);
    if (!p.varias) return otra || marcadas[0] || '';
    return [...marcadas, ...(otra ? [otra] : [])].join(', ');
}

/** Cómo se contesta desde la página: `responder`, con la respuesta entera (el mod la entrega al diálogo); `teclas`, con
 *  el número de la opción en su terminal (sin el mod: solo una pregunta de una opción); sin ninguno, solo se mira. */
export interface Contestar {
    responder?: (r: Record<string, string>) => void;
    teclas?: (opcion: number) => void;
    /** una línea al pie, tenue: cómo contestarla si no es aquí */
    nota?: string;
    /** lo escrito en «otra respuesta» de cada pregunta, de antes de recargar la página; `alEscribir` lo recibe con cada
     *  tecla, para guardarlo (web/guardado.ts) */
    otras?: string[];
    alEscribir?: (otras: string[]) => void;
}

export interface Formulario {
    el: HTMLElement;
    /** de qué pregunta es: mientras sea la misma, se reusa entre repintadas (lo elegido no se pierde) */
    id: string;
    /** mientras se manda la respuesta: no se aprieta, y el botón gira */
    ocupado(si: boolean, que?: string): void;
}

/** El formulario de una pregunta pendiente, de a una pregunta. */
export function formulario(p: Pregunta, o: Contestar): Formulario {
    const elecciones: Eleccion[] = p.preguntas.map(() => ({ marcadas: new Set<number>(), otra: '' }));
    const varias = p.preguntas.length > 1;
    const soloVer = !o.responder && !o.teclas;
    const form = el('form', `pregunta-form${soloVer ? ' solo-ver' : ''}`);
    form.noValidate = true;
    let paso = 0;
    const bloques: HTMLElement[] = [];

    // abajo: qué falta (o cómo contestarla), ir y venir entre preguntas, y responder
    const pie = el('div', 'responder');
    const falta = el('span', 'falta');
    const atras = el('button', 'paso');
    atras.type = 'button'; atras.title = 'la pregunta anterior';
    atras.appendChild(el('span', 'i', I.atras));
    const adelante = el('button', 'paso');
    adelante.type = 'button'; adelante.title = 'la pregunta siguiente';
    adelante.appendChild(el('span', 'i', I.siguiente));
    const enviar = el('button', 'enviar');
    enviar.type = 'submit';
    const icono = el('span', 'i', I.enviar);
    enviar.append(icono, document.createTextNode(' responder'));

    const listo = () => p.preguntas.every((q, i) => !!respuesta(q, elecciones[i]));
    const mandar = () => o.responder?.(Object.fromEntries(p.preguntas.map((q, i) => [q.pregunta, respuesta(q, elecciones[i])])));

    p.preguntas.forEach((q, i) => {
        const b = el('fieldset', 'una');
        const cabeza = el('div', 'cabeza');
        if (q.encabezado) cabeza.appendChild(el('span', 'encabezado', q.encabezado));
        cabeza.appendChild(el('span', 'como', q.varias ? 'elige una o varias' : 'elige una'));
        if (varias) cabeza.appendChild(el('span', 'cuantas', `${i + 1} de ${p.preguntas.length}`));
        b.append(cabeza, el('p', 'enunciado', q.pregunta));
        const lista = el('div', 'opciones');
        const botones: HTMLButtonElement[] = [];
        // otra respuesta: lo que se escribe aquí es la respuesta (con una sola, en vez de la opción marcada). Por teclas
        // no: escribir en el diálogo de la terminal a ciegas no es seguro
        const otraFila = el('label', 'opcion otra');
        const otraMarca = el('span', 'marca-op');
        const campo = el('textarea');
        const pintar = () => {
            botones.forEach((bt, j) => {
                const si = elecciones[i].marcadas.has(j);
                bt.setAttribute('aria-pressed', String(si));
                bt.querySelector('.marca-op')!.innerHTML = circulo(si ? { figura: 'centro' } : { lleno: 0 });
            });
            otraMarca.innerHTML = circulo(elecciones[i].otra.trim() ? { figura: 'centro' } : { lleno: 0 });
            otraFila.classList.toggle('si', !!elecciones[i].otra.trim());
            revisar();
        };
        q.opciones.forEach((op, j) => {
            const bt = el('button', 'opcion');
            bt.type = 'button';
            bt.disabled = soloVer;
            const txt = el('span', 'txt');
            txt.appendChild(el('span', 'etiqueta', op.etiqueta));
            if (op.descripcion) txt.appendChild(el('span', 'descripcion', op.descripcion));
            bt.append(el('span', 'marca-op'), txt);
            bt.addEventListener('click', () => {
                const e = elecciones[i];
                if (q.varias) { if (e.marcadas.has(j)) e.marcadas.delete(j); else e.marcadas.add(j); pintar(); return; }
                e.marcadas = new Set([j]);
                e.otra = ''; campo.value = '';
                pintar();
                // sin el mod, el número de la opción en su terminal (una pregunta de una opción: el número la envía)
                if (!o.responder) { o.teclas?.(j); return; }
                // con una sola: a la siguiente pregunta, o, si era la última y está todo, se envía (un toque)
                if (i < p.preguntas.length - 1) ir(i + 1);
                else if (listo()) mandar();
            });
            botones.push(bt);
            lista.appendChild(bt);
        });
        campo.rows = 1;
        campo.placeholder = 'otra respuesta';
        campo.dataset.guarda = '';
        if (o.responder && o.otras?.[i]) campo.value = elecciones[i].otra = o.otras[i];
        const crecer = () => { campo.style.height = 'auto'; campo.style.height = `${campo.scrollHeight}px`; };
        campo.addEventListener('input', () => {
            elecciones[i].otra = campo.value;
            if (!q.varias && campo.value.trim()) elecciones[i].marcadas.clear();
            crecer();
            pintar();
            o.alEscribir?.(elecciones.map(x => x.otra));
        });
        // ⏎ responde (si está todo) o pasa a la siguiente; ⇧⏎, una línea nueva
        campo.addEventListener('keydown', e => {
            if (e.key !== 'Enter' || e.shiftKey || e.isComposing) return;
            e.preventDefault();
            if (i < p.preguntas.length - 1 && respuesta(q, elecciones[i])) ir(i + 1);
            else form.requestSubmit();
        });
        otraFila.append(otraMarca, campo);
        if (o.responder) lista.appendChild(otraFila);
        b.appendChild(lista);
        bloques.push(b);
        form.appendChild(b);
        pintar();
    });

    pie.append(falta);
    if (varias) pie.append(atras, adelante);
    if (o.responder) pie.append(enviar);
    form.appendChild(pie);

    function ir(n: number) {
        paso = Math.max(0, Math.min(p.preguntas.length - 1, n));
        bloques.forEach((b, i) => { b.hidden = i !== paso; });
        atras.disabled = paso === 0;
        adelante.disabled = paso === p.preguntas.length - 1;
    }
    atras.addEventListener('click', () => ir(paso - 1));
    adelante.addEventListener('click', () => ir(paso + 1));

    function revisar() {
        if (!o.responder) { falta.textContent = o.nota ?? ''; return; }
        const sin = p.preguntas.filter((q, i) => !respuesta(q, elecciones[i] ?? { marcadas: new Set(), otra: '' }));
        enviar.disabled = !!sin.length;
        // con una sola pregunta, lo que falta se ve solo
        falta.textContent = sin.length && varias ? `falta: ${sin.map(q => q.encabezado || q.pregunta).join(', ')}` : '';
    }
    form.addEventListener('submit', e => {
        e.preventDefault();
        revisar();
        if (o.responder && !enviar.disabled) mandar();
    });
    ir(0);
    revisar();
    return {
        el: form, id: p.id,
        ocupado(si, que = '') {
            form.classList.toggle('ocupado', si);
            for (const b of form.querySelectorAll<HTMLButtonElement | HTMLTextAreaElement>('button, textarea')) b.disabled = si;
            icono.innerHTML = si ? circulo({ mov: 'gira' }) : I.enviar;
            enviar.title = que;
            if (!si) { ir(paso); revisar(); }
        },
    };
}

/** Una pregunta ya cerrada, en el historial: lo preguntado (el encabezado y la pregunta), del agente; y debajo lo que
 *  respondió la persona (o que no la contestó), como un mensaje suyo. Las filas, cada una con su marca. */
export function registro(p: Pregunta, marca: (clase: 'usuario' | 'agente', ayuda: string) => HTMLElement): HTMLElement[] {
    const preg = el('div', 'msj agente pregunta hecha');
    const cuerpo = el('div', 'cuerpo');
    for (const q of p.preguntas) {
        const linea = el('div', 'linea');
        if (q.encabezado) linea.append(el('span', 'encabezado', q.encabezado), document.createTextNode(' '));
        linea.appendChild(el('span', 'enunciado', q.pregunta));
        cuerpo.appendChild(linea);
    }
    preg.append(marca('agente', 'el agente preguntó'), cuerpo);
    const resp = el('div', `msj usuario respuesta${p.estado === 'cancelada' ? ' cancelada' : ''}`);
    const rc = el('div', 'cuerpo');
    if (p.estado === 'cancelada') rc.textContent = 'no la contestaste';
    else for (const q of p.preguntas) {
        const linea = el('div', 'linea');
        if (p.preguntas.length > 1 && q.encabezado) linea.append(el('span', 'encabezado', q.encabezado), document.createTextNode(' '));
        linea.appendChild(el('span', 'dicho', p.respuestas?.[q.pregunta] ?? '—'));
        rc.appendChild(linea);
    }
    resp.append(marca('usuario', p.estado === 'cancelada' ? 'tú · no la contestaste' : 'tú respondiste'), rc);
    return [preg, resp];
}
