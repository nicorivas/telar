// Prueba de abrir una dirección de afuera en una pestaña nueva (src/web/abrir.ts, y por él web/ui.ts `abrirExterno`,
// los hipervínculos de la terminal, web/rutas-agente.ts `abrirHipervinculo`, y el visor), con un DOM (happy-dom) y un
// navegador de mentira que hace lo que Safari: window.open abre solo mientras dura el evento de un clic o una tecla
// («el gesto»); fuera, devuelve null sin decir nada.
// · El camino síncrono: en el gesto se abre ahí mismo (una sola llamada a window.open, dentro del gesto), sin `noopener`
//   en las opciones (para saber si abrió), con el `opener` cortado y la dirección cargada desde la pestaña nueva por un
//   enlace `noreferrer`. Un hipervínculo de la terminal (OSC 8) abre así, sin nada que espere antes.
// · Si el navegador no deja (fuera del gesto): un aviso que lo dice, con un botón «Abrir» que abre en su mismo clic o
//   con ⏎; cancelar no abre nada. Una dirección que no es web va como antes; `javascript:` nunca.
// Lo mismo en WebKit, Chrome y Firefox de verdad: npm run prueba:abrir-webkit; con el bloqueo de Safari de verdad (un
// WKWebView, macOS): npm run prueba:abrir-safari. Esta: npm run prueba:abrir
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { Window } from 'happy-dom';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const src = path.join(aqui, '..', 'src');
const outfile = path.join(mkdtempSync(path.join(tmpdir(), 'abrir-')), 'abrir.cjs');
await build({
    stdin: { contents: "export * as A from './web/abrir'; export { abrirExterno } from './web/ui'; export { abrirHipervinculo } from './web/rutas-agente';", resolveDir: src, loader: 'ts' },
    bundle: true, platform: 'node', format: 'cjs', outfile, logLevel: 'warning',
});

const w = new Window({ url: 'http://telar.prueba/?k=la-llave' });
for (const k of ['window', 'document', 'navigator', 'CSS', 'Element', 'HTMLElement', 'HTMLInputElement', 'HTMLTextAreaElement', 'HTMLDialogElement', 'Node',
    'NodeFilter', 'Event', 'KeyboardEvent', 'MouseEvent', 'PointerEvent', 'getComputedStyle', 'requestAnimationFrame', 'innerWidth', 'innerHeight', 'Blob', 'location', 'matchMedia', 'localStorage', 'sessionStorage', 'getSelection', 'MutationObserver', 'ResizeObserver', 'DOMParser', 'customElements']) 
    Object.defineProperty(globalThis, k, { value: k === 'window' ? w : typeof w[k] === 'function' && /^[a-z]/.test(k) ? w[k].bind(w) : w[k] ?? globalThis[k], configurable: true, writable: true });
w.fetch = async () => ({ ok: false, json: async () => ({}) });
globalThis.fetch = w.fetch;
const { A, abrirExterno, abrirHipervinculo } = require(outfile);
const dormir = ms => new Promise(r => setTimeout(r, ms));

// ── el navegador de mentira ──
let enGesto = false;
const gesto = f => { enGesto = true; try { return f(); } finally { enGesto = false; } };
let llamadas = [];   // cada window.open: con qué, y si fue en el gesto
let abiertas = [];   // las pestañas que quedaron: adónde fueron, con qué rel, y su opener
w.open = (url = '', destino = '', opciones = '') => {
    llamadas.push({ url, destino, opciones, enGesto });
    if (!enGesto) return null;
    const doc = w.document.implementation.createHTMLDocument('');
    const pestana = { url, rel: null, opener: w, document: doc, location: { replace: u => { pestana.url = u; pestana.rel = 'location'; } } };
    doc.addEventListener('click', e => {
        const a = e.target.closest?.('a');
        if (!a) return;
        e.preventDefault();
        pestana.url = a.getAttribute('href'); pestana.rel = a.rel;
    });
    abiertas.push(pestana);
    return opciones.includes('noopener') ? null : pestana;
};
const limpiar = () => { llamadas = []; abiertas = []; };
const boton = (a = 'b0') => document.querySelector(`dialog [data-accion="${a}"]`);

// ── el camino síncrono ──
{
    limpiar();
    assert.equal(gesto(() => A.abrirYa('https://ejemplo.prueba/a?b=1')), true, 'en el gesto abre');
    assert.equal(llamadas.length, 1, 'una sola llamada');
    assert.equal(llamadas[0].enGesto, true, 'dentro del gesto');
    assert.doesNotMatch(llamadas[0].opciones, /noopener/, 'sin noopener: así se sabe si abrió');
    assert.equal(abiertas[0].url, 'https://ejemplo.prueba/a?b=1', 'la dirección, cargada en la pestaña nueva');
    assert.equal(abiertas[0].rel, 'noreferrer', 'por un enlace noreferrer: no lleva la dirección de la página (ni su llave)');
    assert.equal(abiertas[0].opener, null, 'sin acceso de vuelta a la página');

    // ui.abrirExterno abre antes de cualquier await: en el mismo gesto
    limpiar();
    const r = gesto(() => abrirExterno('https://ejemplo.prueba/ui'));
    assert.equal(llamadas.length, 1, 'abrirExterno abrió sin salir del gesto');
    assert.equal(await r, true);
    assert.equal(document.querySelector('dialog'), null, 'y no pregunta nada');

    // el hipervínculo de la terminal (OSC 8, lo que deja Claude Code): lo mismo, sin nada que espere antes
    limpiar();
    gesto(() => abrirHipervinculo('https://ejemplo.prueba/osc8', { hilo: 'x', maquina: '' }));
    assert.deepEqual(llamadas.map(l => l.enGesto), [true], 'el hipervínculo abre en el gesto del clic');
    assert.equal(abiertas[0].url, 'https://ejemplo.prueba/osc8');
    await dormir(0);
    assert.equal(document.querySelector('dialog'), null);
}

// ── fuera del gesto: un aviso que lo dice, y su botón abre en su mismo clic o con ⏎ ──
for (const como of ['clic', '⏎']) {
    limpiar();
    const r = abrirExterno(`https://ejemplo.prueba/${como === '⏎' ? 'enter' : 'clic'}`);
    await dormir(0);
    assert.deepEqual(llamadas.map(l => l.enGesto), [false], 'lo intentó, y Safari no dejó');
    assert.ok(boton(), 'el aviso está abierto');
    assert.match(document.querySelector('dialog').textContent, /no dejó abrir la pestaña/);
    assert.match(document.querySelector('dialog').textContent, /ejemplo\.prueba/);
    if (como === 'clic') gesto(() => boton().click());
    else gesto(() => boton().dispatchEvent(new w.KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })));
    assert.equal(await r, true, `${como}: quedó abierta`);
    assert.equal(llamadas.at(-1).enGesto, true, 'la abrió en el evento del botón');
    assert.equal(abiertas.length, 1);
    assert.equal(document.querySelector('dialog'), null, 'y el aviso se cerró');
}
{
    limpiar();
    const r = abrirExterno('https://ejemplo.prueba/no');
    await dormir(0);
    gesto(() => boton('no').click());
    assert.equal(await r, false, 'cancelar no abre');
    assert.equal(abiertas.length, 0);
}

// ── lo que no es web ──
{
    limpiar();
    assert.equal(gesto(() => A.abrirYa('javascript:alert(1)')), false, 'javascript: nunca');
    assert.equal(gesto(() => A.abrirYa(' data:text/html,x')), false, 'data: nunca');
    assert.equal(llamadas.length, 0);
    assert.equal(gesto(() => A.abrirYa('mailto:alguien@ejemplo.prueba')), true, 'mailto, como antes');
    assert.deepEqual(llamadas.map(l => [l.url, l.opciones]), [['mailto:alguien@ejemplo.prueba', 'noopener,noreferrer']]);
}

console.log('abrir: ok');
process.exit(0);
