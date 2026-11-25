// Prueba del panel de la mudanza (src/web/mudanza.ts), con un DOM (happy-dom) y un telar de mentira (`cli` y `modelo`):
// lo que pasa entre la página y telar cuando el hilo tiene algo sin subir. La primera vez telar dice que hay que elegir
// (409, «--subir … --si para llevarla igual») y deja el detalle en el progreso de la mudanza; el panel lo lee, lo muestra
// por repositorio, y lo elegido vuelve a pedir la mudanza con `subir` o con `si`. Lo mismo al traer un hilo de otra
// máquina, con el progreso leído de allá. Sin nada que elegir, ni se ve.
// Corre en Node: npm run prueba:mudanza
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
const MENTIRAS = {
    // lo que la página le pide a telar: cada pedido queda anotado, y la prueba dice qué contesta
    [path.join(src, 'cli.ts')]: `
        export const pedidos = [];
        export const respuestas = {};
        export async function llevar(hilo, maquina, si = false, subir = false) { pedidos.push(['llevar', hilo, maquina, si, subir]); return respuestas.pedir(si, subir); }
        export async function traer(hilo, maquina, si = false, a = '', subir = false) { pedidos.push(['traer', hilo, maquina, si, a, subir]); return respuestas.pedir(si, subir); }
        export async function mudanza(hilo, maquina = '') { pedidos.push(['mudanza', hilo, maquina]); return { datos: respuestas.progreso() }; }
        export async function seguirRevisar(hilo) { pedidos.push(['seguirRevisar', hilo]); return { datos: respuestas.revision() }; }
        export async function seguir(hilo) { pedidos.push(['seguir', hilo]); return respuestas.seguir(); }`,
    [path.join(src, 'modelo.ts')]: 'export const modelo = { mudando: new Map(), cambio: { fire() {} }, invalidar() {}, async sondear() {} };',
};
const mentira = { name: 'mentira', setup(b) {
    b.onResolve({ filter: /^\.\.?\// }, a => {
        const p = path.join(a.resolveDir, a.path) + '.ts';
        return MENTIRAS[p] ? { path: p, namespace: 'mentira' } : undefined;
    });
    b.onLoad({ filter: /.*/, namespace: 'mentira' }, a => ({ contents: MENTIRAS[a.path], loader: 'js' }));
} };
const outfile = path.join(mkdtempSync(path.join(tmpdir(), 'mudanza-')), 'mudanza.cjs');
await build({
    stdin: { contents: "export * as M from './web/mudanza'; export * as cli from './cli';", resolveDir: src, loader: 'ts' },
    bundle: true, platform: 'node', format: 'cjs', outfile, logLevel: 'warning', plugins: [mentira],
});

const w = new Window({ url: 'http://localhost/' });
for (const k of ['window', 'document', 'Element', 'HTMLElement', 'HTMLButtonElement', 'Node', 'Event', 'KeyboardEvent', 'MouseEvent', 'getComputedStyle'])
    globalThis[k] = k === 'window' ? w : w[k] ?? globalThis[k];
// happy-dom no abre un <dialog> modal: que se abra y se cierre como uno
const D = w.HTMLDialogElement?.prototype ?? w.HTMLElement.prototype;
D.showModal ??= function () { this.setAttribute('open', ''); };
D.close ??= function () { this.removeAttribute('open'); };
if (!Object.getOwnPropertyDescriptor(D, 'open')) Object.defineProperty(D, 'open', { get() { return this.hasAttribute('open'); } });
const { M, cli } = require(outfile);

const ahora = () => Date.now() / 1000;
const esperar = async (que, tope = 8000) => {
    const fin = Date.now() + tope;
    while (!que()) { if (Date.now() > fin) throw new Error('no llegó'); await new Promise(r => setTimeout(r, 30)); }
};
const PENDIENTE = { repos: [{ nombre: 'proyectos/faro', relativa: 'proyectos/faro', rama: 'main', commit: 'a1b2c3d4e5',
    del_hilo: ['plan.md'], n_del_hilo: 1, en_su_carpeta: ['mapa.png'], n_en_su_carpeta: 1, commits: [], n_commits: 0,
    puede_subir: true, por_que_no: '', pendiente: true }] };
const QUEJA = { error: 'hay trabajo sin subir: --subir para subir lo suyo y llevarla, --si para llevarla igual', cuerpo: { salida: '' } };

/** Una mudanza de mentira: la primera vez pide elegir; con lo elegido, sigue en curso y llega. */
function preparar() {
    cli.pedidos.length = 0;
    let elegido = null;
    cli.respuestas.pedir = (si, subir) => {
        if (!si && !subir) return QUEJA;
        elegido = subir ? 'subir' : 'igual';
        return { datos: { en_curso: true } };
    };
    cli.respuestas.progreso = () => elegido
        ? { paso: 'listo', hora: ahora(), aviso: elegido === 'subir' ? 'proyectos/faro: llegaron 1 commit de arriba' : '' }
        : { paso: 'revisar', hora: ahora(), pendiente: PENDIENTE, destino: [{ relativa: 'proyectos/faro', existe: true, tiene: false }],
            avisos: ['sus hijos con rama (Calendario) se quedan aquí'] };
}
const boton = texto => [...document.querySelectorAll('dialog.mudanza button')].find(b => b.textContent.includes(texto));

// ── subir y llevar ──
{
    preparar();
    let llego = false;
    const va = M.llevar('Faro', 'servidor', () => { llego = true; });
    await esperar(() => document.querySelector('dialog.mudanza .pendiente') && !document.querySelector('dialog.mudanza .pendiente').hidden);
    const texto = document.querySelector('dialog.mudanza .pendiente').textContent;
    assert.match(texto, /proyectos\/faro · main/);
    assert.match(texto, /1 archivo de este hilo sin commitear: se commitea y se sube/);
    assert.match(texto, /plan\.md/);
    assert.match(texto, /1 archivo más sin commitear en su carpeta: no sé si es suyo, no se sube/);
    assert.match(texto, /servidor va atrás \(no tiene a1b2c3d\)/);
    assert.match(texto, /sus hijos con rama \(Calendario\) se quedan aquí/);
    assert.deepEqual([...document.querySelectorAll('dialog.mudanza .seccion')].map(s => s.dataset.tono), ['sube', 'queda', 'info', 'aviso']);
    // los tres botones, y el primero (con el foco) es subir
    const textos = [...document.querySelectorAll('dialog.mudanza button')].map(b => b.textContent.trim());
    assert.equal(textos.length, 3);
    ['subir y llevar', 'llevar igual', 'no llevarlo'].forEach((x, i) => assert.ok(textos[i].includes(x), textos[i]));
    boton('subir y llevar').click();
    await va;
    assert.ok(llego, 'al llegar va a su terminal allá');
    const pedidas = cli.pedidos.filter(p => p[0] === 'llevar');
    assert.deepEqual(pedidas, [['llevar', 'Faro', 'servidor', false, false], ['llevar', 'Faro', 'servidor', false, true]]);
    assert.equal(document.querySelector('dialog.mudanza'), null, 'el panel se cierra');
}

// ── llevar igual, y no llevarlo ──
{
    preparar();
    const va = M.llevar('Faro', 'servidor', () => {});
    await esperar(() => boton('llevar igual'));
    boton('llevar igual').click();
    await va;
    assert.deepEqual(cli.pedidos.filter(p => p[0] === 'llevar').at(-1), ['llevar', 'Faro', 'servidor', true, false]);

    preparar();
    let llego = false;
    const no = M.llevar('Faro', 'servidor', () => { llego = true; });
    await esperar(() => boton('no llevarlo'));
    boton('no llevarlo').click();
    await no;
    assert.equal(llego, false);
    assert.equal(cli.pedidos.filter(p => p[0] === 'llevar').length, 1, 'no se vuelve a pedir');
    assert.equal(document.querySelector('dialog.mudanza'), null);
}

// ── nada que subir de este hilo, solo lo de su carpeta: no se ofrece subir ──
{
    preparar();
    const progreso = cli.respuestas.progreso;
    cli.respuestas.progreso = () => {
        const p = progreso();
        return p.pendiente ? { ...p, avisos: [], pendiente: { repos: [{ ...PENDIENTE.repos[0], del_hilo: [], n_del_hilo: 0, puede_subir: false }] } } : p;
    };
    const va = M.llevar('Faro', 'servidor', () => {});
    await esperar(() => boton('llevar igual'));
    assert.equal(boton('subir y llevar'), undefined);
    boton('llevar igual').click();
    await va;
}

// ── traer de otra máquina: lo mismo, con el progreso de allá ──
{
    preparar();
    const va = M.llevar('Faro', 'laptop', () => {}, { desde: 'servidor', a: '' });
    await esperar(() => boton('subir y llevar'));
    assert.match(document.querySelector('dialog.mudanza .arriba').textContent, /trayendo «Faro» de servidor a/);
    boton('subir y llevar').click();
    await va;
    assert.deepEqual(cli.pedidos.filter(p => p[0] === 'traer'), [['traer', 'Faro', 'servidor', false, '', false], ['traer', 'Faro', 'servidor', false, '', true]]);
    assert.ok(cli.pedidos.filter(p => p[0] === 'mudanza').every(p => p[2] === 'servidor'), 'el progreso se lee de la que lo tiene');
}

// ── sin nada que elegir: ni se ve ──
{
    cli.pedidos.length = 0;
    let listo = false;
    cli.respuestas.pedir = () => { listo = true; return { datos: { en_curso: false } }; };
    cli.respuestas.progreso = () => listo ? { paso: 'listo', hora: ahora() } : { paso: 'copiar', hora: ahora() };
    const va = M.llevar('Faro', 'servidor', () => {});
    await va;
    assert.equal(cli.pedidos.filter(p => p[0] === 'llevar').length, 1);
}

// ── seguir aquí, con su máquina apagada (telar.seguir): el aviso de lo que falta, y seguirlo o no ──
{
    cli.pedidos.length = 0;
    const aviso = 'Aquí está como quedó hoy 09:12 (61,2 MB). En laptop, la última vez que se lo vio (11:47), pesaba 63,8 MB: faltan unos 2,6 MB, y el agente no va a recordar lo de después.';
    cli.respuestas.revision = () => ({ puede: true, por_que_no: '', aviso, dueno: 'laptop', epoca: 6, conversacion: 'c1',
        aqui: { bytes: 61.2e6, fecha: '2026-11-24T09:12:00-03:00' }, alla: { bytes: 63.8e6 } });
    cli.respuestas.seguir = () => ({ datos: { ok: true, hecho: '«Faro» sigue aquí desde la copia de hoy 09:12 (61,2 MB); cuando laptop vuelva, cede sola' } });
    let llego = false;
    const va = M.seguirAqui('Faro', 'laptop', 'servidor', () => { llego = true; });
    await esperar(() => boton('seguir aquí'));
    assert.match(document.querySelector('dialog.mudanza .arriba').textContent, /siguiendo «Faro», con laptop apagada, en/);
    assert.match(document.querySelector('dialog.mudanza .pendiente').textContent, /faltan unos 2,6 MB/);
    assert.deepEqual([...document.querySelectorAll('dialog.mudanza .paso')].map(s => s.textContent.slice(1)),
        ['mirar la copia de aquí', 'tomarlo y abrirlo aquí', 'listo'], 'ni copiar ni cerrar allá');
    assert.ok(boton('no seguirlo'));
    boton('seguir aquí').click();
    await va;
    assert.ok(llego, 'al seguirlo, a su terminal aquí');
    assert.deepEqual(cli.pedidos.map(p => p[0]), ['seguirRevisar', 'seguir']);
    assert.equal(document.querySelector('dialog.mudanza'), null);

    // no seguirlo: no se toma nada
    cli.pedidos.length = 0;
    const no = M.seguirAqui('Faro', 'laptop', 'servidor', () => { throw new Error('no'); });
    await esperar(() => boton('no seguirlo'));
    boton('no seguirlo').click();
    await no;
    assert.deepEqual(cli.pedidos.map(p => p[0]), ['seguirRevisar']);

    // ya no se puede (volvió, o no hay copia): el panel lo dice, sin preguntar
    cli.respuestas.revision = () => ({ puede: false, por_que_no: 'laptop está en línea: «traer aquí» lo trae entero' });
    const ya = M.seguirAqui('Faro', 'laptop', 'servidor', () => {});
    await esperar(() => boton('cerrar'));
    assert.match(document.querySelector('dialog.mudanza .linea').textContent, /está en línea/);
    boton('cerrar').click();
    await ya;

    // si al tomarlo el registro cambió: la falla, y nada se abrió
    cli.respuestas.revision = () => ({ puede: true, aviso, aqui: { bytes: 1, fecha: '' } });
    cli.respuestas.seguir = () => ({ error: 'no lo tomé: el registro cambió (¿volvió laptop, o otra lo tomó antes?). Aquí no se abrió nada' });
    llego = false;
    const cambio = M.seguirAqui('Faro', 'laptop', 'servidor', () => { llego = true; });
    await esperar(() => boton('seguir aquí'));
    boton('seguir aquí').click();
    await cambio;
    assert.equal(llego, false);
    assert.match(document.querySelector('dialog.mudanza .linea').textContent, /no lo tomé/);
    boton('cerrar').click();
}

await w.happyDOM.close();
console.log('mudanza: ok');
