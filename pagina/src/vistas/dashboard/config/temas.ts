// ⚙ temas: los colores principales de un tema y los temas propios (`[temas.<tema>]`, telar.temas; web/colores.ts). Lo
// que se cambia aquí queda en la raíz (`<raiz>/.telar/temas.toml`) y vale en todas las máquinas; lo que la configuración de
// esta máquina pisa se dice «solo aquí» (`textoDonde`, `marcaDonde`). Arriba, los temas (los de fábrica y los propios), cada uno pintado con sus colores: el que
// se ve va marcado y un clic elige cuál se cambia (de entrada, el que se ve); «nuevo tema…» arma uno propio con un nombre
// y el tema del que parte. Debajo, sobre el fondo de ese tema, una vista previa (una barra, filas con sus líneas, la fila
// activa, la seleccionada y cada tinta) y cada color que se nota: los fondos y las líneas (el fondo, las barras, las
// líneas, la selección: componentes/temas.ts, FONDOS) y las tintas de letra (el texto, lo tenue, los títulos, el acento…:
// EDITABLES), con lo que pinta, su color, el de fábrica al lado y cómo se lee, y para cambiarlo: el selector de color del
// navegador (la muestra misma), un campo para escribir uno (#rrggbb) y, en las tintas, una paleta corta que combina con el
// tema (`paleta`: la de fábrica primero). Un clic en la paleta lo escribe al tiro, solo esa línea; en el selector y en el
// campo se ve mientras se elige (`colores.probar`, sin escribir: en la vista previa y, si es el tema que se ve, en toda la
// página) y se escribe al soltarlo o con ⏎. «de fábrica» vuelve un color; «todo de fábrica», el tema entero (de uno de
// fábrica quita la tabla; de uno propio, sus colores: queda igual a su base). Uno propio se borra con «borrar tema», salvo
// que un modo o un mundo lo tenga puesto.
//
// Lo que se lee mal no se prohíbe: se avisa. Una letra bajo 4,5:1 sobre el fondo, las barras o la fila activa, o tan cerca
// de otra tinta que se confunden (`temas.avisos`); un fondo que deja mal letras que de fábrica se leían bien; el texto que
// no se lee sobre la selección; una línea que no se ve: la fila lo dice en ese momento, mientras se elige, y al escribirlo
// un aviso.
//
// Los botones con texto son los de componentes/boton.ts («la tecla en el pie»): los del pie de la lista de temas y del
// tema, en una banda partida en celdas; los sueltos (volver una tinta, ponerte el tema), una celda sola.

import { esc } from '../../../estilo';
import { boton, pieBotones, type Boton } from '../../../componentes/boton';
import * as temas from '../../../componentes/temas';
import * as cli from '../../../cli';
import * as colores from '../../../web/colores';
import * as modos from '../../../web/modos';
import * as mundo from '../../../web/mundo';
import * as ui from '../../../web/ui';
import { I } from '../../../web/iconos';
import type { FabricaSeccion } from './seccion';

/** Un color escrito como `#rrggbb` (también `#rgb`, o sin `#`), en minúsculas; undefined si no es uno. */
export function leerColor(texto: string): string | undefined {
    const t = texto.trim().toLowerCase().replace(/^#?/, '#');
    if (/^#[0-9a-f]{3}$/.test(t)) return '#' + [...t.slice(1)].map(c => c + c).join('');
    return /^#[0-9a-f]{6}$/.test(t) ? t : undefined;
}

/** Un color como lo da el CSS (`#7dae9a`, `rgb(…)`), en `#rrggbb`; "" si no se entiende. */
const comoHex = (css: string): string => { const c = temas.rgb(css); return c ? temas.hex(c) : ''; };

const coma = (n: number) => n.toFixed(1).replace('.', ',');
const nombreDe = (clave: string) => temas.COLORES.find(e => e.tinta === clave)?.nombre ?? clave;

/** Lo que se mide de un color, en un número: de una letra, su peor contraste sobre los fondos donde va; del fondo, las
 *  barras y la selección, el del texto sobre ellos; de las líneas, el suyo contra el fondo. Y desde cuánto está bien. */
export function razonDe(c: Record<string, string>, clave: string): { razon: number; minimo: number; que: string } {
    const x = (k: string) => temas.rgb(c[k] ?? '');
    if (clave === 'linea') {
        const l = x('linea'), bg = x('bg');
        return { razon: l && bg ? temas.contraste(l, bg) : 0, minimo: temas.LINEA_MINIMA, que: 'contra el fondo' };
    }
    if (temas.esFondo(clave)) {
        const f = x(clave), fg = x('fg');
        return { razon: f && fg ? temas.contraste(fg, f) : 0, minimo: temas.MINIMO, que: 'el texto sobre él' };
    }
    try {
        return { razon: Math.min(...temas.medir(c).contrastes.filter(m => m.texto === clave).map(m => m.razon)), minimo: temas.MINIMO,
            que: 'el peor contraste, sobre el fondo, las barras y la fila activa' };
    } catch { return { razon: 0, minimo: temas.MINIMO, que: '' }; }
}

/** Lo que dicen los avisos de un color, una línea cada uno (vacío si se lee bien). */
const htmlAvisos = (avisos: temas.Aviso[]): string => avisos.map(a =>
    `<div class="te-aviso ${a.tipo}"><span class="i">${I.alerta}</span>${esc(a.texto)}</div>`).join('');

/** Dónde queda lo que se cambia de un tema, en palabras: en la raíz (todas las máquinas), y qué pisa esta máquina; sin raíz
 *  (la configuración no dice raíz), en la de esta máquina. */
export function textoDonde(d: colores.Donde, raiz: string, tema: string): string {
    if (!raiz) return `lo que cambias queda en [temas.${tema}] de esta máquina`;
    const n = cli.nombreRaiz(raiz);
    const partes = [`lo que cambias queda en ${n} y vale en todas las máquinas`];
    if (d.vive === 'maquina') partes.push(`hoy está solo en esta máquina: al cambiarlo pasa a ${n}`);
    if (d.enMaquina.length) partes.push(`solo en esta máquina: ${d.enMaquina.map(nombreDe).join(', ')} (pisa lo de ${n}; cambiarlo lo lleva a ${n})`);
    return partes.join(' · ');
}

/** Al lado de un color propio, dónde vive: «en la raíz» (todas las máquinas) o «solo aquí» (lo pisa esta máquina). Nada sin
 *  raíz. */
export function marcaDonde(d: colores.Donde, raiz: string, clave: string): string {
    if (!raiz) return '';
    return d.enMaquina.includes(clave)
        ? '<span class="te-donde solo" title="en la configuración de esta máquina: la otra no lo ve">solo aquí</span>'
        : `<span class="te-donde" title="${esc(`en ${cli.nombreRaiz(raiz)} (${raiz}): vale en todas las máquinas`)}">en ${esc(cli.nombreRaiz(raiz))}</span>`;
}

/** Por qué se ve ese tema, en palabras. */
function porQue(por: temas.Origen): string {
    if (por === 'mundo') return `lo pone el mundo «${mundo.puesto().mundo}» (⚙ mundos)`;
    if (por === 'a-mano') return 'elegido a mano en este modo (⚙ modos)';
    return `el del modo «${modos.puesto().nombre}» (⚙ modos)`;
}

/** La fila de temas para elegir cuál se cambia: cada uno pintado con sus colores (lleva `data-tema`), el elegido con ✓,
 *  el que se ve con un ojo, el que tiene colores propios con un lápiz; los propios después de los de fábrica. */
export function grillaTemas(elegido: string, visto: string, conPropios: (clave: string) => boolean): string {
    const tintas = `<span class="mu-tintas">${temas.TINTAS.map(x => `<span style="color: var(--${x})">■</span>`).join('')}</span>`;
    return `<div class="mu-temas">${temas.todos().map(x => `<a class="mu-tema${x.clave === elegido ? ' si' : ''}${x.base ? ' propio' : ''}" data-tema="${esc(x.clave)}"`
        + ` data-accion="tema-elegir" data-valor="${esc(x.clave)}" title="${esc(x.descripcion)}"><span class="i">${x.clave === elegido ? I.hecha : ''}</span>`
        + `${esc(x.nombre)}${x.clave === visto ? `<span class="i te-marca" title="el que ves">${I.ver}</span>` : ''}`
        + `${conPropios(x.clave) ? `<span class="i te-marca" title="con colores propios">${I.editar}</span>` : ''}${tintas}</a>`).join('')}</div>`;
}

/** La vista previa de un tema: lo que más se ve de la página, en pequeño, con sus colores (los propios y lo que se prueba):
 *  una barra con su título, filas partidas por sus líneas (una común, la activa, la seleccionada) y una con cada tinta. */
export function vistaPrevia(tema: string): string {
    const fila = (clase: string, izq: string, der: string) => `<div class="te-p-fila${clase ? ` ${clase}` : ''}"><span>${izq}</span><span class="te-p-meta">${der}</span></div>`;
    return `<div class="te-previa" data-tema="${esc(tema)}" aria-label="vista previa de ${esc(temas.nombre(tema))}">`
        + `<div class="te-p-barra"><span class="te-p-titulo">hilos</span><span class="te-p-meta">barras · 21:40</span></div>`
        + fila('', 'una fila con su línea', 'tenue · hace 5 min')
        + fila('activa', '<span class="te-p-acento">la fila activa</span>, con un <span class="te-p-acento">enlace</span>', 'trabajando')
        + fila('sel', 'lo elegido en un menú', 'selección')
        + fila('', '<span style="color: var(--titulo)">títulos</span> · <span style="color: var(--violeta)">agentes</span> · '
            + '<span style="color: var(--verde)">éxito</span> · <span style="color: var(--cian)">remoto</span> · '
            + '<span style="color: var(--magenta)">rosa</span> · <span style="color: var(--rojo)">peligro</span>', '')
        + '</div>';
}

export const temasSeccion: FabricaSeccion = ctx => {
    /** el tema que se cambia; undefined, el que se ve */
    let elegido: string | undefined;
    /** mientras se prueba un color (el selector, el campo): los oyentes no repintan, o se perdería lo que se elige */
    let probando = false;
    const cual = () => (elegido && temas.existe(elegido) ? elegido : modos.tema().clave);
    const pintarSiSeVe = () => { if (!probando && ctx.seVe('temas')) seccion.pintar(); };
    modos.alCambiar(pintarSiSeVe);
    mundo.alCambiar(pintarSiSeVe);

    /** los colores que se están probando (el selector, el campo), además de los propios: los que dicen sus avisos */
    const enPrueba = new Set<string>();

    /** Probar un color sin escribirlo (undefined lo suelta), y decir al tiro cómo se lee. */
    const probar = (tema: string, tinta: string, color: string | undefined) => {
        if (color === undefined) enPrueba.delete(tinta); else enPrueba.add(tinta);
        probando = true;
        try { colores.probar(tema, tinta, color); } finally { probando = false; }
        actualizar(tema);
    };

    /** Si un color es de los elegidos: propio o probándose. */
    const elegidoAhora = (tema: string, clave: string) => enPrueba.has(clave) || !!colores.de(tema)[clave];

    /** Los avisos de un color. De los elegidos (los propios y el que se prueba), todos; de una letra que no se tocó, lo que
     *  le hace un fondo elegido (lo que de fábrica se leía bien y ya no); los demás, nada: lo que ya trae el tema no es algo
     *  que se acaba de elegir (su razón, en rojo si se lee mal, lo dice). */
    const avisosDe = (tema: string, ahora: Record<string, string>, fabrica: Record<string, string>, clave: string): temas.Aviso[] => {
        if (elegidoAhora(tema, clave)) return temas.avisos(ahora, clave, temas.esFondo(clave) ? fabrica : undefined);
        if (!temas.esFondo(clave) && temas.FONDOS.some(f => elegidoAhora(tema, f.tinta))) return temas.empeora(ahora, fabrica, clave);
        return [];
    };

    const htmlRazon = (ahora: Record<string, string>, clave: string) => {
        const r = razonDe(ahora, clave);
        return `<span class="te-razon${r.razon < r.minimo ? ' mal' : ''}" title="${esc(r.que)}">${coma(r.razon)}:1</span>`;
    };

    /** Lo que cambia con un color que se prueba, sin repintar: la razón y los avisos de cada fila (un fondo y el acento
     *  mueven las de las demás), y el campo y la muestra de la que no tiene el foco. */
    const actualizar = (tema: string) => {
        const cajas = document.querySelectorAll<HTMLElement>(`.te-caja[data-tema="${tema}"]`);
        if (!cajas.length) return;
        const ahora = colores.resueltos(tema), fabrica = colores.resueltos(tema, true);
        for (const caja of cajas) for (const e of temas.COLORES) {
            const fila = caja.querySelector<HTMLElement>(`[data-tinta-fila="${e.tinta}"]`);
            if (!fila) continue;
            const razon = fila.querySelector('.te-razon');
            if (razon) razon.outerHTML = htmlRazon(ahora, e.tinta);
            const lugar = fila.querySelector('.te-avisos');
            if (lugar) lugar.innerHTML = htmlAvisos(avisosDe(tema, ahora, fabrica, e.tinta));
            const hex = comoHex(ahora[e.tinta] ?? '');
            for (const inp of fila.querySelectorAll<HTMLInputElement>('input[data-tinta]')) {
                if (inp !== document.activeElement && hex) inp.value = hex;
            }
        }
    };

    /** Escribir un color (null: el de fábrica) y, si se lee mal, decirlo. */
    const guardar = async (tema: string, tinta: string, color: string | null) => {
        // escribir suelta lo que se probaba (salga o no): queda lo que dice el archivo
        enPrueba.clear();
        const e = await colores.ajustar(tema, { [tinta]: color });
        // lo escrito puede ser lo mismo que se probaba (la hoja no cambia y nadie avisa): la fila dice ahora que es propio
        if (ctx.seVe('temas')) seccion.pintar();
        if (e) { void ui.falla(`telar: no se guardó: ${e}`); return; }
        const ahora = colores.resueltos(tema);
        const malos = color ? temas.avisos(ahora, tinta, temas.esFondo(tinta) ? colores.resueltos(tema, true) : undefined) : [];
        if (malos.length) void ui.aviso(`telar: «${nombreDe(tinta)}» de ${temas.nombre(tema)} ${malos[0].texto}`);
        else void ui.estado(`telar: «${nombreDe(tinta)}» de ${temas.nombre(tema)}${color ? ` en ${color}` : ', el de fábrica'}`, 3000);
    };

    /** Lo que no son clics: el selector de color y el campo de cada color. */
    const atar = (tema: string) => {
        for (const caja of document.querySelectorAll<HTMLElement>(`.te-caja[data-tema="${tema}"]`)) {
            for (const inp of caja.querySelectorAll<HTMLInputElement>('input[data-tinta]')) {
                const tinta = inp.dataset.tinta ?? '';
                const original = inp.value;
                inp.addEventListener('input', () => {
                    const c = leerColor(inp.value);
                    inp.classList.toggle('mal', !c);
                    if (c) probar(tema, tinta, c);
                });
                inp.addEventListener('change', () => {
                    const c = leerColor(inp.value);
                    if (c && c !== original) { void guardar(tema, tinta, c); return; }
                    inp.value = original;
                    inp.classList.remove('mal');
                    probar(tema, tinta, undefined);
                });
            }
        }
    };

    /** La fila de un color: su muestra (el selector de color), su nombre, lo que pinta, cómo se lee, el de fábrica al lado
     *  y, si es propio, «de fábrica»; debajo, la de fábrica y la paleta (de una tinta) y el campo para escribir otro. */
    const fila = (e: temas.Editable, tema: string, ahora: Record<string, string>, fabrica: Record<string, string>,
        propios: Record<string, string>, noche: boolean): string => {
        const hex = comoHex(ahora[e.tinta] ?? ''), deFabrica = comoHex(fabrica[e.tinta] ?? '');
        const propio = !!propios[e.tinta];
        const fondo = temas.esFondo(e.tinta);
        const muestra = (o: temas.Opcion, primera = false) =>
            `<a class="te-op${o.color === hex ? ' si' : ''}${primera ? ' fabrica' : ''}" style="--c: ${esc(o.color)}" data-accion="tema-tinta"`
            + ` data-valor="${esc(`${tema} ${e.tinta} ${primera ? '' : o.color}`)}"`
            + ` title="${esc(`${o.nombre} · ${o.color} · ${coma(razonDe({ ...ahora, [e.tinta]: o.color }, e.tinta).razon)}:1`)}"></a>`;
        const opciones = [muestra({ nombre: 'de fábrica', color: deFabrica }, true),
            ...(fondo ? [] : temas.paleta(fabrica, e.tinta, noche, ahora).filter(o => o.color !== deFabrica).map(o => muestra(o)))];
        const vuelta = propio
            ? ` · <span class="i te-propio" title="propio: cambiado">${I.editar}</span>${marcaDonde(colores.donde(tema), colores.raiz(), e.tinta)}`
                + boton({ texto: 'volver', accion: 'tema-tinta', valor: `${tema} ${e.tinta} `, icono: I.deshacer, ayuda: `volver al de fábrica, ${deFabrica}` })
            : '';
        return `<div class="te-tinta${fondo ? ' te-fondo' : ''}" data-tinta-fila="${esc(e.tinta)}">`
            + `<div class="fila"><input type="color" class="te-selector" value="${esc(hex)}" data-tinta="${esc(e.tinta)}" title="elegir con el selector de color: se ve mientras se elige, y queda al soltarlo">`
            + `<b class="te-nombre"${fondo ? '' : ` style="color: var(--${esc(e.tinta)})"`}>${esc(e.nombre)}</b>`
            + `<span class="te-para" title="${esc(e.para)}">${esc(e.tinta)} · ${esc(e.para)}</span>`
            + `<span class="der">${htmlRazon(ahora, e.tinta)}`
            + ` · <span class="te-fab" title="el de fábrica${temas.esDeFabrica(tema) ? '' : `: el de ${esc(temas.nombre(temas.baseDe(tema)))}`}">de fábrica <span class="te-fab-muestra" style="--c: ${esc(deFabrica)}"></span>${esc(deFabrica)}</span>`
            + `${vuelta}</span></div>`
            + `<div class="te-opciones">${opciones.join('')}`
            + `<input type="text" class="te-libre" value="${esc(hex)}" data-tinta="${esc(e.tinta)}" maxlength="7" spellcheck="false" autocomplete="off" title="otro color, #rrggbb: se ve mientras se escribe, y queda con ⏎"></div>`
            + `<div class="te-avisos">${htmlAvisos(avisosDe(tema, ahora, fabrica, e.tinta))}</div></div>`;
    };

    /** Un tema propio nuevo: su nombre (sin pisar uno de fábrica ni uno que ya hay) y de cuál parte (de entrada, el que se
     *  está cambiando). Queda elegido para cambiarlo. */
    const nuevo = async () => {
        const desde = cual();
        const escrito = await ui.campo({ titulo: 'un tema propio · su nombre',
            ayuda: 'en minúsculas, con números y guiones («noche-azul»); los espacios y las tildes se arreglan solos. Después, de cuál parte',
            placeholder: 'noche-azul', validar: t => temas.problemaNombre(temas.aNombre(t)) || undefined });
        if (escrito === undefined) return;
        const nombre = temas.aNombre(escrito);
        const lista = [...temas.todos()].sort((a, b) => (a.clave === desde ? -1 : b.clave === desde ? 1 : 0));
        const base = await ui.elegir(lista.map(t => ({ label: t.nombre, description: [t.clave === desde ? '← el que cambias' : '', t.descripcion].filter(Boolean).join(' · '), id: t.clave })),
            { titulo: `«${nombre}» parte de…`, placeholder: 'sus colores, de entrada: después se cambian' });
        if (!base) return;
        const e = await colores.crear(nombre, base.id);
        if (e) { void ui.falla(`telar: no se creó: ${e}`); return; }
        elegido = nombre;
        seccion.pintar();
        void ui.estado(`telar: «${nombre}», un tema propio que parte de ${temas.nombre(base.id)}: ya se puede elegir en ⚙ modos y ⚙ mundos`, 5000);
    };

    const borrarTema = async (tema: string) => {
        const detalle = colores.raiz()
            ? `Se quita [temas.${tema}] de ${cli.nombreRaiz(colores.raiz())} y de esta máquina, con sus colores: deja de existir en todas las máquinas.`
            : `Se quita [temas.${tema}] de la configuración de esta máquina, con sus colores.`;
        const r = await ui.aviso(`¿Borrar el tema «${tema}»?`, 'Borrar', { detalle, destruye: true });
        if (r !== 'Borrar') return;
        const e = await colores.borrar(tema);
        if (e) { void ui.falla(`telar: no se borró: ${e}`); return; }
        if (elegido === tema) elegido = undefined;
        seccion.pintar();
        void ui.estado(`telar: «${tema}» borrado`, 3000);
    };

    const seccion = {
        clave: 'temas',
        nombre: 'temas',
        ayuda: 'los colores principales de cada tema (los fondos, las líneas, las tintas de letra) y los temas propios, en la raíz: valen en todas las máquinas',
        async abrir(sub?: string): Promise<void> {
            // de entrada, el que se ve; `temas:<tema>` (⚙ mundos › colores…), ese
            elegido = sub && temas.existe(sub) ? sub : undefined;
            seccion.pintar();
            const e = await colores.leer();
            if (e) void ui.falla(`telar: no se pudieron leer los colores propios: ${e}`);
            elegido = sub && temas.existe(sub) ? sub : elegido;
            pintarSiSeVe();
        },
        pintar(): void {
            const t = cual();
            const visto = modos.tema();
            const tema = temas.de(t) ?? temas.TEMAS[0];
            const ahora = colores.resueltos(t), fabrica = colores.resueltos(t, true), propios = colores.de(t);
            const n = Object.keys(propios).length;
            const h: string[] = [`<div class="fila dim">ves ${esc(temas.nombre(visto.clave))}: ${esc(porQue(visto.por))}`
                + `${t !== visto.clave ? `<span class="der">${boton({ texto: `ponerte ${tema.nombre}`, accion: 'tema-usar', valor: t, icono: I.ver, ayuda: 'en este modo, a mano (como ⚙ modos › tema): hasta cambiar de modo' })}</span>` : ''}</div>`];
            h.push(`<h2>temas<small>un clic elige cuál cambiar abajo · <span class="i">${I.ver}</span> el que ves · <span class="i">${I.editar}</span> con colores propios</small></h2>`);
            h.push(grillaTemas(t, visto.clave, x => Object.keys(colores.de(x)).length > 0));
            h.push(pieBotones([{ texto: 'nuevo tema…', accion: 'tema-nuevo', icono: I.nuevo, ayuda: 'uno propio: un nombre y el tema del que parte' }],
                { izq: '<span class="dim">uno propio: parte de otro, y se elige donde se elige un tema</span>', clase: 'te-pie' }));
            const de = tema.base ? `propio, parte de ${temas.nombre(tema.base)}: su de fábrica es el de ${temas.nombre(tema.base)}` : 'de fábrica';
            h.push(`<h2>${esc(tema.nombre)}<small>${esc(de)} · ${esc(textoDonde(colores.donde(t), colores.raiz(), t))}, y se ve aquí mientras lo eliges</small></h2>`);
            h.push(vistaPrevia(t));
            h.push(`<h2>fondos y líneas<small>lo demás sale de ellos: el hover, la fila activa</small></h2>`);
            h.push(`<div class="te-caja" data-tema="${esc(t)}">`);
            for (const e of temas.FONDOS) h.push(fila(e, t, ahora, fabrica, propios, !!tema.noche));
            h.push('</div>');
            h.push(`<h2>tintas de letra<small>un clic en la paleta la cambia al tiro; se lee bien desde 4,5:1</small></h2>`);
            h.push(`<div class="te-caja" data-tema="${esc(t)}">`);
            for (const e of temas.EDITABLES) h.push(fila(e, t, ahora, fabrica, propios, !!tema.noche));
            h.push('</div>');
            // el pie del tema: cuántos colores propios tiene, y lo que se le hace (volverlo de fábrica; borrarlo, si es propio)
            const pie: Boton[] = [];
            if (n) pie.push({ texto: 'todo de fábrica', accion: 'tema-fabrica', valor: t, icono: I.deshacer,
                ayuda: tema.base ? `sus colores, los de ${temas.nombre(tema.base)}` : `quitar [temas.${t}]` });
            if (tema.base) pie.push({ texto: 'borrar tema', accion: 'tema-borrar', valor: t, tono: 'peligro', icono: I.descartar,
                ayuda: `quitar [temas.${t}]: si un modo o un mundo lo tiene puesto, no se puede` });
            const cuenta = n ? `${n} propio${n === 1 ? '' : 's'}` : `todo de fábrica: [temas.${esc(t)}] no cambia ningún color`;
            h.push(pieBotones(pie, { izq: `<span class="dim">${cuenta}</span>`, clase: 'te-pie' }));
            ctx.pintar(h);
            atar(t);
        },
        async accion(accion: string, valor: string): Promise<boolean> {
            switch (accion) {
                case 'tema-elegir': elegido = temas.existe(valor) ? valor : undefined; colores.soltar(); enPrueba.clear(); seccion.pintar(); return true;
                case 'tema-tinta': {
                    // «<tema> <color> <#rrggbb>»; sin el valor, «<tema> <color> »: el de fábrica
                    const [tema, tinta, color] = valor.split(' ');
                    if (tema && tinta) await guardar(tema, tinta, color ? color : null);
                    return true;
                }
                case 'tema-fabrica': {
                    enPrueba.clear();
                    const e = await colores.deFabrica(valor);
                    if (ctx.seVe('temas')) seccion.pintar();
                    if (e) void ui.falla(`telar: no se pudo: ${e}`);
                    else void ui.estado(`telar: ${temas.nombre(valor)}, todo de fábrica`, 3000);
                    return true;
                }
                case 'tema-nuevo': await nuevo(); return true;
                case 'tema-borrar': if (valor) await borrarTema(valor); return true;
                case 'tema-usar': if (temas.existe(valor)) modos.poner('tema', valor); return true;
            }
            return false;
        },
    };
    return seccion;
};
