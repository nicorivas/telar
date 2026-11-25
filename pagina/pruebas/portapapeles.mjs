// Prueba del portapapeles (src/web/portapapeles.ts) y del aviso que copia en su clic (web/interfaz.ts `preguntar` con
// `enElClic`, web/ui.ts `pedirCopiar`), con un DOM (happy-dom) y un navegador de mentira que hace lo que hace Safari:
// `execCommand('copy')` y `navigator.clipboard` andan solo mientras dura el evento de un clic o una tecla («el gesto»), y
// `navigator.clipboard` existe solo en contexto seguro.
// · El camino síncrono: `copiarEnElGesto` copia sin salir del evento (el texto exacto, por el evento `copy`), vuelve el
//   foco adonde estaba y, en contexto seguro, si el campo no pudo, le pide a `navigator.clipboard` ahí mismo. El botón
//   del aviso (con el mouse o con ⏎) copia en su evento; copiar después del `await` del aviso, no (la trampa de antes).
// · El de la promesa: `armar` empieza `navigator.clipboard.write` en el gesto con un ClipboardItem que espera; `dar`
//   escribe lo que llegó después, `soltar` (o el plazo) no escribe nada; por http no se arma. Y `copiarLoQueLlega` usa la
//   armada antes que nada.
// Lo mismo en WebKit, Chrome y Firefox de verdad: npm run prueba:copiar-webkit. Esta: npm run prueba:portapapeles
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
const outfile = path.join(mkdtempSync(path.join(tmpdir(), 'portapapeles-')), 'portapapeles.cjs');
await build({
    stdin: { contents: "export * as P from './web/portapapeles'; export * as interfaz from './web/interfaz'; export { pedirCopiar } from './web/ui';", resolveDir: src, loader: 'ts' },
    bundle: true, platform: 'node', format: 'cjs', outfile, logLevel: 'warning',
});

const w = new Window({ url: 'http://telar.prueba/' });
for (const k of ['window', 'document', 'navigator', 'CSS', 'Element', 'HTMLElement', 'HTMLInputElement', 'HTMLTextAreaElement', 'HTMLDialogElement', 'Node',
    'Event', 'KeyboardEvent', 'MouseEvent', 'PointerEvent', 'getComputedStyle', 'requestAnimationFrame', 'innerWidth', 'innerHeight', 'Blob'])
    Object.defineProperty(globalThis, k, { value: k === 'window' ? w : w[k] ?? globalThis[k], configurable: true, writable: true });
const { P, interfaz, pedirCopiar } = require(outfile);
const dormir = ms => new Promise(r => setTimeout(r, ms));

// ── el navegador de mentira ──
let enGesto = false;
const gesto = f => { enGesto = true; try { return f(); } finally { enGesto = false; } };
let copiado = null;           // lo que quedó en el portapapeles
let llamadas = [];            // lo que se le pidió al navegador, y si fue en el gesto
document.execCommand = cmd => {
    llamadas.push({ que: 'execCommand', enGesto });
    if (cmd !== 'copy' || !enGesto) return false;
    const e = new w.Event('copy', { bubbles: true, cancelable: true });
    let puesto = null;
    Object.defineProperty(e, 'clipboardData', { value: { setData: (_t, v) => { puesto = v; } } });
    (document.activeElement ?? document.body).dispatchEvent(e);
    const sel = document.activeElement?.tagName === 'TEXTAREA' ? document.activeElement.value : '';
    copiado = e.defaultPrevented && puesto !== null ? puesto : sel;
    return true;
};
class ClipboardItem { constructor(datos) { this.datos = datos; } }
const seguro = si => {
    Object.defineProperty(w, 'isSecureContext', { value: si, configurable: true });
    const clipboard = si ? {
        writeText(t) { llamadas.push({ que: 'writeText', enGesto }); return enGesto ? Promise.resolve().then(() => { copiado = t; }) : Promise.reject(new w.DOMException('no', 'NotAllowedError')); },
        write(items) {
            llamadas.push({ que: 'write', enGesto });
            if (!enGesto) return Promise.reject(new w.DOMException('no', 'NotAllowedError'));
            return Promise.resolve(items[0].datos['text/plain']).then(b => b.text()).then(t => { copiado = t; });
        },
    } : undefined;
    Object.defineProperty(w.navigator, 'clipboard', { value: clipboard, configurable: true });
    globalThis.ClipboardItem = si ? ClipboardItem : undefined;
};
const limpiar = () => { copiado = null; llamadas = []; };

// ── el camino síncrono ──
{
    seguro(false); limpiar();
    const antes = document.createElement('input'); document.body.appendChild(antes); antes.focus();
    const texto = 'línea uno\r\n  línea dos\t«con tabs»';
    assert.equal(await gesto(() => P.copiarEnElGesto(texto)), true, 'en el gesto, por http, copia');
    assert.equal(copiado, texto, 'el texto exacto, por el evento copy');
    assert.equal(document.activeElement, antes, 'el foco vuelve adonde estaba');
    assert.equal(document.querySelectorAll('textarea').length, 0, 'el campo escondido no queda');
    limpiar();
    assert.equal(await P.copiarEnElGesto('x'), false, 'fuera del gesto, por http, no');
    assert.deepEqual(llamadas.map(l => l.que), ['execCommand'], 'por http no hay navigator.clipboard que intentar');

    // en contexto seguro, si el campo no puede, navigator.clipboard empezado en el mismo evento
    seguro(true); limpiar();
    const orig = document.execCommand;
    document.execCommand = () => { llamadas.push({ que: 'execCommand', enGesto }); return false; };
    assert.equal(await gesto(() => P.copiarEnElGesto('seguro')), true);
    assert.deepEqual(llamadas, [{ que: 'execCommand', enGesto: true }, { que: 'writeText', enGesto: true }], 'los dos, dentro del gesto');
    assert.equal(copiado, 'seguro');
    document.execCommand = orig;
    antes.remove();
}

// ── el botón del aviso copia en su evento: con el clic y con ⏎ ──
const boton = () => document.querySelector('dialog [data-accion="b0"]');
{
    seguro(false);
    for (const como of ['clic', '⏎']) {
        limpiar();
        let p;
        const r = interfaz.preguntar('copiar', ['Copiar'], { enElClic: b => { if (b === 'Copiar') p = P.copiarEnElGesto(`por ${como}`); } });
        await dormir(0);
        assert.ok(boton(), 'el aviso está abierto con su botón');
        if (como === 'clic') gesto(() => boton().click());
        else gesto(() => boton().dispatchEvent(new w.KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })));
        assert.equal(await r, 'Copiar');
        assert.equal(await p, true, `${como}: copió en el evento`);
        assert.equal(copiado, `por ${como}`);
        assert.equal(document.querySelector('dialog'), null, 'y se cerró');
    }
    // la trampa de antes: copiar después del await del aviso ya no es el gesto (Safari)
    limpiar();
    const r = interfaz.preguntar('copiar', ['Copiar']);
    await dormir(0);
    gesto(() => boton().click());
    assert.equal(await r, 'Copiar');
    assert.equal(await P.copiar('tarde'), false, 'después del await, Safari no deja');
    // «cancelar» no copia
    limpiar();
    let llamado = false;
    const c = interfaz.preguntar('copiar', ['Copiar'], { enElClic: () => { llamado = true; } });
    await dormir(0);
    gesto(() => document.querySelector('dialog [data-accion="no"]').click());
    assert.equal(await c, undefined);
    assert.equal(llamado, false, 'cancelar no corre enElClic');
}

// ── ui.pedirCopiar: el aviso que dice qué hacer y copia en el clic ──
{
    seguro(false); limpiar();
    let listo = 0;
    const r = pedirCopiar('lo seleccionado', 'Aprieta Copiar (o ⏎).', () => { listo++; return true; });
    await dormir(0);
    assert.match(document.querySelector('dialog').textContent, /Aprieta Copiar \(o ⏎\)\.\s*«lo seleccionado»/);
    gesto(() => boton().click());
    assert.equal(await r, true);
    assert.equal(listo, 1);
    assert.equal(copiado, 'lo seleccionado');
    // si ni en el clic se puede: no dice «copiado», y deja el texto a la vista para copiarlo a mano
    limpiar();
    const orig = document.execCommand;
    document.execCommand = () => false;
    const r2 = pedirCopiar('a mano', 'Aprieta Copiar.', () => { listo++; return true; });
    await dormir(0);
    gesto(() => boton().click());
    assert.equal(await r2, false);
    assert.equal(listo, 1, 'no se dio por copiado');
    document.execCommand = orig;
    document.querySelectorAll('dialog, .aviso, [class*="aviso"]').forEach(n => n.remove());
}

// ── el camino de la promesa: armar en el gesto, escribir cuando llega ──
{
    seguro(false);
    assert.equal(gesto(() => P.armar()), undefined, 'por http no se arma');

    seguro(true); limpiar();
    const a = gesto(() => P.armar());
    assert.ok(a);
    assert.deepEqual(llamadas, [{ que: 'write', enGesto: true }], 'write empezó en el gesto');
    await dormir(10);
    assert.equal(copiado, null, 'nada escrito mientras no llega');
    assert.equal(await a.dar('llegó del servidor'), true, 'lo que llega después, fuera del gesto, se escribe');
    assert.equal(copiado, 'llegó del servidor');

    limpiar(); copiado = 'lo de antes';
    const b = gesto(() => P.armar());
    b.soltar();
    await dormir(10);
    assert.equal(copiado, 'lo de antes', 'soltarla no escribe nada');

    const c = gesto(() => P.armar(20));
    await dormir(40);
    assert.equal(copiado, 'lo de antes', 'pasado el plazo se suelta sola');
    assert.equal(await c.dar('tarde'), false, 'y lo que llega después ya no entra por ella');

    // copiarLoQueLlega: la armada primero; sin ella, fuera del gesto, no se puede (y hay que pedir el clic)
    limpiar();
    const d = gesto(() => P.armar());
    llamadas = [];
    assert.equal(await P.copiarLoQueLlega('osc 52', d), true);
    assert.equal(copiado, 'osc 52');
    assert.deepEqual(llamadas, [], 'no hizo falta nada más');
    assert.equal(await P.copiarLoQueLlega('sin armar'), false);
}

console.log('portapapeles: ok');
process.exit(0);
