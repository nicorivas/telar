// La vista «ficha»: lo que el documento de un hilo dice de sí mismo.
//
// No interpreta nada. Pide `telar ficha <hilo> --json` y dibuja lo que venga: el estado en
// una línea, los pendientes, las secciones que el perfil del repositorio haya declarado, y
// las acciones que ese mismo perfil ofrece sobre el hilo. Qué secciones existen y cómo se
// llaman es cosa del repositorio; aquí solo se sabe dibujar una tabla, una lista, unas
// casillas y un párrafo.
//
// Dos modos: la ficha, y el documento entero en markdown (lo renderiza VS Code).

import * as fs from 'fs';
import * as path from 'path';
import * as vscode from 'vscode';

import * as cli from '../cli';
import { GLIFO, NOMBRE_ATENCION, duracion, esc, hace, marco } from '../estilo';
import { modelo } from '../modelo';

const CSS = `
  body { padding: 0 1.5ch 2em; }
  .barra { display: flex; gap: 2ch; align-items: baseline; padding: .5em 0 .4em; position: sticky; top: 0;
           background: var(--bg); border-bottom: 1px solid var(--linea); margin-bottom: .6em; }
  .barra button { font: inherit; background: none; border: 0; padding: 0; color: var(--dim); cursor: pointer; }
  .barra button:hover { color: var(--fg); }
  .barra button.activo { color: var(--fg); text-decoration: underline; text-underline-offset: 3px; }
  .barra .sep { flex: 1; }
  h1.t { font-size: 1em; font-weight: bold; margin: .3em 0 0; }
  .sem { display: inline-block; margin-top: .2em; }
  .sem.trabajando { color: var(--azul); } .sem.espera { color: var(--amarillo); } .sem.termino { color: var(--verde); }
  h2 { font-size: 1em; font-weight: bold; text-transform: uppercase; margin: 1.1em 0 .1em; }
  h2 small { font-size: 1em; font-weight: normal; text-transform: none; color: var(--dim); }
  ul { list-style: none; padding: 0; margin: 0; }
  li { padding-left: 4ch; text-indent: -2ch; }
  li .m { display: inline-block; width: 2ch; text-indent: 0; }
  li.pend { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  li.pend a { color: inherit; } li.pend a:hover { color: var(--azul); text-decoration: none; }
  .ref { color: var(--dim); margin-right: 1ch; }
  .campos div { display: flex; gap: 1ch; }
  .campos .k { color: var(--dim); min-width: 14ch; }
  .accion { display: block; cursor: pointer; }
  .accion .tecla { color: var(--dim); margin-right: 1ch; }
  .accion:hover { background: var(--hover); }
  .md { max-width: 90ch; }
  .md h1, .md h2, .md h3, .md h4 { font-size: 1em; font-weight: bold; text-transform: none; margin: 1.2em 0 .3em; }
  .md h1 { color: var(--magenta); } .md h2 { color: var(--azul); } .md h3, .md h4 { color: var(--cian); }
  .md h1::before { content: "# "; color: var(--dim); } .md h2::before { content: "## "; color: var(--dim); }
  .md h3::before { content: "### "; color: var(--dim); } .md h4::before { content: "#### "; color: var(--dim); }
  .md p { margin: .5em 0; }
  .md table { border-collapse: collapse; margin: .5em 0; }
  .md td, .md th { border: 1px solid var(--linea); padding: 0 1ch; text-align: left; vertical-align: top; }
  .md th { font-weight: bold; }
  .md code { font: inherit; color: var(--verde); }
  .md pre { background: var(--hover); padding: .5em 1ch; overflow-x: auto; } .md pre code { color: var(--fg); }
  .md ul, .md ol { padding-left: 3ch; margin: .3em 0; } .md ul { list-style: "- "; }
  .md li { padding-left: 0; text-indent: 0; }
  .md li::marker { color: var(--dim); }
  .md blockquote { border-left: 2px solid var(--linea); margin: .5em 0; padding: 0 1ch; color: var(--dim); }
  .md strong { color: var(--fg); } .md em { color: var(--amarillo); font-style: normal; }
  .md img { max-width: 100%; } .md hr { border: 0; border-top: 1px dashed var(--linea); margin: 1em 0; }
`;

const SCRIPT = `
document.addEventListener('click', e => {
  const t = e.target.closest('[data-modo],[data-msg],a[href]'); if (!t) return;
  if (t.dataset.modo) return vscode.postMessage({ tipo: 'modo', valor: t.dataset.modo });
  if (t.dataset.msg) { e.preventDefault(); return vscode.postMessage({ tipo: t.dataset.msg, valor: t.dataset.valor }); }
  if (t.getAttribute('href')) { e.preventDefault(); vscode.postMessage({ tipo: 'abrir', valor: t.getAttribute('href') }); }
});
`;

export class VistaFicha implements vscode.WebviewViewProvider {
    vista?: vscode.WebviewView;
    modo: 'ficha' | 'documento' = 'ficha';
    /** un hilo elegido desde el menú; se suelta cuando cambia el que tiene el foco */
    fijado?: string;
    datos?: cli.JsonFichaOrden;
    error = '';
    private mostrado?: string;
    private ultimoActivo?: string;
    private vigia?: fs.FSWatcher;
    private generacion = 0;

    resolveWebviewView(v: vscode.WebviewView): void {
        this.vista = v;
        v.webview.options = { enableScripts: true, localResourceRoots: this.raices() };
        v.webview.onDidReceiveMessage(m => void this.mensaje(m));
        v.onDidChangeVisibility(() => { if (v.visible) void this.actualizar(); });
        v.onDidDispose(() => { this.vista = undefined; this.vigia?.close(); this.vigia = undefined; });
        void this.actualizar();
    }

    /** Las imágenes del markdown salen del repositorio de trabajo, y de la carpeta del
     *  hilo cuando está fuera de él (un hilo vinculado a otra parte). */
    private raices(): vscode.Uri[] {
        const r = [modelo.raiz, this.datos?.hilo.ruta].filter((x): x is string => !!x);
        return [...new Set(r)].map(x => vscode.Uri.file(x));
    }

    /** Lo llama el modelo en cada cambio: si cambió el hilo con foco, la ficha lo sigue. */
    seguir(): void {
        const activo = modelo.activo?.nombre;
        if (activo !== this.ultimoActivo) { this.ultimoActivo = activo; this.fijado = undefined; }
        const objetivo = this.objetivo();
        if (objetivo && objetivo !== this.mostrado) void this.actualizar();
    }

    objetivo(): string | undefined { return this.fijado ?? modelo.activo?.nombre; }

    async actualizar(): Promise<void> {
        const hilo = this.objetivo();
        if (!hilo || !this.vista) return;
        const gen = ++this.generacion;
        if (hilo !== this.mostrado) { this.mostrado = hilo; this.datos = undefined; this.error = ''; await this.render(); }
        const r = await cli.ficha(hilo);
        if (gen !== this.generacion) return;   // ya se pidió otra
        this.datos = r.datos && { ...r.datos, hilo: cli.conRutasAbsolutas(r.datos.hilo, modelo.raiz) };
        this.error = r.error ?? '';
        if (this.vista) this.vista.webview.options = { enableScripts: true, localResourceRoots: this.raices() };
        this.vigilar(this.datos?.hilo.ficha?.documento ?? '');
        await this.render();
    }

    /** Si el documento cambia en el disco, la ficha se rehace sola. */
    private vigilar(archivo: string): void {
        this.vigia?.close(); this.vigia = undefined;
        if (!archivo || !fs.existsSync(archivo)) return;
        try {
            let rebote: NodeJS.Timeout | undefined;
            this.vigia = fs.watch(archivo, { persistent: false }, () => {
                if (rebote) clearTimeout(rebote);
                rebote = setTimeout(() => void this.actualizar(), 400);
            });
        } catch { /* un archivo que no se puede vigilar se relee igual con el sondeo lento */ }
    }

    private async mensaje(m: { tipo: string; valor?: string }): Promise<void> {
        const d = this.datos;
        const documento = d?.hilo.ficha?.documento ?? '';
        switch (m.tipo) {
            case 'modo': this.modo = m.valor === 'documento' ? 'documento' : 'ficha'; await this.render(); break;
            case 'editar': if (documento) await abrir(documento); break;
            case 'carpeta': if (d?.hilo.ruta) {
                await vscode.commands.executeCommand('revealInExplorer', vscode.Uri.file(d.hilo.ruta));
            } break;
            case 'vincular': await vscode.commands.executeCommand('telar.vincular', { hilo: this.objetivo() }); break;
            case 'pendiente': if (documento && m.valor) await abrir(documento, m.valor); break;
            case 'accion': if (m.valor && d) await vscode.commands.executeCommand('telar.accion', { hilo: d.hilo.nombre, accion: m.valor }); break;
            case 'abrir': if (m.valor && documento) {
                if (/^[a-z]+:/i.test(m.valor)) { await vscode.env.openExternal(vscode.Uri.parse(m.valor)); break; }
                const destino = path.resolve(path.dirname(documento), m.valor.split('#')[0]);
                if (fs.existsSync(destino)) await abrir(destino);
            } break;
        }
    }

    async render(): Promise<void> {
        if (!this.vista) return;
        const d = this.datos;
        const hilo = this.objetivo() ?? '';
        const ficha = d?.hilo.ficha;
        let cuerpo: string;
        if (this.error) cuerpo = `<div class="aviso">${esc(this.error)}</div>`;
        else if (!d) cuerpo = `<div class="aviso">leyendo «${esc(hilo)}»…</div>`;
        else if (!d.hilo.vinculado) {
            cuerpo = `<div class="aviso">«${esc(hilo)}» no está vinculado a ninguna carpeta.<br>`
                + '<a data-msg="vincular">Vincular a una carpeta…</a></div>';
        } else if (!ficha || !ficha.documento) {
            cuerpo = `<div class="aviso">sin documento en <code>${esc(d.hilo.relativa)}</code>`
                + `${ficha?.nota ? `<br>${esc(ficha.nota)}` : ''}</div>`;
        } else if (this.modo === 'ficha') cuerpo = this.htmlFicha(d);
        else cuerpo = await this.htmlMarkdown(ficha.documento);
        const boton = (modo: string, texto: string) =>
            `<button data-modo="${modo}" class="${this.modo === modo ? 'activo' : ''}">${texto}</button>`;
        const barra = ficha?.documento
            ? `<div class="barra">${boton('ficha', 'ficha')}${boton('documento', path.basename(ficha.documento))}<span class="sep"></span>`
            + '<button data-msg="editar" title="abrir el documento en el editor">editar</button>'
            + '<button data-msg="carpeta" title="ver la carpeta en el explorador">carpeta</button></div>'
            : '';
        this.vista.webview.html = marco(this.vista.webview, CSS, barra + cuerpo, SCRIPT);
    }

    private htmlFicha(d: cli.JsonFichaOrden): string {
        const hilo = d.hilo;
        const f = hilo.ficha!;
        const h: string[] = [];
        h.push(`<h1 class="t">${esc(f.titulo || hilo.nombre)}</h1>`
            + `<div class="dim"><a data-msg="carpeta">${esc(hilo.relativa || hilo.ruta)}</a></div>`);
        const detalles: string[] = [];
        if (hilo.arquetipo) detalles.push(hilo.arquetipo);
        if (!hilo.vivo) detalles.push('no vivo');
        if (hilo.archivado) detalles.push('archivado');
        if (hilo.prioridad) detalles.push(`prioridad ${hilo.prioridad}`);
        if (hilo.tiempo >= 60) detalles.push(`hoy ${duracion(hilo.tiempo)}`);
        if (hilo.sesiones.length) detalles.push(`${hilo.sesiones.length} conversación(es)`);
        if (f.leida) detalles.push(`leído hace ${hace(f.leida)}`);
        if (detalles.length) h.push(`<div class="dim">${esc(detalles.join(' · '))}</div>`);
        if (GLIFO[hilo.atencion]) {
            h.push(`<div class="sem ${hilo.atencion}">${GLIFO[hilo.atencion]} el agente ${esc(NOMBRE_ATENCION[hilo.atencion] ?? hilo.atencion)}</div>`);
        }
        if (f.nota) h.push(`<div class="dim">${esc(f.nota)}</div>`);

        h.push('<h2>Estado</h2>');
        h.push(f.estado ? `<div>› ${esc(f.estado)}</div>` : '<div class="dim">el documento no dice cómo va</div>');

        h.push('<h2>Pendientes<small> (clic: ir a esa línea del documento)</small></h2>');
        if (f.pendientes.length) {
            h.push('<ul>' + f.pendientes.map((p, i) => {
                const marca = p.en_curso ? '▣' : p.hecho ? '✓' : '☐';
                const ref = p.ref || p.id || `${hilo.nombre}:${i + 1}`;
                return `<li class="pend"><span class="m">${marca}</span>`
                    + `<a data-msg="pendiente" data-valor="${esc(p.texto)}" title="${esc(p.texto)}">`
                    + `<span class="ref">${esc(ref)}</span>${esc(p.texto)}</a></li>`;
            }).join('') + '</ul>');
        } else h.push('<div class="dim">ninguno</div>');

        for (const [nombre, valor] of Object.entries(f.secciones ?? {})) {
            h.push(`<h2>${esc(nombre)}</h2>`, dibujar(valor));
        }

        if (d.acciones.length) {
            h.push(`<h2>Acciones<small> (las declara ${esc(d.perfil)})</small></h2>`);
            for (const a of d.acciones) {
                h.push(`<div class="accion" data-msg="accion" data-valor="${esc(a.nombre)}" title="${esc(a.descripcion || a.nombre)}">`
                    + `<span class="tecla">${a.tecla ? `[${esc(a.tecla)}]` : '  '}</span>${esc(a.nombre)}`
                    + `<span class="dim"> ${esc(a.descripcion)}</span></div>`);
            }
        }
        return h.join('\n');
    }

    private async htmlMarkdown(archivo: string): Promise<string> {
        let texto: string;
        try { texto = fs.readFileSync(archivo, 'utf8'); } catch { return `<div class="aviso">no pude leer ${esc(archivo)}</div>`; }
        if (!/\.(md|markdown)$/i.test(archivo)) return `<pre class="md">${esc(texto)}</pre>`;
        texto = texto.replace(/^---\n[\s\S]*?\n---\n/, '');   // el front matter no es para leer
        let html: string;
        try { html = await vscode.commands.executeCommand<string>('markdown.api.render', texto); }
        catch { html = `<pre>${esc(texto)}</pre>`; }
        const base = path.dirname(archivo);
        html = html.replace(/<img([^>]*?)src="(?!https?:|data:)([^"]+)"/g, (_m, pre, src) =>
            `<img${pre}src="${this.vista!.webview.asWebviewUri(vscode.Uri.file(path.resolve(base, src)))}"`);
        return `<div class="md">${html}</div>`;
    }
}

/** Una sección, del tipo que sea: tabla (objeto), lista (arreglo), casillas o texto.
 *
 *  Lo que viaja en `secciones` ya viene en JSON y sin clases: aquí se dibuja por la forma
 *  que tenga, no por cómo se llame. Un objeto con `texto` y una casilla es un pendiente;
 *  uno con `texto` y `cuando` es una espera; uno con `que` y `cuando` es un hito; uno con
 *  `destino`, un enlace. Lo que no calce con ninguno se muestra clave por clave, que es
 *  mejor que esconderlo. */
function dibujar(valor: unknown): string {
    if (valor && typeof valor === 'object' && !Array.isArray(valor)) {
        const filas = Object.entries(valor as Record<string, unknown>)
            .map(([k, v]) => `<div><span class="k">${esc(k)}</span><span>${esc(String(v))}</span></div>`);
        return `<div class="campos">${filas.join('')}</div>`;
    }
    if (Array.isArray(valor)) {
        if (!valor.length) return '<div class="dim">—</div>';
        return '<ul>' + valor.map(v => `<li>${vinieta(v)}</li>`).join('') + '</ul>';
    }
    const texto = String(valor ?? '');
    return texto.trim() ? `<div>${esc(texto).replace(/\n/g, '<br>')}</div>` : '<div class="dim">—</div>';
}

function vinieta(v: unknown): string {
    if (!v || typeof v !== 'object') return `<span class="m">·</span>${esc(String(v ?? ''))}`;
    const o = v as Record<string, unknown>;
    if (typeof o.texto === 'string' && ('hecho' in o || 'en_curso' in o)) {
        return `<span class="m">${o.en_curso ? '▣' : o.hecho ? '✓' : '☐'}</span>${esc(o.texto)}`;
    }
    if (typeof o.texto === 'string' && typeof o.destino === 'string') {
        return `<span class="m">→</span><a href="${esc(o.destino)}">${esc(o.texto || o.destino)}</a>`;
    }
    if (typeof o.texto === 'string') {
        return `<span class="m">⏳</span>${esc(o.texto)}${o.cuando ? ` <span class="dim">(${esc(String(o.cuando))})</span>` : ''}`;
    }
    if (typeof o.que === 'string') {
        return `<span class="m">·</span><span class="dim">${esc(String(o.cuando ?? ''))}</span> ${esc(o.que)}`;
    }
    return `<span class="m">·</span>${esc(Object.entries(o).map(([k, x]) => `${k}: ${x}`).join(' · '))}`;
}

/** Abre un archivo al lado, y si se dice qué línea buscar, la deja a la vista. */
async function abrir(archivo: string, buscar?: string): Promise<void> {
    const doc = await vscode.workspace.openTextDocument(archivo);
    const editor = await vscode.window.showTextDocument(doc, { viewColumn: vscode.ViewColumn.Beside, preview: true });
    if (!buscar) return;
    const aguja = buscar.trim().slice(0, 40);
    for (let i = 0; i < doc.lineCount; i++) {
        if (!doc.lineAt(i).text.includes(aguja)) continue;
        const donde = new vscode.Range(i, 0, i, 0);
        editor.selection = new vscode.Selection(donde.start, donde.start);
        editor.revealRange(donde, vscode.TextEditorRevealType.InCenter);
        return;
    }
}
