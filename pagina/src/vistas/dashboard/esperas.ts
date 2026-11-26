// «te esperan»: lo que espera una decisión de la persona, junto (`telar esperas`, GET /esperas; la propuesta, en
// docs/propuestas/lo-que-espera-a-la-persona.md). Es una pestaña del dashboard, y su fila en la barra (DASHBOARD) lleva
// el número de lo que pregunta: los hilos que esperan ahora, las decisiones que te piden (el módulo preguntas) y las
// preguntas que los agentes dejaron en las tareas.
//
//   TE ESPERAN  70 · 28 preguntan · la más vieja, hace 6 semanas                        ↻   ← la tecla t
//   buscar ___________ 70            ▽ hilos 0  preguntas 28  cerrar 3  preparado 24  retenidos 14
//   ▾ HILOS QUE ESPERAN AHORA                                   ← siempre arriba: bloquean el turno de un agente
//     ningún hilo te espera
//   ▾ DECISIONES QUE TE PIDEN  2                                 ← `decide`: una pregunta de un repositorio, con opciones
//   ▾ PREGUNTAS EN TAREAS  28
//   ◐ ○ Faro: ¿lo parto en pasos?  · faro                         -3d · 6sem   ← la prioridad y el vencimiento que trae
//   ▾ PARA CERRAR  3                                                               (como en «tareas»); el aro, en el
//   ● ○ descartada  Molino: esperar los accesos                         2sem      color de su clase; la palabra, solo
//                                                                                  si el grupo no la dice
//   ▾ PREPARADO PARA DECIDIR  24 · ▾ MENSAJES RETENIDOS  14 · ▾ DE LOS MÓDULOS
//
// Cada grupo va de lo más viejo a lo más nuevo (así llega de telar). Un clic en una fila abre la ventana para contestarla
// (web/contestar.ts: el paso 2 de la propuesta): sus opciones, «Otra cosa…» y «conversarlo»; un permiso sin pregunta no se
// contesta ahí (es de la terminal), y la ventana ofrece ir al hilo. Al pasar el mouse, abrirla donde vive (su objeto, la
// tarea en su ficha) o ir a su hilo; de un mensaje retenido, además, soltarlo (abre la ventana con «Soltarlo» elegido) y
// descartarlo (en el rojo de quitar: pregunta, con el foco en «cancelar», y lo hace). Con más de un retenido, la cabecera de
// su grupo ofrece descartarlos todos, y la pregunta dice cuántos.
//
// Se relee sola cada minuto y medio (si la página se ve) para el número de la barra, al abrir la pestaña y con ↻. El
// buscador y los filtros esconden filas sin repintar (como «tareas»); lo elegido sobrevive a la relectura.

import * as cli from '../../cli';
import { barraBuscar } from '../../componentes/buscador';
import { descarte } from '../../componentes/contestar';
import { filtros, marcarFiltros, contarFiltro } from '../../componentes/filtros';
import { item, pieza, type Accion as AccionDeItem, type Pieza, type Tono } from '../../componentes/item';
import * as S from '../../componentes/senales';
import { esc, normalizar } from '../../estilo';
import { C, I } from '../../web/iconos';
import * as ui from '../../web/ui';
import * as avisos from '../../web/avisos';
import { avisoRetenidos } from '../../web/detenidos';
import * as mundo from '../../web/mundo';
import { fecha, prioridadTarea } from './fila-tarea';
import type { Accion, Pantalla, Tablero } from './pantalla';

/** Las clases que preguntan: las que cuenta el número de la barra. `decide` es la pregunta que un agente dejó en un
 *  repositorio (el módulo preguntas, `pregunta:<repo>/<id>`). */
export const PREGUNTAN = ['permiso', 'pregunta', 'decide', 'avance:pregunta'];

/** Un grupo: su clave, su nombre (y el corto, el de su filtro), sus clases y qué es. `siempre`: se ve aunque esté vacío. */
interface Grupo { clave: string; nombre: string; corto: string; clases: string[]; ayuda: string; siempre?: boolean }
/** Los grupos, en su orden: lo que bloquea un turno vivo arriba. Lo que no calza en ninguno (la clase de un módulo), en
 *  «de los módulos». */
export const GRUPOS: Grupo[] = [
    { clave: 'hilos', nombre: 'hilos que esperan ahora', corto: 'hilos', clases: ['permiso', 'pregunta'], siempre: true,
        ayuda: 'un agente detenido en su turno: un permiso o una pregunta; se contesta en el hilo' },
    { clave: 'decisiones', nombre: 'decisiones que te piden', corto: 'decisiones', clases: ['decide'],
        ayuda: 'lo que un agente te pide decidir, con sus opciones, en un archivo del repositorio (el módulo preguntas)' },
    { clave: 'preguntas', nombre: 'preguntas en tareas', corto: 'preguntas', clases: ['avance:pregunta'], ayuda: 'lo que un agente dejó preguntado en una tarea' },
    { clave: 'cerrar', nombre: 'para cerrar', corto: 'cerrar', clases: ['avance:cerrar', 'avance:choca'],
        ayuda: 'tareas que un agente propone cerrar (hecha, caduca o descartada), o que chocan con otra' },
    { clave: 'preparado', nombre: 'preparado para decidir', corto: 'preparado', clases: ['avance:preparado'], ayuda: 'lo que un agente dejó listo para que decidas' },
    { clave: 'retenidos', nombre: 'mensajes retenidos', corto: 'retenidos', clases: ['retenido'],
        ayuda: 'mensajes entre hilos que el freno de cadenas retuvo: salen si los sueltas (telar mensaje --soltar); si los descartas, no salen nunca y a quien los mandó le llega un aviso (--descartar)' },
    { clave: 'otras', nombre: 'de los módulos', corto: 'módulos', clases: [], ayuda: 'lo que declaran los módulos ([objetos.X] esperando)' },
];

/** El grupo de una clase. */
export const grupoDe = (clase: string): string => GRUPOS.find(g => g.clases.includes(clase))?.clave ?? 'otras';

/** La palabra de cada clase, en el color de su `avance` en las tareas (fila-tarea.ts). */
export const PALABRA: Record<string, [string, Tono]> = {
    permiso: ['permiso', 'espera'], pregunta: ['pregunta', 'atencion'], decide: ['decide', 'atencion'],
    'avance:pregunta': ['pregunta', 'atencion'], 'avance:preparado': ['preparado', 'exito'], 'avance:cerrar': ['cerrar', 'acento'],
    'avance:choca': ['choca', 'peligro'], retenido: ['retenido', 'remoto'],
};

/** Cuánto lleva esperando, corto: «12m», «3h», «5d», «6sem». Una fecha sola es de este reloj, a medianoche. */
export function edad(desde: string, ahora = Date.now()): string {
    if (!desde) return '';
    const t = Date.parse(desde.length === 10 ? `${desde}T00:00:00` : desde);
    if (Number.isNaN(t)) return '';
    const min = Math.max(0, Math.round((ahora - t) / 60000));
    if (min < 60) return `${min}m`;
    if (min < 60 * 24) return `${Math.round(min / 60)}h`;
    const dias = Math.floor(min / 1440);
    return dias < 14 ? `${dias}d` : `${Math.floor(dias / 7)}sem`;
}

/** El hilo de una espera, si tiene (el de un permiso, al que iba un mensaje): adonde lleva «ir al hilo». */
const suHilo = (e: cli.JsonEspera): string => e.enlaces.find(x => x.startsWith('hilo:')) ?? '';

/** En cuántos días vence (negativo: venció), contados desde hoy a medianoche de este reloj, como en «tareas»; null si
 *  no trae una fecha (`campos.vence`). */
export function diasA(vence: unknown, ahora = Date.now()): number | null {
    if (typeof vence !== 'string' || !/^\d{4}-\d{2}-\d{2}/.test(vence)) return null;
    const hoy = new Date(ahora);
    hoy.setHours(0, 0, 0, 0);
    const t = Date.parse(`${vence.slice(0, 10)}T00:00:00`);
    return Number.isNaN(t) ? null : Math.round((t - hoy.getTime()) / 86400000);
}

/** La prioridad de una espera que la trae (una tarea, `campos.prioridad`; si la trae vacía, el punto de «sin
 *  prioridad»), en el círculo de las filas de tareas. Lo que no la tiene (un mensaje retenido, un hilo), nada. */
function prioridadDe(e: cli.JsonEspera): Pieza | null {
    const c = e.campos ?? {};
    if (!('prioridad' in c)) return null;
    return prioridadTarea(typeof c.prioridad === 'number' ? c.prioridad : null);
}

/** Lo que va al final de la fila: cuánto lleva esperando y, antes, si trae una fecha (`campos.vence`), cuándo vence,
 *  como en las filas de tareas (lo vencido en rojo; hoy y mañana en el de cuidado). */
function metaDe(e: cli.JsonEspera, ahora: number): Pieza {
    const cuanto = edad(e.desde, ahora);
    const desde = `espera desde ${e.desde.replace('T', ' ').slice(0, 16)}`;
    const vence = fecha(diasA(e.campos?.vence, ahora));
    if (!vence) return { texto: cuanto, ayuda: e.desde.replace('T', ' ') };
    return { html: `${pieza(vence, 'item-vence')}${cuanto ? ` · ${esc(cuanto)}` : ''}`,
        ayuda: `${vence.ayuda} (${String(e.campos?.vence).slice(0, 10)}) · ${desde}` };
}

/** El nombre corto de una dirección (`proyecto:trabajo/proyectos/faro` → «faro»). */
export const corto = (d: string): string => {
    const id = d.replace(/^[a-z-]+:/, '').replace(/@[\w-]+$/, '');
    try { return decodeURIComponent(id).split('/').pop() ?? ''; } catch { return id.split('/').pop() ?? ''; }
};

/** Las clases que ya nombra su grupo: su fila no repite la palabra (en el teléfono, el título necesita ese lugar). */
const LO_DICE_EL_GRUPO = ['decide', 'avance:pregunta', 'avance:preparado', 'retenido'];

/** Una espera en su fila (componentes/item.ts): su prioridad (si la trae: una tarea), el círculo de «te espera», en el
 *  color de su clase, y dónde vive; la palabra de su clase si el grupo no la dice (permiso o pregunta, cómo cerrarla,
 *  la de un módulo); su título, dónde se contesta, cuándo vence (si trae fecha) y cuánto lleva. Su resumen, en el
 *  globo. */
export function fila(e: cli.JsonEspera, ahora = Date.now()): string {
    const como = typeof e.campos?.como === 'string' ? e.campos.como : '';
    const [nombre, tono] = PALABRA[e.clase] ?? [e.clase.replace(/^avance:/, ''), 'tenue' as Tono];
    // de una que se propone cerrar, el grupo ya dice «cerrar»: va cómo (hecha, caduca, descartada)
    const palabra = e.clase === 'avance:cerrar' && como ? como : nombre;
    const donde = e.clase === 'retenido' ? '' : e.enlaces.map(corto).find(Boolean) ?? '';
    const hilo = suHilo(e);
    const deTerminal = e.clase === 'permiso' && !!hilo;
    const ayuda = [`${e.titulo}`, e.resumen, `${e.direccion} · espera desde ${e.desde.replace('T', ' ').slice(0, 16)}`,
        deTerminal ? 'clic: ver lo que pide (se contesta en la terminal del hilo)' : 'clic: contestarla'].filter(Boolean).join('\n\n');
    // al pasar el mouse: abrirla donde vive y, si tiene hilo, ir a él; un retenido, además, soltarlo o descartarlo
    const acciones = [
        ...(e.clase === 'retenido' ? accionesRetenido(e) : []),
        { accion: 'espera-abrir', icono: I.ver, datos: { valor: e.direccion }, ayuda: 'abrirla donde vive' },
        ...(hilo ? [{ accion: 'espera-abrir', icono: I.adelante, datos: { valor: hilo }, ayuda: `ir a «${corto(hilo)}»` }] : []),
    ];
    const busca = normalizar([e.titulo, e.resumen, e.direccion, e.clase, nombre, como, ...e.enlaces.map(corto)].join(' '));
    return item({
        accion: 'espera-contestar', datos: { valor: e.direccion, busca, grupo: grupoDe(e.clase) }, clases: ['espera'], ayuda,
        inicio: [prioridadDe(e), { ...S.atencion('espera', false, `te espera: ${nombre}${como ? ` ${como}` : ''}`)!, tono },
            e.maquina ? S.remoto(`en ${e.maquina}`) : null],
        prefijo: LO_DICE_EL_GRUPO.includes(e.clase) ? [] : [{ texto: palabra, tono }],
        titulo: e.titulo || e.direccion,
        sufijo: donde ? [{ texto: `· ${donde}`, tono: 'tenue' }] : [],
        meta: metaDe(e, ahora),
        acciones,
    });
}

/** El color de una acción por lo que hace (web/iconos.ts, C), en los tonos del ítem: quitar es el de peligro (el rojo). */
const TONO: Partial<Record<string, Tono>> = { [C.quitar]: 'peligro', [C.hecho]: 'exito' };

/** Soltar y descartar un retenido, al pasar el mouse por su fila: soltarlo abre la ventana con «Soltarlo» elegido (lo
 *  hace su botón: ninguna fila contesta sola); descartarlo pregunta y lo hace. Cada uno con su ícono, su color y su globo,
 *  los de sus opciones en la ventana (componentes/contestar.ts). */
function accionesRetenido(e: cli.JsonEspera): AccionDeItem[] {
    const para = String(e.campos?.para ?? ''), de = String(e.campos?.de ?? '');
    return [
        { accion: 'espera-soltar', icono: I.enviar, tono: TONO[C.hecho], datos: { valor: e.direccion },
            ayuda: `soltarlo: que salga a «${para || '?'}» (lo confirmas en la ventana)` },
        { accion: 'espera-descartar', icono: I.descartar, tono: TONO[C.quitar], datos: { valor: e.direccion },
            ayuda: `descartarlo: no sale nunca${de ? ` y a «${de}» le llega un aviso` : ''} · pide confirmación` },
    ];
}

/** Lo que dice la barra de la pestaña: cuántas, cuántas preguntan y la más vieja. */
export function resumen(lista: cli.JsonEspera[], ahora = Date.now()): string {
    if (!lista.length) return 'nada';
    const n = lista.filter(e => PREGUNTAN.includes(e.clase)).length;
    const vieja = lista.map(e => e.desde).filter(Boolean).sort()[0] ?? '';
    const e = edad(vieja, ahora).replace(/sem$/, ' semanas').replace(/d$/, ' días').replace(/h$/, ' h').replace(/m$/, ' min');
    return `${lista.length} · ${n} ${n === 1 ? 'pregunta' : 'preguntan'}${vieja ? ` · la más vieja, hace ${e}` : ''}`;
}

/** El pie de la lista: cuántas esperan en los otros mundos (se ven con ese mundo puesto, o con ambos). */
export const pieDeOtros = (fuera: number): string =>
    `<div class="fila dim esperas-otros">${fuera === 1 ? 'una más, de otro mundo' : `${fuera} más, de otros mundos`}: se ven con ese mundo puesto</div>`;

/** El cuerpo de la pestaña: las herramientas (buscar, filtrar por grupo) y los grupos con sus filas. */
export function cuerpo(lista: cli.JsonEspera[], plegados: Set<string>, ahora = Date.now()): string[] {
    const de = (g: Grupo) => lista.filter(e => grupoDe(e.clase) === g.clave);
    const h = ['<div id="esperas" class="lista-tareas lista-esperas">',
        barraBuscar({ id: 'buscar-e', cuenta: { id: 'esperas-cuenta' }, claseBarra: 'herram',
            placeholder: 'lo que te espera', ayuda: 'buscar en el título, lo que dicen, su proyecto o su hilo · ⎋ borra' }),
        filtros({ accion: 'esperas-filtro', grupos: [{ clave: 'grupo', nombre: 'cuáles', activa: '',
            opciones: GRUPOS.filter(g => g.siempre || de(g).length).map(g => ({ clave: g.clave, nombre: g.corto, cuenta: de(g).length,
                ayuda: `${g.nombre}: ${g.ayuda}` })) }] })];
    for (const g of GRUPOS) {
        const suyas = de(g);
        if (!suyas.length && !g.siempre) continue;
        const abierto = !plegados.has(g.clave);
        h.push(`<div class="grupo-esperas" data-grupo="${g.clave}">`);
        // los retenidos, si son varios: descartarlos todos de una vez (la pregunta dice cuántos)
        const todos: AccionDeItem[] = g.clave === 'retenidos' && suyas.length > 1
            ? [{ accion: 'esperas-descartar-todos', icono: I.descartar, tono: TONO[C.quitar], datos: { valor: g.clave },
                ayuda: `descartar los ${suyas.length}: no sale ninguno, y a quien mandó cada uno le llega un aviso · pide confirmación` }]
            : [];
        h.push(item({ variante: 'cabecera', accion: 'esperas-plegar', datos: { valor: g.clave }, ayuda: `${g.ayuda}: abrir o cerrar`,
            inicio: [{ icono: abierto ? I.abierto : I.plegado } as Pieza], titulo: g.nombre,
            sufijo: suyas.length ? [{ texto: String(suyas.length), tono: 'tenue' }] : [], acciones: todos }));
        if (abierto) {
            if (!suyas.length) h.push(item({ apagada: true, inicio: [null, null, null], titulo: g.clave === 'hilos' ? 'ningún hilo te espera' : 'nada' }));
            for (const e of suyas) h.push(fila(e, ahora));
        }
        h.push('</div>');
    }
    h.push('<div id="esperas-vacio" class="vacio" hidden>nada calza</div></div>');
    return h;
}

export class PantallaEsperas implements Pantalla {
    readonly pantallas = ['esperas'] as const;
    /** se repinta al leer, no con el reloj: un repintado cada minuto movería el scroll */
    readonly conReloj = [] as const;
    private lista?: cli.JsonEspera[];
    private leyendo?: Promise<void>;
    /** lo buscado y el grupo que rige: sobreviven a cada relectura */
    private q = '';
    private grupo = '';
    private plegados = new Set<string>(leerPlegados());
    /** lo que avisa que cambió el número de la barra (lo pone `vigilar`) */
    private alCambiar: () => void = () => { /* sin vigilar, nadie */ };

    readonly acciones: Record<string, Accion> = {
        esperas: () => this.abrir(),
        'espera-abrir': v => v && ui.abrirDireccion(v),
        'espera-contestar': v => v && this.contestar(v),
        'espera-soltar': v => v && this.contestar(v, { opcion: 'soltar' }),
        'espera-descartar': v => v && this.descartar(this.lista?.filter(e => e.direccion === v) ?? []),
        // los del grupo que se ven (los del mundo puesto): los que cuenta su cabecera
        'esperas-descartar-todos': () => this.descartar(this.visibles()?.filter(e => e.clase === 'retenido') ?? []),
        'esperas-plegar': v => v && this.plegar(v),
        // ↻ de su barra: esto, no el día (que es lo que relee el ↻ del núcleo)
        'esperas-releer': () => this.leer(true),
    };

    constructor(private readonly t: Tablero) {}

    /** Todas, de todos los mundos (lo que cuenta Todo); nada hasta leerlas. */
    todas(): cli.JsonEspera[] | undefined { return this.lista; }

    /** Las del mundo puesto (web/mundo.ts: lo suyo y lo sin clasificar; con ambos o en todo, todas); nada hasta leerlas. */
    visibles(): cli.JsonEspera[] | undefined { return this.lista?.filter(e => mundo.seVe(e.mundo) && !mundo.deAgenteAjeno(e)); }

    /** Cuántas preguntan (el número de su fila en la barra), en el mundo puesto; nada hasta leerlas. */
    cuenta(): number | undefined { return this.visibles()?.filter(e => PREGUNTAN.includes(e.clase)).length; }
    cuentaAyuda(): string {
        const v = this.visibles();
        if (!v || !this.lista) return '';
        const fuera = this.lista.length - v.length;
        return `${this.cuenta()} preguntan (hilos que esperan, decisiones que te piden y preguntas en tareas); ${v.length} en total`
            + (fuera ? ` · ${fuera} más en otros mundos` : '');
    }

    /** Leerlas ahora y cada minuto y medio, mientras la página se vea; `cambio`, cuando cambia el número. */
    vigilar(cambio: () => void): void {
        this.alCambiar = cambio;
        const leer = async () => {
            const antes = this.cuenta();
            await this.leer();
            if (this.cuenta() !== antes) cambio();
        };
        void leer();
        setInterval(() => { if (!document.hidden) void leer(); }, 90 * 1000);
    }

    async abrir(): Promise<void> {
        this.t.abrir();
        this.t.ir('esperas');
        this.pintar();
        await this.leer(true);
    }

    /** Pide la bandeja (una a la vez) y, si se ve y cambió, la repinta. */
    private leer(forzar = false): Promise<void> {
        this.leyendo ??= (async () => {
            const r = await cli.esperas();
            const antes = JSON.stringify(this.lista);
            if (r.datos) this.lista = r.datos.esperas;
            this.avisar(r);
            // un mensaje retenido no se queda callado: también en la franja (web/detenidos.ts)
            if (r.datos) {
                // (en la franja, siempre a la vista: lo de un agente que pide esconderse fuera de su mundo, con otro puesto, no se nombra)
                const retenidos = avisoRetenidos(r.datos.esperas.filter(e => !mundo.deAgenteAjeno(e)), () => void this.abrir());
                if (retenidos) avisos.poner(retenidos); else avisos.quitar('retenidos');
            }
            if (this.t.pantalla === 'esperas' && (forzar || antes !== JSON.stringify(this.lista))) this.pintar();
        })().finally(() => { this.leyendo = undefined; });
        return this.leyendo;
    }

    /** Lo que no se pudo leer, en la franja de avisos (web/avisos.ts): toda la bandeja (si telar contestó con un error;
     *  sin respuesta, lo dice el aviso de la conexión) o una de sus fuentes. Lo que vuelve a leerse, se va. Antes, una
     *  línea arriba de la lista; Táctica, que lee lo mismo, ya no lo repite. */
    private avisar(r: cli.Respuesta<cli.JsonEsperas>): void {
        if (!r.datos && !r.estado) return;   // sin conexión: lo que se sabía sigue
        const ir = { texto: 'te esperan', hacer: () => void this.abrir() };
        const fallas: avisos.Aviso[] = r.datos
            ? Object.entries(r.datos.fallas ?? {}).map(([tipo, motivo]) => ({ clave: `fuente:esperas:${tipo}`, nivel: 'falla', icono: I.alerta,
                conConexion: true, texto: `«te esperan» sin ${tipo}`, detalle: `No se pudo leer lo que espera de ${tipo}: ${motivo}. Lo demás sí.`,
                hacer: 'Se vuelve a leer sola cada minuto y medio; ↻ en «te esperan», ahora.', ir }))
            : [{ clave: 'fuente:esperas', nivel: 'falla', icono: I.alerta, conConexion: true, texto: 'no se pudo leer lo que te espera',
                detalle: `${(r.error ?? '').replace(/[.]?$/, '.')}${this.lista ? ' La lista es la de la última vez.' : ''}`,
                hacer: 'Se vuelve a leer sola cada minuto y medio; ↻ en «te esperan», ahora.', ir }];
        avisos.soloEstos('fuente:esperas', fallas);
    }

    pintar(): void {
        const enBuscador = document.activeElement?.id === 'buscar-e' ? (document.activeElement as HTMLInputElement).selectionStart ?? 0 : -1;
        const lista = this.visibles();
        const fuera = (this.lista?.length ?? 0) - (lista?.length ?? 0);
        // la barra, solo el título y ↻: cuántas y la más vieja, en el globo del título; las de otros mundos, al pie de la lista
        const barra = { nombre: 'te esperan', color: 'magenta', ayuda: lista ? resumen(lista) : undefined,
            acciones: [{ accion: 'esperas-releer', icono: I.releer, ayuda: 'volver a leer lo que te espera' }], sinReleer: true };
        if (!lista) {
            this.t.pintar(['<div class="vacio">leyendo lo que te espera…</div>'], barra);
            return;
        }
        this.t.pintar([...cuerpo(lista, this.plegados), ...fuera ? [pieDeOtros(fuera)] : []], barra);
        this.montar(enBuscador);
    }

    /** Después de pintar: lo buscado y el grupo que rige, otra vez; y el buscador, que filtra sin repintar. */
    private montar(cursor: number): void {
        const b = document.getElementById('buscar-e') as HTMLInputElement | null;
        if (!b) return;
        b.value = this.q;
        if (cursor >= 0) { b.focus(); b.setSelectionRange(cursor, cursor); }
        b.addEventListener('input', () => { this.q = b.value; this.aplicar(); });
        b.addEventListener('keydown', e => {
            if (e.key !== 'Escape') return;
            e.preventDefault();
            if (b.value) { b.value = ''; this.q = ''; this.aplicar(); } else b.blur();
        });
        // un grupo del filtro: rige, y otro clic en el que rige lo suelta. Se atiende aquí, antes que el dashboard (que
        // con un filtro de otra lista haría lo suyo)
        document.querySelector('#esperas .filtros')?.addEventListener('click', e => {
            const op = (e.target as HTMLElement).closest<HTMLElement>('.filtros-op');
            if (!op) return;
            e.stopPropagation();
            this.filtrar(op.dataset.id ?? '');
        });
        this.aplicar();
    }

    /** Esconde lo que no calza con lo buscado ni con el grupo que rige, y pone las cuentas. */
    private aplicar(): void {
        const raiz = document.getElementById('esperas');
        if (!raiz) return;
        const partes = normalizar(this.q).split(/\s+/).filter(Boolean);
        const calza = (f: HTMLElement) => partes.every(p => (f.dataset.busca ?? '').includes(p));
        let n = 0;
        for (const g of raiz.querySelectorAll<HTMLElement>('.grupo-esperas')) {
            const filas = [...g.querySelectorAll<HTMLElement>('.item.espera')];
            let suyas = 0;
            for (const f of filas) { f.hidden = !calza(f); if (!f.hidden) suyas += 1; }
            // un grupo que el filtro deja fuera no se ve; con lo buscado, tampoco uno que quedó vacío
            g.hidden = (!!this.grupo && g.dataset.grupo !== this.grupo) || (partes.length > 0 && suyas === 0 && filas.length > 0)
                || (partes.length > 0 && !filas.length);
            if (!g.hidden) n += suyas;
        }
        marcarFiltros(raiz, 'grupo', this.grupo);
        for (const b of raiz.querySelectorAll<HTMLElement>('.filtros-op')) {
            const clave = (b.dataset.id ?? '').slice('grupo:'.length);
            contarFiltro(b, [...raiz.querySelectorAll<HTMLElement>(`.grupo-esperas[data-grupo="${CSS.escape(clave)}"] .item.espera`)].filter(calza).length);
        }
        const total = raiz.querySelectorAll('.item.espera').length;
        const cuenta = document.getElementById('esperas-cuenta');
        if (cuenta) cuenta.textContent = partes.length || this.grupo ? `${n} de ${total}` : '';
        const vacio = document.getElementById('esperas-vacio');
        if (vacio) vacio.hidden = n > 0 || (!partes.length && !this.grupo);
    }

    /** Un clic en un grupo del filtro: rige; otro en el que rige, lo suelta. */
    private filtrar(id: string): void {
        const clave = id.startsWith('grupo:') ? id.slice(6) : id;
        this.grupo = this.grupo === clave ? '' : clave;
        this.aplicar();
    }

    /** La ventana para contestar una (web/contestar.ts), con `inicial` elegido si viene de una acción de su fila. Hecho,
     *  sale de la lista al tiro y se relee. */
    private async contestar(direccion: string, inicial: { opcion?: string } = {}): Promise<void> {
        const e = this.lista?.find(x => x.direccion === direccion);
        if (!e) { ui.abrirDireccion(direccion); return; }
        const { abrirContestar, HACER } = await import('../../web/contestar');
        const dice = await abrirContestar(e, HACER, Date.now(), inicial);
        if (!dice) return;
        ui.estado(dice, 6000);
        await this.salieron([direccion]);
    }

    /** Descartar mensajes retenidos (uno, desde su fila; todos los de su grupo, desde la cabecera): pregunta, con el foco
     *  en «cancelar» y cuántos, y los descarta uno tras otro. Los que salieron dejan la lista al tiro, y se relee. */
    private async descartar(lista: cli.JsonEspera[]): Promise<void> {
        if (!lista.length) return;
        const p = descarte(lista);
        if (await ui.aviso(p.pregunta, 'Descartar', { destruye: true, detalle: p.detalle }) !== 'Descartar') return;
        const { descartarRetenidos } = await import('../../web/contestar');
        const r = await ui.progreso({ titulo: lista.length === 1 ? 'descartando…' : `descartando ${lista.length} mensajes…`, discreto: lista.length === 1 },
            () => descartarRetenidos(lista));
        if (r.falla) void ui.falla(`${r.hechos.length ? `${r.dice}. ` : ''}No se descartó: ${r.falla}`);
        else ui.estado(r.dice, 6000);
        if (r.hechos.length) await this.salieron(r.hechos);
    }

    /** Lo contestado o descartado sale de la lista al tiro (y del número de la barra); después se relee. */
    private async salieron(direcciones: string[]): Promise<void> {
        this.lista = this.lista?.filter(x => !direcciones.includes(x.direccion));
        if (this.t.pantalla === 'esperas') this.pintar();
        this.alCambiar();
        await this.leer(true);
        this.alCambiar();
    }

    private plegar(clave: string): void {
        if (this.plegados.has(clave)) this.plegados.delete(clave); else this.plegados.add(clave);
        try { localStorage.setItem('telar.esperas.plegados', JSON.stringify([...this.plegados])); } catch { /* sin almacenamiento: dura lo que la página */ }
        this.pintar();
    }

}

function leerPlegados(): string[] {
    try {
        const v = JSON.parse(localStorage.getItem('telar.esperas.plegados') ?? '[]');
        return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : [];
    } catch { return []; }
}
