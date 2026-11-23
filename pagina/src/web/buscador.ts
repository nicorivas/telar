// El buscador (⌘K): una ventana sobre todo lo demás, como Spotlight, para ir a cualquier cosa escribiendo un poco de
// su nombre: un hilo, un agente, una pestaña del dashboard, una sección de ⚙, un modo, una orden, un proyecto, una
// tarea, un documento del grafo. Sirve también en el modo foco, donde no hay barra ni cabecera.
//
// Lo que se busca lo dan las fuentes, que se registran de afuera (navegador/app.ts): cada una da sus resultados con
// lo que hace abrirlos. Agregar algo que buscar es registrar otra fuente; esta ventana no cambia. Hay de dos clases:
//
//   de la página  lo que ya está a mano (los hilos, los agentes, las pestañas…): lo dan una vez, al abrirse, y aquí se
//                 filtra al escribir, por cuánto se parece cada uno a lo escrito (el nombre pesa más que el detalle, el
//                 comienzo más que el medio)
//   remotas       las que preguntan afuera con lo escrito (los proyectos, las tareas y los documentos del grafo, al
//                 mismo `GET /buscar` de Todo, las tres en un pedido: web/hallados.ts): se les pide al dejar de escribir
//                 (ESPERA), lo que llega de algo escrito antes se descarta, y lo suyo va en el orden en que vino, sin el
//                 puntaje de aquí. Mientras llega, se sigue viendo lo anterior (su grupo dice «…»): la ventana no se
//                 vacía ni salta
//
// En grupos por fuente; las remotas, después de lo de la página que calce. Con dos letras o más, la última fila es la
// que registra `alFinal`: «buscar … en todo», que lleva lo escrito al modo todo (la búsqueda sobre todo junto).

import { esc, normalizar } from '../estilo';
import { barraBuscar } from '../componentes/buscador';
import { item } from '../componentes/item';
import { abrirVentana } from './ventana';

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
    /** lo suyo. Una de la página lo da una vez, al abrirse la ventana (con lo escrito vacío: aquí se filtra); una
     *  `remota`, con lo escrito (dos letras o más), cada vez que se deja de escribir */
    resultados: (q: string) => Resultado[] | Promise<Resultado[]>;
    /** pregunta afuera con lo escrito: lo que da ya calza y viene ordenado (no se puntúa aquí) */
    remota?: boolean;
    /** al abrirse la ventana, antes de escribir nada: que quien contesta empiece a leer */
    preparar?: () => unknown;
}

const fuentes: Fuente[] = [];
/** cuántos de cada grupo se muestran (sin escribir, menos) */
const POR_GRUPO = 8, POR_GRUPO_VACIO = 5;

export function registrar(f: Fuente): void {
    const i = fuentes.findIndex(x => x.clave === f.clave);
    if (i >= 0) fuentes[i] = f; else fuentes.push(f);
}

/** La última fila, con lo escrito (dos letras o más): la da quien la registra, con su grupo. «buscar … en todo», para
 *  ir de lo que está a mano a buscar en todo junto (navegador/app.ts). */
let alFinalDe: { nombre: string; color: string; fila: (q: string) => Resultado } | undefined;
export function alFinal(nombre: string, color: string, fila: (q: string) => Resultado): void {
    alFinalDe = { nombre, color, fila };
}

/** Cuánto se espera, después de la última tecla, para preguntarle a las remotas (ms). */
export const ESPERA = 200;

/** Lo que dan las fuentes remotas mientras la ventana está abierta. `escribir` con cada cambio de lo escrito: con menos de
 *  dos letras no hay nada que pedir (se vacía al tiro); con más, se pide al pasar `espera` sin otra tecla. Una respuesta
 *  de algo escrito antes que lo último pedido se descarta, y también lo que llega con la ventana cerrada. Lo que había
 *  queda hasta que llega lo nuevo (`esperando` dice cuáles siguen preguntando): así la lista no parpadea. Avisa con
 *  `alCambiar` cada vez que hay algo distinto que mostrar. Sin DOM: se prueba en Node (pruebas/buscador.mjs). */
export class Remotas {
    /** lo que dio cada una (por su clave), y para qué se lo pidió */
    readonly dadas = new Map<string, { q: string; rs: Resultado[] }>();
    /** las que siguen preguntando por lo último escrito */
    readonly esperando = new Set<string>();
    private escrito = '';
    private vez = 0;
    private reloj?: ReturnType<typeof setTimeout>;
    private cerrada = false;

    constructor(private readonly fuentes: () => readonly Fuente[], private readonly alCambiar: () => void,
        private readonly espera = ESPERA) {}

    escribir(texto: string): void {
        const q = texto.trim();
        if (this.cerrada || q === this.escrito) return;
        this.escrito = q;
        const vez = ++this.vez;
        clearTimeout(this.reloj);
        if (normalizar(q).length < 2) {
            const habia = this.dadas.size + this.esperando.size;
            this.dadas.clear(); this.esperando.clear();
            if (habia) this.alCambiar();
            return;
        }
        this.reloj = setTimeout(() => this.pedir(q, vez), this.espera);
    }

    private pedir(q: string, vez: number): void {
        const remotas = this.fuentes().filter(f => f.remota);
        if (!remotas.length) return;
        for (const f of remotas) {
            this.esperando.add(f.clave);
            void (async () => {
                let rs: Resultado[] = [];
                try { rs = await f.resultados(q); } catch { /* una remota que falla no muestra nada, ni tapa a las demás */ }
                if (this.cerrada || vez !== this.vez) return;   // de algo escrito antes: lo último ya se pidió
                this.esperando.delete(f.clave);
                this.dadas.set(f.clave, { q, rs });
                this.alCambiar();
            })();
        }
        this.alCambiar();
    }

    /** Lo de una fuente remota para mostrar ahora (lo último que llegó, aunque se esté pidiendo otra cosa). */
    de(clave: string): Resultado[] { return this.dadas.get(clave)?.rs ?? []; }

    cerrar(): void { this.cerrada = true; clearTimeout(this.reloj); }
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

/** La celda de la letra de la página, para la trama ░ del fondo (`--celda-w`, `--celda-h` en el <dialog>: la trama se repite de a una celda). */
function celda(d: HTMLElement): void {
    const m = document.createElement('span');
    m.textContent = '░'.repeat(20);
    m.style.cssText = 'position:absolute;visibility:hidden;white-space:pre;font:inherit;line-height:inherit';
    d.appendChild(m);
    const r = m.getBoundingClientRect();
    m.remove();
    d.style.setProperty('--celda-w', `${r.width / 20 || 8}px`);
    d.style.setProperty('--celda-h', `${parseFloat(getComputedStyle(d).lineHeight) || r.height || 16}px`);
}

/** Abrir el buscador (o cerrarlo, si ya está abierto). Es una ventana `arriba` (componentes/ventana.ts, abrirVentana): el campo
 *  (la barra de un buscador), la lista en grupos por fuente (filas `item()`) y las teclas en el pie. */
export async function abrir(): Promise<void> {
    if (abierto) { abierto.close(); return; }
    let caja!: HTMLDialogElement, lista!: HTMLElement, input!: HTMLInputElement, cerrarVentana!: () => void;
    let todos: { fuente: Fuente; r: Resultado }[] = [];
    let vistos: Resultado[] = [], sel = 0;
    /** la fila elegida, por su grupo y lo que dice: si lo remoto llega y mueve las filas, sigue elegida la misma */
    let claves: string[] = [];
    let remotas!: Remotas;

    const pintar = (mantener = false) => {
        if (abierto !== caja) return;
        const antes = mantener ? claves[sel] : undefined;
        const q = normalizar(input.value.trim());
        const grupos = fuentes.map(f => {
            // las remotas, lo que llegó, en su orden (solo con algo escrito); después de lo de la página que calce
            if (f.remota) return { f, suyos: q.length >= 2 ? remotas.de(f.clave).slice(0, POR_GRUPO).map(r => ({ r, p: 1 })) : [], mejor: 0 };
            const suyos = todos.filter(x => x.fuente === f).map(x => ({ r: x.r, p: puntaje(q, x.r) })).filter(x => x.p > 0)
                .sort((a, b) => q ? b.p - a.p || (b.r.peso ?? 0) - (a.r.peso ?? 0) : (b.r.peso ?? 0) - (a.r.peso ?? 0));
            return { f, suyos: suyos.slice(0, q ? POR_GRUPO : POR_GRUPO_VACIO), mejor: suyos[0]?.p ?? 0 };
        }).filter(g => g.suyos.length)
            .sort((a, b) => q ? b.mejor - a.mejor || a.f.orden - b.f.orden : a.f.orden - b.f.orden);
        // la última, siempre al final: con lo escrito, tal cual
        const escrito = input.value.trim();
        if (alFinalDe && normalizar(escrito).length >= 2) {
            grupos.push({ f: { clave: '__final', nombre: alFinalDe.nombre, orden: 99, color: alFinalDe.color, resultados: () => [] },
                suyos: [{ r: alFinalDe.fila(escrito), p: 1 }], mejor: 0 });
        }
        vistos = grupos.flatMap(g => g.suyos.map(x => x.r));
        claves = grupos.flatMap(g => g.suyos.map(x => `${g.f.clave}\u0000${x.r.titulo}\u0000${x.r.detalle ?? ''}`));
        const igual = antes === undefined ? -1 : claves.indexOf(antes);
        sel = Math.min(igual >= 0 ? igual : sel, Math.max(0, vistos.length - 1));
        let n = 0;
        const espera = (f: Fuente) => (f.remota && remotas.esperando.has(f.clave) ? '<span class="b-espera"> …</span>' : '');
        lista.innerHTML = grupos.map(g => `<div class="b-grupo" style="--b-color: var(--${esc(g.f.color ?? 'dim')})">${esc(g.f.nombre)}${espera(g.f)}</div>` + g.suyos.map(({ r }) => {
            const i = n++;
            return `<div class="b-fila" style="--b-color: var(--${esc(g.f.color ?? 'dim')})">` + item({
                titulo: r.titulo, inicio: [{ texto: r.icono ?? ' ' }], sufijo: r.detalle ? [{ texto: r.detalle }] : undefined,
                activa: i === sel, datos: { i: String(i) },
            }) + '</div>';
        }).join('')).join('') || `<div class="ventana-vacia">${q && !remotas.esperando.size ? 'nada calza' : q ? 'buscando…' : 'leyendo…'}</div>`;
        lista.querySelector('.activa')?.scrollIntoView({ block: 'nearest' });
    };
    const elegir = (i: number) => {
        const r = vistos[i];
        if (!r) return;
        cerrarVentana();
        void r.abrir();
    };
    const marcar = (nueva: number) => {
        sel = nueva;
        let i = 0;
        for (const f of lista.querySelectorAll('.item')) f.classList.toggle('activa', i++ === sel);
        lista.querySelector('.activa')?.scrollIntoView({ block: 'nearest' });
    };

    void abrirVentana({
        lugar: 'arriba', clase: 'ventana-buscador',
        campo: barraBuscar({ placeholder: 'hilos, agentes, el dashboard, la configuración, modos, proyectos, tareas, documentos…',
            ayuda: 'ir a cualquier cosa escribiendo un poco de su nombre' }),
        cuerpo: '<div class="ventana-lista b-lista"></div>',
        pie: '<div class="b-pie">↑↓ elegir · ⏎ abrir · ⎋ cerrar · ⌘K</div>',
    }, {
        foco: 'input.buscar', clase: 'ventana-buscador',
        montar: (d, cerrar) => {
            caja = d; cerrarVentana = () => cerrar(undefined);
            abierto = d;
            input = d.querySelector<HTMLInputElement>('input.buscar')!;
            lista = d.querySelector<HTMLElement>('.b-lista')!;
            remotas = new Remotas(() => fuentes, () => pintar(true));
            celda(d);
            input.addEventListener('input', () => { sel = 0; remotas.escribir(input.value); pintar(); });
            input.addEventListener('keydown', e => {
                if (e.key === 'ArrowDown') { e.preventDefault(); marcar(Math.min(vistos.length - 1, sel + 1)); }
                else if (e.key === 'ArrowUp') { e.preventDefault(); marcar(Math.max(0, sel - 1)); }
                else if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); elegir(sel); }
            });
            lista.addEventListener('click', e => {
                const f = (e.target as HTMLElement).closest<HTMLElement>('.item[data-i]');
                if (f) elegir(Number(f.dataset.i));
            });
            lista.addEventListener('mousemove', e => {
                const f = (e.target as HTMLElement).closest<HTMLElement>('.item[data-i]');
                if (f && Number(f.dataset.i) !== sel) marcar(Number(f.dataset.i));
            });
            const alCambiarLaVentana = () => celda(d);
            window.addEventListener('resize', alCambiarLaVentana);
            return () => {
                remotas.cerrar();
                window.removeEventListener('resize', alCambiarLaVentana);
                if (abierto === d) abierto = undefined;
            };
        },
    });
    pintar();
    for (const f of fuentes) try { f.preparar?.(); } catch { /* solo un adelanto */ }
    // las fuentes de la página, cada una cuando llegue: las que están en memoria al tiro, las que preguntan algo después
    // (las remotas, al escribir)
    await Promise.all(fuentes.filter(f => !f.remota).map(async f => {
        try {
            const rs = await f.resultados('');
            todos = [...todos.filter(x => x.fuente !== f), ...rs.map(r => ({ fuente: f, r }))];
        } catch { /* una fuente que falla no tapa a las demás */ }
        pintar();
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
