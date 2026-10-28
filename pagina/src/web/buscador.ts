// El buscador (⌘K): una ventana sobre todo lo demás, como Spotlight, para ir a cualquier cosa escribiendo un poco de
// su nombre: un hilo, un agente, una pestaña del dashboard, una sección de ⚙, un modo, una orden. Sirve también en
// el modo foco, donde no hay barra ni cabecera.
//
// Lo que se busca lo dan las fuentes, que se registran de afuera (navegador/app.ts): cada una da sus resultados con
// lo que hace abrirlos. Agregar algo que buscar (las tareas, los proyectos, los documentos) es registrar otra fuente;
// esta ventana no cambia. Se filtra al escribir, por cuánto se parece cada uno a lo escrito (el nombre pesa más que
// el detalle, el comienzo más que el medio), en grupos por fuente.

import { esc, normalizar } from '../estilo';

export interface Resultado {
    titulo: string;
    /** una línea tenue al lado: dónde vive, qué es */
    detalle?: string;
    /** lo que también se busca, sin mostrarlo */
    claves?: string;
    /** sin nada escrito, el orden (más alto, primero): lo reciente, lo vivo */
    peso?: number;
    /** un carácter al principio de la fila */
    icono?: string;
    abrir: () => unknown;
}
export interface Fuente {
    clave: string;
    nombre: string;
    /** sin nada escrito, el orden de los grupos (más bajo, primero) */
    orden: number;
    /** el color de su grupo y de sus íconos: el nombre de un token de la página (azul, violeta, cian…) */
    color?: string;
    resultados: () => Resultado[] | Promise<Resultado[]>;
}

const fuentes: Fuente[] = [];
/** cuántos de cada grupo se muestran (sin escribir, menos) */
const POR_GRUPO = 8, POR_GRUPO_VACIO = 5;

export function registrar(f: Fuente): void {
    const i = fuentes.findIndex(x => x.clave === f.clave);
    if (i >= 0) fuentes[i] = f; else fuentes.push(f);
}

/** Cuánto se parece `r` a lo escrito (0: nada). El nombre pesa más que el detalle; empezar por lo escrito, más que
 *  tenerlo al medio; tener sus letras en orden (fzy, «tlr» → «telar»), lo menos. */
export function puntaje(q: string, r: Resultado): number {
    if (!q) return 1;
    const t = normalizar(r.titulo), d = normalizar(`${r.detalle ?? ''} ${r.claves ?? ''}`);
    let p = 0;
    if (t === q) p = 100;
    else if (t.startsWith(q)) p = 80;
    else if (t.split(/[\s·/_-]+/).some(w => w.startsWith(q))) p = 65;
    else if (t.includes(q)) p = 50;
    else if (d.includes(q)) p = 25;
    else {
        // las letras de lo escrito, en orden, en el nombre: cuanto más juntas, mejor
        let i = 0, primera = -1, ultima = -1;
        for (let j = 0; j < t.length && i < q.length; j++) if (t[j] === q[i]) { if (primera < 0) primera = j; ultima = j; i++; }
        if (i === q.length) p = Math.max(5, 30 - (ultima - primera - q.length));
    }
    return p ? p + Math.min(5, (r.peso ?? 0) / 20) : 0;
}

let abierto: HTMLDialogElement | undefined;

/** La caja en la cuadrícula de la trama de atrás (la de ░ del ::backdrop): la celda es la de la letra de la página,
 *  la trama se repite desde la esquina de la ventana, y la caja empieza en una esquina de celda y mide celdas
 *  enteras. Si no, el borde corta los ░ por la mitad y la sombra se ve pegada encima. */
function cuadricula(caja: HTMLDialogElement): void {
    const m = document.createElement('span');
    m.textContent = '░'.repeat(20);
    m.style.cssText = 'position:absolute;visibility:hidden;white-space:pre;font:inherit;line-height:inherit';
    caja.appendChild(m);
    const r = m.getBoundingClientRect();
    m.remove();
    const cw = r.width / 20 || 8, ch = parseFloat(getComputedStyle(caja).lineHeight) || r.height || 16;
    caja.style.setProperty('--celda-w', `${cw}px`);
    caja.style.setProperty('--celda-h', `${ch}px`);
    const columnasVentana = Math.floor(innerWidth / cw), filasVentana = Math.floor(innerHeight / ch);
    const columnas = Math.max(20, Math.min(76, columnasVentana - 4));
    // el alto: lo que pide su contenido, redondeado hacia arriba a filas enteras, hasta el 70% de la ventana
    caja.style.height = 'auto';
    const filas = Math.max(4, Math.min(Math.floor(filasVentana * 0.7), Math.ceil(caja.getBoundingClientRect().height / ch)));
    caja.style.width = `${columnas * cw}px`;
    caja.style.height = `${filas * ch}px`;
    caja.style.left = `${Math.floor((columnasVentana - columnas) / 2) * cw}px`;
    caja.style.top = `${Math.round(filasVentana * 0.14) * ch}px`;
}

/** Abrir el buscador (o cerrarlo, si ya está abierto). */
export async function abrir(): Promise<void> {
    if (abierto) { abierto.close(); return; }
    const caja = document.createElement('dialog');
    caja.className = 'buscador';
    caja.innerHTML = '<input type="text" spellcheck="false" autocomplete="off" placeholder="buscar: hilos, agentes, el dashboard, ⚙, modos…">'
        + '<div class="b-lista"></div><div class="b-pie">↑↓ elegir · ⏎ abrir · ⎋ cerrar · ⌘K</div>';
    document.body.appendChild(caja);
    abierto = caja;
    const input = caja.querySelector('input')!, lista = caja.querySelector<HTMLElement>('.b-lista')!;
    let todos: { fuente: Fuente; r: Resultado }[] = [];
    let vistos: Resultado[] = [], sel = 0;

    const pintar = () => {
        const q = normalizar(input.value.trim());
        const grupos = fuentes.map(f => {
            const suyos = todos.filter(x => x.fuente === f).map(x => ({ r: x.r, p: puntaje(q, x.r) })).filter(x => x.p > 0)
                .sort((a, b) => q ? b.p - a.p || (b.r.peso ?? 0) - (a.r.peso ?? 0) : (b.r.peso ?? 0) - (a.r.peso ?? 0));
            return { f, suyos: suyos.slice(0, q ? POR_GRUPO : POR_GRUPO_VACIO), mejor: suyos[0]?.p ?? 0 };
        }).filter(g => g.suyos.length)
            .sort((a, b) => q ? b.mejor - a.mejor || a.f.orden - b.f.orden : a.f.orden - b.f.orden);
        vistos = grupos.flatMap(g => g.suyos.map(x => x.r));
        sel = Math.min(sel, Math.max(0, vistos.length - 1));
        let n = 0;
        lista.innerHTML = grupos.map(g => `<div class="b-grupo" style="--b-color: var(--${esc(g.f.color ?? 'dim')})">${esc(g.f.nombre)}</div>` + g.suyos.map(({ r }) => {
            const i = n++;
            return `<div class="b-fila${i === sel ? ' sel' : ''}" data-i="${i}" style="--b-color: var(--${esc(g.f.color ?? 'dim')})"><span class="b-ic">${esc(r.icono ?? ' ')}</span>`
                + `<span class="b-t">${esc(r.titulo)}</span>${r.detalle ? `<span class="b-d">${esc(r.detalle)}</span>` : ''}</div>`;
        }).join('')).join('') || `<div class="b-vacio">${q ? 'nada calza' : 'leyendo…'}</div>`;
        cuadricula(caja);
        lista.querySelector('.sel')?.scrollIntoView({ block: 'nearest' });
    };
    const elegir = (i: number) => {
        const r = vistos[i];
        if (!r) return;
        caja.close();
        void r.abrir();
    };

    input.addEventListener('input', () => { sel = 0; pintar(); });
    input.addEventListener('keydown', e => {
        if (e.key === 'ArrowDown') { e.preventDefault(); sel = Math.min(vistos.length - 1, sel + 1); pintar(); }
        else if (e.key === 'ArrowUp') { e.preventDefault(); sel = Math.max(0, sel - 1); pintar(); }
        else if (e.key === 'Enter') { e.preventDefault(); elegir(sel); }
    });
    lista.addEventListener('click', e => {
        const f = (e.target as HTMLElement).closest<HTMLElement>('.b-fila');
        if (f) elegir(Number(f.dataset.i));
    });
    lista.addEventListener('mousemove', e => {
        const f = (e.target as HTMLElement).closest<HTMLElement>('.b-fila');
        if (f && Number(f.dataset.i) !== sel) { sel = Number(f.dataset.i); for (const x of lista.querySelectorAll('.b-fila')) x.classList.toggle('sel', x === f); }
    });
    // un clic fuera de la caja la cierra; ⎋ también (el <dialog> lo trae)
    caja.addEventListener('click', e => { if (e.target === caja) caja.close(); });
    const alCambiarLaVentana = () => cuadricula(caja);
    window.addEventListener('resize', alCambiarLaVentana);
    caja.addEventListener('close', () => {
        window.removeEventListener('resize', alCambiarLaVentana);
        caja.remove();
        if (abierto === caja) abierto = undefined;
    });

    caja.showModal();
    input.focus();
    pintar();
    // las fuentes, cada una cuando llegue: las que están en memoria al tiro, las que preguntan algo después
    await Promise.all(fuentes.map(async f => {
        try {
            const rs = await f.resultados();
            todos = [...todos.filter(x => x.fuente !== f), ...rs.map(r => ({ fuente: f, r }))];
        } catch { /* una fuente que falla no tapa a las demás */ }
        if (abierto === caja) pintar();
    }));
}

/** ⌘K (Ctrl+K fuera del Mac) abre o cierra el buscador, antes que la terminal se coma la tecla. */
export function montar(): void {
    window.addEventListener('keydown', e => {
        const mac = /Mac|iPhone|iPad/.test(navigator.platform);
        if (e.code !== 'KeyK' || e.altKey || e.shiftKey || !(mac ? e.metaKey && !e.ctrlKey : e.ctrlKey && !e.metaKey)) return;
        e.preventDefault(); e.stopPropagation();
        void abrir();
    }, true);
}
