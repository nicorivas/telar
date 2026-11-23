// Prueba de un nombre suelto en la terminal de un hilo (src/web/rutas-agente.ts y src/web/enlaces.ts): el agente escribe
// «En `personal/referencia/artículos/…/`:» y abajo «`original.md` — el texto íntegro», y un clic en original.md tiene que
// abrir el de esa carpeta, no buscarlo en la raíz. La página manda al backend (`/api/archivos/resolver`) la ruta, la
// carpeta del hilo y las carpetas nombradas antes en el mismo mensaje (la más cercana primero, sin las del mensaje
// anterior); abre la que vuelve; si vuelven varios candidatos, el visor (src/web/carpeta.ts) los ofrece para elegir en vez
// de «no existe»; si el backend es de antes, prueba como antes. Y una ruta con tilde (también descompuesta, NFD) es un
// solo enlace, entero. Corre en Node con xterm sin pantalla (@xterm/headless), un fetch de mentira y lo demás de la
// página de mentira (nada sale ni se abre): npm run prueba:nombre-suelto
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const { Terminal } = require('@xterm/headless');
const aqui = path.dirname(fileURLToPath(import.meta.url));
const src = path.join(aqui, '..', 'src');

// lo de la página que no se prueba aquí, de mentira: la lista de hilos, el visor (lo que se abre queda anotado), la
// barra de la derecha y la hoja de códigos
const MENTIRAS = {
    [path.join(src, 'modelo.ts')]: `export const modelo = { aqui: 'laptop',
        porNombre: n => (n === 'Lecturas' ? { nombre: n, ruta: '/Users/ana/vida' } : undefined) };`,
    [path.join(src, 'cli.ts')]: 'export async function espejos() { return { datos: { espejos: [] } }; }',
    [path.join(src, 'web', 'ui.ts')]: `export const abiertos = [];
        export async function abrirArchivo(r) { abiertos.push(r); }
        export async function abrirExterno() {} export async function abrirDireccion() {}`,
    [path.join(src, 'web', 'lado.ts')]: 'export function abrirCodigo() {}',
    [path.join(src, 'web', 'codigos.ts')]: 'export const conocidos = () => new Set(); export const queEs = () => "";',
    [path.join(src, 'web', 'vistas-hilo.ts')]: 'export const teclaParaLaVista = () => true;',
};
const mentira = { name: 'mentira', setup(b) {
    b.onResolve({ filter: /^\.\.?\// }, a => {
        const p = path.join(a.resolveDir, a.path) + '.ts';
        return MENTIRAS[p] ? { path: p, namespace: 'mentira' } : undefined;
    });
    b.onLoad({ filter: /.*/, namespace: 'mentira' }, a => ({ contents: MENTIRAS[a.path], loader: 'js' }));
} };
const salida = path.join(mkdtempSync(path.join(tmpdir(), 'nombre-suelto-')), 'nombre-suelto.cjs');
await build({
    stdin: { contents: `export * from './web/rutas-agente'; export * as carpeta from './web/carpeta'; export * as candidatos from './web/candidatos';
        export * as enlaces from './web/enlaces'; export { abiertos } from './web/ui';`, resolveDir: src, loader: 'ts' },
    bundle: true, platform: 'node', format: 'cjs', outfile: salida, logLevel: 'warning', plugins: [mentira],
});

// el fetch de mentira: los tipos de dirección, y el backend que busca, que contesta lo que diga la prueba
const pedidos = [];
let contestar = () => ({ status: 404, cuerpo: {} });
globalThis.fetch = async url => {
    const u = new URL(url, 'http://pagina');
    if (u.pathname === '/api/objetos/tipos') return { ok: true, json: async () => ({ tipos: [] }) };
    pedidos.push(u);
    const { status, cuerpo } = contestar(u);
    return { ok: status === 200, status, json: async () => cuerpo };
};
globalThis.window = { addEventListener() {} };
const m = require(salida);
const { enlazarTerminal, carpeta, candidatos: elegir, enlaces, abiertos } = m;

const COLS = 100;
const ARTICULO = 'personal/referencia/artículos/2026-06-informe-ia';
/** Una pantalla con estas filas (con sus saltos, como las escribe Claude Code) y su terminal con los enlaces de la
 *  página: el proveedor de enlaces que registra, para pedirle los de una fila y apretar uno. */
async function pantalla(filas, cols = COLS) {
    const t = new Terminal({ cols, rows: 40, allowProposedApi: true });
    await new Promise(r => t.write(filas.join('\r\n'), r));
    let proveedor;
    const term = { buffer: t.buffer, cols, element: undefined, registerLinkProvider: p => { proveedor = p; return { dispose() {} }; } };
    enlazarTerminal(term, { hilo: 'Lecturas', maquina: '' });
    const linksEn = y => new Promise(r => proveedor.provideLinks(y, ls => r(ls ?? [])));
    return { t, linksEn };
}
/** Aprieta el enlace `texto` de la fila `y` y espera a que la página termine de abrirlo. */
async function clic(p, y, texto) {
    const l = (await p.linksEn(y)).find(x => x.text === texto);
    assert.ok(l, `no hay enlace «${texto}» en la fila ${y}: ${(await p.linksEn(y)).map(x => x.text)}`);
    const antes = abiertos.length;
    l.activate({});
    for (let i = 0; i < 50 && abiertos.length === antes; i++) await new Promise(r => setTimeout(r, 1));
    return abiertos.at(-1);
}

// el mensaje del caso real: uno anterior (con otra carpeta), lo que escribió la persona, y la respuesta del hilo
const filas = [
    '⏺ Antes dejé `personal/referencia/artículos/2026-05-yc-playbook/` listo.',
    '',
    '> ¿y el del informe?',
    '',
    '⏺ Lo dejé bajo la carpeta del artículo. Revisé también `personal/referencia/README.md`.',
    '',
    `  En \`${ARTICULO}/\`:`,
    '',
    '  - `original.md` — el texto íntegro, con las figuras descritas',
    '  - `ficha.md` — el resumen y por qué importa',
];
const Y_ORIGINAL = 9;

// 1. las carpetas que nombra el mensaje, la más cercana primero, sin las del mensaje anterior ni lo de la persona
{
    const p = await pantalla(filas);
    assert.deepEqual(enlaces.carpetasAntes(p.t.buffer.active, COLS, Y_ORIGINAL), [ARTICULO, 'personal/referencia']);
    assert.deepEqual(enlaces.carpetasDe('ver https://x.cl/a/b y `a/b/c.md`, y personal/x/.'), ['personal/x', 'a/b'], 'la última primero');
}

// 2. un clic en original.md: el backend recibe la ruta, la carpeta del hilo y las nombradas; abre la que vuelve
{
    const p = await pantalla(filas);
    contestar = u => ({ status: 200, cuerpo: { ruta: `${u.searchParams.getAll('nombradas')[0]}/original.md`, candidatos: [], mas: false } });
    assert.equal(await clic(p, Y_ORIGINAL, 'original.md'), `${ARTICULO}/original.md`);
    const u = pedidos.at(-1);
    assert.equal(u.pathname, '/api/archivos/resolver');
    assert.deepEqual([u.searchParams.get('ruta'), u.searchParams.get('carpeta'), u.searchParams.getAll('nombradas')],
        ['original.md', '/Users/ana/vida', [ARTICULO, 'personal/referencia']]);
}

// 3. varios candidatos: el visor de esa ruta los ofrece, los más cercanos primero, en vez de «no existe»
{
    const p = await pantalla(filas);
    const candidatos = [`${ARTICULO}/original.md`, 'personal/referencia/artículos/2026-05-yc-playbook/original.md'];
    contestar = () => ({ status: 200, cuerpo: { ruta: '', candidatos, mas: true } });
    assert.equal(await clic(p, Y_ORIGINAL, 'original.md'), 'original.md');
    const el = { classList: { add() {} }, dataset: { atendido: '1' }, innerHTML: '', scrollTop: 0, addEventListener() {} };
    const antes = pedidos.length;
    await carpeta.montar(el, '', 'original.md', t => t, null);
    assert.equal(pedidos.length, antes, 'no se pidió nada: los candidatos ya están');
    assert.doesNotMatch(el.innerHTML, /no existe/);
    assert.match(el.innerHTML, /hay 2 o más archivos que se llaman así/);
    const ofrecidos = [...el.innerHTML.matchAll(/data-archivo="([^"]+)"/g)].map(x => x[1]);
    assert.deepEqual(ofrecidos, candidatos);
    // de otra máquina: con la máquina delante, y la carpeta tenue sin ella
    elegir.ofrecer('servidor:x.md', ['servidor:a/x.md', 'servidor:b/x.md']);
    await carpeta.montar(el, '', 'servidor:x.md', t => t, null);
    assert.match(el.innerHTML, /data-archivo="servidor:a\/x\.md"[^>]*><span class="dir">a\/<\/span>x\.md/);
}

// 4. un backend de antes (sin /api/archivos/resolver): como antes, desde la carpeta del hilo si ahí existe
{
    const p = await pantalla(filas);
    contestar = u => (u.pathname === '/api/archivos' && u.searchParams.get('ruta') === 'ficha.md'
        ? { status: 200, cuerpo: {} } : { status: 404, cuerpo: {} });
    assert.equal(await clic(p, Y_ORIGINAL + 1, 'ficha.md'), 'ficha.md');
    assert.deepEqual(pedidos.slice(-3).map(u => `${u.pathname} ${u.searchParams.get('ruta')}`),
        ['/api/archivos/resolver ficha.md', '/api/archivos /Users/ana/vida/ficha.md', '/api/archivos ficha.md']);
}

// 5. una ruta con tilde es un solo enlace, entero: compuesta (NFC), descompuesta (NFD) y partida por Claude Code en
// dos filas porque no cabe
{
    const entera = `${ARTICULO}/original.md`;
    const nfd = entera.normalize('NFD');
    assert.notEqual(nfd, entera);
    const p = await pantalla(['⏺ Quedó en:', `  ${entera} y en`, `  ${nfd}.`]);
    assert.deepEqual((await p.linksEn(2)).map(l => l.text), [entera]);
    assert.deepEqual((await p.linksEn(3)).map(l => l.text), [nfd]);
    assert.deepEqual(enlaces.buscar(`ver ${nfd}:12`).map(h => h.texto), [`${nfd}:12`]);
    const angosta = 50, trozos = entera.match(new RegExp(`.{1,${angosta - 2}}`, 'gu')).map(x => `  ${x}`);
    const q = await pantalla(['⏺ Quedó en:', ...trozos], angosta);
    contestar = () => ({ status: 200, cuerpo: { ruta: entera, candidatos: [entera], mas: false } });
    assert.deepEqual((await q.linksEn(3)).map(l => l.text), [entera]);
    assert.equal(await clic(q, 2, entera), entera);
    assert.equal(pedidos.at(-1).searchParams.get('ruta'), entera);
}

console.log('nombre suelto: bien');
