// «tareas › rutinas» (prototipo, /componentes#rutinas): lo que se repite, con la prueba de que se hizo. Solo el
// prototipo, con rutinas inventadas sobre el catálogo del inventario de la gerencia (§4): el modelo de datos de verdad
// está propuesto en docs/propuestas/rutinas.md y no existe todavía. Lo que se aprieta aquí no hace nada: dice qué haría.
//
//   tareas                                    foco · lista · esperando · rutinas     ↻
//   buscar ___________
//   ▽ tuyas 12  de otros 2  de agentes 3
//   ▾ ATRASADAS  3                                                        ← la vista calcula el estado con la prueba
//     ● 👤 1:1 con Carla · cada dos semanas                    -7d · hace 3sem
//          ↳ prueba: la cita realizada y su nota en la ficha
//   ▾ TOCA HOY  3 · ▾ ESTA SEMANA  2 · ▸ AL DÍA  7 · ▾ SIN PRUEBA DEFINIDA  3 (✓ a mano, solo aquí)
//
// Una rutina dice cada cuánto (`cada`), quién la hace, qué la prepara (un periódico o una skill) y con qué se sabe que se
// hizo (`prueba`). La vista busca la última prueba y calcula cuándo vuelve a tocar: antes de hoy, atrasada; hoy, toca
// hoy; antes del domingo, esta semana; después, al día. La que no dice su prueba no se puede calcular: va en «sin prueba
// definida» y es la única que se marca a mano.

import { esc, normalizar } from '../estilo';
import { I } from '../web/iconos';
import { barraBuscar } from './buscador';
import { filtros } from './filtros';
import { item, pieza, type Pieza } from './item';
import { barra as barraPantalla } from './pantalla';
import { seccion } from './seccion';

/** El día inventado del prototipo: jueves 26 de noviembre de 2026, a las 10:30. */
export const HOY = '2026-11-26';
export const AHORA_MIN = 10 * 60 + 30;

export type Estado = 'atrasada' | 'hoy' | 'semana' | 'aldia' | 'sinprueba';

/** Cada cuánto: un día hábil, un día de la semana (0 domingo … 6 sábado), cada N días, cada mes o trimestre, o lo que
 *  diga el calendario (la próxima reunión de la serie). */
export type Cada =
    | { tipo: 'habil' }
    | { tipo: 'semana'; dia: number }
    | { tipo: 'dias'; n: number }
    | { tipo: 'meses'; n: number }
    | { tipo: 'calendario'; serie: string };

/** Con qué se sabe que se hizo. Sin esto, la rutina se marca a mano. */
export interface Prueba {
    tipo: 'archivo' | 'minuta' | 'cita' | 'resultado' | 'tarea' | 'sello' | 'linea';
    /** dónde se busca, en palabras de la persona */
    donde: string;
    /** lo que la prueba no prueba («que exista no prueba que se leyó») */
    ojo?: string;
}

export interface Rutina {
    clave: string;
    nombre: string;
    cada: Cada;
    /** «yo», una persona o un agente */
    quien: { tipo: 'yo' | 'persona' | 'agente'; nombre: string };
    /** lo que la deja lista: un periódico o una skill */
    prepara?: { tipo: 'periodico' | 'skill'; nombre: string };
    prueba?: Prueba;
    /** la última vez que se hizo: la fecha de la última prueba (o de la última marca, si se marca a mano); null, nunca */
    ultima: string | null;
    /** con `cada: calendario`, la próxima reunión de la serie que todavía no tiene su prueba */
    proxima?: string;
    /** por qué no tiene prueba todavía (lo que dice el inventario: «por definir», «¿sigue?») */
    porDefinir?: string;
}

// ── las fechas, como texto AAAA-MM-DD (al mediodía UTC: ningún cambio de hora las corre de día) ──

const fecha = (iso: string): Date => new Date(`${iso}T12:00:00Z`);
const texto = (d: Date): string => d.toISOString().slice(0, 10);
export const sumar = (iso: string, dias: number): string => { const d = fecha(iso); d.setUTCDate(d.getUTCDate() + dias); return texto(d); };
const sumarMeses = (iso: string, n: number): string => { const d = fecha(iso); d.setUTCMonth(d.getUTCMonth() + n); return texto(d); };
const diaSemana = (iso: string): number => fecha(iso).getUTCDay();
/** Los días de `a` a `b` (negativo si `b` es antes). */
export const entre = (a: string, b: string): number => Math.round((fecha(b).getTime() - fecha(a).getTime()) / 86400000);
/** El domingo de la semana de `iso` (la semana va de lunes a domingo). */
export const domingo = (iso: string): string => sumar(iso, (7 - diaSemana(iso)) % 7);

/** Cuándo vuelve a tocar: el primer día que le toca después de la última vez (sin última, desde hoy, que cuenta). */
export function toca(r: Rutina, hoy = HOY): string {
    const c = r.cada;
    if (c.tipo === 'calendario') return r.proxima ?? hoy;
    if (!r.ultima) return hoy;
    if (c.tipo === 'habil') { let d = sumar(r.ultima, 1); while ([0, 6].includes(diaSemana(d))) d = sumar(d, 1); return d; }
    if (c.tipo === 'semana') { let d = sumar(r.ultima, 1); while (diaSemana(d) !== c.dia) d = sumar(d, 1); return d; }
    if (c.tipo === 'dias') return sumar(r.ultima, c.n);
    return sumarMeses(r.ultima, c.n);
}

/** El estado que calcula la vista: con la prueba, contra el día de hoy; sin prueba, no se calcula. */
export function estado(r: Rutina, hoy = HOY): Estado {
    if (!r.prueba) return 'sinprueba';
    const t = toca(r, hoy);
    if (t < hoy) return 'atrasada';
    if (t === hoy) return 'hoy';
    // lo de cada día, hecho hoy, está al día: que vuelva a tocar mañana no es algo de esta semana
    if (t <= domingo(hoy) && r.cada.tipo !== 'habil') return 'semana';
    return 'aldia';
}

const DIAS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];
/** Cada cuánto, en palabras: «cada día hábil», «cada lunes», «cada dos semanas», «cada mes», «según el calendario». */
export function cadaTexto(c: Cada): string {
    if (c.tipo === 'habil') return 'cada día hábil';
    if (c.tipo === 'semana') return `cada ${DIAS[c.dia]}`;
    if (c.tipo === 'dias') return c.n === 7 ? 'cada semana' : c.n === 14 ? 'cada dos semanas' : `cada ${c.n} días`;
    if (c.tipo === 'meses') return c.n === 1 ? 'cada mes' : c.n === 3 ? 'cada trimestre' : `cada ${c.n} meses`;
    return `según el calendario (${c.serie})`;
}

const PRUEBA_TEXTO: Record<Prueba['tipo'], string> = {
    archivo: 'el archivo', minuta: 'la minuta', cita: 'la cita realizada', resultado: 'lo que dejó el periódico',
    tarea: 'la tarea cerrada', sello: 'el sello', linea: 'la línea',
};
/** La prueba en palabras: «el archivo del día en planes/». */
export const pruebaTexto = (p: Prueba): string => `${PRUEBA_TEXTO[p.tipo]} ${p.donde}`;

// ── las rutinas inventadas: el catálogo del inventario §4, sin nombres de verdad ──

export const RUTINAS: Rutina[] = [
    { clave: 'plan-dia', nombre: 'Plan del día', cada: { tipo: 'habil' }, quien: { tipo: 'yo', nombre: 'tú' },
        prepara: { tipo: 'periodico', nombre: 'planear' }, prueba: { tipo: 'archivo', donde: 'del día en planes/' }, ultima: '2026-11-26' },
    { clave: 'retro-dia', nombre: 'Retro del día', cada: { tipo: 'habil' }, quien: { tipo: 'yo', nombre: 'tú' },
        prepara: { tipo: 'periodico', nombre: 'planear-retro' }, ultima: '2026-11-18', porDefinir: 'su periódico está pausado: ¿sigue?' },
    { clave: 'plan-semana', nombre: 'Plan de la semana', cada: { tipo: 'semana', dia: 0 }, quien: { tipo: 'yo', nombre: 'tú' },
        prepara: { tipo: 'periodico', nombre: 'planear-semana' }, prueba: { tipo: 'resultado', donde: 'planear-semana, de ese domingo' }, ultima: '2026-11-22' },
    { clave: 'horas', nombre: 'Registro de horas', cada: { tipo: 'semana', dia: 5 }, quien: { tipo: 'yo', nombre: 'tú' },
        prepara: { tipo: 'skill', nombre: '/horas' }, prueba: { tipo: 'sello', donde: 'de la semana en la planilla de horas' }, ultima: '2026-11-13' },
    { clave: 'tablero', nombre: 'Revisión del tablero', cada: { tipo: 'semana', dia: 1 }, quien: { tipo: 'yo', nombre: 'tú' },
        prepara: { tipo: 'periodico', nombre: 'tablero' }, prueba: { tipo: 'archivo', donde: 'de la semana en tablero/datos/', ojo: 'que exista no prueba que lo leíste' },
        ultima: '2026-11-23' },
    { clave: 'daily', nombre: 'Daily del área', cada: { tipo: 'calendario', serie: 'lunes a viernes, 9:00' }, quien: { tipo: 'yo', nombre: 'tú' },
        prepara: { tipo: 'skill', nombre: '/preparar-reunion' }, prueba: { tipo: 'minuta', donde: 'del día en area/reuniones/' }, ultima: '2026-11-25', proxima: '2026-11-26' },
    { clave: 'cursos', nombre: 'Revisión de la producción de cursos', cada: { tipo: 'calendario', serie: 'martes por medio' }, quien: { tipo: 'yo', nombre: 'tú' },
        prueba: { tipo: 'minuta', donde: 'en la iniciativa de cursos' }, ultima: '2026-11-17', proxima: '2026-12-01' },
    { clave: 'lideres', nombre: 'Reunión de líderes', cada: { tipo: 'calendario', serie: 'jueves, 15:00' }, quien: { tipo: 'yo', nombre: 'tú' },
        prepara: { tipo: 'skill', nombre: '/preparar-reunion' }, prueba: { tipo: 'minuta', donde: 'en empresa/reuniones/' }, ultima: '2026-11-19', proxima: '2026-11-26' },
    { clave: '1a1-leo', nombre: '1:1 con Leo', cada: { tipo: 'dias', n: 14 }, quien: { tipo: 'yo', nombre: 'tú' },
        prepara: { tipo: 'skill', nombre: '/preparar-reunion' }, prueba: { tipo: 'cita', donde: 'y su nota en la ficha de Leo' }, ultima: '2026-11-12' },
    { clave: '1a1-carla', nombre: '1:1 con Carla', cada: { tipo: 'dias', n: 14 }, quien: { tipo: 'yo', nombre: 'tú' },
        prepara: { tipo: 'skill', nombre: '/preparar-reunion' }, prueba: { tipo: 'cita', donde: 'y su nota en la ficha de Carla' }, ultima: '2026-11-05' },
    { clave: '1a1-tomas', nombre: '1:1 con Tomás', cada: { tipo: 'dias', n: 7 }, quien: { tipo: 'yo', nombre: 'tú' },
        prepara: { tipo: 'skill', nombre: '/preparar-reunion' }, prueba: { tipo: 'cita', donde: 'y su nota en la ficha de Tomás' }, ultima: '2026-11-24' },
    { clave: 'semanal', nombre: 'Revisión semanal', cada: { tipo: 'semana', dia: 5 }, quien: { tipo: 'yo', nombre: 'tú' },
        ultima: null, porDefinir: 'falta decir con qué se sabe que se hizo' },
    { clave: 'comercial', nombre: 'Resumen comercial', cada: { tipo: 'dias', n: 14 }, quien: { tipo: 'agente', nombre: 'Secretaría' },
        prepara: { tipo: 'skill', nombre: '/resumen-comercial' }, prueba: { tipo: 'tarea', donde: 'de enviarlo (el borrador lo deja el agente)' }, ultima: '2026-11-16' },
    { clave: 'diagnostico', nombre: 'Diagnóstico del área', cada: { tipo: 'meses', n: 1 }, quien: { tipo: 'agente', nombre: 'Analista' },
        prueba: { tipo: 'archivo', donde: 'del mes en diagnosticos/' }, ultima: '2026-10-28' },
    { clave: 'retro-metodo', nombre: 'Retro del método', cada: { tipo: 'meses', n: 1 }, quien: { tipo: 'agente', nombre: 'Analista' },
        prueba: { tipo: 'linea', donde: 'del mes en la bitácora de versiones del método' }, ultima: '2026-10-24' },
    { clave: 'direccion', nombre: 'Revisión del área con la dirección', cada: { tipo: 'calendario', serie: 'el primer jueves del mes' }, quien: { tipo: 'yo', nombre: 'tú' },
        prepara: { tipo: 'skill', nombre: '/preparar-reunion' }, prueba: { tipo: 'cita', donde: 'y su nota' }, ultima: '2026-11-05', proxima: '2026-12-03' },
    { clave: 'decisiones', nombre: 'Revisión de decisiones e hipótesis', cada: { tipo: 'semana', dia: 5 }, quien: { tipo: 'persona', nombre: 'Leo' },
        ultima: '2026-11-20', porDefinir: 'falta decir con qué se sabe que se hizo' },
    { clave: 'trimestre', nombre: 'Desarrollo de cada persona, clima y prioridades', cada: { tipo: 'meses', n: 3 }, quien: { tipo: 'yo', nombre: 'tú' },
        ultima: null, porDefinir: 'falta decir con qué se sabe que se hizo' },
];

// ── la vista ──

interface Grupo { clave: Estado; nombre: string; ayuda: string; abierta: boolean }
export const GRUPOS: Grupo[] = [
    { clave: 'atrasada', nombre: 'atrasadas', ayuda: 'le tocaba antes de hoy y no hay prueba de que se hizo', abierta: true },
    { clave: 'hoy', nombre: 'toca hoy', ayuda: 'le toca hoy y todavía no está su prueba', abierta: true },
    { clave: 'semana', nombre: 'esta semana', ayuda: 'le toca antes del domingo', abierta: true },
    { clave: 'aldia', nombre: 'al día', ayuda: 'su prueba está y no le toca hasta la semana que viene', abierta: false },
    { clave: 'sinprueba', nombre: 'sin prueba definida', ayuda: 'no dice con qué se sabe que se hizo: la vista no lo calcula, y es la única que se marca a mano', abierta: true },
];

/** El estado en su círculo (componentes/senales.ts, la gramática): atrasada, el chico lleno de alerta; toca hoy, el aro
 *  de lo que falta, en el de cuidado; esta semana, el mismo aro, tenue; al día, nada (no hay nada que decir); sin prueba,
 *  el aro chico tenue de lo que no se puede saber. */
export function piezaEstado(e: Estado, ayuda: string): Pieza | null {
    if (e === 'atrasada') return { circulo: { tam: 'chico' }, tono: 'peligro', ayuda };
    if (e === 'hoy') return { circulo: { lleno: 0 }, tono: 'atencion', ayuda };
    if (e === 'semana') return { circulo: { lleno: 0 }, tono: 'tenue', ayuda };
    if (e === 'sinprueba') return { circulo: { tam: 'chico', lleno: 0 }, tono: 'tenue', ayuda };
    return null;
}

/** Quién la hace, en su ranura: tú (la persona, en el acento), otra persona (en la tinta de lo ajeno), un agente. */
function piezaQuien(q: Rutina['quien']): Pieza {
    if (q.tipo === 'agente') return { icono: I.agente, tono: 'agente', ayuda: `la hace el agente ${q.nombre}` };
    return { icono: I.persona, tono: q.tipo === 'yo' ? 'acento' : 'remoto', ayuda: q.tipo === 'yo' ? 'la haces tú' : `la hace ${q.nombre}` };
}

/** Cuánto hace, corto: «hoy», «ayer», «5d», «3sem», «2m». */
export function hace(dias: number): string {
    if (dias <= 0) return 'hoy';
    if (dias === 1) return 'ayer';
    if (dias < 14) return `${dias}d`;
    if (dias < 60) return `${Math.floor(dias / 7)}sem`;
    return `${Math.floor(dias / 30)}m`;
}

/** La meta: cuándo vuelve a tocar (lo atrasado en rojo, hoy en el de cuidado) y cuándo se hizo la última vez. */
export function meta(r: Rutina, hoy = HOY): Pieza {
    const e = estado(r, hoy), t = toca(r, hoy), d = entre(hoy, t);
    const ultima = r.ultima ? `hace ${hace(entre(r.ultima, hoy))}` : 'nunca';
    // sin prueba no se calcula: cuándo tocaría va sin el color de lo atrasado
    const cuando: Pieza = e === 'sinprueba' ? { texto: d === 0 ? 'hoy' : `${d}d` }
        : d < 0 ? { texto: `${d}d`, tono: 'peligro' } : d === 0 ? { texto: 'hoy', tono: 'atencion' } : { texto: `${d}d` };
    const ayuda = `${e === 'sinprueba' ? 'tocaría' : 'toca'} el ${DIAS[diaSemana(t)]} ${t}${d < 0 ? ` (hace ${-d} días)` : ''} · `
        + (r.ultima ? `${e === 'sinprueba' ? 'marcada a mano' : 'su última prueba'} el ${r.ultima}` : 'nunca hecha');
    return { html: `${pieza(cuando, 'item-vence')} · ${esc(ultima)}`, ayuda };
}

/** Una rutina en sus filas: el estado, quién la hace, su nombre y cada cuánto, la meta; debajo, tenue, su prueba y qué
 *  la prepara. Al pasar el mouse: ver la prueba, ir a lo que la prepara y, solo si no tiene prueba, marcarla hecha. */
export function filas(r: Rutina, hoy = HOY): string {
    const e = estado(r, hoy);
    const g = GRUPOS.find(x => x.clave === e)!;
    const busca = normalizar([r.nombre, r.quien.nombre, cadaTexto(r.cada), r.prueba ? pruebaTexto(r.prueba) : '', r.prepara?.nombre ?? ''].join(' '));
    const datos = { busca, quien: r.quien.tipo };
    const acciones = [
        ...(r.prueba ? [{ accion: 'rutinas-prueba', id: r.clave, icono: I.ver, ayuda: `ver la prueba: ${pruebaTexto(r.prueba)}` }] : []),
        ...(r.prepara ? [{ accion: 'rutinas-prepara', id: r.clave, icono: I.agente, tono: 'agente' as const,
            ayuda: `${r.prepara.tipo === 'skill' ? 'la skill' : 'el periódico'} ${r.prepara.nombre}: correrlo ahora` }] : []),
        ...(r.prueba ? [] : [{ accion: 'rutinas-marcar', id: r.clave, icono: I.hecha, ayuda: 'marcarla hecha hoy: sin prueba definida, se marca a mano' }]),
    ];
    const principal = item({
        clases: ['rutina'], accion: 'rutinas-abrir', id: r.clave, datos,
        ayuda: `${r.nombre} · ${cadaTexto(r.cada)}\n${g.nombre}: ${g.ayuda}\nclic: abrir la rutina`,
        inicio: [piezaEstado(e, `${g.nombre}: ${g.ayuda}`), piezaQuien(r.quien)],
        titulo: r.nombre, sufijo: [{ texto: `· ${cadaTexto(r.cada)}`, tono: 'tenue' }],
        meta: meta(r, hoy), acciones, menu: { accion: 'rutinas-menu', id: r.clave, icono: I.menu, ayuda: 'más: cambiar la cadencia, quién, la prueba' },
    });
    const prueba = r.prueba ? `prueba: ${pruebaTexto(r.prueba)}${r.prueba.ojo ? ` (${r.prueba.ojo})` : ''}`
        : `sin prueba: ${r.porDefinir ?? 'se marca a mano'}`;
    const prepara = r.prepara ? ` · la prepara ${r.prepara.tipo === 'skill' ? 'la skill' : 'el periódico'} ${r.prepara.nombre}` : '';
    return principal + item({
        clases: ['rutina', 'rutina-prueba'], accion: 'rutinas-abrir', id: r.clave, datos, apagada: true, hondo: 1,
        inicio: [null, null], prefijo: [{ texto: '↳', tono: 'tenue' }], titulo: `${prueba}${prepara}`,
    });
}

/** El cuerpo de la vista: el buscador, los filtros (quién) y una sección por estado. `plegadas`: las que la persona dio
 *  vuelta (al día empieza plegada). */
export function cuerpo(rutinas = RUTINAS, o: { hoy?: string; plegadas?: Set<string>; filtro?: string } = {}): string {
    const hoy = o.hoy ?? HOY, plegadas = o.plegadas ?? new Set<string>();
    const n = (t: string) => rutinas.filter(r => r.quien.tipo === t).length;
    const visibles = rutinas.filter(r => !o.filtro || r.quien.tipo === o.filtro);
    const h = ['<div class="cat-rut lista-tareas">',
        barraBuscar({ id: 'buscar-rutinas', claseBarra: 'herram', placeholder: 'rutinas', ayuda: 'buscar en el nombre, quién, la prueba y lo que la prepara · ⎋ borra' }),
        filtros({ accion: 'rutinas-filtro', grupos: [{ clave: 'quien', nombre: 'quién', activa: o.filtro ?? '', opciones: [
            { clave: 'yo', nombre: 'tuyas', cuenta: n('yo'), ayuda: 'tuyas: las haces tú' },
            { clave: 'persona', nombre: 'de otros', cuenta: n('persona'), ayuda: 'de otros: las hace otra persona del equipo' },
            { clave: 'agente', nombre: 'de agentes', cuenta: n('agente'), ayuda: 'de agentes: las hace un agente; tú las miras' },
        ] }] })];
    for (const g of GRUPOS) {
        const suyas = visibles.filter(r => estado(r, hoy) === g.clave);
        if (!suyas.length) continue;
        const abierta = plegadas.has(g.clave) ? !g.abierta : g.abierta;
        h.push(`<div class="grupo-rutinas" data-estado="${g.clave}">`, seccion({ clave: `rutinas:${g.clave}`, titulo: g.nombre, cuenta: suyas.length, abierta,
            ayuda: g.ayuda, filas: () => suyas.map(r => filas(r, hoy)).join('') }), '</div>');
    }
    h.push('</div>');
    return h.join('');
}

/** La barra de la pantalla: tareas, con sus cuatro vistas (rutinas, la que se ve) y ↻. */
export function barra(rutinas = RUTINAS, hoy = HOY): string {
    const cuenta = (e: Estado) => rutinas.filter(r => estado(r, hoy) === e).length;
    return barraPantalla({
        nombre: 'tareas', color: 'cian',
        ayuda: `${rutinas.length} rutinas · ${cuenta('atrasada')} atrasadas, ${cuenta('hoy')} tocan hoy · ${cuenta('sinprueba')} sin prueba definida`,
        vistas: [{ accion: 'rutinas-vista', valor: 'foco', icono: I.foco, nombre: 'foco' },
            { accion: 'rutinas-vista', valor: 'lista', icono: I.lista, nombre: 'lista' },
            { accion: 'rutinas-vista', valor: 'esperando', icono: I.reloj, nombre: 'esperando' },
            { accion: 'rutinas-vista', valor: 'rutinas', icono: I.repite, nombre: 'rutinas', si: true,
                ayuda: 'lo que se repite: si se hizo, lo dice su prueba' }],
        acciones: [{ accion: 'rutinas-releer', icono: I.releer, ayuda: 'volver a buscar las pruebas (r)' }],
    });
}

// ── lo que dice un clic, y el estado del prototipo (solo mientras dura la página) ──

const plegadas = new Set<string>();
let filtro = '';

/** La pantalla entera del prototipo: la barra y el cuerpo, con lo plegado y el filtro elegidos. */
export const pantalla = (): string => barra() + cuerpo(RUTINAS, { plegadas, filtro });

const porClave = (k: string) => RUTINAS.find(r => r.clave === k);
const DICE: Record<string, (r: Rutina | undefined, v: string) => string> = {
    'rutinas-abrir': r => `abriría «${r?.nombre}»: su archivo (cada cuánto, quién, qué la prepara, su prueba), las últimas pruebas y, si se marca a mano, sus marcas`,
    'rutinas-prueba': r => `abriría la prueba de «${r?.nombre}»: ${r?.prueba ? pruebaTexto(r.prueba) : ''}`,
    'rutinas-prepara': r => `correría ${r?.prepara?.tipo === 'skill' ? 'la skill' : 'el periódico'} ${r?.prepara?.nombre} para «${r?.nombre}»`,
    'rutinas-marcar': r => `marcaría «${r?.nombre}» hecha hoy (una línea en su historia: no tiene prueba que lo diga)`,
    'rutinas-menu': r => `abriría el menú de «${r?.nombre}»: cambiar cada cuánto, quién la hace, qué la prepara y su prueba`,
    'rutinas-vista': (_, v) => `iría a tareas › ${v}`,
    'rutinas-releer': () => 'volvería a buscar las pruebas de todas',
};

/** Un clic en el prototipo: una sección se pliega, el filtro rige o se suelta (y se repinta); lo demás dice qué haría.
 *  true si era suyo. */
export function atender(t: HTMLElement, avisar: (texto: string) => void, repintar: () => void): boolean {
    if (!t.closest('.cat-rut, .cat-rut-pantalla')) return false;
    const op = t.closest<HTMLElement>('.filtros-op[data-accion="rutinas-filtro"]');
    if (op) { const k = (op.dataset.id ?? '').replace(/^quien:/, ''); filtro = filtro === k ? '' : k; repintar(); return true; }
    const cab = t.closest<HTMLElement>('.item.cabecera[data-accion="seccion"]');
    if (cab) {
        const k = (cab.dataset.id ?? '').replace(/^rutinas:/, '');
        if (plegadas.has(k)) plegadas.delete(k); else plegadas.add(k);
        repintar();
        return true;
    }
    const a = t.closest<HTMLElement>('[data-accion^="rutinas-"]');
    if (!a) return true;
    const dice = DICE[a.dataset.accion ?? ''];
    avisar(dice ? dice(porClave(a.dataset.id ?? ''), a.dataset.valor ?? '') : `haría «${a.dataset.accion}»`);
    return true;
}

// ── las pestañas del catálogo ──

const parrafo = (html: string) => `<p class="dim">${html}</p>`;

const TONO_ESTADO: Record<Estado, string> = { atrasada: 'tono-peligro', hoy: 'tono-atencion', semana: '', aldia: 'tono-exito', sinprueba: 'dim' };
/** El estado de una, en singular (el de su sección es plural: «atrasadas»). */
const UNA: Record<Estado, string> = { atrasada: 'atrasada', hoy: 'toca hoy', semana: 'esta semana', aldia: 'al día', sinprueba: 'sin prueba definida' };

/** «cómo se calcula»: cada rutina inventada con cada cuánto, su prueba, la última, cuándo toca y el estado que sale. */
export function seccionCalculo(): string {
    const filasTabla = RUTINAS.map(r => {
        const e = estado(r, HOY);
        return `<div>${esc(r.nombre)}</div><div class="dim">${esc(cadaTexto(r.cada))}</div>`
            + `<div>${r.prueba ? esc(pruebaTexto(r.prueba)) : `<span class="dim">${esc(r.porDefinir ?? '—')}</span>`}</div>`
            + `<div class="dim">${r.ultima ?? 'nunca'}</div><div>${toca(r)}</div><div class="${TONO_ESTADO[e]}">${UNA[e]}</div>`;
    }).join('');
    return '<section class="cat-tactica">'
        + parrafo('<b>Cómo calcula el estado.</b> De la prueba sale la última vez que se hizo; de cada cuánto, cuándo vuelve a tocar: el día '
            + 'hábil siguiente, el próximo día de la semana que le toca, N días o meses después, o la próxima reunión de su serie en el '
            + 'calendario que todavía no tiene su prueba. Contra hoy: antes, <b>atrasada</b>; hoy, <b>toca hoy</b>; hasta el domingo, '
            + '<b>esta semana</b>; después, <b>al día</b>. La que no dice su prueba no se calcula: va en <b>sin prueba definida</b>, y es la '
            + 'única que se marca a mano (su ✓ deja una línea en su historia, y esa marca hace de prueba).')
        + parrafo(`Las rutinas inventadas de la vista, el jueves ${HOY}:`)
        + `<div class="cat-rut-tabla"><b>rutina</b><b>cada</b><b>prueba</b><b>la última</b><b>toca</b><b>estado</b>${filasTabla}</div></section>`;
}

/** «el archivo»: cómo sería una rutina escrita, tres ejemplos (con prueba de archivo, con cita, sin prueba). */
export function seccionArchivo(): string {
    const ej = (ruta: string, txt: string) => `<figure class="cat-tac-fig"><figcaption class="dim">${esc(ruta)}</figcaption><pre class="cat-rut-pre">${esc(txt)}</pre></figure>`;
    return '<section class="cat-tactica">'
        + parrafo('<b>Un archivo por rutina</b>, como las tareas: arriba sus campos (una clave por línea), después qué es, en prosa, y su '
            + 'historia, que solo crece por el final. Lo abierto del área va en su repositorio; lo de la persona, en el suyo. La propuesta '
            + 'entera, con dónde vive cada una y cómo se busca cada clase de prueba: <code>docs/propuestas/rutinas.md</code>. Todavía no existe: '
            + 'esto es para mirarlo.')
        + '<div class="cat-tac-par">'
        + ej('rutinas/plan-del-dia.md', `---
nombre: Plan del día
cada: día hábil
quien: yo
prepara: periodico:planear
prueba: archivo planes/{fecha}*.md
---
El plan de cada día de trabajo: qué hacer y en qué reunión, con un bloque
estratégico protegido.`)
        + ej('rutinas/1a1-leo.md', `---
nombre: 1:1 con Leo
cada: 14 días
quien: yo
prepara: skill:preparar-reunion
prueba: cita "1:1 Leo" y nota personas/leo.md
---
Cada dos semanas. La nota de la ficha dice lo conversado.`)
        + ej('rutinas/revision-semanal.md', `---
nombre: Revisión semanal
cada: viernes
quien: yo
---
Mirar la semana entera: qué se cumplió, qué se mueve.

## Historia
- 2026-11-13 [hecha] a mano
- 2026-11-20 [hecha] a mano`)
        + '</div></section>';
}

/** «la vista»: la pantalla en un laptop y en un teléfono, con el tema de la primera columna elegida. */
export function seccionVista(marco: (html: string, px: number) => string): string {
    const fig = (px: number, nombre: string) => `<figure class="cat-tac-fig"><figcaption class="dim">${esc(nombre)} · ${px}px · `
        + `<a href="#rutinas/ver/vista" target="_blank" title="la página entera: abrirla en una ventana de ${px}px de ancho">pantalla completa</a></figcaption>`
        + `${marco(pantalla(), px)}</figure>`;
    return '<section class="cat-tactica">'
        + parrafo('<b>Prototipo.</b> «tareas › rutinas»: lo que se repite (el plan del día, los 1:1, la revisión del tablero…) y si se hizo, '
            + 'calculado con su prueba. Una sección por estado: <b>atrasadas</b>, <b>toca hoy</b>, <b>esta semana</b>, <b>al día</b> (plegada) y '
            + '<b>sin prueba definida</b>. Cada fila: el estado en su círculo (al día no lleva: no hay nada que decir), quién la hace (tú, otra '
            + 'persona, un agente), el nombre y cada cuánto, y a la derecha cuándo vuelve a tocar y cuándo se hizo; debajo, tenue, su prueba y '
            + 'qué la prepara. Al pasar el mouse: ver la prueba, correr lo que la prepara y, <b>solo en las que no tienen prueba</b>, marcarla '
            + 'hecha. Las rutinas son inventadas sobre el catálogo del inventario de la gerencia (§4), el jueves 26-nov a las 10:30.')
        + parrafo('Las secciones se pliegan y el filtro «quién» rige de verdad; lo demás dice qué haría.')
        + `<div class="cat-tac-par">${fig(1120, 'laptop')}${fig(412, 'teléfono')}</div></section>`;
}
