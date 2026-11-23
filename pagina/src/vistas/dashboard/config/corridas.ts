// El calendario de los procesos periódicos (⚙ › periódicos): cada proceso es una fila con su línea, y cada corrida un
// círculo sobre ella, a su hora («sobre una línea: un momento», en la gramática visual: componentes/gramatica.ts). En
// un día la línea va de 00 a 24; en una semana, de lunes a domingo. Las filas van en grupos, por a quién le llega cada
// corrida: un agente (los de un mismo agente comparten su casilla, y el que llega mientras trabaja espera su turno: la
// cabecera del grupo junta todas sus llegadas en una línea), un hilo nuevo cada vez, o un comando que corre solo.
// Las dependencias que se declaran (`despues`: usa lo que deja otro) se dibujan al elegir un proceso, con líneas en
// ángulo recto desde la corrida de la que sale hasta la que la usa. Aquí solo se dibuja; lo que se hace (elegir, ir a
// otro día, crear) está en periodicos.ts.

import type * as cli from '../../../cli';
import { esc } from '../../../estilo';
import * as S from '../../../componentes/senales';
import type { Pieza } from '../../../componentes/item';
import { I } from '../../../web/iconos';

export type Modo = 'dia' | 'semana';

/** Dos corridas que llegan al mismo agente con menos de esto (en minutos) se juntan en su casilla. */
export const COLA_MIN = 15;
const DIA = 1440;

const DIAS = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'];
const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
const dos = (n: number) => String(n).padStart(2, '0');

/** «jue 12 nov»; sin el mes, «jue 12». */
export function fechaCorta(iso: string, mes = true): string {
    const f = new Date(`${iso}T12:00:00`);
    return `${DIAS[f.getDay()]} ${f.getDate()}${mes ? ` ${MESES[f.getMonth()]}` : ''}`;
}

/** Una fecha más `n` días, sin pasar por la zona de nadie. */
export function sumarDias(iso: string, n: number): string {
    const f = new Date(`${iso}T12:00:00Z`);
    f.setUTCDate(f.getUTCDate() + n);
    return f.toISOString().slice(0, 10);
}

/** El lunes de la semana de ese día (la semana de los periódicos va de lunes a domingo: corren también el fin de semana). */
export function lunesDe(iso: string): string {
    const d = new Date(`${iso}T12:00:00Z`).getUTCDay();
    return sumarDias(iso, d === 0 ? -6 : 1 - d);
}

const entre = (a: string, b: string) => Math.round((Date.parse(`${b}T00:00:00Z`) - Date.parse(`${a}T00:00:00Z`)) / 864e5);
const hm = (min: number) => `${dos(Math.floor(min / 60))}:${dos(min % 60)}`;

/** Un grupo de filas: a quién le llegan sus corridas. */
export interface Grupo {
    clave: string;
    nombre: string;
    ayuda: string;
    agente?: cli.JsonAgentePer;
    procesos: cli.JsonPeriodico[];
}

/** Lo que dice una corrida cuando se junta con otra en la casilla de su agente: con cuál, y cuántos minutos antes llegó. */
export interface Junta { con: string; antes: number }

/** Lo leído, con lo que el dibujo necesita ya calculado: en qué minuto de la ventana cae cada corrida, los grupos y
 *  dónde se juntan. */
export interface Calendario {
    d: cli.JsonCalendarioPer;
    grupos: Grupo[];
    /** `nombre|en` → con quién se junta */
    juntas: Map<string, Junta>;
    /** el minuto de ahora dentro de la ventana, o null si cae fuera */
    ahora: number | null;
    hoy: string;
}

/** El minuto de una corrida desde el principio de la ventana. */
export const tDe = (desde: string, c: cli.JsonCorrida) => entre(desde, c.dia) * DIA + c.min;

const destinoDe = (p: cli.JsonPeriodico) => p.destino ?? { tipo: p.tipo === 'mensaje' ? (p.agente ? 'agente' : 'hilo') : 'comando', agente: p.agente ?? '', inferido: false };

export function calendario(d: cli.JsonCalendarioPer): Calendario {
    const porClave = new Map<string, Grupo>();
    for (const p of d.procesos) {
        const dst = destinoDe(p);
        const clave = dst.tipo === 'agente' ? `agente:${dst.agente}` : dst.tipo;
        let g = porClave.get(clave);
        if (!g) {
            const agente = (d.agentes ?? []).find(a => a.clave === dst.agente);
            g = dst.tipo === 'agente'
                ? { clave, nombre: agente?.nombre ?? dst.agente, agente, procesos: [],
                    ayuda: `se los encarga a ${agente?.nombre ?? dst.agente}: comparten su casilla, y el que llega mientras trabaja espera su turno` }
                : dst.tipo === 'hilo'
                    ? { clave, nombre: 'hilo nuevo', procesos: [], ayuda: 'abren un hilo nuevo cada vez, con el agente y el prompt' }
                    : { clave, nombre: 'comandos', procesos: [], ayuda: 'una línea de shell, sin agente' };
            porClave.set(clave, g);
        }
        g.procesos.push(p);
    }
    const primera = (p: cli.JsonPeriodico) => Math.min(...(p.corridas ?? []).map(c => c.min), Infinity);
    for (const g of porClave.values()) g.procesos.sort((a, b) => primera(a) - primera(b) || a.nombre.localeCompare(b.nombre));
    const orden = (g: Grupo) => (g.clave.startsWith('agente:') ? 0 : g.clave === 'hilo' ? 1 : 2);
    const grupos = [...porClave.values()].sort((a, b) => orden(a) - orden(b) || a.nombre.localeCompare(b.nombre));

    // en la casilla de un agente: la que llega poco después de otra (de otro proceso) espera su turno
    const juntas = new Map<string, Junta>();
    for (const g of grupos.filter(x => x.agente || x.clave.startsWith('agente:'))) {
        const todas = g.procesos.flatMap(p => (p.corridas ?? []).filter(c => c.estado !== 'sin-registro' && c.estado !== 'pausado')
            .map(c => ({ p: p.nombre, c, t: tDe(d.desde, c) }))).sort((a, b) => a.t - b.t);
        for (let i = 1; i < todas.length; i++) {
            const previa = [...todas.slice(0, i)].reverse().find(x => x.p !== todas[i].p);
            if (previa && todas[i].t - previa.t < COLA_MIN) juntas.set(`${todas[i].p}|${todas[i].c.en}`, { con: previa.p, antes: todas[i].t - previa.t });
        }
    }
    const hoy = d.ahora.slice(0, 10);
    const minAhora = entre(d.desde, hoy) * DIA + Number(d.ahora.slice(11, 13)) * 60 + Number(d.ahora.slice(14, 16));
    return { d, grupos, juntas, ahora: minAhora >= 0 && minAhora <= d.dias * DIA ? minAhora : null, hoy };
}

/** Los que usa un proceso (declarados), los que lo usan a él, y con quién comparte casilla en la ventana. */
export function relaciones(cal: Calendario, nombre: string): { usa: string[]; loUsan: string[]; juntas: { con: string; en: string; antes: number }[] } {
    const p = cal.d.procesos.find(x => x.nombre === nombre);
    const juntas: { con: string; en: string; antes: number }[] = [];
    for (const [k, j] of cal.juntas) {
        const [n, en] = k.split('|');
        if (n === nombre) juntas.push({ con: j.con, en, antes: j.antes });
        else if (j.con === nombre) juntas.push({ con: n, en, antes: -j.antes });
    }
    return { usa: p?.despues ?? [], loUsan: cal.d.procesos.filter(x => x.despues?.includes(nombre)).map(x => x.nombre), juntas };
}

/** Lo que dice una corrida al pasar el mouse. */
function ayudaCorrida(p: cli.JsonPeriodico, c: cli.JsonCorrida, junta: Junta | undefined, agente: string): string {
    const que: Record<string, string> = {
        bien: 'corrió', corrio: 'corrió (de cómo salió no quedó nota)', fallo: 'falló', saltado: 'se saltó', corriendo: 'corriendo ahora',
        falto: 'le tocaba y no hay rastro de que corriera', 'sin-registro': 'en su horario; de antes de que se anotara',
        proxima: 'viene', pausado: 'en su horario, pero está pausado',
    };
    return [`${p.nombre} · ${fechaCorta(c.dia, false)} ${hm(c.min)}${c.manual ? ' · a mano, fuera de su horario' : ''}`,
        que[c.estado] ?? c.estado, c.resultado ?? '',
        junta ? `llega ${junta.antes} min después de ${junta.con}: si ${agente} sigue trabajando, espera su turno en la casilla` : '',
    ].filter(Boolean).join('\n');
}

const pos = (t: number, total: number) => `${((t / total) * 100).toFixed(3)}%`;

/** El eje de arriba: las horas (un día) o los días (una semana). */
function htmlEje(cal: Calendario, modo: Modo): string {
    const { d } = cal;
    const total = d.dias * DIA;
    const marcas: string[] = [];
    if (modo === 'dia') {
        for (let h = 0; h < 24; h += 3) marcas.push(`<span class="cr-marca" style="left:${pos(h * 60, total)}">${dos(h)}</span>`);
    } else {
        for (let i = 0; i < d.dias; i++) {
            const f = sumarDias(d.desde, i);
            marcas.push(`<a class="cr-marca dia${f === cal.hoy ? ' hoy' : ''}" style="left:${pos(i * DIA, total)};width:${pos(DIA, total)}" data-accion="per-ver-dia" data-valor="${esc(f)}" title="ver el ${esc(fechaCorta(f))} en el día">${esc(DIAS[new Date(`${f}T12:00:00`).getDay()])}<span class="num">&nbsp;${Number(f.slice(8))}</span></a>`);
        }
    }
    return `<div class="cr-eje"><span class="cr-et"></span><div class="cr-tiempo">${marcas.join('')}</div></div>`;
}

/** Las líneas verticales de fondo (cada tres horas, o entre los días) y la de ahora. */
function htmlRejilla(cal: Calendario, modo: Modo): string {
    const total = cal.d.dias * DIA;
    const h: string[] = [];
    if (modo === 'dia') for (let x = 3; x < 24; x += 3) h.push(`<span class="cr-v" style="left:${pos(x * 60, total)}"></span>`);
    else for (let i = 1; i < cal.d.dias; i++) h.push(`<span class="cr-v dia" style="left:${pos(i * DIA, total)}"></span>`);
    if (cal.ahora !== null) h.push(`<span class="cr-ahora" style="left:${pos(cal.ahora, total)}" title="ahora, ${esc(cal.d.ahora.slice(11, 16))}"></span>`);
    return `<div class="cr-rejilla">${h.join('')}</div>`;
}

/** Las líneas en ángulo recto del elegido: de la corrida de la que sale cada una (la última antes, en la ventana)
 *  bajando o subiendo a la fila de la que la usa, y por su línea hasta su corrida. */
function htmlConectores(cal: Calendario, filas: Map<string, number>, sel: string): string {
    const { d } = cal;
    const total = d.dias * DIA;
    const de = (n: string) => d.procesos.find(x => x.nombre === n);
    const pares: [string, string][] = [...(de(sel)?.despues ?? []).map(u => [u, sel] as [string, string]),
        ...d.procesos.filter(x => x.despues?.includes(sel)).map(x => [sel, x.nombre] as [string, string])];
    const h: string[] = [];
    const vistos = new Set<string>();
    for (const [u, b] of pares) {
        const iu = filas.get(u), ib = filas.get(b);
        if (iu === undefined || ib === undefined) continue;
        const ts = (n: string) => (de(n)?.corridas ?? []).filter(c => c.estado !== 'sin-registro').map(c => tDe(d.desde, c)).sort((x, y) => x - y);
        const tu = ts(u);
        for (const tb of ts(b)) {
            const ta = [...tu].reverse().find(t => t <= tb);
            if (ta === undefined) continue;
            const v = `${u}|${ta}|${b}`;
            if (!vistos.has(v)) {
                vistos.add(v);
                h.push(`<span class="cr-con v" style="left:${pos(ta, total)};top:calc(var(--cr-fila) * ${Math.min(iu, ib) + .5});height:calc(var(--cr-fila) * ${Math.abs(ib - iu)})"></span>`);
            }
            h.push(`<span class="cr-con h" style="left:${pos(ta, total)};width:${pos(tb - ta, total)};top:calc(var(--cr-fila) * ${ib + .5})"></span>`);
        }
    }
    return h.length ? `<div class="cr-sobre">${h.join('')}</div>` : '';
}

/** El calendario entero: el eje, y cada grupo con su cabecera y sus filas. `sel`, el proceso elegido. */
export function htmlCalendario(cal: Calendario, modo: Modo, sel: string): string {
    const { d } = cal;
    const total = d.dias * DIA;
    const filas = new Map<string, number>();
    const rel = new Set(sel ? [...relaciones(cal, sel).usa, ...relaciones(cal, sel).loUsan] : []);
    const cuerpo: string[] = [];
    let i = 0;
    for (const g of cal.grupos) {
        // la cabecera de un agente junta en su línea todo lo que le llega: ahí se ve dónde se amontona
        const llegadas = g.clave.startsWith('agente:') ? g.procesos.flatMap(p => (p.corridas ?? [])
            .filter(c => c.estado !== 'sin-registro' && c.estado !== 'pausado').map(c => {
                const junta = cal.juntas.get(`${p.nombre}|${c.en}`);
                const pieza: Pieza = { circulo: { tam: 'punto' }, tono: junta ? 'atencion' : 'tenue' };
                return `<span class="cr-c" style="left:${pos(tDe(d.desde, c), total)}">${S.enLinea(pieza)}</span>`;
            })) : [];
        const nJuntas = g.procesos.reduce((n, p) => n + (p.corridas ?? []).filter(c => cal.juntas.has(`${p.nombre}|${c.en}`) && c.estado === 'proxima').length, 0);
        // un agente, con su ícono (o su inicial, como en la barra); un hilo nuevo, el de la terminal; un comando, el de una acción
        const icono = g.clave.startsWith('agente:') ? esc(g.agente?.icono || g.nombre.slice(0, 1).toUpperCase()) : `<span class="i">${g.clave === 'hilo' ? I.terminal : I.accion}</span>`;
        cuerpo.push(`<div class="cr-grupo" title="${esc(g.ayuda)}"><span class="cr-et"><span class="cr-icono">${icono}</span>`
            + `<b>${esc(g.nombre)}</b>${nJuntas ? `<span class="cr-tras atencion" title="de las que vienen, las que llegan menos de ${COLA_MIN} min después de otra">${nJuntas} ${nJuntas === 1 ? 'se junta' : 'se juntan'}</span>` : ''}</span>`
            + `<div class="cr-linea casilla">${llegadas.join('')}</div></div>`);
        i++;
        for (const p of g.procesos) {
            filas.set(p.nombre, i++);
            const agente = g.nombre;
            const cs = (p.corridas ?? []).map(c => {
                const junta = cal.juntas.get(`${p.nombre}|${c.en}`);
                const pieza = S.corrida(c.estado, !!junta && c.estado === 'proxima', ayudaCorrida(p, c, junta, agente));
                return `<span class="cr-c${c.manual ? ' manual' : ''}" style="left:${pos(tDe(d.desde, c), total)}">${S.enLinea(pieza)}</span>`;
            });
            const nota = !cs.length ? `<span class="cr-nota">${p.activo ? (p.proxima ? `la próxima: ${esc(fechaCorta(p.proxima.slice(0, 10)))} ${esc(p.proxima.slice(11, 16))}` : 'no le toca') : 'pausado'}</span>` : '';
            const tras = p.despues?.length ? `<span class="cr-tras" title="usa lo que dejan: ${esc(p.despues.join(', '))}">tras ${esc(p.despues.join(', '))}</span>` : '';
            const clases = ['cr-fila', p.nombre === sel ? 'sel' : '', rel.has(p.nombre) ? 'rel' : '', p.activo ? '' : 'pausado'].filter(Boolean).join(' ');
            cuerpo.push(`<div class="${clases}" data-accion="per-sel" data-valor="${esc(p.nombre)}" title="${esc(`${p.descripcion || p.nombre}\nclic: lo que es, de qué depende y qué hacer con él`)}">`
                + `<span class="cr-et"><span class="cr-n">${esc(p.nombre)}</span>${tras}</span>`
                + `<div class="cr-linea">${cs.join('')}${nota}</div></div>`);
        }
    }
    return `<div class="corridas modo-${modo}">${htmlEje(cal, modo)}<div class="cr-cuerpo">${htmlRejilla(cal, modo)}`
        + `${sel ? htmlConectores(cal, filas, sel) : ''}${cuerpo.join('')}</div></div>`;
}

/** Qué quiere decir cada círculo, en una línea. */
export function htmlLeyenda(): string {
    const c = (estado: string, dice: string, cola = false) => `<span>${S.enLinea(S.corrida(estado, cola))} ${esc(dice)}</span>`;
    return `<div class="cr-leyenda">${c('bien', 'corrió')}${c('proxima', 'viene')}${c('proxima', 'se junta con otro en la casilla de su agente', true)}`
        + `${c('fallo', 'falló')}${c('falto', 'le tocaba y no corrió')}${c('saltado', 'se saltó')}${c('sin-registro', 'sin registro')}</div>`;
}

/** Sus horas en palabras, de lo que se ve en la ventana: «07:00 · 09:00 · 11:00, lun a vie». */
export function horasDe(cal: Calendario, p: cli.JsonPeriodico): string {
    const cs = (p.corridas ?? []).filter(c => !c.manual);
    if (!cs.length) return '';
    const mins = [...new Set(cs.map(c => c.min))].sort((a, b) => a - b);
    const dias = [...new Set(cs.map(c => new Date(`${c.dia}T12:00:00`).getDay()))];
    const semana = cal.d.dias >= 7 && dias.length < 7 ? `, ${[1, 2, 3, 4, 5, 6, 0].filter(x => dias.includes(x)).map(x => DIAS[x]).join(' ')}` : '';
    const lista = mins.length > 8 ? `${mins.slice(0, 3).map(hm).join(' · ')} … ${hm(mins[mins.length - 1])} (${mins.length} al día)` : mins.map(hm).join(' · ');
    return `${lista}${semana}`;
}
