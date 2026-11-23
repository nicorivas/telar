// La interfaz de la página: los avisos que se van solos y los diálogos que esperan una respuesta (un campo para
// escribir, un menú para elegir, un aviso con botones). Viven en la página misma, encima de todo: se ven mire
// uno lo que mire (el dashboard, un hilo, la lista en un celular). Sus estilos, en media/css/web.css.

import { abrirVentana } from './ventana';
import { barraBuscar } from '../componentes/buscador';
import { cancelar, pieBotones, type Boton } from '../componentes/boton';
import { item } from '../componentes/item';
import { esc } from '../estilo';

export type Nivel = 'info' | 'aviso' | 'falla';

function el<K extends keyof HTMLElementTagNameMap>(tag: K, clase = '', texto?: string): HTMLElementTagNameMap[K] {
    const e = document.createElement(tag);
    if (clase) e.className = clase;
    if (texto !== undefined) e.textContent = texto;
    return e;
}

let avisos: HTMLElement | undefined;

/** Un aviso abajo a la derecha, que se va solo. */
export function avisar(texto: string, nivel: Nivel = 'info', ms = 6000): void {
    // el modo puesto dice cuáles (web/modos.ts, `data-avisos` en body): todos, urgentes (no los «info») o ninguno
    const cuales = document.body.dataset.avisos;
    if (cuales === 'ninguno' || (cuales === 'urgentes' && nivel === 'info')) return;
    if (!avisos?.isConnected) { avisos = el('div', 'web-avisos'); document.body.appendChild(avisos); }
    const a = el('div', `web-aviso ${nivel}`, texto);
    avisos.appendChild(a);
    setTimeout(() => a.remove(), ms);
}

export interface PedidoCampo { titulo?: string; ayuda?: string; placeholder?: string; valor?: string; password?: boolean; problema?: string }

/** Un campo para escribir: lo escrito con ⏎, o undefined si se canceló. Es una ventana (`abrirVentana`). */
export function campo(o: PedidoCampo): Promise<string | undefined> {
    const html = `<input${o.password ? ' type="password"' : ''} value="${esc(o.valor ?? '')}" placeholder="${esc(o.placeholder ?? '')}">`
        + `<div class="problema">${esc(o.problema ?? '')}</div>`;
    return abrirVentana<string>({ titulo: o.titulo, ayuda: o.ayuda, cuerpo: html, clase: 'ventana-texto' }, {
        montar: (d, cerrar) => {
            const inp = d.querySelector('input')!;
            inp.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); cerrar(inp.value); } });
            inp.select();
        },
    });
}

export interface PedidoEscrito {
    titulo?: string; ayuda?: string; placeholder?: string; valor?: string;
    /** a quién va, para elegir arriba (sin opciones no se pregunta), y el que viene elegido */
    destinos?: { valor: string; nombre: string }[]; destino?: string;
    /** lo escrito a medida que se escribe: quien pide lo guarda, y un ⎋ o un clic afuera no lo pierde */
    borrador?: (texto: string) => void;
}

/** Un texto largo para mandar, y a quién: un área de varias líneas (⏎ es un salto, ⌘⏎ o ⌃⏎ envía) y, con
 *  `destinos`, un selector arriba. Lo escrito y el destino elegido, o undefined si se canceló. Es una ventana. */
export function escribir(o: PedidoEscrito): Promise<{ texto: string; destino: string } | undefined> {
    const opciones = (o.destinos ?? []).map(d => `<option value="${esc(d.valor)}">${esc(d.nombre)}</option>`).join('');
    const html = (o.destinos?.length ? `<label class="destino">a <select>${opciones}</select></label>` : '')
        + `<textarea placeholder="${esc(o.placeholder ?? '')}">${esc(o.valor ?? '')}</textarea>`;
    // «enviar» no tiene `accion` (no cierra con un clic: manda lo escrito, si hay); ⌘⏎ lo aprieta también desde el área
    const pie = pieBotones([{ texto: 'enviar', tecla: '⌘⏎', datos: { enviar: '' } }, cancelar()]);
    return abrirVentana<{ texto: string; destino: string }>({ titulo: o.titulo, ayuda: o.ayuda, cuerpo: html, pie, clase: 'ventana-texto' }, {
        foco: 'textarea',
        montar: (d, cerrar) => {
            const sel = d.querySelector('select');
            if (sel && o.destino) sel.value = o.destino;
            const area = d.querySelector('textarea')!;
            const enviar = () => { if (area.value.trim()) cerrar({ texto: area.value, destino: sel?.value ?? '' }); };
            area.addEventListener('input', () => o.borrador?.(area.value));
            d.querySelector('[data-enviar]')!.addEventListener('click', enviar);
        },
    });
}

export interface OpcionMenu { label: string; description?: string; detail?: string; separador?: boolean;
    /** un ícono de la letra de la página (web/iconos.ts) y el color que distingue lo que hace (azul, verde…) */
    icono?: string; color?: string;
    /** en un menú junto al puntero, en lugar del ícono: una señal, el HTML de un círculo (componentes/senales.ts), que
     *  arma la página y no trae nada escrito por otro */
    senal?: string }

/** El ícono de una opción: el de la letra, o su señal (un círculo, HTML de la página). */
function icono(op: OpcionMenu): HTMLElement {
    const ico = el('span', 'i ico', op.senal ? undefined : op.icono ?? '');
    if (op.senal) ico.innerHTML = op.senal;
    return ico;
}

const norm = (t: string | undefined) => (t ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();

/** Un menú para elegir, con un filtro arriba (↑ ↓ y ⏎): el índice de la opción elegida, o undefined. `inicial`: la
 *  opción que parte marcada (su índice en `opciones`), a la vista. Si alguna trae `detail`, abajo va entera la que está
 *  marcada (su `description` y su `detail`, sin cortar): al pasar el mouse o con ↑ ↓. */
export function elegir(opciones: OpcionMenu[], o: { titulo?: string; placeholder?: string; inicial?: number } = {}): Promise<number | undefined> {
    const conDetalle = opciones.some(op => op.detail);
    // el filtro: la barra de un buscador (componentes/buscador.ts); `placeholder`, en qué se elige. La lista y el detalle se pintan en `montar`
    return abrirVentana<number>({
        titulo: o.titulo,
        campo: barraBuscar({ placeholder: o.placeholder || 'opciones', ayuda: '↑ ↓ elegir · ⏎ esa · ⎋ cancelar' }),
        cuerpo: `<div class="web-lista"></div>${conDetalle ? '<div class="web-detalle"></div>' : ''}`,
        clase: 'ventana-elegir',
    }, {
        foco: 'input.buscar',
        montar: (d, responder) => {
            const filtro = d.querySelector<HTMLInputElement>('input.buscar')!;
            const lista = d.querySelector<HTMLElement>('.web-lista')!;
            const detalle = d.querySelector<HTMLElement>('.web-detalle');
            let vis: [HTMLElement, number][] = [], sel = 0;
            const marcar = (alaVista = false) => {
                vis.forEach(([f], k) => f.classList.toggle('sel', k === sel));
                const op = vis[sel] ? opciones[vis[sel][1]] : undefined;
                if (detalle) {
                    detalle.replaceChildren();
                    if (op?.color) detalle.style.setProperty('--c', `var(--${op.color})`); else detalle.style.removeProperty('--c');
                    if (op) {
                        detalle.append(el('div', 'l', op.label));
                        if (op.description) detalle.append(el('div', 'd', op.description));
                        if (op.detail) detalle.append(el('div', 'x', op.detail));
                    }
                }
                if (alaVista) vis[sel]?.[0].scrollIntoView({ block: 'nearest' });
            };
            const pintar = () => {
                lista.replaceChildren(); vis = [];
                const q = norm(filtro.value);
                opciones.forEach((op, i) => {
                    if (op.separador) { if (!q) lista.appendChild(el('div', 'web-sep', op.label)); return; }
                    if (q && !norm(`${op.label} ${op.description ?? ''} ${op.detail ?? ''}`).includes(q)) return;
                    const f = el('div', 'web-op');
                    if (op.color) f.style.setProperty('--c', `var(--${op.color})`);
                    f.appendChild(icono(op));
                    f.appendChild(el('span', 'l', op.label));
                    if (op.description) f.appendChild(el('span', 'd', op.description));
                    f.addEventListener('click', () => responder(i));
                    const k = vis.length;
                    if (detalle) f.addEventListener('mouseenter', () => { sel = k; marcar(); });
                    vis.push([f, i]); lista.appendChild(f);
                });
                sel = Math.min(sel, Math.max(0, vis.length - 1));
                marcar(true);
            };
            filtro.addEventListener('input', () => { sel = 0; pintar(); });
            filtro.addEventListener('keydown', e => {
                if (e.key === 'ArrowDown') { e.preventDefault(); sel = Math.min(sel + 1, vis.length - 1); marcar(true); }
                if (e.key === 'ArrowUp') { e.preventDefault(); sel = Math.max(sel - 1, 0); marcar(true); }
                if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); if (vis[sel]) responder(vis[sel][1]); }
            });
            pintar();
            if (o.inicial !== undefined) {
                const k = vis.findIndex(([, i]) => i === o.inicial);
                if (k >= 0) sel = k;
            }
            marcar(true);
        },
    });
}

/** Un menú junto a donde se hizo clic (el clic derecho sobre una entidad, o su ⋯): las opciones, con ↑ ↓ ⏎ ⎋ y
 *  escribir para filtrar. Es una ventana `junto` (componentes/ventana.ts, `abrirVentana`): un <dialog> abierto sin fondo
 *  (`show`, no `showModal`); mientras está, las teclas del dashboard callan (miran `dialog[open]`). Las filas son
 *  `item()`: el ícono (o la señal) en la ranura, la descripción como sufijo tenue; el color de lo que hace (`--c`) tiñe
 *  ranura y título. Se cierra al elegir, con ⎋, con un clic afuera o si la página pierde el foco. El índice de la
 *  opción elegida, o undefined. */
export function menu(opciones: OpcionMenu[], donde: { x: number; y: number }, o: { titulo?: string } = {}): Promise<number | undefined> {
    return abrirVentana<number>({
        lugar: 'junto', titulo: o.titulo, clase: 'ventana-menu',
        campo: barraBuscar({ placeholder: 'acciones', ayuda: '↑ ↓ elegir · ⏎ esa · ⎋ cerrar' }),
        cuerpo: '<div class="ventana-lista m-lista"></div>',
    }, {
        junto: donde, foco: 'input.buscar', clase: 'ventana-menu',
        montar: (d, responder) => {
            const filtro = d.querySelector<HTMLInputElement>('input.buscar')!;
            const lista = d.querySelector<HTMLElement>('.m-lista')!;
            let vis: number[] = [], sel = 0;
            const marcar = (alaVista = false) => {
                let k = 0;
                for (const f of lista.querySelectorAll('.item')) f.classList.toggle('activa', k++ === sel);
                if (alaVista) lista.querySelector('.activa')?.scrollIntoView({ block: 'nearest' });
            };
            const pintar = () => {
                vis = [];
                const q = norm(filtro.value);
                let html = '';
                opciones.forEach((op, i) => {
                    if (op.separador) { if (!q) html += `<div class="m-sep">${esc(op.label)}</div>`; return; }
                    if (q && !norm(`${op.label} ${op.description ?? ''} ${op.detail ?? ''}`).includes(q)) return;
                    const k = vis.length;
                    vis.push(i);
                    const ranura = op.senal ? { html: op.senal } : op.icono ? { icono: op.icono } : null;
                    html += `<div class="m-fila"${op.color ? ` style="--c: var(--${esc(op.color)})"` : ''}>` + item({
                        titulo: op.label, inicio: ranura ? [ranura] : undefined,
                        sufijo: op.description ? [{ texto: op.description }] : undefined,
                        activa: k === sel, datos: { k: String(k) },
                    }) + '</div>';
                });
                sel = Math.min(sel, Math.max(0, vis.length - 1));
                lista.innerHTML = html || '<div class="ventana-vacia">nada calza</div>';
                marcar(true);
            };
            filtro.addEventListener('input', () => { sel = 0; pintar(); });
            // las teclas no siguen a la página (el dashboard tiene atajos de una letra); ⎋ la cierra aquí mismo
            filtro.addEventListener('keydown', e => {
                if (e.key === 'ArrowDown') { e.preventDefault(); sel = Math.min(sel + 1, vis.length - 1); marcar(true); }
                if (e.key === 'ArrowUp') { e.preventDefault(); sel = Math.max(sel - 1, 0); marcar(true); }
                if (e.key === 'Enter') { e.preventDefault(); if (vis[sel] !== undefined) responder(vis[sel]); }
                if (e.key === 'Escape') { e.preventDefault(); responder(undefined); }
                e.stopPropagation();
            });
            const fila = (e: Event) => (e.target as HTMLElement).closest<HTMLElement>('.item[data-k]');
            lista.addEventListener('click', e => { const f = fila(e); if (f) responder(vis[Number(f.dataset.k)]); });
            lista.addEventListener('mousemove', e => { const f = fila(e); if (f && Number(f.dataset.k) !== sel) { sel = Number(f.dataset.k); marcar(); } });
            // si la página pierde el foco (otra ventana, otra pestaña), se cierra
            const alPerderElFoco = () => responder(undefined);
            window.addEventListener('blur', alPerderElFoco);
            pintar();
            return () => window.removeEventListener('blur', alPerderElFoco);
        },
    });
}

export interface OpcionesPreguntar {
    /** el foco parte en «cancelar» (lo que concede algo, o una acción que viene de afuera y no se sabe qué hace) */
    foco?: 'primero' | 'cancelar';
    /** el primer botón destruye: va en el de peligro, con su acorde (⌘⌫, nunca ⏎), y el foco parte en «cancelar» */
    destruye?: boolean;
}

/** Los botones de un aviso, con la tecla de cada uno: lo que destruye, ⌘⌫; si hay una sola acción, ⏎ (o ⌘⏎, si el foco
 *  no parte en ella: ⏎ es del foco); si hay varias, 1, 2, 3…; y «cancelar» al último, con ⎋. */
export function botonesDeAviso(botones: string[], o: OpcionesPreguntar = {}): Boton[] {
    const peligro = !!o.destruye && botones.length > 0;
    const enCancelar = peligro || o.foco === 'cancelar';
    const acciones = botones.length - (peligro ? 1 : 0);
    let k = 0;
    return [...botones.map((texto, i): Boton => {
        if (peligro && i === 0) return { texto, accion: `b${i}`, tono: 'peligro', tecla: '⌘⌫' };
        const tecla = acciones > 1 ? String(++k) : enCancelar ? '⌘⏎' : '⏎';
        return { texto, accion: `b${i}`, tono: 'accion', tecla };
    }), cancelar()];
}

/** Un aviso con botones (componentes/boton.ts, «la tecla en el pie»): el botón elegido, o undefined si se canceló. La tecla
 *  de cada uno lo aprieta; ⏎ aprieta el que tiene el foco (⇥ pasa al siguiente; web/botonera.ts). El foco parte en el
 *  primero; con `destruye` o `foco: 'cancelar'`, en «cancelar»: lo que destruye, para que un ⏎ distraído sea no hacerlo. */
export function preguntar(texto: string, botones: string[], o: OpcionesPreguntar = {}): Promise<string | undefined> {
    const enCancelar = !!o.destruye || o.foco === 'cancelar' || !botones.length;
    return abrirVentana<string>({ cuerpo: `<p>${esc(texto)}</p>`, pie: pieBotones(botonesDeAviso(botones, o)), clase: 'ventana-texto' }, {
        foco: enCancelar ? '[data-accion="no"]' : '[data-accion="b0"]',
    }).then(r => (r && r !== 'no' ? botones[Number(r.slice(1))] : undefined));
}
