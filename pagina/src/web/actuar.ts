// «Acción…»: pedirle algo a un hilo o a un agente sobre una entidad, con su contexto (docs/propuestas/acciones.md).
// Un panel con tres secciones: el contexto (lo que `telar objeto` sabe de ella, y lo que se pide), la skill (opcional,
// las del agente del destino) y el destino (el hilo de la entidad, los agentes, los hilos), ya elegido. ⌘⏎ lo manda
// (`telar actuar`, POST /actuar); la casilla de abajo lo deja escrito en la entrada del hilo, sin mandar.
// Todo del mismo tamaño: lo que distingue es el color y el ícono (web/iconos.ts).

import * as cli from '../cli';
import { modelo } from '../modelo';
import { C, I } from './iconos';
import * as ui from './ui';

function el<K extends keyof HTMLElementTagNameMap>(tag: K, clase = '', texto?: string): HTMLElementTagNameMap[K] {
    const e = document.createElement(tag);
    if (clase) e.className = clase;
    if (texto !== undefined) e.textContent = texto;
    return e;
}

const norm = (t: string | undefined) => (t ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

/** Una lista con un filtro arriba y una opción elegida (la de la skill, la del destino): ↑ ↓ mueven la elección. */
interface Opcion { valor: string; nombre: string; detalle?: string; icono: string; color: string }
function lista(titulo: string, placeholder: string, alCambiar: (valor: string) => void) {
    const seccion = el('section');
    seccion.appendChild(el('h4', '', titulo));
    const filtro = el('input'); filtro.placeholder = placeholder; filtro.spellcheck = false;
    const caja = el('div', 'web-lista');
    seccion.append(filtro, caja);
    let opciones: Opcion[] = [], elegida = '', vis: Opcion[] = [];
    const pintar = () => {
        caja.replaceChildren();
        const q = norm(filtro.value);
        vis = opciones.filter(o => !q || norm(`${o.nombre} ${o.detalle ?? ''}`).includes(q));
        for (const o of vis) {
            const f = el('div', `web-op${o.valor === elegida ? ' sel' : ''}`);
            f.style.setProperty('--c', `var(--${o.color})`);
            f.append(el('span', 'i ico', o.valor === elegida ? I.hecha : o.icono), el('span', 'l', o.nombre));
            if (o.detalle) f.appendChild(el('span', 'd', o.detalle));
            f.title = [o.nombre, o.detalle].filter(Boolean).join('\n');
            f.addEventListener('click', () => elegir(o.valor));
            caja.appendChild(f);
        }
        caja.querySelector('.sel')?.scrollIntoView({ block: 'nearest' });
    };
    const elegir = (valor: string) => { if (valor === elegida) return; elegida = valor; pintar(); alCambiar(valor); };
    filtro.addEventListener('input', pintar);
    filtro.addEventListener('keydown', e => {
        if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
        e.preventDefault();
        const i = vis.findIndex(o => o.valor === elegida);
        const j = Math.max(0, Math.min(vis.length - 1, i + (e.key === 'ArrowDown' ? 1 : -1)));
        if (vis[j]) elegir(vis[j].valor);
    });
    return {
        seccion, filtro,
        poner(nuevas: Opcion[], eleccion?: string) {
            opciones = nuevas;
            elegida = eleccion ?? (opciones.some(o => o.valor === elegida) ? elegida : opciones[0]?.valor ?? '');
            pintar();
        },
        get valor() { return elegida; },
    };
}

/** El contexto de cada entidad, ya leído (`telar objeto`), por unos minutos. */
const contextos = new Map<string, { hora: number; r: Awaited<ReturnType<typeof cli.objeto>> }>();

/** Las skills de cada destino, ya leídas: abrir el panel otra vez es instantáneo. Se olvidan a los 5 minutos. */
const skillsLeidas = new Map<string, { hora: number; lista: cli.JsonSkill[] }>();

async function skillsDe(hilo: string, carpeta: string): Promise<cli.JsonSkill[]> {
    const llave = `${hilo}|${carpeta}`;
    const guardadas = skillsLeidas.get(llave);
    if (guardadas && Date.now() - guardadas.hora < 5 * 60_000) return guardadas.lista;
    const r = hilo ? await cli.skills(hilo) : carpeta ? await cli.skills('', carpeta) : undefined;
    const lista_ = [...(r?.datos?.skills ?? [])].sort((a, b) => (b.usada ?? 0) - (a.usada ?? 0) || a.nombre.localeCompare(b.nombre));
    if (r?.datos) skillsLeidas.set(llave, { hora: Date.now(), lista: lista_ });
    return lista_;
}

/** El panel de «Acción…» para una entidad (su dirección). Se abre al tiro con lo que la página ya sabe (los hilos y
 *  los agentes, del modelo); lo que hay que pedir (el contexto de la entidad, las skills del destino) llega después y
 *  se pinta cuando llega. Un clic fuera del panel, ⎋ o «cancelar» lo cierran. */
export async function abrir(direccion: string): Promise<void> {
    const [tipo, id] = [direccion.slice(0, direccion.indexOf(':')), direccion.slice(direccion.indexOf(':') + 1)];
    const esProyecto = tipo === 'proyecto';
    const suHilo = esProyecto ? modelo.hilos.find(h => h.relativa === id && !h.archivado) : undefined;

    const c = el('dialog', 'web-caja web-actuar');
    document.body.appendChild(c);
    const titulo = el('h3', '', `Acción · ${id}`);
    c.appendChild(titulo);

    // el contexto: lo que se sabe de la entidad (llega después), y lo que se pide
    const ctx = el('section');
    ctx.appendChild(el('h4', '', 'contexto'));
    const linea = el('div', 'web-op');
    linea.style.setProperty('--c', 'var(--azul)');
    const nombre = el('span', 'l', id);
    linea.append(el('span', 'i ico', esProyecto ? I.carpeta : I.direccion), nombre, el('span', 'd', direccion));
    const campos = el('div', 'campos', 'leyendo…');
    const nota = el('textarea'); nota.placeholder = 'qué quieres que haga (opcional si eliges una skill)'; nota.rows = 3;
    ctx.append(linea, campos, nota);

    const skills = lista('skill · opcional', 'buscar una skill', () => {});
    const sinSkill = { valor: '', nombre: 'sin skill', detalle: 'solo el prompt, con el contexto', icono: I.escribir, color: C.otro };
    let pedidas = '';
    async function cargarSkills(destino: string): Promise<void> {
        const hilo = destino === '' ? suHilo?.nombre ?? '' : destino;
        const llave = `${hilo}|${esProyecto && !hilo ? id : ''}`;
        pedidas = llave;
        skills.poner([sinSkill, { valor: '…', nombre: 'leyendo sus skills…', icono: I.accion, color: 'dim' }], skills.valor || '');
        const lista_ = await skillsDe(hilo, esProyecto && !hilo ? id : '');
        if (pedidas !== llave) return;  // ya se eligió otro destino
        skills.poner([sinSkill, ...lista_.map(x => ({ valor: x.nombre, nombre: `/${x.nombre}`,
            detalle: (x.usada ? `${x.usada}× · ` : '') + (x.descripcion ?? ''), icono: I.accion, color: C.agente }))]);
    }
    const destinos = lista('a quién', 'buscar un hilo o un agente', valor => void cargarSkills(valor));

    // los destinos, de lo que la página ya tiene: el hilo de la entidad, los agentes residentes y los hilos
    const agentes = modelo.secciones.filter(x => x.grupo === 'agentes');
    const deAgente = (h: cli.JsonHilo) => agentes.some(a => cli.enSeccion(a, h.nombre));
    destinos.poner([
        ...(esProyecto ? [{ valor: '', nombre: suHilo ? `su hilo · ${suHilo.nombre}` : 'su hilo (se abre con el prompt)',
            detalle: id, icono: suHilo ? I.agente : I.nuevo, color: suHilo ? C.ir : C.hecho }] : []),
        ...agentes.map(a => ({ valor: a.nombre, nombre: a.nombre, detalle: 'agente: se le encarga', icono: I.agente, color: C.agente })),
        ...modelo.hilos.filter(h => !h.archivado && h.nombre !== suHilo?.nombre && !deAgente(h))
            .map(h => ({ valor: h.nombre, nombre: h.nombre, detalle: h.remoto ? `en ${h.remoto}: por el bus` : h.relativa || '',
                icono: h.vivo ? I.ver : I.retomar, color: C.ir })),
    ]);
    c.append(ctx, skills.seccion, destinos.seccion);

    const pie = el('div', 'botones');
    const solo = el('label', 'solo');
    const caja = el('input'); caja.type = 'checkbox';
    solo.append(caja, el('span', '', 'dejarlo escrito, sin mandar'));
    const si = el('a', '', '⌘⏎ ejecutar'); const no = el('a', '', 'cancelar');
    pie.append(solo, si, no);
    c.appendChild(pie);

    let hecho = false;
    const cerrar = () => { if (hecho) return; hecho = true; c.close(); c.remove(); };
    const ejecutar = async () => {
        if (!skills.valor && !nota.value.trim()) { nota.focus(); ui.estado('elige una skill, o escribe qué quieres', 4000); return; }
        const destino = destinos.valor, skill = skills.valor === '…' ? '' : skills.valor;
        cerrar();
        const r = await ui.progreso({ titulo: `telar: ${nombre.textContent}…` },
            () => cli.actuar(direccion, destino, skill, nota.value.trim(), caja.checked));
        if (!r.datos) { void ui.falla(`telar: ${r.error ?? 'no se pudo'}`); return; }
        ui.estado(`«${r.datos.destino}»${r.datos.maquina ? ` en ${r.datos.maquina}` : ''}: ${r.datos.como}`, 6000);
        await modelo.sondear();
    };
    si.addEventListener('click', () => void ejecutar());
    no.addEventListener('click', cerrar);
    c.addEventListener('cancel', e => { e.preventDefault(); cerrar(); });
    c.addEventListener('keydown', e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); void ejecutar(); } });
    // un clic afuera (en el fondo, que es del <dialog> mismo) lo cierra, como a las demás cajas
    c.addEventListener('mousedown', e => {
        const r = c.getBoundingClientRect();
        if (e.target === c && (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom)) cerrar();
    });

    c.showModal();
    nota.focus();

    // lo que hay que pedir, sin esperar uno al otro (el contexto, guardado unos minutos: abrirlo de nuevo es al tiro)
    const guardado = contextos.get(direccion);
    const pedido = guardado && Date.now() - guardado.hora < 5 * 60_000 ? Promise.resolve(guardado.r)
        : cli.objeto(direccion).then(r => { if (r.datos) contextos.set(direccion, { hora: Date.now(), r }); return r; });
    void pedido.then(r => {
        if (hecho) return;
        if (!r.datos) { campos.textContent = r.error ?? 'no lo encontré'; return; }
        const o = r.datos;
        titulo.textContent = `Acción · ${o.titulo}`;
        nombre.textContent = o.titulo;
        // lo corto y útil de sus campos (no las fechas de archivo ni lo largo): el resto lo abre el agente
        campos.textContent = [o.estado && `estado ${o.estado}`, ...Object.entries(o.campos ?? {})
            .filter(([k, v]) => (typeof v === 'string' || typeof v === 'number') && String(v).length <= 40 && !/modificad|mtime|creado/.test(k))
            .slice(0, 4).map(([k, v]) => `${k} ${v}`)].filter(Boolean).join(' · ');
    });
    void cargarSkills(destinos.valor);
}
