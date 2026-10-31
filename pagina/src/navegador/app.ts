// La página de telar: a la izquierda la barra de hilos (vistas/hilos.ts); a la derecha, una vista a la vez: el
// dashboard (vistas/dashboard/panel.ts, que pinta en vistas/dashboard/vista.ts) o un hilo (web/vistas-hilo.ts), su carpeta o
// «compartir». Todo en este documento, sin marcos:
//
//   - la API, por `fetch` a `/api` (cli.ts; la misma de `telar serve`, detrás de la llave de esta página);
//   - los avisos, campos y menús que piden el dashboard y la barra (web/ui.ts) los pone esta página, encima de
//     todo (web/interfaz.ts).
//
// Se empaqueta con esbuild (scripts/navegador.mjs) en src/telar/web/app.js, que sirve `telar serve --web`; los
// estilos van aparte, en src/telar/web/marco.css.

import * as cli from '../cli';
import { modelo } from '../modelo';
import { esc } from '../estilo';
import { I } from '../web/iconos';
import { BarraHilos, type Guardado } from '../vistas/hilos';
import { crearOrdenes } from '../web/ordenes';
import { Dashboard } from '../vistas/dashboard/panel';
import { montar as montarCarpeta, type Vuelta } from '../web/carpeta';
import { montar as montarCompartir } from '../web/compartir';
import { montar as montarObjeto, partir as partirDireccion } from '../web/objeto';
import * as ui from '../web/ui';
import * as version from '../web/version';
import * as lado from '../web/lado';
import * as modos from '../web/modos';
import * as buscador from '../web/buscador';
import { type Vista, vista, VISTAS } from '../web/vistas-hilo';


// ── la bandeja del equipo: la del servidor que sirve la página («aqui») o la de la máquina que diga /config ──

void cli.config().then(r => {
    if (r.datos?.equipo) { modelo.equipoRemoto = r.datos.equipo.trim(); void modelo.leerEquipo(); }
});

// ── a la izquierda la barra (vistas/hilos.ts); a la derecha, una vista a la vez: el dashboard o un hilo ──

const marcos = () => document.getElementById('vistas')!;
let actual = 'dashboard';

/** Lo que se ve a la derecha: el dashboard, una vista de un hilo, su carpeta o «compartir», cada una dibujada en un
 *  elemento de la página con su clave en `data-p`. */
const vistas = () => [...marcos().children] as HTMLElement[];

/** Las vistas de un hilo dibujadas en la página (la lectura, la conversación), por su clave: se les avisa al
 *  volver a verse. */
const montadas = new Map<string, Vista>();

/** Una vista: un elemento que su módulo llena (vistas/dashboard/vista.ts, web/carpeta.ts, web/compartir.ts, las vistas
 *  de un hilo). */
function nuevaVista(clave: string): HTMLElement {
    const s = document.createElement('section');
    s.dataset.p = clave;
    marcos().appendChild(s);
    return s;
}

/** Lo que la barra recuerda (el orden de cada grupo): en este navegador. */
const guardado: Guardado = {
    get: <T>(clave: string) => {
        try { return JSON.parse(localStorage.getItem(`telar.barra.${clave}`) ?? 'null') ?? undefined as T | undefined; } catch { return undefined; }
    },
    update: async (clave, valor) => { try { localStorage.setItem(`telar.barra.${clave}`, JSON.stringify(valor)); } catch { /* sin almacén */ } },
};

/** Cómo se ve un hilo: una de sus vistas (web/vistas-hilo.ts): la terminal, la lectura, la conversación. En
 *  pantalla ancha empieza en la terminal; en angosta, en la conversación; la barra de arriba del hilo (y ⌥T,
 *  ⌥L, ⌥C) cambian. */
const modo: Record<string, string> = {};
const angosto = () => document.body.classList.contains('angosto');
const esHilo = (que: string) => !(que === 'dashboard' || que === 'compartir' || que.startsWith('doc:') || que.startsWith('arch:') || que.startsWith('obj:'));
function forma(que: string): string {
    if (!esHilo(que)) return '';
    // uno archivado o cerrado no tiene terminal: se ve su conversación, con «retomar» (web/conversacion.ts)
    if (!que.startsWith('rem:') && modelo.hilos.some(h => h.nombre === que && (!h.vivo || h.archivado))) return 'conv';
    return modo[que] ?? (angosto() ? 'conv' : 'term');
}
/** las terminales que se miraron hace poco: cada una es una vista de tmux abierta, y se cierran las viejas */
const TOPE = 8;
const usadas: string[] = [];
/** Cierra la terminal de un hilo que ya no la tiene (archivado, cerrado). */
function soltar(hilo: string): void {
    const llave = `term:${hilo}`;
    if (!montadas.has(llave)) return;
    cerrarVista(llave);
    const j = usadas.indexOf(llave);
    if (j >= 0) usadas.splice(j, 1);
}
/** Cierra una vista de un hilo (su conexión, sus lecturas) y la saca de la página. */
function cerrarVista(llave: string): void {
    montadas.get(llave)?.cerrar();
    montadas.delete(llave);
    vistas().find(x => x.dataset.p === llave)?.remove();
}

/** De dónde se vino al visor de un archivo, a la carpeta de un hilo o a la vista de un objeto: lo que se veía antes
 *  (un hilo, en la vista que tenía; el dashboard), adonde vuelve su «‹ …». Pasar de un archivo a otro no la cambia. */
let origen = '';
const esDocumento = (que: string) => que.startsWith('doc:') || que.startsWith('arch:') || que.startsWith('obj:');

/** La vuelta del visor (web/carpeta.ts) y de la vista de un objeto: «‹ Telar · conversación», «‹ dashboard». */
const vuelta = (): Vuelta | null => vueltaA(origen);
function vueltaA(o: string): Vuelta | null {
    if (!o || esDocumento(o)) return null;
    const como = forma(o), nombre = o.startsWith('rem:') ? o.slice(4) : o;
    return { nombre: como ? `${nombre} · ${vista(como)?.nombre ?? como}` : nombre, ir: () => mostrar(o) };
}

/** Una dirección (`tipo:id[@máquina]`) en la vista de siempre de su objeto: una tarea, en su ficha (con «‹» de vuelta
 *  a lo que se veía); un archivo o un proyecto, en el visor (el proyecto, su carpeta); un hilo de la lista (en esa
 *  máquina, si la dice), el hilo, como un clic en la barra. Si no es de esas, o es un hilo que la lista no tiene,
 *  false: la vista del objeto (web/objeto.ts), que dice si existe y deja escribirle. */
function abrirDireccion(direccion: string): boolean {
    const { tipo, id, maquina } = partirDireccion(direccion);
    const alla = maquina && maquina !== modelo.aqui ? maquina : '';
    if (!id) return false;
    if (tipo === 'tarea') { void hoy.abrirTarea(JSON.stringify(['tareas', id, id]), vueltaA(actual) ?? undefined); return true; }
    if (tipo === 'archivo' || tipo === 'proyecto') { mostrar(`arch:${alla ? `${alla}:` : ''}${id}`); return true; }
    if (tipo === 'hilo') {
        const de = (x: { remoto?: string }) => (x.remoto && x.remoto !== '?' ? x.remoto : modelo.aqui);
        const h = modelo.hilos.find(x => x.nombre === id && (!alla || de(x) === alla));
        if (h) { void ui.orden(h.vivo && !h.archivado ? 'telar.ir' : 'telar.retomar', { hilo: id }); return true; }
    }
    return false;
}

/** A la derecha: «dashboard» («config»: el dashboard en su configuración, el ⚙ de la cabecera), un hilo de aquí (su terminal o su conversación), «rem:<máquina>:<hilo>» (uno de
 *  otra máquina: su terminal reenviada, o su conversación por el bus), «doc:<hilo>» (su carpeta y su documento), «arch:<ruta>» (un
 *  archivo), «obj:<dirección>» (un objeto: `abrirDireccion`, o su vista) o «compartir» (lo
 *  que el teléfono le compartió a la app: la página se abrió en /compartir). */
function mostrar(que: string): void {
    if (!que) return;
    // el ⚙ de la cabecera: la configuración, en el dashboard
    if (que === 'config') { void hoy.irAPestana('config'); return; }
    if (que.startsWith('obj:') && abrirDireccion(que.slice(4))) return;
    if (esDocumento(que) && !esDocumento(actual)) origen = actual;
    actual = que;
    let f: HTMLElement | undefined;
    if (que === 'dashboard') {
        if (!hoy.panel) hoy.abrir();
        f = vistas().find(x => x.dataset.p === 'dashboard');
    } else {
        const como = forma(que), llave = como ? `${como}:${que}` : que;
        f = vistas().find(x => x.dataset.p === llave);
        if (esDocumento(que) || que === 'compartir') {
            f ??= nuevaVista(llave);
            if (que === 'compartir') montarCompartir(f, location.search);
            else if (que.startsWith('obj:')) void montarObjeto(f, que.slice(4), ui.markdown, vuelta());
            else if (que.startsWith('arch:')) void montarCarpeta(f, '', que.slice(5), ui.markdown, vuelta());
            else void montarCarpeta(f, que.slice(4), '', ui.markdown, vuelta());
        } else if (!f) {
            const remoto = que.startsWith('rem:') ? que.slice(4) : '';
            const i = remoto.indexOf(':');
            const hilo = remoto ? remoto.slice(i + 1) : que, maquina = remoto ? remoto.slice(0, i) : '';
            f = nuevaVista(llave);
            montadas.set(llave, (vista(como) ?? VISTAS[0]).montar(f, { hilo, maquina }, () => cambiarVista('term')));
        }
        if (como === 'term') {
            const j = usadas.indexOf(llave);
            if (j >= 0) usadas.splice(j, 1);
            usadas.push(llave);
            while (usadas.length > TOPE) cerrarVista(usadas.shift()!);
        }
    }
    for (const x of vistas()) x.hidden = x !== f;
    pintarAcciones(que);
    // a la derecha, la ficha del agente, si lo que se ve es el hilo de uno (web/lado.ts)
    void lado.mostrar(que, !!forma(que));
    // ya a la vista: la terminal toma el teclado, la lectura y la conversación se releen
    if (f && forma(que)) montadas.get(f.dataset.p ?? '')?.mostrada?.();
    // lo que se ve, como se nombra un hilo: «hilo» si es de esta máquina, «máquina:hilo» si es de otra (como
    // `scp máquina:ruta`; con la persona sería «ana@laptop:Faro»). Lo muestra la cabecera (indice.html)
    const remoto = que.startsWith('rem:') ? que.slice(4) : '';
    const nombre = remoto ? remoto
        : que.startsWith('doc:') ? `${que.slice(4)} · carpeta`
        : que.startsWith('arch:') ? relativa(que.slice(5)) : que.startsWith('obj:') ? que.slice(4) : que;
    window.telar?.donde?.(que === 'dashboard' ? null : { texto: nombre, otraMaquina: !!remoto });
    document.title = que === 'dashboard' ? 'telar' : `${nombre} · telar`;
    document.body.classList.remove('en-lista');
    document.body.classList.add('en-detalle');
    // la barra marca lo que se ve
    barra.dashboardActivo = que === 'dashboard';
    barra.mostrado = que === 'dashboard' ? '' : que;
    barra.refrescar(true);
}

// ── arrancar ──────────────────────────────────────────────────────────────────

const hoy = new Dashboard();
hoy.donde = () => nuevaVista('dashboard');
hoy.mostrarme = () => mostrar('dashboard');
const barra = new BarraHilos();
barra.estado = guardado;
barra.dashboardActivo = true;
barra.mostrado = '';
ui.usarNavegacion({ mostrar, ordenes: crearOrdenes({ hoy, barra, mostrar, soltar, releerOtras: () => otras() }) });
barra.montar(document.getElementById('barra')!);
hoy.alCambiarFoco = () => {
    const app = hoy.appActual;
    if (barra.appActiva === app) return;
    barra.appActiva = app;
    barra.refrescar(true);
};
// las pestañas del dashboard son un grupo de la barra: sus filas, sus cuentas y la que se ve, al día con cada pintada
barra.pestanasDashboard = () => hoy.pestanas();
// (también la app: al salir de ella a una pestaña, su fila dejaba de ser la que se ve y seguía marcada)
hoy.alPintar = () => { barra.pestanaActiva = hoy.pestanaActiva(); barra.appActiva = hoy.appActual; barra.refrescar(); };
modelo.cambio.event(() => barra.refrescar());

// un archivo soltado donde nadie lo recibe (lo recibe la terminal de un hilo: web/terminal.ts) no hace nada: de
// fábrica, el navegador navega al archivo y la página se pierde
window.addEventListener('dragover', e => {
    if (e.defaultPrevented || !e.dataTransfer?.types.includes('Files')) return;
    e.preventDefault(); e.dataTransfer.dropEffect = 'none';
});
window.addEventListener('drop', e => { if (e.dataTransfer?.types.includes('Files')) e.preventDefault(); });

// los hilos de otras máquinas (sus fotos): en HILOS, cada uno con su máquina; y el nombre de esta, para la
// columna ancha
// una versión nueva de telar, arriba (web/version.ts): un clic la instala; si no se puede desde aquí, ⚙ versión
lado.montar();
version.vigilar(() => { mostrar('dashboard'); void hoy.irAPestana('config', 'version'); });
// el buscador (⌘K): sus fuentes. Cada una da lo suyo y cómo abrirlo; el buscador solo filtra y muestra
// (web/buscador.ts). Abrir algo estando en foco lo abre ahí mismo, sin barra ni cabecera
const recencia = (iso?: string | null) => {
    const t = iso ? Date.parse(iso) : NaN;
    return Number.isNaN(t) ? 0 : Math.max(0, 100 - (Date.now() - t) / 3600000);   // 100 recién, 0 hace 4 días o más
};
buscador.registrar({
    clave: 'hilos', nombre: 'hilos', orden: 1, color: 'azul',
    resultados: () => {
        // (sin los de un agente, que van en «agentes», y sin una carpeta que desde aquí se ve como «../..»)
        const deAgentes = new Set(modelo.secciones.filter(x => x.grupo === 'agentes').map(x => x.nombre));
        const legible = (r?: string) => (r && !r.startsWith('..') ? r : '');
        const aqui = modelo.hilos.filter(h => !deAgentes.has(h.nombre) && (!h.agente || cli.nombreVisible(h) !== h.agente)).map(h => ({
            titulo: cli.nombreVisible(h), icono: h.archivado ? '▫' : h.vivo ? '●' : '○',
            detalle: [legible(h.relativa), h.remoto ? `en ${h.remoto}` : '', h.archivado ? 'archivado' : !h.vivo ? 'sin ventana' : ''].filter(Boolean).join(' · '),
            claves: h.nombre, peso: (h.archivado ? 0 : h.vivo ? 50 : 20) + recencia(h.actividad || h.atencion_desde) / 2,
            abrir: () => (h.archivado || !h.vivo ? ui.orden('telar.retomar', { hilo: h.nombre }) : mostrar(h.nombre)),
        }));
        // los de las otras máquinas, de su foto: se leen y se les escribe por el bus
        const ya = new Set(modelo.hilos.map(h => `${h.remoto ?? ''}|${h.nombre}`));
        const otras = barra.otras.flatMap(m => m.hilos.filter(x => x.vivo && !ya.has(`${m.nombre}|${x.nombre}`) && !deAgentes.has(x.nombre)).map(x => ({
            titulo: x.nombre, icono: '⇄', detalle: [legible(x.relativa), `en ${m.nombre}`].filter(Boolean).join(' · '), peso: 35,
            abrir: () => ui.orden('telar.irRemoto', `${m.nombre}|${x.nombre}`),
        })));
        return [...aqui, ...otras];
    },
});
buscador.registrar({
    clave: 'agentes', nombre: 'agentes', orden: 2, color: 'violeta',
    resultados: () => modelo.secciones.filter(s => s.grupo === 'agentes').map(s => {
        const suyo = modelo.hilos.find(h => h.nombre === s.nombre);
        return {
            titulo: s.nombre, icono: '◈', detalle: suyo?.vivo ? 'su hilo, abierto' : 'su casa', peso: suyo?.vivo ? 60 : 30,
            abrir: () => (suyo?.vivo ? mostrar(s.nombre) : ui.orden('telar.seccion', s.clave)),
        };
    }),
});
buscador.registrar({
    clave: 'dashboard', nombre: 'dashboard', orden: 3, color: 'cian',
    resultados: () => [
        ...hoy.pestanas().map((p, i) => ({
            titulo: p.nombre, icono: '▦', detalle: p.tecla ? `pestaña · ${p.tecla}` : 'pestaña', claves: p.clave, peso: 40 - i,
            abrir: () => { mostrar('dashboard'); return hoy.irAPestana(p.accion, p.valor); },
        })),
        ...hoy.seccionesConfig().map(c => ({
            titulo: `⚙ ${c.nombre}`, icono: '⚙', detalle: c.ayuda, claves: `configuracion ${c.clave}`, peso: 5,
            abrir: () => { mostrar('dashboard'); return hoy.irAPestana('config', c.clave); },
        })),
    ],
});
buscador.registrar({
    clave: 'modos', nombre: 'modos', orden: 4, color: 'amarillo',
    resultados: () => modos.lista().map(m => ({
        titulo: `modo ${m.nombre}`, icono: '◧', detalle: m.clave === modos.puesto().clave ? 'puesto' : '', claves: m.clave,
        peso: m.clave === modos.puesto().clave ? 0 : 10, abrir: () => modos.cambiar(m.clave),
    })),
});
buscador.registrar({
    clave: 'ordenes', nombre: 'órdenes', orden: 5, color: 'verde',
    resultados: () => [
        { titulo: 'hilo nuevo', icono: '+', detalle: 'un tab con su agente', claves: 'nuevo crear abrir', abrir: () => ui.orden('telar.nuevo') },
        { titulo: 'agente nuevo', icono: '+', detalle: 'un agente residente: su carpeta', claves: 'nuevo crear', abrir: () => ui.orden('telar.agenteNuevo') },
        { titulo: 'máquinas', icono: '⌂', detalle: 'tus máquinas y los servidores', claves: 'servidores maquinas', abrir: () => { location.href = '/maquinas'; } },
        { titulo: 'actualizar la lista', icono: '↻', detalle: 'volver a leer los hilos', claves: 'refrescar', abrir: () => ui.orden('telar.actualizar') },
    ],
});
buscador.montar();

// los modos (estándar, foco…): lo de este navegador al tiro, y el selector de la cabecera, «◧ estándar»
modos.montar();
const selectorModo = document.getElementById('modos-sel');
const nombrarModo = () => { if (selectorModo) selectorModo.textContent = `◧ ${modos.puesto().nombre}`; };
nombrarModo();
modos.alCambiar(nombrarModo);
selectorModo?.addEventListener('click', async e => {
    e.preventDefault();
    const filas = [
        ...modos.lista().map(m => ({ label: m.nombre, description: m.clave === modos.puesto().clave ? '← puesto' : '', id: m.clave })),
        { label: 'editar los modos…', description: '⚙ modos: qué dice cada uno, guardar lo cambiado, uno nuevo', id: '__editar' },
    ];
    const elegido = await ui.elegir(filas, { titulo: 'modo de la página', placeholder: '⌥⇧F foco y vuelta · ⌥⇧M el siguiente' });
    if (!elegido) return;
    if (elegido.id === '__editar') { mostrar('dashboard'); void hoy.irAPestana('config', 'modos'); }
    else modos.cambiar(elegido.id);
});

void fetch('/api/salud', { cache: 'no-store' }).then(r => r.json()).then((s: { maquina?: string }) => {
    barra.aqui = modelo.aqui = s.maquina ?? ''; barra.refrescar(true);
}).catch(() => undefined);
const otras = async () => {
    const r = await cli.espejos().catch(() => undefined);
    const nuevas = (r?.datos?.espejos ?? []).filter(e => !e.error)
        .map(e => ({ nombre: e.nombre, en_linea: e.en_linea, edad: e.edad, hilos: e.hilos.filter(h => !h.remoto) }));
    if (JSON.stringify(nuevas) !== JSON.stringify(barra.otras)) { barra.otras = nuevas; barra.refrescar(true); }
};
void otras();
// cada 6 s: es leer un archivo de aquí (el nodo guarda la foto apenas llega por el bus, y la otra máquina la publica
// apenas cambian sus hilos)
setInterval(() => void otras(), 6 * 1000);

/** Una ruta, relativa a la raíz del repositorio si está adentro (para el título). */
function relativa(ruta: string): string {
    const raiz = (modelo.raiz || '').replace(/\/$/, '');
    return raiz && ruta.startsWith(raiz + '/') ? ruta.slice(raiz.length + 1) : ruta;
}

/** La barra de acciones de un hilo, arriba: sus vistas (con su atajo) y su carpeta. Solo con un hilo a la vista. */
function pintarAcciones(que: string): void {
    const barraH = document.getElementById('acciones')!;
    const como = forma(que);
    barraH.hidden = !como;
    if (!como) return;
    const local = !que.startsWith('rem:');
    barraH.innerHTML = VISTAS.map(v => `<a data-vista="${v.clave}" class="${v.clave === como ? 'si' : ''}" title="${v.ayuda}">${v.nombre} <span class="tecla">${v.atajo}</span></a>`).join('')
        + '<span class="lleno"></span>'
        + (local ? (() => {
            // su carpeta, como ruta (relativa a la raíz si está adentro); sin vínculo, la raíz
            const h = modelo.porNombre(que);
            const ruta = h?.relativa && h.relativa !== '.' ? h.relativa : h?.ruta ? relativa(h.ruta) : '';
            return `<a data-carpeta="1" class="ruta" title="${esc(`${ruta || 'la raíz'}\nclic: la carpeta del hilo y su documento`)}"><span class="i">${I.carpeta}</span> ${esc(ruta || '~')}</a>`;
        })() : '');
}

/** Cambiar la vista del hilo que se ve (la barra de acciones, o ⌥ y su letra desde adentro de una vista). */
function cambiarVista(clave: string): void {
    if (!forma(actual) || !vista(clave) || forma(actual) === clave) return;
    modo[actual] = clave;
    mostrar(actual);
}

document.getElementById('acciones')!.addEventListener('click', e => {
    const a = (e.target as HTMLElement).closest('a');
    if (!a) return;
    if (a.dataset.vista) cambiarVista(a.dataset.vista);
    else if (a.dataset.carpeta) mostrar(`doc:${actual}`);
});
// el atajo (⌥ y la letra), antes que nadie: la terminal se lo comería
window.addEventListener('keydown', e => {
    if (!e.altKey || e.metaKey || e.ctrlKey) return;
    const v = VISTAS.find(x => x.tecla === e.code);
    if (v && forma(actual)) { e.preventDefault(); e.stopPropagation(); cambiarVista(v.clave); }
}, true);

declare global {
    interface Window {
        telar?: {
            mostrar?: (que: string) => void;
            donde?: (lo: { texto: string; otraMaquina: boolean } | null) => void;
            /** la transición de una mudanza, sin mudar nada: para mirarla y afinarla (web/mudanza.ts, `ensayo`) */
            ensayoMudanza?: (maquina?: string, falla?: boolean) => Promise<void>;
        };
    }
}
window.telar = { ...(window.telar ?? {}), mostrar,
    ensayoMudanza: async (maquina, falla) => { const { ensayo } = await import('../web/mudanza'); await ensayo(maquina, falla); } };
// abierta por «compartir» del teléfono (share_target del manifiesto): eso primero, también en el celular
const compartiendo = location.pathname === '/compartir';
mostrar(compartiendo ? 'compartir' : 'dashboard');
// en el celular se empieza por la lista
if (document.body.classList.contains('angosto') && !compartiendo) { document.body.classList.remove('en-detalle'); document.body.classList.add('en-lista'); }

setInterval(() => { if (hoy.panel && !document.hidden && actual === 'dashboard') void hoy.actualizar(); }, 60 * 1000);
// al volver a la pestaña, el dashboard se pone al día (lo que pasó mientras no se miraba)
document.addEventListener('visibilitychange', () => { if (hoy.panel?.visible) void hoy.actualizar(); });
// el modelo (los hilos, su atención) se sondea mientras la página se mira
const sondear = async () => {
    if (!document.hidden) await modelo.sondear().catch(() => undefined);
    setTimeout(sondear, modelo.error || !modelo.viva ? 5000 : 3000);
};
void modelo.sondear(true).catch(() => undefined).then(sondear);
