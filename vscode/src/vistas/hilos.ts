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

import * as vscode from 'vscode';
import { anotarDesdeFuera as anotarClic, mostrarTerminal } from '../acciones';

import * as cli from '../cli';
import { GLIFO, NOMBRE_ATENCION, PRIORIDAD, duracion, esc, hace, haceCorto } from '../estilo';
import { marco } from '../estilo';
import { modelo } from '../modelo';

const CSS = `
  #lista { padding: .5em 0 1.5em; user-select: none; }
  .fila { display: flex; position: relative; white-space: pre; padding: 0 1.5ch; cursor: pointer; }
  .fila:hover { background: var(--hover); }
  .fila.activa { background: var(--sel); }
  .prio { flex: none; width: 1ch; margin-right: 1ch; }
  .prio.p0 { color: var(--dim); }
  .p1 { color: var(--fg); } .p2 { color: color-mix(in srgb, var(--fg) 65%, var(--bg)); } .p3 { color: var(--dim); }
  .nombre { flex: 0 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; }
  .muerto .nombre, .archivado .nombre, .archivado .prio { color: var(--dim); }
  .at { flex: none; margin-left: 1ch; }
  .remoto { flex: none; margin-left: 1ch; color: var(--cian); }
  .at.trabajando { color: var(--azul); } .at.espera { color: var(--amarillo); } .at.termino { color: var(--verde); }
  .der { flex: none; margin-left: auto; padding-left: 1ch; color: var(--dim); }
  .sep { border-top: 1px solid var(--linea); margin: .4em 1.5ch; }
  .cab { color: var(--amarillo); font-weight: bold; }
  .hoy .nombre { color: var(--azul); }
  .cab .dim { font-weight: normal; }
  .nota { color: var(--dim); padding: .2em 1.5ch; white-space: pre-wrap; }
  .iconos { position: absolute; right: 1.5ch; top: 0; bottom: 0; display: none; padding-left: 1ch;
           background: linear-gradient(var(--hover), var(--hover)), var(--bg); }
  .activa .iconos { background: linear-gradient(var(--sel), var(--sel)), var(--bg); }
  .fila:hover .iconos { display: flex; }
  .icono { margin-left: 1ch; color: var(--dim); cursor: pointer; font-variant-emoji: text; }
  .icono:hover { color: var(--fg); }
`;

const SCRIPT = `
const lista = document.getElementById('lista');
window.addEventListener('message', e => {
  const m = e.data;
  if (m.tipo !== 'lista') return;
  lista.innerHTML = m.html;
  if (m.mostrar) { const el = document.querySelector(m.mostrar); if (el) el.scrollIntoView({ block: 'nearest' }); }
});
document.addEventListener('click', e => {
  const f = e.target.closest('[data-hilo],[data-accion]');
  if (!f) return;
  if (f.dataset.accion) vscode.postMessage({ tipo: f.dataset.accion, id: f.dataset.id });
  else vscode.postMessage({ tipo: 'ir', hilo: f.dataset.hilo });
});
vscode.postMessage({ tipo: 'listo' });
`;

type Seccion = 'hilo' | 'archivado';

export class VistaHilos implements vscode.WebviewViewProvider {
    vista?: vscode.WebviewView;
    archivoAbierto = false;
    private listo = false;
    private ultimoHtml = '';
    private ultimoActivo?: string;
    private irAlArchivo = false;
    /** las secciones plegadas, por clave; abiertas por defecto */
    private plegadas = new Set<string>();

    resolveWebviewView(v: vscode.WebviewView): void {
        this.vista = v;
        v.webview.options = { enableScripts: true };
        v.webview.onDidReceiveMessage(m => this.mensaje(m));
        v.onDidDispose(() => { this.vista = undefined; this.listo = false; });
        // Abrir la barra de telar es ir a trabajar en la sesión: el terminal que la muestra
        // pasa al frente, como cuando se elige con ⌃P. Solo si lo encuentra: sin terminal
        // de la sesión, abrir la barra no le quita el foco a nadie.
        const alFrente = () => { if (v.visible) void mostrarTerminal({ soloSuyo: true }); };
        v.onDidChangeVisibility(alFrente);
        alFrente();
        this.pintarMarco();
    }

    /** El HTML fijo (estilo y script); la lista entra después por mensajes. */
    pintarMarco(): void {
        if (!this.vista) return;
        this.listo = false; this.ultimoHtml = '';
        this.vista.webview.html = marco(this.vista.webview, CSS, '<div id="lista"></div>', SCRIPT);
    }

    private mensaje(m: { tipo: string; hilo?: string; id?: string }): void {
        switch (m.tipo) {
            case 'listo': this.listo = true; this.refrescar(true); break;
            case 'ir': {
                if (!m.hilo) break;
                // un archivado no tiene tab al que ir: pincharlo es retomarlo
                const sinTab = modelo.hilos.some(x => x.nombre === m.hilo && (!x.vivo || x.archivado));
                void vscode.commands.executeCommand(sinTab ? 'telar.retomar' : 'telar.ir', { hilo: m.hilo });
                break;
            }
            case 'archivar': if (m.id) void vscode.commands.executeCommand('telar.archivar', { hilo: m.id }); break;
            case 'retomar': if (m.id) void vscode.commands.executeCommand('telar.retomar', { hilo: m.id }); break;
            case 'cerrar': if (m.id) void vscode.commands.executeCommand('telar.cerrar', { hilo: m.id }); break;
            case 'archivo': void vscode.commands.executeCommand('telar.archivo'); break;
            case 'seccion':
                if (m.id) { if (this.plegadas.has(m.id)) this.plegadas.delete(m.id); else this.plegadas.add(m.id); this.refrescar(true); }
                break;
            case 'home': if (m.id) void vscode.commands.executeCommand('telar.seccion', m.id); break;
            case 'cmd': if (m.id?.startsWith('telar.')) void vscode.commands.executeCommand(m.id); break;
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
        v.badge = modelo.esperan
            ? { value: modelo.esperan, tooltip: `${modelo.esperan} te espera${modelo.esperan === 1 ? '' : 'n'}` }
            : undefined;
        v.description = modelo.error ? 'sin telar' : !modelo.viva ? 'sesión no tejida' : modelo.sesion;
        const orden = ({ alfa: 'a-z', reciente: '◷', prioridad: '●' } as Record<string, string>)[modelo.orden] ?? '';
        v.title = orden ? `hilos · ${orden}` : 'hilos';
        if (!this.listo) return;
        const html = this.html();
        const activo = modelo.activo?.nombre;
        const seMovio = activo !== this.ultimoActivo;
        if (!forzar && !seMovio && html === this.ultimoHtml) return;
        this.ultimoActivo = activo; this.ultimoHtml = html;
        const mostrar = this.irAlArchivo ? '#archivo' : seMovio || forzar ? '.activa' : undefined;
        this.irAlArchivo = false;
        void v.webview.postMessage({ tipo: 'lista', html, mostrar });
    }

    private fila(h: cli.JsonHilo, seccion: Seccion): string {
        const contexto = esc(JSON.stringify({
            webviewSection: seccion, hilo: h.nombre, preventDefaultContextMenuItems: true,
        }));
        const glifo = GLIFO[h.atencion] ? `<span class="at ${h.atencion}">${GLIFO[h.atencion]}</span>` : '';
        // ⇄: el agente vive en otra máquina y esta ventana solo lo mira
        const remoto = h.remoto ? `<span class="remoto" title="${esc(h.remoto === '?' ? 'conectado a otra máquina' : `remoto: ${h.remoto}`)}">⇄</span>` : '';
        const der = seccion === 'archivado' || !h.vivo ? haceCorto(h.visto) : duracion(h.tiempo);
        const clases = [seccion, h.activo ? 'activa' : '', h.vivo ? '' : 'muerto'].filter(Boolean).join(' ');
        return `<div class="fila ${clases}" data-hilo="${esc(h.nombre)}" data-vscode-context="${contexto}" title="${esc(this.tooltip(h))}">`
            + `<span class="prio p${h.prioridad ?? 0}">${PRIORIDAD[h.prioridad ?? 0] ?? PRIORIDAD[0]}</span>`
            + `<span class="nombre">${esc(cli.nombreVisible(h))}</span>${remoto}${glifo}<span class="der">${esc(der)}</span>`
            // sin tab que cerrar, lo único que cabe es volver a abrirlo
            + '<span class="iconos">' + (!h.vivo || seccion === 'archivado'
                ? `<span class="icono" data-accion="retomar" data-id="${esc(h.nombre)}" title="retomar: reabre el tab con su conversación">▶</span>`
                : `<span class="icono" data-accion="archivar" data-id="${esc(h.nombre)}" title="archivar: cierra el tab, guarda su conversación y lo manda al archivo">⏸</span>`
                  + `<span class="icono" data-accion="cerrar" data-id="${esc(h.nombre)}" title="cerrar: cierra el tab y lo que corra adentro, y lo saca de la lista; para guardarlo, ⏸">✕</span>`)
            + '</span></div>';
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
        h.push('<div class="fila hoy" data-accion="cmd" data-id="telar.hoy" title="el día: agenda, tareas y lo que espera">'
            + '<span class="prio"> </span><span class="nombre">dashboard</span></div>');
        // cada sección es un grupo propio entre el dashboard y la lista general: sus hilos
        // (los vivos; los archivados siguen en el archivo) salen de la lista de abajo
        // los que tienen tab primero, los que no después; dentro de cada grupo, el orden elegido
        const vivosPrimero = (l: cli.JsonHilo[]) => [...l.filter(x => x.vivo), ...l.filter(x => !x.vivo)];
        for (const s of modelo.secciones) {
            const suyos = vivosPrimero(modelo.enLista.filter(x => cli.enSeccion(s, x.nombre)));
            const abierta = !this.plegadas.has(s.clave);
            h.push('<div class="sep"></div>');
            h.push(`<div class="fila cab" data-accion="seccion" data-id="${esc(s.clave)}" title="abrir o cerrar la sección">`
                + `<span class="prio">${abierta ? '▾' : '▸'}</span>${esc(s.nombre.toUpperCase())}`
                + (suyos.length ? ` <span class="dim">${suyos.length}</span>` : '') + '</div>');
            if (!abierta) continue;
            if (s.home) {
                h.push(`<div class="fila hoy" data-accion="home" data-id="${esc(s.clave)}" title="la página de ${esc(s.nombre)}">`
                    + '<span class="prio"> </span><span class="nombre">home</span></div>');
            }
            for (const x of suyos) h.push(this.fila(x, 'hilo'));
        }
        h.push('<div class="sep"></div>');
        for (const x of vivosPrimero(modelo.enLista.filter(y => !modelo.seccionDe(y.nombre)))) h.push(this.fila(x, 'hilo'));
        const archivados = modelo.archivados;
        if (archivados.length) {
            h.push('<div class="sep"></div>');
            h.push('<div id="archivo" class="fila cab" data-accion="archivo" title="abrir o cerrar el archivo">'
                + `<span class="prio">${this.archivoAbierto ? '▾' : '▸'}</span>`
                + `ARCHIVO <span class="dim">${archivados.length} hilo${archivados.length === 1 ? '' : 's'}</span></div>`);
            if (this.archivoAbierto) for (const x of archivados) h.push(this.fila(x, 'archivado'));
        }
        return h.join('');
    }
}
