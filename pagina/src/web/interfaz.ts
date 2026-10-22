// La interfaz de la página: los avisos que se van solos y los diálogos que esperan una respuesta (un campo para
// escribir, un menú para elegir, un aviso con botones). Viven en la página misma, encima de todo: se ven mire
// uno lo que mire (el dashboard, un hilo, la lista en un celular). Sus estilos, en media/css/web.css.

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
    if (!avisos?.isConnected) { avisos = el('div', 'web-avisos'); document.body.appendChild(avisos); }
    const a = el('div', `web-aviso ${nivel}`, texto);
    avisos.appendChild(a);
    setTimeout(() => a.remove(), ms);
}

/** Una caja (<dialog>): el navegador pone el fondo, atrapa el foco adentro y cierra con Escape (evento
 *  cancel). Un clic fuera de la caja, en el fondo, es cancelar. `responder` la cierra, una sola vez. */
function caja<T>(titulo: string, ayuda: string, armar: (caja: HTMLDialogElement, responder: (valor: T | undefined) => void) => void): Promise<T | undefined> {
    return new Promise(listo => {
        const c = el('dialog', 'web-caja');
        document.body.appendChild(c);
        let hecho = false;
        const responder = (valor: T | undefined) => {
            if (hecho) return;
            hecho = true; c.close(); c.remove();
            listo(valor);
        };
        c.addEventListener('cancel', e => { e.preventDefault(); responder(undefined); });
        c.addEventListener('click', e => {
            const r = c.getBoundingClientRect();
            if (e.target === c && (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom)) responder(undefined);
        });
        if (titulo) c.appendChild(el('h3', '', titulo));
        if (ayuda) c.appendChild(el('p', 'ayuda', ayuda));
        armar(c, responder);
    });
}

export interface PedidoCampo { titulo?: string; ayuda?: string; placeholder?: string; valor?: string; password?: boolean; problema?: string }

/** Un campo para escribir: lo escrito con ⏎, o undefined si se canceló. */
export function campo(o: PedidoCampo): Promise<string | undefined> {
    return caja<string>(o.titulo ?? '', o.ayuda ?? '', (c, responder) => {
        const inp = el('input');
        inp.value = o.valor ?? ''; inp.placeholder = o.placeholder ?? '';
        if (o.password) inp.type = 'password';
        c.append(inp, el('div', 'problema', o.problema ?? ''));
        inp.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); responder(inp.value); } });
        c.showModal(); inp.focus(); inp.select();
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
 *  `destinos`, un selector arriba. Lo escrito y el destino elegido, o undefined si se canceló. */
export function escribir(o: PedidoEscrito): Promise<{ texto: string; destino: string } | undefined> {
    return caja<{ texto: string; destino: string }>(o.titulo ?? '', o.ayuda ?? '', (c, responder) => {
        const sel = el('select');
        for (const d of o.destinos ?? []) { const op = el('option', '', d.nombre); op.value = d.valor; sel.appendChild(op); }
        if (o.destino) sel.value = o.destino;
        if (o.destinos?.length) { const fila = el('label', 'destino', 'a'); fila.appendChild(sel); c.appendChild(fila); }
        const area = el('textarea');
        area.value = o.valor ?? ''; area.placeholder = o.placeholder ?? '';
        const enviar = () => { if (area.value.trim()) responder({ texto: area.value, destino: sel.value }); };
        area.addEventListener('input', () => o.borrador?.(area.value));
        area.addEventListener('keydown', e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); enviar(); } });
        const bot = el('div', 'botones');
        const si = el('a', '', '⌘⏎ enviar'); si.addEventListener('click', enviar);
        const no = el('a', '', 'cancelar'); no.addEventListener('click', () => responder(undefined));
        bot.append(si, no);
        c.append(area, bot);
        c.showModal(); area.focus();
    });
}

export interface OpcionMenu { label: string; description?: string; detail?: string; separador?: boolean }

const norm = (t: string | undefined) => (t ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();

/** Un menú para elegir, con un filtro arriba (↑ ↓ y ⏎): el índice de la opción elegida, o undefined. */
export function elegir(opciones: OpcionMenu[], o: { titulo?: string; placeholder?: string } = {}): Promise<number | undefined> {
    return caja<number>(o.titulo ?? '', '', (c, responder) => {
        const filtro = el('input'); filtro.placeholder = o.placeholder || 'buscar';
        const lista = el('div', 'web-lista');
        c.append(filtro, lista);
        let vis: [HTMLElement, number][] = [], sel = 0;
        const pintar = () => {
            lista.replaceChildren(); vis = [];
            const q = norm(filtro.value);
            opciones.forEach((op, i) => {
                if (op.separador) { if (!q) lista.appendChild(el('div', 'web-sep', op.label)); return; }
                if (q && !norm(`${op.label} ${op.description ?? ''} ${op.detail ?? ''}`).includes(q)) return;
                const f = el('div', 'web-op'); f.appendChild(el('span', '', op.label));
                if (op.description) f.appendChild(el('span', 'd', op.description));
                f.addEventListener('click', () => responder(i));
                vis.push([f, i]); lista.appendChild(f);
            });
            sel = Math.min(sel, Math.max(0, vis.length - 1));
            vis.forEach(([f], k) => f.classList.toggle('sel', k === sel));
        };
        filtro.addEventListener('input', () => { sel = 0; pintar(); });
        filtro.addEventListener('keydown', e => {
            if (e.key === 'ArrowDown') { e.preventDefault(); sel = Math.min(sel + 1, vis.length - 1); pintar(); }
            if (e.key === 'ArrowUp') { e.preventDefault(); sel = Math.max(sel - 1, 0); pintar(); }
            if (e.key === 'Enter') { e.preventDefault(); if (vis[sel]) responder(vis[sel][1]); }
        });
        pintar(); c.showModal(); filtro.focus();
    });
}

/** Un aviso con botones: el botón elegido, o undefined si se canceló. */
export function preguntar(texto: string, botones: string[]): Promise<string | undefined> {
    return caja<string>('', '', (c, responder) => {
        c.appendChild(el('p', '', texto));
        const bot = el('div', 'botones');
        for (const b of botones) { const a = el('a', '', b); a.addEventListener('click', () => responder(b)); bot.appendChild(a); }
        const cancelar = el('a', '', 'cancelar'); cancelar.addEventListener('click', () => responder(undefined)); bot.appendChild(cancelar);
        c.appendChild(bot);
        c.showModal();
        const primero = bot.querySelector('a');
        if (primero) { primero.tabIndex = 0; primero.focus(); }
    });
}
