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
import { BarraHilos, type Guardado } from '../vistas/hilos';
import { crearOrdenes } from '../web/ordenes';
import { Dashboard } from '../vistas/dashboard/panel';
import { montar as montarCarpeta, type Vuelta } from '../web/carpeta';
import { montar as montarCompartir } from '../web/compartir';
import * as ui from '../web/ui';
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
const esHilo = (que: string) => !(que === 'dashboard' || que === 'compartir' || que.startsWith('doc:') || que.startsWith('arch:'));
function forma(que: string): string {
    if (!esHilo(que)) return '';
    return modo[que] ?? (angosto() ? 'conv' : 'term');
}
/** las terminales que se miraron hace poco: cada una es una vista de tmux abierta, y se cierran las viejas */
const TOPE = 8;
const usadas: string[] = [];
/** Cierra una vista de un hilo (su conexión, sus lecturas) y la saca de la página. */
function cerrarVista(llave: string): void {
    montadas.get(llave)?.cerrar();
    montadas.delete(llave);
    vistas().find(x => x.dataset.p === llave)?.remove();
}

/** De dónde se vino al visor de un archivo o a la carpeta de un hilo: lo que se veía antes (un hilo, en la vista que
 *  tenía; el dashboard), adonde vuelve su «‹ …». Pasar de un archivo a otro no la cambia. */
let origen = '';
const esDocumento = (que: string) => que.startsWith('doc:') || que.startsWith('arch:');

/** La vuelta del visor (web/carpeta.ts): «‹ Telar · conversación», «‹ dashboard». */
function vuelta(): Vuelta | null {
    const o = origen;
    if (!o || esDocumento(o)) return null;
    const como = forma(o), nombre = o.startsWith('rem:') ? o.slice(4) : o;
    return { nombre: como ? `${nombre} · ${vista(como)?.nombre ?? como}` : nombre, ir: () => mostrar(o) };
}

/** A la derecha: «dashboard» («config»: el dashboard en su configuración, el ⚙ de la cabecera), un hilo de aquí (su terminal o su conversación), «rem:<máquina>:<hilo>» (uno de
 *  otra máquina: su terminal reenviada, o su conversación por el bus), «doc:<hilo>» (su carpeta y su documento) o «compartir» (lo
 *  que el teléfono le compartió a la app: la página se abrió en /compartir). */
function mostrar(que: string): void {
    if (!que) return;
    // el ⚙ de la cabecera: la configuración, en el dashboard
    if (que === 'config') { void hoy.irAPestana('config'); return; }
    if (esDocumento(que) && !esDocumento(actual)) origen = actual;
    actual = que;
    let f: HTMLElement | undefined;
    if (que === 'dashboard') {
        if (!hoy.panel) hoy.abrir();
        f = vistas().find(x => x.dataset.p === 'dashboard');
    } else {
        const como = forma(que), llave = como ? `${como}:${que}` : que;
        f = vistas().find(x => x.dataset.p === llave);
        if (que.startsWith('doc:') || que.startsWith('arch:') || que === 'compartir') {
            f ??= nuevaVista(llave);
            if (que === 'compartir') montarCompartir(f, location.search);
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
    // ya a la vista: la terminal toma el teclado, la lectura y la conversación se releen
    if (f && forma(que)) montadas.get(f.dataset.p ?? '')?.mostrada?.();
    // lo que se ve, como se nombra un hilo: «hilo» si es de esta máquina, «máquina:hilo» si es de otra (como
    // `scp máquina:ruta`; con la persona sería «nico@laptop:Telar»). Lo muestra la cabecera (indice.html)
    const remoto = que.startsWith('rem:') ? que.slice(4) : '';
    const nombre = remoto ? remoto
        : que.startsWith('doc:') ? `${que.slice(4)} · carpeta`
        : que.startsWith('arch:') ? relativa(que.slice(5)) : que;
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
ui.usarNavegacion({ mostrar, ordenes: crearOrdenes({ hoy, barra, mostrar }) });
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

// los hilos de otras máquinas (sus fotos): en HILOS, cada uno con su máquina; y el nombre de esta, para la
// columna ancha
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
setInterval(() => void otras(), 30 * 1000);

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
        + (local ? `<a data-carpeta="1" title="la carpeta del hilo y su documento">carpeta</a>` : '');
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
        };
    }
}
window.telar = { ...(window.telar ?? {}), mostrar };
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
