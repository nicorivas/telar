// Todo: ver y buscar todo, sin filtros ni topes (docs/propuestas/orden-por-modos.md, pasos 2 y 5). PROTOTIPO: lo muestra
// el catálogo (/componentes#modos-mundos/todo) con datos inventados; la página todavía no lo usa. Nunca es la vista de partida,
// pero siempre está a un paso: su modo en la cabecera, ⌥⇧4, el «ver todo» de Táctica y ⌘K (que va a una cosa; Todo las
// muestra todas).
//
//   TODO  412 en trabajo · y 132 en personal                                             ↻
//   / buscar en todo: tareas, casillas, esperas, correos, hilos, proyectos ________  23 de 412
//
//   sin buscar, las fuentes, cada una entera a un clic:
//   ◔ te esperan   50 · 18 preguntan · la más vieja, hace 6 semanas          +14 en personal  ›
//   ✓ tareas       64 · 9 vencen esta semana · 14 de deuda                    +23 en personal  ›
//
//   buscando, lo hallado por fuente (hasta 4 de cada una, y «+N más en tareas» la abre con lo buscado; filtrado a una
//   fuente, todo lo suyo):
//   ▾ TAREAS  4
//     T42 Armar la [vitrina] con la foto elegida · vitrina                         el plan: hoy
//   ▸ EN OTROS MUNDOS  2                                         ← el mundo ordena, no esconde: lo de los otros, al final
//     T61 Vender la [vitrina] vieja del living · casa                                  personal
//
// Lo sin clasificar se ve en cualquier mundo, con su marca. Da HTML; un clic lleva `data-accion` (`todo-…`) y `data-id`.
// Cómo se ve: media/css/modos.css (con el marco de los modos).

import { esc, normalizar as norm } from '../estilo';
import { I } from '../web/iconos';
import { item, type Pieza } from './item';
import { barraBuscar } from './buscador';
import { filtros } from './filtros';
import * as S from './senales';
import type { Barra } from './pantalla';
import { SIN_CLASIFICAR, tintaMundo, type Mundo } from './modos-mundos';

/** Una fuente: de dónde vienen las cosas (las tareas, el correo, los hilos…), con su ícono y su tinta (la de su pantalla). */
export interface Fuente {
    clave: string; nombre: string; icono: string; color: string;
    /** cuántas en cada mundo, y en «sin-clasificar» */
    cuenta: Record<string, number>;
    /** lo que dice de sí, tenue, por mundo ('' con ambos) */
    dice: Record<string, string>;
}

/** Una cosa de alguna fuente, como la encontraría el buscador. */
export interface Cosa {
    fuente: string; id: string; titulo: string;
    /** antes del título: su código o su clase («T42», «pregunta», «de la vidriería») */
    antes?: string;
    /** dónde vive, corto */
    donde?: string;
    /** al final, tenue (o en su tono): cuándo, en qué estado */
    meta?: string;
    mundo: string;
    /** ya pasó: hecha, leída, descartada */
    pasada?: boolean;
    tono?: 'espera' | 'atencion' | 'exito' | 'acento';
}

/** Cuántas cosas suyas se ven con un mundo puesto: las de ese mundo y las sin clasificar; con ambos, todas. */
export const cuantas = (f: Fuente, puesto: string): number => (puesto
    ? (f.cuenta[puesto] ?? 0) + (f.cuenta[SIN_CLASIFICAR] ?? 0)
    : Object.values(f.cuenta).reduce((n, c) => n + c, 0));
/** Cuántas quedan en los otros mundos (con ambos, ninguna). */
export const enOtros = (f: Fuente, puesto: string): number => (puesto
    ? Object.entries(f.cuenta).filter(([k]) => k !== puesto && k !== SIN_CLASIFICAR).reduce((n, [, c]) => n + c, 0) : 0);
/** Si una cosa es del mundo puesto (o sin clasificar, que se ve en todos). */
export const delMundo = (x: Cosa, puesto: string): boolean => !puesto || x.mundo === puesto || x.mundo === SIN_CLASIFICAR;

/** Cuántas de cada fuente se ven antes del «+N más»: lo justo para elegir dónde seguir. */
export const POR_FUENTE = 4;

export interface PropsTodo {
    fuentes: Fuente[];
    mundos: readonly Mundo[];
    /** el mundo puesto ('' ambos) */
    puesto: string;
    /** lo buscado y lo hallado (de todos los mundos: el componente separa los otros) */
    buscado?: string;
    halladas?: Cosa[];
    /** una fuente entera: sus cosas, en su orden, y cuántas son */
    abierta?: { fuente: string; cosas: Cosa[]; total: number };
    /** buscando, la fuente que rige en el filtro ('' todas) */
    filtro?: string;
    /** buscando, cuántas calzan en total (la búsqueda trae hasta un tope de cada fuente) */
    total?: number;
    /** sin buscar, lo que se dice cuando las fuentes no traen cuentas (leyendo, una falla) */
    aviso?: string;
}

/** El título con lo buscado marcado (en el acento; el mismo largo, nada de tamaño). */
export function resaltar(titulo: string, q: string): string {
    if (!q) return esc(titulo);
    const i = norm(titulo).indexOf(norm(q));
    if (i < 0) return esc(titulo);
    return `${esc(titulo.slice(0, i))}<span class="todo-hallado">${esc(titulo.slice(i, i + q.length))}</span>${esc(titulo.slice(i + q.length))}`;
}

/** El ícono de una fuente, en su tinta. */
const iconoFuente = (f?: Fuente): Pieza | null => (f ? { html: `<span class="i todo-icono" style="color: var(--${esc(f.color)})">${f.icono}</span>`, ayuda: f.nombre } : null);

/** El mundo de una cosa que no es el puesto, en su color: «personal», «sin clasificar». */
function marcaMundo(x: Cosa, mundos: readonly Mundo[], puesto: string): Pieza | undefined {
    if (puesto && x.mundo === puesto) return undefined;
    if (!puesto && x.mundo !== SIN_CLASIFICAR) {
        const m = mundos.find(y => y.clave === x.mundo);
        return m ? { html: `<span class="todo-mundo"${tintaMundo(m)}>${esc(m.nombre)}</span>` } : undefined;
    }
    if (x.mundo === SIN_CLASIFICAR) return { html: '<span class="todo-mundo sin">sin clasificar</span>', ayuda: 'no calza en ningún mundo: se ve en todos' };
    const m = mundos.find(y => y.clave === x.mundo);
    return { html: `<span class="todo-mundo"${tintaMundo(m)}>${esc(m?.nombre ?? x.mundo)}</span>` };
}

/** Una cosa, en una fila: su estado si espera, su código o su clase, el título (con lo buscado marcado), dónde vive y
 *  cuándo; si es de otro mundo o sin clasificar, lo dice en su color. Un clic la abre donde vive. */
export function filaCosa(x: Cosa, p: { q?: string; mundos: readonly Mundo[]; puesto: string; fuente?: Fuente; conFuente?: boolean }): string {
    return item({
        accion: 'todo-abrir', datos: { valor: x.id }, clases: ['todo-cosa'], apagada: x.pasada, ayuda: `${x.titulo}\n\nclic: abrirla donde vive`,
        inicio: [x.tono === 'espera' && !x.pasada ? S.atencion('espera') : null, ...p.conFuente ? [iconoFuente(p.fuente)] : []],
        prefijo: x.antes ? [{ texto: x.antes, tono: 'tenue' }] : [],
        tituloHtml: resaltar(x.titulo, p.q ?? ''),
        sufijo: x.donde ? [{ texto: `· ${x.donde}`, tono: 'tenue' }] : [],
        aviso: marcaMundo(x, p.mundos, p.puesto),
        meta: x.meta ? { texto: x.meta, tono: x.pasada ? 'tenue' : x.tono } : undefined,
    });
}

/** La cabecera de un grupo (una fuente, u «otros mundos»): como las de la barra, con su cuenta tenue. */
const cabecera = (nombre: string, cuenta: number, icono: Pieza | null, clave: string, apagada = false): string => item({
    variante: 'cabecera', accion: 'todo-fuente', datos: { valor: clave }, clases: ['todo-cab'], apagada, ayuda: `${nombre}: verla entera`,
    inicio: [icono], titulo: nombre, sufijo: [{ texto: String(cuenta), tono: 'tenue' }],
    fijas: [{ accion: 'todo-fuente', datos: { valor: clave }, icono: I.adelante, ayuda: `${nombre}, entera` }],
});

/** Sin buscar: cada fuente en una fila, con lo que tiene en el mundo puesto y lo que queda en los otros. */
function lasFuentes(p: PropsTodo): string {
    const otro = (n: number) => {
        const otros = p.mundos.filter(m => m.clave !== p.puesto);
        return n && otros.length === 1 ? { html: `<span class="todo-mundo"${tintaMundo(otros[0])}>+${n} en ${esc(otros[0].nombre)}</span>` }
            : n ? { texto: `+${n} en otros mundos`, tono: 'tenue' as const } : undefined;
    };
    return '<section class="todo-grupo todo-fuentes">' + p.fuentes.map(f => item({
        accion: 'todo-fuente', datos: { valor: f.clave }, clases: ['todo-fuente'], ayuda: `${f.nombre}: verla entera, sin filtros ni topes`,
        inicio: [iconoFuente(f)], titulo: f.nombre,
        // una fuente sin cuentas (un bloque que no se ha leído) va solo con su nombre
        sufijo: [...Object.keys(f.cuenta).length ? [{ texto: String(cuantas(f, p.puesto)) }] : [],
            ...(f.dice[p.puesto] ?? f.dice['']) ? [{ texto: `· ${f.dice[p.puesto] ?? f.dice['']}`, tono: 'tenue' as const }] : []],
        meta: otro(enOtros(f, p.puesto)),
        fijas: [{ accion: 'todo-fuente', datos: { valor: f.clave }, icono: I.adelante, ayuda: `${f.nombre}, entera` }],
    })).join('') + '</section>';
}

/** Buscando: lo hallado del mundo puesto por fuente, hasta POR_FUENTE de cada una (filtrado a una, todo lo suyo); lo de
 *  los otros mundos, al final. */
function loHallado(p: PropsTodo): string {
    const q = p.buscado ?? '';
    const todas = (p.halladas ?? []).filter(x => !p.filtro || x.fuente === p.filtro);
    const aqui = todas.filter(x => delMundo(x, p.puesto)), otras = todas.filter(x => !delMundo(x, p.puesto));
    const tope = p.filtro ? Infinity : POR_FUENTE;
    const h: string[] = [];
    for (const f of p.fuentes) {
        const suyas = aqui.filter(x => x.fuente === f.clave);
        if (!suyas.length) continue;
        h.push(`<section class="todo-grupo" data-fuente="${esc(f.clave)}">`, cabecera(f.nombre, suyas.length, iconoFuente(f), f.clave));
        for (const x of suyas.slice(0, tope)) h.push(filaCosa(x, { q, mundos: p.mundos, puesto: p.puesto, fuente: f }));
        if (suyas.length > tope) {
            h.push(item({ accion: 'todo-fuente', datos: { valor: f.clave }, clases: ['todo-mas'], inicio: [null], titulo: `+${suyas.length - POR_FUENTE} más`,
                sufijo: [{ texto: `en ${f.nombre}, con «${q}»`, tono: 'tenue' }], ayuda: `${f.nombre}, entera, con lo buscado` }));
        }
        h.push('</section>');
    }
    if (!aqui.length) h.push(item({ clases: ['todo-nada'], apagada: true, inicio: [null], titulo: `nada con «${q}» en este mundo` }));
    if (otras.length) {
        // el mundo ordena, no esconde: lo de los otros, al final, cada una con su fuente y su mundo
        h.push('<section class="todo-grupo todo-otros">', item({ variante: 'cabecera', clases: ['todo-cab'], apagada: true, inicio: [{ icono: I.abierto }],
            titulo: 'en otros mundos', sufijo: [{ texto: String(otras.length), tono: 'tenue' }], ayuda: 'lo hallado que no es del mundo puesto' }));
        for (const x of otras) h.push(filaCosa(x, { q, mundos: p.mundos, puesto: p.puesto, fuente: p.fuentes.find(f => f.clave === x.fuente), conFuente: true }));
        h.push('</section>');
    }
    return h.join('');
}

/** Una fuente entera: todas sus cosas en su orden, sin topes, con lo hecho al final y tenue. */
function entera(p: PropsTodo): string {
    const a = p.abierta!;
    const f = p.fuentes.find(x => x.clave === a.fuente);
    const vivas = a.cosas.filter(x => !x.pasada), pasadas = a.cosas.filter(x => x.pasada);
    return `<section class="todo-grupo todo-entera" data-fuente="${esc(a.fuente)}">`
        + vivas.map(x => filaCosa(x, { mundos: p.mundos, puesto: p.puesto, fuente: f })).join('')
        + (pasadas.length ? item({ variante: 'submenu', clases: ['todo-cab'], inicio: [null, { icono: I.abierto }], titulo: 'hechas y descartadas',
            sufijo: [{ texto: String(pasadas.length), tono: 'tenue' }] }) + pasadas.map(x => filaCosa(x, { mundos: p.mundos, puesto: p.puesto, fuente: f })).join('') : '')
        + item({ clases: ['todo-mas'], apagada: true, inicio: [null], titulo: `… y ${a.total - a.cosas.length} más`, sufijo: [{ texto: 'sin topes: siguen al bajar', tono: 'tenue' }] })
        + '</section>';
}

/** Todo, en HTML: el cuerpo de su pantalla (la barra, `barraTodo`). */
export function todo(p: PropsTodo): string {
    const total = p.fuentes.reduce((n, f) => n + cuantas(f, p.puesto), 0);
    const q = p.buscado ?? '';
    const hallado = (p.halladas ?? []).filter(x => delMundo(x, p.puesto));
    const f = p.abierta ? p.fuentes.find(x => x.clave === p.abierta!.fuente) : undefined;
    const lugar = f ? f.nombre : 'todo: tareas, casillas, esperas, correos, hilos, proyectos';
    // la cuenta del buscador, ya puesta (la vista la cambia al escribir)
    const cuenta = p.abierta ? `${p.abierta.total}` : q ? `${hallado.length} de ${p.total ?? total}` : total ? `${total}` : '';
    const h = ['<div class="todo">', barraBuscar({ id: 'todo-q', atajo: '/', valor: q, placeholder: lugar, claseBarra: 'todo-buscar',
        ayuda: 'buscar en el título, lo que dice, dónde vive · ⏎ abre la primera · ⎋ borra', cuenta: { id: 'todo-cuenta', texto: cuenta } })];
    if (q && !p.abierta) {
        h.push(filtros({ accion: 'todo-filtro', clase: 'todo-filtros', grupos: [{ clave: 'fuente', nombre: 'fuente', activa: p.filtro ?? '',
            opciones: p.fuentes.map(x => ({ clave: x.clave, nombre: x.nombre, cuenta: hallado.filter(y => y.fuente === x.clave).length }))
                .filter(o => o.cuenta) }] }));
    }
    if (p.aviso && !q) h.push(item({ clases: ['todo-nada'], apagada: true, inicio: [null], titulo: p.aviso }));
    h.push(p.abierta ? entera(p) : q ? loHallado(p) : lasFuentes(p), '</div>');
    return h.join('');
}

/** La barra de su pantalla: «todo»; con una fuente abierta, «‹» y su nombre. Cuántas cosas hay en el mundo puesto y en
 *  los otros, en el globo del título: a la vista ya lo dice cada fuente («+N en otros mundos») y el buscador. */
export function barraTodo(p: PropsTodo): Barra {
    const total = p.fuentes.reduce((n, f) => n + cuantas(f, p.puesto), 0);
    const otros = p.fuentes.reduce((n, f) => n + enOtros(f, p.puesto), 0);
    const mundo = p.mundos.find(m => m.clave === p.puesto);
    const f = p.abierta ? p.fuentes.find(x => x.clave === p.abierta!.fuente) : undefined;
    const resumen = f ? `${p.abierta!.total} · todas, sin filtros${mundo ? ` · ${mundo.nombre}` : ''}`
        : `${total}${mundo ? ` en ${mundo.nombre}` : ' en todos los mundos'}${otros ? ` · y ${otros} en los otros` : ''}`;
    return {
        volver: f ? { accion: 'todo-volver', icono: I.atras, ayuda: 'volver a todo (⎋)' } : undefined,
        nombre: f ? f.nombre : 'todo', color: f ? f.color : 'cian', ayuda: resumen,
        acciones: [{ accion: 'todo-releer', icono: I.releer, ayuda: 'volver a leer (r)' }],
    };
}
