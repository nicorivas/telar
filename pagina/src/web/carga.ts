// La hoja «contexto» de la barra de la derecha (#lado, web/lado.ts): lo que carga el contexto del hilo que se ve
// (`GET /contexto`, docs/contratos.md «telar hilo contexto»). Para ver cuánto pesan los archivos generales —los que todo
// hilo carga sin pedirlos: los CLAUDE.md, la memoria, los hooks, la lista de skills, los MCP— contra lo que el hilo
// leyó para su trabajo, y decidir qué recortar en lo general.
//
// Arriba, el resumen: cuánto pesa ahora y desde cuándo (que empezó, el último /clear o la última compactación), las
// partes de ese total (componentes/partes.ts) y una fila por grupo, con cuántas cosas y cuánto pesan. Un clic en un
// grupo (o en su parte) lo abre: cada cosa con su ruta, su tamaño y cuántas veces entró; un clic en una que es un
// archivo, lo abre en el visor. Lo que una compactación ya resumió va aparte, tenue. Solo rutas y tamaños: nunca lo
// que dice un archivo. Lo calcula la máquina donde vive la conversación; de otra, se le pide por el bus.

import * as cli from '../cli';
import { esc } from '../estilo';
import { item, type Pieza } from '../componentes/item';
import { partes } from '../componentes/partes';
import { maquinaDe } from './codigos';
import { I } from './iconos';
import * as ui from './ui';

/** cada cuánto se relee mientras se ve el mismo hilo */
const CADA = 30 * 1000;
/** cuántas cosas de un grupo abierto se ven antes de «más» */
const VISIBLES = 12;

/** el ícono de cada grupo; su color es su token, `--carga-<grupo>` (tokens.css) */
const GRUPO_I: Record<string, string> = {
    claude: I.claude, inicio: I.capas, carpetas: I.carpeta, leido: I.lectura, repetido: I.repite, hilos: I.correo,
    conversacion: I.conversacion,
};
/** el ícono de cada clase de cosa, y cómo se nombra */
const CLASE: Record<string, [string, string]> = {
    claude_md: [I.markdown, 'instrucciones (CLAUDE.md)'], memoria: [I.memoria, 'el índice de la memoria'],
    hook: [I.gancho, 'lo que agrega un hook'], skills: [I.listado, 'una lista de skills'], skill: [I.skill, 'una skill'],
    mcp: [I.mcp, 'las instrucciones de un MCP'], herramientas: [I.herramientas, 'los nombres de herramientas'],
    agentes: [I.subagentes, 'los tipos de subagente'], git: [I.git, 'el estado de git'],
    sistema: [I.claude, 'lo de Claude Code'], aviso: [I.campana, 'un aviso de Claude Code'],
    archivo: [I.archivo, 'un archivo'], imagen: [I.imagen, 'una imagen'], busqueda: [I.buscar, 'una búsqueda'],
    mensaje: [I.correo, 'un mensaje de otro hilo'], sesion: [I.sesion, 'un mensaje de otra sesión'],
    resumen: [I.resumen, 'el resumen de una compactación'], resto: [I.razonamiento, 'deducido de lo medido'],
};
/** las partes de la conversación, por su nombre (carga_claude.py) */
const DIJO: Record<string, string> = {
    'lo que escribió la persona': I.persona, 'lo que respondió el agente': I.escribir, 'las llamadas a herramientas': I.llamada,
};

let clave = '';
let hilo = '', maquina = '';
let datos: cli.JsonCarga | undefined;
let falla = '';
let leida = 0;
/** los grupos abiertos, los que se ven enteros y los que muestran lo ya resumido */
const abiertos = new Set<string>();
const enteros = new Set<string>();
const resumidos = new Set<string>();

/** Si hay algo que mostrar: cualquier hilo (si no tiene una conversación que se sepa leer, la hoja lo dice). */
export function hay(): boolean { return !!clave; }

/** Lo que se ve cambió: carga lo del hilo (`que`, la clave de la página) si no está o está viejo. True si cambió lo que
 *  hay que mostrar. */
export async function cargar(que: string, h: string, m: string): Promise<boolean> {
    if (!que) { const habia = !!clave; clave = ''; datos = undefined; falla = ''; return habia; }
    if (que !== clave) {
        clave = que; datos = undefined; falla = ''; leida = 0;
        abiertos.clear(); enteros.clear(); resumidos.clear();
    }
    if (Date.now() - leida < CADA) return false;
    hilo = h; maquina = maquinaDe(h, m);
    leida = Date.now();
    const r = await cli.carga(hilo, maquina);
    if (clave !== que) return false;  // ya se fue a otro
    const antes = JSON.stringify([datos ?? null, falla]);
    if (r.datos) { datos = r.datos; falla = ''; } else if (!datos) falla = r.error ?? 'sin respuesta';
    return JSON.stringify([datos ?? null, falla]) !== antes;
}

/** Tokens, cortos: 812, 5,3 k, 284 k. */
function k(t: number): string {
    if (t < 1000) return String(t);
    return t < 10000 ? `${(t / 1000).toFixed(1).replace('.', ',')} k` : `${Math.round(t / 1000)} k`;
}

/** La hora local de un momento (y el día, si no es hoy). */
function cuando(iso: string | undefined): string {
    if (!iso) return '';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return '';
    const hora = d.toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit', hour12: false });
    const hoy = new Date();
    return d.toDateString() === hoy.toDateString() ? hora
        : `${d.toLocaleDateString('es-CL', { day: 'numeric', month: 'short' }).replace('.', '')} ${hora}`;
}

/** Una ruta, corta: relativa a la carpeta del hilo, o con «~» en su casa. */
function corta(ruta: string): string {
    const c = datos?.carpeta?.replace(/\/$/, ''), casa = datos?.casa?.replace(/\/$/, '');
    if (c && ruta.startsWith(`${c}/`)) return ruta.slice(c.length + 1);
    if (casa && ruta.startsWith(`${casa}/`)) return `~/${ruta.slice(casa.length + 1)}`;
    return ruta;
}

/** El ícono de un grupo, en su color. */
const iconoGrupo = (g: string): Pieza => ({ html: `<span class="i" style="color: var(--carga-${esc(g)})">${GRUPO_I[g] ?? I.punto}</span>` });

function desde(): string {
    if (!datos) return '';
    const d = datos.desde;
    const hora = cuando(d.hora);
    if (d.que === 'compactacion') {
        const como = d.como === 'manual' ? ' (/compact)' : '';
        return `desde la compactación de las ${hora}${como}` + (d.antes ? ` · tenía ${k(d.antes)}` : '');
    }
    if (d.que === 'clear') return `desde el /clear de las ${hora}`;
    if (d.que === 'retomada') return `desde que se retomó, ${hora}`;
    return `desde que empezó, ${hora}`;
}

/** Una cosa de un grupo abierto, en su fila. */
function fila(x: cli.JsonItemCarga): string {
    const [icono, que] = CLASE[x.clase] ?? [DIJO[x.nombre] ?? (x.nombre.startsWith('lo que devolvió') ? I.salida : I.punto), 'parte de la conversación'];
    const vigente = x.veces > 0;
    const esRuta = x.nombre.startsWith('/') || x.nombre.startsWith('~');
    const nombre = esRuta ? corta(x.nombre) : x.nombre;
    const i = esRuta ? nombre.lastIndexOf('/') : -1;
    const titulo = x.clase === 'skill' ? `/${nombre}` : i > 0 ? nombre.slice(i + 1) : nombre, dir = i > 0 ? nombre.slice(0, i) : '';
    const tokens = vigente ? x.tokens : (x.antes?.tokens ?? 0);
    const veces = vigente ? x.veces : (x.antes?.veces ?? 0);
    const ayuda = [esRuta ? nombre : x.nombre, que,
        x.deducido ? 'no está en la conversación como texto: sale de lo que midió el modelo' : '',
        veces > 1 ? `${veces} veces${x.primera ? `: ${cuando(x.primera)} → ${cuando(x.ultima)}` : ''}` : (x.ultima ? cuando(x.ultima) : ''),
        x.vias?.length ? `por ${x.vias.join(', ')}` : '',
        vigente && x.antes ? `antes de compactar: ${x.antes.veces} ${x.antes.veces === 1 ? 'vez' : 'veces'}, ${k(x.antes.tokens)}` : '',
        !vigente ? 'ya no está en el contexto: lo resumió una compactación' : '',
        x.ruta ? 'clic: abrirlo' : ''].filter(Boolean).join('\n');
    return item({
        inicio: [null, { icono, ayuda: que }],
        titulo, sufijo: dir ? [{ texto: dir, tono: 'tenue' }] : undefined,
        meta: { texto: `${veces > 1 ? `×${veces} ` : ''}${x.deducido ? '≈ ' : ''}${k(tokens)}` },
        apagada: !vigente, ayuda,
        ...(x.ruta ? { accion: 'carga-abrir', datos: { ruta: x.ruta } } : {}),
    });
}

/** Un grupo: su fila (un submenú que se pliega) y, abierto, sus cosas. */
function grupo(g: cli.JsonGrupoCarga): string {
    if (!datos) return '';
    const total = datos.total || 1;
    const todas = datos.items.filter(x => x.grupo === g.clave);
    const vigentes = todas.filter(x => x.veces > 0), viejas = todas.filter(x => x.veces === 0);
    if (!g.tokens && !viejas.length) return '';
    const abierto = abiertos.has(g.clave);
    const pct = Math.round((100 * g.tokens) / total);
    const h = [item({
        variante: 'submenu', accion: 'carga-grupo', id: g.clave, ayuda: `${g.para}\nclic: ${abierto ? 'plegarlo' : 'ver qué es'}`,
        inicio: [iconoGrupo(g.clave), { icono: abierto ? I.abierto : I.plegado }],
        titulo: g.nombre, sufijo: g.cuantos ? [{ texto: String(g.cuantos), tono: 'tenue' }] : undefined,
        meta: { texto: g.tokens ? `${k(g.tokens)} · ${pct < 1 && g.tokens ? '<1' : pct}%` : 'resumido' },
        clases: ['carga-grupo'],
    })];
    if (!abierto) return h.join('');
    const enteras = enteros.has(g.clave);
    const vistas = enteras ? vigentes : vigentes.slice(0, VISIBLES);
    h.push(...vistas.map(fila));
    if (vigentes.length > vistas.length) {
        const resto = vigentes.slice(vistas.length).reduce((s, x) => s + x.tokens, 0);
        h.push(item({ variante: 'enlace', accion: 'carga-todas', id: g.clave, inicio: [null, { icono: I.menu }],
            titulo: `${vigentes.length - vistas.length} más`, meta: { texto: k(resto) }, ayuda: 'ver todas' }));
    }
    if (viejas.length) {
        const ver = resumidos.has(g.clave);
        const pesaban = viejas.reduce((s, x) => s + (x.antes?.tokens ?? 0), 0);
        h.push(item({ variante: 'enlace', accion: 'carga-resumidos', id: g.clave, inicio: [null, { icono: ver ? I.abierto : I.plegado }],
            titulo: `${viejas.length} que ya resumió una compactación`, meta: { texto: k(pesaban), tono: 'tenue' },
            ayuda: 'lo que entró antes de la última compactación y ya no está en el contexto (pesaba esto)' }));
        if (ver) h.push(...viejas.slice(0, enteras ? undefined : VISIBLES * 2).map(fila));
    }
    return h.join('');
}

/** La hoja entera (sin la cabecera de la barra, que es de web/lado.ts). */
export function html(): string {
    if (!datos) {
        return falla ? `<div class="carga-aviso dim">${esc(falla)}</div>` : '<div class="carga-aviso dim">leyendo su conversación…</div>';
    }
    const d = datos;
    const visibles = d.grupos.filter(g => g.tokens > 0);
    const h = [
        `<div class="carga-total"><span class="carga-cifra">${d.medido ? '' : '≈ '}${esc(k(d.total))}</span> tokens ahora`
            + `<span class="dim"> · ${esc(desde())}</span></div>`,
        partes({ accion: 'carga-grupo', partes: visibles.map(g => ({
            clave: g.clave, valor: g.tokens, tinta: `carga-${g.clave}`, activa: abiertos.has(g.clave),
            ayuda: `${g.nombre}: ${k(g.tokens)} (${Math.round((100 * g.tokens) / (d.total || 1))}%)`,
        })) }),
    ];
    const notas = [d.al_empezar ? `${d.desde.que === 'compactacion' ? 'recién compactada' : 'al empezar'} pesaba ${k(d.al_empezar)}` : '',
        d.compactaciones ? `${d.compactaciones} ${d.compactaciones === 1 ? 'compactación' : 'compactaciones'}` : ''].filter(Boolean);
    if (notas.length) h.push(`<div class="carga-nota dim">${esc(notas.join(' · '))}</div>`);
    h.push(`<div class="carga-lista">${d.grupos.map(grupo).join('')}</div>`);
    h.push(`<div class="carga-pie dim">cada cosa, estimada por sus caracteres (${String(d.caracteres_por_token).replace('.', ',')} por token);`
        + ` el total, ${d.medido ? 'lo mide el modelo en cada pedido' : 'estimado también: la conversación no trae el uso'}`
        + `${d.truncado ? '; de los grupos muy largos, lo que más pesa' : ''}.</div>`);
    return h.join('');
}

/** Los clics de la hoja; true si era suyo. Lo llama web/lado.ts, que redibuja si `true`. */
export function atender(e: Event): boolean {
    if (e.type !== 'click') return false;
    const a = (e.target as HTMLElement).closest<HTMLElement>('[data-accion^="carga-"]');
    if (!a) return false;
    e.preventDefault();
    const que = a.dataset.accion, id = a.dataset.id ?? '';
    if (que === 'carga-abrir' && a.dataset.ruta) { void ui.abrirArchivo(maquina ? `${maquina}:${a.dataset.ruta}` : a.dataset.ruta); return true; }
    const conjunto = que === 'carga-grupo' ? abiertos : que === 'carga-todas' ? enteros : que === 'carga-resumidos' ? resumidos : undefined;
    if (!conjunto || !id) return false;
    if (conjunto.has(id)) conjunto.delete(id); else conjunto.add(id);
    repintar();
    return true;
}

function repintar(): void {
    const el = document.querySelector<HTMLElement>('#lado .carga');
    if (el) el.innerHTML = html();
}

/** Para las pruebas y la consola: lo que se cargó. */
export const _datos = (): cli.JsonCarga | undefined => datos;
