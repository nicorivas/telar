// La vista «hilos»: lo que hay abierto, con semáforo, prioridad y tiempo del día.
//
// Es la lista de proyectos de la barra, pero se llama como la llama telar: un hilo es una
// unidad de trabajo viva, y qué cuenta como proyecto lo declara el perfil del repositorio,
// no esta extensión.
//
//   ● faro            ●   49m   ← prioridad (· si no tiene) · nombre · atención · hoy
//   ◐ molino               7m
//   ▸ ARCHIVO 6 hilos         2d  ← plegado; a la derecha, hace cuánto se usó
//
// El id del multiplexor no se muestra: para elegir un hilo basta la prioridad y el nombre.
// Los botones de la fila (⏸ ✕ ▶) flotan sobre el borde derecho al pasar el mouse y no
// ocupan lugar, porque si lo ocuparan correrían la columna del tiempo según cuántos hay.
//
// El HTML entra por mensajes y no recargando la webview: así no se pierde el scroll ni
// parpadea la lista cada vez que cambia un segundo del tiempo de hoy.

import { ui } from '../anfitrion';

import * as cli from '../cli';
import { GLIFO, NOMBRE_ATENCION, PRIORIDAD, duracion, esc, hace, haceCorto, estilo } from '../estilo';
import { marco } from '../estilo';
import { modelo } from '../modelo';

const CSS = estilo('hilos');

const SCRIPT = `
const lista = document.getElementById('lista');
// lo escrito en cada buscador sobrevive a los redibujos (llegan varios por minuto) y a recargar
const est = vscode.getState() || {};
est.q = est.q || {};
const norm = t => (t || '').normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();
function filtrar() {
  document.querySelectorAll('input.buscar').forEach(inp => {
    const g = inp.dataset.grupo, q = norm(inp.value.trim());
    let n = 0;
    document.querySelectorAll('.fila[data-grupo="' + g + '"]').forEach(f => {
      const ok = !q || norm(f.dataset.busca).includes(q);
      f.hidden = !ok; if (ok) n++;
    });
    const v = document.querySelector('.vacia[data-grupo="' + g + '"]');
    if (v) v.hidden = !(q && !n);
  });
}
window.addEventListener('message', e => {
  const m = e.data;
  if (m.tipo !== 'lista') return;
  const a = document.activeElement, foco = a && a.classList && a.classList.contains('buscar')
    ? { g: a.dataset.grupo, i: a.selectionStart, j: a.selectionEnd } : null;
  lista.innerHTML = m.html;
  document.querySelectorAll('input.buscar').forEach(inp => { inp.value = est.q[inp.dataset.grupo] || ''; });
  if (foco) {
    const inp = document.querySelector('input.buscar[data-grupo="' + foco.g + '"]');
    if (inp) { inp.focus(); inp.setSelectionRange(foco.i, foco.j); }
  }
  filtrar();
  if (m.mostrar) { const el = document.querySelector(m.mostrar); if (el && !el.hidden) el.scrollIntoView({ block: 'nearest' }); }
});
document.addEventListener('input', e => {
  if (!e.target.classList.contains('buscar')) return;
  est.q[e.target.dataset.grupo] = e.target.value; vscode.setState(est); filtrar();
});
document.addEventListener('keydown', e => {
  if (!e.target.classList || !e.target.classList.contains('buscar')) return;
  if (e.key === 'Escape') { e.target.value = ''; est.q[e.target.dataset.grupo] = ''; vscode.setState(est); filtrar(); }
  // ⏎: al primero que se ve
  if (e.key === 'Enter') {
    const f = document.querySelector('.fila[data-grupo="' + e.target.dataset.grupo + '"]:not([hidden])');
    if (f) vscode.postMessage({ tipo: 'ir', hilo: f.dataset.hilo });
  }
});
document.addEventListener('click', e => {
  const f = e.target.closest('[data-hilo],[data-accion]');
  if (!f) return;
  if (f.dataset.accion) vscode.postMessage({ tipo: f.dataset.accion, id: f.dataset.id });
  else vscode.postMessage({ tipo: 'ir', hilo: f.dataset.hilo });
});
// en el navegador no hay menú contextual nativo: el clic derecho abre el del hilo (⋯)
document.addEventListener('contextmenu', e => {
  if (!window.__telarWeb) return;
  const f = e.target.closest('[data-hilo]');
  if (!f) return;
  e.preventDefault();
  vscode.postMessage({ tipo: 'menu', id: f.dataset.hilo });
});
vscode.postMessage({ tipo: 'listo' });
`;

/** Un hilo de otra máquina, como viene en su foto (`telar.espejo`). */
export interface HiloDeFoto { nombre: string; atencion?: string; vivo?: boolean; relativa?: string; prioridad?: number | null; resumen?: string }

type Seccion = 'hilo' | 'archivado';
/** Cómo se ordena un grupo: "" como lo da telar (el orden de ⌘⇧P «ordenar»), o uno de estos. */
type Orden = '' | 'urgencia' | 'nombre' | 'reciente';
const ORDENES: [Orden, string, string][] = [
    ['urgencia', '●', 'urgencia: prioridad alta primero; a igual prioridad, el que te espera y después el más reciente'],
    ['nombre', 'a-z', 'nombre, alfabético'],
    ['reciente', '◷', 'última modificación: el último prompt a su agente, lo más reciente arriba'],
];

/** La última modificación de un hilo: cuándo se le pidió algo a su agente. Si telar todavía no lo
 *  anotó (un hilo de antes), lo último que hizo su agente. Mirarlo (`visto`) nunca cuenta: un clic
 *  no es trabajo. */
const ultimaDe = (h: cli.JsonHilo): string => h.actividad || h.atencion_desde || '';

function ordenar(l: cli.JsonHilo[], orden: Orden): cli.JsonHilo[] {
    if (!orden) return l;
    const reciente = (a: cli.JsonHilo, b: cli.JsonHilo) => ultimaDe(b).localeCompare(ultimaDe(a));
    const cmp: Record<Exclude<Orden, ''>, (a: cli.JsonHilo, b: cli.JsonHilo) => number> = {
        urgencia: (a, b) => ((a.prioridad || 9) - (b.prioridad || 9))
            || (Number(b.atencion === 'espera') - Number(a.atencion === 'espera')) || reciente(a, b),
        nombre: (a, b) => cli.nombreVisible(a).localeCompare(cli.nombreVisible(b), 'es', { sensitivity: 'base' }),
        reciente,
    };
    return [...l].sort(cmp[orden]);
}

/** Donde se dibuja la barra: la vista lateral de VS Code (hilos-vscode.ts) o la columna izquierda
 *  de la página web (src/navegador). Lo mismo que la superficie del dashboard, más su cabecera. */
export interface SuperficieBarra {
    readonly cspSource: string;
    readonly cspConectar?: string;
    readonly visible: boolean;
    html(pagina: string): void;
    enviar(mensaje: unknown): void;
    /** el título, la línea de abajo y la cuenta de los que esperan (en VS Code, la insignia) */
    cabecera(c: { titulo: string; descripcion: string; insignia?: { valor: number; ayuda: string } }): void;
}

/** Donde se guarda lo que se recuerda entre sesiones (en VS Code, su globalState). */
export interface Guardado {
    get<T>(clave: string): T | undefined;
    update(clave: string, valor: unknown): PromiseLike<void>;
}

/** La barra de hilos, sin VS Code: arma la lista y responde a sus clics. */
export class BarraHilos {
    vista?: SuperficieBarra;
    private listo = false;
    private ultimoHtml = '';
    private ultimoActivo?: string;
    /** el dashboard tiene el foco: su fila va marcada, y no la del último hilo (que no es lo que se mira) */
    dashboardActivo = false;
    /** la app que el dashboard muestra (si está al frente): su fila se marca, no la del dashboard */
    appActiva = '';
    /** en la web: el hilo cuya terminal se muestra a la derecha. Si se da, manda sobre el foco de
     *  tmux para marcar la fila (en VS Code no se da: manda el hilo con foco) */
    mostrado?: string;
    /** los hilos de otras máquinas que esta no ve en su multiplexor, de la foto que publica cada una
     *  (`telar espejo ver`): van en HILOS, con su máquina en la columna de dónde vive. Lo pone la página web */
    otras: { nombre: string; en_linea: boolean; edad: number | null; hilos: HiloDeFoto[] }[] = [];
    /** el nombre de esta máquina (la que sirve la página): con la columna ancha, lo muestran sus hilos */
    aqui = '';
    /** la columna de dónde vive cada hilo: ⇄ (o nada, si vive aquí), o el nombre de la máquina */
    private conMaquina(): boolean { return !!this.estado?.get<boolean>('telar.hilos.maquina'); }
    /** el ancho de esa columna con los nombres: el del nombre más largo, hasta 12 */
    private anchoMaquina = 1;
    private irAlArchivo = false;
    /** dónde guardar el orden elegido de cada grupo (el globalState de la extensión) */
    estado?: Guardado;
    private ordenDe(grupo: string): Orden { return (this.estado?.get<string>(`telar.orden.${grupo}`) ?? '') as Orden; }
    /** las cabeceras que el usuario dejó al revés de como empiezan (abierta una cerrada, o al revés) */
    private invertidas = new Set<string>();

    /** El archivo es una cabecera más (`__archivo`); `archivoAbierto` lo deja ver y cambiar desde afuera. */
    get archivoAbierto(): boolean { return this.abierta('__archivo', false); }
    set archivoAbierto(v: boolean) { if (v !== this.archivoAbierto) this.alternar('__archivo'); }

    private abierta(clave: string, porDefecto: boolean): boolean { return porDefecto !== this.invertidas.has(clave); }
    private alternar(clave: string): void { if (this.invertidas.has(clave)) this.invertidas.delete(clave); else this.invertidas.add(clave); }

    /** La barra ya tiene dónde dibujarse. Abrirla es ir a trabajar en la sesión: la terminal que
     *  la muestra pasa al frente (en VS Code; en la web, la terminal es otra ventana). */
    conectar(vista: SuperficieBarra): void {
        this.vista = vista;
        this.pintarMarco();
    }

    /** La superficie se cerró. */
    desconectar(): void { this.vista = undefined; this.listo = false; }

    /** El HTML fijo (estilo y script); la lista entra después por mensajes. */
    pintarMarco(): void {
        if (!this.vista) return;
        this.listo = false; this.ultimoHtml = '';
        this.vista.html(marco(this.vista, CSS, '<div id="lista"></div>', SCRIPT));
    }

    mensaje(m: { tipo: string; hilo?: string; id?: string }): void {
        switch (m.tipo) {
            case 'listo': this.listo = true; this.refrescar(true); break;
            case 'ir': {
                if (!m.hilo) break;
                // un archivado no tiene tab al que ir: pincharlo es retomarlo
                const sinTab = modelo.hilos.some(x => x.nombre === m.hilo && (!x.vivo || x.archivado));
                void ui().orden(sinTab ? 'telar.retomar' : 'telar.ir', { hilo: m.hilo });
                break;
            }
            case 'archivar': if (m.id) void ui().orden('telar.archivar', { hilo: m.id }); break;
            case 'retomar': if (m.id) void ui().orden('telar.retomar', { hilo: m.id }); break;
            case 'cerrar': if (m.id) void ui().orden('telar.cerrar', { hilo: m.id }); break;
            case 'archivo': void ui().orden('telar.archivo'); break;
            case 'menu': if (m.id) void ui().orden('telar.menuHilo', { hilo: m.id }); break;
            case 'ir-remoto': if (m.id) void ui().orden('telar.irRemoto', m.id); break;
            case 'seccion':
                if (m.id === '__archivo') { void ui().orden('telar.archivo'); break; }
                if (m.id) { this.alternar(m.id); this.refrescar(true); }
                break;
            case 'equipo': void ui().orden('telar.equipoVer', m.id); break;
            case 'home': if (m.id) void ui().orden('telar.seccion', m.id); break;
            case 'app': if (m.id) void ui().orden('telar.app', m.id); break;
            case 'ver-maquina':
                void this.estado?.update('telar.hilos.maquina', !this.conMaquina()).then(() => this.refrescar(true));
                break;
            case 'orden-grupo': if (m.id) {
                const [grupo, orden] = m.id.split(':');
                void this.estado?.update(`telar.orden.${grupo}`, orden === this.ordenDe(grupo) ? '' : orden).then(() => this.refrescar(true));
            } break;
            case 'cmd': if (m.id?.startsWith('telar.')) void ui().orden(m.id); break;
        }
    }

    alternarArchivo(): void {
        this.archivoAbierto = !this.archivoAbierto;
        this.irAlArchivo = this.archivoAbierto;
        this.refrescar(true);
    }

    refrescar(forzar = false): void {
        const v = this.vista;
        if (!v) return;
        const orden = ({ alfa: 'a-z', reciente: '◷', prioridad: '●' } as Record<string, string>)[modelo.orden] ?? '';
        v.cabecera({
            titulo: orden ? `hilos · ${orden}` : 'hilos',
            descripcion: modelo.error ? 'sin telar' : !modelo.viva ? 'sesión no tejida' : modelo.sesion,
            insignia: modelo.esperan ? { valor: modelo.esperan, ayuda: `${modelo.esperan} te espera${modelo.esperan === 1 ? '' : 'n'}` } : undefined,
        });
        if (!this.listo) return;
        const html = this.html();
        const activo = this.dashboardActivo ? '\u0000dashboard' : this.mostrado ?? modelo.activo?.nombre;
        const seMovio = activo !== this.ultimoActivo;
        if (!forzar && !seMovio && html === this.ultimoHtml) return;
        this.ultimoActivo = activo; this.ultimoHtml = html;
        const mostrar = this.irAlArchivo ? '#archivo' : seMovio || forzar ? '.activa' : undefined;
        this.irAlArchivo = false;
        v.enviar({ tipo: 'lista', html, mostrar });
    }

    /** `grupo`: el buscador que la filtra («hilos», «archivo»), si alguno. */
    private fila(h: cli.JsonHilo, seccion: Seccion, alFinal = '', grupo = ''): string {
        const contexto = esc(JSON.stringify({
            webviewSection: seccion, hilo: h.nombre, preventDefaultContextMenuItems: true,
        }));
        // al principio, todos los íconos, cada uno en su columna aunque esté vacía: así los nombres
        // empiezan siempre en el mismo lugar. Prioridad · semáforo · ⇄ · nombre · última actividad
        const visto = h.atencion === 'termino' && !h.sin_ver;
        const glifo = `<span class="at ${esc(h.atencion)}${visto ? ' visto' : ''}" title="${esc(visto ? 'terminó (ya lo viste)' : h.sin_ver ? 'terminó y no lo has visto: ⌥S' : NOMBRE_ATENCION[h.atencion] ?? '')}">${GLIFO[h.atencion] ?? ' '}</span>`;
        // dónde vive: ⇄ si es en otra máquina y esta ventana solo lo mira (con la columna ancha, su nombre)
        const remoto = this.columnaMaquina(h.remoto === '?' ? '?' : h.remoto ?? '',
            h.remoto ? (h.remoto === '?' ? 'conectado a otra máquina' : `vive en ${h.remoto}`) : '');
        // al final, solo su última modificación: el último prompt a su agente (un clic no cuenta)
        const ultima = ultimaDe(h);
        const der = haceCorto(ultima);
        const marcada = this.mostrado !== undefined ? h.nombre === this.mostrado : h.activo;
        const clases = [seccion, marcada && !this.dashboardActivo ? 'activa' : '', h.vivo ? '' : 'muerto'].filter(Boolean).join(' ');
        const busca = grupo ? ` data-grupo="${grupo}" data-busca="${esc(`${cli.nombreVisible(h)} ${h.nombre} ${h.relativa ?? ''} ${h.remoto || this.aqui}`)}"` : '';
        return `<div class="fila ${clases}"${busca} data-hilo="${esc(h.nombre)}" data-vscode-context="${contexto}" title="${esc(this.tooltip(h))}">`
            + `<span class="prio p${h.prioridad ?? 0}">${PRIORIDAD[h.prioridad ?? 0] ?? PRIORIDAD[0]}</span>`
            + `${glifo}${remoto}<span class="nombre">${esc(cli.nombreVisible(h))}</span><span class="der">${esc(der)}</span>${alFinal}`
            // sin tab que cerrar, lo único que cabe es volver a abrirlo
            // ⋯ el menú del hilo: solo en el navegador (en VS Code es su menú contextual; ahí se esconde)
            + `<span class="iconos"><span class="icono menu-web" data-accion="menu" data-id="${esc(h.nombre)}" title="más: renombrar, vincular, prioridad, llevar…">⋯</span>` + (!h.vivo || seccion === 'archivado'
                ? `<span class="icono" data-accion="retomar" data-id="${esc(h.nombre)}" title="retomar: reabre el tab con su conversación">▶</span>`
                : `<span class="icono" data-accion="archivar" data-id="${esc(h.nombre)}" title="archivar: cierra el tab, guarda su conversación y lo manda al archivo">⏸</span>`
                  + `<span class="icono" data-accion="cerrar" data-id="${esc(h.nombre)}" title="cerrar: cierra el tab y lo que corra adentro, y lo saca de la lista; para guardarlo, ⏸">✕</span>`)
            + '</span></div>';
    }

    /** La columna de dónde vive un hilo: `maquina` vacía es esta. Angosta, ⇄ para los de otra máquina;
     *  ancha (el botón ⇄ junto a buscar), el nombre de la máquina de cada uno, también el de esta. */
    private columnaMaquina(maquina: string, titulo: string): string {
        const t = titulo ? ` title="${esc(titulo)}"` : '';
        if (!this.conMaquina()) return `<span class="remoto"${t}>${maquina ? '⇄' : ' '}</span>`;
        const nombre = maquina === '?' ? '?' : maquina || this.aqui || '·';
        return `<span class="remoto ancho${maquina ? '' : ' aqui'}" style="width: ${this.anchoMaquina}ch"${t || ` title="${esc(`vive aquí${this.aqui ? ` (${this.aqui})` : ''}`)}"`}>${esc(nombre)}</span>`;
    }

    /** Bajo la cabecera de un grupo: el buscador (lo filtra la vista, sin redibujar) y los órdenes.
     *  Un clic en el orden que ya rige vuelve al de telar. En HILOS, además, ⇄: ver la máquina de cada uno. */
    private herramientas(grupo: string, orden: Orden): string {
        const maquina = grupo === 'hilos'
            ? `<span class="ord${this.conMaquina() ? ' si' : ''}" data-accion="ver-maquina" title="${this.conMaquina() ? 'ver solo ⇄ en los hilos de otra máquina' : 'ver en qué máquina vive cada hilo'}">⇄</span>` : '';
        return `<div class="herram"><input class="buscar" data-grupo="${grupo}" placeholder="buscar" spellcheck="false" title="buscar por nombre, carpeta o máquina · ⏎ abre el primero · ⎋ borra">`
            + ORDENES.map(([k, glifo, ayuda]) => `<span class="ord${k === orden ? ' si' : ''}" data-accion="orden-grupo" data-id="${grupo}:${k}" title="${esc(`ordenar por ${ayuda}${k === orden ? ' (clic: volver al orden de telar)' : ''}`)}">${glifo}</span>`).join('')
            + maquina + `</div><div class="vacia" data-grupo="${grupo}" hidden>nada calza</div>`;
    }

    private tooltip(h: cli.JsonHilo): string {
        const visible = cli.nombreVisible(h);
        const l: string[] = [...(visible !== h.nombre ? [visible] : []),
            `${h.nombre}${h.id !== h.nombre ? ` · ${h.id}` : ''} · ${h.relativa || 'sin carpeta'}`];
        const datos: string[] = [];
        if (h.arquetipo) datos.push(h.arquetipo);
        if (h.remoto) datos.push(h.remoto === '?' ? '⇄ en otra máquina' : `⇄ remoto: ${h.remoto}`);
        if (!h.vivo) datos.push('no vivo');
        if (GLIFO[h.atencion]) datos.push(`${GLIFO[h.atencion]} ${NOMBRE_ATENCION[h.atencion] ?? h.atencion}`);
        if (h.prioridad) datos.push(`prioridad ${PRIORIDAD[h.prioridad]} ${['', 'alta', 'media', 'baja'][h.prioridad]}`);
        if (h.tiempo >= 60) datos.push(`hoy ${duracion(h.tiempo)}`);
        if (h.actividad) datos.push(`último prompt hace ${hace(h.actividad)}`);
        if (h.visto) datos.push(`último foco hace ${hace(h.visto)}`);
        if (datos.length) l.push(datos.join(' · '));
        const f = h.ficha;
        if (f?.estado) l.push('', `› ${f.estado}`);
        else if (f?.nota) l.push('', f.nota);
        for (const p of (f?.pendientes ?? []).slice(0, 6)) l.push(`${p.en_curso ? '▣' : p.hecho ? '✓' : '☐'} ${p.texto}`);
        return l.join('\n');
    }

    private html(): string {
        if (modelo.error) {
            return `<div class="aviso">${esc(modelo.error)}<br><br>`
                + `<a data-accion="cmd" data-id="telar.actualizar">reintentar</a></div>`;
        }
        const h: string[] = [];
        if (modelo.aviso) h.push(`<div class="nota">(${esc(modelo.aviso)})</div>`);
        if (!modelo.viva && !modelo.hilos.length) {
            return h.join('') + `<div class="aviso">la sesión «${esc(modelo.sesion)}» no está tejida.<br><br>`
                + `<a data-accion="cmd" data-id="telar.tejer">tejerla en un terminal</a></div>`;
        }
        if (!modelo.hilos.length) {
            return h.join('') + '<div class="aviso">ningún hilo todavía.<br><br>'
                + '<a data-accion="cmd" data-id="telar.nuevo">abrir uno</a></div>';
        }
        if (!modelo.viva) h.push('<div class="nota">la sesión no está viva; esto es lo que telar recuerda</div>');
        // el dashboard encabeza la lista como una fila más, no solo como un ícono en la barra del
        // título: es el lugar al que se vuelve varias veces al día, y en flow estaba ahí
        // porque era un tab. En telar no es un tab del multiplexor sino un panel de VS Code,
        // así que la fila la pone la vista y no la sesión.
        h.push(`<div class="fila hoy${this.dashboardActivo && !this.appActiva ? ' activa' : ''}" data-accion="cmd" data-id="telar.hoy"`
            + ' title="el día: agenda, tareas y lo que espera">'
            + '<span class="prio"> </span><span class="nombre">dashboard</span></div>');
        // debajo, grupos con cabecera plegable, en este orden: AGENTES, HILOS (y las secciones propias),
        // EQUIPO, ARCHIVO y APPS. Los dos primeros empiezan abiertos (es donde se trabaja); los demás,
        // cerrados (se miran de vez en cuando). Dentro de cada grupo, los que tienen tab primero
        const vivosPrimero = (l: cli.JsonHilo[]) => [...l.filter(x => x.vivo), ...l.filter(x => !x.vivo)];
        // `extra`: lo que va al final de la cabecera, con su propia acción (el + de HILOS)
        const cabecera = (clave: string, titulo: string, cuenta: number, porDefecto: boolean, ayuda: string, extra = ''): boolean => {
            const abierta = this.abierta(clave, porDefecto);
            h.push('<div class="sep"></div>');
            h.push(`<div${clave === '__archivo' ? ' id="archivo"' : ''} class="fila cab" data-accion="seccion" data-id="${esc(clave)}" title="${esc(ayuda)}: abrir o cerrar">`
                + `<span class="prio">${abierta ? '▾' : '▸'}</span>${esc(titulo)}${cuenta ? ` <span class="dim">${cuenta}</span>` : ''}${extra}</div>`);
            return abierta;
        };

        // los agentes residentes: uno por línea, como cualquier hilo, con su home al final de la línea.
        // Un agente sin hilo abierto sale igual, tenue, y su línea lleva a su home
        const agentes = modelo.secciones.filter(s => s.grupo === 'agentes');
        if (agentes.length && cabecera('__agentes', 'AGENTES', 0, true, 'los agentes residentes')) {
            for (const a of agentes) {
                const casa = `<span class="icono casa" data-accion="home" data-id="${esc(a.clave)}" title="la casa de ${esc(a.nombre)}: bitácora, memoria, archivos">home</span>`;
                const suyos = vivosPrimero(modelo.enLista.filter(x => cli.enSeccion(a, x.nombre)));
                if (!suyos.length) {
                    // sin hilo vivo: si telar recuerda uno (cerrado o archivado), la línea lo retoma;
                    // si nunca existió, lleva a su home
                    const previo = modelo.hilos.find(x => cli.enSeccion(a, x.nombre));
                    const retomar = previo
                        ? `<span class="icono" data-accion="retomar" data-id="${esc(previo.nombre)}" title="retomar: reabre el hilo con su conversación">▶</span>` : '';
                    const clic = previo ? `data-accion="retomar" data-id="${esc(previo.nombre)}"` : `data-accion="home" data-id="${esc(a.clave)}"`;
                    h.push(`<div class="fila agente muerto" ${clic} title="${esc(a.nombre)}: sin hilo abierto; ${previo ? 'pincha para retomarlo' : 'su home'}">`
                        + '<span class="prio"> </span><span class="at"> </span><span class="remoto"> </span>'
                        + `<span class="nombre">${esc(a.nombre)}</span><span class="der"></span>${retomar}${casa}</div>`);
                    continue;
                }
                suyos.forEach((x, i) => h.push(this.fila(x, 'hilo', i === 0 ? casa : '').replace('class="fila ', 'class="fila agente ')));
            }
        }

        // los hilos abiertos que no reclama nadie: los de esta máquina y, después, los de las otras (de su foto,
        // solo los vivos; un hilo que la lista ya trae, uno de [remotos], no se repite). Cada uno dice dónde vive
        const ordenH = this.ordenDe('hilos');
        const sueltos = ordenar(vivosPrimero(modelo.enLista.filter(y => !modelo.seccionDe(y.nombre))), ordenH);
        const yaEstan = new Set(modelo.hilos.filter(x => x.remoto).map(x => `${x.remoto}|${x.nombre}`));
        const deOtras = this.otras.flatMap(m => m.hilos.filter(x => x.vivo && !yaEstan.has(`${m.nombre}|${x.nombre}`)).map(x => ({ m, x })));
        const nombres = [this.aqui, ...this.otras.map(m => m.nombre), ...sueltos.map(x => x.remoto ?? '')];
        this.anchoMaquina = Math.min(12, Math.max(1, ...nombres.map(n => n.length)));
        // + abre un hilo nuevo: solo en el navegador (en VS Code es el + de la barra del título)
        const nuevo = '<span class="nuevo-web" data-accion="cmd" data-id="telar.nuevo" title="hilo nuevo: un tab con su agente">+ nuevo</span>';
        if (cabecera('__hilos', 'HILOS', sueltos.length + deOtras.length, true, 'los hilos abiertos, de esta máquina y de las otras', nuevo)) {
            h.push(this.herramientas('hilos', ordenH));
            for (const x of sueltos) h.push(this.fila(x, 'hilo', '', 'hilos'));
            for (const { m, x } of deOtras) {
                const at = x.atencion ?? 'ninguna';
                const estadoM = m.en_linea ? '' : `\n${m.nombre} está apagado${m.edad !== null ? ` hace ${haceCorto(new Date(Date.now() - m.edad * 1000).toISOString())}` : ''}`;
                h.push(`<div class="fila remota${m.en_linea ? '' : ' muerto'}" data-accion="ir-remoto" data-id="${esc(`${m.nombre}|${x.nombre}`)}"`
                    + ` data-grupo="hilos" data-busca="${esc(`${x.nombre} ${x.relativa ?? ''} ${m.nombre}`)}"`
                    + ` title="${esc(`${m.nombre}:${x.nombre}${x.relativa ? `\n${x.relativa}` : ''}${x.resumen ? `\n${x.resumen}` : ''}${estadoM}`)}">`
                    + `<span class="prio p${x.prioridad ?? 0}">${PRIORIDAD[x.prioridad ?? 0] ?? PRIORIDAD[0]}</span>`
                    + `<span class="at ${esc(at)}" title="${esc(NOMBRE_ATENCION[at] ?? '')}">${GLIFO[at] ?? ' '}</span>`
                    + this.columnaMaquina(m.nombre, `vive en ${m.nombre}`)
                    + `<span class="nombre">${esc(x.nombre)}</span></div>`);
            }
        }

        // las secciones propias (`[secciones]`): un grupo de hilos cada una, como HILOS
        for (const s of modelo.secciones.filter(x => x.grupo !== 'agentes')) {
            const suyos = vivosPrimero(modelo.enLista.filter(x => cli.enSeccion(s, x.nombre)));
            if (!cabecera(s.clave, s.nombre.toUpperCase(), suyos.length, true, `la sección ${s.nombre}`)) continue;
            if (s.home) {
                h.push(`<div class="fila hoy" data-accion="home" data-id="${esc(s.clave)}" title="la página de ${esc(s.nombre)}">`
                    + '<span class="prio"> </span><span class="nombre">home</span></div>');
            }
            for (const x of suyos) h.push(this.fila(x, 'hilo'));
        }

        // lo que el equipo le pide a Nico; pinchar una fila abre sus acciones
        if (modelo.equipoRemoto) {
            const pend = modelo.sugerencias;
            if (cabecera('__equipo', 'EQUIPO', pend.length, false, 'lo que el equipo te pide')) {
                if (!pend.length) h.push('<div class="fila dim"><span class="prio"> </span>nada esperando</div>');
                for (const x of pend) {
                    const pedido = x.tipo === 'tarea';
                    h.push(`<div class="fila equipo" data-accion="equipo" data-id="${esc(x.id)}" title="${esc(`${x.persona}: ${x.titulo}${x.motivo ? `\n«${x.motivo}»` : ''}\nclic: acciones`)}">`
                        + `<span class="prio">◆</span><span class="nombre">${esc(x.persona)} · ${esc(pedido ? x.titulo : `${x.tarea}: subir`)}</span>`
                        + `<span class="der dim">${x.revisando ? 'Gestión' : (x.similares?.length ? '¿ya existe?' : '')}</span></div>`);
                }
            }
        }

        const ordenA = this.ordenDe('archivo');
        const archivados = ordenar(modelo.archivados, ordenA);
        if (archivados.length && cabecera('__archivo', 'ARCHIVO', archivados.length, false, 'los hilos archivados')) {
            h.push(this.herramientas('archivo', ordenA));
            for (const x of archivados) h.push(this.fila(x, 'archivado', '', 'archivo'));
        }

        // las apps (`[apps]`): lo que se abre en el panel y no es un hilo; una fila cada una
        if (modelo.apps.length && cabecera('__apps', 'APPS', 0, false, 'lo que se abre en el panel')) {
            for (const a of modelo.apps) {
                const activa = this.dashboardActivo && this.appActiva === a.clave ? ' activa' : '';
                h.push(`<div class="fila hoy${activa}" data-accion="app" data-id="${esc(a.clave)}" title="${esc(a.descripcion || a.nombre)}">`
                    + `<span class="prio"> </span><span class="nombre">${esc(a.nombre)}</span></div>`);
            }
        }
        return h.join('');
    }
}
