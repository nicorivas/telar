// Los bloques del día (`[bloques.<clave>]`): lo que imprime el comando de cada uno (`telar bloque`), en su pestaña
// (el correo de hoy) o como subpestaña de una fija (`dentro`, el Gantt). Un ítem se abre a la derecha de la
// lista, con su cuerpo y las tareas que nacieron de él: la lista sigue a la vista y otro clic cambia el que se lee
// (en una pantalla angosta, solo, en vez de la lista).

import { barraBuscar } from '../../componentes/buscador';
import * as ui from '../../web/ui';
import * as avisos from '../../web/avisos';
import * as cli from '../../cli';
import { esc } from '../../estilo';
import { cuerpo, pendientes } from './dia';
import { mdSimple } from './pagina';
import { type Accion, type EnBarra, type Pantalla, type Tablero, abrirEnlace, pestanaDeSeccion } from './pantalla';
import type { AccionDePantalla } from '../../componentes/pantalla';
import { I } from '../../web/iconos';

const alternar = (s: Set<string>, k: string) => { if (s.has(k)) s.delete(k); else s.add(k); };

export class PantallaBloques implements Pantalla {
    readonly pantallas = ['bloque'] as const;
    readonly conReloj = ['bloque'] as const;
    /** los bloques declarados (`telar config`, los pone el núcleo), y lo último que mostró cada uno */
    declarados: cli.JsonBloque[] = [];
    private readonly leidos = new Map<string, { pagina?: cli.JsonPagina; error: string; hora: number }>();
    /** el bloque (`[bloques.x]`) que muestra la pestaña 'bloque' */
    private sel = '';
    /** el detalle de los ítems abiertos (el cuerpo de un correo), por «<bloque>:<id>»; y cuáles se ven enteros */
    private readonly cuerpos = new Map<string, { texto?: string; error?: string }>();
    private readonly cuerposAbiertos = new Set<string>();
    /** los bloques donde se ven solo los ítems con alguna tarea pendiente */
    private readonly soloPendientes = new Set<string>();
    /** las conversaciones desplegadas en los bloques («correo:<grupo>») */
    private readonly gruposAbiertos = new Set<string>();
    /** el ítem del bloque que se está mirando (un correo y sus tareas), si alguno */
    private item?: number;
    /** el bloque y la hora de lo leído que la pestaña pintó la última vez (ver `pintar`) */
    private pintado = '';
    /** el aviso de cada bloque que lo da (`aviso` de su página), y el que manda su lienzo mientras se ve (`ponerAviso`) */
    private readonly avisos = new Map<string, string>();

    readonly acciones: Record<string, Accion> = {
        'bloque': v => v && this.abrir(v),
        'ver-item': v => {
            if (!v) return;
            const corte = v.lastIndexOf(':');
            return this.abrir(v.slice(0, corte), Number(v.slice(corte + 1)));
        },
        'item-volver': () => this.abrir(this.sel),
        'abrir-item': v => v && this.abrirItem(v),
        'item-enlace': async v => {
            if (!v) return;
            const corte = v.lastIndexOf(':');
            const x = (this.leidos.get(v.slice(0, corte))?.pagina?.bloques ?? []).flatMap(y => y.items ?? [])[Number(v.slice(corte + 1))];
            if (x?.enlace) await abrirEnlace(x.enlace);
        },
        // los interruptores repintan lo que se ve
        'solo-pendientes': v => { if (v) { alternar(this.soloPendientes, v); this.t.render(); } },
        'cuerpo-alternar': v => { if (v) { alternar(this.cuerposAbiertos, v); this.t.render(); } },
        'grupo-item': v => { if (v) { alternar(this.gruposAbiertos, v); this.t.render(); } },
    };

    constructor(private readonly t: Tablero) {}

    /** El bloque y el ítem que se ven («<clave>:<ítem>»): la ficha de una tarea vuelve ahí. */
    abierto(): string { return `${this.sel}:${this.item ?? ''}`; }

    /** La fila de la barra que se marca: la del bloque, o la de la pestaña fija si es una subpestaña suya. */
    pestanaMarcada(): string { const d = this.dentroDelAbierto(); return d ? pestanaDeSeccion(d) : `bloque:${this.sel}`; }

    /** La pestaña fija de la que el bloque que se ve es subpestaña (`dentro`), o "". */
    dentroDelAbierto(): string { return this.declarados.find(b => b.clave === this.sel)?.dentro ?? ''; }

    /** Un bloque (`[bloques.x]`) en su pestaña: lo que imprime su comando, con sus atajos. */
    pintar(): void {
        this.t.teclas.clear();
        const b = this.declarados.find(x => x.clave === this.sel);
        const leido = b ? this.leidos.get(b.clave) : undefined;
        const item = this.item !== undefined ? (leido?.pagina?.bloques ?? []).flatMap(x => x.items ?? [])[this.item] : undefined;
        if (b && item) {
            this.pintado = '';
            if (document.body.classList.contains('angosto')) { this.t.pintar(this.htmlItem(b, item, this.item!), this.barraDe(b)); return; }
            // ⎋ lo cierra y deja la lista sola (dashboard/vista.ts)
            this.t.pintar(['<div class="dividido"><div class="lista">', ...this.html(b, this.item),
                '</div><aside class="detalle">', ...this.htmlItem(b, item, this.item!, true), '</aside></div>'], this.barraDe(b));
            return;
        }
        // un bloque con lienzo no se repinta si no cambió: el refresco de cada minuto rehace el
        // iframe (el gráfico parpadea y pierde el mouse). Sin lienzo, sí, para que el reloj avance
        const firma = `${this.sel}:${leido?.hora ?? 0}`;
        if (leido?.pagina?.bloques.some(x => x.lienzo) && firma === this.pintado) return;
        this.pintado = firma;
        this.t.pintar(b ? this.html(b) : ['<div class="vacio">ese bloque ya no está en la configuración</div>'], b ? this.barraDe(b) : {});
    }

    /** El aviso de un bloque («3 chats sin leer»): un punto en su fila del dashboard; "" si no hay. */
    aviso(clave: string): string { return this.avisos.get(clave) ?? ''; }

    /** El aviso que manda el lienzo de un bloque mientras se ve (`window.lienzo.aviso`). true si cambió. */
    ponerAviso(clave: string, texto: string): boolean {
        if (!this.declarados.some(b => b.clave === clave) || this.aviso(clave) === texto) return false;
        this.avisos.set(clave, texto);
        return true;
    }

    /** De fondo: los bloques que dan aviso (su página trae el campo), releídos si tienen más de 2 minutos. El que se
     *  ve no: su lienzo lo tiene al día, y releerlo lo redibujaría. true si cambió algún aviso. */
    async leerAvisos(): Promise<boolean> {
        const ahora = Date.now();
        const viendo = this.t.pantalla === 'bloque' ? this.sel : '';
        const cuales = this.declarados.filter(b => {
            const l = this.leidos.get(b.clave);
            return l?.pagina?.aviso !== undefined && b.clave !== viendo && ahora - l.hora > 2 * 60 * 1000;
        });
        let cambio = false;
        await Promise.all(cuales.map(async b => {
            const r = await cli.bloque(b.clave);
            if (!r.datos) return;
            await this.t.paginas.precargar(r.datos.bloques);
            this.leidos.set(b.clave, { pagina: r.datos, error: '', hora: Date.now() });
            if (this.aviso(b.clave) !== (r.datos.aviso ?? '')) { this.avisos.set(b.clave, r.datos.aviso ?? ''); cambio = true; }
        }));
        return cambio;
    }

    /** Abre la pestaña de un bloque y lo relee si tiene más de 5 minutos. */
    async abrir(clave: string, item?: number): Promise<void> {
        this.t.ir('bloque');
        this.pintado = '';
        this.item = item;
        // un ítem abierto con `id`: su detalle (el cuerpo de un correo) se pide ahora, una vez
        const x = item === undefined ? undefined : (this.leidos.get(clave)?.pagina?.bloques ?? []).flatMap(b => b.items ?? [])[item];
        if (x?.id && !this.cuerpos.has(`${clave}:${x.id}`)) {
            const llave = `${clave}:${x.id}`;
            this.cuerpos.set(llave, {});
            void cli.bloqueItem(clave, x.id).then(r => {
                this.cuerpos.set(llave, r.datos ? { texto: r.datos.texto } : { error: r.error ?? 'no pude leerlo' });
                if (this.t.pantalla === 'bloque' && this.sel === clave && this.item === item) this.pintar();
            });
        }
        this.sel = clave;
        this.pintar();
        await this.leer();
    }

    /** Lo que un bloque pone en la barra de su pestaña (componentes/pantalla.ts): su nombre y su tinta, lo que resume (su
     *  subtítulo) y sus acciones, íconos: los atajos que van en él, el filtro «solo con tareas pendientes» y su ⚙. */
    barraDe(b: cli.JsonBloque): EnBarra {
        const leido = this.leidos.get(b.clave);
        const conTareas = (leido?.pagina?.bloques ?? []).flatMap(x => x.items ?? []).some(x => Array.isArray(x.tareas));
        const solo = this.soloPendientes.has(b.clave);
        const acciones: AccionDePantalla[] = [...this.t.atajosEnBarra(b.clave)];
        if (conTareas) acciones.push({ accion: 'solo-pendientes', valor: b.clave, icono: I.filtro, si: solo, tono: 'amarillo',
            ayuda: solo ? 'se ven solo los que tienen alguna tarea pendiente: clic, todos' : 'mostrar solo los que tienen alguna tarea pendiente' });
        // el ⚙ de un bloque que es la pestaña de un módulo con pantalla de configuración: a ella (⚙ módulos)
        if (this.t.config()?.modulos?.some(m => m.nombre === b.clave && m.configurar))
            acciones.push({ accion: 'config', valor: `modulos:${b.clave}`, icono: I.config, ayuda: `configurar ${b.nombre}` });
        return { nombre: b.nombre, color: b.color, resumen: leido?.pagina?.subtitulo ?? '', acciones };
    }

    /** Un bloque en su pestaña: su cabecera va en la barra (barraDe), y aquí sus filas. */
    html(b: cli.JsonBloque, marcado?: number): string[] {
        const h: string[] = [];
        const leido = this.leidos.get(b.clave);
        const itemsB = (leido?.pagina?.bloques ?? []).flatMap(x => x.items ?? []);
        const solo = this.soloPendientes.has(b.clave);
        h.push(cuerpo(b.color));
        // con muchas filas (la bandeja), la barra de un buscador: filtra lo que se ve sin repintar (dashboard/vista.ts)
        if (itemsB.length >= 8) {
            h.push(barraBuscar({ clase: 'buscar-c', datos: { bloque: b.clave }, atajo: '/', placeholder: b.nombre.toLowerCase(),
                ayuda: 'buscar por nombre, dirección de correo, asunto o código de tarea · ⎋ borra', cuenta: { clase: 'buscar-c-cuenta' },
                claseBarra: 'buscar-c-caja' }));
        }
        if (!leido) h.push('<div class="vacio">leyendo…</div>');
        // lo que falló lo dice la franja de avisos (`avisar`): aquí, solo que no hay qué mostrar
        else if (leido.error) h.push('<div class="vacio">sin leer</div>');
        else {
            // un bloque puede traer, además de filas, un lienzo (un gráfico) y texto, como una página
            for (const x of leido.pagina?.bloques ?? []) {
                if (x.lienzo) h.push(this.t.paginas.lienzo(x.lienzo, `bloque:${b.clave}`));
                if (x.texto) h.push(`<div class="md-pag">${mdSimple(x.texto)}</div>`);
            }
            const items = (leido.pagina?.bloques ?? []).flatMap(x => x.items ?? []);
            const otros = (leido.pagina?.bloques ?? []).some(x => x.lienzo || x.texto);
            if (!items.length && !otros) h.push('<div class="vacio">nada</div>');
            // si el bloque dice las tareas de sus ítems (un correo), van en una columna propia, a la derecha
            const conTareas = items.some(x => Array.isArray(x.tareas));
            // ¿sigue pendiente? Lo dice la lista de tareas de ahora (el estado que trae el ítem
            // puede ser de antes); sin ella todavía, el estado del ítem
            const d = this.t.dia();
            const vivas = d ? new Set(pendientes(d).filter(q => !this.t.tareas.decididas.has(q.fila.id || q.ref))
                .map(q => `${q.fila.proveedor}:${q.fila.id || q.ref}`)) : undefined;
            const pendiente = (t: { proveedor: string; id: string; estado?: string }) =>
                vivas ? vivas.has(`${t.proveedor}:${t.id}`) : !/^(hecha|cerrada|descartada|cancelada)$/.test(t.estado ?? '');
            // un ítem es una fila; un clic lo muestra con sus tareas (procesarlo en un hilo es un botón de ahí)
            type Extra = { hijo?: boolean; cuantos?: number; abierta?: boolean; llave?: string; ts?: NonNullable<cli.JsonPaginaItem['tareas']>; nuevo?: boolean; marca?: string; busca?: string };
            // lo que encuentra el buscador en una fila: de quién, el asunto, su `busca` (las direcciones y los
            // nombres de un correo) y sus tareas (en una conversación plegada, los de todos sus correos)
            const textoDe = (y: cli.JsonPaginaItem) => `${y.texto ?? ''} ${y.titulo} ${y.busca ?? ''} ${(y.tareas ?? []).map(t => t.id).join(' ')}`;
            const fila = (x: cli.JsonPaginaItem, i: number, e: Extra = {}) => {
                const clic = x.mensaje || x.tareas?.length ? ` data-accion="ver-item" data-valor="${esc(b.clave)}:${i}"` : '';
                const ts = e.ts ?? x.tareas ?? [];
                // las cerradas, apagadas: de un vistazo, si al correo le queda algo por hacer
                const tareas = !conTareas ? '' : `<span class="tar" title="${esc(ts.map(t => `${t.id} ${pendiente(t) ? (t.estado || 'pendiente') : 'cerrada'}`).join('\n') || 'sin tareas')}">`
                    + (ts.length ? ts.map(t => `<span class="${pendiente(t) ? 'abierta' : 'cerrada'}">${esc(t.id)}</span>`).join(', ') : '—') + '</span>';
                // una conversación: ▸ con cuántos son, que la despliega
                const plegar = e.cuantos ? `<span class="plegar" data-accion="grupo-item" data-valor="${esc(e.llave!)}" title="${e.abierta ? 'plegar' : `ver los ${e.cuantos} de esta conversación`}">${e.abierta ? I.abierto : I.plegado}${e.cuantos}</span> ` : '';
                const nuevo = e.nuevo ?? x.destacado;
                const sel = i === marcado && b.clave === this.sel;
                const busca = (e.busca ?? textoDe(x)).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
                return `<div data-texto="${esc(busca)}" class="cr${conTareas ? ' con-t' : ''}${e.hijo ? ' hijo' : ''}${nuevo ? ' nuevo' : ''}${clic ? ' clic' : ''}${sel ? ' sel' : ''}"${clic}`
                    + ` title="${esc(clic ? `clic: ${x.tareas?.length ? 'sus tareas' : 'verlo'}${x.mensaje ? ', y procesarlo en un hilo' : ''}` : x.titulo)}"><span class="mk">${esc(e.marca ?? x.marca ?? '·')}</span>`
                    + `<span class="hora" title="${esc((x.fecha ?? '').replace('T', ' '))}">${esc(cuandoCorto(x.fecha ?? ''))}</span>`
                    + `<span class="de">${esc(conTareas ? (x.texto ?? '').replace(/ · tareas: .*$/, '') : x.texto ?? '')}</span><span class="que">${plegar}${esc(x.titulo)}</span>${tareas}</div>`;
            };
            // los de una misma conversación (`grupo`), anidados bajo el más reciente, como Gmail; el
            // orden es el de la lista: cada conversación va donde aparece su primer ítem
            const grupos = new Map<string, number[]>();
            items.forEach((x, i) => { const g = x.grupo || `#${i}`; if (!grupos.has(g)) grupos.set(g, []); grupos.get(g)!.push(i); });
            let mostrados = 0;
            for (const [g, idx] of grupos) {
                const x = items[idx[0]];
                if (solo && !idx.some(k => (items[k].tareas ?? []).some(pendiente))) continue;
                mostrados++;
                if (idx.length === 1) { h.push(fila(x, idx[0])); continue; }
                const llave = `${b.clave}:${g}`;
                const abierta = this.gruposAbiertos.has(llave);
                const todos = idx.map(k => items[k]);
                const ts = [...new Map(todos.flatMap(y => y.tareas ?? []).map(t => [t.id, t])).values()];
                // la conversación está sin procesar si alguno de sus correos lo está
                const nuevo = todos.some(y => y.destacado);
                h.push(fila(x, idx[0], { cuantos: idx.length, abierta, llave, ts, nuevo, busca: todos.map(textoDe).join(' '), marca: nuevo ? (todos.find(y => y.destacado)?.marca ?? x.marca) : x.marca }));
                if (abierta) idx.slice(1).forEach(k => h.push(fila(items[k], k, { hijo: true })));
            }
            if (solo && items.length && !mostrados) h.push('<div class="vacio">ningún correo con tareas pendientes</div>');
        }
        h.push('</section>');
        return h;
    }

    /** Pide lo que muestra cada bloque. Sin `forzar`, solo los que tienen más de 5 minutos. */
    async leer(forzar = false): Promise<void> {
        const ahora = Date.now();
        await Promise.all(this.declarados.map(async b => {
            const antes = this.leidos.get(b.clave);
            if (!forzar && antes && ahora - antes.hora < 5 * 60 * 1000) return;
            // una subpestaña (el Gantt) no se ve de paso: se pide cuando se abre
            if (b.dentro && !(this.t.pantalla === 'bloque' && this.sel === b.clave)) return;
            const r = await cli.bloque(b.clave);
            await this.t.paginas.precargar(r.datos?.bloques);
            this.leidos.set(b.clave, { pagina: r.datos, error: r.datos ? '' : (r.error ?? 'no contestó'), hora: Date.now() });
            this.avisar(b, r);
            if (r.datos?.aviso !== undefined) this.avisos.set(b.clave, r.datos.aviso);
            if (this.t.pantalla === 'bloque') this.t.render();
        }));
    }

    /** Un bloque que no se pudo leer, en la franja de avisos (web/avisos.ts): una fuente que falla. Sin respuesta de telar
     *  no se dice (lo dice el de la conexión); al leerse bien, se va. Antes, en su lugar, en rojo. */
    private avisar(b: cli.JsonBloque, r: cli.Respuesta<unknown>): void {
        const clave = `fuente:bloque:${b.clave}`;
        if (r.datos) { avisos.quitar(clave); return; }
        if (!r.estado) return;
        avisos.poner({ clave, nivel: 'falla', icono: I.alerta, conConexion: true, texto: `no se pudo leer ${b.nombre}`,
            detalle: `${b.nombre}: ${(r.error ?? 'no contestó').replace(/[.]?$/, '.')}`, hacer: 'Se vuelve a pedir solo cada cinco minutos; si sigue, revisa su módulo en ⚙ módulos.',
            ir: { texto: `la pestaña ${b.nombre}`, hacer: () => void ui.orden('telar.pestana', 'bloque', b.clave) },
            acciones: [{ id: 'releer', texto: 'leerlo de nuevo', hacer: () => void this.leer(true) }] });
    }

    /** Un ítem de un bloque, solo: lo que dice, las tareas que nacieron de él (cada una abre su
     *  ficha) y, si trae `mensaje`, el botón para procesarlo en un hilo. */
    private htmlItem(b: cli.JsonBloque, x: cli.JsonPaginaItem, i: number, alLado = false): string[] {
        // el título lleva al original (la conversación en Gmail), en su pestaña si ya está abierta
        const titulo = x.enlace ? `<a class="titulo-item" data-accion="item-enlace" data-valor="${esc(b.clave)}:${i}" title="${esc(`abrirlo: ${x.enlace}`)}"><b>${esc(x.titulo)}</b> ${I.externo}</a>` : `<b>${esc(x.titulo)}</b>`;
        // al lado de la lista, se cierra con ✕ (o ⎋); solo, se vuelve a la lista
        const volver = alLado ? `<a class="cerrar-item" data-accion="item-volver" title="cerrarlo (⎋)">${I.cerrar}</a>`
            : `<a data-accion="item-volver" title="volver a la lista">‹ ${esc(b.nombre)}</a>&nbsp; `;
        const h = [`<div class="subcab">${alLado ? '' : volver}${titulo}${alLado ? volver : ''}`
            + `<span class="dim">${esc((x.texto ?? '').replace(/ · tareas: .*$/, ''))}${x.fecha ? ` · ${esc(x.fecha.slice(0, 16).replace('T', ' '))}` : ''}</span></div>`];
        // el cuerpo: cinco líneas, y «ver todo» lo despliega
        if (x.id) {
            const llave = `${b.clave}:${x.id}`;
            const c = this.cuerpos.get(llave);
            if (!c || (!c.texto && !c.error)) h.push('<div class="fila dim">leyendo el correo…</div>');
            else if (c.error) h.push(`<div class="fila dim">sin el cuerpo: ${esc(c.error)}</div>`);
            else {
                const abierto = this.cuerposAbiertos.has(llave);
                const largo = c.texto!.split('\n').length > 5 || c.texto!.length > 600;
                h.push(`<div class="cuerpo${abierto || !largo ? '' : ' plegado'}">${esc(c.texto!)}</div>`);
                if (largo) h.push(`<div class="fila"><a data-accion="cuerpo-alternar" data-valor="${esc(llave)}">${abierto ? `${I.subir} plegar` : `${I.abierto} ver todo`}</a></div>`);
            }
        }
        h.push('<h2>Tareas<small>las que nacieron de este correo o de otro mensaje de su conversación</small></h2>');
        if (!x.tareas?.length) h.push('<div class="fila dim">ninguna</div>');
        // las pendientes, con la misma fila que «tareas» (✓ ◉ ▶ ⋯, fecha, responsable): se responde en
        // Gmail y se vuelve aquí a cerrarla. Las que ya no están pendientes, en una línea, a su ficha
        const d = this.t.dia();
        const vivas = (d ? pendientes(d) : []).filter(q => !this.t.tareas.decididas.has(q.fila.id || q.ref));
        h.push('<div class="tareas-sueltas">');
        for (const t of x.tareas ?? []) {
            const p = vivas.find(q => q.fila.proveedor === t.proveedor && (q.fila.id === t.id || q.ref === t.id));
            if (p) { h.push(this.t.tareas.filaTarea(p, !!p.avance && !!p.fila.ficha, false)); continue; }
            const valor = esc(JSON.stringify([t.proveedor, t.id, t.id]));
            h.push(`<div class="fila clic" data-accion="tarea" data-valor="${valor}" title="clic: su ficha">`
                + `<span class="dim">${esc(t.id)}</span>&nbsp; <span class="dim">ya no está pendiente</span></div>`);
        }
        h.push('</div>');
        if (x.mensaje) {
            // por la instrucción: su mensaje ya escrito y «un hilo nuevo» elegido, y se puede cambiar antes de mandarlo
            h.push('<h2>Procesar</h2>');
            h.push(`<div class="fila"><a data-accion="abrir-item" data-valor="${esc(b.clave)}:${i}" title="${esc(`instrucción: ${x.mensaje}, a un hilo nuevo`)}">`
                + `<span style="color: var(--violeta)">${I.instruccion}</span> procesarlo en un hilo</a>`
                + `&nbsp;<span class="dim">la instrucción con <code>${esc(x.mensaje)}</code>, a un hilo nuevo</span></div>`);
        }
        return h;
    }

    /** Un clic en «procesarlo en un hilo» de un ítem que trae `mensaje`: la ventana de la instrucción (web/instruccion.ts)
     *  con su mensaje escrito y «un hilo nuevo» elegido, que se llama como el ítem. Si se abrió un hilo, se va a él. */
    private async abrirItem(valor: string): Promise<void> {
        const corte = valor.lastIndexOf(':');
        const clave = valor.slice(0, corte);
        const x = (this.leidos.get(clave)?.pagina?.bloques ?? []).flatMap(b => b.items ?? [])[Number(valor.slice(corte + 1))];
        if (!x?.mensaje) return;
        const { abrir, NUEVO } = await import('../../web/instruccion');
        const r = await abrir({ texto: x.mensaje, a: NUEVO, nombre: x.nombre || x.titulo });
        if (r?.como === 'abierto') await ui.mostrarTerminal();
    }
}

/** La hora de un ítem si es de hoy; si no, el día («21 sep»): en la bandeja hay correos de semanas atrás. */
function cuandoCorto(fecha: string): string {
    const hoy = new Date();
    const dia = `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, '0')}-${String(hoy.getDate()).padStart(2, '0')}`;
    if (!fecha || fecha.slice(0, 10) === dia) return fecha.slice(11, 16);
    const [, m, d] = fecha.slice(0, 10).split('-').map(Number);
    return `${d} ${['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'][(m || 1) - 1]}`;
}
