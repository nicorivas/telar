// Contestar una espera de «te esperan» en su ventana (componentes/contestar.ts dibuja; aquí se abre, se elige y se manda).
// Una sola ventana para todas las clases, sobre `abrirVentana` (web/ventana.ts). Lo que hace cada clase es lo que ya
// existía, por su camino de siempre:
//
// - el `avance` de una tarea: `responder` (lo escrito) o, si propone cerrarla, `cerrar` como propone; las dos sobre la
//   versión que se leyó (POST /objetos/tarea:…/acciones/…);
// - un retenido: soltarlo (POST /mensajes/<id>/soltar) o descartarlo (POST /mensajes/<id>/descartar), que antes pregunta,
//   con el foco en «cancelar» (`Hacer.confirmar`);
// - la pregunta en vivo de un hilo: como la vista conversación (POST /hilos/responder), una respuesta por pregunta;
// - la pregunta de un módulo (`decide`): su acción `responder`, con `opcion` o con `texto`, sobre su versión.
//
// De una tarea, la barra del encabezado (componentes/contestar.ts, `barraHtml`) corre las acciones de su ficha como en la
// vista tareas (vistas/dashboard/tareas.ts, `correrAccion`: la fecha con elegirFecha, la prioridad, quién la hace…), sin
// cerrar la ventana: después se relee la tarea, y la ficha, la barra y la versión sobre la que se contesta quedan las de
// ahora. Mover la fecha no contesta la propuesta (sigue ahí para responderla); esperar a alguien, hecha o descartar sí
// (el modelo la borra): entonces la ventana se cierra con lo hecho.
//
// Si lo que se contesta cambió mientras se miraba (409), la ventana relee la espera y lo dice, con lo nuevo a la vista; si
// ya no espera (la contestaron en otro lado, la retiraron), lo dice y no deja mandar. Lo escrito en «Otra cosa…» se guarda
// mientras viva la pestaña (web/guardado.ts): cerrar la ventana sin mandar no lo pierde.
//
// Lo que hace cada botón llega en `Hacer`: el de verdad es `HACER`; el catálogo (/componentes) y el ensayo (`window.telar
// .ensayoContestar`) le pasan uno de mentira, que no toca nada.

import * as cli from '../cli';
import {
    MARCAS_AGENTE, aQuien, comoCierre, contestable, eleccion, estadoInicial, hayQueMandar, lineasAgente, listo, porConfirmar, propsContestar, quita,
    ventanaContestar, type Confirmacion, type Contestable, type EstadoContestar, type ParaElAgente,
} from '../componentes/contestar';
import { hito } from '../componentes/ficha-contestar';
import { detallesDeMuestra, fichaDeMuestra } from '../componentes/muestras-contestar';
import { guardar, leer } from './guardado';
import { abrirVentana } from './ventana';

/** Lo que resulta de mandar: hecho (con lo que se dice), o no (y por qué; `cambio`: cambió desde que se leyó). */
export type Resultado = { ok: true; dice: string } | { ok: false; error: string; cambio?: boolean };

/** Lo que hacen los botones de la ventana. */
export interface Hacer {
    /** mandar lo elegido */
    contestar(e: cli.JsonEspera, c: Contestable, s: EstadoContestar): Promise<Resultado>;
    /** la espera otra vez, como está ahora: null si ya no espera, undefined si no se pudo leer */
    releer(e: cli.JsonEspera): Promise<cli.JsonEspera | null | undefined>;
    /** lo que no viene en la espera y hace recordar (la tarea entera, su proyecto, las otras del proyecto): campos para
     *  sumar a los de la espera. Lo que llega antes (la tarea) lo puede ir dando `parcial`, y lo último, al terminar */
    completar?(e: cli.JsonEspera, parcial?: (mas: Record<string, unknown>) => void): Promise<Record<string, unknown> | undefined>;
    /** «conversarlo»: la instrucción con la espera como contexto */
    conversar(e: cli.JsonEspera, c: Contestable): void;
    /** «ir al hilo», «abrirla» */
    ir(direccion: string): void;
    /** ofrece «para el agente» (la nota para la tarea y cómo trabajar esto) */
    paraElAgente?: boolean;
    /** dejarle al agente sus líneas en la tarea (una [respuesta] cada una) y, con «hazte cargo ya», avisarle; `hecho` dice
     *  lo que ya salió en un intento anterior (no se repite) y se va llenando */
    alAgente?(e: cli.JsonEspera, c: Contestable, lineas: string[], hecho: { lineas: number; mensaje: boolean }): Promise<Resultado>;
    /** el agente que escribe los avances (el de `[agentes] sin_proyecto`), para cuando no se sabe quién la propuso */
    agenteGeneral?(): Promise<string>;
    /** correr la acción `k` de la ficha de la tarea (la de su barra): undefined si se canceló */
    accionTarea?(e: cli.JsonEspera, k: number): Promise<Resultado | undefined>;
    /** antes de lo que destruye (descartar un retenido): ¿sí? Con el foco en «cancelar». Sin esto, no se pregunta */
    confirmar?(c: Confirmacion): Promise<boolean>;
}

/** El agente que escribe los avances, de la configuración (una vez por página). */
let general: Promise<string> | undefined;
const agenteGeneral = (): Promise<string> => (general ??= cli.config()
    .then(r => r.datos?.agente_general?.nombre || r.datos?.agente_general?.clave || '').catch(() => ''));

/** La respuesta a la pregunta en vivo, una por pregunta: la elegida, las elegidas con coma, o lo escrito (como
 *  web/pregunta.ts: con varias, lo escrito va al final). */
export function respuestasEnVivo(e: cli.JsonEspera, c: Contestable, s: EstadoContestar): Record<string, string> {
    const preguntas = (e.campos?.preguntas ?? []) as { pregunta: string }[];
    const elegido = eleccion(c, s);
    return Object.fromEntries(preguntas.map((q, i) => [q.pregunta, [...elegido[i].opciones, ...(elegido[i].texto ? [elegido[i].texto] : [])].join(', ')]));
}

const sinTildes = (t: string) => t.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();

/** A quién va «conversarlo» de una pregunta: el que preguntó (`agente:almacen`, `hilo:Faro`), con el nombre con que
 *  lo lista la instrucción (un agente se lista por su nombre, «Almacén»; su carpeta va en minúsculas y sin tildes). */
export function quienPregunto(de: string, agentes: string[]): string {
    const [tipo, ...resto] = de.split(':');
    const id = resto.join(':').trim();
    if (!id) return '';
    if (tipo === 'agente') return agentes.find(n => sinTildes(n) === sinTildes(id)) ?? id;
    return tipo === 'hilo' ? id : '';
}

/** Los proyectos (`telar proyectos`), una vez por página: el nombre y el estado del de cada tarea. Si falla, se vuelve a
 *  pedir la próxima vez. */
let proyectos: Promise<cli.JsonProyecto[]> | undefined;
const losProyectos = (): Promise<cli.JsonProyecto[]> => (proyectos ??= cli.proyectos().then(r => {
    if (!r.datos) { proyectos = undefined; return []; }
    return r.datos.proyectos;
}));

/** El número de una tarea por su dirección: `tarea:T129@servidor` → `T129`. */
const numeroDe = (direccion: string): string => direccion.replace(/^tarea:/, '').replace(/@[\w-]+$/, '');

const de = (r: cli.Respuesta<unknown>, hecho: string): Resultado =>
    r.datos !== undefined ? { ok: true, dice: hecho } : { ok: false, error: r.error ?? 'no se pudo', cambio: r.estado === 409 };

/** Lo de verdad: las acciones de telar, por la API. */
export const HACER: Hacer = {
    async contestar(e, c, s) {
        const [b] = eleccion(c, s);
        const version = String(e.campos?.version ?? '');
        if (c.clase === 'tarea') {
            if (b.opciones[0] === 'cerrar') {
                const r = await cli.accionObjeto(e.direccion, 'cerrar', { como: comoCierre(e) || 'hecha', nota: '' }, version);
                // cerrada, sale de lo pendiente en todas las vistas (la lista de tareas, Hacer) sin esperar la relectura
                if (r.datos !== undefined) (await import('../vistas/dashboard/dia')).salio(String(e.campos?.proveedor || 'tareas'), numeroDe(e.direccion));
                return de(r, 'cerrada');
            }
            // una opción (de decidir, su texto; de aprobar, enviar o descartar) o lo escrito (de aprobar, «editar: …»)
            const texto = b.opciones[0] ?? `${c.prefijoOtra ?? ''}${b.texto}`;
            return de(await cli.accionObjeto(e.direccion, 'responder', { texto }, version), 'respondida');
        }
        if (c.clase === 'retenido') {
            if (b.opciones[0] === 'descartar') {
                const r = await descartarRetenidos([e]);
                return r.falla ? { ok: false, error: r.falla } : { ok: true, dice: r.dice };
            }
            return de(await cli.soltarMensaje(e.direccion.replace(/^mensaje:/, '')), `soltado: va a «${String(e.campos?.para ?? '')}»`);
        }
        if (c.clase === 'decide') {
            return de(await cli.accionObjeto(e.direccion, 'responder', b.opciones[0] ? { opcion: b.opciones[0] } : { texto: b.texto }, version),
                'respondida: le llega a quien preguntó');
        }
        if (c.clase === 'en-vivo') {
            const r = await cli.responderPregunta(String(e.campos?.hilo ?? ''), e.maquina ?? '', String(e.campos?.pregunta ?? ''), respuestasEnVivo(e, c, s));
            if (!r.datos) return { ok: false, error: r.error ?? 'no se envió', cambio: r.estado === 409 };
            if (r.datos.por === 'terminal') return { ok: true, dice: 'ya la habían contestado en la terminal' };
            if (!r.datos.tomada) return { ok: false, error: 'quedó en camino: el agente todavía no la toma (si sigue abierta, vuelve a responder)' };
            return { ok: true, dice: 'respondida: el agente sigue' };
        }
        return { ok: false, error: 'esto no se contesta desde aquí' };
    },
    async releer(e) {
        const r = await cli.esperas([e.tipo]);
        if (!r.datos) return undefined;
        return r.datos.esperas.find(x => x.direccion === e.direccion) ?? null;
    },
    async completar(e, parcial) {
        if (e.tipo !== 'tarea') return undefined;
        // la tarea entera primero (el contexto, la historia, sus conexiones) y, a la par, su ficha del proveedor (las
        // acciones de la barra); después su proyecto y las otras del proyecto
        const id = numeroDe(e.direccion);
        const deFicha = fichaDelProveedor(id);
        const r = await cli.tareaEntera(id);
        if (!r.datos) return { tarea_falla: r.error ?? 'no contestó' };
        const t = r.datos;
        const tarea = { tarea: t, ...(t.version ? { version: e.campos?.version ?? t.version } : {}) };
        const ruta = t.proyecto || (e.enlaces.find(x => x.startsWith('proyecto:')) ?? '').slice('proyecto:'.length).replace(/@[\w-]+$/, '');
        if (!ruta) return { ...tarea, ...await deFicha };
        parcial?.(tarea);
        const [ps, otras, ficha] = await Promise.all([losProyectos(), cli.tareasDeProyecto(ruta), deFicha]);
        const p = ps.find(x => x.ruta === ruta);
        return { ...tarea, ...ficha, ...(p ? { proyecto_ficha: p } : {}), ...(otras.datos ? { otras: otras.datos.tareas } : {}) };
    },
    conversar(e, c) {
        void (async () => {
            const [m, { modelo }] = await Promise.all([import('./instruccion'), import('../modelo')]);
            // la de un agente va de entrada al que preguntó (su `de`): por su nombre en la lista de a quién
            const agentes = modelo.secciones.filter(x => x.grupo === 'agentes').map(x => x.nombre);
            const a = c.clase === 'decide' ? quienPregunto(String(e.campos?.de ?? ''), agentes) : '';
            await m.abrir({ direccion: e.direccion, titulo: c.titulo, ...(a ? { a } : {}) });
        })();
    },
    ir(direccion) { void import('./ui').then(ui => ui.abrirDireccion(direccion)); },
    paraElAgente: true,
    async alAgente(e, c, lineas, hecho) {
        return await alAgenteDe(e.direccion, lineas, hecho, c.agente?.a);
    },
    agenteGeneral,
    async accionTarea(e, k) {
        // como en la ficha de la vista tareas: con su selector, lo que pide y su confirmación, sobre la versión de su ficha
        const ficha = e.campos?.ficha_tarea as cli.JsonPagina | undefined;
        const a = ficha?.acciones?.[k];
        if (!ficha || !a) return { ok: false, error: 'todavía no llegan las acciones de la tarea' };
        const [{ correrAccion }, { olvidarDia }] = await Promise.all([import('../vistas/dashboard/tareas'), import('../vistas/dashboard/dia')]);
        const hecho = await correrAccion(numeroDe(e.direccion), String(e.campos?.proveedor || 'tareas'), ficha, k);
        if (!hecho) return undefined;
        olvidarDia();
        const nombre = a.nombre.replace(/^[★☆◉○✓]\s*/, '').replace(/…$/, '');
        return de(hecho.r, `${nombre}${hecho.texto ? `: ${hecho.texto}` : ''}`);
    },
    async confirmar(p) {
        const ui = await import('./ui');
        return (await ui.aviso(p.pregunta, p.boton, { destruye: true, detalle: p.detalle })) === p.boton;
    },
};

/** Descartar mensajes retenidos, uno tras otro (POST /mensajes/<id>/descartar): desde Contestar, uno; desde «te esperan»,
 *  el de una fila o todos los de su grupo. Sin preguntar: pregunta quien llama. Si uno falla, sigue con los demás.
 *  Devuelve las direcciones que salieron de los retenidos, lo que se dice (cuántos, y si a quien los mandó le llegó su
 *  aviso) y, si alguno no se pudo, por qué (`falla`). */
export async function descartarRetenidos(lista: readonly cli.JsonEspera[]): Promise<{ hechos: string[]; dice: string; falla?: string }> {
    const hechos: string[] = [], sinAviso: string[] = [], fallas: string[] = [];
    for (const e of lista) {
        const r = await cli.descartarMensaje(e.direccion.replace(/^mensaje:/, ''));
        if (!r.datos) { fallas.push(r.error ?? 'no se pudo'); continue; }
        hechos.push(e.direccion);
        if (r.datos.sin_aviso) sinAviso.push(`a «${r.datos.de}» no le llegó el aviso (${r.datos.sin_aviso})`);
    }
    const uno = lista.length === 1 ? lista[0] : undefined;
    const de = uno ? String(uno.campos?.de ?? '') : '';
    const dice = !hechos.length ? ''
        : uno ? `descartado: no va a «${String(uno.campos?.para ?? '')}»${sinAviso.length ? `; ${sinAviso[0]}` : de ? `; a «${de}» le llegó un aviso` : ''}`
            : `${hechos.length} ${hechos.length === 1 ? 'descartado' : 'descartados'}${sinAviso.length ? `; ${sinAviso.join('; ')}` : '; a quien los mandó le llegó un aviso'}`;
    const falla = !fallas.length ? undefined
        : uno ? fallas[0] : `${fallas.length} no se ${fallas.length === 1 ? 'pudo' : 'pudieron'} descartar: ${[...new Set(fallas)].join('; ')}`;
    return { hechos, dice, ...falla ? { falla } : {} };
}

/** Dejarle al agente sus líneas en la tarea (una [respuesta] cada una, sin versión: la respuesta de recién ya la cambió)
 *  y, si una es un prompt («hazte cargo ya»; «revisar ya» en Táctica), avisarle con un mensaje como de la persona, con la
 *  dirección de la tarea. Le llega al agente `a` (el que la propuso) o, sin él, al que escribe los avances. `hecho` dice lo
 *  que ya salió en un intento anterior (no se repite) y se va llenando. */
export async function alAgenteDe(direccion: string, lineas: string[], hecho: { lineas: number; mensaje: boolean }, a0 = ''): Promise<Resultado> {
    const a = a0 || await agenteGeneral();
    const prompt = lineas.find(l => l.startsWith(`${MARCAS_AGENTE.ya}:`));
    // sin a quién avisarle, ni siquiera se escribe: la tarea diría que se le avisó
    if (prompt && !hecho.mensaje && !a) return { ok: false, error: 'no sé a qué agente avisarle: la configuración no dice quién escribe los avances ([agentes] sin_proyecto)' };
    for (; hecho.lineas < lineas.length; hecho.lineas++) {
        const r = await cli.accionObjeto(direccion, 'responder', { texto: lineas[hecho.lineas] });
        if (r.datos === undefined) return { ok: false, error: r.error ?? 'no quedó en la tarea' };
    }
    if (prompt && !hecho.mensaje) {
        const r = await cli.escribirComoPersona(a, `${direccion} · ${prompt}`, '');
        if (r.error) return { ok: false, error: `quedó en la tarea, pero el aviso a ${a} no salió: ${r.error}` };
        hecho.mensaje = true;
    }
    return { ok: true, dice: `${lineas.length === 1 ? 'la nota quedó' : 'las notas quedaron'} en la tarea${a ? ` para ${a}` : ''}${prompt ? ', con un aviso para que lo atienda ya' : ''}` };
}

/** La ficha de una tarea como la da su proveedor (`GET /tareas/<id>`): sus acciones, para la barra. El proveedor, el de
 *  su fila en el día (vistas/dashboard/dia.ts, `proveedorDe`). Si no se pudo leer, sin barra. */
async function fichaDelProveedor(id: string): Promise<{ ficha_tarea?: cli.JsonPagina; proveedor?: string }> {
    const { proveedorDe } = await import('../vistas/dashboard/dia');
    const proveedor = proveedorDe(`tarea:${id}`);
    const r = await cli.tarea(id, proveedor);
    return r.datos ? { ficha_tarea: r.datos, proveedor } : {};
}

/** Lo que dice una línea `edita` de la historia («prioridad, tamano»), con cómo quedó cada campo en la tarea. */
function editado(campos: string, t: cli.JsonTarea): string {
    const valor: Record<string, () => string> = {
        prioridad: () => `prioridad P${t.prioridad ?? '?'}`, tamano: () => `tamaño ${t.tamano || 'sin decir'}`,
        etiquetas: () => `etiquetas: ${t.etiquetas?.join(', ') || 'ninguna'}`,
    };
    return campos.split(/,\s*/).map(c => valor[c]?.() ?? c).join(', ');
}

/** Lo que llega elegido al abrirla (desde una fila de Táctica): una opción, u «Otra cosa…» abierto. */
export interface Inicial { opcion?: string; otra?: boolean }

/** Abre la ventana de una espera. Termina con lo que se dijo al hacerlo, o undefined si se cerró sin hacer nada. */
export function abrirContestar(e0: cli.JsonEspera, hacer: Hacer = HACER, ahora = Date.now(), inicial: Inicial = {}): Promise<string | undefined> {
    let e = e0;
    let c = contestable(e, ahora);
    const llave = `contestar:${e.direccion}`;
    // lo que se le deja al agente, con lo que quedó escrito si se cerró (o falló) antes
    const agenteGuardado = leer<ParaElAgente>(`${llave}:agente`);
    let s: EstadoContestar = { ...estadoInicial(c), otras: c.bloques.map((_, i) => leer<string[]>(llave)?.[i] ?? ''),
        ...hacer.paraElAgente && c.agente ? { agente: { cuando: 'revision', nota: '', meta: '', abierto: false, ...agenteGuardado,
            ...agenteGuardado && (agenteGuardado.nota || agenteGuardado.meta) ? { abierto: true } : {} } as ParaElAgente } : {} };
    // lo elegido desde la fila: una opción que esté, o «Otra cosa…» abierto
    if (inicial.opcion && c.bloques[0]?.opciones.some(o => o.id === inicial.opcion)) s = { ...s, elegidas: s.elegidas.map((x, i) => (i === 0 ? [inicial.opcion!] : x)) };
    if (inicial.otra && c.bloques[0]?.otra) s = { ...s, abierta: 0 };
    const recordarAgente = () => guardar(`${llave}:agente`, s.agente && (s.agente.nota.trim() || s.agente.meta.trim())
        ? { cuando: s.agente.cuando, nota: s.agente.nota, meta: s.agente.meta } : undefined);
    /** lo que ya salió en un intento anterior: no se repite al volver a mandar */
    const hecho = { respuesta: false, lineas: 0, mensaje: false };
    let dialogo: HTMLDialogElement | undefined;
    let cerrar: (v?: string) => void = () => { /* lo pone abrirVentana */ };

    /** Repintar lo de adentro con el estado; el campo que tenía el foco lo vuelve a tener, con el cursor donde estaba. */
    const pintar = () => {
        if (!dialogo) return;
        const activo = document.activeElement as HTMLTextAreaElement | null;
        const enCampo = activo?.classList.contains('contestar-campo') ? { sel: `.contestar-campo[data-bloque="${activo.dataset.bloque}"]`, pos: activo.selectionStart }
            : activo?.classList.contains('contestar-agente-campo') ? { sel: `.contestar-agente-campo[data-agente="${activo.dataset.agente}"]`, pos: activo.selectionStart } : null;
        dialogo.innerHTML = ventanaContestar(c, s);
        const campo = enCampo ? dialogo.querySelector<HTMLTextAreaElement>(enCampo.sel) : null;
        if (campo) { campo.focus(); campo.setSelectionRange(enCampo!.pos, enCampo!.pos); }
        crecer();
    };
    const crecer = () => dialogo?.querySelectorAll<HTMLTextAreaElement>('.contestar-campo, .contestar-agente-campo').forEach(t => {
        t.style.height = 'auto'; t.style.height = `${t.scrollHeight}px`;
    });
    const recordar = () => guardar(llave, s.otras);

    /** Lo que dijo lo ya hecho, para el final. */
    const dicho: string[] = [];

    /** Una acción de la barra de la tarea, sin cerrar la ventana: se corre, se relee la tarea (la ficha, su historia y la
     *  barra como quedaron; la versión de ahora, para lo que se conteste después) y se dice lo que quedó en su historia.
     *  Si con eso la propuesta dejó de esperar (esperar a alguien, hecha, descartar), está contestada: se cierra. */
    let haciendo = false;
    const deLaBarra = async (k: number) => {
        if (!hacer.accionTarea || s.enviando || haciendo) return;
        haciendo = true;
        try {
            const r = await hacer.accionTarea(e, k);
            if (!r || !dialogo?.isConnected) return;
            if (!r.ok) {
                s = { ...s, aviso: { tono: 'falla', texto: `No se hizo: ${r.error}${r.cambio ? ' (la tarea cambió mientras la mirabas: ciérrala y vuelve a abrirla)' : ''}` } };
                pintar();
                return;
            }
            s = { ...s, haciendo: true, aviso: undefined };
            pintar();
            const mas = await hacer.completar?.(e).catch(() => undefined);
            const t = mas?.tarea as cli.JsonTarea | undefined;
            if (mas && !mas.tarea_falla) {
                // lo de la tarea que la espera también trae (su línea de arriba), como quedó
                e = { ...e, campos: { ...e.campos ?? {}, ...mas, ...t?.version ? { version: t.version } : {},
                    ...t ? { vence: t.vence ?? '', prioridad: t.prioridad ?? e.campos?.prioridad, dueno: t.dueno ?? '' } : {} } };
                const otro = contestable(e, ahora);
                c = { ...c, ayuda: otro.ayuda, detalle: otro.detalle, ficha: otro.ficha, barra: otro.barra };
            }
            const ultima = t?.historia?.at(-1);
            const quedo = !ultima ? r.dice : ultima.tipo === 'edita' && t ? editado(ultima.texto, t) : hito(ultima).texto;
            if (t && (!t.avance || ['hecha', 'caduca', 'descartada'].includes(t.estado))) {
                dicho.push(quedo);
                cerrar(dicho.join('; '));
                return;
            }
            s = { ...s, haciendo: false, aviso: { tono: 'info', texto: `Quedó en su historia: ${quedo}. La propuesta sigue esperando tu respuesta.` } };
            pintar();
        } finally {
            haciendo = false;
            if (s.haciendo && dialogo?.isConnected) { s = { ...s, haciendo: false }; pintar(); }
        }
    };
    /** Lo que se le deja al agente: después de la respuesta (si la hay). Si falla, la ventana sigue abierta, con lo
     *  escrito, y volver a mandar hace solo lo que falta. */
    const alAgente = async (): Promise<void> => {
        const lineas = lineasAgente(s.agente);
        if (lineas.length && hacer.alAgente) {
            const r = await hacer.alAgente(e, c, lineas, hecho);
            if (!r.ok) {
                s = { ...s, enviando: false, aviso: { tono: 'falla', texto: `${dicho.length ? `${dicho.join('; ')}. ` : ''}Lo que le dejabas al agente no salió: ${r.error}. Queda escrito: vuelve a mandarlo.` } };
                pintar();
                return;
            }
            dicho.push(r.dice);
        }
        guardar(`${llave}:agente`, undefined);
        cerrar(dicho.join('; '));
    };

    /** mientras pregunta si de verdad (lo que destruye): un ⏎ más no vuelve a preguntar */
    let confirmando = false;
    const mandar = async () => {
        if (!(hecho.respuesta ? lineasAgente(s.agente).length : hayQueMandar(c, s)) || s.enviando || confirmando) return;
        // lo que destruye (descartar un retenido) pregunta antes, con el foco en «cancelar»; si no, no se manda nada
        if (!hecho.respuesta && listo(c, s) && hacer.confirmar) {
            confirmando = true;
            try {
                for (const p of porConfirmar(c, s)) if (!(await hacer.confirmar(p))) return;
            } finally { confirmando = false; }
            if (!dialogo?.isConnected) return;
        }
        s = { ...s, enviando: true, aviso: undefined };
        pintar();
        // sin nada elegido (o ya contestada), solo lo del agente
        if (hecho.respuesta || !listo(c, s)) { await alAgente(); return; }
        const r = await hacer.contestar(e, c, s);
        if (r.ok) { guardar(llave, undefined); hecho.respuesta = true; dicho.push(r.dice); await alAgente(); return; }
        if (r.cambio) {
            // cambió desde que se leyó: se relee, y lo de ahora queda a la vista; lo elegido, si sigue estando
            const nueva = await hacer.releer(e);
            if (nueva === null) {
                c = { ...c, bloques: [], nota: 'Ya no te espera: la contestaron en otro lado, o la retiraron. No se mandó nada.' };
                s = { ...s, enviando: false, aviso: undefined };
            } else {
                if (nueva) { e = nueva; c = contestable(e, ahora); }
                s = { ...s, enviando: false, elegidas: c.bloques.map((b, i) => (s.elegidas[i] ?? []).filter(id => b.opciones.some(o => o.id === id))),
                    aviso: { tono: 'falla', texto: nueva ? 'Cambió mientras la mirabas: esto es lo de ahora. No se mandó nada; míralo y vuelve a responder.'
                        : `Cambió mientras la mirabas, y no pude releerla (${r.error}). No se mandó nada.` } };
            }
        } else {
            s = { ...s, enviando: false, aviso: { tono: 'falla', texto: `No se hizo: ${r.error}` } };
        }
        pintar();
    };

    const elegir = (b: number, id: string) => {
        const bloque = c.bloques[b];
        if (!bloque || s.enviando) return;
        const antes = s.elegidas[b] ?? [];
        const elegidas = bloque.varias ? (antes.includes(id) ? antes.filter(x => x !== id) : [...antes, id]) : antes.includes(id) && bloque.opciones.length > 1 ? [] : [id];
        const otras = [...s.otras];
        // en una de una sola, elegir una opción deja de lado lo escrito (queda guardado si se vuelve a «Otra cosa…»)
        if (!bloque.varias && elegidas.length) otras[b] = '';
        s = { ...s, elegidas: s.elegidas.map((x, i) => (i === b ? elegidas : x)), otras, abierta: bloque.varias ? s.abierta : -1, aviso: undefined };
        pintar();
    };

    const montar = (d: HTMLDialogElement, cerrarla: (v?: string) => void) => {
        dialogo = d;
        cerrar = cerrarla;
        crecer();
        d.addEventListener('click', ev => {
            const t = ev.target as HTMLElement;
            const op = t.closest<HTMLElement>('.contestar-op');
            if (op) {
                const b = Number(op.dataset.bloque ?? 0);
                if (op.dataset.otra) {
                    // «Otra cosa…»: se abre (y en una de una sola, deja de lado la opción elegida)
                    if (!c.bloques[b]?.varias) s = { ...s, elegidas: s.elegidas.map((x, i) => (i === b ? [] : x)) };
                    s = { ...s, abierta: b };
                    pintar();
                    d.querySelector<HTMLTextAreaElement>(`.contestar-campo[data-bloque="${b}"]`)?.focus();
                } else elegir(b, op.dataset.op ?? '');
                return;
            }
            const cuando = t.closest<HTMLElement>('[data-agente-cuando]');
            if (cuando && s.agente) { s = { ...s, agente: { ...s.agente, cuando: cuando.dataset.agenteCuando === 'ya' ? 'ya' : 'revision' } }; recordarAgente(); pintar(); return; }
            const a = t.closest<HTMLElement>('[data-contestar]');
            if (!a) return;
            ev.preventDefault();
            switch (a.dataset.contestar) {
                case 'hacer': void mandar(); break;
                case 'tarea': void deLaBarra(Number(a.dataset.valor)); break;
                case 'cancelar': if (!s.enviando) cerrar(); break;
                case 'conversar': cerrar(); hacer.conversar(e, c); break;
                case 'ir': cerrar(); hacer.ir(a.dataset.valor ?? ''); break;
            }
        });
        d.addEventListener('toggle', ev => {
            const det = ev.target as HTMLDetailsElement;
            if (det.classList?.contains('contestar-detalle')) s = { ...s, detalle: det.open };
            if (det.classList?.contains('ficha-mas')) s = { ...s, historia: det.open };
            if (det.classList?.contains('contestar-agente') && s.agente) s = { ...s, agente: { ...s.agente, abierto: det.open } };
        }, true);
        // lo escrito: sin repintar (el foco y el cursor son del campo); solo lo que depende de que haya texto
        d.addEventListener('input', ev => {
            const t = ev.target as HTMLTextAreaElement;
            // lo que se le deja al agente: se guarda sin repintar
            if (t.classList.contains('contestar-agente-campo') && s.agente) {
                s = { ...s, agente: { ...s.agente, [t.dataset.agente === 'meta' ? 'meta' : 'nota']: t.value } };
                recordarAgente();
                crecer();
                pintarPie();
                return;
            }
            if (!t.classList.contains('contestar-campo')) return;
            const b = Number(t.dataset.bloque ?? 0);
            const otras = s.otras.map((x, i) => (i === b ? t.value : x));
            const elegidas = t.value.trim() && !c.bloques[b]?.varias ? s.elegidas.map((x, i) => (i === b ? [] : x)) : s.elegidas;
            const cambiaMarca = !!t.value.trim() !== !!s.otras[b]?.trim() || elegidas !== s.elegidas;
            s = { ...s, otras, elegidas, aviso: undefined };
            recordar();
            if (cambiaMarca) pintar(); else { crecer(); pintarPie(); }
        });
        // ⏎ manda (si está todo); ⇧⏎ es una línea más en lo escrito. Lo que quita (descartar) no se hace con ⏎: su botón
        // dice ⌘⌫ (y la tecla de cada botón, y ⏎ en el que tiene el foco, los atiende web/botonera.ts, antes que esto)
        d.addEventListener('keydown', ev => {
            if (ev.key !== 'Enter' || ev.shiftKey || ev.isComposing || ev.altKey || ev.defaultPrevented) return;
            const t = ev.target as HTMLElement;
            if (t.closest('summary') || (t.closest('.contestar-op') && !ev.metaKey && !ev.ctrlKey)) return;
            ev.preventDefault();
            if (quita(c, s)) return;
            void mandar();
        });
        // a quién le llega lo del agente, si no se sabe quién la propuso: el que escribe los avances (la configuración)
        if (c.agente && !c.agente.a && hacer.agenteGeneral) {
            void hacer.agenteGeneral().then(a => {
                if (!a || !dialogo?.isConnected || !c.agente || c.agente.a) return;
                c = { ...c, agente: { a, propuso: false, general: true } };
                pintar();
            });
        }
        // lo que hace recordar y no vino en la espera (la tarea entera, su proyecto): llega después, y se suma a la ficha
        if (hacer.completar) {
            const sumar = (mas: Record<string, unknown> | undefined) => {
                if (!mas || !dialogo?.isConnected) return;
                e = { ...e, campos: { ...(e.campos ?? {}), ...mas } };
                const otro = contestable(e, ahora);
                if (JSON.stringify([otro.detalle, otro.ficha, otro.barra]) === JSON.stringify([c.detalle, c.ficha, c.barra])) return;
                c = { ...c, detalle: otro.detalle, ficha: otro.ficha, barra: otro.barra };
                pintar();
            };
            void hacer.completar(e, sumar).then(sumar, (err: unknown) => sumar({ tarea_falla: String(err) }));
        }
    };
    /** Solo el botón de abajo (su verbo, si se puede): mientras se escribe, sin repintar el campo. */
    const pintarPie = () => {
        if (!dialogo) return;
        const tmp = document.createElement('div');
        tmp.innerHTML = ventanaContestar(c, s);
        const nuevo = tmp.querySelector('.contestar-pie'), viejo = dialogo.querySelector('.contestar-pie');
        if (nuevo && viejo) viejo.replaceWith(nuevo);
    };

    // el foco: en el campo, si la respuesta es escrita; si no, en la ventana (Tab va a las opciones, ⏎ manda lo elegido)
    const primero = s.abierta >= 0 ? '.contestar-campo' : '.ventana';
    return abrirVentana<string>(propsContestar(c, s), { clase: `contestar-dialogo${c.ficha ? ' con-ficha' : ''}`, foco: primero,
        puedeCerrar: () => !s.enviando && !s.haciendo, montar });
}

/** De mentira: no toca nada, dice qué haría (el catálogo y el ensayo). Con `cambio`, la primera vez que se manda
 *  responde como si hubiera cambiado mientras se miraba (409), y al releer trae la misma con otro resumen. */
export function hacerDeEnsayo(o: { cambio?: boolean; decir?: (texto: string) => void; elegirFecha?: (titulo: string) => Promise<string | undefined>; pausa?: number;
    confirmar?: (c: Confirmacion) => Promise<boolean> } = {}): Hacer {
    let cambio = !!o.cambio;
    /** las pausas de mentira, para que se vea lo que está en curso; `pausa` las escala (0, ninguna: la prueba no espera) */
    const dormir = (ms: number) => new Promise(r => setTimeout(r, ms * (o.pausa ?? 1)));
    const decir = o.decir ?? ((t: string) => { void import('./ui').then(ui => ui.estado(t, 6000)); });
    /** lo cambiado desde la barra en el ensayo, por tarea: la de mentira lo muestra al releerse (solo la fecha) */
    const cambios = new Map<string, { tarea: Partial<cli.JsonTarea> }>();
    return {
        async contestar(e, c, s) {
            await dormir(900);
            if (cambio) { cambio = false; return { ok: false, error: 'cambió desde que se leyó', cambio: true }; }
            const [b] = eleccion(c, s);
            const que = c.clase === 'en-vivo' ? JSON.stringify(respuestasEnVivo(e, c, s)) : b.opciones.length ? b.opciones.join(', ') : `«${b.texto}»`;
            return { ok: true, dice: `(ensayo) contestaría ${e.direccion} con ${que}: no se hizo nada` };
        },
        paraElAgente: true,
        async alAgente(e, c, lineas) {
            await dormir(600);
            const aviso = lineas.some(l => l.startsWith(`${MARCAS_AGENTE.ya}:`)) ? ', con un aviso para que lo atienda ya' : '';
            return { ok: true, dice: `(ensayo) dejaría en ${e.direccion} ${lineas.map(x => `«${x}»`).join(' y ')}, que le llega ${aQuien(c.agente)}${aviso}: no se hizo nada` };
        },
        async releer(e) {
            await dormir(400);
            return { ...e, resumen: `${e.resumen} (cambió: alguien la editó mientras la mirabas)`,
                campos: { ...(e.campos ?? {}), ...(e.campos?.secciones ? { secciones: { ...(e.campos.secciones as object),
                    resumen: `${String((e.campos.secciones as Record<string, string>).resumen ?? '')} **Nuevo:** la feria pidió que salga antes del 1 de diciembre.` } } : {}) } };
        },
        async completar(e, parcial) {
            if (e.tipo !== 'tarea') return undefined;
            // la tarea, al rato; su proyecto y las otras del proyecto, un rato después (como de verdad)
            await dormir(300);
            const m = detallesDeMuestra()[e.direccion.replace(/@[\w-]+$/, '')]
                ?? { tarea: { id: numeroDe(e.direccion), titulo: e.titulo, estado: 'activa', historia: [{ fecha: e.desde.slice(0, 10), tipo: 'creada', texto: 'a mano' }] } };
            const { proyecto, otras, ...leida } = m;
            // lo hecho desde la barra en el ensayo: la tarea de mentira lo muestra, con su línea en la historia; y su
            // propuesta, la de la espera (como en el modelo, mover la fecha no la contesta)
            const t = { avance: String(e.campos?.avance ?? ''), ...leida.tarea, ...cambios.get(e.direccion)?.tarea };
            const tarea = { ...leida, tarea: t };
            parcial?.(tarea);
            await dormir(400);
            return { ...tarea, ficha_tarea: fichaDeMuestra(t), proveedor: 'tareas', ...(proyecto ? { proyecto_ficha: proyecto } : {}), ...(otras ? { otras } : {}) };
        },
        async accionTarea(e, k) {
            const a = (e.campos?.ficha_tarea as cli.JsonPagina | undefined)?.acciones?.[k];
            if (!a) return { ok: false, error: 'todavía no llegan las acciones de la tarea' };
            const antes = { ...(e.campos?.tarea as cli.JsonTarea), ...cambios.get(e.direccion)?.tarea };
            const linea = (tipo: string, texto: string): cli.JsonCambio => ({ fecha: new Date().toLocaleDateString('sv'), hora: new Date().toTimeString().slice(0, 5), tipo, texto });
            // la fecha: la lista de siempre, de verdad (no toca nada); lo demás, dice qué haría
            if (a.rol === 'fecha') {
                const f = await (o.elegirFecha ?? (async (titulo: string) => (await import('../vistas/dashboard/tareas')).elegirFecha(titulo)))(e.titulo);
                if (!f) return undefined;
                await dormir(500);
                cambios.set(e.direccion, { tarea: { vence: f, version: `${antes.version ?? 'v'}+`, historia: [...antes.historia ?? [], linea('mover', `${antes.vence ?? ''} → ${f}`.trim())] } });
                decir(`(ensayo) movería ${e.direccion} al ${f}, por la acción de rol «fecha» de su proveedor: no se hizo nada`);
                return { ok: true, dice: `nueva fecha: ${f}` };
            }
            await dormir(400);
            const dice = `(ensayo) correría «${a.nombre}»: no se hizo nada`;
            cambios.set(e.direccion, { tarea: { ...cambios.get(e.direccion)?.tarea, historia: [...antes.historia ?? [], linea('nota', dice)] } });
            decir(`${dice} en ${e.direccion}`);
            return { ok: true, dice: `(ensayo) ${a.nombre}` };
        },
        conversar(e) { decir(`(ensayo) abriría la instrucción con ${e.direccion} como contexto`); },
        ir(direccion) { decir(`(ensayo) iría a ${direccion}`); },
        // la pregunta de lo que destruye, de verdad (no toca nada): así se ve; la prueba pasa la suya
        confirmar: o.confirmar ?? (p => HACER.confirmar!(p)),
    };
}
