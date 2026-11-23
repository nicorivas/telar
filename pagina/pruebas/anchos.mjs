// Prueba del ancho de la barra de hilos y de la ficha, a mano (src/web/anchos.ts): las dos franjas de agarre, el arrastre
// con pointer events (en vivo, con sus topes y el centro de al menos 480 px), el doble clic que vuelve al de fábrica, lo
// que se recuerda por pantalla (y sin almacén, o con uno roto), que plegada no se arrastre ni pierda lo elegido, que en el
// teléfono no haya, y que la terminal reciba un solo ajuste al soltar (y ninguno mientras se arrastra). Y el borde de la
// terminal del centro: su franja (en el borde que toca según su posición), el arrastre de columna en columna, sus topes
// (80 columnas, o lo que quepa; llegar al tope es «todo»), el doble clic que vuelve a lo de ⚙ terminal, lo recordado por
// pantalla junto a la barra y la ficha, que ⚙ terminal lo olvide, y un solo resize a tmux al soltar. Corre en Node, con
// un DOM mínimo que hace la disposición de la página (la barra, la ficha y el centro): npm run prueba:anchos
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const outfile = path.join(mkdtempSync(path.join(tmpdir(), 'anchos-')), 'anchos.cjs');
await build({ entryPoints: [path.join(aqui, '..', 'src', 'web', 'anchos.ts')], bundle: true, platform: 'node', format: 'cjs', outfile,
    logLevel: 'warning' });
const A = require(outfile);

// ── los topes, solos ──
assert.deepEqual(A.topes('barra', 1440, 0), { min: 200, max: 648 }, 'sin ficha: el 45% de la ventana');
assert.deepEqual(A.topes('barra', 1440, 600), { min: 200, max: 360 }, 'con la ficha, el centro conserva 480');
assert.deepEqual(A.topes('lado', 1440, 300), { min: 240, max: 648 });
assert.deepEqual(A.topes('barra', 600, 300), { min: 200, max: 200 }, 'ventana chica: gana el mínimo');
assert.equal(A.acotar(10, { min: 200, max: 400 }), 200);
assert.equal(A.acotar(999, { min: 200, max: 400 }), 400);
assert.equal(A.acotar(300.4, { min: 200, max: 400 }), 300);
assert.equal(A.clavePantalla({ width: 3008, height: 1692 }), '3008x1692');
assert.deepEqual(A.leer(null), {});
assert.deepEqual(A.leer({ getItem: () => '{roto' }), {}, 'lo que no se entiende: nada');
assert.deepEqual(A.leer({ getItem: () => '[1]' }), {});
assert.deepEqual(A.leer({ getItem: () => { throw new Error('sin permiso'); } }), {});

// ── un DOM mínimo: elementos con clases, dataset, estilo con variables, eventos y la disposición de la página ──
class Estilo {
    constructor() { this.v = {}; }
    setProperty(k, x) { this.v[k] = String(x); }
    removeProperty(k) { delete this.v[k]; }
    getPropertyValue(k) { return this.v[k] ?? ''; }
}
class Nodo {
    constructor(tag) {
        this.tagName = tag.toUpperCase(); this.children = []; this.parentElement = null; this.oyentes = {}; this.dataset = {};
        this.style = new Estilo(); this.atributos = {}; this.hidden = false; this.id = ''; this.title = ''; this.capturado = null;
        const clases = new Set();
        this.clases = clases;
        this.classList = { contains: c => clases.has(c), add: c => clases.add(c), remove: c => clases.delete(c),
            toggle: (c, si = !clases.has(c)) => { if (si) clases.add(c); else clases.delete(c); return si; } };
    }
    set className(v) { this.clases.clear(); for (const c of v.split(/\s+/).filter(Boolean)) this.clases.add(c); }
    get className() { return [...this.clases].join(' '); }
    setAttribute(k, v) { this.atributos[k] = v; }
    appendChild(n) { n.parentElement = this; this.children.push(n); return n; }
    insertAdjacentElement(donde, n) {
        assert.equal(donde, 'afterend');
        const p = this.parentElement; n.parentElement = p; p.children.splice(p.children.indexOf(this) + 1, 0, n); return n;
    }
    addEventListener(tipo, fn) { (this.oyentes[tipo] ??= []).push(fn); }
    disparar(tipo, datos = {}) {
        const e = { type: tipo, button: 0, pointerId: 1, clientX: 0, ...datos, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } };
        for (const fn of this.oyentes[tipo] ?? []) fn(e);
        return e;
    }
    setPointerCapture(id) { this.capturado = id; }
    releasePointerCapture(id) { if (this.capturado === id) { this.capturado = null; this.disparar('lostpointercapture', { pointerId: id }); } }
    getBoundingClientRect() { return { width: anchoDe(this) }; }
}

/** Arma la página: body, #barra, #marcos con #lado. Devuelve el entorno y lo que hace falta para mirarla. */
function pagina({ vista = 1440, pantalla = { width: 1440, height: 900 }, almacen = memoria() } = {}) {
    const body = new Nodo('body'), barra = new Nodo('aside'), marcos = new Nodo('div'), lado = new Nodo('aside');
    barra.id = 'barra'; lado.id = 'lado'; marcos.id = 'marcos';
    body.appendChild(barra); body.appendChild(marcos); marcos.appendChild(lado);
    const ventana = new Nodo('#window');
    ventana.innerWidth = vista;
    ventana.eventos = [];
    ventana.dispatchEvent = e => { ventana.eventos.push(e.type); for (const fn of ventana.oyentes[e.type] ?? []) fn(e); return true; };
    disposicion = { body, barra, lado, ventana };
    const p = { body, barra, lado, marcos, ventana, almacen, pantalla: () => p.laPantalla, crear: tag => new Nodo(tag),
        evento: () => ({ type: A.EVENTO }) };
    p.laPantalla = pantalla;
    p.montado = A.montar(p);
    p.franja = cual => [...marcos.children].find(n => n.id === `tirador-${cual}`);
    return p;
}
/** la disposición de la página que se mira: lo que diría marco.css */
let disposicion;
function anchoDe(el) {
    const { body, barra, lado, ventana } = disposicion;
    const vw = ventana.innerWidth, px = v => parseFloat(body.style.getPropertyValue(v));
    if (el === barra) {
        if (body.dataset.barra === 'plegada') return 40;
        return Number.isFinite(px('--barra-ancho')) ? px('--barra-ancho') : Math.max(240, 0.22 * vw);
    }
    if (el === lado) {
        if (lado.hidden) return 0;
        if (lado.classList.contains('plegado')) return 24;
        return Number.isFinite(px('--lado-ancho')) ? px('--lado-ancho') : Math.min(46 * 8, 0.4 * vw);
    }
    return 0;
}
function memoria() {
    const d = {};
    return { d, getItem: k => (k in d ? d[k] : null), setItem: (k, v) => { d[k] = String(v); } };
}
const variable = (p, v) => p.body.style.getPropertyValue(v);
/** Arrastrar la franja de `cual` desde x hasta cada uno de `pasos`, y soltar (o no). Devuelve el ancho tras cada paso. */
function arrastrar(p, cual, desde, pasos, { soltar = true, enCadaPaso = () => {} } = {}) {
    const f = p.franja(cual);
    f.disparar('pointerdown', { clientX: desde });
    const vistos = [];
    for (const x of pasos) { f.disparar('pointermove', { clientX: x }); vistos.push(anchoDe(cual === 'barra' ? p.barra : p.lado)); enCadaPaso(); }
    if (soltar) f.disparar('pointerup', { clientX: pasos.at(-1) ?? desde });
    return vistos;
}

// ── las franjas ──
{
    const p = pagina();
    const barra = p.franja('barra'), lado = p.franja('lado');
    assert.ok(barra && lado, 'las dos franjas, en #marcos');
    assert.equal(p.marcos.children[p.marcos.children.indexOf(p.lado) + 1], lado, 'la de la ficha, justo después de ella (el CSS la esconde con la ficha)');
    for (const f of [barra, lado]) {
        assert.equal(f.className, 'tirador');
        assert.equal(f.atributos.role, 'separator');
        assert.equal(f.atributos['aria-orientation'], 'vertical');
        assert.match(f.title, /doble clic/);
    }
    assert.equal(variable(p, '--barra-ancho'), '', 'sin nada recordado: el de fábrica');
    assert.equal(variable(p, '--lado-ancho'), '');
}

// ── arrastrar la barra: en vivo, con la captura del puntero, la línea marcada y un solo aviso al soltar ──
{
    const p = pagina();
    const f = p.franja('barra');
    assert.equal(anchoDe(p.barra), 316.8, 'la de fábrica: el 22% de 1440');
    const e = f.disparar('pointerdown', { clientX: 317 });
    assert.ok(e.defaultPrevented, 'no selecciona texto');
    assert.equal(f.capturado, 1, 'captura el puntero: el movimiento llega aunque se salga de la franja');
    assert.ok(A.arrastrando());
    assert.equal(p.body.dataset.arrastra, 'barra', 'la línea con el acento (marco.css)');
    const vistos = [];
    for (const x of [340, 380, 417]) { f.disparar('pointermove', { clientX: x }); vistos.push(anchoDe(p.barra)); }
    assert.deepEqual(vistos, [340, 380, 417], 'en vivo, píxel a píxel (con lo que tenía al empezar)');
    assert.deepEqual(p.ventana.eventos, [], 'mientras se arrastra, ningún aviso');
    assert.equal(p.almacen.d[A.CLAVE], undefined, 'ni se guarda en cada píxel');
    f.disparar('pointerup', { clientX: 417 });
    assert.ok(!A.arrastrando());
    assert.equal(p.body.dataset.arrastra, undefined);
    assert.equal(f.capturado, null, 'suelta el puntero');
    assert.deepEqual(p.ventana.eventos, [A.EVENTO], 'al soltar, un aviso (y uno solo, aunque llegue lostpointercapture)');
    assert.deepEqual(JSON.parse(p.almacen.d[A.CLAVE]), { '1440x900': { barra: 417 } }, 'recordado para esta pantalla');
}

// ── los topes: la barra entre 200 y lo que deja 480 al centro; la ficha crece hacia la izquierda ──
{
    const p = pagina();
    p.lado.hidden = true;   // el dashboard: sin ficha
    assert.deepEqual(arrastrar(p, 'barra', 317, [0]), [200], 'el mínimo');
    assert.deepEqual(arrastrar(p, 'barra', 200, [1400]), [648], 'el máximo, sin ficha: el 45%');
    const q = pagina();
    assert.equal(anchoDe(q.lado), 368, 'la ficha de fábrica: 46ch');
    assert.deepEqual(arrastrar(q, 'lado', 1072, [1000, 900]), [440, 540], 'hacia la izquierda, más ancha');
    assert.deepEqual(arrastrar(q, 'barra', 317, [1400]), [420], 'la barra, con la ficha de 540: el centro conserva 480');
    assert.equal(1440 - anchoDe(q.barra) - anchoDe(q.lado), 480);
    assert.deepEqual(arrastrar(q, 'lado', 900, [1400]), [240], 'la ficha, su mínimo');
    assert.deepEqual(arrastrar(q, 'lado', 1200, [0]), [540], 'y su máximo con la barra de 420');
}

// ── la terminal: un solo ajuste al soltar, ninguno mientras se arrastra (lo que hace web/terminal.ts) ──
{
    const p = pagina();
    let ajustes = 0, mandados = 0, cols = 0;
    // como la terminal: el ajuste mide el centro y le manda a tmux el tamaño nuevo solo si cambió
    const ajustar = () => {
        ajustes++;
        const c = Math.floor((p.ventana.innerWidth - anchoDe(p.barra) - anchoDe(p.lado)) / 8);
        if (c !== cols) { cols = c; mandados++; }
    };
    const observador = () => { if (!A.arrastrando()) ajustar(); };   // el ResizeObserver de la caja
    p.ventana.addEventListener(A.EVENTO, ajustar);
    ajustar(); ajustes = 0; mandados = 0;
    arrastrar(p, 'barra', 317, [330, 360, 390, 420, 450], { soltar: false, enCadaPaso: observador });
    assert.equal(ajustes, 0, 'el observador avisa en cada píxel y no se mide');
    p.franja('barra').disparar('pointerup', { clientX: 450 });
    observador();   // el aviso del observador que llega después de soltar, en el mismo cuadro
    assert.equal(mandados, 1, 'un solo resize a tmux');
    assert.equal(cols, Math.floor((1440 - 450 - 368) / 8));
}

// ── un clic sin mover: nada se guarda ni se avisa ──
{
    const p = pagina();
    arrastrar(p, 'barra', 317, []);
    arrastrar(p, 'barra', 317, [317.4]);
    assert.deepEqual(p.ventana.eventos, []);
    assert.equal(p.almacen.d[A.CLAVE], undefined);
    assert.equal(variable(p, '--barra-ancho'), '');
}

// ── el doble clic: el de fábrica, olvidado para esta pantalla, y un aviso ──
{
    const p = pagina();
    arrastrar(p, 'barra', 317, [500]);
    arrastrar(p, 'lado', 1072, [1000]);
    p.ventana.eventos.length = 0;
    p.franja('barra').disparar('dblclick');
    assert.equal(variable(p, '--barra-ancho'), '', 'la barra, la de fábrica');
    assert.equal(variable(p, '--lado-ancho'), '440px', 'la ficha no se toca');
    assert.deepEqual(JSON.parse(p.almacen.d[A.CLAVE]), { '1440x900': { lado: 440 } });
    assert.deepEqual(p.ventana.eventos, [A.EVENTO]);
    p.franja('lado').disparar('dblclick');
    assert.deepEqual(JSON.parse(p.almacen.d[A.CLAVE]), {}, 'sin nada: la pantalla se va de lo recordado');
}

// ── recordar: por pantalla, dentro de los topes de ahora; sin almacén o con uno roto, el de fábrica ──
{
    const almacen = memoria();
    almacen.d[A.CLAVE] = JSON.stringify({ '1440x900': { barra: 300, lado: 400 }, '3008x1692': { barra: 520 } });
    const p = pagina({ almacen });
    assert.equal(variable(p, '--barra-ancho'), '300px', 'lo del laptop');
    assert.equal(variable(p, '--lado-ancho'), '400px');
    const m = pagina({ almacen, vista: 3008, pantalla: { width: 3008, height: 1692 } });
    assert.equal(variable(m, '--barra-ancho'), '520px', 'lo del monitor de 27"');
    assert.equal(variable(m, '--lado-ancho'), '', 'la ficha no se eligió ahí: la de fábrica');
    // la ventana se mueve del laptop al monitor: lo de esa pantalla, al tiro
    p.laPantalla = { width: 3008, height: 1692 }; p.ventana.innerWidth = 3008;
    for (const fn of p.ventana.oyentes.resize) fn({ type: 'resize' });
    assert.equal(variable(p, '--barra-ancho'), '520px');
    assert.equal(variable(p, '--lado-ancho'), '');
    // una ventana más chica que lo recordado: dentro de los topes de ahora, sin olvidarlo
    const chica = pagina({ almacen, vista: 900 });
    assert.equal(variable(chica, '--barra-ancho'), '200px', 'con la ficha de fábrica (360), el centro pide: gana el mínimo');
    assert.equal(variable(chica, '--lado-ancho'), '240px', 'y la ficha, el suyo');
    assert.deepEqual(JSON.parse(almacen.d[A.CLAVE])['1440x900'], { barra: 300, lado: 400 }, 'lo recordado sigue');

    const roto = memoria(); roto.d[A.CLAVE] = '{roto';
    assert.equal(variable(pagina({ almacen: roto }), '--barra-ancho'), '');
    const sin = pagina({ almacen: null });
    assert.deepEqual(arrastrar(sin, 'barra', 317, [400]), [400], 'sin almacén se arrastra igual (vale hasta recargar)');
    const quejon = { getItem: () => { throw new Error('bloqueado'); }, setItem: () => { throw new Error('bloqueado'); } };
    const q = pagina({ almacen: quejon });
    assert.deepEqual(arrastrar(q, 'barra', 317, [400]), [400], 'un almacén que se queja no rompe nada');
    assert.deepEqual(q.ventana.eventos, [A.EVENTO]);
}

// ── plegada: no se arrastra, y lo elegido vuelve al desplegarla; la ficha plegada u oculta, tampoco ──
{
    const p = pagina();
    arrastrar(p, 'barra', 317, [450]);
    p.body.dataset.barra = 'plegada';
    assert.equal(anchoDe(p.barra), 40);
    arrastrar(p, 'barra', 40, [600]);
    assert.equal(variable(p, '--barra-ancho'), '450px', 'plegada no se arrastra, y lo elegido queda');
    p.body.dataset.barra = 'abierta';
    assert.equal(anchoDe(p.barra), 450, 'al desplegarla, el ancho elegido');
    p.lado.classList.add('plegado');
    arrastrar(p, 'lado', 1400, [1000]);
    assert.equal(variable(p, '--lado-ancho'), '');
    p.lado.classList.remove('plegado'); p.lado.hidden = true;
    arrastrar(p, 'lado', 1400, [1000]);
    assert.equal(variable(p, '--lado-ancho'), '');
    assert.ok(!A.arrastrando());
}

// ── la barra plegada u oculta no se lleva la franja de la ficha: esa sigue y arrastra (y en marco.css, lo que esconde la
//    barra plegada es solo su propia franja) ──
for (const estado of ['plegada', 'oculta']) {
    const p = pagina();
    p.body.dataset.barra = estado;
    assert.deepEqual(arrastrar(p, 'lado', 1072, [1000]), [440], `con la barra ${estado}, la ficha se arrastra`);
    assert.equal(variable(p, '--lado-ancho'), '440px');
    p.franja('lado').disparar('dblclick');
    assert.equal(variable(p, '--lado-ancho'), '', 'y su doble clic vuelve al de fábrica');
}
{
    const css = readFileSync(path.join(aqui, '..', 'media', 'css', 'marco.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
    const selectores = [...css.matchAll(/([^{}]+)\{([^}]*)\}/g)]
        .filter(([, , cuerpo]) => /display:\s*none/.test(cuerpo))
        .flatMap(([, sel]) => sel.split(/,(?![^(]*\))/).map(x => x.trim()));
    const porBarra = selectores.filter(x => /data-barra/.test(x) && /tirador/.test(x));
    assert.ok(porBarra.length > 0, 'marco.css esconde la franja de la barra plegada');
    for (const x of porBarra) assert.match(x, /#tirador-barra$/, `con la barra plegada, solo su franja se esconde: «${x}»`);
    assert.ok(!selectores.some(x => /data-barra/.test(x) && /\.tirador\b/.test(x)), 'ninguna regla de la barra esconde todas las franjas');
}

// ── en el teléfono no hay: la barra ahí es su propia pantalla ──
{
    const p = pagina({ vista: 390, pantalla: { width: 390, height: 844 } });
    p.body.classList.add('angosto');
    arrastrar(p, 'barra', 100, [300]);
    p.franja('barra').disparar('dblclick');
    assert.equal(variable(p, '--barra-ancho'), '');
    assert.deepEqual(p.ventana.eventos, []);
}

// ── la terminal del centro: el borde que se arrastra (montarTerminal) ──
assert.equal(A.caben(1200, 8, 14), 146, 'lo que cabe: una columna de aire a cada lado y la barra de desplazamiento');
assert.deepEqual(A.topesTerminal(1200, 8, 14), { min: 80, max: 146 });
assert.deepEqual(A.topesTerminal(600, 8, 14), { min: 71, max: 71 }, 'un centro chico: lo que quepa, aunque sea menos de 80');
assert.equal(A.columnasRecordadas(null, { width: 1440, height: 900 }), undefined);

/** Una terminal como la de web/terminal.ts: la caja (el centro), el marco del ancho de sus columnas y la franja en su
 *  borde. `ajustar` mide como ella (lo elegido arrastrando, o lo de ⚙ terminal; 0, todo) y cuenta lo que manda a tmux. */
function terminal({ caja = 1200, posicion = 'centro', fabrica = 130, almacen = memoria(), pantalla = { width: 1440, height: 900 }, celda = 8 } = {}) {
    const body = new Nodo('body'), cajaN = new Nodo('div'), marco = new Nodo('div');
    cajaN.clientWidth = caja; cajaN.appendChild(marco); body.appendChild(cajaN);
    const ventana = new Nodo('#window');
    ventana.eventos = [];
    ventana.dispatchEvent = e => { ventana.eventos.push(e.type); for (const fn of ventana.oyentes[e.type] ?? []) fn(e); return true; };
    const t = { body, caja: cajaN, marco, ventana, almacen, crear: tag => new Nodo(tag), evento: () => ({ type: A.EVENTO }),
        barra: 14, celda: () => t.laCelda, posicion: () => t.laPosicion, pantalla: () => t.laPantalla,
        laCelda: celda, laPosicion: posicion, laPantalla: pantalla, fabrica, cols: 0, mandados: [] };
    t.borde = A.montarTerminal(t);
    t.franja = marco.children.find(n => n.id === 'tirador-terminal');
    t.ajustar = () => {
        const quiere = (t.borde.columnas() ?? t.fabrica) || 10000;
        const cols = Math.max(20, Math.min(quiere, A.caben(cajaN.clientWidth, t.laCelda, 14)));
        marco.style.width = `${Math.ceil(cols * t.laCelda + 14)}px`;
        if (cols !== t.cols) { t.cols = cols; t.mandados.push(cols); }
    };
    t.observador = () => { if (!A.arrastrando()) t.ajustar(); };   // el ResizeObserver de la caja
    ventana.addEventListener(A.EVENTO, t.ajustar);
    t.ajustar(); t.mandados.length = 0;
    t.ancho = () => parseFloat(marco.style.width);
    t.arrastrar = (desde, pasos, { soltar = true } = {}) => {
        t.franja.disparar('pointerdown', { clientX: desde });
        const vistos = [];
        for (const x of pasos) { t.franja.disparar('pointermove', { clientX: x }); vistos.push(t.ancho()); t.observador(); }
        if (soltar) { t.franja.disparar('pointerup', { clientX: pasos.at(-1) ?? desde }); t.observador(); }
        return vistos;
    };
    return t;
}
const colsDe = px => (px - 14) / 8;

// la franja, en el borde que no está pegado
{
    const t = terminal();
    assert.ok(t.franja, 'la franja, en el marco de la terminal');
    assert.equal(t.franja.className, 'tirador');
    assert.equal(t.franja.atributos.role, 'separator');
    assert.match(t.franja.title, /doble clic: el de ⚙ terminal/);
    assert.equal(t.franja.dataset.borde, 'der', 'centrada: el borde derecho');
    assert.equal(t.cols, 130, 'de fábrica, lo de ⚙ terminal');
    t.laPosicion = 'derecha'; t.borde.colocar();
    assert.equal(t.franja.dataset.borde, 'izq', 'a la derecha va pegada: el borde izquierdo');
    t.laPosicion = 'izquierda'; t.borde.colocar();
    assert.equal(t.franja.dataset.borde, 'der');
}

// centrada: en vivo, de columna en columna, creciendo hacia los dos lados; nada a tmux hasta soltar, y una vez
{
    const t = terminal();
    t.franja.disparar('pointerdown', { clientX: 1000 });
    assert.ok(A.arrastrando(), 'mientras, lo demás que mide espera');
    assert.equal(t.body.dataset.arrastra, 'terminal');
    assert.equal(t.marco.dataset.estira, 'der', 'la línea de ese borde, con el acento; el marco recorta');
    const vistos = [];
    for (const x of [1004, 1008, 1013, 1016]) { t.franja.disparar('pointermove', { clientX: x }); vistos.push(colsDe(t.ancho())); t.observador(); }
    assert.deepEqual(vistos, [131, 132, 133, 134], 'centrada, el ancho cambia el doble que el puntero: el borde lo sigue');
    assert.deepEqual(t.mandados, [], 'nada a tmux mientras se arrastra');
    assert.deepEqual(t.ventana.eventos, []);
    assert.equal(t.almacen.d[A.CLAVE], undefined, 'ni se guarda en cada píxel');
    t.franja.disparar('pointerup', { clientX: 1016 }); t.observador();
    assert.ok(!A.arrastrando());
    assert.equal(t.marco.dataset.estira, undefined);
    assert.equal(t.franja.capturado, null);
    assert.deepEqual(t.ventana.eventos, [A.EVENTO], 'al soltar, un aviso');
    assert.deepEqual(t.mandados, [134], 'un solo resize a tmux, con las columnas nuevas');
    assert.deepEqual(JSON.parse(t.almacen.d[A.CLAVE]), { '1440x900': { terminal: 134 } }, 'recordado para esta pantalla, en columnas');
    assert.equal(t.borde.columnas(), 134);
}

// a la izquierda crece lo que se mueve el puntero; a la derecha se tira del borde izquierdo
{
    const i = terminal({ posicion: 'izquierda' });
    assert.deepEqual(i.arrastrar(1054, [1070]).map(colsDe), [132]);
    const d = terminal({ posicion: 'derecha' });
    assert.deepEqual(d.arrastrar(146, [130]).map(colsDe), [132], 'hacia la izquierda, más ancha');
    assert.equal(d.marco.dataset.estira, undefined);
    assert.deepEqual(d.mandados, [132]);
}

// los topes: 80 columnas, y todo el centro (que se recuerda como «todo»)
{
    const t = terminal();
    assert.deepEqual(t.arrastrar(1000, [0]).map(colsDe), [80], 'el mínimo');
    assert.deepEqual(t.mandados, [80]);
    assert.equal(t.borde.columnas(), 80);
    assert.deepEqual(t.arrastrar(1000, [5000]).map(colsDe), [146], 'el máximo: lo que cabe en el centro');
    assert.equal(t.borde.columnas(), 0, 'llegar al tope es «todo»');
    assert.deepEqual(t.mandados, [80, 146]);
    t.caja.clientWidth = 1600; t.observador();   // se cerró la ficha: todo, de nuevo
    assert.equal(t.cols, 196, 'con «todo», el centro entero al crecer');
    const chica = terminal({ caja: 600 });
    assert.equal(chica.cols, 71, 'un centro chico: lo que quepa');
    assert.deepEqual(chica.arrastrar(500, [0]).map(colsDe), [71], 'y no se arrastra a menos de lo que cabe ni a más');
}

// un clic sin mover: nada; el doble clic: lo de ⚙ terminal, olvidado para esta pantalla
{
    const t = terminal();
    t.arrastrar(1000, []);
    t.arrastrar(1000, [1000.5]);
    assert.deepEqual(t.ventana.eventos, []);
    assert.equal(t.almacen.d[A.CLAVE], undefined);
    assert.equal(t.marco.dataset.estira, undefined, 'la línea vuelve aunque no se haya movido');
    t.arrastrar(1000, [960]);
    assert.equal(t.cols, 120, '40 px a la izquierda, centrada: 10 columnas menos');
    t.ventana.eventos.length = 0; t.mandados.length = 0;
    t.franja.disparar('dblclick');
    assert.deepEqual(t.ventana.eventos, [A.EVENTO]);
    assert.equal(t.cols, 130, 'vuelve a lo de ⚙ terminal');
    assert.deepEqual(t.mandados, [130], 'una vez a tmux');
    assert.deepEqual(JSON.parse(t.almacen.d[A.CLAVE]), {});
    t.fabrica = 0; t.ajustar();
    assert.equal(t.cols, 146, '⚙ terminal en «todo»: el centro entero');
}

// lo recordado: por pantalla, junto a la barra y la ficha; ⚙ terminal lo olvida en todas, sin tocar lo demás
{
    const almacen = memoria();
    almacen.d[A.CLAVE] = JSON.stringify({ '1440x900': { barra: 300 }, '3008x1692': { terminal: 160, lado: 500 } });
    const t = terminal({ almacen });
    assert.equal(t.cols, 130, 'en el laptop no se arrastró: lo de ⚙ terminal');
    t.arrastrar(1000, [960]);
    assert.deepEqual(JSON.parse(almacen.d[A.CLAVE])['1440x900'], { barra: 300, terminal: 120 }, 'junto a la barra');
    const m = terminal({ almacen, caja: 2400, pantalla: { width: 3008, height: 1692 } });
    assert.equal(m.cols, 160, 'en el monitor, lo de ahí');
    t.laPantalla = { width: 3008, height: 1692 }; t.caja.clientWidth = 2400; t.observador();
    assert.equal(t.cols, 160, 'la ventana se mueve al monitor: lo de esa pantalla');
    // la barra vuelve a la de fábrica: lo de la terminal sigue
    const p = pagina({ almacen });
    p.franja('barra').disparar('dblclick');
    assert.deepEqual(JSON.parse(almacen.d[A.CLAVE])['1440x900'], { terminal: 120 });
    A.olvidarTerminal(almacen);
    assert.deepEqual(JSON.parse(almacen.d[A.CLAVE]), { '3008x1692': { lado: 500 } }, '⚙ terminal: lo arrastrado, olvidado en todas');
    t.observador();
    assert.equal(t.cols, 130);
    almacen.d[A.CLAVE] = JSON.stringify({ '1440x900': { terminal: 'ancha' } });
    assert.equal(A.columnasRecordadas(almacen, { width: 1440, height: 900 }), undefined, 'lo que no se entiende: lo de ⚙ terminal');
    const sin = terminal({ almacen: null });
    assert.deepEqual(sin.arrastrar(1000, [1016]).map(colsDe), [134], 'sin almacén se arrastra igual');
    assert.deepEqual(sin.mandados, [], 'pero no se recuerda: al medirse, lo de ⚙ terminal');
    A.olvidarTerminal(null);
}

// arrastrar la barra mientras hay terminal: la terminal espera igual; y en el teléfono, o sin medidas, no hay arrastre
{
    const t = terminal();
    const p = pagina();
    p.franja('barra').disparar('pointerdown', { clientX: 317 });
    t.franja.disparar('pointerdown', { clientX: 1000 });
    t.franja.disparar('pointermove', { clientX: 1100 });
    assert.equal(t.cols, 130, 'una a la vez: con la barra en curso, la terminal no empieza');
    p.franja('barra').disparar('pointerup', { clientX: 317 });
    const tel = terminal();
    tel.body.classList.add('angosto');
    tel.arrastrar(1000, [1100]);
    tel.franja.disparar('dblclick');
    assert.deepEqual(tel.ventana.eventos, [], 'en el teléfono no hay');
    const nueva = terminal();
    nueva.laCelda = null;
    nueva.arrastrar(1000, [1100]);
    assert.deepEqual(nueva.ventana.eventos, [], 'xterm sin medir todavía: tampoco');
    assert.ok(!A.arrastrando());
}

console.log('prueba:anchos ok');
