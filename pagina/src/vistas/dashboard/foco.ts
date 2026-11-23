// «foco»: lo más urgente e importante, de a pocas tarjetas, para decidir una por una. Un clic en una tarjeta la elige
// (la primera viene elegida) y arriba de las tarjetas, en una banda de íconos (componentes/casillas.ts), están sus
// acciones, las que le corresponden a esa tarea: junto a «nueva fecha», hoy si venció y los aplazamientos de siempre;
// junto al tamaño, «rápida» o «larga»; junto a la instrucción, «trabajarla» (a su hilo, a trabajarla ahí) y, en
// concentración, «bloquear tiempo». También se puede
// arrastrar la tarjeta a una acción. La tarjeta se va y entra la siguiente, ya elegida. Una tarea vencida va primero y no
// se queda vencida: o se le da una fecha real (hoy, mañana…), o se suelta.
//
// Dos modos, porque no se trabajan igual: **gestión** (lo rápido, media hora o menos: hasta cinco, para despachar
// en una sesión) y **concentración** (lo largo, horas o días: dos a lo más, cada una necesita un bloque propio). Una
// tarea sin tamaño va en gestión, y sus acciones traen «es rápida» y «es larga».
//
// Solo lo que es de la persona (sin dueño, o ella) y tiene ficha (una tarea, no la casilla de un documento). El orden:
// las vencidas, las de hoy, y después la urgencia de «tareas» (la prioridad manda; la fecha desempata). La deuda (lo
// vencido hace más de 30 días) no va con las vencidas: va donde la pone la urgencia.

import * as cli from '../../cli';
import { esc } from '../../estilo';
import { C, I } from '../../web/iconos';
import { casillas, type Casilla, type Rapida } from '../../componentes/casillas';
import { circulo } from '../../componentes/circulo';
import type { Pieza } from '../../componentes/item';
import { tarjeta } from '../../componentes/tarjeta';
import * as ui from '../../web/ui';
import { modelo } from '../../modelo';
import { esDeuda, esMia, olvidarDia, pendientes, salio, yo } from './dia';
import { fechasDeSiempre, iso, piezasTarea } from './fila-tarea';
import { type Accion, type Pantalla, type Tablero } from './pantalla';
import { asignar, llevarPendiente, marcarHecha, reagendar } from './tareas';
import { nombreCorto } from './unidad';

type Modo = 'gestion' | 'concentracion';
type Fila = ReturnType<typeof pendientes>[number];

/** cuántas tarjetas a la vista en cada modo: las demás esperan su turno */
const TOPE: Record<Modo, number> = { gestion: 5, concentracion: 2 };

/** Las acciones de foco (componentes/casillas.ts): un ícono en el color de lo que hace (web/iconos.ts, C), su nombre en
 *  el globo. Van en grupos, en el mismo orden en los dos modos (la mano aprende dónde está cada una): ver · hecha · la
 *  fecha y el tamaño · pasarla · el primer paso y unirla · descartar. Las de cada tarea, en `gruposDe`. */
const VER: Casilla = { valor: 'ver', nombre: 'ver el detalle', icono: I.documento, color: C.ir,
    ayuda: 'su ficha entera: el contexto, la historia y todas sus acciones («‹ foco» vuelve aquí)' };
const HECHA: Casilla = { valor: 'hecha', nombre: 'hecha', icono: I.hecha, color: C.hecho, ayuda: 'ya está: se marca hecha' };
const ASIGNAR: Casilla = { valor: 'asignar', nombre: 'de otra persona', icono: I.persona, color: C.cambiar, ayuda: 'asignarla: sale de tu foco' };
const PASO: Casilla = { valor: 'paso', nombre: 'sacar el primer paso', icono: I.nuevo, color: C.hecho,
    ayuda: 'una tarea rápida que la empieza: va a gestión; esta espera su bloque' };
const UNIR: Casilla = { valor: 'unir', nombre: 'es la misma que…', icono: I.unir, color: C.otro,
    ayuda: 'otra tarea dice lo mismo: esta se le une (su texto pasa a esa) y se descarta' };
const DESCARTAR: Casilla = { valor: 'descartar', nombre: 'descartar', icono: I.descartar, color: C.quitar, ayuda: 'no se va a hacer: sale de la lista' };
const RAPIDA: Rapida = { valor: 'rapida', texto: 'rápida', nombre: 'es rápida', ayuda: 'media hora o menos: va en gestión' };
const LARGA: Rapida = { valor: 'larga', texto: 'larga', nombre: 'es larga', ayuda: 'horas o días: pasa a concentración' };
/** trabajarla: «trabajar en un hilo», lo mismo que en su ficha: a su hilo (el de su proyecto; sin proyecto, el agente
 *  que las toma), con «Veamos T84» escrito sin mandar, y se va a él: ahí sigue la persona */
const TRABAJAR: Rapida = { valor: 'trabajar', texto: 'trabajarla', nombre: 'trabajar en un hilo',
    ayuda: 'a su hilo, con «Veamos …» escrito: te lleva a él para trabajarla ahí (lo mismo que «trabajar en un hilo» en su ficha)' };
/** bloquear tiempo: una instrucción hecha (`telar actuar`, a su hilo, con /tarea y este pedido), de un clic */
const BLOQUEAR: Rapida = { valor: 'bloque', texto: 'bloquear tiempo', nombre: 'bloquear tiempo',
    ayuda: 'una instrucción hecha, a su hilo: /tarea con «busca un hueco de 2 a 3 horas en mi calendario y crea el bloque»' };
const PIDE_BLOQUE = 'bloquear tiempo: busca en mi calendario un hueco de 2 a 3 horas en los próximos días hábiles para trabajarla, '
    + 'y crea el bloque solo en mi calendario, sin invitar a nadie. Dime cuándo quedó.';

const DIAS = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'];

/** Los aplazamientos a un clic, junto a «nueva fecha»: un día (desde su fecha si es futura; si no, desde hoy), el
 *  viernes de esta semana (el de la próxima si ya es viernes o fin de semana) y el lunes de la próxima.
 *  [para qué, lo que se ve, AAAA-MM-DD] */
function aplazamientos(cuando: string): [string, string, string][] {
    const hoy = new Date(); hoy.setHours(0, 0, 0, 0);
    const fecha = cuando ? new Date(`${cuando.slice(0, 10)}T00:00:00`) : null;
    const base = fecha && fecha > hoy ? fecha : hoy;
    const unDia = new Date(base); unDia.setDate(unDia.getDate() + 1);
    const viernes = new Date(hoy); viernes.setDate(hoy.getDate() + ((5 - hoy.getDay() + 7) % 7 || 7));
    const lunes = new Date(hoy); lunes.setDate(hoy.getDate() + ((8 - hoy.getDay()) % 7 || 7));
    const corto = (d: Date) => `${DIAS[d.getDay()]} ${d.getDate()}`;
    return [['un día más', `+1 · ${corto(unDia)}`, iso(unDia)], ['el viernes', corto(viernes), iso(viernes)],
        ['el lunes', corto(lunes), iso(lunes)]];
}

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
        // la deuda (vencida hace más de 30 días, dia.ts) no va primero: en su lugar por la urgencia de siempre
        const peso = (p: Fila) => (esDeuda(p.dias) ? 2 : p.dias !== null && p.dias < 0 ? 0 : p.dias === 0 ? 1 : 2);
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
        const modos: [Modo, string, string, string][] = [
            ['gestion', I.hecha, 'gestión', 'lo rápido (media hora o menos): despachar varias en una sesión'],
            ['concentracion', I.consolidar, 'concentración', 'lo largo (horas o días): una o dos, cada una con su bloque'],
        ];
        const h: string[] = ['<div id="foco">'];
        h.push('<div class="foco-cab">' + modos.map(([m, ic, nombre, ayuda]) => {
            const n = m === this.modo ? cola.length : this.cola(m).length;
            return `<a class="modo${m === this.modo ? ' si' : ''}" data-accion="foco-modo" data-valor="${m}" title="${esc(ayuda)}"><span class="i">${ic}</span> ${nombre} <span class="n">${n}</span></a>`;
        }).join('')
            + '</div>');
        // la banda de sus acciones, arriba de las tarjetas: las de la elegida (mientras una va a telar, lo dice)
        h.push(`<div class="foco-cuerpo ${this.modo}">`);
        if (elegida) h.push(casillas({ grupos: this.gruposDe(elegida), accion: 'foco-soltar', ocupadas: !!this.haciendo,
            haciendo: this.haciendo ? `${circulo({ mov: 'gira' })} ${esc(this.haciendo)}` : '' }));
        h.push('<div class="tarjetas lista-tarjetas">');
        if (!vista.length) {
            const quedan = this.cola(otro).length;
            h.push(`<div class="vacio"><span class="i">${I.hecha}</span> ${this.modo === 'gestion' ? 'nada rápido pendiente' : 'nada largo pendiente'}.`
                + (quedan ? ` <a data-accion="foco-modo" data-valor="${otro}">${quedan} en ${otro === 'gestion' ? 'gestión' : 'concentración'}</a>` : ' Respira.') + '</div>');
        }
        for (const p of vista) h.push(this.tarjeta(p));
        if (cola.length > vista.length) h.push(`<div class="dim">${cola.length - vista.length} más esperan su turno</div>`);
        h.push('</div></div></div>');
        // su ↻ relee las tareas y lo dice mientras (el del núcleo releería el día entero, sin decir nada)
        this.t.pintar(h, { sinReleer: true, acciones: [{ accion: 'foco-releer', icono: I.releer,
            ayuda: 'volver a leer las tareas ahora (se releen solas cada minuto y cuando algo cambia)' }] });
    }

    /** Las acciones de una tarea, en sus grupos: las mismas en los dos modos, más lo que pide su situación. Junto a
     *  «nueva fecha», «hoy» si venció (o va hoy, o tiene fecha de verdad) y los aplazamientos; junto al tamaño, el que no
     *  tiene (las dos, si no tiene ninguno); junto a la instrucción, trabajarla y, en concentración, bloquear tiempo; y en
     *  concentración, sacar el primer paso. */
    private gruposDe(p: Fila): Casilla[][] {
        const concentracion = this.modo === 'concentracion';
        const tamano = this.tamanoDe(p);
        const fecha: Casilla = { valor: 'fecha', nombre: 'nueva fecha', icono: I.fecha, color: C.cambiar,
            ayuda: 'hoy, mañana, el lunes…: cuándo de verdad (los de siempre, al lado)',
            rapidas: [
                ...(p.dias !== null && p.dias < 0 ? [{ valor: 'hoy', texto: 'hoy', nombre: 'va hoy', ayuda: 'la haces hoy: su fecha pasa a hoy' }] : []),
                ...aplazamientos(p.cuando).map(([nombre, texto, f]) => ({ valor: `aplazar:${f}`, texto, nombre, ayuda: f })),
            ] };
        const tamanos: Casilla = { valor: 'tamano', nombre: 'tamaño', icono: I.tamano, color: C.cambiar, padre: true,
            ayuda: 'cuánto toma: rápida, media hora o menos (gestión); larga, horas o días (concentración)',
            rapidas: !tamano ? [RAPIDA, LARGA] : tamano === 'larga' ? [RAPIDA] : [LARGA] };
        // mandársela a un hilo (el suyo, uno nuevo, otro) o a un agente, con una skill (de entrada /tarea) o lo escrito: la
        // ventana de siempre (web/instruccion.ts)
        const instruccion: Casilla = { valor: 'instruccion', nombre: 'instrucción', icono: I.instruccion, color: C.agente,
            ayuda: 'mandársela a su hilo, a uno nuevo, a otro o a un agente, con una skill o lo que le pidas',
            rapidas: concentracion ? [TRABAJAR, BLOQUEAR] : [TRABAJAR] };
        return [[VER], [HECHA], [fecha, tamanos], [instruccion, ASIGNAR], [...(concentracion ? [PASO] : []), UNIR], [DESCARTAR]];
    }

    private valor(p: Fila): string { return JSON.stringify([p.fila.proveedor, p.fila.id || p.ref, p.ref]); }

    /** La tarjeta de una tarea (componentes/tarjeta.ts), con las piezas de su fila en «tareas» (fila-tarea.ts): en la
     *  cabecera su prioridad y su estado, el título entero y lo de todos los días con el ⋯; en el pie su código, su
     *  proyecto (o su área), «sin tamaño» si le falta, la estrella y la fecha. Un clic la elige; se arrastra a una casilla. */
    private tarjeta(p: Fila): string {
        const valor = this.valor(p);
        const proy = this.t.proyectos.deFila(p.fila);
        const donde = proy ? nombreCorto(proy) : (p.fila.area ?? '');
        const x = piezasTarea(p);
        const datos: Pieza[] = [{ texto: p.fila.id || p.ref }];
        if (proy) datos.push({ html: `<span data-accion="proy-ir" data-valor="${esc(proy.ruta)}">${esc(donde)}</span>`, tono: 'acento',
            ayuda: `${proy.nombre}\nclic: verlo en proyectos` });
        else if (donde) datos.push({ texto: donde });
        // sin tamaño: lo dice, y sus acciones traen «es rápida» y «es larga»
        if (!this.tamanoDe(p)) datos.push({ texto: 'sin tamaño', tono: 'atencion', ayuda: 'sin tamaño: dile si es rápida o larga' });
        return tarjeta({
            inicio: [x.prioridad, x.estado], prefijo: x.prefijo, titulo: x.texto, acciones: x.acciones, menu: x.menu,
            datos, aviso: x.aviso, meta: x.meta,
            activa: this.elegida === valor, holgada: this.modo === 'concentracion', arrastrable: true,
            accion: 'foco-elegir', datosHtml: { valor, arrastra: valor },
            ayuda: `${p.fila.id || p.ref} · ${x.texto}\nclic: sus acciones, a la derecha (o arrástrala a una)`,
        });
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
        // ver el detalle: su ficha, la de «tareas»; «‹ foco» vuelve aquí, con la misma elegida
        if (casilla === 'ver') { await this.t.tareas.abrirTarea(valor, { nombre: 'foco', ir: () => void this.t.accion('foco') }); return; }
        // la fila que ya tiene foco: telar no la vuelve a buscar
        const fila = this.t.dia() ? pendientes(this.t.dia()!).find(p => (p.fila.id || p.ref) === id)?.fila : undefined;
        // instrucción: la ventana para elegir a quién, la skill (de entrada /tarea) y lo que se le pide. Al mandarla, la
        // tarjeta se va al tiro y foco sigue con la siguiente (abrir o retomar su hilo toma segundos); si no se pudo, vuelve
        if (casilla === 'instruccion') {
            const { abrir } = await import('../../web/instruccion');
            const r = await abrir({ direccion: fila?.direccion ?? '', fila,
                titulo: `${id} · ${fila?.texto ?? ''}`, skill: 'tarea' }, () => { this.hechas.add(id); this.elegida = ''; this.pintar(); });
            if (!r && this.hechas.delete(id)) this.pintar();
            // su historia cambió (la instrucción queda en ella): la ficha guardada en «tareas» ya no vale
            if (r) this.t.tareas.olvidarFicha(proveedor, id);
            return;
        }
        // trabajarla: a su hilo, como «trabajar en un hilo» de su ficha, y se va a él. No la decide: la tarjeta se queda
        if (casilla === 'trabajar') { await llevarPendiente(ref, false, proveedor, '', false, { fila }); return; }
        // bloquear tiempo: una instrucción hecha, sin la ventana: a su hilo (`telar actuar`), con /tarea y lo que se pide
        // escrito aquí. Queda en su historia como cualquier instrucción. La tarjeta se va al tiro; si no se pudo, vuelve
        if (casilla === 'bloque') {
            this.hechas.add(id);
            this.elegida = '';
            this.pintar();
            const r = await ui.progreso({ titulo: `telar: instrucción a su hilo · bloquear tiempo para ${id}…`, discreto: true },
                () => cli.actuar({ direccion: fila?.direccion ?? '', skill: 'tarea', nota: PIDE_BLOQUE, ...(fila ? { fila } : { fila: { ref, id, proveedor } }) }));
            if (!r.datos) {
                void ui.falla(`telar: ${r.error ?? `no pude mandarle la instrucción a su hilo (${id})`}`);
                this.hechas.delete(id);
                this.pintar();
                return;
            }
            ui.estado(`${id} · bloquear tiempo: instrucción a «${r.datos.destino}»${r.datos.maquina ? ` en ${r.datos.maquina}` : ''}: ${r.datos.como}`, 8000);
            this.t.tareas.olvidarFicha(proveedor, id);
            void modelo.sondear();
            return;
        }
        this.haciendo = casilla.startsWith('aplazar:') ? `moviéndola al ${casilla.slice(8)}…` : { unir: 'uniéndola…', hecha: 'marcándola hecha…', hoy: 'moviéndola a hoy…', manana: 'moviéndola a mañana…', fecha: 'cambiando la fecha…',
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
        // la fecha: la de siempre (tareas.ts, reagendar), con la de su casilla o la que se elija
        if (casilla.startsWith('aplazar:')) hecho = !!await reagendar(valor, { fecha: casilla.slice(8) });
        else if (casilla === 'hoy' || casilla === 'manana') {
            const f = fechasDeSiempre();
            hecho = !!await reagendar(valor, { fecha: iso(casilla === 'hoy' ? f.hoy : f.manana) });
        } else if (casilla === 'hecha') hecho = await marcarHecha(valor);
        else if (casilla === 'fecha') hecho = !!await reagendar(valor, { titulo: '', conHoy: true });
        else if (casilla === 'asignar') hecho = await asignar(JSON.stringify([proveedor, id, ref]), '', yo.persona);
        else if (casilla === 'unir') {
            // con cuál: las tareas de la persona que ya tiene foco (las de los dos modos), menos esta
            const d = this.t.dia();
            const otras = d ? pendientes(d).filter(x => x.fila.ficha && esMia(x.fila.dueno ?? '') && (x.fila.id || x.ref) !== id) : [];
            const con = await ui.elegir(otras.map(x => ({ label: `${x.fila.id || x.ref} ${x.texto}`, valor: x.fila.id || x.ref })),
                { titulo: `${id} es la misma que…`, placeholder: 'la que queda' });
            if (!con) return;
            const r = await cli.accionObjeto(`tarea:${id}`, 'unir', { con: con.valor });
            if (r.datos) { ui.estado(`${id} se unió a ${con.valor}`, 5000); hecho = true; } else void ui.aviso(`telar: ${r.error ?? `no pude unir ${id}`}`);
        } else if (casilla === 'paso') {
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
        // descartada o unida a otra, sale de lo pendiente en todas las vistas (hecha, ya lo dijo marcarHecha)
        if (casilla === 'descartar' || casilla === 'unir') salio(proveedor, id); else olvidarDia();
        this.pintar();
        void this.t.actualizar(true).then(() => this.pintar());
    }
}
