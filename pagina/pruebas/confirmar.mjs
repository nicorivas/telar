// Prueba de las confirmaciones: «la tecla en el pie» (componentes/boton.ts, sus teclas en web/botonera.ts) en todas.
// · `preguntar` (web/interfaz.ts; ui.aviso con botones): lo que destruye va en el de peligro con ⌘⌫ y abre con el foco en
//   «cancelar», así que ⏎ cancela; lo que no, con ⏎ y el foco en lo que hace; lo que pide mirar, el foco en cancelar y
//   ⌘⏎; varias acciones, 1 2 3; la tecla de cada celda la aprieta; una sostenida no; ⎋ cancela; cancelar, al último.
// · escribir: ⌘⏎ envía desde el área. Una franja que no es ventana (soltar en la terminal): ⎋ aprieta su «no».
// · Cada confirmación de la página: la que dice un verbo que destruye lo pide (`destruye: true`); cada archivo con una
//   está en el catastro del catálogo (componentes/catalogo-botones.ts), para que ninguna quede sin decidir; y las que no
//   pasan por `preguntar` (contestar, la instrucción, la mudanza, soltar, quitar una cuenta, el eliminar de agentes)
//   usan los botones y sus teclas. El botón: lo que destruye nunca dice ⏎, y el foco se marca con `:focus`.
// Corre en Node, con un DOM mínimo hecho aquí (lo que usan abrirVentana, web/ventana.ts, y web/botonera.ts):
// npm run prueba:confirmar
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const src = path.join(aqui, '..', 'src');
const css = n => readFileSync(path.join(aqui, '..', 'media', 'css', `${n}.css`), 'utf8');

// ── un DOM mínimo: un árbol de verdad (lo que se escribe en innerHTML se lee en nodos), eventos que suben hasta window,
//    foco, <dialog> y los selectores simples (tag.clase[data-x="y"], separados por comas) ──
const VACIOS = new Set(['input', 'br', 'img', 'hr', 'meta']);
class Nodo {
    constructor(tag = '') {
        this.tagName = tag.toUpperCase(); this.children = []; this.parentElement = null; this.oyentes = {}; this.style = { setProperty() {} };
        this.atributos = {}; this.dataset = {}; this.texto = ''; this.open = false; this.disabled = false; this.value = '';
        this.tabIndex = ['BUTTON', 'INPUT', 'TEXTAREA', 'SELECT'].includes(this.tagName) ? 0 : -1;
    }
    get className() { return this.atributos.class ?? ''; }
    set className(c) { this.atributos.class = c; }
    get textContent() { return this.texto + this.children.map(c => c.textContent).join(''); }
    set textContent(t) { this.children = []; this.texto = t; }
    appendChild(n) { n.parentElement?.children.splice(n.parentElement.children.indexOf(n), 1); n.parentElement = this; this.children.push(n); return n; }
    append(...ns) { for (const n of ns) this.appendChild(n); }
    remove() { if (this.parentElement) { this.parentElement.children.splice(this.parentElement.children.indexOf(this), 1); this.parentElement = null; } }
    addEventListener(tipo, fn, captura) { (this.oyentes[tipo] ??= []).push(fn); void captura; }
    removeEventListener(tipo, fn) { this.oyentes[tipo] = (this.oyentes[tipo] ?? []).filter(f => f !== fn); }
    getBoundingClientRect() { return { left: 0, right: 100, top: 0, bottom: 100, width: 100, height: 100 }; }
    showModal() { this.open = true; }
    show() { this.open = true; }
    close() { this.open = false; }
    focus() { documento.activeElement = this; }
    select() {}
    click() { if (!this.disabled) disparar(this, { type: 'click', detail: 1 }); }
    set innerHTML(h) {
        this.children = []; this.texto = '';
        let actual = this;
        for (const m of h.matchAll(/<(\/?)([a-zA-Z][\w-]*)([^>]*?)(\/?)>|([^<]+)/g)) {
            if (m[5] !== undefined) { const t = new Nodo('#text'); t.texto = m[5].replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&amp;/g, '&'); actual.appendChild(t); continue; }
            if (m[1]) { actual = actual.parentElement ?? this; continue; }
            const n = new Nodo(m[2]);
            for (const at of m[3].matchAll(/([\w-]+)(?:="([^"]*)")?/g)) {
                const v = (at[2] ?? '').replace(/&quot;/g, '"').replace(/&amp;/g, '&');
                n.atributos[at[1]] = v;
                if (at[1].startsWith('data-')) n.dataset[at[1].slice(5).replace(/-(\w)/g, (_, l) => l.toUpperCase())] = v;
                if (at[1] === 'tabindex') n.tabIndex = Number(v);
                if (at[1] === 'disabled') n.disabled = true;
            }
            actual.appendChild(n);
            if (!VACIOS.has(m[2].toLowerCase()) && !m[4]) actual = n;
        }
    }
    insertAdjacentHTML(_, h) { const tmp = new Nodo('div'); tmp.innerHTML = h; for (const c of [...tmp.children]) this.appendChild(c); }
    get lastElementChild() { return this.children.filter(c => c.tagName !== '#TEXT').at(-1) ?? null; }
    get firstElementChild() { return this.children.find(c => c.tagName !== '#TEXT') ?? null; }
    todos() { return this.children.flatMap(c => [c, ...c.todos()]); }
    matches(sel) { return sel.split(',').some(t => calza(this, t.trim())); }
    querySelectorAll(sel) { return this.todos().filter(n => n.tagName !== '#TEXT' && n.matches(sel)); }
    querySelector(sel) { return this.querySelectorAll(sel)[0] ?? null; }
    closest(sel) { for (let n = this; n && n.tagName; n = n.parentElement) if (n.tagName !== '#TEXT' && n.matches(sel)) return n; return null; }
    contains(n) { for (; n; n = n.parentElement) if (n === this) return true; return false; }
}
/** Un selector simple: tag, .clase, [atributo] o [atributo="valor"], juntos (sin combinadores). */
function calza(n, sel) {
    const m = sel.match(/^([a-zA-Z]*)((?:\.[\w-]+)*)((?:\[[^\]]+\])*)$/);
    if (!m) return false;
    if (m[1] && n.tagName !== m[1].toUpperCase()) return false;
    const clases = n.className.split(/\s+/);
    if (m[2] && !m[2].split('.').filter(Boolean).every(c => clases.includes(c))) return false;
    for (const a of m[3].matchAll(/\[([\w-]+)(?:="([^"]*)")?\]/g)) {
        if (a[1] === 'tabindex') { if (n.tabIndex < 0) return false; continue; }
        if (!(a[1] in n.atributos)) return false;
        if (a[2] !== undefined && n.atributos[a[1]] !== a[2]) return false;
    }
    return true;
}
const ventana = new Nodo('#window');
const documento = new Nodo('#document');
documento.body = new Nodo('body');
documento.appendChild(documento.body);
documento.parentElement = ventana;
documento.activeElement = documento.body;
documento.createElement = tag => new Nodo(tag);
/** Un evento que sube del blanco hasta window, como en el navegador; `stopPropagation` lo para; `stopImmediatePropagation`,
 *  también a los oyentes que siguen en el mismo nodo. */
function disparar(blanco, datos) {
    let parado = false, ya = false;
    const e = { metaKey: false, ctrlKey: false, altKey: false, shiftKey: false, repeat: false, isComposing: false, ...datos, target: blanco, defaultPrevented: false,
        preventDefault() { this.defaultPrevented = true; }, stopPropagation() { parado = true; }, stopImmediatePropagation() { parado = true; ya = true; } };
    for (let n = blanco; n && !parado; n = n.parentElement) for (const fn of [...(n.oyentes[e.type] ?? [])]) { if (ya) break; fn(e); }
    return e;
}
globalThis.document = documento;
globalThis.window = ventana;
globalThis.HTMLElement = Nodo;

/** Lo que contesta la ventana; si no contesta, falla en vez de quedarse esperando. */
const contesta = r => Promise.race([r, new Promise((_, no) => setTimeout(() => no(new Error('la ventana no contestó')), 500))]);
const sigueAbierta = async r => { const x = await Promise.race([r.then(() => 'cerró'), new Promise(ok => setTimeout(() => ok('abierta'), 30))]); return x === 'abierta'; };
const abierta = () => documento.body.children.find(n => n.tagName === 'DIALOG' && n.open);
const tecla = (key, o = {}) => disparar(documento.activeElement, { type: 'keydown', key, ...o });
const botones = () => abierta().querySelectorAll('button.boton');
const enFoco = () => documento.activeElement;
// lo que la página haría con una tecla que se le escapa a la ventana (el dashboard abre lo marcado)
const escapados = [];
ventana.addEventListener('keydown', e => escapados.push(e.key));

const dir = mkdtempSync(path.join(tmpdir(), 'confirmar-'));
const entrada = path.join(dir, 'entrada.ts');
writeFileSync(entrada, [
    `export { preguntar, escribir, botonesDeAviso } from ${JSON.stringify(path.join(src, 'web', 'interfaz.ts'))};`,
    `export { teclasDeBotones, teclaDelEvento } from ${JSON.stringify(path.join(src, 'web', 'botonera.ts'))};`,
    `export { boton, pieBotones, teclaDe, cancelar, DESTRUYE } from ${JSON.stringify(path.join(src, 'componentes', 'boton.ts'))};`,
    `export { CONFIRMACIONES } from ${JSON.stringify(path.join(src, 'componentes', 'catalogo-botones.ts'))};`,
].join('\n'));
const salida = path.join(dir, 'confirmar.cjs');
await build({ entryPoints: [entrada], bundle: true, platform: 'node', format: 'cjs', outfile: salida, logLevel: 'warning' });
const B = require(salida);

// 1. lo que destruye: en el de peligro con ⌘⌫ (nunca ⏎), cancelar al último con ⎋; abre con el foco en «cancelar», y ⏎ cancela
//    (sin que siga de largo a la página)
{
    const r = B.preguntar('¿Borrar el estilo «tinta»?', ['Borrar'], { destruye: true });
    assert.ok(abierta(), 'la ventana se abre');
    assert.ok(abierta().querySelector('div.botonera'), 'el pie es la banda de botones');
    const [borrar, cancelar] = botones();
    assert.deepEqual([borrar.dataset.tecla, cancelar.dataset.tecla], ['⌘⌫', '⎋'], 'lo que destruye, con ⌘⌫; cancelar, con ⎋');
    assert.match(borrar.className, /tono-peligro/, 'en el de peligro');
    assert.match(cancelar.className, /tono-callado/, 'cancelar, en el del texto');
    assert.equal(borrar.textContent, '⌘⌫borrar', 'la tecla y la palabra, en minúscula');
    assert.equal(enFoco(), cancelar, 'el foco parte en «cancelar»');
    const e = tecla('Enter');
    assert.equal(await contesta(r), undefined, '⏎ cancela');
    assert.ok(e.defaultPrevented, 'el ⏎ no escribe nada');
    assert.equal(abierta(), undefined, 'la ventana se cierra');
    assert.deepEqual(escapados, [], 'el ⏎ no sigue a la página');
}

// 2. su acorde lo hace, tenga o no el foco; sostenido (viene de antes de abrirse), no
{
    const r = B.preguntar('¿Quitar el módulo?', ['Quitar'], { destruye: true });
    tecla('Backspace', { metaKey: true, repeat: true });
    assert.ok(await sigueAbierta(r), 'un ⌘⌫ sostenido no hace nada');
    tecla('Enter', { repeat: true });
    assert.ok(await sigueAbierta(r), 'un ⏎ sostenido tampoco (ni cancela)');
    tecla('Backspace');
    assert.ok(await sigueAbierta(r), '⌫ solo no es el acorde');
    tecla('Backspace', { metaKey: true });
    assert.equal(await contesta(r), 'Quitar', '⌘⌫ lo hace, con el foco en «cancelar»');
    assert.deepEqual(escapados, ['Backspace'], 'las de los botones no siguen a la página (⌫ solo, que no es de ninguno, sí)');
    escapados.length = 0;
}

// 3. con el foco en «cancelar», hacerlo con ⏎ es a propósito: pasando a él (⇥ los alcanza a todos) y ⏎; o con un clic
{
    const r = B.preguntar('¿Descartar «faro»?', ['Descartar'], { destruye: true });
    const bs = botones();
    assert.deepEqual(bs.map(b => [b.textContent, b.tabIndex]), [['⌘⌫descartar', 0], ['⎋cancelar', 0]], 'todos se alcanzan con ⇥');
    bs[0].focus();
    tecla('Enter');
    assert.equal(await contesta(r), 'Descartar', '⏎ hace el que tiene el foco');
    const r2 = B.preguntar('¿Descartar «faro»?', ['Descartar'], { destruye: true });
    botones()[0].click();
    assert.equal(await contesta(r2), 'Descartar', 'un clic lo hace');
}

// 4. lo que no destruye: el foco en lo que hace, con ⏎, y ⏎ lo hace; sostenido, no
{
    const r = B.preguntar('¿Instalar telar 9.9?', ['Instalar']);
    const [instalar] = botones();
    assert.equal(instalar.dataset.tecla, '⏎', 'la acción sola, con ⏎');
    assert.match(instalar.className, /tono-accion/);
    assert.equal(enFoco(), instalar, 'el foco parte en lo que hace');
    tecla('Enter', { repeat: true });
    assert.ok(await sigueAbierta(r), 'un ⏎ sostenido no lo hace');
    tecla('Enter');
    assert.equal(await contesta(r), 'Instalar', '⏎ hace el que tiene el foco');
}

// 5. lo que pide mirar (conceder un permiso para siempre): el foco en cancelar, sin rojo; con varias acciones, 1 2 3
{
    const r = B.preguntar('El módulo «x» pide leer tus chats.', ['Permitir siempre', 'Solo esta vez', 'No'], { foco: 'cancelar' });
    const bs = botones();
    assert.deepEqual(bs.map(b => b.dataset.tecla), ['1', '2', '3', '⎋'], 'cada acción con su número; cancelar con ⎋');
    assert.ok(bs.every(b => !/tono-peligro/.test(b.className)), 'nada en rojo: no destruye');
    assert.equal(enFoco(), bs[3], 'el foco en «cancelar»');
    tecla('Enter');
    assert.equal(await contesta(r), undefined, '⏎ cancela');
    const r2 = B.preguntar('El módulo «x» pide leer tus chats.', ['Permitir siempre', 'Solo esta vez', 'No'], { foco: 'cancelar' });
    tecla('2');
    assert.equal(await contesta(r2), 'Solo esta vez', 'su número la hace');
    const r3 = B.preguntar('¿Uso Claude Code?', ['Usar Claude Code'], { foco: 'cancelar' });
    assert.equal(botones()[0].dataset.tecla, '⌘⏎', 'una sola, con el foco en cancelar: ⌘⏎ (⏎ es del foco)');
    tecla('Enter', { metaKey: true });
    assert.equal(await contesta(r3), 'Usar Claude Code');
    const r4 = B.preguntar('Tiene hilos hijos: ¿se archivan también?', ['Con sus hijos', 'Solo él']);
    assert.deepEqual(botones().map(b => b.dataset.tecla), ['1', '2', '⎋']);
    assert.equal(enFoco(), botones()[0], 'el foco en la primera');
    tecla('Enter');
    assert.equal(await contesta(r4), 'Con sus hijos');
}

// 6. ⎋ (el `cancel` del <dialog>) cancela; una letra no hace nada
{
    const r = B.preguntar('¿Descartar «faro»?', ['Descartar'], { destruye: true });
    tecla('a');
    assert.ok(abierta(), 'una letra no la cierra');
    disparar(abierta(), { type: 'cancel' });
    assert.equal(await contesta(r), undefined, '⎋ cancela');
}

// 7. escribir: «⌘⏎ enviar · ⎋ cancelar»; ⌘⏎ desde el área envía lo escrito; ⏎ es una línea más
{
    const r = B.escribir({ titulo: 'a Secretaría' });
    const area = abierta().querySelector('textarea');
    assert.deepEqual(botones().map(b => b.dataset.tecla), ['⌘⏎', '⎋']);
    assert.equal(enFoco(), area, 'el foco en el área');
    area.value = 'hola';
    tecla('Enter');
    assert.ok(await sigueAbierta(r), '⏎ no envía');
    tecla('Enter', { metaKey: true });
    assert.deepEqual(await contesta(r), { texto: 'hola', destino: '' }, '⌘⏎ envía, aunque se esté escribiendo');
}

// 8. una franja que no es ventana (soltar en la terminal): ⎋ aprieta su «no»; ⏎, el del foco
{
    const franja = new Nodo('div');
    documento.body.appendChild(franja);
    franja.innerHTML = `<div class="botonera">${B.boton({ texto: 'guardar', datos: { soltar: 'si' }, tecla: '⏎' })}${B.boton({ ...B.cancelar('no', null), datos: { soltar: 'no' } })}</div>`;
    const dejar = B.teclasDeBotones(franja);
    const hechos = [];
    for (const b of franja.querySelectorAll('button')) b.addEventListener('click', () => hechos.push(b.dataset.soltar));
    franja.querySelector('[data-soltar="si"]').focus();
    tecla('Escape');
    tecla('Enter');
    assert.deepEqual(hechos, ['no', 'si'], '⎋ es su «no»; ⏎, el del foco');
    dejar();
    franja.remove();
}

// ── 9. el botón: lo que destruye nunca dice ⏎; el foco se marca con :focus, y el contenido no se pega a la banda ──
assert.equal(B.teclaDe({ tono: 'peligro', tecla: '⏎' }), '⌘⌫', 'un botón de peligro con ⏎ pasa a ⌘⌫');
assert.match(B.boton({ texto: 'Borrar', tono: 'peligro', tecla: '⏎' }), /data-tecla="⌘⌫"[^>]*>.*>borrar</);
for (const tono of ['peligro', 'accion', 'callado']) assert.match(B.boton({ texto: 'x', tono }), new RegExp(`^<button type="button" class="boton tono-${tono}"`));
assert.doesNotMatch(css('boton'), /:focus-visible/, 'boton.css no marca el foco con :focus-visible (no se ve si se abrió con un clic)');
assert.match(css('boton'), /:not\(:disabled\):focus, &\.es-foco \{ background:/, 'el foco: su color tenue en la celda');
assert.match(css('boton'), /\.botonera \{[^}]*margin-top: var\(--boton-pie-aire\);[^}]*border-top: var\(--borde\);/s, 'la banda: su aire y su línea');
assert.match(css('tokens'), /--boton-pie-aire: var\(--e-3\);/, 'el aire entre el contenido y la banda: una línea');
assert.ok(B.DESTRUYE.test('Borrar') && B.DESTRUYE.test('descartar') && B.DESTRUYE.test('Cancelar el encargo') && !B.DESTRUYE.test('Archivar'));

// ── 10. cada confirmación de la página (ui.aviso/info/falla con botones): la que dice un verbo que destruye lo pide; las
//    que vienen de afuera (una acción de tarea u objeto), según su verbo; y cada archivo con una, en el catastro ──
const archivos = [];
const recorrer = d => { for (const n of readdirSync(d)) { const p = path.join(d, n); if (statSync(p).isDirectory()) recorrer(p); else if (p.endsWith('.ts')) archivos.push(p); } };
recorrer(src);
/** Cada llamada a `ui.<función>(…)` de un texto sin comentarios: su texto entero y sus argumentos de arriba. */
function llamadas(texto, funcion) {
    const out = [];
    for (let i = texto.indexOf(`ui.${funcion}(`); i >= 0; i = texto.indexOf(`ui.${funcion}(`, i + 1)) {
        let hondo = 1, j = i + funcion.length + 4, cita = null;
        const args = []; let actual = '';
        for (; j < texto.length && hondo; j++) {
            const ch = texto[j];
            if (cita) { actual += ch; if (ch === cita && texto[j - 1] !== '\\') cita = null; continue; }
            if (ch === '\'' || ch === '"' || ch === '`') { cita = ch; actual += ch; continue; }
            if ('([{'.includes(ch)) hondo++;
            if (')]}'.includes(ch)) hondo--;
            if (hondo === 0) break;
            if (ch === ',' && hondo === 1) { args.push(actual.trim()); actual = ''; continue; }
            actual += ch;
        }
        args.push(actual.trim());
        out.push({ texto: texto.slice(i, j + 1), args });
    }
    return out;
}
const sinComentarios = t => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/.*$/gm, '$1');
const enCatastro = new Set(B.CONFIRMACIONES.map(c => c.archivo));
const conConfirmacion = new Set();
let destructivas = 0, todas = 0;
for (const p of archivos) {
    const rel = path.relative(src, p);
    if (rel === 'web/ui.ts' || rel === 'web/ensayo-confirmar.ts') continue;
    const texto = sinComentarios(readFileSync(p, 'utf8'));
    for (const f of ['aviso', 'info', 'falla']) for (const ll of llamadas(texto, f)) {
        const botonesDe = ll.args.slice(1).filter(a => a && !a.startsWith('{'));
        if (!botonesDe.length) continue;
        todas++;
        conConfirmacion.add(rel);
        const opciones = ll.args.slice(1).find(a => a.startsWith('{')) ?? '';
        const literales = botonesDe.flatMap(a => [...a.matchAll(/'([^']+)'/g)].map(m => m[1]));
        if (literales.some(b => B.DESTRUYE.test(b)) || /destruye: true/.test(opciones)) {
            destructivas++;
            assert.match(opciones, /destruye: true/, `${rel}: lo que destruye lo pide (destruye: true):\n${ll.texto}`);
        }
        // un botón que no se sabe (el nombre de una acción que viene de afuera): el foco en cancelar, y peligro según su verbo
        if (botonesDe.some(a => /\.nombre$/.test(a))) assert.match(opciones, /foco: 'cancelar', destruye: DESTRUYE\.test\(/, `${rel}: una acción de afuera:\n${ll.texto}`);
        // y los que la variable dice (borrar o volver un modo, borrar un mundo, descartar un retenido)
        if (botonesDe.some(a => /^(boton|p\.boton)$/.test(a))) assert.match(opciones, /destruye: true/, `${rel}: ${ll.texto}`);
    }
}
assert.ok(todas >= 30, `se encontraron las confirmaciones (${todas})`);
assert.ok(destructivas >= 14, `se encontraron las que destruyen (${destructivas})`);
for (const a of conConfirmacion) assert.ok(enCatastro.has(a), `${a} tiene una confirmación que no está en el catastro (componentes/catalogo-botones.ts, CONFIRMACIONES): decide si destruye`);
for (const c of B.CONFIRMACIONES) assert.ok(['destruye', 'mira', 'hace'].includes(c.clase), `${c.archivo}: su clase`);

// ── 11. las que no pasan por `preguntar` ──
const leer = p => sinComentarios(readFileSync(path.join(src, p), 'utf8'));
{
    // abrirVentana pone las teclas de los botones en cada ventana, antes que las de quien la usa
    const v = leer('web/ventana.ts');
    assert.ok(v.indexOf('teclasDeBotones(d)') > 0 && v.indexOf('teclasDeBotones(d)') < v.indexOf('o.montar?.(d, cerrar)'), 'abrirVentana: las teclas de los botones, antes que montar');
    // pieVentana es la banda
    assert.match(leer('componentes/ventana.ts'), /pieVentana = \(acciones: Boton\[\]\): string => pieBotones\(acciones\)/);
    // contestar: su botón, en el de peligro con ⌘⌫ si quita, y ⏎ no lo hace (la prueba de su HTML, en prueba:contestar)
    assert.match(leer('componentes/contestar.ts'), /tono: destruye \? 'peligro' : 'accion', tecla: destruye \? '⌘⌫' : '⏎'/);
    assert.match(leer('web/contestar.ts'), /ev\.preventDefault\(\);\s*if \(quita\(c, s\)\) return;\s*void mandar\(\);/, 'contestar: ⏎ no hace lo que quita');
    // la instrucción: «⌘⏎ mandar · ⎋ cancelar», y sus teclas
    const ins = leer('web/instruccion.ts');
    assert.match(ins, /boton\(\{ texto: 'mandar', tecla: '⌘⏎'/);
    assert.match(ins, /teclasDeBotones\(c\)/);
    assert.doesNotMatch(ins, /'⌘⏎ mandar'|'⎋ cancelar'/, 'la instrucción: sin los <a> de antes');
    // la mudanza: «⏎ llevar igual · ⎋ no llevarlo» (antes, en rojo); ⎋ aprieta su botón de ⎋
    const mu = leer('web/mudanza.ts');
    assert.match(mu, /texto: 'llevar igual', color: C\.hecho, tecla: '⏎'/);
    assert.match(mu, /cancelar\('no llevarlo', null\)/);
    assert.match(mu, /teclasDeBotones\(c\)/);
    assert.match(mu, /addEventListener\('cancel', e => \{ e\.preventDefault\(\); botones\.querySelector<HTMLElement>\('\[data-tecla="⎋"\]'\)\?\.click\(\); \}\)/);
    assert.doesNotMatch(mu, /C\.quitar/, 'la mudanza: nada en rojo (no llevarlo es cancelar)');
    // soltar en la terminal: «⏎ guardar · ⎋ no», y sus teclas
    const te = leer('web/terminal.ts');
    assert.match(te, /boton\(\{ texto: 'guardar', datos: \{ soltar: 'si' \}[^)]*tecla: '⏎'/);
    assert.match(te, /teclasDeBotones\(franja\)/);
    // quitarle la cuenta a alguien: una confirmación que destruye (antes, un «elegir» con el «no» marcado)
    assert.match(leer('vistas/dashboard/config/personas.ts'), /ui\.aviso\(`¿Quitarle la cuenta a \$\{nombre\}\?`, 'Quitar la cuenta',[^)]*destruye: true/);
    // el eliminar de agentes: en el de peligro de verdad
    assert.match(leer('vistas/dashboard/agentes.ts'), /boton\(\{ texto: 'eliminar', accion: 'agente-eliminar', valor: a\.clave, tono: 'peligro'/);
    // el pulso: «⎋ listo», callado
    assert.match(leer('componentes/pulso.ts'), /pieVentana\(\[\{ texto: 'listo', tecla: '⎋', accion: 'listo', tono: 'callado' \}\]\)/);
}

// 12. descartar un hilo vivo pregunta: ningún camino lo termina sin pasar por descartar()
{
    const ordenes = leer('web/ordenes.ts');
    assert.doesNotMatch(ordenes, /sacar\(\w+, 'cerrar'/, 'sacar(…, \'cerrar\') solo desde descartar(), que pregunta');
    assert.match(ordenes, /'telar\.cerrar': a => descartar\(/, 'la ✕ de la fila de un hilo vivo pregunta');
    assert.match(ordenes, /Está vivo/, 'la pregunta dice que está vivo');
}

console.log(`confirmar: ok (${todas} confirmaciones, ${destructivas} destruyen)`);
