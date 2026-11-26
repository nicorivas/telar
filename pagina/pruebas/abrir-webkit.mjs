// Prueba de los enlaces de la terminal en navegadores de verdad (Playwright: WebKit, el motor de Safari; Chrome y
// Firefox), por http y por https: xterm.js de verdad con lo que la página le pone (web/rutas-agente.ts: el linkHandler de
// los hipervínculos OSC 8, `abrirHipervinculo`, y las direcciones sueltas, `enlazarTerminal`), y web/abrir.ts. La página la
// sirve page.route en telar.prueba; la de afuera, en afuera.prueba (para ver qué le llega).
//
// Lo que espera, con y sin el mouse de la terminal puesto (el tmux de otra máquina, Claude Code: 1003, «any»):
// · un clic en un hipervínculo OSC 8 y uno en una dirección suelta abren una pestaña, en el evento del mouse (mouseup:
//   ahí activa xterm sus enlaces), con la dirección exacta, sin `opener` y sin `Referer`;
// Lo que no puede: el bloqueo de ventanas. Los navegadores de Playwright abren todo, aun sin gesto (en Chrome y
// Firefox tampoco vuelve con --disable-popup-blocking quitado ni con dom.disable_open_during_load). Lo mide, con el
// bloqueo de Safari de verdad, prueba:abrir-safari; el aviso cuando no abre, prueba:abrir.
// Necesita los navegadores: npx playwright-core install webkit chromium-headless-shell firefox. Sin ellos, se salta.
// npm run prueba:abrir-webkit [-- webkit]
import { build } from 'esbuild';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import pw from 'playwright-core';

const aqui = path.dirname(fileURLToPath(import.meta.url));
const src = path.join(aqui, '..', 'src');
const xterm = path.join(aqui, '..', 'node_modules', '@xterm', 'xterm');
const pedidos = process.argv.slice(2).filter(a => !a.startsWith('-'));
const nombres = pedidos.length ? pedidos : ['webkit', 'chromium', 'firefox'];

const { outputFiles: [js] } = await build({
    stdin: { contents: "import { abrirHipervinculo, enlazarTerminal } from './web/rutas-agente'; Object.assign(window, { abrirHipervinculo, enlazarTerminal });", resolveDir: src, loader: 'ts' },
    bundle: true, platform: 'browser', format: 'iife', write: false, logLevel: 'warning',
});

const pagina = `<!doctype html><meta charset="utf-8"><title>abrir</title>
<style>${readFileSync(path.join(xterm, 'css', 'xterm.css'), 'utf8')} body { margin: 0 }</style>
<div id="t" style="width:800px;height:300px"></div>
<script>${readFileSync(path.join(xterm, 'lib', 'xterm.js'), 'utf8')}</script>
<script>${js.text}</script>
<script>
window.r = [];
const abrir = window.open.bind(window);
window.open = (...a) => { r.push({ url: a[0], ev: window.event ? window.event.type : null }); return abrir(...a); };
const vista = { hilo: 'prueba', maquina: '' };
const term = new Terminal({ linkHandler: { activate: (_e, uri) => abrirHipervinculo(uri, vista), allowNonHttpProtocols: true } });
term.open(document.getElementById('t'));
enlazarTerminal(term, vista);
window.term = term;
window.escribir = mouse => new Promise(ok => term.write('\\x1b[H\\x1b[2J' + (mouse ? '\\x1b[?1000h\\x1b[?1003h\\x1b[?1006h' : '\\x1b[?1003l\\x1b[?1000l')
    + '\\x1b]8;;https://afuera.prueba/osc8?a=1\\x07ENLACE-OSC8\\x1b]8;;\\x07   https://afuera.prueba/suelta?b=2   \\r\\n', ok));
</script>`;

let fallas = 0, corridas = 0;
const revisar = (que, f) => {
    corridas++;
    try { f(); } catch (e) { fallas++; console.log(`✗ ${que}: ${e.message}`); }
};
for (const nombre of nombres) {
    if (!existsSync(pw[nombre].executablePath())) { console.log(`${nombre}: no está instalado (npx playwright-core install ${nombre === 'chromium' ? 'chromium-headless-shell' : nombre}): se salta`); continue; }
    const nav = await pw[nombre].launch();
    for (const esquema of ['http', 'https']) {
        const ctx = await nav.newContext({ ignoreHTTPSErrors: true });
        const afuera = [];
        await ctx.route('**/*', r => {
            const u = new URL(r.request().url());
            if (u.hostname === 'afuera.prueba') { afuera.push({ url: u.href, referer: r.request().headers().referer ?? '' }); return r.fulfill({ contentType: 'text/html', body: '<!doctype html><title>afuera</title>afuera' }); }
            return r.fulfill({ contentType: 'text/html', body: pagina });
        });
        const p = await ctx.newPage();
        p.on('pageerror', e => console.log(`${nombre} ${esquema}: error de la página: ${e.message}`));
        await p.goto(`${esquema}://telar.prueba/?k=la-llave`);
        const celda = await p.evaluate(() => { const c = term._core._renderService.dimensions.css.cell; const s = term.element.querySelector('.xterm-screen').getBoundingClientRect(); return { x: s.x, y: s.y, w: c.width, h: c.height }; });
        const clic = async col => {
            const x = celda.x + celda.w * (col + 0.5), y = celda.y + celda.h * 0.5;
            await p.mouse.move(x - 8, y); await p.mouse.move(x, y, { steps: 3 }); await p.waitForTimeout(80);
            const nueva = ctx.waitForEvent('page', { timeout: 4000 }).catch(() => null);
            await p.mouse.down(); await p.mouse.up();
            const q = await nueva;
            if (q) await q.waitForURL(/afuera\.prueba/, { timeout: 4000 }).catch(() => {});
            return q;
        };
        for (const mouse of [false, true]) {
            await p.evaluate(m => window.escribir(m), mouse);
            const donde = `${nombre} ${esquema}${mouse ? ' (mouse de la terminal)' : ''}`;
            for (const [que, col, url] of [['osc8', 3, 'https://afuera.prueba/osc8?a=1'], ['suelta', 18, 'https://afuera.prueba/suelta?b=2']]) {
                await p.evaluate(() => { window.r = []; });
                afuera.length = 0;
                const q = await clic(col);
                const r = await p.evaluate(() => window.r);
                revisar(`${donde} ${que}`, () => {
                    assert.deepEqual(r.map(x => x.ev), ['mouseup'], 'una llamada a window.open, en el evento del mouse');
                    assert.ok(q, 'abrió una pestaña');
                    assert.equal(q.url(), url, 'con la dirección exacta');
                    assert.deepEqual(afuera.map(x => x.referer), [''], 'sin Referer');
                });
                if (q) {
                    const opener = await q.evaluate(() => window.opener === null).catch(() => 'no se pudo leer');
                    revisar(`${donde} ${que} opener`, () => assert.equal(opener, true, 'sin opener'));
                    await q.close();
                }
                const aviso = await p.locator('dialog').count();
                revisar(`${donde} ${que} sin aviso`, () => assert.equal(aviso, 0, 'abrió sin preguntar'));
            }
        }
        console.log(`${nombre} ${esquema}: listo`);
        await ctx.close();
    }
    await nav.close();
}
assert.equal(fallas, 0, `${fallas} de ${corridas} no dieron lo esperado`);
console.log(`abrir-webkit: ok (${corridas})`);
