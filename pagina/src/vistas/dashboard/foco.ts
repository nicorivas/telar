// «foco»: lo más urgente e importante, de a pocas tarjetas, para decidir una por una. Un clic en una tarjeta la elige
// (la primera viene elegida) y a la derecha aparecen sus acciones, las que le corresponden a esa tarea: una vencida
// trae «hoy» y «mañana» a un clic; una sin tamaño, «rápida» y «larga». También se puede arrastrar la tarjeta a una
// acción. La tarjeta se va y entra la siguiente, ya elegida. Una tarea vencida va primero y no se queda vencida: o se le da una fecha real (hoy, mañana…), o se suelta.
//
// Dos modos, porque no se trabajan igual: **gestión** (lo rápido, media hora o menos: hasta cinco, para despachar
// en una sesión) y **concentración** (lo largo, horas o días: dos a lo más, cada una necesita un bloque propio). Una
// tarea sin tamaño va en gestión, y sus acciones traen «es rápida» y «es larga».
//
// Solo lo que es de la persona (sin dueño, o ella) y tiene ficha (una tarea, no la casilla de un documento). El orden:
// las vencidas, las de hoy, y después la urgencia de «tareas» (la prioridad manda; la fecha desempata).

import * as cli from '../../cli';
import { esc } from '../../estilo';
import { C, I } from '../../web/iconos';
import * as ui from '../../web/ui';
import { esMia, olvidarDia, pendientes, plazo, yo } from './dia';
import { type Accion, type Pantalla, type Tablero } from './pantalla';
import { asignar, elegirFecha, llevarPendiente, marcarHecha } from './tareas';

type Modo = 'gestion' | 'concentracion';
type Fila = ReturnType<typeof pendientes>[number];
type Casilla = { clave: string; nombre: string; icono: string; color: string; ayuda: string };

/** cuántas tarjetas a la vista en cada modo: las demás esperan su turno */
const TOPE: Record<Modo, number> = { gestion: 5, concentracion: 2 };

const HECHA: Casilla = { clave: 'hecha', nombre: 'hecha', icono: I.hecha, color: C.hecho, ayuda: 'ya está: se marca hecha' };
const FECHA: Casilla = { clave: 'fecha', nombre: 'nueva fecha', icono: I.fecha, color: C.cambiar, ayuda: 'hoy, mañana, el lunes…: cuándo de verdad' };
const ASIGNAR: Casilla = { clave: 'asignar', nombre: 'de otra persona', icono: I.persona, color: C.ir, ayuda: 'asignarla: sale de tu foco' };
const DESCARTAR: Casilla = { clave: 'descartar', nombre: 'descartar', icono: I.descartar, color: C.quitar, ayuda: 'no se va a hacer: sale de la lista' };

/** Las casillas de la derecha, en cada modo. */
const CASILLAS: Record<Modo, Casilla[]> = {
    gestion: [
        HECHA,
        FECHA,
        ASIGNAR,
        { clave: 'claude', nombre: 'con Claude', icono: I.agente, color: C.agente, ayuda: 'abrir un hilo que la trabaje contigo' },
        { clave: 'larga', nombre: 'es larga', icono: I.consolidar, color: C.otro, ayuda: 'toma horas o días: pasa a concentración' },
        DESCARTAR,
    ],
    concentracion: [
        { clave: 'empezar', nombre: 'empezar ahora', icono: I.retomar, color: C.agente, ayuda: 'un hilo con Claude para trabajarla, ya' },
        { clave: 'bloque', nombre: 'bloquear tiempo', icono: I.fecha, color: C.ir, ayuda: 'que Claude le busque un bloque de 2 a 3 horas en tu calendario' },
        { clave: 'paso', nombre: 'sacar el primer paso', icono: I.nuevo, color: C.hecho, ayuda: 'una tarea rápida que la empieza: va a gestión; esta espera su bloque' },
        HECHA,
        FECHA,
        ASIGNAR,
        { clave: 'rapida', nombre: 'es rápida', icono: I.hecha, color: C.otro, ayuda: 'toma media hora o menos: pasa a gestión' },
        DESCARTAR,
    ],
};

const hoyISO = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };

export class PantallaFoco implements Pantalla {
    readonly pantallas = ['foco'] as const;
    /** se repinta con cada lectura del día (cada minuto, y cuando avisan que algo cambió): una tarea que cerró otro
     *  (un agente, la persona en otra pestaña) sale sola */
    readonly conReloj = ['foco'] as const;
    /** las que ya se decidieron en esta pasada: salen al tiro, sin esperar a que el día se relea */
    private readonly hechas = new Set<string>();
    /** el tamaño que se le acaba de dar a una (mientras el día se relee): la tarjeta cambia de modo al tiro */
    private readonly tamanos = new Map<string, string>();
    /** la tarjeta elegida con un clic, para soltarla con otro clic en una casilla */
    private elegida = '';
    /** lo que se está haciendo con la elegida (una acción va a telar, quizás por el bus): mientras, las acciones no se
     *  aprietan dos veces ni se aprieta otra encima */
    private haciendo = '';
    private modo: Modo = (() => { try { return localStorage.getItem('telar.foco.modo') === 'concentracion' ? 'concentracion' : 'gestion'; } catch { return 'gestion'; } })();

    readonly acciones: Record<string, Accion> = {
        'foco': () => this.abrir(),
        // ↻: volver a leer las tareas ya, de su proveedor (no lo guardado de hace un rato)
        'foco-releer': async () => {
            if (this.haciendo) return;
            this.haciendo = 'leyendo las tareas…';
            this.pintar();
            try {
                await this.t.actualizar(true);
                // lo leído ya trae lo decidido en esta pasada: lo que se escondía a mano ya no hace falta
                this.hechas.clear();
                this.tamanos.clear();
            } finally {
                this.haciendo = '';
                this.pintar();
            }
        },
        'foco-modo': v => {
            if (v !== 'gestion' && v !== 'concentracion') return;
            this.modo = v; this.elegida = '';
            try { localStorage.setItem('telar.foco.modo', v); } catch { /* sin almacén: solo esta vez */ }
            this.pintar();
        },
        'foco-elegir': v => { if (v && v !== this.elegida && !this.haciendo) { this.elegida = v; this.pintar(); } },
        'foco-soltar': v => {
            // arrastrada: «<casilla>|<tarjeta>»; con un clic, la casilla y la tarjeta elegida antes
            const [casilla, tarjeta] = (v ?? '').split('|');
            const cual = tarjeta || this.elegida;
            if (!casilla || !cual) { ui.estado('elige una tarjeta, o arrástrala a una casilla', 3000); return; }
            if (this.haciendo) return;
            return this.decidir(casilla, cual);
        },
    };

    constructor(private readonly t: Tablero) {}

    /** Es una subpestaña de «tareas»: la barra marca esa fila. */
    pestanaMarcada(): string { return 'revisar'; }

    private async abrir(): Promise<void> {
        this.t.ir('foco');
        this.pintar();
        await this.t.actualizar(false);
        if (this.t.pantalla === 'foco') this.pintar();
    }

    private tamanoDe(p: Fila): string { return this.tamanos.get(p.fila.id || p.ref) ?? p.fila.tamano ?? ''; }

    /** Las tareas de la persona para un modo, en orden de foco: vencidas, de hoy, y la urgencia de siempre. */
    private cola(modo: Modo): Fila[] {
        const d = this.t.dia();
        if (!d) return [];
        const decididas = this.t.tareas.decididas;
        const peso = (p: Fila) => (p.dias !== null && p.dias < 0 ? 0 : p.dias === 0 ? 1 : 2);
        return pendientes(d)
            .filter(p => p.fila.ficha && esMia(p.fila.dueno ?? '') && !this.hechas.has(p.fila.id || p.ref) && !decididas.has(p.fila.id || p.ref))
            .filter(p => (this.tamanoDe(p) === 'larga') === (modo === 'concentracion'))
            .sort((a, b) => peso(a) - peso(b) || (peso(a) < 2 ? (a.dias ?? 0) - (b.dias ?? 0) : 0) || a.urgencia - b.urgencia);
    }

    pintar(): void {
        if (this.t.pantalla !== 'foco') return;
        this.t.teclas.clear();
        const d = this.t.dia();
        if (!d) { this.t.pintar(['<div class="vacio">leyendo…</div>']); return; }
        const cola = this.cola(this.modo);
        const otro: Modo = this.modo === 'gestion' ? 'concentracion' : 'gestion';
        const vista = cola.slice(0, TOPE[this.modo]);
        // siempre hay una elegida, si hay alguna: la que se eligió, o la primera
        if (!vista.some(p => this.valor(p) === this.elegida)) this.elegida = vista[0] ? this.valor(vista[0]) : '';
        const elegida = vista.find(p => this.valor(p) === this.elegida);
        const vencidas = cola.filter(p => p.dias !== null && p.dias < 0).length;
        const modos: [Modo, string, string, string][] = [
            ['gestion', I.hecha, 'gestión', 'lo rápido (media hora o menos): despachar varias en una sesión'],
            ['concentracion', I.consolidar, 'concentración', 'lo largo (horas o días): una o dos, cada una con su bloque'],
        ];
        const h: string[] = ['<div id="foco">'];
        h.push('<div class="foco-cab">' + modos.map(([m, ic, nombre, ayuda]) => {
            const n = m === this.modo ? cola.length : this.cola(m).length;
            return `<a class="modo${m === this.modo ? ' si' : ''}" data-accion="foco-modo" data-valor="${m}" title="${esc(ayuda)}"><span class="i">${ic}</span> ${nombre} <span class="n">${n}</span></a>`;
        }).join('')
            + (vencidas ? `<span class="vencidas">${vencidas} vencida${vencidas === 1 ? '' : 's'}: dales fecha o suéltalas</span>` : '')
            + `<a class="i releer" data-accion="foco-releer" title="volver a leer las tareas ahora (se releen solas cada minuto y cuando algo cambia)">${I.releer}</a>`
            + '</div>');
        h.push(`<div class="foco-cuerpo ${this.modo}"><div class="tarjetas">`);
        if (!vista.length) {
            const quedan = this.cola(otro).length;
            h.push(`<div class="vacio"><span class="i">${I.hecha}</span> ${this.modo === 'gestion' ? 'nada rápido pendiente' : 'nada largo pendiente'}.`
                + (quedan ? ` <a data-accion="foco-modo" data-valor="${otro}">${quedan} en ${otro === 'gestion' ? 'gestión' : 'concentración'}</a>` : ' Respira.') + '</div>');
        }
        for (const p of vista) h.push(this.tarjeta(p));
        if (cola.length > vista.length) h.push(`<div class="dim">${cola.length - vista.length} más esperan su turno</div>`);
        h.push(`</div><div class="casillas${this.haciendo ? ' ocupadas' : ''}">`);
        if (elegida) {
            h.push(`<div class="de-cual"><span class="dim">${esc(elegida.fila.id || elegida.ref)}</span> ${esc(elegida.texto)}</div>`);
            if (this.haciendo) h.push(`<div class="haciendo"><span class="i">${I.viaja}</span> ${esc(this.haciendo)}</div>`);
            for (const c of this.accionesDe(elegida)) {
                h.push(`<div class="casilla" data-suelta="${c.clave}" data-accion="foco-soltar" data-valor="${c.clave}" style="--c: var(--${c.color})"`
                    + ` title="${esc(c.ayuda)}"><span class="i">${c.icono}</span> ${esc(c.nombre)}</div>`);
            }
        }
        h.push('</div></div></div>');
        this.t.pintar(h);
    }

    /** Las acciones de una tarea: las de su modo, más las que pide su situación. Una vencida, «hoy» y «mañana» a un
     *  clic (primero: o va hoy, o tiene fecha de verdad); una sin tamaño, «rápida» o «larga» (en vez de «es larga»). */
    private accionesDe(p: Fila): Casilla[] {
        let lista = [...CASILLAS[this.modo]];
        if (p.dias !== null && p.dias < 0) {
            lista = [{ clave: 'hoy', nombre: 'va hoy', icono: I.fecha, color: C.cambiar, ayuda: 'la haces hoy: su fecha pasa a hoy' },
                { clave: 'manana', nombre: 'mañana', icono: I.fecha, color: C.cambiar, ayuda: 'su fecha pasa a mañana' }, ...lista];
        }
        if (!this.tamanoDe(p)) {
            lista = lista.filter(c => c.clave !== 'larga' && c.clave !== 'rapida');
            lista.push({ clave: 'rapida', nombre: 'es rápida', icono: I.hecha, color: C.otro, ayuda: 'media hora o menos: se queda en gestión' },
                { clave: 'larga', nombre: 'es larga', icono: I.consolidar, color: C.otro, ayuda: 'horas o días: pasa a concentración' });
        }
        return lista;
    }

    private valor(p: Fila): string { return JSON.stringify([p.fila.proveedor, p.fila.id || p.ref, p.ref]); }

    private tarjeta(p: Fila): string {
        const valor = this.valor(p);
        const vencida = p.dias !== null && p.dias < 0;
        const proy = this.t.proyectos.deFila(p.fila);
        const donde = proy ? (proy.cliente && !proy.interno ? proy.cliente : proy.nombre) : (p.fila.area ?? '');
        // sin tamaño: lo dice, y sus acciones traen «es rápida» y «es larga»
        const sinTamano = !this.tamanoDe(p) ? '<span class="sin-tamano">sin tamaño</span>' : '';
        return `<div class="tarjeta${vencida ? ' vencida' : ''}${this.elegida === valor ? ' sel' : ''}" draggable="true" data-arrastra="${esc(valor)}"`
            + ` data-accion="foco-elegir" data-valor="${esc(valor)}" title="${esc(`${p.fila.id || p.ref} · ${p.texto}\nclic: sus acciones, a la derecha (o arrástrala a una)`)}">`
            + `<div class="t">${esc(p.texto)}</div>`
            + `<div class="m"><span class="dim">${esc(p.fila.id || p.ref)}</span>${donde ? `<span class="dim">${esc(donde)}</span>` : ''}${sinTamano}`
            + `<span class="cuando">${plazo(p.dias)}</span></div></div>`;
    }

    /** Darle un tamaño a una tarea: en la tarjeta, al tiro; en su archivo, por su acción. */
    private async ponerTamano(valor: string, tamano: string): Promise<boolean> {
        const [proveedor, id] = JSON.parse(valor) as string[];
        const r = await cli.accionPorRol(id, proveedor, 'tamano', tamano);
        if (!r.datos) { void ui.aviso(`telar: ${r.error ?? `no pude cambiarle el tamaño a ${id}`}`); return false; }
        this.tamanos.set(id, tamano);
        this.elegida = '';
        ui.estado(`${id}: ${tamano === 'larga' ? 'larga, en concentración' : 'rápida, en gestión'}`, 4000);
        olvidarDia();
        this.pintar();
        void this.t.actualizar(true).then(() => this.pintar());
        return true;
    }

    /** Lo que hace cada casilla con una tarea. Si se decidió, sale de la vista y entra la siguiente. */
    private async decidir(casilla: string, valor: string): Promise<void> {
        const [proveedor, id, ref] = JSON.parse(valor) as string[];
        // con Claude: abrir o retomar su hilo toma segundos (a veces en el servidor, por ssh): no se espera. La tarjeta
        // se va al tiro y foco sigue con la siguiente; cuando el hilo está listo, la línea de estado lo dice
        if (casilla === 'claude' || casilla === 'empezar' || casilla === 'bloque') {
            const texto = casilla === 'bloque'
                ? `/tarea ${id} — bloquear tiempo: busca en mi calendario un hueco de 2 a 3 horas en los próximos días hábiles `
                  + 'para trabajarla, y crea el bloque solo en mi calendario, sin invitar a nadie. Dime cuándo quedó.'
                : `/tarea ${id}`;
            this.hechas.add(id);
            this.elegida = '';
            this.pintar();
            ui.estado(`${id}: abriendo su hilo con Claude…`, 15000);
            // la fila que ya tiene foco: telar no la vuelve a buscar
            const fila = this.t.dia() ? pendientes(this.t.dia()!).find(p => (p.fila.id || p.ref) === id)?.fila : undefined;
            void llevarPendiente(ref, false, proveedor, texto, true, { ir: false, fila }).then(hilo => {
                if (hilo) ui.estado(`${id} → «${hilo}»: Claude la está trabajando (está en la barra de hilos)`, 8000);
                else { this.hechas.delete(id); this.pintar(); }  // no se pudo: la tarjeta vuelve
            });
            return;
        }
        this.haciendo = { hecha: 'marcándola hecha…', hoy: 'moviéndola a hoy…', manana: 'moviéndola a mañana…', fecha: 'cambiando la fecha…',
            asignar: 'asignándola…', descartar: 'descartándola…', paso: 'creando el primer paso…', rapida: 'dándole tamaño…',
            larga: 'dándole tamaño…' }[casilla] ?? 'un momento…';
        this.pintar();
        try {
            await this.hacer(casilla, valor, proveedor, id, ref);
        } finally {
            this.haciendo = '';
            this.pintar();
        }
    }

    private async hacer(casilla: string, valor: string, proveedor: string, id: string, ref: string): Promise<void> {
        if (casilla === 'larga' || casilla === 'rapida') { await this.ponerTamano(valor, casilla); return; }
        let hecho = false;
        if (casilla === 'hoy' || casilla === 'manana') {
            const d = new Date(); if (casilla === 'manana') d.setDate(d.getDate() + 1);
            const fecha = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
            const r = await cli.accionPorRol(id, proveedor, 'fecha', fecha);
            if (r.datos) { ui.estado(`${id} → ${casilla === 'hoy' ? 'hoy' : 'mañana'}`, 4000); hecho = true; } else void ui.aviso(`telar: ${r.error ?? `no pude mover ${id}`}`);
        } else if (casilla === 'hecha') hecho = await marcarHecha(valor);
        else if (casilla === 'fecha') {
            const fecha = await elegirFecha(id, { conHoy: true });
            if (fecha) {
                const r = await cli.accionPorRol(id, proveedor, 'fecha', fecha);
                if (r.datos) { ui.estado(`${id} → ${fecha}`, 4000); hecho = true; } else void ui.aviso(`telar: ${r.error ?? `no pude mover ${id}`}`);
            }
        } else if (casilla === 'asignar') hecho = await asignar(JSON.stringify([proveedor, id, ref]), '', yo.persona);
        else if (casilla === 'paso') {
            const paso = await ui.campo({ titulo: `El primer paso · ${id}`, ayuda: 'algo que la empiece y tome media hora o menos («pedir los datos», «escribir el índice»)' });
            if (!paso?.trim()) return;
            const fila = this.t.dia() ? pendientes(this.t.dia()!).find(p => (p.fila.id || p.ref) === id) : undefined;
            const r = await cli.crearTarea({ titulo: paso.trim(), tamano: 'rapida', vence: hoyISO(), desde: `el primer paso de ${id}`,
                ...(fila?.fila.proyecto ? { proyecto: fila.fila.proyecto } : {}), ...(fila?.fila.area ? { area: fila.fila.area } : {}) });
            if (!r.datos) { void ui.aviso(`telar: ${r.error ?? 'no pude crear el paso'}`); return; }
            ui.estado(`${r.datos.id}: el primer paso de ${id}, en gestión para hoy`, 5000);
            // la larga se queda: esperando su bloque, ya empezada
            olvidarDia();
            void this.t.actualizar(true).then(() => this.pintar());
            return;
        } else if (casilla === 'descartar') {
            const r = await cli.accionPorRol(id, proveedor, 'descartar');
            if (r.datos) { ui.estado(`${id} descartada`, 4000); hecho = true; } else void ui.aviso(`telar: ${r.error ?? `no pude descartar ${id}`}`);
        }
        if (!hecho) return;
        this.hechas.add(id);
        this.elegida = '';
        olvidarDia();
        this.pintar();
        void this.t.actualizar(true).then(() => this.pintar());
    }
}
