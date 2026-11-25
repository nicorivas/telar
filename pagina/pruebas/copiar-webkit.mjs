// Prueba del portapapeles en navegadores de verdad (Playwright: WebKit, el motor de Safari; Chrome y Firefox), por http
// y por https, con el código de la página (src/web/portapapeles.ts y el aviso de web/interfaz.ts) en una página de
// prueba: nada del dashboard. La página la sirve page.route en telar.prueba (por http no es contexto seguro, por https
// sí); el WebSocket es uno de verdad, aquí mismo en 127.0.0.1 (ws y wss, con un certificado que hace openssl): el de mentira de Playwright (routeWebSocket) entrega sus
// mensajes como si fueran un gesto, y en WebKit copiaba lo que Safari no copia.
//
// Lo que reproduce, y lo que espera:
// · «osc, como antes»: soltar el mouse en la terminal, que el texto vuelva por el WebSocket (como el OSC 52 del tmux de
//   otra máquina) y copiarlo al llegar. En WebKit no se puede (ni http ni https): un mensaje del WebSocket no es un gesto.
//   En Chrome sí (da unos segundos después del clic). Es la causa del aviso.
// · «osc, armado»: lo que hace la terminal ahora: al soltar, `armar`; al llegar, `copiarLoQueLlega`. Por https copia en
//   los tres; por http, WebKit sigue sin poder (y la terminal pide el clic).
// · «botón»: el aviso con `enElClic` copia en el clic y con ⏎, por http y por https, en los tres.
// · «botón, después del await» (lo de antes): se anota, no se exige; en el WebKit medido también copia.
//
// En macOS, el portapapeles de la persona se guarda al empezar y se devuelve al terminar (el WebKit de Playwright
// escribe en el de verdad), y lo que copia WebKit se lee con pbpaste (Chrome y Firefox headless tienen uno propio). Necesita los navegadores: npx playwright-core install
// webkit chromium-headless-shell firefox. Sin ellos, se salta.  npm run prueba:copiar-webkit [-- webkit]
import { build } from 'esbuild';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import https from 'node:https';
import { createHash } from 'node:crypto';
import http from 'node:http';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import pw from 'playwright-core';

const aqui = path.dirname(fileURLToPath(import.meta.url));
const src = path.join(aqui, '..', 'src');
const pedidos = process.argv.slice(2).filter(a => !a.startsWith('-'));
const nombres = pedidos.length ? pedidos : ['webkit', 'chromium', 'firefox'];

const { outputFiles: [js] } = await build({
    stdin: { contents: "import * as P from './web/portapapeles'; import { preguntar } from './web/interfaz'; Object.assign(window, { P, preguntar });", resolveDir: src, loader: 'ts' },
    bundle: true, platform: 'browser', format: 'iife', write: false, logLevel: 'warning',
});

// el servidor: contesta cada mensaje a los 150 ms, como el OSC 52 que vuelve del tmux de otra máquina
const alSubir = (q, sock) => {
    const llave = createHash('sha1').update(`${q.headers['sec-websocket-key']}258EAFA5-E914-47DA-95CA-C5AB0DC85B11`).digest('base64');
    sock.write(`HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ${llave}\r\n\r\n`);
    sock.on('data', d => {
        if ((d[0] & 0x0f) !== 1) return;   // solo los de texto, cortos y enmascarados (los de la página)
        const largo = d[1] & 0x7f, mascara = d.subarray(2, 6);
        const texto = Buffer.from(d.subarray(6, 6 + largo).map((b, i) => b ^ mascara[i % 4])).toString();
        const sale = Buffer.from(`${texto}: lo seleccionado`);
        setTimeout(() => sock.write(Buffer.concat([Buffer.from([0x81, sale.length]), sale])), 150);
    });
    sock.on('error', () => {});
};
const carpeta = mkdtempSync(path.join(tmpdir(), 'copiar-'));
execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1', '-subj', '/CN=127.0.0.1',
    '-addext', 'subjectAltName=IP:127.0.0.1', '-keyout', path.join(carpeta, 'llave.pem'), '-out', path.join(carpeta, 'cert.pem')], { stdio: 'ignore' });
const servidores = {
    http: http.createServer((_q, s) => s.end()),
    https: https.createServer({ key: readFileSync(path.join(carpeta, 'llave.pem')), cert: readFileSync(path.join(carpeta, 'cert.pem')) }, (_q, s) => s.end()),
};
const puertos = {};
for (const [esquema, sv] of Object.entries(servidores)) {
    sv.on('upgrade', alSubir);
    await new Promise(ok => sv.listen(0, '127.0.0.1', ok));
    puertos[esquema] = sv.address().port;
}

// la página: una «terminal» donde se arrastra, y lo que hace cada camino. window.r junta los resultados
const pagina = esquema => `<!doctype html><meta charset="utf-8"><title>copiar</title>
<div id="terminal" style="width:400px;height:200px;background:#222"></div>
<script>${js.text}</script>
<script>
window.r = {};
const ws = new WebSocket('${esquema === 'https' ? 'wss' : 'ws'}://127.0.0.1:${puertos[esquema]}/ws');
let alLlegar = null;
ws.onmessage = e => { const f = alLlegar; alLlegar = null; f?.(e.data); };
ws.onopen = () => { window.abierto = true; };
window.modo = '';
let armada;
document.addEventListener('mouseup', () => {
    if (!modo) return;
    const m = modo; modo = '';
    if (m === 'armado') { armada?.soltar(); armada = P.armar(); }
    alLlegar = async texto => {
        const a = armada; armada = undefined;
        r[m] = m === 'armado' ? await P.copiarLoQueLlega(texto, a) : await P.copiar(texto);
    };
    ws.send(m);
}, true);
window.aviso = async (clave, enElClic) => {
    let p;
    const b = await preguntar('copiar', ['Copiar'], enElClic ? { enElClic: () => { p = P.copiarEnElGesto(clave); } } : {});
    if (b !== 'Copiar') { r[clave] = 'sin apretar'; return; }
    r[clave] = enElClic ? await p : await P.copiar(clave);
};
</script>`;

const mac = process.platform === 'darwin';
const pbpaste = () => execFileSync('pbpaste', { encoding: 'utf8' });
const pbcopy = t => execFileSync('pbcopy', { input: t });
const guardado = mac ? pbpaste() : null;
let fallas = 0, corridas = 0;
try {
    for (const nombre of nombres) {
        if (!existsSync(pw[nombre].executablePath())) { console.log(`${nombre}: no está instalado (npx playwright-core install ${nombre === 'chromium' ? 'chromium-headless-shell' : nombre}): se salta`); continue; }
        const nav = await pw[nombre].launch();
        for (const esquema of ['http', 'https']) {
            const ctx = await nav.newContext({ ignoreHTTPSErrors: true });
            if (nombre === 'chromium') await ctx.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: `${esquema}://telar.prueba` });
            const p = await ctx.newPage();
            await p.route(`${esquema}://telar.prueba/**`, r => r.fulfill({ contentType: 'text/html', body: pagina(esquema) }));
            await p.goto(`${esquema}://telar.prueba/`);
            await p.waitForFunction(() => window.abierto, null, { timeout: 5000 });
            const seguro = await p.evaluate(() => window.isSecureContext);
            assert.equal(seguro, esquema === 'https', `${nombre} ${esquema}: contexto seguro`);
            const esperar = clave => p.waitForFunction(k => k in window.r, clave, { timeout: 5000 }).then(() => p.evaluate(k => window.r[k], clave));
            const arrastrar = async m => {
                await p.evaluate(x => { window.modo = x; }, m);
                const caja = await p.locator('#terminal').boundingBox();
                await p.mouse.move(caja.x + 20, caja.y + 20); await p.mouse.down();
                await p.mouse.move(caja.x + 200, caja.y + 60, { steps: 4 }); await p.mouse.up();
                return esperar(m);
            };
            const enPortapapeles = esperado => {
                if (!mac || nombre !== 'webkit') return;
                const hay = pbpaste();
                if (hay !== esperado) throw new assert.AssertionError({ message: `en el portapapeles: «${hay}», no «${esperado}»` });
            };
            const r = {};
            const revisar = (que, obtenido, esperado, texto) => {
                corridas++;
                r[que] = obtenido;
                try {
                    assert.equal(obtenido, esperado);
                    if (obtenido === true && texto) enPortapapeles(texto);
                } catch (e) { fallas++; console.log(`✗ ${nombre} ${esquema} ${que}: ${e.message}`); }
            };
            if (mac) pbcopy('(antes)');
            revisar('osc, como antes', await arrastrar('antes'), nombre !== 'webkit', 'antes: lo seleccionado');
            if (mac) pbcopy('(antes)');
            revisar('osc, armado', await arrastrar('armado'), !(nombre === 'webkit' && esquema === 'http'), 'armado: lo seleccionado');
            for (const tecla of [false, true]) {
                const clave = `boton${tecla ? '-enter' : ''}`;
                void p.evaluate(k => window.aviso(k, true), clave);
                await p.locator('dialog [data-accion="b0"]').waitFor();
                if (tecla) await p.keyboard.press('Enter'); else await p.click('dialog [data-accion="b0"]');
                revisar(tecla ? 'botón con ⏎' : 'botón', await esperar(clave), true, clave);
            }
            void p.evaluate(() => window.aviso('despues', false));
            await p.locator('dialog [data-accion="b0"]').waitFor();
            await p.click('dialog [data-accion="b0"]');
            r['botón, después del await'] = await esperar('despues');
            console.log(`${nombre} ${esquema}:`, JSON.stringify(r));
            await ctx.close();
        }
        await nav.close();
    }
} finally {
    if (mac) pbcopy(guardado);
    for (const sv of Object.values(servidores)) { sv.closeAllConnections(); sv.close(); }
}
assert.equal(fallas, 0, `${fallas} de ${corridas} no dieron lo esperado`);
console.log(`copiar-webkit: ok (${corridas})`);
