// Prueba de la ventana de mundos (⌘M, el clic en el mundo de la banda, «cambiar de mundo» en ⌘K) y del arte de sus tarjetas:
// 1. El contrato del arte (componentes/arte.ts): registrar uno, el lienzo de cada cuadro (siempre ANCHO × ALTO, el mismo
//    instante da el mismo cuadro), los de fábrica, un arte escrito en un archivo (`leerArteTexto`: la cabecera, los cuadros,
//    la escena de hover, lo que no se entiende), los de la raíz que tapan a uno de fábrica y lo devuelven al irse, qué
//    arte lleva cada mundo (`arteDeMundo`) y el efecto de hover (la ola: sobre cualquier arte, salvo el que declara el
//    suyo).
// 2. Lo que dicen las tarjetas (componentes/mundos-ventana.ts): el horario, la de ahora y por qué, la que viene, ambos, las
//    teclas (también 10, 11…), la grilla y sus columnas (hasta cuatro en una fila; más, de a tres hacia abajo), el pie; y
//    el planeta delante del nombre en la banda.
// 3. La ventana viva (web/mundos-ventana.ts), con un DOM mínimo hecho aquí: abre con el foco en la de ahora, las flechas, los
//    números, ⏎, «volver al horario» (h, apagado si ya rige), ⎋, ⌘M que abre y cierra; elegir pone ese mundo (web/mundo.ts).
//    Con diez mundos: al abrir, la de ahora a la vista; la del foco siempre a la vista (suave, o de golpe con «reducir
//    movimiento»); 1 y 1 es la 11, y 1 sola, la 1.
// 4. El arte vivo (web/arte-vivo.ts), con un requestAnimationFrame de mentira: anima solo con la ventana abierta y la
//    pestaña a la vista (cerrada, ningún cuadro pedido), acelera con el mouse o el foco encima, con «reducir movimiento» no
//    pide ninguno y deja el primer cuadro, y un arte que llega con la ventana abierta (uno nuevo de la raíz) se toma al tiro.
//    La ola pasa una vez al entrar y deja el cuadro como estaba; con un IntersectionObserver de mentira, solo anima lo que
//    se ve (y nada si no se ve ninguno).
// 5. El CSS (media/css/mundos.css): sin colores fijos ni esquinas redondeadas, sus tokens en tokens.css, «reducir
//    movimiento» sin animación, y en el marco de la página (scripts/navegador.mjs).
// Corre en Node: npm run prueba:mundos-ventana
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const src = path.join(aqui, '..', 'src');
const css = n => readFileSync(path.join(aqui, '..', 'media', 'css', `${n}.css`), 'utf8');

// ── un DOM mínimo: un árbol de verdad (lo que se escribe en innerHTML se lee en nodos), eventos que suben hasta window,
//    foco, <dialog>, classList y los selectores simples (tag.clase[data-x="y"], separados por comas) ──
const VACIOS = new Set(['input', 'br', 'img', 'hr', 'meta']);
const desescapar = t => t.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&amp;/g, '&');
class Nodo {
    constructor(tag = '') {
        this.tagName = tag.toUpperCase(); this.children = []; this.parentElement = null; this.oyentes = {};
        const estilos = {};
        this.style = { setProperty: (k, v) => { estilos[k] = v; }, getPropertyValue: k => estilos[k] ?? '' };
        this.atributos = {}; this.dataset = {}; this.texto = ''; this.open = false; this.disabled = false; this.value = '';
        this.tabIndex = ['BUTTON', 'INPUT', 'TEXTAREA', 'SELECT'].includes(this.tagName) ? 0 : -1;
        this.classList = {
            contains: c => this.className.split(/\s+/).includes(c),
            add: (...cs) => { this.className = [...new Set([...this.className.split(/\s+/).filter(Boolean), ...cs])].join(' '); },
            remove: (...cs) => { this.className = this.className.split(/\s+/).filter(c => c && !cs.includes(c)).join(' '); },
            toggle: (c, si) => ((si ?? !this.classList.contains(c)) ? (this.classList.add(c), true) : (this.classList.remove(c), false)),
        };
    }
    get className() { return this.atributos.class ?? ''; }
    set className(c) { this.atributos.class = c; }
    get textContent() { return this.texto + this.children.map(c => c.textContent).join(''); }
    set textContent(t) { this.children = []; this.texto = t; }
    appendChild(n) { n.parentElement?.children.splice(n.parentElement.children.indexOf(n), 1); n.parentElement = this; this.children.push(n); return n; }
    append(...ns) { for (const n of ns) this.appendChild(n); }
    remove() { if (this.parentElement) { this.parentElement.children.splice(this.parentElement.children.indexOf(this), 1); this.parentElement = null; } }
    addEventListener(tipo, fn) { (this.oyentes[tipo] ??= []).push(fn); }
    removeEventListener(tipo, fn) { this.oyentes[tipo] = (this.oyentes[tipo] ?? []).filter(f => f !== fn); }
    getBoundingClientRect() { return { left: 0, right: 100, top: 0, bottom: 100, width: 100, height: 100 }; }
    scrollIntoView(o) { aLaVista.push({ el: this, ...o }); }
    showModal() { this.open = true; }
    show() { this.open = true; }
    close() { this.open = false; }
    focus() {
        const antes = documento.activeElement;
        if (antes === this) return;
        documento.activeElement = this;
        if (antes && antes !== documento.body) disparar(antes, { type: 'focusout', relatedTarget: this });
        disparar(this, { type: 'focusin', relatedTarget: antes });
    }
    click() { if (!this.disabled) disparar(this, { type: 'click', detail: 1 }); }
    set innerHTML(h) {
        this.children = []; this.texto = '';
        let actual = this;
        for (const m of h.matchAll(/<(\/?)([a-zA-Z][\w-]*)([^>]*?)(\/?)>|([^<]+)/g)) {
            if (m[5] !== undefined) { const t = new Nodo('#text'); t.texto = desescapar(m[5]); actual.appendChild(t); continue; }
            if (m[1]) { actual = actual.parentElement ?? this; continue; }
            const n = new Nodo(m[2]);
            for (const at of m[3].matchAll(/([\w-]+)(?:="([^"]*)")?/g)) {
                const v = desescapar(at[2] ?? '');
                n.atributos[at[1]] = v;
                if (at[1].startsWith('data-')) n.dataset[at[1].slice(5).replace(/-(\w)/g, (_, l) => l.toUpperCase())] = v;
                if (at[1] === 'tabindex') n.tabIndex = Number(v);
                if (at[1] === 'disabled') n.disabled = true;
            }
            actual.appendChild(n);
            if (!VACIOS.has(m[2].toLowerCase()) && !m[4]) actual = n;
        }
    }
    get firstElementChild() { return this.children.find(c => c.tagName !== '#TEXT') ?? null; }
    todos() { return this.children.flatMap(c => [c, ...c.todos()]); }
    matches(sel) { return sel.split(',').some(t => calza(this, t.trim())); }
    querySelectorAll(sel) { return this.todos().filter(n => n.tagName !== '#TEXT' && n.matches(sel)); }
    querySelector(sel) { return this.querySelectorAll(sel)[0] ?? null; }
    closest(sel) { for (let n = this; n && n.tagName; n = n.parentElement) if (n.tagName !== '#TEXT' && n.matches(sel)) return n; return null; }
    contains(n) { for (; n; n = n.parentElement) if (n === this) return true; return false; }
}
function calza(n, sel) {
    const m = sel.match(/^([a-zA-Z]*)((?:\.[\w-]+)*)((?:\[[^\]]+\])*)$/);
    if (!m) return false;
    if (m[1] && n.tagName !== m[1].toUpperCase()) return false;
    const clases = n.className.split(/\s+/);
    if (m[2] && !m[2].split('.').filter(Boolean).every(c => clases.includes(c))) return false;
    for (const a of m[3].matchAll(/\[([\w-]+)(?:="([^"]*)")?\]/g)) {
        if (a[1] === 'tabindex') { if (n.tabIndex < 0) return false; continue; }
        if (a[1].startsWith('data-') && !(a[1] in n.atributos)) {
            const k = a[1].slice(5).replace(/-(\w)/g, (_, l) => l.toUpperCase());
            if (!(k in n.dataset)) return false;
            if (a[2] !== undefined && n.dataset[k] !== a[2]) return false;
            continue;
        }
        if (!(a[1] in n.atributos)) return false;
        if (a[2] !== undefined && n.atributos[a[1]] !== a[2]) return false;
    }
    return true;
}
/** cada scrollIntoView que se pidió: qué tarjeta y cómo */
const aLaVista = [];
const ventana = new Nodo('#window');
const documento = new Nodo('#document');
documento.body = new Nodo('body');
documento.appendChild(documento.body);
documento.parentElement = ventana;
documento.activeElement = documento.body;
documento.createElement = tag => new Nodo(tag);
documento.visibilityState = 'visible';
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
Object.defineProperty(globalThis, 'navigator', { value: { platform: 'MacIntel' }, configurable: true });

// un requestAnimationFrame de mentira: los cuadros pedidos esperan a que la prueba los corra, con el reloj que ella dice
let pedidos = new Map(), siguiente = 1, cancelados = 0, reloj = 0;
globalThis.requestAnimationFrame = fn => { const id = siguiente++; pedidos.set(id, fn); return id; };
globalThis.cancelAnimationFrame = id => { if (pedidos.delete(id)) cancelados++; };
/** Corre `n` cuadros, `ms` cada uno. */
const cuadros = (n, ms = 16) => {
    for (let i = 0; i < n; i++) {
        reloj += ms;
        const ahora = [...pedidos.entries()];
        pedidos = new Map();
        for (const [, fn] of ahora) fn(reloj);
    }
};
// «reducir movimiento», a pedido de la prueba
let quieto = false;
globalThis.matchMedia = q => ({ matches: /reduced-motion: reduce/.test(q) && quieto });
// la API: los artes de la raíz (`GET /arte`), los que la prueba ponga
let deLaRaiz = [];
globalThis.fetch = async url => {
    if (String(url).startsWith('/api/arte')) return { ok: true, status: 200, json: async () => ({ carpeta: '/raiz/.telar/arte', artes: deLaRaiz, errores: {} }) };
    return { ok: false, status: 404, json: async () => ({ detail: 'Not Found' }) };
};

const dir = mkdtempSync(path.join(tmpdir(), 'mundos-ventana-'));
const entrada = path.join(dir, 'entrada.ts');
const de = r => JSON.stringify(path.join(src, r));
writeFileSync(entrada, [
    `export * as A from ${de('componentes/arte.ts')};`,
    `import ${de('componentes/arte/index.ts')};`,
    `export * as MV from ${de('componentes/mundos-ventana.ts')};`,
    `export * as W from ${de('web/mundos-ventana.ts')};`,
    `export * as mundo from ${de('web/mundo.ts')};`,
    `export { mundoBoton } from ${de('componentes/modos-mundos.ts')};`,
    `export { I } from ${de('web/iconos.ts')};`,
].join('\n'));
const salida = path.join(dir, 'mundos-ventana.cjs');
await build({ entryPoints: [entrada], bundle: true, platform: 'node', format: 'cjs', outfile: salida, logLevel: 'warning' });
const { A, MV, W, mundo, mundoBoton, I } = require(salida);

// ── 1. el contrato del arte ──
{
    // los de fábrica: el telar, el cielo, la órbita y la binaria; cada cuadro, del lienzo exacto, y el mismo instante da el
    // mismo cuadro (son funciones puras del tiempo)
    const claves = A.artes().map(a => a.clave);
    for (const k of ['telar', 'cielo', 'orbita', 'binaria']) assert.ok(claves.includes(k), `de fábrica: ${k}`);
    for (const a of A.artes()) {
        assert.equal(a.origen, 'fabrica');
        assert.ok(a.nombre && a.que, `${a.clave}: nombre y qué es, para el catálogo y ⚙ mundos`);
        assert.ok(a.alHover.fps > a.fps, `${a.clave}: más rápido con el mouse encima`);
        const vistos = new Set();
        for (const t of [0, .37, 1.1, 2.5, 7.9, 30]) {
            const c = A.cuadro(a, t);
            const lineas = c.split('\n');
            assert.equal(lineas.length, A.ALTO, `${a.clave} a los ${t} s: ${A.ALTO} líneas`);
            for (const l of lineas) assert.equal([...l].length, A.ANCHO, `${a.clave} a los ${t} s: cada línea de ${A.ANCHO} letras («${l}»)`);
            assert.equal(A.cuadro(a, t), c, `${a.clave}: el mismo instante, el mismo cuadro`);
            assert.ok(c.trim(), `${a.clave}: dibuja algo`);
            vistos.add(c);
        }
        assert.ok(vistos.size > 2, `${a.clave}: se mueve`);
    }
    // registrar uno: la clave en minúsculas, al menos un cuadro, los fps acotados; uno con lista de cuadros va a su ritmo
    assert.throws(() => A.registrarArte('Con Espacio', { cuadros: ['x'] }), /minúsculas/);
    assert.throws(() => A.registrarArte('vacio', { cuadros: [] }), /al menos un cuadro/);
    const parpadeo = A.registrarArte('parpadeo', { cuadros: ['o', '-'], fps: 2 });
    assert.deepEqual([parpadeo.fps, parpadeo.alHover.fps], [2, 2 * A.ACELERA], 'sin decir el de hover: el triple');
    assert.equal(A.registrarArte('lento', { cuadros: ['x'], fps: 0 }).fps, .5, 'fps acotados');
    const medio = A.cuadro(parpadeo, 0).split('\n');
    assert.equal(medio[Math.floor((A.ALTO - 1) / 2)].trim(), 'o', 'un cuadro chico va al medio del lienzo');
    assert.equal(A.cuadro(parpadeo, .6).split('\n')[Math.floor((A.ALTO - 1) / 2)].trim(), '-', 'a 2 fps, el segundo cuadro a los 0,6 s');
    assert.equal(A.indice(parpadeo, 1.2), 2);
    // los cuadros de una lista se centran juntos: la caja de todos, no cada uno por su cuenta (así no saltan)
    const [c1, c2] = A.encuadrar(['xxxxxx', 'x'], 10, 3);
    assert.equal(c1.split('\n')[1], '  xxxxxx  ');
    assert.equal(c2.split('\n')[1], '  x       ', 'el chico, alineado con el grande');
    assert.equal(A.encuadrar(['0123456789ABCDEF'], 10, 1)[0], '0123456789', 'lo que no cabe se recorta');
    A.olvidarArte('parpadeo'); A.olvidarArte('lento');
}
// un arte escrito en un archivo
{
    const { def, avisos } = A.leerArteTexto('fps: 4\nhover: 12\nnombre: el faro\nque: un faro que gira\npara: casa, playa\n---\n /\\\n/  \\\n---\n /\\ \n/**\\\n--- hover\n *\n***\n');
    assert.deepEqual([def.fps, def.alHover.fps, def.nombre, def.que, def.para], [4, 12, 'el faro', 'un faro que gira', ['casa', 'playa']]);
    assert.deepEqual(def.cuadros, [' /\\\n/  \\', ' /\\ \n/**\\'], 'los cuadros, sin las líneas en blanco de los bordes');
    assert.deepEqual(def.alHover.cuadros, [' *\n***'], 'desde «--- hover», la escena de hover');
    assert.deepEqual(avisos, []);
    // sin cabecera: todo es dibujo (también una línea que parece «clave: valor» si no está sola arriba)
    const solo = A.leerArteTexto('  .\n ...\n.....\n').def;
    assert.deepEqual([solo.cuadros, solo.fps], [['  .\n ...\n.....'], undefined]);
    assert.deepEqual(A.leerArteTexto('nota: esto es dibujo\n').def.cuadros, ['nota: esto es dibujo'], 'sin «---», no hay cabecera');
    assert.deepEqual(A.leerArteTexto('fps: rapido\n---\nx\n').avisos, ['«fps: rapido»: se esperaba un número de cuadros por segundo']);
    assert.throws(() => A.leerArteTexto('fps: 3\n---\n\n'), /ningún cuadro/);
    assert.throws(() => A.leerArteTexto('--- hover\nx\n'), /ningún cuadro antes/);
    assert.deepEqual(A.leerArteTexto('a\r\nb\r\n---\r\nc\r\n').def.cuadros, ['a\nb', 'c'], 'los finales de línea de Windows');
}
// los de la raíz: se registran, uno con la clave de uno de fábrica lo tapa, y al irse vuelve el de fábrica
{
    const fabrica = A.arte('cielo');
    const r = A.registrarDeArchivos([{ nombre: 'faro', texto: ' /\\\n' }, { nombre: 'cielo', texto: '***\n' }, { nombre: 'roto', texto: '' }]);
    assert.deepEqual(r.registrados, ['faro', 'cielo']);
    assert.match(r.errores.roto, /ningún cuadro/);
    assert.equal(A.arte('faro').origen, 'archivo');
    assert.notEqual(A.arte('cielo'), fabrica, 'el de la raíz tapa al de fábrica');
    A.registrarDeArchivos([{ nombre: 'faro', texto: ' /\\\n' }]);
    assert.equal(A.arte('cielo'), fabrica, 'el archivo se fue: vuelve el de fábrica');
    A.registrarDeArchivos([]);
    assert.equal(A.arte('faro'), undefined, 'el que ya no está, se olvida');
}
// qué arte lleva cada mundo
{
    assert.equal(A.arteDeMundo({ clave: 'trabajo' }).clave, 'telar', 'el que lo sugiere (para)');
    assert.equal(A.arteDeMundo({ clave: 'personal' }).clave, 'cielo');
    assert.equal(A.arteDeMundo({ clave: 'estudio' }).clave, 'orbita', 'sin arte: la órbita');
    assert.equal(A.arteDeMundo({ clave: 'trabajo', arte: 'binaria' }).clave, 'binaria', 'el que dice su `arte`');
    assert.equal(A.arteDeMundo({ clave: 'trabajo', arte: 'no-hay' }).clave, 'telar', 'uno que no hay: el que le toca');
    assert.equal(A.arteDeMundo(undefined).clave, 'binaria', 'ambos');
    A.registrarArte('estudio', { cuadros: ['E'] });
    assert.equal(A.arteDeMundo({ clave: 'estudio' }).clave, 'estudio', 'el que se llama como el mundo');
    A.olvidarArte('estudio');
}

// el efecto de hover: la ola, sobre cualquier arte (de fábrica, registrado o de un archivo), salvo el que declara el suyo
{
    const ola = A.efecto('ola');
    assert.ok(ola && ola.dura > 0 && ola.fps > 0, 'la ola, de fábrica');
    const deArchivo = A.registrarArte('faro-ola', { ...A.leerArteTexto('fps: 2\n---\n /\\\n/__\\\n').def });
    for (const a of [...A.artes()]) {
        assert.equal(A.efectoDe(a), ola, `${a.clave}: sin decir nada, la ola`);
        const base = A.cuadro(a, 1.3);
        const vistos = new Set();
        for (const u of [.1, .3, .5, .7, .9]) {
            const c = A.cuadro(a, 1.3, { efecto: u * ola.dura });
            assert.equal(c.split('\n').length, A.ALTO, `${a.clave} con la ola: ${A.ALTO} líneas`);
            for (const l of c.split('\n')) assert.equal([...l].length, A.ANCHO, `${a.clave} con la ola: cada línea de ${A.ANCHO}`);
            assert.equal(A.cuadro(a, 1.3, { efecto: u * ola.dura }), c, `${a.clave}: la ola es pura`);
            assert.notEqual(c, base, `${a.clave}: a los ${u} de su pasada, la ola se ve`);
            assert.match(c, /[▓▒░]/, `${a.clave}: la ola es de letras`);
            vistos.add(c);
        }
        assert.ok(vistos.size >= 4, `${a.clave}: la ola avanza`);
        assert.equal(A.cuadro(a, 1.3, { efecto: ola.dura }), base, `${a.clave}: pasada la ola, el cuadro como estaba`);
        assert.equal(A.cuadro(a, 1.3, { efecto: undefined }), base);
    }
    // la ola cruza de izquierda a derecha: al principio a la izquierda, al final a la derecha
    const columnaDeLaOla = c => { const xs = c.split('\n').flatMap(l => [...l].map((ch, x) => (/[▓]/.test(ch) ? x : -1)).filter(x => x >= 0)); return xs.reduce((a, b) => a + b, 0) / Math.max(1, xs.length); };
    const orb = A.arte('orbita');
    assert.ok(columnaDeLaOla(A.cuadro(orb, 0, { efecto: .2 * ola.dura })) < columnaDeLaOla(A.cuadro(orb, 0, { efecto: .7 * ola.dura })), 'de izquierda a derecha');
    // uno que declara el suyo: gana el suyo
    const propio = { dura: .5, aplicar: c => c.replace(/\S/g, '#') };
    const conPropio = A.registrarArte('con-propio', { cuadros: ['xy'], alHover: { efecto: propio } });
    assert.equal(A.efectoDe(conPropio), propio);
    assert.match(A.cuadro(conPropio, 0, { efecto: .1 }), /##/, 'el suyo, no la ola');
    assert.equal(A.cuadro(conPropio, 0, { efecto: .6 }), A.cuadro(conPropio, 0), 'y dura lo que dice');
    assert.equal(A.efectoDe(A.registrarArte('sin-ola', { cuadros: ['x'], alHover: { efecto: 'ninguno' } })), undefined, 'ninguno');
    assert.equal(A.efectoDe(A.registrarArte('con-escena', { cuadros: ['x'], alHover: { cuadros: ['y'] } })), undefined,
        'con escena de hover propia: manda su escena, sin ola');
    assert.equal(A.efectoDe(A.registrarArte('escena-y-ola', { cuadros: ['x'], alHover: { cuadros: ['y'], efecto: 'ola' } })), ola, 'salvo que pida la ola');
    // uno registrado por su clave; una clave que no hay, la ola
    const brillo = A.registrarEfecto('brillo', { dura: .3, aplicar: c => c.toUpperCase() });
    assert.equal(A.efectoDe(A.registrarArte('con-brillo', { cuadros: ['x'], alHover: { efecto: 'brillo' } })), brillo);
    assert.equal(A.efectoDe(A.registrarArte('con-otro', { cuadros: ['x'], alHover: { efecto: 'no-hay' } })), ola, 'uno que no hay: la ola');
    assert.throws(() => A.registrarEfecto('ninguno', { dura: 1, aplicar: c => c }), /clave/);
    assert.throws(() => A.registrarEfecto('nada', { dura: 0, aplicar: c => c }), /dura/);
    // un efecto que falla no rompe el cuadro
    const roto = A.registrarArte('roto-ola', { cuadros: ['x'], alHover: { efecto: { dura: 1, aplicar: () => { throw new Error('no'); } } } });
    assert.equal(A.cuadro(roto, 0, { efecto: .5 }), A.cuadro(roto, 0));
    // en un archivo: `efecto: ninguno` (u otra clave) en la cabecera; lo que no es una clave, un aviso
    assert.equal(A.leerArteTexto('efecto: ninguno\n---\nx\n').def.alHover.efecto, 'ninguno');
    assert.equal(A.leerArteTexto('efecto: Brillo\n---\nx\n').def.alHover.efecto, 'brillo');
    assert.match(A.leerArteTexto('efecto: ¿?\n---\nx\n').avisos[0], /un efecto es «ola», «ninguno» u otra clave/);
    for (const k of ['faro-ola', 'con-propio', 'sin-ola', 'con-escena', 'escena-y-ola', 'con-brillo', 'con-otro', 'roto-ola']) A.olvidarArte(k);
    void deArchivo;
}

// ── 2. lo que dicen las tarjetas ──
const T = (dias, desde, hasta) => ({ dias, desde: desde * 60, hasta: hasta * 60 });
const MUNDOS = [
    { clave: 'trabajo', nombre: 'trabajo', color: 'cian', horario: [T([1, 2, 3, 4, 5], 9, 19)] },
    { clave: 'personal', nombre: 'personal', color: 'magenta', horario: [] },
];
const lunes10 = new Date(2026, 10, 23, 10, 0);
{
    const p = { mundo: 'trabajo', por: 'horario', hasta: new Date(2026, 10, 23, 19, 0), luego: 'personal' };
    const ts = MV.tarjetasDeMundos(p, MUNDOS, lunes10, 'personal');
    assert.deepEqual(ts.map(t => [t.clave, t.nombre, t.tecla, t.puesto, t.arte]),
        [['trabajo', 'trabajo', '1', true, 'telar'], ['personal', 'personal', '2', false, 'cielo'], ['', 'ambos', '3', false, 'binaria']]);
    assert.deepEqual(ts.map(t => t.horario), ['lun–vie 9:00–19:00', 'fuera de todo horario', 'todo junto, en tandas']);
    assert.deepEqual(ts.map(t => t.estado), ['por horario, hasta las 19:00', 'desde las 19:00', ''], 'la de ahora, por qué y hasta cuándo; la que viene, desde cuándo');
    const aMano = MV.tarjetasDeMundos({ mundo: '', por: 'a-mano', hasta: new Date(2026, 10, 23, 19, 0), luego: 'personal' }, MUNDOS, lunes10, 'personal');
    assert.equal(aMano[2].estado, 'a mano, hasta las 19:00');
    assert.ok(aMano[2].puesto && !aMano[0].puesto);
    const sinHorarios = MV.tarjetasDeMundos({ mundo: '', por: 'sin-horario' }, MUNDOS.map(m => ({ ...m, horario: [] })), lunes10, '');
    assert.deepEqual(sinHorarios.map(t => t.horario), ['a mano', 'a mano', 'todo junto, en tandas'], 'sin horarios, todo a mano');

    const h = MV.ventanaMundos(ts, { aMano: false });
    assert.equal((h.match(/class="mt-tarjeta/g) ?? []).length, 3, 'una tarjeta por mundo, y ambos');
    assert.match(h, /<div class="mt-grilla cols-3" style="--mt-cols: 3"/, 'tres, en una fila');
    assert.match(h, /class="mt-tarjeta puesto" data-mundo="trabajo" data-indice="0" aria-pressed="true"[^>]*style="--mundo-c: var\(--cian\)"/);
    assert.match(h, /class="mt-tarjeta ambos" data-mundo="" data-indice="2" aria-pressed="false"/, 'ambos, en el color del texto');
    assert.match(h, /<span class="mt-arte" data-arte="telar">/);
    assert.match(h, /<span class="mt-ahora"><span class="circulo tam-chico"[^>]*><\/span><span>ahora<\/span><\/span>/, 'la de ahora, con su círculo lleno');
    assert.match(h, new RegExp(`<span class="i mt-planeta">${I.planeta}</span>`), 'el planeta junto al título');
    assert.match(h, /data-accion="horario"[^>]*data-tecla="h"[^>]* disabled>/, 'volver al horario, apagado: ya rige');
    assert.match(MV.ventanaMundos(ts, { aMano: true }), /data-accion="horario"[^>]*data-tecla="h"[^>]*title="soltar lo elegido a mano[^"]*">/);
    assert.match(h, /data-accion="editar"[^>]*data-tecla="e"/);
    assert.match(h, /data-accion="no"[^>]*data-tecla="⎋"/, 'cerrar, con ⎋, al último');
    assert.match(h, /1–3 elegir/);
    // columnas: hasta cuatro en una fila; más, de a tres hacia abajo, y la última de una fila corta se estira
    assert.deepEqual([1, 2, 3, 4, 5, 6, 7, 8, 11, 30].map(n => MV.columnas(n)), [1, 2, 3, 4, 3, 3, 3, 3, 3, 3]);
    const cinco = MV.grillaMundos(Array.from({ length: 5 }, (_, i) => ({ ...ts[0], clave: `m${i}`, puesto: false })));
    assert.equal((cinco.match(/span-2/g) ?? []).length, 1, 'cinco en tres columnas: la última ocupa dos');
    assert.match(h, /← → recorrer · 1–3 elegir/, 'en una fila, ← →');
    // diez mundos: cada uno con su número (también 10 y 11), de a tres hacia abajo, y ↑ ↓ en el pie
    const diez = MV.tarjetasDeMundos({ mundo: 'm7', por: 'a-mano' },
        Array.from({ length: 10 }, (_, i) => ({ clave: `m${i}`, nombre: `m${i}`, color: 'cian', horario: [] })), lunes10, '');
    assert.deepEqual(diez.map(t => t.tecla), ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11']);
    const hd = MV.ventanaMundos(diez, { aMano: true });
    assert.match(hd, /<div class="mt-grilla cols-3" style="--mt-cols: 3"/);
    assert.match(hd, /← → ↑ ↓ recorrer · 1–11 elegir/);
    assert.match(hd, /<span class="mt-tecla">11<\/span><span class="mt-nombre">ambos/);
    // una sin estado lleva su línea igual (en blanco): todas las de una fila miden lo mismo, y todas las filas también
    assert.match(hd, /<span class="mt-estado">\u00a0<\/span>/);
    // encima, en el catálogo: la ola a medio camino
    assert.match(MV.tarjetaMundo(diez[0], { estado: 'hover' }), /[▓▒░]/, 'encima, la ola');
    assert.doesNotMatch(MV.tarjetaMundo(diez[0], {}), /[▓]/);
}
// el planeta en la banda, delante del nombre, como el ícono de cada modo
{
    const b = mundoBoton({ mundo: 'trabajo', por: 'horario' }, MUNDOS, lunes10, 'banda-mundo-boton');
    assert.match(b, new RegExp(`<span class="i mundo-icono">${I.planeta}</span><span class="mundo-nombre">trabajo</span>`));
    assert.match(b, /⌘M/, 'la ayuda dice la tecla de la ventana');
    assert.match(css('modos'), /& > \.mundo-icono \{ display: inline-block; flex: none; inline-size: 2ch; text-align: center; \}/);
    assert.match(css('modos'), /& > \.mundo-icono \+ \.mundo-nombre \{ padding-inline-start: \.5ch; \}/, 'el aire del ícono de un modo');
}
// las flechas: ← → de a una; ↑ ↓ de a una fila (en una sola fila o columna, de a una); dan la vuelta
{
    assert.equal(W.vecina(0, 'ArrowRight', 3, 3), 1);
    assert.equal(W.vecina(2, 'ArrowRight', 3, 3), 0);
    assert.equal(W.vecina(0, 'ArrowLeft', 3, 3), 2);
    assert.equal(W.vecina(0, 'ArrowDown', 3, 3), 1, 'una sola fila: abajo es la siguiente');
    assert.equal(W.vecina(0, 'ArrowDown', 3, 1), 1, 'una columna (el teléfono)');
    assert.equal(W.vecina(0, 'ArrowUp', 3, 1), 2);
    assert.equal(W.vecina(1, 'ArrowDown', 5, 3), 4, 'de a una fila');
    assert.equal(W.vecina(2, 'ArrowDown', 5, 3), 2, 'la fila de abajo es corta: a la misma columna de arriba');
    assert.equal(W.vecina(1, 'ArrowUp', 5, 3), 4, 'por arriba, a la de abajo');
}

// los números: hasta nueve, al tiro; con diez o más, una cifra que puede empezar otro espera la segunda
{
    assert.deepEqual(W.numero('', '3', 3), { elegir: 3 });
    assert.deepEqual(W.numero('', '4', 3), {}, 'no hay cuarta');
    assert.deepEqual(W.numero('', '1', 9), { elegir: 1 }, 'hasta nueve, el 1 elige al tiro');
    assert.deepEqual(W.numero('', '0', 11), {}, 'el 0 solo, nada');
    assert.deepEqual(W.numero('', '1', 11), { espera: '1' }, 'con once, el 1 espera');
    assert.deepEqual(W.numero('', '2', 11), { elegir: 2 }, 'el 2 no empieza ninguno: al tiro');
    assert.deepEqual(W.numero('1', '1', 11), { elegir: 11 });
    assert.deepEqual(W.numero('1', '0', 11), { elegir: 10 });
    assert.deepEqual(W.numero('1', '5', 11), { elegir: 5 }, 'el 15 no existe: el 5 solo');
    assert.deepEqual(W.numero('', '2', 25), { espera: '2' });
}

// ── 3 y 4. la ventana viva y su arte ──
const abierta = () => documento.body.children.find(n => n.tagName === 'DIALOG' && n.open);
const tecla = (key, o = {}) => disparar(documento.activeElement, { type: 'keydown', key, code: o.code ?? '', ...o });
const contesta = r => Promise.race([r, new Promise((_, no) => setTimeout(() => no(new Error('la ventana no contestó')), 500))]);
const elegidos = [];
const o = { elegir: x => elegidos.push(x), editar: () => elegidos.push({ editar: true }) };
// los mundos de la configuración, como los da `telar config` (el horario ya leído), un lunes a las 10
mundo.recibir({ mundos: [
    { nombre: 'trabajo', color: 'cian', horario: [{ texto: 'lun-vie 9:00-19:00', dias: [1, 2, 3, 4, 5], desde: 540, hasta: 1140 }] },
    { nombre: 'personal', color: 'magenta', horario: [] },
], mundos_fuera: 'personal' });
{
    const r = W.abrir(o);
    const d = abierta();
    assert.ok(d && W.estaAbierta(), 'se abre');
    const ts = d.querySelectorAll('.mt-tarjeta');
    assert.equal(ts.length, 3);
    const puesto = mundo.puesto().mundo;
    assert.equal(documento.activeElement, ts.find(t => t.dataset.mundo === puesto), 'el foco parte en la de ahora');
    // el arte se anima: un cuadro pedido, y al correr el tiempo cambia lo dibujado
    assert.ok(W.vivoAbierto().corriendo(), 'abierta: un cuadro pedido');
    const arte0 = ts[0].querySelector('[data-arte]');
    const antes = arte0.textContent;
    cuadros(90, 16);
    assert.notEqual(arte0.textContent, antes, 'el telar teje');
    assert.equal(arte0.textContent.split('\n').length, 9);
    // con la pestaña escondida, nada; al volver, sigue
    documento.visibilityState = 'hidden';
    disparar(documento, { type: 'visibilitychange' });
    assert.equal(pedidos.size, 0, 'escondida: ningún cuadro pedido');
    assert.ok(!W.vivoAbierto().corriendo());
    documento.visibilityState = 'visible';
    disparar(documento, { type: 'visibilitychange' });
    assert.ok(W.vivoAbierto().corriendo(), 'a la vista otra vez: sigue');
    // las flechas mueven el foco; con el foco encima, el arte acelera (de a poco)
    documento.activeElement = ts[0];
    tecla('ArrowRight');
    assert.equal(documento.activeElement, ts[1], '→ a la siguiente');
    tecla('ArrowLeft');
    tecla('ArrowLeft');
    assert.equal(documento.activeElement, ts[2], '← desde la primera, a la última');
    ts[1].focus();
    const relojes = () => W.vivoAbierto().estado().map(e => e.reloj);
    const [a0, a1] = relojes();
    cuadros(120, 16);
    const [b0, b1] = relojes();
    const est = W.vivoAbierto().estado();
    assert.ok(est[1].hover && !est[0].hover, 'el foco enciende solo la suya');
    assert.ok(b1 - a1 > 2 * (b0 - a0), `encima, su reloj corre más rápido (${(b1 - a1).toFixed(2)} s contra ${(b0 - a0).toFixed(2)} s)`);
    assert.ok(est[1].vel > 2.5 && est[1].vel <= 3.01, 'llega a su ritmo de hover sin pasarse');
    ts[0].focus();
    cuadros(120, 16);
    assert.ok(W.vivoAbierto().estado()[1].vel < 1.05, 'al salir, frena hasta su ritmo de siempre');
    // un arte nuevo que llega con la ventana abierta (uno de la raíz que se llama como el mundo): la tarjeta lo toma al tiro
    A.registrarArte('trabajo', { cuadros: ['T R A B A J O'], origen: 'archivo' });
    assert.equal(ts[0].querySelector('[data-arte]').dataset.arte, 'trabajo');
    cuadros(2);
    assert.match(ts[0].querySelector('[data-arte]').textContent, /T R A B A J O/);
    A.olvidarArte('trabajo');
    // 2: pone personal
    tecla('2');
    assert.equal(await contesta(r), 'mundo:personal');
    assert.deepEqual(elegidos.pop(), { mundo: 'personal' });
    assert.equal(abierta(), undefined, 'se cierra');
    // cerrada: nada corriendo, ningún cuadro pedido, y uno que estuviera en vuelo no pide otro
    assert.ok(!W.estaAbierta());
    assert.equal(pedidos.size, 0, 'cerrada: ningún requestAnimationFrame');
    cuadros(5);
    assert.equal(pedidos.size, 0);
}
{
    // ⏎ pone la del foco; sostenido, no
    const r = W.abrir(o);
    const ts = abierta().querySelectorAll('.mt-tarjeta');
    ts[2].focus();
    tecla('Enter', { repeat: true });
    assert.ok(abierta(), 'un ⏎ sostenido no elige');
    const e = tecla('Enter');
    assert.ok(e.defaultPrevented);
    assert.equal(await contesta(r), 'mundo:');
    assert.deepEqual(elegidos.pop(), { mundo: '' }, 'ambos');
}
{
    // un clic (o un toque) en una tarjeta la pone
    const r = W.abrir(o);
    abierta().querySelectorAll('.mt-tarjeta')[0].querySelector('.mt-nombre').click();
    assert.equal(await contesta(r), 'mundo:trabajo');
    assert.deepEqual(elegidos.pop(), { mundo: 'trabajo' });
}
{
    // volver al horario: apagado si ya rige; con uno a mano, h lo suelta. De verdad (sin `elegir`): web/mundo.ts
    mundo.volverAlHorario();
    let r = W.abrir(o);
    tecla('h');
    assert.ok(abierta(), 'ya rige el horario: h no hace nada');
    tecla('Escape');
    assert.equal(await contesta(r), undefined, '⎋ la cierra sin elegir');
    assert.equal(elegidos.length, 0);
    mundo.poner('personal');
    assert.equal(mundo.puesto().por, 'a-mano');
    r = W.abrir({ editar: o.editar });
    tecla('h');
    assert.equal(await contesta(r), 'horario');
    assert.notEqual(mundo.puesto().por, 'a-mano', 'rige el horario otra vez');
    // y elegir de verdad pone el mundo
    r = W.abrir({});
    tecla('3');
    await contesta(r);
    assert.deepEqual([mundo.puesto().mundo, mundo.puesto().por], ['', 'a-mano'], 'ambos, a mano');
    mundo.volverAlHorario();
    // editar lleva a ⚙ mundos
    r = W.abrir(o);
    tecla('e');
    assert.equal(await contesta(r), 'editar');
    assert.deepEqual(elegidos.pop(), { editar: true });
}
{
    // ⌘M la abre y, abierta, la cierra; sin ⌘, o con ⌥ o ⇧, no
    W.montar(o);
    const m = extra => disparar(ventana, { type: 'keydown', key: 'm', code: 'KeyM', ...extra });
    m({ altKey: true, metaKey: true });
    assert.equal(abierta(), undefined, '⌥⌘M no');
    m({ shiftKey: true, metaKey: true });
    assert.equal(abierta(), undefined, '⌘⇧M es de Chrome (cambiar de persona): no');
    const e = m({ metaKey: true });
    assert.ok(e.defaultPrevented, 'se la quita a Chrome: no minimiza');
    assert.ok(abierta(), '⌘M la abre');
    m({ metaKey: true, repeat: true });
    assert.ok(abierta(), 'sostenida, no la cierra');
    m({ metaKey: true });
    await new Promise(ok => setTimeout(ok, 0));
    assert.equal(abierta(), undefined, '⌘M otra vez la cierra');
    assert.equal(pedidos.size, 0);
    assert.equal(elegidos.length, 0, 'cerrarla así no elige nada');
}
{
    // con «reducir movimiento»: ningún cuadro pedido, el primero quieto, y el foco no acelera nada
    quieto = true;
    const n = siguiente;
    const r = W.abrir(o);
    const ts = abierta().querySelectorAll('.mt-tarjeta');
    assert.equal(siguiente, n, 'ningún requestAnimationFrame');
    assert.ok(!W.vivoAbierto().corriendo());
    assert.equal(ts[0].querySelector('[data-arte]').textContent, A.cuadro(A.arte('telar'), 0), 'el primer cuadro, quieto');
    ts[1].focus();
    cuadros(30);
    assert.equal(ts[1].querySelector('[data-arte]').textContent, A.cuadro(A.arte('cielo'), 0), 'encima, también quieto');
    tecla('Escape');
    await contesta(r);
    quieto = false;
}
{
    // los artes de la raíz se leen al abrirla: uno que se llama como un mundo es el suyo
    deLaRaiz = [{ nombre: 'personal', texto: 'fps: 2\n---\n( casa )\n' }];
    const r = W.abrir(o);
    await new Promise(ok => setTimeout(ok, 10));
    const t = abierta().querySelectorAll('.mt-tarjeta')[1];
    assert.equal(t.querySelector('[data-arte]').dataset.arte, 'personal');
    cuadros(2);
    assert.match(t.querySelector('[data-arte]').textContent, /\( casa \)/);
    tecla('Escape');
    await contesta(r);
    deLaRaiz = [];
    await W.leerArtes();
    assert.equal(A.arte('personal'), undefined, 'el archivo se fue: se olvida');
}

{
    // un <dialog> que otro cerró por su cuenta no cuenta como abierta: ⌘M (o un clic) la vuelve a abrir, y la vieja no
    // le quita nada a la nueva al terminar de cerrarse
    const r1 = W.abrir(o);
    abierta().close();
    assert.ok(!W.estaAbierta());
    const r2 = W.abrir(o);
    assert.ok(abierta() && W.estaAbierta(), 'se abre una nueva');
    assert.equal(await contesta(r1), undefined, 'la vieja termina sin elegir');
    assert.ok(W.estaAbierta(), 'y la nueva sigue contando como abierta');
    tecla('Escape');
    assert.equal(await contesta(r2), undefined);
    assert.ok(!W.estaAbierta());
    assert.equal(pedidos.size, 0);
}

{
    // diez mundos: abre con la de ahora a la vista; la del foco, siempre a la vista; 1 y 1 es la 11
    const lista = Array.from({ length: 10 }, (_, i) => ({ clave: `m${i}`, nombre: `m${i}`, color: 'cian', horario: [] }));
    const fuente = () => ({ puesto: { mundo: 'm8', por: 'a-mano' }, mundos: lista, fuera: '', ahora: lunes10 });
    aLaVista.length = 0;
    let r = W.abrir({ ...o, fuente });
    let ts = abierta().querySelectorAll('.mt-tarjeta');
    assert.equal(ts.length, 11);
    assert.equal(documento.activeElement, ts[8], 'el foco en la de ahora');
    await new Promise(ok => setTimeout(ok, 5));
    assert.deepEqual(aLaVista.map(x => [x.el, x.block, x.behavior]), [[ts[8], 'nearest', 'auto']], 'al abrir, la de ahora a la vista, de golpe');
    tecla('ArrowDown');
    assert.equal(documento.activeElement, ts[9], 'abajo, de a una (este DOM no tiene filas: una columna)');
    assert.deepEqual([aLaVista.at(-1).el, aLaVista.at(-1).behavior], [ts[9], 'smooth'], 'la del foco, a la vista, suave');
    // 1 y 1: la 11 (ambos)
    tecla('1');
    assert.ok(abierta(), 'con once, el 1 espera la segunda');
    assert.equal(documento.activeElement, ts[0], 'con el foco ya en la 1');
    assert.equal(aLaVista.at(-1).el, ts[0], 'y a la vista');
    tecla('1');
    assert.equal(await contesta(r), 'mundo:');
    assert.deepEqual(elegidos.pop(), { mundo: '' });
    // 1 sola: la 1, pasado un momento
    r = W.abrir({ ...o, fuente });
    tecla('1');
    assert.equal(await Promise.race([r, new Promise(ok => setTimeout(() => ok('esperando'), W.ESPERA_CIFRA / 2))]), 'esperando');
    assert.equal(await Promise.race([r, new Promise((_, no) => setTimeout(() => no(new Error('no eligió')), W.ESPERA_CIFRA + 300))]), 'mundo:m0');
    assert.deepEqual(elegidos.pop(), { mundo: 'm0' });
    // 3: al tiro (no empieza ninguno)
    r = W.abrir({ ...o, fuente });
    tecla('3');
    assert.equal(await contesta(r), 'mundo:m2');
    elegidos.pop();
    // con «reducir movimiento», a la vista de golpe
    quieto = true;
    aLaVista.length = 0;
    r = W.abrir({ ...o, fuente });
    ts = abierta().querySelectorAll('.mt-tarjeta');
    tecla('ArrowUp');
    assert.deepEqual([aLaVista.at(-1).el, aLaVista.at(-1).behavior], [ts[7], 'auto']);
    tecla('Escape');
    await contesta(r);
    quieto = false;
    assert.equal(pedidos.size, 0);
}
{
    // la ola: al entrar el foco (o el mouse), pasa una vez con el reloj de la pared, y deja el cuadro como estaba
    const r = W.abrir(o);
    const ts = abierta().querySelectorAll('.mt-tarjeta');
    const ola = A.efecto('ola');
    const el = ts[1].querySelector('[data-arte]');
    ts[0].focus();
    cuadros(3);
    ts[1].focus();
    assert.equal(W.vivoAbierto().estado()[1].efecto, 0, 'al entrar, la ola empieza');
    const sinOla = () => A.cuadro(A.arte('cielo'), W.vivoAbierto().estado()[1].reloj, { hover: true });
    const vistos = new Set();
    let conOla = 0;
    for (let i = 0; i < 40; i++) { cuadros(1, 16); vistos.add(el.textContent); if (el.textContent !== sinOla()) conOla++; }
    assert.ok(conOla > 30, `la ola se ve mientras pasa (${conOla} de 40 cuadros)`);
    assert.ok(vistos.size > 15, `y avanza (${vistos.size} cuadros distintos)`);
    cuadros(Math.ceil(ola.dura * 1000 / 16));
    assert.equal(W.vivoAbierto().estado()[1].efecto, -1, 'pasó');
    assert.equal(el.textContent, sinOla(), 'y el cuadro queda como estaba');
    // salir a media pasada: la ola termina su pasada igual
    ts[2].focus();
    cuadros(5);
    ts[1].focus();
    cuadros(5);
    ts[0].focus();
    assert.ok(W.vivoAbierto().estado()[1].efecto > 0, 'sigue pasando aunque salió');
    cuadros(Math.ceil(ola.dura * 1000 / 16));
    assert.equal(W.vivoAbierto().estado()[1].efecto, -1);
    tecla('Escape');
    await contesta(r);
}
{
    // con «reducir movimiento», ninguna ola
    quieto = true;
    const r = W.abrir(o);
    const ts = abierta().querySelectorAll('.mt-tarjeta');
    ts[1].focus();
    assert.equal(W.vivoAbierto().estado()[1].efecto, -1, 'quieto: sin ola');
    assert.equal(ts[1].querySelector('[data-arte]').textContent, A.cuadro(A.arte('cielo'), 0), 'el primer cuadro, sin ola');
    assert.ok(!W.vivoAbierto().corriendo());
    tecla('Escape');
    await contesta(r);
    quieto = false;
}
{
    // solo anima lo que se ve: un IntersectionObserver de mentira dice cuáles están a la vista
    const observados = new Set();
    let avisar;
    globalThis.IntersectionObserver = class {
        constructor(f) { avisar = (els, si) => f(els.map(target => ({ target, isIntersecting: si }))); }
        observe(el) { observados.add(el); }
        unobserve(el) { observados.delete(el); }
        disconnect() { observados.clear(); }
    };
    const r = W.abrir(o);
    const artes = abierta().querySelectorAll('[data-arte]');
    assert.equal(observados.size, 3, 'mira cada arte');
    assert.ok(!W.vivoAbierto().corriendo(), 'hasta saber qué se ve, ningún cuadro');
    avisar([artes[0]], true);
    assert.ok(W.vivoAbierto().corriendo(), 'uno a la vista: anima');
    const antes = W.vivoAbierto().estado().map(e => e.reloj);
    const textos = [...artes].map(a => a.textContent);
    cuadros(60);
    const despues = W.vivoAbierto().estado();
    assert.ok(despues[0].reloj > antes[0], 'el que se ve, avanza');
    assert.deepEqual([despues[1].reloj, despues[2].reloj], [antes[1], antes[2]], 'los que no se ven, ni avanzan');
    assert.deepEqual([artes[1].textContent, artes[2].textContent], [textos[1], textos[2]], 'ni se dibujan');
    avisar([artes[0]], false);
    cuadros(2);
    assert.equal(pedidos.size, 0, 'ninguno a la vista: ningún requestAnimationFrame');
    avisar([artes[2]], true);
    assert.ok(W.vivoAbierto().corriendo(), 'vuelve uno a la vista: sigue');
    tecla('Escape');
    await contesta(r);
    assert.equal(observados.size, 0, 'cerrada, deja de mirar');
    assert.equal(pedidos.size, 0);
    delete globalThis.IntersectionObserver;
}

// ── 5. el CSS ──
{
    const c = css('mundos');
    assert.doesNotMatch(c, /#[0-9a-f]{3,8}\b|rgb\(/i, 'sin colores fijos: los del tema y los del mundo');
    assert.doesNotMatch(c.replace(/border-radius: 0;/g, ''), /border-radius/, 'sin esquinas redondeadas');
    assert.match(c, /@media \(prefers-reduced-motion: reduce\) \{[\s\S]*\.mt-arte,[\s\S]*transition: none;/, 'con «reducir movimiento», sin transiciones');
    // lo que se mueve es de letras: nada se inclina, crece, brilla borroso ni barre por CSS
    assert.doesNotMatch(c, /transform|text-shadow|@keyframes|mt-barrido/, 'nada de CSS que se mueva: la ola es de letras');
    // muchos: se desplazan entre la línea de la cabecera y la del pie, con alto máximo
    assert.match(c, /& \.ventana-cuerpo \{[^}]*max-height: var\(--mundos-alto\);[^}]*overflow: hidden auto;[^}]*border-top: var\(--borde\);/);
    assert.match(c, /\.mt-grilla \{[^}]*gap: 1px;[^}]*background: var\(--linea\);/, 'las líneas entre tarjetas: las de siempre');
    assert.match(c, /\.angosto \.mt-grilla \{ grid-template-columns: minmax\(0, 1fr\); \}/, 'en el teléfono, una bajo otra');
    const tokens = css('tokens');
    for (const t of new Set(c.match(/--mundos-[a-z-]+/g))) assert.ok(tokens.includes(`${t}:`), `${t}, en tokens.css`);
    assert.match(readFileSync(path.join(aqui, '..', 'scripts', 'navegador.mjs'), 'utf8'), /'boton', 'mundos',/, 'en el marco de la página');
}

console.log('prueba:mundos-ventana ok');
