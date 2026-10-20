// Prueba del eco de la terminal (src/navegador/eco/entrada.ts) contra un «Claude Code» falso: con cada tecla,
// 250 ms después, vuelve a dibujar la pantalla entera (como el de verdad). Corre en Node con xterm sin
// pantalla (@xterm/headless): npm run prueba:eco
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const { Terminal } = require('@xterm/headless');
const aqui = path.dirname(fileURLToPath(import.meta.url));
const salida = path.join(mkdtempSync(path.join(tmpdir(), 'eco-')), 'eco.cjs');
await build({ entryPoints: [path.join(aqui, '..', 'src', 'navegador', 'eco', 'entrada.ts')], bundle: true,
    platform: 'node', format: 'cjs', outfile: salida, logLevel: 'warning' });
const { conEco } = require(salida);
const espera = ms => new Promise(r => setTimeout(r, ms));

const term = new Terminal({ cols: 80, rows: 8, allowProposedApi: true });
const eco = conEco(term);
let escrito = '';
// como Claude Code: la caja del input se rellena con espacios duros después del texto
const cuadro = () => `\x1b[?25l\x1b[H\x1b[2Jcabecera\r\n────────\r\n❯ ${escrito}${'\u00a0'.repeat(20)}\r\n────────\r\n  ctx 41%\x1b[3;${3 + escrito.length}H\x1b[?25h`;
const linea = () => term.buffer.active.getLine(2).translateToString(true).replace(/[\s\u00a0]+$/, '');
const LATENCIA = 250;
const tecla = c => { eco.tecleado(c); setTimeout(() => { escrito += c; eco.escribir(cuadro()); }, LATENCIA); };

eco.escribir(cuadro());
await espera(50);

// 1. mientras no mide latencia, no inventa nada: la letra aparece cuando llega el cuadro
tecla('a');
await espera(30);
assert.equal(linea(), '❯', 'sin latencia medida no hay eco');
await espera(LATENCIA + 50);
assert.equal(linea(), '❯ a');

// 2. con unas letras confirmadas ya sabe la latencia, y desde ahí las muestra al tiro
for (const c of 'prendi') { tecla(c); await espera(LATENCIA + 40); }
assert.ok(eco.estado().mostrando, `debería mostrar el eco: ${JSON.stringify(eco.estado())}`);
assert.equal(linea(), '❯ aprendi');
tecla('z');
await espera(20);
assert.equal(linea(), '❯ aprendiz', 'la letra aparece antes que el cuadro');

// 3. tecleando más rápido que la ida y vuelta: siempre se ven todas, ninguna doble
for (const [i, c] of [...' rapido'].entries()) {
    tecla(c);
    await espera(40);
    assert.equal(linea(), `❯ aprendiz${' rapido'.slice(0, i + 1)}`.trimEnd(), `tras «${c}»`);
}
await espera(LATENCIA + 100);
assert.equal(linea(), '❯ aprendiz rapido', 'al final, lo del servidor y nada más');
assert.equal(eco.estado().pendientes, '');

// 3b. cuadros que llegan solos (el reloj, la animación de Claude) entre teclas: el eco sigue ahí
tecla('!');
await espera(20);
eco.escribir(cuadro());
await espera(20);
assert.equal(linea(), '❯ aprendiz rapido!', 'un cuadro sin la letra no borra el eco');
await espera(LATENCIA + 50);
assert.equal(linea(), '❯ aprendiz rapido!');
eco.tecleado('\x7f');
setTimeout(() => { escrito = escrito.slice(0, -1); eco.escribir(cuadro()); }, LATENCIA);
await espera(LATENCIA + 100);

// 4. ⌫ sobre una letra pendiente la quita al tiro
tecla('x');
await espera(20);
assert.equal(linea(), '❯ aprendiz rapidox');
eco.tecleado('\x7f');
await espera(20);
assert.equal(linea(), '❯ aprendiz rapido', '⌫ deshace la pendiente');
setTimeout(() => { escrito = escrito.slice(0, -1); eco.escribir(cuadro()); }, LATENCIA);
await espera(LATENCIA + 100);
assert.equal(linea(), '❯ aprendiz rapido');

// 5. con el cursor escondido (Claude trabajando) no se dibuja nada
eco.escribir(`\x1b[?25l`);
await espera(20);
eco.tecleado('q');
await espera(20);
assert.equal(linea(), '❯ aprendiz rapido', 'cursor escondido: sin eco');
eco.tecleado('\r');

console.log('eco: bien', JSON.stringify(eco.estado()));
term.dispose();
