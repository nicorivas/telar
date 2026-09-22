// La vista «hilos»: lo que hay abierto, con semáforo, prioridad y tiempo del día.
//
// Es la lista de proyectos de la barra, pero se llama como la llama telar: un hilo es una
// unidad de trabajo viva, y qué cuenta como proyecto lo declara el perfil del repositorio,
// no esta extensión.
//
//   3 ● faro            ●   49m   ← id del multiplexor · prioridad · nombre · atención · hoy
//   4 ◐ molino               7m
//   ▸ ARCHIVO 6 hilos         2d  ← plegado; a la derecha, hace cuánto se usó
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
  .fila { display: flex; white-space: pre; padding: 0 1.5ch; cursor: pointer; }
  .fila:hover { background: var(--hover); }
  .fila.activa { background: var(--sel); }
  .num { flex: none; width: 3ch; text-align: right; color: var(--dim); }
  .activa .num { color: var(--fg); }
  .prio { flex: none; width: 1ch; margin: 0 1ch; }
  .p1 { color: var(--fg); } .p2 { color: color-mix(in srgb, var(--fg) 65%, var(--bg)); } .p3 { color: var(--dim); }
  .nombre { flex: 0 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; }
  .muerto .nombre, .archivado .nombre, .archivado .prio { color: var(--dim); }
  .at { flex: none; margin-left: 1ch; }
  .at.trabajando { color: var(--azul); } .at.espera { color: var(--amarillo); } .at.termino { color: var(--verde); }
  .der { flex: none; margin-left: auto; padding-left: 1ch; color: var(--dim); }
  .sep { border-top: 1px solid var(--linea); margin: .4em 1.5ch; }
  .cab { color: var(--amarillo); font-weight: bold; }
  .hoy .nombre { color: var(--azul); }
  .cab .dim { font-weight: normal; }
  .nota { color: var(--dim); padding: .2em 1.5ch; white-space: pre-wrap; }
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
            case 'ir': anotarClic(`clic en la lista: «${m.hilo ?? ''}»`); if (m.hilo) void vscode.commands.executeCommand('telar.ir', { hilo: m.hilo }); break;
            case 'archivo': void vscode.commands.executeCommand('telar.archivo'); break;
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
        // El id es la llave del multiplexor: un índice en tmux, el nombre en zellij. Se muestra
        // solo cuando dice algo que el nombre no diga ya.
        const num = h.id !== h.nombre && h.id.length <= 3 ? h.id : '';
        const glifo = GLIFO[h.atencion] ? `<span class="at ${h.atencion}">${GLIFO[h.atencion]}</span>` : '';
        const der = seccion === 'archivado' || !h.vivo ? haceCorto(h.visto) : duracion(h.tiempo);
        const clases = [seccion, h.activo ? 'activa' : '', h.vivo ? '' : 'muerto'].filter(Boolean).join(' ');
        return `<div class="fila ${clases}" data-hilo="${esc(h.nombre)}" data-vscode-context="${contexto}" title="${esc(this.tooltip(h))}">`
            + `<span class="num">${esc(num)}</span>`
            + `<span class="prio p${h.prioridad ?? 0}">${PRIORIDAD[h.prioridad ?? 0] ?? ' '}</span>`
            + `<span class="nombre">${esc(h.nombre)}</span>${glifo}<span class="der">${esc(der)}</span></div>`;
    }

    private tooltip(h: cli.JsonHilo): string {
        const l: string[] = [`${h.nombre}${h.id !== h.nombre ? ` · ${h.id}` : ''} · ${h.relativa || 'sin carpeta'}`];
        const datos: string[] = [];
        if (h.arquetipo) datos.push(h.arquetipo);
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
            + '<span class="num"></span><span class="prio"> </span><span class="nombre">dashboard</span></div>');
        h.push('<div class="sep"></div>');
        for (const x of modelo.enLista) h.push(this.fila(x, 'hilo'));
        const archivados = modelo.archivados;
        if (archivados.length) {
            h.push('<div class="sep"></div>');
            h.push('<div id="archivo" class="fila cab" data-accion="archivo" title="abrir o cerrar el archivo">'
                + `<span class="num">${this.archivoAbierto ? '▾' : '▸'}</span><span class="prio"> </span>`
                + `ARCHIVO <span class="dim">${archivados.length} hilo${archivados.length === 1 ? '' : 's'}</span></div>`);
            if (this.archivoAbierto) for (const x of archivados) h.push(this.fila(x, 'archivado'));
        }
        return h.join('');
    }
}
