// Prueba de los enlaces de la terminal con el bloqueo de ventanas de Safari de verdad: un WKWebView (el motor de Safari
// de esta Mac, con javaScriptCanOpenWindowsAutomatically en false, como Safari) que hace clics de verdad
// (pruebas/safari/ventana.swift, compilado con swiftc). Playwright no sirve para esto: sus navegadores abren todo.
// La página: xterm.js con lo que la página le pone (web/rutas-agente.ts) y web/abrir.ts.
//
// Lo que espera:
// · un clic en un hipervínculo OSC 8, en una dirección suelta, y en el OSC 8 con el mouse de la terminal puesto (el tmux
//   de otra máquina): Safari abre la pestaña (xterm activa el enlace al soltar el mouse, y eso es gesto), y va a la
//   dirección exacta;
// · window.open después de un fetch, como se abría antes (`noopener`): Safari no abre, y window.open da null igual que
//   cuando abre, así que nadie se entera. Con abrirExterno, tampoco abre, pero sale el aviso, y un clic en su botón abre.
//
// Cada paso abre su ventana fuera de la pantalla, sin activar la aplicación: no se ve ni le quita el foco a nadie (los
// clics van directo al WKWebView). Solo macOS, con swiftc (Xcode o sus herramientas de línea de órdenes); si no, se
// salta. No corre en CI ni en la suite: a mano, después de tocar web/abrir.ts o los enlaces de la
// terminal. npm run prueba:abrir-safari
import { build } from 'esbuild';
import { execFileSync, spawn } from 'node:child_process';
import { mkdtempSync, readFileSync } from 'node:fs';
import http from 'node:http';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const aqui = path.dirname(fileURLToPath(import.meta.url));
if (process.platform !== 'darwin') { console.log('abrir-safari: solo en macOS: se salta'); process.exit(0); }
const carpeta = mkdtempSync(path.join(tmpdir(), 'abrir-safari-'));
const ventana = path.join(carpeta, 'ventana');
try {
    execFileSync('xcrun', ['swiftc', '-O', path.join(aqui, 'safari', 'ventana.swift'), '-o', ventana], { stdio: ['ignore', 'ignore', 'pipe'] });
} catch (e) {
    console.log(`abrir-safari: no pude compilar la ventana (${String(e.stderr ?? e.message).trim().split('\n')[0]}): se salta`);
    process.exit(0);
}

const src = path.join(aqui, '..', 'src');
const xterm = path.join(aqui, '..', 'node_modules', '@xterm', 'xterm');
const { outputFiles: [js] } = await build({
    stdin: { contents: "import { abrirHipervinculo, enlazarTerminal } from './web/rutas-agente'; import { abrirExterno } from './web/ui'; Object.assign(window, { abrirHipervinculo, enlazarTerminal, abrirExterno });", resolveDir: src, loader: 'ts' },
    bundle: true, platform: 'browser', format: 'iife', write: false, logLevel: 'warning',
});

const pagina = `<!doctype html><meta charset="utf-8"><title>abrir</title>
<style>${readFileSync(path.join(xterm, 'css', 'xterm.css'), 'utf8')} body { margin: 0 } #b { position: fixed; right: 0; bottom: 0; width: 200px; height: 60px; background: #444 }</style>
<div id="t" style="width:800px;height:200px"></div><div id="b"></div>
<script>${readFileSync(path.join(xterm, 'lib', 'xterm.js'), 'utf8')}</script>
<script>${js.text}</script>
<script>
const log = s => webkit.messageHandlers.log.postMessage(String(s));
const clic = (x, y) => webkit.messageHandlers.log.postMessage({ clic: [x, y] });
const dormir = ms => new Promise(r => setTimeout(r, ms));
// el mouse de verdad (el de la persona) no cuenta: el paso del mouse por un enlace lo hace la prueba
let quieto = true;
for (const k of ['mousemove', 'mouseover', 'mouseout', 'mouseleave', 'mouseenter']) window.addEventListener(k, e => { if (e.isTrusted && quieto) e.stopImmediatePropagation(); }, true);
const vista = { hilo: 'prueba', maquina: '' };
if (location.search.includes('depurar')) for (const k of ['mousedown', 'mouseup']) window.addEventListener(k, e => log('  ' + k + ' ' + e.clientX + ',' + e.clientY), true);
const term = new Terminal({ linkHandler: { activate: (_e, uri) => abrirHipervinculo(uri, vista), allowNonHttpProtocols: true } });
term.open(document.getElementById('t'));
enlazarTerminal(term, vista);
const escribir = mouse => new Promise(ok => term.write('\\x1b[H\\x1b[2J' + (mouse ? '\\x1b[?1000h\\x1b[?1003h\\x1b[?1006h' : '')
    + '\\x1b]8;;https://afuera.prueba/osc8?a=1\\x07ENLACE-OSC8\\x1b]8;;\\x07   https://afuera.prueba/suelta?b=2   \\r\\n', ok));
const enCelda = col => {
    const s = term.element.querySelector('.xterm-screen').getBoundingClientRect(), c = term._core._renderService.dimensions.css.cell;
    return [s.x + c.width * (col + 0.5), s.y + c.height * 0.5];
};
const pasar = async col => {
    const [x, y] = enCelda(col), s = term.element.querySelector('.xterm-screen');
    for (const dx of [-8, 0]) s.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, clientX: x + dx, clientY: y }));
    await dormir(100);
    return [x, y];
};
let alClic = null;
document.getElementById('b').addEventListener('click', () => { const f = alClic; alClic = null; f?.(); });
const enB = () => { const r = document.getElementById('b').getBoundingClientRect(); return [r.x + 50, r.y + 30]; };
const paso = new URLSearchParams(location.search).get('paso');
(async () => {
    await dormir(400);
    const enTerminal = { 'osc8': [false, 3], 'suelta': [false, 18], 'osc8 con el mouse de la terminal': [true, 3] }[paso];
    if (enTerminal) {
        await escribir(enTerminal[0]);
        log('PASO ' + paso); clic(...await pasar(enTerminal[1])); await dormir(1200);
    }
    if (paso === 'antes, después de un fetch') {
        log('PASO ' + paso);
        alClic = () => fetch('/x').then(r => r.text()).then(() => log('  window.open: ' + window.open('https://afuera.prueba/antes', '_blank', 'noopener,noreferrer')));
        clic(...enB()); await dormir(1200);
    }
    if (paso === 'ahora, después de un fetch') {
        log('PASO ' + paso);
        alClic = () => fetch('/x').then(r => r.text()).then(() => abrirExterno('https://afuera.prueba/ahora').then(ok => log('  abierta: ' + ok)));
        clic(...enB()); await dormir(1200);
        const b = document.querySelector('dialog [data-accion="b0"]');
        log('  aviso: ' + (b ? b.textContent.trim() : 'no'));
        if (b) { log('PASO el botón del aviso'); const r = b.getBoundingClientRect(); clic(r.x + r.width / 2, r.y + r.height / 2); await dormir(1200); }
    }
    log('FIN');
})();
</script>`;

const servidor = http.createServer((q, s) => { s.setHeader('content-type', 'text/html; charset=utf-8'); s.end(q.url === '/x' ? 'ok' : pagina); });
await new Promise(ok => servidor.listen(0, '127.0.0.1', ok));
// cada paso, en una ventana nueva: después de abrir una pestaña, la de la prueba deja de recibir los clics
const correr = paso => new Promise((ok, no) => {
    const q = new URLSearchParams({ paso, ...(process.argv.includes('--depurar') ? { depurar: '1' } : {}) });
    const p = spawn(ventana, [`http://127.0.0.1:${servidor.address().port}/?${q}`]);
    let texto = '';
    p.stdout.on('data', d => { texto += d; });
    p.stderr.on('data', () => {});
    p.on('error', no);
    p.on('close', codigo => (codigo === 0 ? ok(texto) : no(new Error(`la ventana terminó con ${codigo}:\n${texto}`))));
});
let salida = '';
try {
    for (const paso of ['osc8', 'suelta', 'osc8 con el mouse de la terminal', 'antes, después de un fetch', 'ahora, después de un fetch'])
        salida += await correr(paso);
} finally { servidor.close(); }

// lo que pasó en cada paso
const pasos = {};
let actual = '';
for (const linea of salida.split('\n')) {
    if (linea.startsWith('PASO ')) { actual = linea.slice(5); pasos[actual] = []; } else if (actual && linea && linea !== 'FIN') pasos[actual].push(linea);
}
console.log(Object.entries(pasos).map(([k, v]) => `${k}:\n  ${v.join('\n  ') || '(nada)'}`).join('\n'));
const abrio = (paso, url) => {
    const l = pasos[paso] ?? [];
    assert.ok(l.some(x => x.startsWith('ABRE')), `${paso}: Safari abrió la pestaña`);
    assert.ok(l.includes(`VA ${url}`), `${paso}: fue a ${url}`);
};
abrio('osc8', 'https://afuera.prueba/osc8?a=1');
abrio('suelta', 'https://afuera.prueba/suelta?b=2');
abrio('osc8 con el mouse de la terminal', 'https://afuera.prueba/osc8?a=1');
assert.ok(!pasos['antes, después de un fetch'].some(x => x.startsWith('ABRE')), 'después de un fetch, Safari no abre');
assert.ok(pasos['antes, después de un fetch'].includes('  window.open: null'), 'y window.open con noopener da null: nadie se entera');
assert.ok(!pasos['ahora, después de un fetch'].some(x => x.startsWith('ABRE')), 'ahora tampoco abre después de un fetch…');
assert.match(pasos['ahora, después de un fetch'].join('\n'), /aviso: .*abrir/i, '…pero sale el aviso');
abrio('el botón del aviso', 'https://afuera.prueba/ahora');
assert.ok(pasos['el botón del aviso'].includes('  abierta: true'), 'y abrirExterno dice que quedó abierta');
console.log('abrir-safari: ok');
