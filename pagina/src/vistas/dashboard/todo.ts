// «todo»: ver y buscar todo, sin filtros ni topes (docs/propuestas/orden-por-modos.md, pasos 2 y 5). Es la vista del
// modo todo, que nunca es el de partida pero siempre está a un paso (su ícono en la cabecera, ⌥⇧4, «ver todo» en
// táctica). Se dibuja con el componente (componentes/todo.ts):
//
//   sin buscar  cada pestaña del dashboard, entera a un clic, con lo que tiene en el mundo puesto y lo que queda en los
//               otros cuando se sabe (lo que espera, las tareas, el calendario, los proyectos)
//   buscando    lo que da `GET /buscar` (telar.servicios.buscar: lo que espera, las tareas, las casillas, los hilos, los
//               proyectos, los objetos de cada tipo de un módulo que los lista —los documentos de un grafo— y los
//               bloques), por fuente: lo del mundo puesto primero y lo de los otros al final, porque en todo el mundo
//               ordena y no esconde. Se pide con el mundo puesto (`primero`): así lo suyo entra al tope de cada fuente
//               aunque los otros tengan mucho más que calce; si el mundo cambia con Todo abierto, se vuelve a pedir
//
// Un clic en una cosa la abre donde vive (su dirección; una casilla, o un objeto que es un documento, su documento en el
// visor; la fila de un bloque, su pestaña); en una fuente, su pestaña entera, y si no tiene (los objetos de un módulo),
// solo lo hallado de ella, entero.

import * as cli from '../../cli';
import { esc, normalizar } from '../../estilo';
import * as ui from '../../web/ui';
import * as mundo from '../../web/mundo';
import * as modos from '../../web/modos';
import { abrirHallado, cuandoCorto, deFuente } from '../../web/hallados';
import { barraTodo, todo, type Cosa, type Fuente } from '../../componentes/todo';
import type { Accion, Pantalla, Tablero } from './pantalla';

/** Una pestaña del dashboard, como la da el núcleo (panel.ts). */
export interface PestanaDeTodo { clave: string; accion: string; valor: string; nombre: string }

/** El ícono y la tinta de cada fuente: los de lo hallado (web/hallados.ts, que comparte con ⌘K). */
export { deFuente };

/** Cuántas de una lista hay en cada mundo (y sin clasificar). */
function porMundo<T>(xs: readonly T[], de: (x: T) => string | undefined): Record<string, number> {
    const c: Record<string, number> = { 'sin-clasificar': 0 };
    for (const x of xs) { const m = de(x) || 'sin-clasificar'; c[m] = (c[m] ?? 0) + 1; }
    return c;
}

/** Una cosa de la búsqueda, como la dibuja el componente: su clave es su lugar en la respuesta (`fuente|n`). Al final, lo
 *  que ya pasó dice su estado y lo demás cuándo; un objeto de un módulo sin fecha, su estado («12 conexiones»). */
export function cosaDe(h: cli.JsonHallado, clave: string): Cosa {
    const antes = h.fuente === 'tareas' ? h.id : h.fuente === 'esperas' ? h.estado.replace(/^avance:/, '') : '';
    const espera = h.fuente === 'esperas' || (h.fuente === 'hilos' && h.estado === 'espera');
    const meta = h.pasada && h.estado ? h.estado : cuandoCorto(h.cuando) || (h.fuente.startsWith('objeto:') ? h.estado : '');
    return { fuente: h.fuente, id: clave, titulo: h.titulo, antes, donde: h.donde, mundo: h.mundo,
        meta, pasada: h.pasada, tono: espera ? 'espera' : undefined };
}

export class PantallaTodo implements Pantalla {
    readonly pantallas = ['todo'] as const;
    /** se repinta al buscar, no con el reloj: movería el scroll */
    readonly conReloj = [] as const;
    private q = '';
    private filtro = '';
    private resultado?: cli.JsonBusqueda;
    private buscado = '';
    private error = '';
    private espera?: number;
    /** lo que vino `tarde` se vuelve a pedir, unas veces, mientras lo buscado no cambie */
    private reintento?: number;
    private reintentos = 0;
    private proyectos?: cli.JsonProyecto[];
    /** lo hallado, por su clave (`fuente|n`): lo que abre un clic */
    private porClave = new Map<string, cli.JsonHallado>();

    readonly acciones: Record<string, Accion> = {
        todo: () => this.abrir(),
        'todo-abrir': v => v && this.abrirCosa(v),
        'todo-fuente': v => v && this.abrirFuente(v),
        'todo-releer': () => { this.resultado = undefined; void this.buscar(true, true); },
        'todo-volver': () => this.pintar(),
    };

    constructor(private readonly t: Tablero, private readonly pestanas: () => PestanaDeTodo[],
        private readonly esperas: () => cli.JsonEspera[] | undefined) {
        // otro mundo puesto con Todo abierto: lo hallado se vuelve a pedir con él primero (sin tocar el filtro); si Todo
        // no está a la vista (el mundo nuevo puso otro modo), al volver a abrirse
        mundo.alCambiar(() => { if (this.t.pantalla === 'todo' && this.deOtroMundo()) this.rebuscar(); });
    }

    /** El mundo cuyo contenido va primero en cada fuente: el puesto ('' con ambos). */
    private primero(): string { return mundo.puesto().mundo; }

    /** Si lo hallado se pidió con otro mundo primero que el puesto ahora. */
    private deOtroMundo(): boolean {
        return !!this.buscado && !!this.resultado && this.resultado.q === this.buscado && (this.resultado.primero ?? '') !== this.primero();
    }

    /** Lo buscado, de nuevo con el mundo puesto primero, sin tocar el filtro. */
    private rebuscar(): void {
        clearTimeout(this.reintento);
        this.reintentos = 0;
        void this.pedir(this.buscado);
    }

    pestanaMarcada(): string { return 'todo'; }

    /** Lo que se buscará al abrirse (⌘K, «buscar … en todo»). */
    preparar(q: string): void {
        this.q = q;
        this.filtro = '';
    }

    async abrir(): Promise<void> {
        this.t.montar();
        this.t.ir('todo');
        this.pintar();
        if (this.q.trim() && this.resultado?.q !== this.q.trim()) void this.buscar();
        else if (this.q.trim() && this.deOtroMundo()) this.rebuscar();
        // sin nada que buscar todavía, que telar empiece a leer: mientras se escribe, se lee
        else void cli.prepararBusqueda();
        // los proyectos, para su cuenta por mundo (una vez: su pestaña los relee)
        if (!this.proyectos) {
            const r = await cli.proyectos();
            this.proyectos = r.datos?.proyectos ?? [];
            if (this.t.pantalla === 'todo' && !this.q) this.pintar();
        }
    }

    /** Las pestañas, cada una como una fuente, con sus cuentas por mundo si se saben. */
    private fuentes(): Fuente[] {
        const d = this.t.dia();
        const esperas = this.esperas();
        // las tareas: lo que lista su pestaña (las casillas de los documentos y lo de los proveedores), sin lo hecho
        const tareas = (d?.pendientes ?? []).filter(f => f.clase !== 'evento' && !f.hecho);
        const inis = modos.tipos('iniciativas');
        const fuentes: Fuente[] = this.pestanas().filter(p => p.clave !== 'todo').map(p => {
            const [icono, color] = deFuente(p.clave);
            // (lo que espera de un agente que pide esconderse fuera de su mundo no se cuenta ni se ve: web/mundo.ts, `deAgenteAjeno`)
            const cuenta = p.clave === 'esperas' && esperas ? porMundo(esperas.filter(e => !mundo.deAgenteAjeno(e)), e => e.mundo)
                : p.clave === 'revisar' && d ? porMundo(tareas, f => f.mundo)
                    : p.clave === 'calendario' && d?.agenda ? porMundo(d.agenda, f => f.mundo)
                        : p.clave === 'proyectos' && this.proyectos ? porMundo(this.proyectos.filter(x => !inis.includes(x.arquetipo.toLowerCase())), x => x.mundo) : {};
            return { clave: p.clave, nombre: p.nombre, icono, color, cuenta, dice: {} };
        });
        // las iniciativas, si el modo las tiene: no son una pestaña, son una sección de la de proyectos, que se abre sola
        const i = fuentes.findIndex(f => f.clave === 'proyectos');
        if (inis.length && i >= 0) {
            const [icono, color] = deFuente('iniciativas');
            fuentes.splice(i + 1, 0, { clave: 'iniciativas', nombre: 'iniciativas', icono, color, dice: {},
                cuenta: this.proyectos ? porMundo(this.proyectos.filter(x => inis.includes(x.arquetipo.toLowerCase())), x => x.mundo) : {} });
        }
        return fuentes;
    }

    /** Las fuentes de la búsqueda, en su orden, con su ícono. */
    private fuentesDeBusqueda(r: cli.JsonBusqueda): Fuente[] {
        return r.fuentes.map(f => { const [icono, color] = deFuente(f.clave); return { clave: f.clave, nombre: f.nombre, icono, color, cuenta: {}, dice: {} }; });
    }

    pintar(): void {
        if (!this.t.panel) return;
        this.t.teclas.clear();
        const cursor = document.activeElement?.id === 'todo-q' ? (document.activeElement as HTMLInputElement).selectionStart ?? 0 : -1;
        const puesto = mundo.puesto().mundo;
        const mundos = mundo.declarados();
        const r = this.q && this.resultado?.q === this.buscado ? this.resultado : undefined;
        const h: string[] = [];
        if (this.error) h.push(`<div class="fila falla">${esc(this.error)}</div>`);
        if (r) for (const f of r.fuentes) {
            // la que viene tarde y sin nada sigue leyéndose: se pide de nuevo sola (reintentar); la que trae lo de antes
            // no lo dice, porque la próxima vuelta la pone al día
            const antes = f.leida ? `; sale lo de las ${f.leida.slice(11, 16)}` : '';
            if (f.tarde && !f.leida) h.push(`<div class="fila dim">${esc(f.nombre)}: sigue leyéndose…</div>`);
            else if (f.falla && !f.tarde) h.push(`<div class="fila falla">${esc(f.nombre)}: no se pudo leer: ${esc(f.falla)}${esc(antes)}</div>`);
        }
        let props;
        if (this.q && r) {
            this.porClave.clear();
            // en todo, lo de otro mundo va al final; lo de un agente que pide esconderse fuera de su mundo (su hilo, lo que espera de él, lo de su
            // carpeta), no sale (web/mundo.ts, `deAgenteAjeno`), ni se cuenta
            const ajenos = r.fuentes.reduce((n, f) => n + f.hallados.filter(mundo.deAgenteAjeno).length, 0);
            const halladas = r.fuentes.flatMap(f => f.hallados.flatMap((x, i) => {
                if (mundo.deAgenteAjeno(x)) return [];
                const k = `${f.clave}|${i}`; this.porClave.set(k, x); return [cosaDe(x, k)];
            }));
            props = { fuentes: this.fuentesDeBusqueda(r), mundos, puesto, buscado: this.q, halladas, filtro: this.filtro,
                total: r.fuentes.reduce((n, f) => n + f.total, 0) - ajenos };
        } else {
            props = { fuentes: this.fuentes(), mundos, puesto, buscado: this.q, halladas: [], aviso: this.q ? 'buscando…' : '' };
        }
        h.push(todo(props));
        const b = barraTodo(props);
        this.t.pintar(h, { nombre: b.nombre, color: b.color, ayuda: b.ayuda, acciones: b.acciones, sinReleer: true });
        this.montar(cursor);
    }

    /** Después de pintar: el buscador (busca al dejar de escribir, ⎋ borra, ⏎ abre la primera) y el filtro por fuente. */
    private montar(cursor: number): void {
        const b = document.getElementById('todo-q') as HTMLInputElement | null;
        if (!b) return;
        b.value = this.q;
        if (cursor >= 0) { b.focus(); b.setSelectionRange(cursor, cursor); } else if (!this.q) b.focus();
        b.addEventListener('input', () => {
            this.q = b.value.trim() ? b.value : '';
            clearTimeout(this.espera);
            this.espera = window.setTimeout(() => void this.buscar(), 300);
        });
        b.addEventListener('keydown', e => {
            if (e.key === 'Escape') {
                e.preventDefault();
                if (b.value) { b.value = ''; this.q = ''; this.filtro = ''; this.pintar(); } else b.blur();
            } else if (e.key === 'Enter') {
                e.preventDefault();
                const primera = document.querySelector<HTMLElement>('.todo .todo-cosa[data-valor]');
                if (primera?.dataset.valor) void this.abrirCosa(primera.dataset.valor);
            }
        });
        document.querySelector('.todo .todo-filtros')?.addEventListener('click', e => {
            const op = (e.target as HTMLElement).closest<HTMLElement>('.filtros-op');
            if (!op) return;
            e.stopPropagation();
            const clave = (op.dataset.id ?? '').replace(/^fuente:/, '');
            this.filtro = this.filtro === clave ? '' : clave;
            this.pintar();
        });
    }

    /** Busca lo escrito (si cambió, o `forzar`; `releer`, que telar lea todo de nuevo); se repinta al llegar, si sigue
     *  siendo lo escrito. */
    private async buscar(forzar = false, releer = false): Promise<void> {
        const q = this.q.trim();
        clearTimeout(this.reintento);
        this.reintentos = 0;
        if (normalizar(q).length < 2) { this.resultado = undefined; this.buscado = ''; this.pintar(); return; }
        if (!forzar && q === this.buscado && this.resultado && (this.resultado.primero ?? '') === this.primero()) return;
        this.buscado = q;
        this.filtro = '';
        this.pintar();
        await this.pedir(q, releer);
    }

    /** Pide la búsqueda (con el mundo puesto primero) y la pone, si sigue siendo lo buscado en ese mundo. Si alguna
     *  fuente vino tarde (telar no espera a la lenta más que su tope, y la sigue leyendo), la pide de nuevo al rato, hasta
     *  REINTENTOS veces: lo que faltaba llega solo, sin tocar el filtro; y si no cambió nada, sin repintar. */
    private async pedir(q: string, releer = false): Promise<void> {
        const primero = this.primero();
        const r = await cli.buscar(q, 30, releer, primero);
        // otra búsqueda, u otro mundo mientras llegaba: la que corresponde la pide quien la cambió
        if (this.buscado !== q || this.primero() !== primero) return;
        const igual = !!r.datos && !!this.resultado && JSON.stringify(r.datos) === JSON.stringify(this.resultado);
        if (r.datos) { this.resultado = r.datos; this.error = ''; } else this.error = r.error ?? 'no se pudo buscar';
        if (this.t.pantalla === 'todo' && !igual) this.pintar();
        if (r.datos?.fuentes.some(f => f.tarde) && this.reintentos < PantallaTodo.REINTENTOS) {
            this.reintentos++;
            this.reintento = window.setTimeout(() => {
                if (this.buscado === q && this.primero() === primero && this.t.pantalla === 'todo') void this.pedir(q);
            }, 1500);
        }
    }

    static readonly REINTENTOS = 5;

    /** Abrir lo hallado donde vive (web/hallados.ts, lo mismo que ⌘K: un documento en el visor con sus conexiones, lo
     *  demás su dirección); la fila de un bloque, su pestaña. */
    private async abrirCosa(clave: string): Promise<void> {
        const h = this.porClave.get(clave);
        if (!h || await abrirHallado(h)) return;
        if (h.fuente.startsWith('bloque:')) await this.t.accion('bloque', h.fuente.slice(7));
    }

    /** Una fuente, entera: su pestaña (las de la búsqueda, la que les corresponde). Los objetos de un módulo no tienen
     *  pestaña: buscando, lo hallado de esa fuente, entero (el filtro por fuente); sin buscar no se listan aquí. */
    private async abrirFuente(clave: string): Promise<void> {
        const destino: Record<string, string> = { tareas: 'revisar', casillas: 'revisar', esperas: 'esperas', proyectos: 'proyectos' };
        if (clave === 'iniciativas') { await this.t.accion('proy-iniciativas', 'solas'); return; }
        if (clave.startsWith('objeto:')) {
            if (this.q && this.filtro !== clave) { this.filtro = clave; this.pintar(); }
            return;
        }
        const k = destino[clave] ?? clave;
        const p = this.pestanas().find(x => x.clave === k);
        if (p) await this.t.accion(p.accion, p.valor);
        else if (clave === 'hilos') ui.estado('telar: los hilos están en la barra de la izquierda (en todo, con los de todos los mundos)', 5000);
    }
}
