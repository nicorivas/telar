// El horario de los mundos, para verlo y cambiarlo con clics (⚙ mundos › horario): la vista previa de la semana y el
// editor de cada mundo. Sin DOM ni red: da HTML y hace la cuenta, y su prueba es `npm run prueba:horario`.
//
// · La semana: un renglón por día, de lunes a domingo, y en cada uno una franja de 0 a 24 h partida en pedazos: el de un
//   mundo, en su color; donde dos o más se pisan (un choque: a esa hora no rige ninguno, sino el de fuera), en el de
//   peligro y rayado; donde no rige ninguno (un hueco), el de fuera de todo horario, apagado (o nada, si es ambos). La
//   hora de ahora, una línea en el día de hoy. Lo que se ve es el borrador: lo que quedaría si se guarda.
// · El editor de un mundo: sus tramos, uno por renglón, cada uno con sus días (lun … dom, un clic prende o apaga uno) y de
//   qué hora a qué hora (de a 15 minutos; «hasta» antes que «desde» pasa la medianoche). Al pie, lo que se va a escribir
//   en `[mundos.<n>] horario` y los botones de la casa (componentes/boton.ts): guardar y deshacer.
//
// La cuenta de los choques es la de telar.horario.choques, que el servidor usa para no escribir uno: la misma regla a los
// dos lados. Cómo se ve: media/css/configuracion.css (`.hs-…`).

import { esc } from '../estilo';
import { I } from '../web/iconos';
import { pieBotones, type Boton } from './boton';
import { leerTramo, type TramoHorario } from './modos-mundos';

export const DIA = 24 * 60;
/** de a cuánto se eligen las horas, en minutos */
export const PASO = 15;
/** los días en el orden de la semana de aquí, de lunes a domingo (como `Date.getDay`: 0 es domingo) */
export const ORDEN_DIAS = [1, 2, 3, 4, 5, 6, 0] as const;
/** el nombre corto de cada día, desde el domingo, como se escribe en un tramo */
export const CORTOS = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'] as const;
/** el nombre entero, como se dice */
export const NOMBRES = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'] as const;

/** Un minuto del día como se escribe: 540 → «9:00», 1440 → «24:00». */
export const hora = (m: number): string => `${Math.floor(m / 60)}:${String(m % 60).padStart(2, '0')}`;

/** Los días de un tramo como se escriben: seguidos de lunes a domingo, en rangos («lun-vie», «sáb-dom»); sueltos, con
 *  coma («lun,mié»). Todos: "". */
export function escribirDias(dias: readonly number[]): string {
    const hay = new Set(dias);
    if (hay.size >= 7) return '';
    const corridas: number[][] = [];
    for (const d of ORDEN_DIAS) {
        if (!hay.has(d)) continue;
        const ultima = corridas[corridas.length - 1];
        const previo = ORDEN_DIAS[ORDEN_DIAS.indexOf(d) - 1];
        if (ultima && ultima[ultima.length - 1] === previo) ultima.push(d); else corridas.push([d]);
    }
    return corridas.map(c => (c.length > 1 ? `${CORTOS[c[0]]}-${CORTOS[c[c.length - 1]]}` : CORTOS[c[0]])).join(',');
}

/** Un tramo como se escribe en `[mundos.<n>] horario`: «lun-vie 9:00-19:00»; el día entero, sin horas («sáb-dom»); todos
 *  los días, sin días («20:00-23:00»); todos y entero, «todos». Lo lee leerTramo (y telar.horario) tal cual. */
export function escribirTramo(t: TramoHorario): string {
    const dias = escribirDias(t.dias);
    const horas = t.desde === 0 && t.hasta === DIA ? '' : `${hora(t.desde)}-${hora(t.hasta)}`;
    return [dias, horas].filter(Boolean).join(' ') || 'todos';
}

/** Por qué un tramo del editor no se puede escribir ("" si se puede). */
export function problemaTramo(t: TramoHorario): string {
    if (!t.dias.length) return 'elige al menos un día';
    if (t.desde === t.hasta) return 'empieza y termina a la misma hora';
    return '';
}

/** Un tramo nuevo para agregar: el primero del mundo con las horas que siguen a las suyas, o de lunes a viernes de 9 a 18. */
export function tramoNuevo(hay: readonly TramoHorario[]): TramoHorario {
    const u = hay[hay.length - 1];
    if (!u) return { dias: [1, 2, 3, 4, 5], desde: 9 * 60, hasta: 18 * 60 };
    if (u.hasta > DIA - 2 * 60 || u.hasta < u.desde) return { dias: [6, 0], desde: 10 * 60, hasta: 14 * 60 };
    return { dias: [...u.dias], desde: u.hasta, hasta: u.hasta + 60 };
}

/** Prender o apagar un día de un tramo (los días quedan en orden). */
export function alternarDia(t: TramoHorario, dia: number): TramoHorario {
    const dias = t.dias.includes(dia) ? t.dias.filter(d => d !== dia) : [...t.dias, dia];
    return { ...t, dias: [...new Set(dias)].sort((a, b) => a - b) };
}

/** Los minutos que cubre un tramo en cada día (desde el domingo): [desde, hasta) dentro del día; uno que pasa la
 *  medianoche sigue en el día siguiente (el del sábado, el domingo). Lo mismo que telar.horario.intervalos. */
export function intervalos(t: TramoHorario): { dia: number; desde: number; hasta: number }[] {
    const salida: { dia: number; desde: number; hasta: number }[] = [];
    for (const d of t.dias) {
        if (t.desde < t.hasta) { salida.push({ dia: d, desde: t.desde, hasta: t.hasta }); continue; }
        salida.push({ dia: d, desde: t.desde, hasta: DIA });
        if (t.hasta) salida.push({ dia: (d + 1) % 7, desde: 0, hasta: t.hasta });
    }
    return salida;
}

/** El horario de un mundo, para la cuenta: su clave y sus tramos. */
export interface HorarioDe { clave: string; tramos: readonly TramoHorario[] }

/** Un pedazo de un día: de qué minuto a qué minuto, y qué mundos rigen ahí (ninguno: un hueco; dos o más: un choque). */
export interface Pedazo { desde: number; hasta: number; mundos: string[] }

/** La semana, día por día (desde el domingo): cada día partido en pedazos seguidos de 0 a 24 h, con los mundos que rigen
 *  en cada uno, en el orden en que vienen. */
export function semana(horarios: readonly HorarioDe[]): Pedazo[][] {
    return [0, 1, 2, 3, 4, 5, 6].map(dia => {
        const marcas = new Uint32Array(DIA);
        horarios.forEach((h, i) => {
            for (const t of h.tramos) for (const x of intervalos(t)) {
                if (x.dia !== dia) continue;
                for (let k = x.desde; k < x.hasta; k++) marcas[k] |= 1 << i;
            }
        });
        const pedazos: Pedazo[] = [];
        for (let k = 0; k < DIA;) {
            let j = k;
            while (j < DIA && marcas[j] === marcas[k]) j++;
            pedazos.push({ desde: k, hasta: j, mundos: horarios.filter((_, i) => marcas[k] >> i & 1).map(h => h.clave) });
            k = j;
        }
        return pedazos;
    });
}

/** Un choque: dos mundos o más que rigen a la vez, un día, de un minuto a otro (como telar.horario.choques). */
export interface Choque { mundos: string[]; dia: number; desde: number; hasta: number }

/** Dónde se pisan los horarios, día por día desde el domingo. Con `de`, solo los de ese mundo. */
export function choques(horarios: readonly HorarioDe[], de = ''): Choque[] {
    return semana(horarios).flatMap((pedazos, dia) => pedazos.filter(p => p.mundos.length > 1 && (!de || p.mundos.includes(de)))
        .map(p => ({ mundos: p.mundos, dia, desde: p.desde, hasta: p.hasta })));
}

/** Un choque en una frase, como lo dice el servidor: «trabajo» y «estudio» se pisan el lunes de 9:00 a 10:00. */
export function decirChoque(c: Choque): string {
    const n = c.mundos.map(x => `«${x}»`);
    return `${n.slice(0, -1).join(', ')} y ${n[n.length - 1]} se pisan el ${NOMBRES[c.dia]} de ${hora(c.desde)} a ${hora(c.hasta)}`;
}

/** Los choques juntados: los mismos mundos a las mismas horas en varios días, uno solo con esos días. */
export function juntarChoques(cs: readonly Choque[]): (Omit<Choque, 'dia'> & { dias: number[] })[] {
    const salida = new Map<string, Omit<Choque, 'dia'> & { dias: number[] }>();
    for (const c of cs) {
        const clave = `${c.mundos.join('+')} ${c.desde} ${c.hasta}`;
        const hay = salida.get(clave);
        if (hay) hay.dias.push(c.dia); else salida.set(clave, { mundos: c.mundos, desde: c.desde, hasta: c.hasta, dias: [c.dia] });
    }
    return [...salida.values()];
}

/** Un choque juntado en una frase: «trabajo» y «personal» se pisan los lun-vie de 18:00 a 19:00 (de un día: el lunes). */
export function decirChoques(c: Omit<Choque, 'dia'> & { dias: number[] }): string {
    const n = c.mundos.map(x => `«${x}»`);
    const dias = c.dias.length === 1 ? `el ${NOMBRES[c.dias[0]]}` : c.dias.length === 7 ? 'todos los días' : `los ${escribirDias(c.dias)}`;
    return `${n.slice(0, -1).join(', ')} y ${n[n.length - 1]} se pisan ${dias} de ${hora(c.desde)} a ${hora(c.hasta)}`;
}

/** Cuántas horas de la semana no rige ningún horario (los huecos: ahí rige el de fuera). */
export function horasDeHueco(horarios: readonly HorarioDe[]): number {
    return semana(horarios).flat().filter(p => !p.mundos.length).reduce((s, p) => s + (p.hasta - p.desde), 0) / 60;
}

/** Lo que se va a escribir de un borrador (sus tramos como texto, sin repetir) o por qué no se puede: un tramo sin días o
 *  que empieza y termina a la misma hora, o un choque con los horarios guardados de los otros mundos (`otros`). */
export function revisar(clave: string, tramos: readonly TramoHorario[], otros: readonly HorarioDe[]): { textos: string[]; error: string } {
    for (const [i, t] of tramos.entries()) {
        const p = problemaTramo(t);
        if (p) return { textos: [], error: `${tramos.length > 1 ? `el tramo ${i + 1}: ` : ''}${p}` };
    }
    const textos = [...new Set(tramos.map(escribirTramo))];
    for (const x of textos) leerTramo(x); // lo que se escribe se lee igual: si no, es un error de aquí, y se dice
    const pisa = juntarChoques(choques([{ clave, tramos }, ...otros.filter(o => o.clave !== clave)], clave));
    if (pisa.length) return { textos, error: `${decirChoques(pisa[0])}${pisa.length > 1 ? ` (y ${pisa.length - 1} más)` : ''}: a esa hora no regiría ninguno de los dos` };
    return { textos, error: '' };
}

/** Si dos listas de tramos dicen lo mismo (los mismos días y horas, en cualquier orden). */
export function iguales(a: readonly TramoHorario[], b: readonly TramoHorario[]): boolean {
    const forma = (x: readonly TramoHorario[]) => x.map(t => `${[...t.dias].sort().join(',')} ${t.desde}-${t.hasta}`).sort().join(';');
    return forma(a) === forma(b);
}

// ───────────────────────── lo que se dibuja ─────────────────────────

/** Un mundo, para dibujarlo: su clave, su nombre y su tinta (una del tema). */
export interface MundoDibujo { clave: string; nombre: string; color: string }

const tinta = (m: MundoDibujo | undefined) => (m ? ` style="--mundo-c: var(--${esc(m.color)})"` : '');
const pct = (m: number) => `${(m / DIA * 100).toFixed(4)}%`;
/** el estilo de un pedazo: dónde va, qué tan ancho y, si es de un mundo, su tinta */
const estilo = (p: Pedazo, m: MundoDibujo | undefined) =>
    ` style="left: ${pct(p.desde)}; width: ${pct(p.hasta - p.desde)}${m ? `; --mundo-c: var(--${esc(m.color)})` : ''}"`;

/** La vista previa de la semana: un renglón por día (de lunes a domingo), con sus pedazos (el de cada mundo en su color,
 *  los choques rayados en el de peligro, los huecos en el de fuera, apagado), la hora de ahora en el día de hoy, la escala
 *  de horas y la leyenda. */
export function htmlSemana(horarios: readonly HorarioDe[], mundos: readonly MundoDibujo[], fuera: string, ahora?: Date): string {
    const dias = semana(horarios);
    const de = (k: string) => mundos.find(m => m.clave === k);
    const deFuera = de(fuera);
    const pedazo = (p: Pedazo, dia: number) => {
        const cuando = `${NOMBRES[dia]} de ${hora(p.desde)} a ${hora(p.hasta)}`;
        if (p.mundos.length > 1) {
            return `<span class="hs-pedazo hs-choque"${estilo(p, undefined)}`
                + ` title="${esc(`${p.mundos.join(' y ')} se pisan el ${cuando}: rige ${deFuera?.nombre ?? 'ambos'} (fuera)`)}"></span>`;
        }
        if (!p.mundos.length) {
            return `<span class="hs-pedazo hs-hueco"${estilo(p, deFuera)}`
                + ` title="${esc(`sin horario el ${cuando}: rige ${deFuera ? `${deFuera.nombre}, fuera de todo horario` : 'ambos'}`)}"></span>`;
        }
        const m = de(p.mundos[0]);
        return `<span class="hs-pedazo hs-mundo"${estilo(p, m)} title="${esc(`${m?.nombre ?? p.mundos[0]}, el ${cuando}`)}"></span>`;
    };
    const filas = ORDEN_DIAS.map(d => {
        const hoy = ahora && ahora.getDay() === d;
        const linea = hoy ? `<span class="hs-ahora" style="left: ${pct(ahora.getHours() * 60 + ahora.getMinutes())}" title="ahora, ${hora(ahora.getHours() * 60 + ahora.getMinutes())}"></span>` : '';
        return `<div class="hs-dia${hoy ? ' hoy' : ''}"><span class="hs-nombre">${CORTOS[d]}</span>`
            + `<span class="hs-franja">${dias[d].map(p => pedazo(p, d)).join('')}${linea}</span></div>`;
    });
    const escala = `<div class="hs-dia hs-escala"><span class="hs-nombre"></span><span class="hs-franja">${[0, 6, 12, 18, 24]
        .map(h => `<span class="hs-hora" style="left: ${pct(h * 60)}">${h}</span>`).join('')}</span></div>`;
    const hayChoque = dias.some(ps => ps.some(p => p.mundos.length > 1));
    const hayHueco = dias.some(ps => ps.some(p => !p.mundos.length));
    const leyenda = [
        ...mundos.filter(m => horarios.some(h => h.clave === m.clave && h.tramos.length))
            .map(m => `<span${tinta(m)}><span class="hs-muestra hs-mundo"></span>${esc(m.nombre)}</span>`),
        hayHueco ? `<span${tinta(deFuera)}><span class="hs-muestra hs-hueco"></span>sin horario: rige ${esc(deFuera?.nombre ?? 'ambos')}</span>` : '',
        hayChoque ? '<span class="hs-se-pisan"><span class="hs-muestra hs-choque"></span>se pisan: no rige ninguno</span>' : '',
    ].filter(Boolean).join('');
    return `<div class="hs-semana">${filas.join('')}${escala}</div><div class="hs-leyenda">${leyenda}</div>`;
}

/** Lo que dice el pie del editor de un mundo. */
export interface EstadoEditor {
    /** si el borrador es distinto de lo guardado */
    cambiado: boolean;
    /** lo que se escribiría, o por qué no (`revisar`) */
    textos: string[];
    error: string;
    /** mientras se guarda */
    guardando?: boolean;
    /** dónde vive lo guardado, en palabras («en la raíz: todas las máquinas») */
    vive?: string;
}

/** Las horas para elegir, de a PASO minutos: «desde», de 0:00 a 23:45; «hasta», de 0:15 a 24:00. Una que no cae en el paso
 *  (escrita a mano: 8:10) se agrega en su lugar, para no perderla. */
function opcionesHora(cual: 'desde' | 'hasta', valor: number): string {
    const horas: number[] = [];
    for (let m = cual === 'desde' ? 0 : PASO; m <= (cual === 'desde' ? DIA - PASO : DIA); m += PASO) horas.push(m);
    if (!horas.includes(valor)) horas.push(valor), horas.sort((a, b) => a - b);
    return horas.map(m => `<option value="${m}"${m === valor ? ' selected' : ''}>${hora(m)}</option>`).join('');
}

/** El editor del horario de un mundo: sus tramos (los días, cada uno un clic; desde y hasta, de a PASO minutos; quitar),
 *  «otro tramo» y, al pie, lo que se va a escribir y guardar / deshacer. Las acciones: `horario-dia` («<mundo> <i>
 *  <día>»), `horario-quitar` («<mundo> <i>»), `horario-tramo` («<mundo>»), `horario-guardar` y `horario-deshacer`
 *  («<mundo>»); las horas son `<select data-horario="<mundo> <i> desde|hasta">`. */
export function htmlEditor(m: MundoDibujo, tramos: readonly TramoHorario[], e: EstadoEditor): string {
    const v = (x: string) => esc(`${m.clave} ${x}`);
    const filas = tramos.map((t, i) => {
        const dias = ORDEN_DIAS.map(d => `<a class="hs-dia-op${t.dias.includes(d) ? ' si' : ''}" data-accion="horario-dia" data-valor="${v(`${i} ${d}`)}"`
            + ` title="${esc(`${NOMBRES[d]}: un clic lo ${t.dias.includes(d) ? 'apaga' : 'prende'}`)}">${CORTOS[d]}</a>`).join('');
        const problema = problemaTramo(t);
        const nota = problema ? `<span class="hs-nota mal">${esc(problema)}</span>`
            : t.hasta < t.desde ? '<span class="hs-nota">pasa la medianoche</span>' : '';
        return `<div class="hs-tramo"><span class="hs-dias">${dias}</span>`
            + `<span class="hs-horas"><select data-horario="${v(`${i} desde`)}" title="desde">${opcionesHora('desde', t.desde)}</select>`
            + `<span class="dim">–</span><select data-horario="${v(`${i} hasta`)}" title="hasta">${opcionesHora('hasta', t.hasta)}</select></span>`
            + `<a class="hs-quitar" data-accion="horario-quitar" data-valor="${v(String(i))}" title="quitar este tramo"><span class="i">${I.descartar}</span></a>`
            + `${nota}</div>`;
    });
    const vacio = tramos.length ? '' : '<div class="fila dim">&nbsp;&nbsp;sin horario: se pone solo a mano</div>';
    const otro = `<div class="fila"><a data-accion="horario-tramo" data-valor="${esc(m.clave)}" title="otro tramo de días y horas">`
        + `<span class="i">${I.nuevo}</span> otro tramo</a></div>`;
    const escribe = e.textos.length ? `horario = ${e.textos.length === 1 ? `"${e.textos[0]}"` : `[${e.textos.map(x => `"${x}"`).join(', ')}]`}` : 'sin horario';
    const izq = e.error ? `<span class="i hs-error">${I.alerta}</span><span class="hs-error">${esc(e.error)}</span>`
        : e.cambiado ? `<span class="dim">se escribe <code>${esc(escribe)}</code></span>`
            : `<span class="dim">guardado${e.vive ? ` · ${esc(e.vive)}` : ''}</span>`;
    const apagado = !e.cambiado || !!e.error;
    const botones: Boton[] = [
        { texto: 'guardar', accion: 'horario-guardar', valor: m.clave, color: 'verde', icono: I.hecha,
            ayuda: e.error ? `no se puede: ${e.error}` : e.cambiado ? `escribir ${escribe}` : 'nada cambió', ...(apagado || e.guardando ? { estado: 'deshabilitado' as const } : {}) },
        { texto: 'deshacer', accion: 'horario-deshacer', valor: m.clave, tono: 'callado', icono: I.deshacer,
            ayuda: 'volver a lo guardado', ...(e.cambiado && !e.guardando ? {} : { estado: 'deshabilitado' as const }) },
    ];
    return `<div class="hs-editor" data-mundo="${esc(m.clave)}"${tinta(m)}>${filas.join('')}${vacio}${otro}`
        + `${pieBotones(botones, { izq, clase: 'hs-pie' })}</div>`;
}
