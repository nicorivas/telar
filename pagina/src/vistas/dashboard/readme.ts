// El README de un proyecto, partido para el detalle de la pantalla de proyectos (proyectos.ts): su título, su
// entrada (lo que va antes de la primera sección: el resumen del documento) y sus secciones, cada una con las suyas
// de un nivel más abajo. Con eso el detalle muestra un resumen (lo que pide atención, qué es, los datos) y el
// documento plegado por secciones, que se abren con un clic. Sin markdown-it: aquí solo se parte y se mira el texto;
// dibujarlo es de proyectos.ts. Se prueba con `npm run prueba:readme`.

/** Una sección: su título, su texto propio (antes de la primera de las suyas) y las suyas. */
export interface Parte {
    titulo: string;
    md: string;
    subs: Parte[];
}

/** El README partido. `intro` es lo que va entre el título y la primera sección; `pie`, lo que cierra el documento
 *  después de una raya (*Actualizado: …*), que no es de su última sección. */
export interface Partido {
    titulo: string;
    intro: string;
    partes: Parte[];
    pie: string;
}

const CERCO = /^\s{0,3}(```|~~~)/;
const TITULO = /^(#{1,6})\s+(.*?)\s*#*\s*$/;
/** Un valor que no dice nada («—», «pendiente»). */
const VACIO = /^(—|–|-|\?|pendiente|por definir|tbd|n\/a|sin dato)?$/i;

/** El título de una sección, sin las marcas de énfasis, los escapes («\\(») ni los dos puntos del final. */
const limpioTitulo = (t: string): string => t.replace(/\*\*|__|`/g, '').replace(/\\([\\`*_{}[\]()#+\-.!|])/g, '$1')
    .replace(/\s*:\s*$/, '').trim();

/** Las líneas con el nivel del título que abren (0 si no abren ninguno), sin contar las de un bloque de código. */
function lineas(texto: string): { linea: string; nivel: number; titulo: string }[] {
    let cerco = '';
    return texto.split('\n').map(linea => {
        const c = CERCO.exec(linea);
        if (c) { cerco = cerco ? (linea.trim().startsWith(cerco) ? '' : cerco) : c[1]; return { linea, nivel: 0, titulo: '' }; }
        const t = cerco ? null : TITULO.exec(linea);
        return { linea, nivel: t ? t[1].length : 0, titulo: t ? limpioTitulo(t[2]) : '' };
    });
}

/** Parte un README: sin su encabezado YAML; el primer título de nivel 1 es el suyo; las secciones son las del nivel
 *  más alto que queda (## casi siempre) y las suyas, las del siguiente que haya (###). Un README sin secciones queda
 *  entero en la entrada. */
export function partir(texto: string): Partido {
    const ls = lineas(texto.replace(/^﻿?---\r?\n[\s\S]*?\r?\n---\r?\n/, '').replace(/\r\n/g, '\n'));
    const i1 = ls.findIndex(l => l.nivel === 1);
    const antes = ls.findIndex(l => l.nivel >= 2);
    // el título es el primer # si viene antes que cualquier otra sección
    const conTitulo = i1 >= 0 && (antes < 0 || i1 < antes);
    const titulo = conTitulo ? ls[i1].titulo : '';
    const resto = conTitulo ? ls.filter((_, i) => i !== i1) : ls;
    const niveles = [...new Set(resto.filter(l => l.nivel).map(l => l.nivel))].sort((a, b) => a - b);
    const arriba = niveles[0] ?? 0;
    const abajo = niveles.find(n => n > arriba) ?? 0;
    const intro: string[] = [];
    const partes: Parte[] = [];
    let parte: Parte | undefined, sub: Parte | undefined;
    for (const l of resto) {
        if (arriba && l.nivel === arriba) { parte = { titulo: l.titulo, md: '', subs: [] }; sub = undefined; partes.push(parte); continue; }
        if (parte && abajo && l.nivel === abajo) { sub = { titulo: l.titulo, md: '', subs: [] }; parte.subs.push(sub); continue; }
        const donde = sub ?? parte;
        if (donde) donde.md += `${l.linea}\n`; else intro.push(l.linea);
    }
    const recortar = (p: Parte): Parte => ({ titulo: p.titulo, md: p.md.trim(), subs: p.subs.map(recortar) });
    const listas = partes.map(recortar);
    // el pie: tras la última raya, unas pocas líneas sin títulos ni tablas
    let ultima = listas[listas.length - 1];
    while (ultima?.subs.length) ultima = ultima.subs[ultima.subs.length - 1];
    const pie = ultima ? /(?:^|\n)\s*(?:-{3,}|\*{3,}|_{3,})\s*\n((?:[^\n#|]*\S[^\n]*(?:\n|$)){1,3})\s*$/.exec(ultima.md) : null;
    if (ultima && pie) ultima.md = ultima.md.slice(0, pie.index).trim();
    return { titulo, intro: intro.join('\n').trim(), partes: listas, pie: pie ? pie[1].trim() : '' };
}

/** El texto sin los comentarios de HTML (las marcas de los bloques que escribe una máquina). */
export const sinComentarios = (md: string): string => md.replace(/<!--[\s\S]*?-->/g, '');

/** Las filas de una tabla en líneas de markdown: sus celdas, sin la fila que separa el encabezado. */
function celdas(linea: string): string[] {
    return linea.trim().replace(/^\|/, '').replace(/\|$/, '').split(/(?<!\\)\|/).map(c => c.trim().replace(/\\\|/g, '|'));
}
const esSeparador = (l: string): boolean => /^\s*\|?[\s:|-]+\|?\s*$/.test(l) && l.includes('-');
const esTabla = (l: string): boolean => l.trim().startsWith('|');

/** Las tablas de un texto: cada una, su encabezado y sus filas. */
export function tablas(md: string): { cab: string[]; filas: string[][] }[] {
    const out: { cab: string[]; filas: string[][] }[] = [];
    const ls = sinComentarios(md).split('\n');
    for (let i = 0; i < ls.length; i++) {
        if (!esTabla(ls[i]) || !ls[i + 1] || !esSeparador(ls[i + 1])) continue;
        const t = { cab: celdas(ls[i]), filas: [] as string[][] };
        i += 2;
        while (i < ls.length && esTabla(ls[i])) { t.filas.push(celdas(ls[i])); i++; }
        out.push(t);
    }
    return out;
}

/** Sin contenido propio: lo que queda al quitarle los comentarios, las citas (en una plantilla, la ayuda de qué va
 *  ahí), las tablas sin filas y las rayas, no es nada; y las suyas, tampoco. */
export function vacia(p: Parte): boolean {
    const ls = sinComentarios(p.md).split('\n');
    let tabla = false;
    const queda = ls.filter((l, i) => {
        if (esTabla(l)) {
            // el encabezado y su separador no cuentan; una fila de datos sí
            if (ls[i + 1] && esSeparador(ls[i + 1])) { tabla = true; return false; }
            if (esSeparador(l)) return false;
            return tabla && !!l.replace(/[|\s]/g, '');
        }
        tabla = false;
        return !!l.trim() && !/^\s*>/.test(l) && !/^\s*(-{3,}|\*{3,}|_{3,})\s*$/.test(l);
    });
    return !queda.length && p.subs.every(vacia);
}

/** El texto sin la cita con que empieza, si trae algo más después: en una plantilla, la ayuda de qué va ahí. */
export function sinAyuda(md: string): string {
    const m = /^(?:\s*<!--[\s\S]*?-->\s*)*((?:[ \t]*>.*(?:\n|$))+)/.exec(md);
    if (!m) return md;
    const resto = md.slice(m.index + m[0].length);
    return sinComentarios(resto).trim() ? resto.trim() : md;
}

/** La escribió una máquina: trae la marca de un bloque generado (`<!-- X:auto … -->`). */
export const generada = (p: Parte): boolean => /<!--[^>]*\bauto\b/i.test(p.md);

/** El markdown de una línea, en texto: sin enlaces (queda su texto), énfasis, código ni viñetas. */
export function enTexto(linea: string): string {
    return linea.replace(/!\[[^\]]*\]\([^)]*\)/g, '').replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
        .replace(/^\s*(?:[-*+]|\d+[.)])\s+(\[[ xX]\]\s+)?/, '').replace(/\*\*|__|`/g, '').replace(/(^|\s)[*_](\S)/g, '$1$2')
        .replace(/(\S)[*_](\s|$)/g, '$1$2').replace(/\s+/g, ' ').trim();
}

/** Lo que se lee de una sección plegada, a su lado, para saber si abrirla: cuántas casillas abiertas y hechas, si las
 *  tiene; si no, lo primero que trae: su primera línea de texto o su tabla (una de campo y valor, sus primeros; otra,
 *  cuántas filas); si no trae nada propio, el nombre de las suyas; y si solo trae una cita, la cita. */
export function vistazo(p: Parte): string {
    const todo = [p.md, ...p.subs.flatMap(s => [s.md, ...s.subs.map(x => x.md)])].join('\n');
    const abiertas = (todo.match(/^\s*[-*+]\s+\[ \]/gm) ?? []).length;
    const hechas = (todo.match(/^\s*[-*+]\s+\[[xX]\]/gm) ?? []).length;
    if (abiertas + hechas) {
        return [abiertas ? `${abiertas} abierta${abiertas === 1 ? '' : 's'}` : '', hechas ? `${hechas} hecha${hechas === 1 ? '' : 's'}` : '']
            .filter(Boolean).join(' · ');
    }
    let cerco = false;
    const ls = sinComentarios(p.md).split('\n');
    for (const [i, l] of ls.entries()) {
        if (CERCO.test(l)) { cerco = !cerco; continue; }
        if (!cerco && esTabla(l) && ls[i + 1] && esSeparador(ls[i + 1])) {
            const t = tablas(ls.slice(i).join('\n'))[0];
            if (t?.filas.length) {
                const dicen = t.filas.filter(([, v]) => !VACIO.test(enTexto(v ?? '')));
                return t.cab.length === 2 && dicen.length ? dicen.slice(0, 3).map(([k, v]) => `${enTexto(k)}: ${enTexto(v ?? '')}`).join(' · ')
                    : `tabla · ${t.filas.length} fila${t.filas.length === 1 ? '' : 's'}`;
            }
        }
        if (cerco || !l.trim() || /^\s*(>|\||#|<|-{3,}|\*{3,}|!\[)/.test(l)) continue;
        const t = enTexto(l);
        if (t) return t;
    }
    if (p.subs.length) return p.subs.map(s => s.titulo).join(' · ');
    const cita = ls.filter(l => /^\s*>/.test(l)).map(l => enTexto(l.replace(/^\s*>\s?/, ''))).join(' ').trim();
    return cita;
}

/** Qué es una sección para el resumen, por su título: lo que dice cómo va (`estado`: «Estado», «Foco…», «Al 9-nov»;
 *  no la que escribe una máquina), lo que espera de otros o queda abierto (`abierto`: «Esperando», «Preguntas
 *  abiertas», «Próximos pasos»…) y la ficha de datos (`datos`: «Info general»). Las demás, "". */
export type Clase = 'estado' | 'abierto' | 'datos' | '';
export function claseDe(p: Parte): Clase {
    const t = p.titulo.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
    if (/^(info|informacion)( general)?$|^ficha\b|^datos\b/.test(t)) return 'datos';
    if (/^(estado|foco|ahora|situacion|en que va|donde vamos|al \d)/.test(t) && !generada(p)) return 'estado';
    if (/^(esperando|bloqueos?|preguntas abiertas|por resolver|que falta|lo que queda abierto|proximos pasos)\b/.test(t)) return 'abierto';
    return '';
}

/** Los datos de una ficha: las filas de su primera tabla de dos columnas (campo y valor), sin las que no dicen nada
 *  («—», «pendiente») ni las que el detalle ya muestra arriba (`menos`, por su campo en minúsculas). */
export function datos(p: Parte, menos: string[] = []): [string, string][] {
    const t = tablas(p.md).find(x => x.cab.length === 2);
    if (!t) return [];
    return t.filas.filter(f => f.length >= 2)
        .map(([k, v]): [string, string] => [k.replace(/\*\*|__/g, '').trim(), v.trim()])
        .filter(([k, v]) => k && !VACIO.test(enTexto(v)) && !menos.includes(k.toLowerCase()));
}
