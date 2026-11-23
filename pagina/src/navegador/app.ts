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
import { C, I } from '../web/iconos';
import * as glifos from '../web/glifos';
import { BarraHilos, type Guardado } from '../vistas/hilos';
import { crearOrdenes } from '../web/ordenes';
import { Dashboard } from '../vistas/dashboard/panel';
import { montar as montarCarpeta, type Vuelta } from '../web/carpeta';
import { montar as montarCompartir } from '../web/compartir';
import { montar as montarObjeto, partir as partirDireccion } from '../web/objeto';
import * as ui from '../web/ui';
import * as version from '../web/version';
import * as jornadaCab from '../web/jornada';
import * as recarga from '../web/recarga';
import * as lado from '../web/lado';
import * as anchos from '../web/anchos';
import * as modos from '../web/modos';
import * as buscador from '../web/buscador';
import * as buscadores from '../web/buscadores';
import * as buscadorHilos from '../web/buscador-hilos';
import * as hallados from '../web/hallados';
import { type Vista, vista, VISTAS } from '../web/vistas-hilo';
import { barra as barraPantalla } from '../componentes/pantalla';
import { modosAdentro, mundoBoton, type ClaveModo } from '../componentes/modos-mundos';
import * as mundo from '../web/mundo';
import * as mundosVentana from '../web/mundos-ventana';
import * as franja from '../web/franja';
import * as pulso from '../web/pulso';
import * as vigia from '../web/vigia';
import * as avisosArchivos from '../web/avisos-archivos';
import * as dormidos from '../web/dormidos';


// ── la bandeja del equipo: la del servidor que sirve la página («aqui») o la de la máquina que diga /config ──

void cli.config().then(r => {
    if (r.datos?.equipo) { modelo.equipoRemoto = r.datos.equipo.trim(); void modelo.leerEquipo(); }
});

// ── a la izquierda la barra (vistas/hilos.ts); a la derecha, una vista a la vez: el dashboard o un hilo ──

const marcos = () => document.getElementById('vistas')!;
let actual = 'dashboard';
/** el último hilo que se miró: poner foco desde el dashboard vuelve a él */
let ultimoHilo = '';

/** Lo que se ve a la derecha: el dashboard, una vista de un hilo, su carpeta o «compartir», cada una dibujada en un
 *  elemento de la página con su clave en `data-p`. */
const vistas = () => ([...marcos().children] as HTMLElement[]).filter(x => x.dataset.p);

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
 *  a lo que se veía); un archivo o un proyecto, en el visor (el proyecto, su carpeta); una pestaña del dashboard
 *  (`pestana:<nombre>`), el dashboard en ella; un hilo de la lista (en esa máquina, si la dice), el hilo, como un clic
 *  en la barra. Si no es de esas, o es un hilo que la lista no tiene,
 *  false: la vista del objeto (web/objeto.ts), que dice si existe y deja escribirle. */
function abrirDireccion(direccion: string): boolean {
    const { tipo, id, maquina } = partirDireccion(direccion);
    const alla = maquina && maquina !== modelo.aqui ? maquina : '';
    if (!id) return false;
    if (tipo === 'tarea') { void hoy.abrirTarea(JSON.stringify(['tareas', id, id]), vueltaA(actual) ?? undefined); return true; }
    // una pestaña del dashboard (`pestana:calendario`, o la de un módulo por su nombre): el dashboard, en ella
    if (tipo === 'pestana') { mostrar('dashboard'); void hoy.irAPestanaNombrada(id); return true; }
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
    if (que !== 'dashboard' && que !== 'compartir' && !esDocumento(que)) ultimoHilo = que;
    ponerApps();
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
    // lo que se mira no se duerme, y abrir uno dormido lo despierta (web/dormidos.ts)
    mirador.decir(que, document.hidden);
    mirador.alMostrar(que, modelo.hilos, barra.otras);
    ubicarCampo();
}

/** El campo de glifos (web/glifos), en la pantalla que se ve si su modo se lo pone: la pestaña del dashboard, o la
 *  conversación o la lectura de un hilo (la terminal tiene su propio fondo, ⚙ terminal). */
function ubicarCampo(): void {
    const como = forma(actual);
    const pantalla = actual === 'dashboard' ? hoy.pestanaActiva() : como === 'conv' ? 'conversacion' : como === 'lectura' ? 'lectura' : '';
    const f = vistas().find(x => !x.hidden);
    glifos.ubicar(pantalla, f, marcos());
}

// ── arrancar ──────────────────────────────────────────────────────────────────

const hoy = new Dashboard();
hoy.donde = () => nuevaVista('dashboard');
hoy.mostrarme = () => mostrar('dashboard');
const barra = new BarraHilos();
/** lo que esta página le dice a telar que muestra, y despertar al que se abre dormido (web/dormidos.ts) */
const mirador = new dormidos.Mirador((pagina, hilo, maquina) => cli.mirando(pagina, hilo, maquina),
    (hilo, maquina) => cli.despertar(hilo, maquina));
setInterval(() => mirador.decir(actual, document.hidden), dormidos.CADA);
document.addEventListener('visibilitychange', () => mirador.decir(actual, document.hidden, true));
barra.estado = guardado;
barra.dashboardActivo = true;
barra.mostrado = '';
ui.usarNavegacion({ mostrar, ordenes: crearOrdenes({ hoy, barra, mostrar, soltar, releerOtras: () => otras() }) });
barra.montar(document.getElementById('barra')!);
// arriba de la barra, la franja de avisos: el estado del sistema y de los hilos (web/franja.ts; lo que mira, web/vigia.ts)
franja.montar(document.getElementById('barra')!);
// debajo, la última pasada de pulso que no has visto, si hay un pulso declarado (web/pulso.ts)
void pulso.montar(document.getElementById('barra')!);
vigia.vigilar();
// y lo que dicen los archivos de aviso declarados (`[avisos]`), en la misma franja (web/avisos-archivos.ts)
avisosArchivos.vigilar();
hoy.alCambiarFoco = () => {
    const app = hoy.appActual;
    if (barra.appActiva === app) return;
    barra.appActiva = app;
    barra.refrescar(true);
};
// las pestañas del dashboard son un grupo de la barra: sus filas, sus cuentas y la que se ve, al día con cada pintada
barra.pestanasDashboard = () => hoy.pestanas();
// (también la app: al salir de ella a una pestaña, su fila dejaba de ser la que se ve y seguía marcada)
hoy.alPintar = () => { barra.pestanaActiva = hoy.pestanaActiva(); barra.appActiva = hoy.appActual; barra.refrescar(); ponerApps(); pintarModos(); if (actual === 'dashboard') ubicarCampo(); };
// cambiar de modo puede prender, apagar o mover el campo
modos.alCambiar(() => ubicarCampo());
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
// el ancho de la barra y de la ficha, arrastrando su línea (web/anchos.ts)
anchos.montarEnPagina();
version.vigilar(() => { mostrar('dashboard'); void hoy.irAPestana('config', 'version'); });
// el día en una línea, en la cabecera (web/jornada.ts): un clic lleva al calendario del dashboard. Una pestaña sola
// (instalada como su app) no tiene cabecera
const lugarJornada = document.getElementById('jornada');
if (lugarJornada && !document.body.classList.contains('solo')) jornadaCab.montar(lugarJornada, () => { mostrar('dashboard'); void hoy.irAPestanaNombrada('calendario'); });
// el buscador (⌘K): sus fuentes. Cada una da lo suyo y cómo abrirlo; el buscador solo filtra y muestra
// (web/buscador.ts). Abrir algo estando en foco lo abre ahí mismo, sin barra ni cabecera
// los hilos y los agentes, de lo que la página ya tiene (web/buscador-hilos.ts)
for (const f of buscadorHilos.fuentes({ otras: () => barra.otras, mostrar, orden: (o, arg) => ui.orden(o, arg) })) buscador.registrar(f);
buscador.registrar({
    clave: 'dashboard', nombre: 'dashboard', orden: 3, color: 'cian',
    resultados: () => [
        ...hoy.pestanas().map((p, i) => ({
            titulo: p.nombre, icono: I.ventana, detalle: p.tecla ? `pestaña · ${p.tecla}` : 'pestaña', claves: p.clave, peso: 40 - i,
            abrir: () => { mostrar('dashboard'); return hoy.irAPestana(p.accion, p.valor); },
        })),
        ...hoy.seccionesConfig().map(c => ({
            titulo: `configuración · ${c.nombre}`, icono: I.config, detalle: c.ayuda, claves: `configuracion ${c.clave}`, peso: 5,
            abrir: () => { mostrar('dashboard'); return hoy.irAPestana('config', c.clave); },
        })),
    ],
});
buscador.registrar({
    clave: 'modos', nombre: 'modos', orden: 4, color: 'amarillo',
    resultados: () => modos.permitidos().map(m => ({
        titulo: `modo ${m.nombre}`, icono: I.modo, detalle: m.clave === modos.puesto().clave ? 'puesto' : '', claves: m.clave,
        peso: m.clave === modos.puesto().clave ? 0 : 10, abrir: () => modos.cambiar(m.clave),
    })),
});
buscador.registrar({
    clave: 'ordenes', nombre: 'órdenes', orden: 5, color: 'verde',
    resultados: () => [
        { titulo: 'hilo nuevo', icono: I.nuevo, detalle: 'un tab con su agente', claves: 'nuevo crear abrir', abrir: () => ui.orden('telar.nuevo') },
        { titulo: 'agente nuevo', icono: I.nuevo, detalle: 'un agente residente: su carpeta', claves: 'nuevo crear', abrir: () => ui.orden('telar.agenteNuevo') },
        { titulo: 'máquinas', icono: I.maquinas, detalle: 'tus máquinas y los servidores', claves: 'servidores maquinas', abrir: () => { location.href = '/maquinas'; } },
        { titulo: 'actualizar la lista', icono: I.releer, detalle: 'volver a leer los hilos', claves: 'refrescar', abrir: () => ui.orden('telar.actualizar') },
        // con mundos declarados: la ventana de mundos (también ⌘M y un clic en el mundo de la banda)
        ...mundo.declarados().length ? [{ titulo: 'cambiar de mundo', icono: I.planeta, detalle: `ahora ${mundo.mundo()?.nombre ?? 'ambos'} · ⌘M`,
            claves: `mundo mundos ${mundo.declarados().map(m => m.nombre).join(' ')} ambos`, abrir: () => mundosVentana.abrir(opcionesMundos) }] : [],
    ],
});
// los proyectos, las tareas y los documentos del grafo: los pide a telar mientras se escribe, en un solo pedido (la misma
// búsqueda de Todo, con el mundo puesto primero), y abrirlos es lo mismo que en Todo (web/hallados.ts)
for (const f of hallados.fuentesDeTelar()) buscador.registrar(f);
// la última fila, con lo escrito: buscarlo en todo junto (el modo todo, vistas/dashboard/todo.ts), más allá de lo que
// está a mano aquí
buscador.alFinal('en todo', 'cian', q => ({ titulo: `buscar «${q}» en todo`, icono: I.lista,
    detalle: 'lo que espera, tareas, casillas, hilos, proyectos, correo…', abrir: () => hoy.buscarEnTodo(q) }));
buscador.montar();
// el ✕ de cualquier buscador de la página (componentes/buscador.ts): lo borra y avisa a su vista
buscadores.atender();

// los íconos de la cabecera (la página es estática: la letra de íconos se recorta con lo que nombra web/iconos.ts)
for (const [id, icono] of [['ir-maquinas', I.maquinas], ['ir-config', I.config]]) {
    const a = document.getElementById(id);
    if (a) a.textContent = icono;
}

// los modos y el mundo (docs/propuestas/orden-por-modos.md, paso 2), a la vista en la banda, el segundo nivel de la
// cabecera (indice.html, modos.css): a la izquierda las cuatro actitudes (táctica, estrategia, foco, todo; la puesta en
// violeta, y táctica con el único número de la página cuando no es la que se ve), y a la derecha el mundo, su nombre en
// su color y hasta cuándo (la línea de abajo de la cabecera, que es la de la banda, es la de siempre). Un clic en un modo lo
// pone y lleva a su vista; en el mundo, la ventana de mundos. Clic derecho en los modos: los propios y editarlos. Teclas:
// ⌥⇧1–4, ⌥⇧F foco y vuelta, ⌥⇧M el siguiente, ⌥⇧0 el mundo (web/modos.ts); ⌘M, la ventana de mundos
mundo.montar();
modos.montar();
const filaModos = document.getElementById('modos-fila');
const lugarMundo = document.getElementById('mundo-sel');
/** (busca su lugar cada vez: lo llama también el dashboard al pintarse, que puede ser antes de llegar aquí) */
function pintarModos(): void {
    const fila = document.getElementById('modos-fila');
    if (!fila) return;
    const m = modos.puesto();
    // solo los que tiene el mundo puesto: sus actitudes y aquellas sobre las que se arma uno propio suyo
    const solo = modos.delMundo() && [...new Set(modos.permitidos().map(x => modos.base(x)))];
    const html = modosAdentro(modos.base() as ClaveModo, { propio: m.de_fabrica ? '' : m.nombre, solo });
    if (fila.innerHTML !== html) fila.innerHTML = html;
}
function pintarMundo(): void {
    if (!lugarMundo) return;
    lugarMundo.hidden = !mundo.declarados().length;
    lugarMundo.innerHTML = lugarMundo.hidden ? '' : mundoBoton(mundo.puesto(), mundo.declarados(), new Date(), 'banda-mundo-boton');
}
pintarModos();
pintarMundo();
modos.alCambiar(pintarModos);
mundo.alCambiar(() => { pintarMundo(); pintarModos(); barra.refrescar(true); hoy.repintar(); });
// poner un modo lleva a su vista: la pestaña de su primera fila en DASHBOARD (táctica; proyectos, en estrategia; todo); foco, al último
// hilo que se miró si se estaba en el dashboard. El que pone un mundo al entrar a él no saca de un hilo
modos.alPoner((_, o) => {
    const b = modos.base();
    if (o.porMundo && actual !== 'dashboard' && b !== 'foco') return;
    if (b === 'foco') { if (actual === 'dashboard' && ultimoHilo) mostrar(ultimoHilo); return; }
    mostrar('dashboard');
    void hoy.irAModo();
});
filaModos?.addEventListener('click', e => {
    const a = (e.target as HTMLElement).closest<HTMLElement>('[data-accion="modos-modo"]');
    if (!a?.dataset.id) return;
    e.preventDefault();
    // un modo propio puesto sobre esa actitud: volver a su vista, sin cambiarlo; una que el mundo no tiene pero sí uno
    // propio sobre ella: ese
    const m = modos.puesto();
    const id = a.dataset.id;
    const propio = modos.permitido(id) ? undefined : modos.permitidos().find(x => !x.de_fabrica && modos.base(x) === id);
    modos.cambiar(!m.de_fabrica && modos.base(m) === id ? m.clave : propio?.clave ?? id);
});
filaModos?.addEventListener('contextmenu', async e => {
    e.preventDefault();
    const puesto = modos.puesto().clave;
    const filas = [
        ...modos.permitidos().map(m => ({ label: m.nombre, icono: m.clave === puesto ? I.hecha : ' ', color: C.ir, id: m.clave,
            description: m.de_fabrica ? '' : `sobre ${modos.lista().find(x => x.clave === modos.base(m))?.nombre ?? 'táctica'}`
                + (String(m.valores.etiquetas ?? '') ? ` · hilos de ${String(m.valores.etiquetas).split(',').join(', ')}` : '') })),
        { label: '', separador: true, id: '' },
        { label: 'editar los modos…', icono: I.config, color: C.cambiar, description: 'qué dice cada uno, uno nuevo', id: '__editar' },
    ];
    const elegido = await ui.menu(filas, { x: e.clientX, y: e.clientY + 4 }, 'modo de la página');
    if (!elegido) return;
    if (elegido.id === '__editar') { mostrar('dashboard'); void hoy.irAPestana('config', 'modos'); }
    else modos.cambiar(elegido.id);
});
// cambiar de mundo: la ventana de mundos (web/mundos-ventana.ts), una tarjeta por mundo con su arte. La abren un clic en el
// mundo de la banda, ⌘M y «cambiar de mundo» en ⌘K; «editar» lleva a ⚙ mundos
const opcionesMundos: mundosVentana.OpcionesMundos = { editar: () => { mostrar('dashboard'); void hoy.irAPestana('config', 'mundos'); } };
lugarMundo?.addEventListener('click', e => {
    e.preventDefault();
    void mundosVentana.abrir(opcionesMundos);
});
mundosVentana.montar(opcionesMundos);

// las apps (`[apps]`: juegos, visores), en un menú de la cabecera y no en la barra, que es la del trabajo: su ícono, si
// hay alguna, y un clic las lista debajo. La que se mira, marcada (y el ícono, en el acento)
function ponerApps(): void {
    const sel = document.getElementById('apps-sel');
    if (!sel) return;
    sel.textContent = I.apps;
    sel.hidden = !modelo.apps.length;
    sel.classList.toggle('si', actual === 'dashboard' && !!hoy.appActual);
}
ponerApps();
modelo.cambio.event(ponerApps);
document.getElementById('apps-sel')?.addEventListener('click', async e => {
    e.preventDefault();
    const abierta = actual === 'dashboard' ? hoy.appActual : '';
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const elegida = await ui.menu(modelo.apps.map(a => ({ label: a.nombre, id: a.clave, description: a.descripcion ?? '',
        icono: a.clave === abierta ? I.hecha : ' ', color: C.ir })), { x: r.left, y: r.bottom + 4 }, 'apps');
    if (elegida) await ui.orden('telar.app', elegida.id);
});

void fetch('/api/salud', { cache: 'no-store' }).then(r => r.json()).then((s: { maquina?: string }) => {
    barra.aqui = modelo.aqui = s.maquina ?? ''; barra.refrescar(true);
}).catch(() => undefined);
const otras = async () => {
    const r = await cli.espejos().catch(() => undefined);
    // sin respuesta (telar se reinicia), las otras máquinas quedan como estaban: no se borran de la barra
    if (!r?.datos) return;
    // fuera de línea (telar.alcance): su foto envejeció con el nodo de aquí al día; con lo que le espera en cola
    const nuevas = (r?.datos?.espejos ?? []).filter(e => !e.error)
        .map(e => ({ nombre: e.nombre, en_linea: e.en_linea, edad: e.edad, fuera: !e.en_linea && !!r.datos?.al_dia,
            cola: e.cola ?? [], hechos: e.hechos ?? [], hilos: e.hilos.filter(h => !h.remoto) }));
    vigia.espejos(nuevas);
    // la edad cambia en cada lectura: lo que se compara para redibujar es lo demás (fuera o no, y desde cuándo lo dice su
    // ayuda, que se rehace al redibujar por otra cosa)
    const firma = (l: typeof barra.otras) => JSON.stringify(l.map(m => ({ ...m, edad: m.en_linea ? 0 : Math.round((m.edad ?? 0) / 600) })));
    if (firma(nuevas) !== firma(barra.otras)) { barra.otras = nuevas; barra.refrescar(true); }
    else barra.otras = nuevas;
};
void otras();
// el servidor avisa cuando cambia algo de telar (`/eventos`): la lista y las fotos de las otras máquinas se releen al
// tiro. Los sondeos de abajo quedan de respaldo, más espaciados mientras los avisos llegan (lo que no pasa por el
// estado de telar, como una ventana de tmux que se cae sola, lo trae el sondeo)
let avisos = false;
(() => {
    if (typeof EventSource === 'undefined') return;
    const es = new EventSource('/eventos');
    let pendiente = 0;
    // al volver la API (telar se reinició), la lista se relee al tiro, sin esperar el sondeo
    // (y si volvió de un despliegue, con otra página: web/recarga.ts)
    es.onopen = () => { avisos = true; if (modelo.error) void modelo.sondear().catch(() => undefined); void recarga.revisar(); };
    es.onerror = () => { avisos = false; };
    es.onmessage = e => {
        if (e.data === 'espejos') { void otras(); return; }
        // juntar los que llegan seguidos (una orden escribe varios archivos): una sola lectura
        if (e.data === 'hilos' && !pendiente) {
            pendiente = window.setTimeout(() => { pendiente = 0; if (!document.hidden) void modelo.sondear().catch(() => undefined); }, 120);
        }
    };
})();
// cada 6 s (30 con avisos): es leer un archivo de aquí (el nodo guarda la foto apenas llega por el bus)
const otrasCada = () => { void otras().finally(() => setTimeout(otrasCada, avisos ? 30000 : 6000)); };
setTimeout(otrasCada, 6000);

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
    // la barra de una pantalla (componentes/pantalla.ts), la misma de las apps del dashboard: sin nombre (lo dice la
    // cabecera de la página), sus vistas y, a la derecha, su carpeta como ruta (un ícono no alcanza: es una palabra)
    const h = local ? modelo.porNombre(que) : undefined;
    const ruta = h?.relativa && h.relativa !== '.' ? h.relativa : h?.ruta ? relativa(h.ruta) : '';
    barraH.innerHTML = barraPantalla({
        vistas: VISTAS.map(v => ({ accion: 'vista', valor: v.clave, icono: v.icono, nombre: `${v.nombre} (${v.atajo})`, ayuda: v.ayuda, si: v.clave === como })),
        // su carpeta, como ruta (relativa a la raíz si está adentro); sin vínculo, la raíz
        acciones: local ? [{ accion: 'carpeta', icono: I.carpeta, texto: ruta || '~', tono: 'azul',
            ayuda: `${ruta || 'la raíz'}\nclic: la carpeta del hilo y su documento` }] : [],
    });
}

/** Cambiar la vista del hilo que se ve (la barra de acciones, o ⌥ y su letra desde adentro de una vista). */
function cambiarVista(clave: string): void {
    if (!forma(actual) || !vista(clave) || forma(actual) === clave) return;
    modo[actual] = clave;
    mostrar(actual);
}

document.getElementById('acciones')!.addEventListener('click', e => {
    const a = (e.target as HTMLElement).closest<HTMLElement>('[data-accion]');
    if (!a) return;
    if (a.dataset.accion === 'vista' && a.dataset.valor) cambiarVista(a.dataset.valor);
    else if (a.dataset.accion === 'carpeta') {
        // en el celular la ruta está escondida: el clic en el ícono la muestra y, con ella a la vista, un clic en ella abre la carpeta
        const celular = document.body.classList.contains('angosto');
        const sobreRuta = !!(e.target as HTMLElement).closest('.txt');
        if (celular && !sobreRuta) a.classList.toggle('abierta');
        else mostrar(`doc:${actual}`);
    }
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
            /** poner un mundo a mano ("" ambos; web/mundo.ts), como la ventana de mundos: para recorrer la página en cada uno */
            ponerMundo?: (clave: string) => void;
            /** abrir la ventana de mundos (o cerrarla, si está abierta), como ⌘M; devuelve lo elegido (web/mundos-ventana.ts) */
            mundos?: () => Promise<string | undefined>;
            /** cambiar la vista del hilo que se ve (`term`, `lectura`, `conv`): lo que hace su barra de arriba */
            vista?: (clave: string) => void;
            donde?: (lo: { texto: string; otraMaquina: boolean } | null) => void;
            /** la transición de una mudanza, sin mudar nada: para mirarla y afinarla (web/mudanza.ts, `ensayo`) */
            ensayoMudanza?: (maquina?: string, falla?: boolean | 'pregunta') => Promise<void>;
            /** una confirmación de verdad (`ui.aviso` con botones) con textos de muestra: `borrar`, `archivar`, `descartar`,
             *  `traer` (con contenido largo, que se desplaza) y `permiso` (tres botones); dice qué se apretó y no lo hace
             *  (web/ensayo-confirmar.ts) */
            ensayoConfirmar?: (cual?: string) => Promise<string>;
            /** la ventana de contestar con una espera de mentira (`tarea`, `retenido`, `en-vivo`, `decide`, `permiso`, y las
             *  de la ficha: `decision`, `aprobar`, `sin-contexto`), sin contestar nada; con `cambio`, el primer envío
             *  responde que cambió mientras se miraba (web/contestar.ts) */
            ensayoContestar?: (clase?: string, cambio?: boolean) => Promise<string | undefined>;
            /** «táctica» con un día de mentira, en uno de sus estados (`reunion`, `hoy`, `libre`, `bloque`, `nada`,
             *  `muchas`, `sinplan`: componentes/muestras-tactica.ts), sin leer ni contestar nada; la línea del día de la cabecera
             *  dice el de mentira hasta el minuto siguiente */
            ensayoTactica?: (estado?: string) => Promise<void>;
            /** la franja de avisos con los de una escena de mentira (`ninguno`, `sin-conexion`, `fuente`, `varios`:
             *  componentes/muestras-avisos.ts), sin que nada falle; con `abrir`, la lista abierta (web/franja.ts) */
            ensayoAvisos?: (escena?: string, abrir?: boolean) => string;
            /** la línea del pulso con pasadas de mentira (componentes/muestras-pulso.ts) y, con `abrir` (de fábrica), su
             *  ventana, sin leer ni marcar nada (web/pulso.ts) */
            ensayoPulso?: (abrir?: boolean) => Promise<string>;
        };
    }
}
window.telar = { ...(window.telar ?? {}), mostrar, ponerMundo: mundo.poner, mundos: () => mundosVentana.abrir(opcionesMundos), vista: cambiarVista, ensayoAvisos: franja.ensayo, ensayoPulso: pulso.ensayo,
    ensayoMudanza: async (maquina, falla) => { const { ensayo } = await import('../web/mudanza'); await ensayo(maquina, falla); },
    ensayoConfirmar: async cual => { const { ensayo } = await import('../web/ensayo-confirmar'); return ensayo(cual); },
    ensayoContestar: async (clase = 'decide', cambio = false) => {
        const [{ abrirContestar, hacerDeEnsayo }, { esperasDeMuestra }] = await Promise.all([import('../web/contestar'), import('../componentes/muestras-contestar')]);
        const e = esperasDeMuestra()[clase];
        return e ? await abrirContestar(e, hacerDeEnsayo({ cambio })) : undefined;
    },
    ensayoTactica: async (estado = 'reunion') => {
        const [{ ESTADOS }, { jornada }] = await Promise.all([import('../componentes/muestras-tactica'), import('../componentes/jornada')]);
        const e = ESTADOS.find(x => x.clave === estado) ?? ESTADOS[0];
        mostrar('dashboard');
        await hoy.ensayoTactica(e.datos);
        // la cabecera, con el mismo día: la reescribe sola al cambiar el minuto (web/jornada.ts)
        const lugar = document.getElementById('jornada');
        const medianoche = new Date(e.datos.ahora).setHours(0, 0, 0, 0);
        const tramos = jornadaCab.tramosDe(e.datos.dia, medianoche);
        if (lugar) { lugar.innerHTML = jornada({ ...jornadaCab.abarca(tramos), ahora: Math.round((e.datos.ahora - medianoche) / 60000), tramos }); lugar.hidden = false; }
    } };
// abierta por «compartir» del teléfono (share_target del manifiesto): eso primero, también en el celular
const compartiendo = location.pathname === '/compartir';
// lo que se mira, para retomarlo si la página se recarga (un despliegue, F5: web/recarga.ts): en el celular, también si
// se estaba en la lista
recarga.lugar(() => ({ que: actual, como: forma(actual), pestana: actual === 'dashboard' ? hoy.pestanaActiva() : '',
    lista: angosto() && document.body.classList.contains('en-lista') }));
// recargada: lo que se miraba, como estaba (gana sobre `?abrir=`, que es de cuando se abrió). La pestaña sola no tiene otra cosa
const retomar = /^\/pestana\//.test(location.pathname) ? undefined : recarga.lugarAlRecargar();
mostrar((retomar ? retomar.que === 'compartir' : compartiendo) ? 'compartir' : 'dashboard');
// `?abrir=<dirección>` (`hilo:Secretaría`, `tarea:T84`, `pestana:calendario`): la página abre eso al cargar, en vez del dashboard o la lista. Un
// hilo, en el celular, en su conversación (la que tiene la caja para escribir), con «◀ hilos» de vuelta a la lista.
// Espera a la primera lectura de los hilos: hasta entonces no se sabe dónde vive
// `/pestana/<nombre>/`: una pestaña sola, instalada como su propia app (api_web; indice.html le saca la cabecera y la
// lista): esa pestaña al cargar
const soloPestana = /^\/pestana\/([^/]+)\/?$/.exec(location.pathname)?.[1];
const abrirAlCargar = compartiendo ? '' : soloPestana ? `pestana:${decodeURIComponent(soloPestana)}`
    : (new URLSearchParams(location.search).get('abrir') ?? '').trim();
// en el celular se empieza por la lista (o en ella, si ahí se estaba al recargar)
if (document.body.classList.contains('angosto') && (retomar ? retomar.lista : !compartiendo && !abrirAlCargar)) {
    document.body.classList.remove('en-detalle'); document.body.classList.add('en-lista');
}
// el dashboard, en la pestaña que se miraba
if (retomar?.que === 'dashboard' && !retomar.lista && retomar.pestana && retomar.pestana !== 'ahora') {
    void (retomar.pestana === 'config' ? hoy.irAPestana('config') : hoy.irAPestanaNombrada(retomar.pestana, true));
}

setInterval(() => { if (hoy.panel && !document.hidden && actual === 'dashboard') void hoy.actualizar(); }, 60 * 1000);
// al volver a la pestaña, el dashboard se pone al día (lo que pasó mientras no se miraba)
document.addEventListener('visibilitychange', () => { if (hoy.panel?.visible) void hoy.actualizar(); });
// el modelo (los hilos, su atención) se sondea mientras la página se mira
const sondear = async () => {
    if (!document.hidden) await modelo.sondear().catch(() => undefined);
    // sin API, cada 2 s: un reinicio de telar dura unos segundos y la lista vuelve apenas contesta
    setTimeout(sondear, modelo.error ? 2000 : !modelo.viva ? 5000 : avisos ? 10000 : 3000);
};
// la pestaña sola no espera a los hilos: se abre ya, sin pasar por «ahora»
if (soloPestana) void hoy.irAPestanaNombrada(decodeURIComponent(soloPestana));
void modelo.sondear(true).catch(() => undefined).then(() => {
    // recargada viendo un hilo (o un archivo, un objeto): ese, en la vista que tenía
    if (retomar) {
        const q = retomar.que;
        if (retomar.lista || q === 'dashboard' || q === 'compartir') return;
        // un hilo de aquí que ya no está (se cerró del todo mientras tanto): el dashboard, como al abrirla
        if (esHilo(q) && !q.startsWith('rem:') && !modelo.error && !modelo.hilos.some(h => h.nombre === q)) return;
        if (retomar.como && esHilo(q)) modo[q] = retomar.como;
        mostrar(q);
        return;
    }
    if (!abrirAlCargar || soloPestana) return;
    // un hilo dormido o archivado se muestra sin retomarlo (su conversación, con «retomar»): cargar la página no
    // levanta su agente
    const { tipo, id, maquina } = partirDireccion(abrirAlCargar);
    const dormido = tipo === 'hilo' && modelo.hilos.find(x => x.nombre === id && (!maquina || maquina === modelo.aqui || x.remoto === maquina));
    if (dormido && (!dormido.vivo || dormido.archivado)) { mostrar(id); return; }
    // un hilo que la lista no tiene (o algo que no es de los de siempre): la vista del objeto, que dice si existe
    if (!abrirDireccion(abrirAlCargar)) mostrar(`obj:${abrirAlCargar}`);
}).then(sondear);
