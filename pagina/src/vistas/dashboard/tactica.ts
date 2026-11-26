// «táctica»: la vista de partida del orden por modos (docs/propuestas/orden-por-modos.md, paso 3), con los datos de
// verdad. Es una pestaña más del dashboard, primera en DASHBOARD, y todavía no reemplaza a «ahora», a foco ni a «te
// esperan»: eso, y volverla el modo de partida, lo decide el paso 2. Se dibuja con el componente (componentes/tactica.ts),
// en la disposición que eligió la persona el 17-nov: Ahora arriba y Decidir y Hacer lado a lado.
//
//   Ahora   el bloque en curso, de la agenda cruzada con el plan (eventos.ts): una reunión con su ficha, un bloque del
//           plan con su paso, o lo libre hasta lo próximo y lo que cabe en ello
//   Decidir lo que espera a la persona (`telar esperas`) y le pide decidir, aprobar, confirmar o delegar, por cuenta (el
//           cliente o el proyecto de cada cosa; lo sin cuenta, junto al final), en el orden de la urgencia
//           (urgencia.ts: el peso, si una persona espera, la fecha dura, y el orden de hoy). Cada fila dice lo que hay
//           que decidir, no el título de la tarea. Un clic abre «Contestar» (web/contestar.ts). Arriba, los hilos
//           detenidos en su turno; fuera, los mensajes retenidos entre hilos (plomería: al pie). Al final, lo que
//           contestó y espera al agente (`telar esperas`, `contestadas`: sale de la historia de cada tarea, así que
//           sobrevive a recargar), con la próxima pasada del agente («pulso», PASADA, de `telar periodicos`) y
//           «revisar ya», que se la encarga ahora (web/contestar.ts, `alAgenteDe`, como «hazte cargo ya»)
//   Hacer   la próxima reunión si hay algo que preparar, el próximo bloque estratégico del plan, lo que un agente dice
//           que pide hacer, y las tareas propias que vencen hoy (o vencieron hace 30 días o menos) o que el plan pone
//           hoy, en el orden de la urgencia; cada una con su tamaño
//   el pie  los retenidos y lo que espera a otros (llevan a «te esperan»), las demás pestañas de fuentes (los bloques,
//           los feeds) y cuántas tareas quedan, que llevan a lo suyo
//
// Arriba de las funciones puras (lo que se prueba en npm run prueba:componentes, «táctica en la página»); abajo,
// PantallaTactica, el estado y las acciones.

import * as cli from '../../cli';
import { limpiarMd } from '../../estilo';
import * as ui from '../../web/ui';
import * as mundo from '../../web/mundo';
import * as modos from '../../web/modos';
import { I } from '../../web/iconos';
import { abarca, tramosDe } from '../../web/jornada';
import type { Accion as AccionDeFila, Pieza } from '../../componentes/item';
import { APROBAR, MARCAS_AGENTE, comoCierre } from '../../componentes/contestar';
import type { Inicial } from '../../web/contestar';
import { type Ahora, type Carril, type Clic, type Contestada, type Cuenta, type Decision, type Pasada, type Quehacer, type Resto, type Tactica, SIN_CLASIFICAR, VIAS, VIA_HACER, barraTactica, porDecidir, queCabe, tactica } from '../../componentes/tactica';
import { type Dia, type Pendiente, esMia, pendientes } from './dia';
import { PALABRA, corto, edad } from './esperas';
import { type EventoCal, eventosDelDia } from './eventos';
import { claseDe, queEs } from './clases';
import { accionFecha, piezasTarea, valorDe } from './fila-tarea';
import type { Plan } from './plan';
import { type Declarado, type Pide, MESES, cuando as cuandoDia, declaradoDe, deEspera, dePendiente, delPlan, nivel, ordenar, porque, viaDe } from './urgencia';
import type { Accion, Pantalla, Tablero } from './pantalla';
import { sinCasa, unidadDe } from './unidad';

// ───────────────────────── lo que espera: en sus vías, por cuenta ─────────────────────────

/** Un proyecto como lo da `telar proyectos`: lo que hace falta para saber de qué cuenta es. */
export interface ProyectoDeCuenta { ruta: string; nombre: string; cliente?: string; interno?: boolean }

/** El nombre del grupo de lo que no tiene cuenta (va al final). */
export const SIN_CUENTA = 'sin cuenta';

/** La ruta del proyecto de una espera: su enlace `proyecto:`; si no, el proyecto que contiene un archivo que toca (el
 *  más hondo: una pregunta que vive en la carpeta de un proyecto); si no, el de una tarea que toca (`tareas`: la
 *  dirección de cada tarea del día y su proyecto). Vacío si no tiene. */
export function proyectoDe(e: cli.JsonEspera, proyectos: readonly ProyectoDeCuenta[] = [], tareas: ReadonlyMap<string, string> = new Map()): string {
    const directo = e.enlaces.find(x => x.startsWith('proyecto:'));
    if (directo) return directo.slice('proyecto:'.length).replace(/@[\w-]+$/, '');
    const rutas = e.enlaces.filter(x => x.startsWith('archivo:')).map(x => x.slice('archivo:'.length));
    const dentro = proyectos.filter(p => rutas.some(r => r.startsWith(`${p.ruta}/`))).sort((a, b) => b.ruta.length - a.ruta.length)[0];
    if (dentro) return dentro.ruta;
    return e.enlaces.map(x => tareas.get(x.replace(/@[\w-]+$/, '')) ?? '').find(Boolean) ?? '';
}

/** La cuenta de un proyecto: su cliente, si lo tiene y no es la casa misma (los proyectos de un mismo cliente van
 *  juntos); si no, el proyecto, por su nombre sin el cliente de la casa delante (una iniciativa, un proyecto interno: su
 *  nombre). Una carpeta dentro de una unidad es de esa unidad (la más honda); una que no es de ninguna, el final de su
 *  ruta. Sin proyecto, sin cuenta (clave vacía). */
export function cuentaDe(ruta: string, proyectos: readonly ProyectoDeCuenta[] = []): { clave: string; nombre: string } {
    if (!ruta) return { clave: '', nombre: SIN_CUENTA };
    const dentro = proyectos.find(x => x.ruta === ruta) ? ruta : unidadDe(ruta, proyectos.map(x => x.ruta));
    const p = dentro ? proyectos.find(x => x.ruta === dentro) : undefined;
    if (p?.cliente && !p.interno) return { clave: `cliente:${p.cliente.toLowerCase()}`, nombre: p.cliente };
    return { clave: p?.ruta ?? ruta, nombre: (p && sinCasa(p)) || ruta.split('/').filter(Boolean).pop() || ruta };
}

/** Con mayúscula al principio (después de «¿» o «¡» si los trae). */
const conMayuscula = (t: string): string => t.replace(/^([¿¡«"]*)(\p{Ll})/u, (_, a: string, b: string) => a + b.toUpperCase());

/** El texto de un agente sin la fecha del principio («16-nov 11:00: …»). */
const sinFecha = (t: string): string => t.replace(/^\d{1,2}-[a-zé]{3,5}\.?(?: \d{1,2}:\d{2})?:\s*/i, '');

/** Lo que la persona tiene que decidir, en una línea: lo que el agente dice que falta («· falta: ¿la mandas hoy?»), o
 *  todo su texto sin la fecha del principio; de una pregunta del módulo, su asunto; de un cierre propuesto, la tarea (cómo
 *  y su prueba van aparte); de lo demás (un hilo, un módulo), su título. Sin nada, el título. Lo que ya dice su vía no se
 *  repite: en aprobar, «Aprobar el stand» queda en «el stand», que se lee de corrido con la vía. */
export function pedido(e: cli.JsonEspera, d: Declarado = declaradoDe(e), via: Pide | null = viaDe(e, d)): string {
    const titulo = e.titulo || e.direccion;
    if (e.clase === 'avance:cerrar' || via === 'cerrar' || !e.clase.startsWith('avance:')) return titulo;
    const t = d.resto.replace(/\s+/g, ' ').trim();
    const i = t.toLowerCase().lastIndexOf('falta:');
    const dice = (i >= 0 ? t.slice(i + 'falta:'.length) : sinFecha(t)).trim().replace(/[.;]+$/, '');
    const verbo = via === 'hacer-tu' ? 'hacer' : via;
    if (verbo && dice.toLowerCase().startsWith(`${verbo} `)) return dice.slice(verbo.length + 1).trim() || titulo;
    return dice ? conMayuscula(dice) : titulo;
}

/** Lo que el agente dejó hecho, si su texto lo nombra: el primer enlace (https://…) o la primera ruta de un archivo
 *  (`carpeta/nombre.md`). Lo demás (un borrador en el correo, un id) no se adivina. */
export function artefactoDe(texto: string): Decision['artefacto'] {
    const url = /https?:\/\/[^\s)»"]+/.exec(texto)?.[0];
    if (url) return { nombre: url.replace(/^https?:\/\//, '').replace(/[/?#].*$/, ''), direccion: url.replace(/[.,;]+$/, '') };
    const ruta = /(?:[\w.@-]+\/)+[\w.@-]+\.(?:md|pdf|pptx?|docx?|xlsx?|csv|html|png|jpe?g)\b/i.exec(texto)?.[0];
    return ruta ? { nombre: ruta.split('/').pop()!, direccion: `archivo:${ruta}` } : undefined;
}

/** Lo que declara el agente como hecho, si no tiene la forma de un archivo conocido: una ruta tal cual. */
const enlaceDe = (x: string): Decision['artefacto'] => ({ nombre: x.split('/').filter(Boolean).pop() ?? x, direccion: /^[a-z]+:/.test(x) ? x : `archivo:${x}` });

/** La prueba de un cierre propuesto: lo que dice el agente, sin la fecha y sin lo que pide («falta: confirmar el cierre»). */
export function pruebaDe(texto: string): string {
    const t = texto.replace(/\s+/g, ' ').trim();
    const i = t.toLowerCase().lastIndexOf('falta:');
    // sin «cerrar como hecha:» delante: cómo se cierra ya va en la fila
    return sinFecha(i > 0 ? t.slice(0, i).replace(/[\s·]+$/, '') : t).replace(/^cerrar(?:la)? como (?:hecha|caduca|descartada)\s*:\s*/i, '')
        .replace(/[.;]+$/, '');
}


/** La fecha de una fila de tarea, en Táctica: la de la lista de tareas (fila-tarea.ts, `accionFecha`), atendida como
 *  `tactica-fecha`, que después relee también lo que espera y en un ensayo no toca nada. */
const deTactica = (a: AccionDeFila): AccionDeFila => (a.accion === 'reagendar' ? { ...a, accion: 'tactica-fecha' } : a);

/** Una fila de lo que espera: lo que hay que decidir (no el título: ese va en el globo), su peso si lo declaró, por qué
 *  está donde está, y lo de su vía: de decidir sus opciones (las de una pregunta del módulo), de aprobar lo que dejó
 *  hecho, de lo que pide hacer el tamaño de su tarea (`tamanos`: el de cada tarea del día), de cerrar cómo y su prueba. Un hilo
 *  detenido dice su clase (permiso, pregunta): se contesta en su terminal. De una tarea, además, otra fecha al pasar el
 *  mouse, la de su fila en la lista de tareas (`valores`: lo que lleva la de cada tarea del día; si no está en el día, la
 *  del proveedor de siempre, como abre su dirección la página). */
export function decision(e: cli.JsonEspera, plan: ReadonlySet<string>, ahora = Date.now(), tamanos: ReadonlyMap<string, string> = new Map(),
    valores: ReadonlyMap<string, string> = new Map()): Decision {
    const d = declaradoDe(e);
    const via = viaDe(e, d);
    const vivo = e.clase === 'permiso' || e.clase === 'pregunta';
    const s = deEspera(e, plan, ahora);
    const p = porque(s, ahora);
    const peso = d.peso ? `peso ${d.peso}${d.porque ? `: ${d.porque}` : ''}` : '';
    const texto = (d.resto || e.resumen).replace(/\s+/g, ' ').trim();
    const antes = typeof e.campos?.aplique === 'string' && e.campos.aplique ? `con tu respuesta anterior, apliqué: ${e.campos.aplique}` : '';
    // las opciones: las de una pregunta del módulo (por su id), o las que declara el agente en una tarea (su texto es lo
    // que se contesta)
    const opciones = Array.isArray(e.campos?.opciones) ? (e.campos.opciones as { id?: unknown; texto?: unknown; recomendada?: unknown }[])
        .filter(o => typeof o?.id === 'string' && typeof o?.texto === 'string')
        .map(o => ({ id: String(o.id), texto: String(o.texto), ...o.recomendada ? { recomendada: true } : {} }))
        : (d.opciones ?? []).map(o => ({ id: o.texto, texto: o.texto, ...o.recomendada ? { recomendada: true } : {} }));
    const dir = e.direccion.replace(/@[\w-]+$/, '');
    const tamano = tamanos.get(dir);
    const id = dir.replace(/^tarea:/, '');
    const valor = e.tipo === 'tarea' ? valores.get(dir) ?? JSON.stringify(['tareas', id, id]) : '';
    // lo que dejó hecho: lo que declara (una ruta o un enlace), o lo primero que su texto nombra
    const artefacto = via !== 'aprobar' ? undefined : d.artefacto ? artefactoDe(d.artefacto) ?? enlaceDe(d.artefacto) : artefactoDe(texto);
    return {
        id: e.direccion, titulo: pedido(e, d, via), maquina: e.maquina,
        ...vivo ? { palabra: PALABRA[e.clase][0], tono: PALABRA[e.clase][1] } : {},
        porque: p ? { texto: p.texto, tono: p.tono } : undefined, edad: s.espera ? edad(e.desde, ahora) : '',
        ...d.peso ? { peso: { nivel: d.peso, porque: d.porque ?? '' } } : {},
        ayuda: [e.titulo, peso, texto, antes, e.direccion].filter(Boolean).join('\n\n'),
        ...opciones.length ? { opciones } : {},
        ...artefacto ? { artefacto } : {},
        ...via === 'hacer-tu' && (tamano === 'rapida' || tamano === 'larga') ? { tamano } : {},
        ...via === 'cerrar' ? { como: comoCierre(e), prueba: pruebaDe(texto) } : {},
        ...valor ? { acciones: [deTactica(accionFecha(valor, !e.campos?.vence))] } : {},
    };
}

/** Lo que espera, repartido: las tres vías y lo sin clasificar (`vias`, cada una por cuenta), lo que pide hacer (`hacerTu`:
 *  va primero en Hacer), y lo que no va en ellas:
 *  los hilos detenidos (`vivo`: arriba, sin cuenta) y los mensajes retenidos entre hilos (plomería: una línea al pie). */
export interface Reparto {
    vias: Carril[];
    /** lo que pide hacer (`pide=hacer-tu`): va primero en Hacer, por cuenta */
    hacerTu: Cuenta[];
    vivo: Decision[];
    retenidos: number;
    /** lo que contesta un clic: cada espera por su dirección, las de una cuenta por `cuenta:<vía>|<cuenta>` y las de una
     *  vía por `via:<vía>`, en su orden */
    grupos: Map<string, cli.JsonEspera[]>;
}

/** Lo que espera, en el orden de la urgencia (sin la deuda) y repartido: cada espera en su vía (la que declara el agente;
 *  sin declarar, sin clasificar: urgencia.ts, `viaDe`), y en su vía por cuenta, cada cuenta en el lugar de la más urgente
 *  de las suyas, con ella primero; lo que no tiene cuenta, junto al final. */
export function decisiones(esperas: readonly cli.JsonEspera[], plan: ReadonlySet<string>, ahora = Date.now(),
    proyectos: readonly ProyectoDeCuenta[] = [], tareas: ReadonlyMap<string, string> = new Map(), tamanos: ReadonlyMap<string, string> = new Map(),
    valores: ReadonlyMap<string, string> = new Map()): Reparto {
    const vias: Carril[] = [...VIAS.map(v => ({ clave: v.clave, cuentas: [] as Cuenta[] })), { clave: SIN_CLASIFICAR, cuentas: [] }];
    const deHacer: Carril = { clave: VIA_HACER.clave, cuentas: [] };
    const r: Reparto = { vias, hacerTu: deHacer.cuentas, vivo: [], retenidos: 0, grupos: new Map() };
    const sumar = (k: string, e: cli.JsonEspera) => r.grupos.set(k, [...r.grupos.get(k) ?? [], e]);
    const porClave = new Map<string, Cuenta>();
    for (const e of ordenar(esperas, x => deEspera(x, plan, ahora))) {
        if (e.clase === 'retenido') { r.retenidos++; continue; }
        r.grupos.set(e.direccion, [e]);
        if (e.clase === 'permiso' || e.clase === 'pregunta') { r.vivo.push(decision(e, plan, ahora)); continue; }
        const via = viaDe(e) ?? SIN_CLASIFICAR;
        const carril = via === VIA_HACER.clave ? deHacer : vias.find(v => v.clave === via)!;
        const c = cuentaDe(proyectoDe(e, proyectos, tareas), proyectos);
        const k = `${via}|${c.clave}`;
        let cuenta = porClave.get(k);
        if (!cuenta) { cuenta = { ...c, decisiones: [] }; porClave.set(k, cuenta); carril.cuentas.push(cuenta); }
        cuenta.decisiones.push(decision(e, plan, ahora, tamanos, valores));
        sumar(`cuenta:${k}`, e);
    }
    // lo que no tiene cuenta, junto al final de su vía; y la vía se recorre como se ve, cuenta por cuenta
    for (const v of [...vias, deHacer]) {
        v.cuentas.sort((a, b) => Number(!a.clave) - Number(!b.clave));
        const todas = v.cuentas.flatMap(c => r.grupos.get(`cuenta:${v.clave}|${c.clave}`) ?? []);
        if (todas.length) r.grupos.set(`via:${v.clave}`, todas);
    }
    return r;
}

// ───────────────────────── lo contestado: espera al agente ─────────────────────────

const hm = (ms: number): string => new Date(ms).toTimeString().slice(0, 5);

/** Cuántos días de esta máquina hay entre dos instantes (de medianoche a medianoche): 0 el mismo día. */
const diasEntre = (desde: number, hasta: number): number =>
    Math.round((new Date(hasta).setHours(0, 0, 0, 0) - new Date(desde).setHours(0, 0, 0, 0)) / 86400000);

/** El periódico que pasa por las tareas y retoma lo contestado primero (`telar periodicos`): «pulso», que desde el 18-nov
 *  reemplaza a /avanzar. Cuentan el que se llama así y los que piden la skill (`mensaje = "/pulso …"`, como «pulso-noche»).
 *  Si no hay ninguno, el de antes: RESPALDO. */
export const PASADA = 'pulso';
export const RESPALDO = 'avanzar';

/** Lo que deja «revisar ya» en la tarea (una [respuesta] más, como «hazte cargo ya»: un prompt) y lo que le llega al agente,
 *  con la dirección de la tarea delante. telar.objetos la reconoce (`_REVISAR_YA`): no es algo que se contestó, solo dice
 *  cuándo se le encargó. */
export const REVISAR_YA = `${MARCAS_AGENTE.ya}: revisar ya: te contesté; atiéndela ahora, sin esperar la próxima pasada`;

/** Una hora de esta máquina (`2026-11-18T18:27:00`, o solo la fecha) dicha desde hoy: «18:27», «ayer 18:27», «14-nov». */
export function horaDesde(iso: string, ahora = Date.now()): string {
    const solo = iso.length === 10;
    const t = iso ? Date.parse(solo ? `${iso}T00:00:00` : iso) : NaN;
    if (Number.isNaN(t)) return '';
    const dias = diasEntre(t, ahora);
    if (dias === 0) return solo ? 'hoy' : hm(t);
    if (dias === 1) return solo ? 'ayer' : `ayer ${hm(t)}`;
    const d = new Date(t);
    return `${d.getDate()}-${MESES[d.getMonth()]}`;
}

/** Lo que pasa con un «revisar ya» mientras dura la página (lo que la tarea todavía no dice): en camino, hecho a tal hora,
 *  o que no salió (y por qué). `para`: el `cuando` de la contestada que se encargó (si se contesta de nuevo, ya no vale);
 *  `hecho`: lo que ya salió, para que un reintento no lo repita (web/contestar.ts, `alAgenteDe`). */
export interface Encargo { estado: 'enviando' | 'hecho' | 'fallo'; para: string; hora?: string; error?: string; hecho: { lineas: number; mensaje: boolean } }

/** Las contestadas como las muestra Táctica, lo más reciente primero: la tarea, lo que contestó y cuándo, y si se la
 *  encargó (lo dice la tarea: su último «prompt: …»; o, recién, `encargos`). Un «revisar ya» que no salió se puede
 *  volver a apretar aunque la línea haya quedado en la tarea. */
export function contestadasDe(cs: readonly cli.JsonContestada[], ahora = Date.now(), encargos: ReadonlyMap<string, Encargo> = new Map()): Contestada[] {
    return [...cs].sort((a, b) => (b.cuando || '').localeCompare(a.cuando || '') || a.direccion.localeCompare(b.direccion)).map(c => {
        const e = encargos.get(c.direccion);
        const local = e?.para === c.cuando ? e : undefined;
        const cuando = horaDesde(c.cuando, ahora);
        const encargada = (c.encargada ? horaDesde(c.encargada, ahora) : '') || (local?.estado === 'hecho' ? local.hora ?? '' : '');
        const titulo = limpiarMd(c.titulo) || c.direccion;
        return {
            id: c.direccion, titulo, respuesta: c.respuesta, cuando,
            ...local?.estado === 'enviando' ? { encargando: true } : local?.estado === 'fallo' ? { fallo: local.error || 'no se sabe por qué' }
                : encargada ? { encargada } : {},
            ayuda: [titulo, `contestaste${cuando ? ` (${cuando})` : ''}: ${c.respuesta || '—'}`,
                encargada ? `se la encargaste al agente: ${encargada}` : '', c.direccion].filter(Boolean).join('\n\n'),
        };
    });
}

/** Si un periódico es de la pasada `skill`: se llama así o la pide (`/pulso`, `/pulso noche --seco`). */
const esDe = (p: cli.JsonPeriodico, skill: string): boolean => p.nombre === skill || new RegExp(`^/${skill}(\\s|$)`).test(p.mensaje ?? '');

/** El periódico de la pasada entre los de `telar periodicos`: de los de PASADA (o, sin ninguno, de RESPALDO), el que está
 *  corriendo; si no, el activo que corre antes (así «pulso-noche» cuenta solo cuando es la próxima: de noche, después del
 *  último de «pulso»); si ninguno está activo, el que se llama como la skill (o el primero), que dirá «pausada». */
export function procesoDePasada(ps: readonly cli.JsonPeriodico[]): cli.JsonPeriodico | undefined {
    for (const skill of [PASADA, RESPALDO]) {
        const de = ps.filter(p => esDe(p, skill));
        if (!de.length) continue;
        const cuando = (p: cli.JsonPeriodico) => Date.parse(p.proxima ?? '');
        return de.find(p => p.ultima?.corriendo)
            ?? de.filter(p => p.activo && !Number.isNaN(cuando(p))).sort((a, b) => cuando(a) - cuando(b))[0]
            ?? de.find(p => p.activo) ?? de.find(p => p.nombre === skill) ?? de[0];
    }
    return undefined;
}

/** Cuándo pasa el agente por lo contestado: la próxima corrida del periódico de la pasada, como la calcula `telar
 *  periodicos` donde viven (en la hora de esta máquina): «próxima pasada 15:00», «… mañana 07:00», «… el lun 07:00».
 *  Corriendo, «pasando ahora»; pausado o sin ese periódico, lo dice como un cuidado (nadie va a pasar); si no se pudo leer
 *  desde aquí, que no se sabe y por qué. Sin leer todavía, nada. */
export function pasadaDe(p: cli.JsonPeriodicos | { error: string } | undefined, ahora = Date.now()): Pasada | undefined {
    if (!p) return undefined;
    if ('error' in p) return { texto: 'próxima pasada: no se sabe', ayuda: `no pude leer los periódicos desde aquí, así que no sé cuándo pasa el agente: ${p.error}` };
    const proc = procesoDePasada(p.procesos ?? []);
    const donde = p.maquina ? ` (en ${p.maquina})` : '';
    if (!proc) return { texto: 'sin pasada', tono: 'atencion', ayuda: `ningún periódico${donde} pasa por las tareas: falta «${PASADA}» (o «${RESPALDO}») en telar periodicos. Solo «revisar ya» se las lleva al agente` };
    if (proc.ultima?.corriendo) {
        const desde = Date.parse(proc.ultima.inicio ?? '');
        return { texto: 'pasando ahora', tono: 'agente', ayuda: `«${proc.nombre}»${donde} está corriendo${Number.isNaN(desde) ? '' : ` desde las ${hm(desde)}`}: puede que ya vaya por ellas` };
    }
    if (!proc.activo) return { texto: 'pasada pausada', tono: 'atencion', ayuda: `«${proc.nombre}»${donde} está pausado: nadie pasa por ellas hasta que se active (telar periodicos). «revisar ya» sí se las lleva al agente` };
    const t = Date.parse(proc.proxima ?? '');
    if (Number.isNaN(t)) return { texto: 'próxima pasada: no se sabe', ayuda: `«${proc.nombre}»${donde} no dice cuándo corre de nuevo (${proc.cuando})` };
    const dias = diasEntre(ahora, t);
    const cuando = dias <= 0 ? hm(t) : `${cuandoDia(dias, ahora)} ${hm(t)}`;
    return { texto: `próxima pasada ${cuando}`, ayuda: `la próxima vez que corre «${proc.nombre}»${donde}, con el horario ${proc.cuando}: ${cuando}. `
        + 'Retoma lo contestado primero; «revisar ya» no la espera' };
}

/** Cuándo vuelve a corresponder leer la pasada: ya pasó la que se sabía, o lo leído tiene un rato (un periódico se cambia
 *  poco). Sin nada leído, sí. */
export function pasadaVieja(p: cli.JsonPeriodicos | { error: string } | undefined, leida: number, ahora = Date.now()): boolean {
    if (!p || !leida) return true;
    if (ahora - leida < RELEER_PASADA_MIN) return false;
    if (ahora - leida > RELEER_PASADA) return true;
    const proc = 'error' in p ? undefined : procesoDePasada(p.procesos ?? []);
    const t = Date.parse(proc?.proxima ?? '');
    return !!proc?.ultima?.corriendo || (!Number.isNaN(t) && ahora >= t);
}
/** Lo leído de los periódicos se relee pasado esto, o al pasar la hora que se sabía (pero no antes de un minuto). */
const RELEER_PASADA = 15 * 60 * 1000;
const RELEER_PASADA_MIN = 60 * 1000;

// ───────────────────────── Hacer: lo de hoy ─────────────────────────

/** Lo que pide una reunión antes, según el plan y la invitación, en pocas letras (va al final de su fila, que es
 *  angosta): responderla si no se ha respondido, lo que hay que llevar, o prepararla si en ella se decide algo. Vacío si
 *  nada: entonces no ocupa un lugar en Hacer. El detalle, en `queSePrepara`. */
export function porPreparar(e: EventoCal): string {
    if (e.respuesta === 'sin_responder') return 'responderla';
    const f = (e.plan?.ficha ?? {}) as Plan;
    if (Array.isArray(f.llevar) && f.llevar.length) return f.llevar.length === 1 ? 'llevar 1 cosa' : `llevar ${f.llevar.length} cosas`;
    if (f.decision) return 'prepararla';
    return '';
}

/** Lo que dice el plan de una reunión, entero (el globo de su fila): lo que se decide y lo que hay que llevar. */
function queSePrepara(e: EventoCal): string {
    const f = (e.plan?.ficha ?? {}) as Plan;
    return [f.decision ? `se decide: ${String(f.decision)}` : '', Array.isArray(f.llevar) && f.llevar.length ? `llevar: ${f.llevar.map(String).join(', ')}` : '',
        e.respuesta === 'sin_responder' ? 'la invitación está sin responder' : ''].filter(Boolean).join('\n');
}

/** Lo que va arriba de un evento en Hacer, y lo que hace un clic en él: prepararla (`reunion`, como «ahora»). */
const valorReunion = (e: EventoCal): string => JSON.stringify([e.titulo, hm(e.inicio), e.url, e.id, e.asistentes]);

/** Hacer: la próxima reunión (solo si hay algo que preparar), el próximo bloque estratégico del plan, y las tareas
 *  propias que vencen hoy o que el plan pone hoy, en el orden de la urgencia. Fuera: lo que espera a la persona
 *  (`enEsperas`: las tareas con algo de un agente van a sus vías) y lo de otras personas. `resto`: las que quedaron fuera,
 *  para contarlas en el pie. */
export function quehaceres(d: Dia, evs: readonly EventoCal[], plan: Plan | undefined, refs: ReadonlySet<string>, ahora = Date.now(),
    enEsperas: ReadonlySet<string> = new Set()): { lista: Quehacer[]; resto: number } {
    const vale = evs.filter(e => !queEs(e).rechazada);
    const lista: Quehacer[] = [];
    const reunion = vale.find(e => e.inicio > ahora && queEs(e).tipo === 'cita');
    const pide = reunion ? porPreparar(reunion) : '';
    if (reunion && pide) lista.push({ tipo: 'reunion', id: reunion.id, titulo: reunion.titulo, hora: hm(reunion.inicio), nota: pide,
        ayuda: `${reunion.titulo}\n${queSePrepara(reunion)}\n\nclic: prepararla con el agente de su proyecto`, clic: { accion: 'reunion', valor: valorReunion(reunion) } });
    const bloque = vale.find(e => e.inicio > ahora && claseDe(e) === 'estrategico');
    const paso = String((plan?.foco as Plan | undefined)?.paso ?? '');
    if (bloque) lista.push({ tipo: 'bloque', id: bloque.id, titulo: bloque.titulo, hora: hm(bloque.inicio), nota: 'el foco del día',
        ayuda: `${bloque.titulo}${paso ? `\nel paso: ${paso}` : ''}`, clic: { accion: 'ahora' } });
    const propias = pendientes(d).filter(p => !p.avance && esMia(p.fila.dueno ?? '') && !enEsperas.has(p.fila.direccion ?? `tarea:${p.ref}`));
    const deHoy = ordenar(propias.filter(p => { const n = nivel(dePendiente(p, refs)); return n === 'hoy' || n === 'plan'; }), p => dePendiente(p, refs));
    for (const p of deHoy) lista.push(quehacerDe(p, refs, ahora));
    return { lista, resto: propias.length - deHoy.length };
}

const tamanoDe = (t: string | undefined): Quehacer['tamano'] => (t === 'rapida' || t === 'larga' ? t : '');

/** Una tarea en Hacer: lo de su fila de siempre (fila-tarea.ts: abrir su ficha o llevarla a su hilo, otra fecha, la
 *  instrucción, hecha y su ⋯), su proyecto, su tamaño y por qué está ahí. */
function quehacerDe(p: Pendiente, refs: ReadonlySet<string>, ahora: number): Quehacer {
    const f = p.fila;
    const { valor, acciones, menu } = piezasTarea(p);
    const pq = porque(dePendiente(p, refs), ahora);
    return {
        tipo: 'tarea', id: f.direccion ?? `tarea:${p.ref}`, titulo: limpiarMd(p.texto),
        donde: (f.proyecto ?? '').split('/').filter(Boolean).pop() || p.hilo,
        tamano: tamanoDe(f.tamano),
        porque: pq ? { texto: pq.texto, tono: pq.tono } : undefined,
        clic: f.ficha ? { accion: 'tarea', valor } : { accion: 'pendiente', valor: p.ref },
        acciones: acciones.filter(a => a.accion === 'reagendar' || a.accion === 'instruccion-fila' || a.accion.startsWith('hecha')).map(deTactica), menu,
    };
}

// ───────────────────────── Ahora: el bloque en curso ─────────────────────────

/** Ahora: la reunión en curso (con lo que dice el plan de ella), el bloque del plan en curso, o lo libre hasta lo
 *  próximo (una reserva es tiempo libre) y lo que cabe en ello (`decidir`: cuántas decisiones esperan); sin nada más en
 *  el día, libre hasta el fin de la jornada (`hasta`, en ms). */
export function ahoraDe(evs: readonly EventoCal[], ahora: number, hasta: number, plan: Plan | undefined, decidir: number, hacer: Quehacer[]): Ahora {
    const vale = evs.filter(e => !queEs(e).rechazada);
    const en = vale.filter(e => e.inicio <= ahora && ahora < e.fin);
    const min = (ms: number) => Math.max(0, Math.round(ms / 60000));
    const reunion = en.find(e => queEs(e).tipo === 'cita');
    if (reunion) {
        const p = (reunion.plan ?? {}) as Plan, f = (p.ficha ?? {}) as Plan;
        const datos: Pieza[] = [];
        if (Array.isArray(f.llevar) && f.llevar.length) datos.push({ texto: `llevar: ${f.llevar.map(String).join(', ')}`, tono: 'atencion' });
        if (reunion.asistentes.length) datos.push({ texto: `${reunion.asistentes.length} ${reunion.asistentes.length === 1 ? 'persona' : 'personas'}` });
        if (reunion.respuesta === 'tentativa' || reunion.respuesta === 'sin_responder') datos.push({ texto: reunion.respuesta.replace('_', ' '), tono: 'atencion' });
        const acciones: AccionDeFila[] = [];
        if (reunion.url) acciones.push({ accion: 'tactica-entrar', datos: { url: reunion.url }, icono: I.externo, tono: 'acento', ayuda: 'entrar a la llamada' });
        acciones.push({ accion: 'reunion', datos: { valor: valorReunion(reunion) }, icono: I.ficha, ayuda: 'prepararla o procesar la minuta (con el agente de su proyecto)' });
        return { tipo: 'reunion', titulo: reunion.titulo, cuando: `${hm(reunion.inicio)}–${hm(reunion.fin)}`, queda: min(reunion.fin - ahora),
            que: f.decision ? `se decide: ${String(f.decision)}` : String(p.nota ?? f.nota ?? ''), datos, acciones,
            clic: { accion: 'ahora' } };
    }
    const bloque = en.find(e => claseDe(e) !== 'reserva');
    if (bloque) {
        const p = (bloque.plan ?? {}) as Plan, foco = (plan?.foco ?? {}) as Plan;
        const estrategico = claseDe(bloque) === 'estrategico';
        const que = estrategico && foco.paso ? `el paso: ${String(foco.paso)}` : String(p.nota ?? p.accion ?? '');
        const datos: Pieza[] = [];
        if (estrategico && foco.terminado) datos.push({ texto: `terminado si: ${String(foco.terminado)}` });
        if (Array.isArray(p.tareas) && p.tareas.length) datos.push({ texto: `${p.tareas.length} ${p.tareas.length === 1 ? 'tarea' : 'tareas'} del bloque`, tono: 'acento' });
        return { tipo: 'bloque', titulo: bloque.titulo, cuando: `${hm(bloque.inicio)}–${hm(bloque.fin)}`, queda: min(bloque.fin - ahora), que, datos,
            clic: { accion: 'ahora' } };
    }
    const sig = vale.find(e => e.inicio > ahora && claseDe(e) !== 'reserva');
    const libre = sig ? min(sig.inicio - ahora) : min(hasta - ahora);
    return { tipo: sig ? 'libre' : 'fin', queda: libre, luego: sig ? `${hm(sig.inicio)} ${sig.titulo}` : undefined, caben: queCabe(libre, decidir, hacer),
        clic: { accion: 'ahora' } };
}

// ───────────────────────── todo lo demás ─────────────────────────

/** Una pestaña del dashboard, como la da el núcleo (`Dashboard.pestanas`). */
export interface PestanaDeTactica { clave: string; accion: string; valor: string; nombre: string; aviso: string }

/** El pie: los mensajes retenidos entre hilos (no son de la persona: llevan a «te esperan», donde se sueltan), cuántas
 *  tareas quedan fuera (llevan a la lista), y cada fuente (un bloque, un feed) con lo que dice de sí. */
export function resto(tareas: number, pestanas: readonly PestanaDeTactica[], retenidos = 0): Resto[] {
    const fuentes = pestanas.filter(p => /^(bloque|pestana):/.test(p.clave)).map(p => ({
        clave: p.clave, nombre: p.nombre, texto: p.aviso ? `${p.nombre}: ${p.aviso}` : p.nombre, clic: { accion: p.accion, valor: p.valor } }));
    return [
        ...retenidos ? [{ clave: 'retenidos', nombre: retenidos === 1 ? 'mensaje entre hilos retenido' : 'mensajes entre hilos retenidos', cuenta: retenidos,
            clic: { accion: 'tactica-todo', valor: 'esperas' } }] : [],
        { clave: 'tareas', nombre: tareas === 1 ? 'tarea más' : 'tareas más', cuenta: tareas, clic: { accion: 'revisar' } }, ...fuentes];
}

// ───────────────────────── todo junto ─────────────────────────

/** Lo que hace falta para armar Táctica: el día (`telar hoy`), el plan de hoy, lo que espera, la hora, las pestañas
 *  del dashboard (para el pie), los proyectos (para nombrar las cuentas: `telar proyectos`), las cuentas que se
 *  desplegaron y lo contestado. Lo da la pantalla con lo de verdad, y el catálogo y el ensayo con lo de mentira. */
export interface DatosTactica {
    dia: Dia;
    plan?: Plan;
    esperas: readonly cli.JsonEspera[];
    ahora: number;
    pestanas: readonly PestanaDeTactica[];
    proyectos?: readonly ProyectoDeCuenta[];
    abiertas?: readonly string[];
    /** lo que contestó y espera al agente (`telar esperas`, `contestadas`), lo de cada «revisar ya» de aquí, los
     *  periódicos (para la próxima pasada; o por qué no se pudieron leer) y el agente que escribe los avances */
    contestadas?: readonly cli.JsonContestada[];
    encargos?: ReadonlyMap<string, Encargo>;
    periodicos?: cli.JsonPeriodicos | { error: string };
    agente?: string;
}

/** Táctica armada (lo que dibuja componentes/tactica.ts) y lo que contesta un clic (cada espera por su dirección, las de
 *  una cuenta por `cuenta:<vía>|<cuenta>`, las de una vía por `via:<vía>`). */
export function armar(o: DatosTactica): { tactica: Tactica; grupos: Map<string, cli.JsonEspera[]> } {
    const refs = delPlan(o.plan);
    // de cada tarea del día: su proyecto (el de una pregunta que la toca) y su tamaño (el de hacer tú)
    const tareas = new Map(o.dia.pendientes.filter(f => f.proyecto && f.direccion).map(f => [f.direccion!, f.proyecto!]));
    const tamanos = new Map(o.dia.pendientes.filter(f => f.tamano && f.direccion).map(f => [f.direccion!, f.tamano!]));
    // y lo que lleva la fecha de su fila, para las que esperan
    const valores = new Map(pendientes(o.dia).filter(p => p.fila.ficha && p.fila.direccion).map(p => [p.fila.direccion!, valorDe(p)]));
    const r = decisiones(o.esperas, refs, o.ahora, o.proyectos, tareas, tamanos, valores);
    const evs = eventosDelDia(o.dia, o.plan);
    const { lista: hacer, resto: quedan } = quehaceres(o.dia, evs, o.plan, refs, o.ahora, new Set(o.esperas.map(e => e.direccion)));
    const medianoche = new Date(o.ahora).setHours(0, 0, 0, 0);
    const fin = medianoche + abarca(tramosDe(o.dia, medianoche)).hasta * 60000;
    return {
        tactica: { ahora: ahoraDe(evs, o.ahora, fin, o.plan, porDecidir(r.vias, r.vivo), hacer), vias: r.vias, hacerTu: r.hacerTu, vivo: r.vivo, hacer,
            sinPlan: !o.plan, resto: resto(quedan, o.pestanas, r.retenidos), disposicion: 'lado', abiertas: o.abiertas,
            contestadas: contestadasDe(o.contestadas ?? [], o.ahora, o.encargos), pasada: pasadaDe(o.periodicos, o.ahora), agente: o.agente },
        grupos: r.grupos,
    };
}

// ───────────────────────── el ensayo ─────────────────────────

/** Lo que una fila de Táctica puede llevar en un ensayo (`window.telar.ensayoTactica`): lo que la pantalla atiende sin tocar
 *  la API que escribe. Contestar, de mentira (web/contestar.ts, `hacerDeEnsayo`: una fila, una vía, lo de bajo una fila);
 *  desplegar una cuenta; la fecha (la lista de siempre, y dice qué haría); decir qué haría (`tactica-ensayo`, `tactica-ver`);
 *  salir a lo de verdad (Todo); y las de fábrica que la página no atiende (las del catálogo). Las tareas de un
 *  ensayo son de mentira y sus números pueden ser los de tareas de verdad: lo demás que lleva una fila va, en un ensayo,
 *  como `tactica-ensayo` (`deEnsayo`). La prueba (npm run prueba:componentes) falla si una acción de un ensayo no está aquí. */
export const DE_ENSAYO: ReadonlySet<string> = new Set([
    'tactica-contestar', 'tactica-via', 'tactica-opcion', 'tactica-aprobar', 'tactica-cerrar', 'tactica-cuenta', 'tactica-fecha',
    'tactica-ver', 'tactica-ensayo', 'tactica-todo',
    'tactica-tarea', 'tactica-hecha', 'tactica-evento', 'tactica-ahora', 'tactica-franja', 'tactica-revisar',
]);

/** Táctica para un ensayo: cada acción de una fila que no es de Táctica (marcar hecha, la instrucción, el ⋯, abrir su ficha,
 *  llevarla a su hilo, preparar la reunión, entrar a la llamada) pasa a `tactica-ensayo`, con lo que habría hecho en su
 *  valor: un clic dice «ensayo: no se hizo nada». */
export function deEnsayo(t: Tactica): Tactica {
    const accion = (a: AccionDeFila): AccionDeFila => (DE_ENSAYO.has(a.accion) ? a
        : { ...a, accion: 'tactica-ensayo', datos: { valor: JSON.stringify([a.accion, a.datos?.valor ?? a.datos?.url ?? '']) } });
    const clic = (c: Clic | undefined): Clic | undefined => (!c || DE_ENSAYO.has(c.accion) ? c
        : { accion: 'tactica-ensayo', valor: JSON.stringify([c.accion, c.valor ?? '']) });
    const decision = (d: Decision): Decision => (d.acciones ? { ...d, acciones: d.acciones.map(accion) } : d);
    const cuentas = (cs: Cuenta[]): Cuenta[] => cs.map(c => ({ ...c, decisiones: c.decisiones.map(decision) }));
    return {
        ...t,
        ahora: { ...t.ahora, clic: clic(t.ahora.clic), ...t.ahora.acciones ? { acciones: t.ahora.acciones.map(accion) } : {} },
        vias: t.vias.map(v => ({ ...v, cuentas: cuentas(v.cuentas) })),
        ...t.hacerTu ? { hacerTu: cuentas(t.hacerTu) } : {},
        ...t.vivo ? { vivo: t.vivo.map(decision) } : {},
        hacer: t.hacer.map(q => ({ ...q, clic: clic(q.clic), ...q.acciones ? { acciones: q.acciones.map(accion) } : {}, ...q.menu ? { menu: accion(q.menu) } : {} })),
        resto: t.resto.map(r => ({ ...r, clic: clic(r.clic) })),
    };
}

/** Lo que habría hecho una acción en un ensayo, en palabras. */
const HARIA: Record<string, string> = {
    'hecha-fila': 'marcarla hecha', 'hecha-vineta': 'marcarla hecha en su documento', 'instruccion-fila': 'la instrucción',
    'menu-tarea': 'sus acciones (el ⋯)', 'menu-vineta': 'sus acciones (el ⋯)', tarea: 'abrir su ficha', pendiente: 'llevarla a su hilo',
    reunion: 'prepararla con el agente de su proyecto', ahora: 'ir a «ahora»', 'tactica-entrar': 'entrar a la llamada',
    revisar: 'ir a la lista de tareas', bloque: 'ir a esa pestaña', pestana: 'ir a esa pestaña',
};

// ───────────────────────── la pantalla ─────────────────────────

/** Un valor que es una lista en JSON (`["tarea:T1","enviar"]`): la dirección de lo que se contesta y qué. */
const lista = (v: string): string[] => {
    try { const x: unknown = JSON.parse(v); return Array.isArray(x) ? x.map(String) : []; } catch { return []; }
};

/** Cada cuánto se releen las esperas mientras se ve (el número de «te esperan» las lee aparte, se vea o no). */
const RELEER_ESPERAS = 90 * 1000;

export class PantallaTactica implements Pantalla {
    readonly pantallas = ['tactica'] as const;
    /** con el reloj: lo de ahora y lo libre cambian solos */
    readonly conReloj = ['tactica'] as const;
    private lista?: cli.JsonEspera[];
    private leida = 0;
    private leyendo?: Promise<void>;
    /** lo que contesta un clic: cada espera por su dirección, y las de una cuenta (`cuenta:<clave>`) una tras otra */
    private grupos = new Map<string, cli.JsonEspera[]>();
    /** un ensayo (`window.telar.ensayoTactica`): un día de mentira en vez del de verdad, y «Contestar» sin contestar nada */
    private muestra?: DatosTactica;
    /** los proyectos, para nombrar las cuentas (se leen una vez: cambian poco) */
    private proyectos?: ProyectoDeCuenta[];
    /** las cuentas que se desplegaron (`<vía>|<cuenta>`, mientras dura la página) */
    private abiertas = new Set<string>();
    /** lo contestado que espera al agente, como llegó con lo que espera */
    private contestadas: cli.JsonContestada[] = [];
    /** cada «revisar ya» de aquí, por tarea (en un ensayo, aparte: sus números pueden ser los de tareas de verdad) */
    private encargos = new Map<string, Encargo>();
    private encargosEnsayo = new Map<string, Encargo>();
    /** los periódicos, para la próxima pasada (o por qué no se pudieron leer), y cuándo se leyeron */
    private periodicos?: cli.JsonPeriodicos | { error: string };
    private pasadaLeida = 0;
    private leyendoPasada?: Promise<void>;
    /** el agente que escribe los avances (a quién le llega «revisar ya»), de la configuración */
    private agente = '';

    readonly acciones: Record<string, Accion> = {
        tactica: () => this.abrir(),
        'tactica-contestar': v => v && this.contestar(v),
        // recorrer una vía en «Contestar» (su cabecera, o su tecla)
        'tactica-via': v => v && this.contestar(`via:${v}`),
        // lo que va bajo una fila (una opción, enviar/editar/descartar, confirmar un cierre): abre «Contestar» con eso
        // elegido, y un clic más lo manda (como siempre: uno elige, el otro responde)
        'tactica-opcion': v => { const [id, opcion] = lista(v); return this.contestar(id, { opcion }); },
        'tactica-aprobar': v => {
            const [id, que] = lista(v);
            return this.contestar(id, que === 'editar' ? { otra: true } : { opcion: que === 'descartar' ? APROBAR.descartar : APROBAR.enviar });
        },
        'tactica-cerrar': v => v && this.contestar(v, { opcion: 'cerrar' }),
        'tactica-ver': v => (this.muestra ? ui.estado(`ensayo: no se hizo nada (abriría ${v} donde vive)`, 6000)
            : v && /^https?:\/\//.test(v) ? ui.abrirExterno(v) : v && ui.abrirDireccion(v)),
        // lo que en un ensayo no se hace (deEnsayo): solo se dice
        'tactica-ensayo': v => {
            const [que, valor] = lista(v);
            const id = /"([A-Za-z]+\d+)"/.exec(valor)?.[1] ?? (valor.length < 60 ? valor : '');
            ui.estado(`ensayo: no se hizo nada (${HARIA[que] ?? que}${id ? ` · ${id}` : ''})`, 6000);
        },
        // «ver todo», al modo todo (todo.ts); «+N más» de una vía y los retenidos del pie, «te esperan» entera; el de Hacer,
        // la lista de tareas
        'tactica-todo': v => (v === 'decidir' || v === 'esperas' ? this.t.accion('esperas') : v ? this.t.accion('revisar') : modos.cambiar('todo')),
        // desplegar o plegar una cuenta de una vía
        'tactica-cuenta': v => { if (this.abiertas.has(v)) this.abiertas.delete(v); else this.abiertas.add(v); this.pintar(); },
        'tactica-releer': () => this.releer(),
        // la fecha de una fila de tarea (en las vías y en Hacer): la de la lista de tareas (tareas.ts), y después se relee
        // también lo que espera. En un ensayo, las tareas son de mentira: se elige la fecha y se dice qué haría
        'tactica-fecha': v => this.otraFecha(v),
        // encargarle ya al agente una contestada, sin esperar la pasada (en un ensayo, dice qué haría)
        'tactica-revisar': v => this.revisar(v),
    };

    constructor(private readonly t: Tablero, private readonly pestanas: () => PestanaDeTactica[]) {}

    async abrir(): Promise<void> {
        this.muestra = undefined;
        this.t.montar();
        this.t.ir('tactica');
        // recargada (un despliegue): los proyectos de antes, mientras llegan los de ahora (y se piden igual)
        const deAntes = this.proyectos ? undefined : cli.proyectosRecordados()?.proyectos;
        if (deAntes) this.proyectos = deAntes;
        if (!this.lista) {
            const esperas = cli.recordado<cli.JsonEsperas>('esperas')?.valor;
            if (esperas) { this.lista = esperas.esperas; this.contestadas = esperas.contestadas ?? []; }
        }
        this.pintar();
        const d = await this.t.diaLeido();
        // el plan de hoy (como «ahora»), y lo que espera
        const [plan, proyectos] = await Promise.all([
            this.t.planes.plan?.dia === d.fecha ? Promise.resolve(undefined) : cli.resultado('plan', ''),
            this.proyectos && !deAntes ? Promise.resolve(undefined) : cli.proyectos(),
            this.leer(),
            this.agente ? Promise.resolve() : import('../../web/contestar').then(m => m.HACER.agenteGeneral?.()).then(a => { this.agente = a ?? ''; }, () => undefined),
        ]);
        if (plan?.datos?.ok) this.t.planes.plan = plan.datos;
        if (proyectos?.datos) this.proyectos = proyectos.datos.proyectos;
        if (this.t.pantalla === 'tactica') this.pintar();
    }

    /** Un ensayo: Táctica con un día de mentira (componentes/muestras-tactica.ts), sin leer nada; ↻ o la pestaña vuelven
     *  a lo de verdad. */
    ensayo(m: DatosTactica): void {
        this.t.montar();
        this.t.ir('tactica');
        this.muestra = m;
        this.encargosEnsayo = new Map();
        this.pintar();
    }

    private repintar(): void { if (this.t.pantalla === 'tactica') this.pintar(); }

    /** ↻: el día (lo local) y lo que espera. */
    private async releer(): Promise<void> {
        if (this.muestra) { void this.abrir(); return; }
        await Promise.all([this.t.actualizar(), this.leer()]);
        if (this.t.pantalla === 'tactica') this.pintar();
    }

    /** Lo que espera (una lectura a la vez); si se ve, se repinta. */
    private leer(): Promise<void> {
        this.leyendo ??= (async () => {
            const r = await cli.esperas();
            if (r.datos) {
                cli.recordar('esperas', r.datos);
                this.lista = r.datos.esperas;
                this.contestadas = r.datos.contestadas ?? [];
            }
            this.leida = Date.now();
        })().finally(() => { this.leyendo = undefined; });
        return this.leyendo;
    }

    pintar(): void {
        if (!this.t.panel) return;
        this.t.teclas.clear();
        const m = this.muestra;
        const d = m?.dia ?? this.t.dia();
        // con el reloj se repinta cada minuto: de paso, lo que espera se relee si ya tiene un rato
        if (!m && !this.leyendo && this.leida && Date.now() - this.leida > RELEER_ESPERAS) {
            void this.leer().then(() => { if (this.t.pantalla === 'tactica') this.pintar(); });
        }
        // la próxima pasada, si hay contestadas que la esperan y lo sabido ya pasó o tiene un rato
        if (!m && this.contestadas.length && !this.leyendoPasada && pasadaVieja(this.periodicos, this.pasadaLeida)) void this.leerPasada();
        // lo del mundo puesto (y lo sin clasificar): web/mundo.ts; lo de un agente que pide esconderse fuera de su mundo, tampoco en todo
        const esperas = m?.esperas ?? this.lista?.filter(e => mundo.seVe(e.mundo) && !mundo.deAgenteAjeno(e));
        if (!d || !esperas) {
            this.t.pintar(['<div class="vacio">leyendo lo de hoy y lo que te espera…</div>'],
                { nombre: 'táctica', color: 'amarillo', sinReleer: true });
            return;
        }
        const { tactica: t, grupos } = armar({ dia: d, plan: m ? m.plan : this.t.planes.planDe(d.fecha), esperas, ahora: m?.ahora ?? Date.now(),
            pestanas: m?.pestanas ?? this.pestanas(), proyectos: m ? m.proyectos : this.proyectos, abiertas: [...this.abiertas],
            contestadas: m ? m.contestadas : this.contestadas.filter(c => mundo.seVe(c.mundo)), encargos: m ? this.encargosEnsayo : this.encargos,
            periodicos: m ? m.periodicos : this.periodicos, agente: m ? m.agente : this.agente });
        this.grupos = grupos;
        // la tecla de cada vía (1 a 4: decidir, aprobar, cerrar, hacer) la recorre en «Contestar»
        for (const v of [...VIAS, VIA_HACER]) this.t.teclas.set(v.tecla, () => this.contestar(`via:${v.clave}`));
        // lo que no se pudo leer (lo que espera entero, o una de sus fuentes) lo dice la franja de avisos, arriba de la barra: lo
        // pone dashboard/esperas.ts, que lee lo mismo
        const h: string[] = [];
        // en un ensayo, lo que no atiende Táctica (hecha, la instrucción, el ⋯…) no sale a la API: solo se dice
        // en un ensayo, lo dice la primera línea de la pantalla (y ↻ vuelve a lo de verdad): la barra no lleva estados
        if (m) h.push('<div class="fila atencion tac-ensayo">ensayo: un día de mentira, nada se contesta · ↻ vuelve a lo de verdad</div>');
        h.push(tactica(m ? deEnsayo(t) : t));
        const b = barraTactica(t);
        this.t.pintar(h, { nombre: b.nombre, color: b.color, ayuda: b.ayuda, acciones: b.acciones, sinReleer: true });
    }

    /** Otra fecha para una tarea, desde su fila (tareas.ts, `reagendar`): se relee lo de hoy y lo que espera (su fecha,
     *  y por qué está donde está). Mover la fecha no contesta lo que espera: sigue en su vía. */
    private async otraFecha(valor: string): Promise<void> {
        if (!valor) return;
        // tareas.ts cuando se usa: trae lo de la página (el guardado, la lista), que las pruebas en Node no tienen
        const { elegirFecha, reagendar } = await import('./tareas');
        if (this.muestra) {
            const [, id] = lista(valor);
            const f = await elegirFecha(id);
            if (f) ui.estado(`(ensayo) movería ${id} al ${f}: no se hizo nada`, 6000);
            return;
        }
        if (await reagendar(valor)) await this.releer();
    }

    /** Los periódicos, para la próxima pasada (una lectura a la vez): de esta máquina o de donde viven, por el bus. Si no
     *  se pueden leer, queda el porqué (la cabecera lo dice). */
    private leerPasada(): Promise<void> {
        this.leyendoPasada ??= (async () => {
            const r = await cli.periodicos();
            this.periodicos = r.datos ?? { error: r.error ?? 'no contestó' };
            this.pasadaLeida = Date.now();
        })().finally(() => { this.leyendoPasada = undefined; this.repintar(); });
        return this.leyendoPasada;
    }

    /** «revisar ya»: encargarle una contestada al agente que escribe los avances, ahora, por el camino de «hazte cargo ya»
     *  (web/contestar.ts, `alAgenteDe`: queda en la tarea como un prompt, REVISAR_YA, y le llega un aviso con su
     *  dirección). Encargada (lo dice la tarea, o recién), no se encarga de nuevo; si no salió, lo dice y se puede volver
     *  a apretar (sin repetir lo que ya salió). En un ensayo, no manda nada: dice qué haría. */
    private async revisar(direccion: string): Promise<void> {
        const m = this.muestra;
        const encargos = m ? this.encargosEnsayo : this.encargos;
        const c = (m ? m.contestadas ?? [] : this.contestadas).find(x => x.direccion === direccion);
        const [vista] = contestadasDe(c ? [c] : [], Date.now(), encargos);
        if (!c || !vista || vista.encargando) return;
        const quien = (m ? m.agente : this.agente) || 'el agente que escribe los avances';
        if (vista.encargada) { ui.estado(`ya se la encargaste a ${quien} (${vista.encargada}): no se encarga dos veces seguidas`, 6000); return; }
        const antes = encargos.get(direccion);
        const hecho = antes?.para === c.cuando ? antes.hecho : { lineas: 0, mensaje: false };
        encargos.set(direccion, { estado: 'enviando', para: c.cuando, hecho });
        this.repintar();
        if (m) {
            await new Promise(r => setTimeout(r, 700));
            encargos.set(direccion, { estado: 'hecho', para: c.cuando, hora: hm(Date.now()), hecho });
            ui.estado(`(ensayo) dejaría en ${direccion} «${REVISAR_YA}» y le avisaría a ${quien}: no se hizo nada`, 8000);
            this.repintar();
            return;
        }
        const { alAgenteDe } = await import('../../web/contestar');
        const r = await alAgenteDe(direccion, [REVISAR_YA], hecho).catch((e: unknown) => ({ ok: false as const, error: String(e) }));
        if (!r.ok) {
            encargos.set(direccion, { estado: 'fallo', para: c.cuando, error: r.error, hecho });
            ui.estado(`«revisar ya» no salió (${direccion}): ${r.error}`, 10000);
            this.repintar();
            return;
        }
        encargos.set(direccion, { estado: 'hecho', para: c.cuando, hora: hm(Date.now()), hecho });
        ui.estado(`${direccion} encargada: ${r.dice}`, 6000);
        this.repintar();
        // lo que dice la tarea ahora (su prompt): de ahí sale la hora desde aquí en adelante
        await this.leer();
        this.repintar();
    }

    /** Contestar en la ventana de «Contestar»: una espera, o las de una cuenta una tras otra (hasta que se cierre una sin
     *  contestar). Lo contestado sale al tiro, y al final se relee. */
    private async contestar(direccion: string, inicial: Inicial = {}): Promise<void> {
        if (!direccion) return;
        const deVarias = /^(via|cuenta):/.test(direccion);
        const grupo = this.grupos.get(direccion) ?? (deVarias ? [] : this.lista?.filter(e => e.direccion === direccion) ?? []);
        if (!grupo.length) { if (!deVarias) void ui.abrirDireccion(direccion); return; }
        const { abrirContestar, hacerDeEnsayo } = await import('../../web/contestar');
        const ensayo = this.muestra ? hacerDeEnsayo() : undefined;
        for (const e of grupo) {
            const dice = await abrirContestar(e, ensayo, Date.now(), grupo.length === 1 ? inicial : {});
            if (!dice) break;
            ui.estado(dice, 6000);
            if (ensayo) continue;
            // sale de su vía al tiro; si queda esperando al agente, la relectura del final la trae a las contestadas
            this.lista = this.lista?.filter(x => x.direccion !== e.direccion);
            if (this.t.pantalla === 'tactica') this.pintar();
        }
        if (ensayo) return;
        // lo que espera, y el día (si en la ventana se movió una fecha, Hacer y las listas la muestran)
        await Promise.all([this.leer(), this.t.actualizar()]);
        if (this.t.pantalla === 'tactica') this.pintar();
    }
}
