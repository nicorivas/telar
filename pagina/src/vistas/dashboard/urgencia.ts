// La urgencia: en qué orden pide atención lo que espera a la persona. Es lo que ordena Decidir y Hacer en Táctica, y
// puede ordenar cualquier lista que mezcle tareas y esperas.
//
// Desde el 17-nov la ordenan, primero, tres señales que declara el agente al proponer (CAMPOS, más abajo), y después
// las que ya calculaba telar:
//
//   0. un hilo detenido   un hilo espera en su turno (un permiso, una pregunta en vivo) o un mensaje retenido: bloquea ahora
//   1. el peso            alto, medio o bajo, con su porqué; sin peso cuenta como medio
//   2. una persona espera alguien de afuera espera la respuesta
//   3. una fecha dura     una fecha externa que el agente marcó como dura: la más próxima primero
//   4. el orden de hoy    vence hoy (o venció hace 30 días o menos) > el plan la puso hoy > vence esta semana > lo demás;
//                         dentro, lo que vence antes y, a igual fecha, lo que espera hace más
//
// Sin señales declaradas, todo empata en 1 a 3 y queda el orden de hoy. El peso es lo único que declara el agente que
// salta la fila (lo decidió la persona el 17-nov): ni la prioridad de una tarea ni la `urgencia` de una pregunta lo
// hacen, y no se deduce de nada todavía. Lo vencido hace más de 30 días es **deuda** (`esDeuda`, dia.ts) y no entra: va
// al filtro «deuda» de tareas; salvo lo que tiene estrella, lo que alguien espera (un hilo, una persona), lo de peso alto y lo que
// tiene una fecha dura.
//
// El color: solo lo dicen una fecha dura y una persona que espera hoy (y un hilo detenido, que espera ahora). Lo demás
// (lo vencido, lo de hoy, lo del plan) dice su fecha en el tono de siempre.
//
// Todo es puro: recibe las señales y la hora, y no lee nada. Las señales de una espera (`telar esperas`) y de un
// pendiente (`telar hoy`) las sacan `deEspera` y `dePendiente`; las tareas que el plan pone hoy, `delPlan`; lo que
// declara el agente, `declarado`. La prueba: npm run prueba:componentes (pruebas/componentes.mjs, «la urgencia»). En el
// catálogo, /componentes#tactica/urgencia.

import type * as cli from '../../cli';
import { type Pendiente, esDeuda } from './dia';
import { diasA, edad } from './esperas';
import type { Plan } from './plan';

// ───────────────────────── lo que declara el agente ─────────────────────────

/** Los nombres de lo que declara un agente al proponer, en un solo lugar: si cambia un formato, cambia aquí.
 *  En una tarea van al principio de su última línea `[avance]`, como `clave=valor`, separados por « · » y antes del
 *  texto: «pide=aprobar · peso=alto (renueva el contrato) · artefacto=casa/propuesta.md · falta: …» (con o sin la marca
 *  delante: «preparado: …»). En una pregunta del módulo, como `clave: valor` en las primeras líneas de su resumen:
 *  «peso: alto (renueva el contrato)». `persona`, `dura`, `opciones` y `artefacto` todavía no tienen formato confirmado:
 *  estos nombres son provisorios. */
export const CAMPOS = {
    /** qué pide a la persona, una de las cuatro vías: decidir, aprobar, hacer-tu o cerrar */
    pide: 'pide',
    /** cuánto pesa: alto, medio o bajo, con su porqué entre paréntesis */
    peso: 'peso',
    /** quién espera la respuesta: una persona (provisorio) */
    persona: 'espera',
    /** una fecha externa dura, AAAA-MM-DD (provisorio) */
    dura: 'dura',
    /** de decidir: las opciones cerradas, separadas por « | »; la recomendada lleva un `*` al final (provisorio) */
    opciones: 'opciones',
    /** de aprobar: lo que dejó hecho, una ruta o un enlace (provisorio) */
    artefacto: 'artefacto',
} as const;

/** Lo que una espera pide a la persona: una de las cuatro vías de Táctica. Decidir, elegir entre opciones; aprobar, lo
 *  que el agente ya dejó hecho; hacer-tu, lo que solo la persona puede (un pago, una firma, una llamada); cerrar, lo que
 *  ya pasó. */
export type Pide = 'decidir' | 'aprobar' | 'hacer-tu' | 'cerrar';
export const PIDES: readonly Pide[] = ['decidir', 'aprobar', 'hacer-tu', 'cerrar'];
export type Peso = 'alto' | 'medio' | 'bajo';
export const PESOS: readonly Peso[] = ['alto', 'medio', 'bajo'];

/** Lo que declaró el agente (lo que falta, no viene) y el texto que queda después. */
export interface Declarado {
    pide?: Pide;
    peso?: Peso;
    /** el porqué del peso, en pocas palabras */
    porque?: string;
    persona?: string;
    /** la fecha dura, AAAA-MM-DD */
    dura?: string;
    /** las opciones de una decisión, con la recomendada */
    opciones?: { texto: string; recomendada?: boolean }[];
    /** lo que dejó hecho: una ruta o un enlace */
    artefacto?: string;
    /** el texto sin lo declarado */
    resto: string;
}

/** Un valor declarado, con su porqué entre paréntesis si lo trae: «alto (renueva el contrato)». */
function conPorque(valor: string): { valor: string; porque: string } {
    const m = /^(.*?)\s*\(([^)]*)\)\s*$/.exec(valor.trim());
    return m ? { valor: m[1].trim(), porque: m[2].trim() } : { valor: valor.trim(), porque: '' };
}

/** Guarda un campo declarado en lo que se va leyendo; false si no es de los nuestros (ahí termina lo declarado). */
function guardar(d: Declarado, clave: string, valor: string): boolean {
    if (clave === CAMPOS.opciones) {
        const ops = valor.split(' | ').map(x => x.trim()).filter(Boolean)
            .map(x => (x.endsWith('*') ? { texto: x.slice(0, -1).trim(), recomendada: true } : { texto: x })).filter(o => o.texto);
        if (ops.length) d.opciones = ops;
        return true;
    }
    if (clave === CAMPOS.artefacto) { if (valor.trim()) d.artefacto = valor.trim(); return true; }
    const v = conPorque(valor);
    const minus = v.valor.toLowerCase();
    if (clave === CAMPOS.pide) { if ((PIDES as readonly string[]).includes(minus)) d.pide = minus as Pide; return true; }
    if (clave === CAMPOS.peso) {
        if ((PESOS as readonly string[]).includes(minus)) { d.peso = minus as Peso; if (v.porque) d.porque = v.porque; }
        return true;
    }
    if (clave === CAMPOS.persona) { if (v.valor) d.persona = v.valor; return true; }
    if (clave === CAMPOS.dura) { if (/^\d{4}-\d{2}-\d{2}$/.test(v.valor)) d.dura = v.valor; return true; }
    return false;
}

/** Lo declarado en el texto de una línea `[avance]`: los `clave=valor` del principio, separados por « · », hasta el
 *  primero que no lo es. Con la marca delante («preparado: pide=…») o sin ella (como lo da `telar esperas`). Un valor
 *  que no se entiende (pide=quizás) no cuenta, pero no corta. */
export function declarado(texto: string): Declarado {
    const original = (texto ?? '').trim();
    // la marca delante («preparado: », «cerrar:hecha: »), solo si lo que sigue es uno de los nuestros
    const t = original.replace(new RegExp(`^[\\w:]+:\\s+(?=(${Object.values(CAMPOS).join('|')})=)`), '');
    const d: Declarado = { resto: original };
    const partes = t.split(' · ');
    let i = 0;
    for (; i < partes.length; i++) {
        const m = /^(\w+)=(.*)$/.exec(partes[i].trim());
        if (!m || !guardar(d, m[1], m[2])) break;
    }
    if (i) d.resto = partes.slice(i).join(' · ').trim();
    return d;
}

/** Lo declarado en el resumen de una pregunta: las líneas `clave: valor` del principio que son de los nuestros. */
export function declaradoEnResumen(resumen: string): Declarado {
    const lineas = (resumen ?? '').split('\n');
    const d: Declarado = { resto: '' };
    let i = 0;
    for (; i < lineas.length; i++) {
        const m = /^\s*(\w+):\s+(.*)$/.exec(lineas[i]);
        if (!m || !guardar(d, m[1].toLowerCase(), m[2])) break;
    }
    d.resto = lineas.slice(i).join('\n').trim();
    return d;
}

/** La vía de una espera: la que declara el agente (`pide=`). Sin declararla, solo lo que ya dice qué es por su forma:
 *  un cierre propuesto (`avance:cerrar`, la marca del agente) es cerrar, y una pregunta del módulo (`decide`, con sus
 *  opciones) es decidir. Lo demás no se adivina: null, sin clasificar (una pregunta en una tarea suele ser una decisión,
 *  pero «preparado» con un «¿…?» al final también). */
export function viaDe(e: cli.JsonEspera, d: Declarado = declaradoDe(e)): Pide | null {
    if (d.pide) return d.pide;
    if (e.clase === 'avance:cerrar') return 'cerrar';
    if (e.clase === 'decide') return 'decidir';
    return null;
}

/** Lo que declaró el agente en una espera: en una tarea, su línea `[avance]` (`campos.texto`); en una pregunta del
 *  módulo, su resumen (`campos.secciones.resumen`, o el corto). Lo demás no declara nada. */
export function declaradoDe(e: cli.JsonEspera): Declarado {
    const c = e.campos ?? {};
    if (e.clase.startsWith('avance:')) return declarado(typeof c.texto === 'string' ? c.texto : e.resumen);
    if (e.clase === 'decide') {
        const s = (c.secciones as { resumen?: unknown } | undefined)?.resumen;
        return declaradoEnResumen(typeof s === 'string' && s ? s : e.resumen);
    }
    return { resto: e.resumen };
}

// ───────────────────────── el orden ─────────────────────────

/** Los niveles del orden de hoy, del más urgente al menos. */
export type Nivel = 'espera' | 'hoy' | 'plan' | 'semana' | 'resto';
export const NIVELES: readonly Nivel[] = ['espera', 'hoy', 'plan', 'semana', 'resto'];

/** Lo que se sabe de una cosa para ordenarla. Lo que falta, no cuenta. */
export interface Senales {
    /** un hilo detenido en su turno, un mensaje retenido: bloquea ahora */
    espera?: boolean;
    /** en cuántos días vence (negativo: venció); null o sin decir, no tiene fecha */
    dias?: number | null;
    /** el plan del día la puso hoy */
    plan?: boolean;
    /** desde cuándo existe o espera, en ms; null o sin decir, no se sabe */
    desde?: number | null;
    /** la persona le puso estrella: no es deuda aunque lo sea */
    estrella?: boolean;
    /** lo declara el agente: cuánto pesa */
    peso?: Peso;
    /** lo declara el agente: quién espera la respuesta (una persona) */
    persona?: string;
    /** lo declara el agente: en cuántos días es su fecha dura (negativo: pasó) */
    dura?: number | null;
}

/** Lo que vence en 7 días o menos es de esta semana (como el filtro «esta semana» de «tareas»). */
export const SEMANA_DIAS = 7;

const tieneFecha = (s: Senales): s is Senales & { dias: number } => typeof s.dias === 'number';
const tieneDura = (s: Senales): s is Senales & { dura: number } => typeof s.dura === 'number';

/** Si no entra a lo de ahora: vencida hace más de 30 días, sin estrella, sin nadie esperando (un hilo o una persona),
 *  sin peso alto y sin fecha dura. */
export const esDeudaDe = (s: Senales): boolean => tieneFecha(s) && esDeuda(s.dias) && !s.estrella && !s.espera && !s.persona
    && s.peso !== 'alto' && !tieneDura(s);

/** El nivel de una cosa en el orden de hoy; null si es deuda (no entra). */
export function nivel(s: Senales): Nivel | null {
    if (esDeudaDe(s)) return null;
    if (s.espera) return 'espera';
    if (tieneFecha(s) && s.dias <= 0) return 'hoy';
    if (s.plan) return 'plan';
    if (tieneFecha(s) && s.dias <= SEMANA_DIAS) return 'semana';
    return 'resto';
}

/** El rango de un peso: alto primero; sin peso, como medio. */
const RANGO_PESO: Record<string, number> = { alto: 0, medio: 1, '': 1, bajo: 2 };

/** El orden entre dos (negativo: `a` va antes). La deuda, después de todo (aunque `ordenar` la saca). */
export function comparar(a: Senales, b: Senales): number {
    const na = nivel(a), nb = nivel(b);
    if ((na === null) !== (nb === null)) return na === null ? 1 : -1;
    // 0. un hilo detenido bloquea ahora
    if (!!a.espera !== !!b.espera) return a.espera ? -1 : 1;
    // 1. el peso
    const pa = RANGO_PESO[a.peso ?? ''], pb = RANGO_PESO[b.peso ?? ''];
    if (pa !== pb) return pa - pb;
    // 2. una persona espera
    if (!!a.persona !== !!b.persona) return a.persona ? -1 : 1;
    // 3. la fecha dura más próxima; la que no tiene, después
    const ua = tieneDura(a) ? a.dura : Infinity, ub = tieneDura(b) ? b.dura : Infinity;
    if (ua !== ub) return ua < ub ? -1 : 1;
    // 4. el orden de hoy: su nivel, lo que vence antes y lo que espera hace más (lo que no lo dice, al final)
    const ia = na === null ? NIVELES.length : NIVELES.indexOf(na), ib = nb === null ? NIVELES.length : NIVELES.indexOf(nb);
    if (ia !== ib) return ia - ib;
    const da = tieneFecha(a) ? a.dias : Infinity, db = tieneFecha(b) ? b.dias : Infinity;
    if (da !== db) return da < db ? -1 : 1;
    const ta = a.desde ?? Infinity, tb = b.desde ?? Infinity;
    return ta === tb ? 0 : ta < tb ? -1 : 1;
}

/** Las cosas en su orden, sin la deuda. Estable: lo que empata queda como venía. */
export function ordenar<T>(cosas: readonly T[], senales: (x: T) => Senales): T[] {
    return cosas.map((x, i) => ({ x, i, s: senales(x) }))
        .filter(c => nivel(c.s) !== null)
        .sort((a, b) => comparar(a.s, b.s) || a.i - b.i)
        .map(c => c.x);
}

// ───────────────────────── por qué está donde está ─────────────────────────

/** Por qué está donde está, en pocas letras, con su tono (si lo tiene): lo que va al final de su fila. */
export interface Porque { nivel: Nivel; texto: string; tono?: 'espera' | 'atencion' | 'peligro' | 'tenue' }

const DIAS_SEMANA = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'];
/** Los meses, cortos, como los dicen las fechas de una fila («14-nov»). */
export const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sept', 'oct', 'nov', 'dic'];

/** El día que cae a `dias` de hoy, corto: «hoy», «mañana», «el vie» (esta semana), «el 2-dic» (más lejos o pasado). */
export function cuando(dias: number, ahora = Date.now()): string {
    if (dias === 0) return 'hoy';
    if (dias === 1) return 'mañana';
    const d = new Date(ahora);
    d.setHours(12, 0, 0, 0);
    d.setDate(d.getDate() + dias);
    return dias > 1 && dias <= SEMANA_DIAS - 1 ? `el ${DIAS_SEMANA[d.getDay()]}` : `el ${d.getDate()}-${MESES[d.getMonth()]}`;
}

/** Por qué está donde está (null si es deuda). Un hilo detenido, «te espera»; una persona, «espera Ana» (con color si
 *  vence hoy o ya venció: «Ana espera hoy»); una fecha dura, con color siempre («vence el vie»; rojo si es hoy o pasó);
 *  y lo de hoy, en el tono de siempre: «venció el 14-nov», «vence hoy», «el plan: hoy», «vence el vie», «hace 6d». */
export function porque(s: Senales, ahora = Date.now()): Porque | null {
    const n = nivel(s);
    if (n === null) return null;
    if (n === 'espera') return { nivel: n, texto: 'te espera', tono: 'espera' };
    if (s.persona) {
        const hoy = (tieneFecha(s) && s.dias <= 0) || (tieneDura(s) && s.dura <= 0);
        return hoy ? { nivel: n, texto: `${s.persona} espera hoy`, tono: 'espera' } : { nivel: n, texto: `espera ${s.persona}` };
    }
    if (tieneDura(s)) {
        return s.dura < 0 ? { nivel: n, texto: `venció ${cuando(s.dura, ahora)}`, tono: 'peligro' }
            : { nivel: n, texto: `vence ${cuando(s.dura, ahora)}`, tono: s.dura === 0 ? 'peligro' : 'atencion' };
    }
    if (n === 'hoy') return { nivel: n, texto: s.dias! < 0 ? `venció ${cuando(s.dias!, ahora)}` : 'vence hoy' };
    if (n === 'plan') return { nivel: n, texto: 'el plan: hoy' };
    if (n === 'semana') return { nivel: n, texto: `vence ${cuando(s.dias!, ahora)}` };
    const hace = s.desde ? edad(new Date(s.desde).toISOString(), ahora) : '';
    return { nivel: n, texto: hace ? `hace ${hace}` : 'sin fecha', tono: 'tenue' };
}

// ───────────────────────── las señales, de lo que ya hay ─────────────────────────

/** Las clases de espera en que un hilo espera ahora: detenido en su turno (permiso, pregunta en vivo) o un mensaje que
 *  el freno de cadenas retuvo. Lo que un agente dejó en una tarea o en una pregunta no bloquea a nadie. */
export const ALGUIEN_ESPERA: readonly string[] = ['permiso', 'pregunta', 'retenido'];

/** El código de una tarea en una dirección (`tarea:T84` → `T84`), en mayúsculas; vacío si no es una tarea. */
const codigoDe = (direccion: string): string => (/^tarea:([^@]+)/.exec(direccion)?.[1] ?? '').toUpperCase();

/** Las tareas que el plan del día pone hoy: las de sus tácticos de hoy (`tacticos.hoy[].ref`) y las que nombra un
 *  bloque de su agenda (`agenda[].tareas`). En mayúsculas, como `T84`. */
export function delPlan(plan: Plan | undefined | null): Set<string> {
    const refs = new Set<string>();
    const sumar = (x: unknown) => { if (typeof x === 'string' && x.trim()) refs.add(x.trim().toUpperCase()); };
    const hoy: unknown = plan?.tacticos?.hoy;
    if (Array.isArray(hoy)) for (const t of hoy) sumar(typeof t === 'string' ? t : (t as { ref?: unknown })?.ref);
    const agenda: unknown = plan?.agenda;
    if (Array.isArray(agenda)) for (const b of agenda) {
        const ts: unknown = (b as { tareas?: unknown })?.tareas;
        if (Array.isArray(ts)) ts.forEach(sumar);
    }
    return refs;
}

/** Las señales de una espera (`telar esperas`): si un hilo espera (su clase), cuándo vence (`campos.vence`), si el plan
 *  la pone hoy (una tarea, por su código), desde cuándo espera, y lo que declaró el agente (el peso, quién espera, la
 *  fecha dura). */
export function deEspera(e: cli.JsonEspera, plan: ReadonlySet<string> = new Set(), ahora = Date.now()): Senales {
    const desde = e.desde ? Date.parse(e.desde.length === 10 ? `${e.desde}T00:00:00` : e.desde) : NaN;
    const codigo = codigoDe(e.direccion);
    const d = declaradoDe(e);
    return {
        espera: ALGUIEN_ESPERA.includes(e.clase),
        dias: diasA(e.campos?.vence, ahora),
        plan: !!codigo && plan.has(codigo),
        desde: Number.isNaN(desde) ? null : desde,
        ...d.peso ? { peso: d.peso } : {},
        ...d.persona ? { persona: d.persona } : {},
        ...d.dura ? { dura: diasA(d.dura, ahora) } : {},
    };
}

/** Las señales de un pendiente (`telar hoy`, ya con sus días: dia.ts, `pendientes`): cuándo vence, si el plan lo pone
 *  hoy (por su código o su id), su estrella y, si se sabe, desde cuándo existe. Nadie espera en un pendiente: lo que un
 *  agente dejó en él llega como espera. */
export function dePendiente(p: Pendiente, plan: ReadonlySet<string> = new Set(), desde: number | null = null): Senales {
    const enPlan = [p.ref, p.fila.id].some(x => !!x && plan.has(x.toUpperCase()));
    return { dias: p.dias, plan: enPlan, estrella: !!p.fila.estrella, desde };
}
