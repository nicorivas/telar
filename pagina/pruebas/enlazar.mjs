// Prueba de `enlazar` (src/web/rutas-agente.ts) con lo que ya se dibujó: los tipos de dirección de los módulos llegan
// después (/api/objetos/tipos), y lo que se enlazó antes de que llegaran (la primera vista de un objeto) se vuelve a
// enlazar cuando llegan, sin repetir lo que ya era enlace. Corre en Node, con un DOM mínimo hecho aquí (lo único que
// usa `enlazar`) y lo demás de la página de mentira: npm run prueba:enlazar
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));

// ── un DOM mínimo: nodos de texto, elementos, fragmentos y un TreeWalker de los textos ──
class Nodo {
    constructor() { this.parentNode = null; this.childNodes = []; }
    get parentElement() { return this.parentNode instanceof Elemento ? this.parentNode : null; }
    get isConnected() { let n = this; while (n.parentNode) n = n.parentNode; return n === documento; }
    get textContent() { return this.childNodes.map(c => c.textContent).join(''); }
    /** Pone `n` antes de `antes` (al final, sin él); un fragmento pone sus hijos. */
    poner(n, antes = null) {
        if (n instanceof Fragmento) { for (const c of [...n.childNodes]) this.poner(c, antes); return; }
        n.remove();
        n.parentNode = this;
        const i = antes ? this.childNodes.indexOf(antes) : -1;
        this.childNodes.splice(i < 0 ? this.childNodes.length : i, 0, n);
    }
    append(...xs) { for (const x of xs) this.poner(typeof x === 'string' ? new Texto(x) : x); }
    remove() { if (this.parentNode) { this.parentNode.childNodes.splice(this.parentNode.childNodes.indexOf(this), 1); this.parentNode = null; } }
    replaceWith(...xs) { const p = this.parentNode; for (const x of xs) p.poner(typeof x === 'string' ? new Texto(x) : x, this); this.remove(); }
    *descendientes() { for (const c of this.childNodes) { yield c; yield* c.descendientes(); } }
}
class Texto extends Nodo {
    constructor(data) { super(); this.data = data; }
    get textContent() { return this.data; }
}
class Fragmento extends Nodo {}
class Elemento extends Nodo {
    constructor(tag) {
        super(); this.tagName = tag.toUpperCase(); this.atributos = {}; this.dataset = {}; this.title = ''; this.className = '';
        this.classList = { add: c => { this.className = `${this.className} ${c}`.trim(); } };
    }
    get textContent() { return super.textContent; }
    set textContent(t) { for (const c of [...this.childNodes]) c.remove(); this.append(t); }
    get href() { return this.atributos.href ?? ''; }
    set href(v) { this.atributos.href = v; }
    getAttribute(k) { return this.atributos[k] ?? null; }
    removeAttribute(k) { delete this.atributos[k]; }
    /** Solo selectores de etiquetas: `a`, `code, pre`. */
    closest(sel) {
        const tags = sel.split(',').map(s => s.trim().toUpperCase());
        for (let n = this; n instanceof Elemento; n = n.parentNode) if (tags.includes(n.tagName)) return n;
        return null;
    }
    /** Solo el que usa `enlazar`: `a[href^="http://"]`. */
    querySelectorAll(sel) {
        assert.equal(sel, 'a[href^="http://"]');
        return [...this.descendientes()].filter(n => n.tagName === 'A' && (n.getAttribute('href') ?? '').startsWith('http://'));
    }
}
const documento = new Nodo();
documento.body = new Elemento('body');
documento.poner(documento.body);
documento.createElement = tag => new Elemento(tag);
documento.createDocumentFragment = () => new Fragmento();
documento.createTreeWalker = (raiz, _que, filtro) => {
    const textos = [...raiz.descendientes()].filter(n => n instanceof Texto && filtro.acceptNode(n) === NodeFilter.FILTER_ACCEPT);
    return { nextNode: () => textos.shift() ?? null };
};
globalThis.document = documento;
globalThis.NodeFilter = { SHOW_TEXT: 4, FILTER_ACCEPT: 1, FILTER_REJECT: 2, FILTER_SKIP: 3 };
globalThis.HTMLElement = Elemento;

/** Un elemento con sus hijos (texto o elementos). */
const el = (tag, ...hijos) => { const e = new Elemento(tag); e.append(...hijos); return e; };
/** Los enlaces de `raiz`, como «direccion decision:casa/D-001» o «ruta docs/x.md». */
const enlaces = raiz => [...raiz.descendientes()].filter(n => n.tagName === 'A')
    .map(a => (a.dataset.direccion ? `direccion ${a.dataset.direccion}` : a.dataset.ruta ? `ruta ${a.dataset.ruta}` : `web ${a.href}`));

// ── /api/objetos/tipos, de mentira: contesta cuando la prueba lo suelta ──
const pedidos = [];
let soltar;
globalThis.fetch = url => {
    pedidos.push(url);
    return new Promise(r => { soltar = tipos => r({ ok: true, json: async () => ({ tipos: tipos.map(tipo => ({ tipo })) }) }); });
};
const TIPOS = ['archivo', 'hilo', 'proyecto', 'tarea', 'decision'];
const llegan = async () => { soltar(TIPOS); for (let i = 0; i < 5; i++) await new Promise(r => setImmediate(r)); };

// rutas-agente.ts, con lo demás de la página de mentira (la API, el modelo, la hoja de códigos, el visor)
const MENTIRA = {
    '../cli': 'export const espejos = async () => ({});',
    '../modelo': 'export const modelo = { porNombre: () => undefined, aqui: "" };',
    './codigos': 'export const conocidos = () => undefined; export const queEs = () => "";',
    './lado': 'export const abrirCodigo = () => {};',
    './ui': 'export const abrirArchivo = async () => {}; export const abrirDireccion = async () => {}; export const abrirExterno = async () => {};',
};
const salida = path.join(mkdtempSync(path.join(tmpdir(), 'enlazar-')), 'rutas-agente.cjs');
await build({
    entryPoints: [path.join(aqui, '..', 'src', 'web', 'rutas-agente.ts')], bundle: true, platform: 'node', format: 'cjs',
    outfile: salida, logLevel: 'warning',
    plugins: [{ name: 'mentira', setup(b) {
        b.onResolve({ filter: /^(\.\.\/cli|\.\.\/modelo|\.\/codigos|\.\/lado|\.\/ui)$/ }, a => ({ path: a.path, namespace: 'mentira' }));
        b.onLoad({ filter: /.*/, namespace: 'mentira' }, a => ({ contents: MENTIRA[a.path], loader: 'ts' }));
    } }],
});
const { enlazar } = require(salida);

// 1. la primera vista de un objeto, antes de que lleguen los tipos: la dirección de un tipo de telar es enlace, la de un
// tipo de un módulo todavía no; los tipos se piden una vez
const resumen = el('div', el('p', 'Sale de decision:casa/D-001, en archivo:docs/x.md.'));
const campos = el('div', el('code', 'decision:casa/D-002'));
const vista = el('section', resumen, campos);
documento.body.append(vista);
enlazar(resumen, false);
enlazar(campos, false);
assert.deepEqual(enlaces(resumen), ['direccion archivo:docs/x.md'], 'sin los tipos del módulo, decision: es texto');
assert.deepEqual(enlaces(campos), []);
assert.deepEqual(pedidos, ['/api/objetos/tipos'], 'los tipos se piden una vez');

// 2. una vista que se cerró antes de que llegaran (otro objeto la reemplazó): no se toca
const cerrada = el('div', 'de decision:casa/D-009');
documento.body.append(cerrada);
enlazar(cerrada, false);
cerrada.remove();

// 3. llegan los tipos: lo que ya se dibujó se vuelve a enlazar, sin repetir lo que ya era enlace
await llegan();
assert.deepEqual(enlaces(resumen), ['direccion decision:casa/D-001', 'direccion archivo:docs/x.md'], 'decision: es enlace al llegar los tipos');
assert.equal(resumen.textContent, 'Sale de decision:casa/D-001, en archivo:docs/x.md.', 'el texto queda igual');
assert.deepEqual(enlaces(campos), ['direccion decision:casa/D-002'], 'también en un campo (dentro de un code)');
assert.deepEqual(enlaces(cerrada), [], 'la vista cerrada no');

// 4. después, una vista nueva se enlaza con los tipos del módulo al tiro, sin volver a pedirlos
const otra = el('div', 'y decision:casa/D-003 con docs/y.md');
documento.body.append(otra);
enlazar(otra);
assert.deepEqual(enlaces(otra), ['direccion decision:casa/D-003', 'ruta docs/y.md']);
assert.deepEqual(pedidos, ['/api/objetos/tipos'], 'no se vuelven a pedir');

console.log('enlazar: bien');
