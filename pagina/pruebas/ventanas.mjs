// Prueba de las ventanas que piden los módulos (src/componentes/ventana-modulo.ts y src/web/ventanas.ts): lo que lleva la
// de un chat de foco (sus líneas, la raya de lo nuevo, la caja, el pie con teclas, todo escapado) y, con un DOM
// (happy-dom) y un telar de mentira que anota lo que se le pide, lo que hace el vigía: llega una → sale; varias juntas
// en una sola; responder con ⌘⏎ por la consulta de la persona y verlo salir (o no); aplazar y que vuelva; ⎋ aplaza, nunca
// «visto»; lo de otro mundo no se pide ni queda abierto; el silencio (a mano y en una reunión) no abre nada y pide solo
// cuántas; no robar teclas (quieta mientras se escribe en otra parte, y toma el teclado con un clic); atendida en otra
// pestaña, se cierra sola; abrir el chat y mandarlo a un agente. Y lo que es obvio por su ícono va como ícono (enviar,
// aplazar, abrir el chat, mandarlo, quitar el foco, descartar, cuántos nuevos), con su nombre en el title y el aria-label y
// su tecla delante en el pie; lo que no declara un ícono que la página conozca, en palabras. Nada sale: npm run prueba:ventanas
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { Window } from 'happy-dom';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const src = path.join(aqui, '..', 'src');
const outfile = path.join(mkdtempSync(path.join(tmpdir(), 'ventanas-')), 'ventanas.cjs');
await build({
    stdin: { contents: "export * as C from './componentes/ventana-modulo'; export * as V from './web/ventanas';", resolveDir: src, loader: 'ts' },
    bundle: true, platform: 'node', format: 'cjs', outfile, logLevel: 'warning',
});

const w = new Window({ url: 'http://localhost/' });
for (const k of ['window', 'document', 'CSS', 'Element', 'HTMLElement', 'HTMLInputElement', 'HTMLTextAreaElement', 'HTMLDialogElement', 'Node', 'Event',
    'KeyboardEvent', 'MouseEvent', 'PointerEvent', 'getComputedStyle', 'requestAnimationFrame', 'innerWidth', 'innerHeight'])
    globalThis[k] = k === 'window' ? w : w[k] ?? globalThis[k];
const { C, V } = require(outfile);
const dormir = ms => new Promise(r => setTimeout(r, ms));

// ── una ventana de mentira, como la da el módulo whatsapp ──
const JID = '56911111111@s.whatsapp.net';
const ventana = (o = {}) => ({
    modulo: 'whatsapp', id: JID, version: 'a3:1', mundo: 'personal', titulo: 'Ana <Rojas>', ayuda: '', nuevos: 1, icono: 'persona',
    desde: '2026-11-23T10:42:00-03:00',
    lineas: [
        { de: 'Ana', ts: '2026-11-23T10:00:00-03:00', texto: '¿Mañana?', marca: '', nueva: false, mia: false },
        { de: 'yo', ts: '2026-11-23T10:01:00-03:00', texto: 'sí', marca: '', nueva: false, mia: true },
        { de: 'Ana', ts: '2026-11-23T10:42:00-03:00', texto: '<b>¿Llegaste?</b>', marca: '', nueva: true, mia: false },
    ],
    responder: { verbo: 'salida', params: { accion: 'enviar', chat: JID }, campo: 'texto', placeholder: 'responder a Ana…', largo: 4000,
        despues: { verbo: 'foco', params: { accion: 'atender', chat: JID, hasta: 1 } } },
    acciones: [
        { texto: 'aplazar 15 min', icono: 'aplazar', corto: '15m', tecla: '', en: 'pie', verbo: 'foco', params: { accion: 'aplazar', chat: JID, por: '15m' }, despues: null },
        { texto: 'aplazar 1 h', icono: 'aplazar', corto: '1h', tecla: '1', en: 'pie', verbo: 'foco', params: { accion: 'aplazar', chat: JID, por: '1h' }, despues: null },
        { texto: 'aplazar 3 h', icono: 'aplazar', corto: '3h', tecla: '2', en: 'pie', verbo: 'foco', params: { accion: 'aplazar', chat: JID, por: '3h' }, despues: null },
        { texto: 'aplazar hasta mañana a las 9', icono: 'aplazar', corto: 'mañana', tecla: '3', en: 'pie', verbo: 'foco', params: { accion: 'aplazar', chat: JID, por: 'manana' }, despues: null },
        { texto: 'abrir el chat', icono: 'externo', tecla: '', en: 'cabecera', abrir: 'pestana:whatsapp', item: JID, despues: { verbo: 'foco', params: { accion: 'atender', chat: JID } } },
        { texto: 'mandar a…', icono: 'instruccion', tecla: '', en: 'cabecera', instruccion: { verbo: 'contexto', params: { chat: JID } }, despues: { verbo: 'foco', params: { accion: 'atender', chat: JID } } },
        { texto: 'quitar el foco', icono: 'sinFoco', tecla: '', en: 'cabecera', verbo: 'foco', params: { accion: 'quitar', chat: JID }, despues: null },
    ],
    escape: 0, ...o,
});

// ── 1. lo que lleva: escapado, con la raya de lo nuevo, la caja y el pie con sus teclas ──
{
    const AHORA = Date.parse('2026-11-23T12:00:00-03:00');
    const p = C.propsVentanaModulo(ventana(), { cola: 3, ahora: AHORA });
    assert.equal(p.titulo, 'Ana <Rojas>', 'el título lo escapa ventana()');
    // cuántos nuevos y cuántas más esperan: íconos con su número, pegados al título, y lo que dicen en el title; sin ayuda
    assert.equal(p.ayuda, undefined, 'sin ayuda del módulo, sin línea de texto bajo el título');
    assert.equal(p.junto, '<span class="vm-nuevos" title="1 nuevo"><span class="i">\u{ea71}</span>1</span>'
        + '<span class="vm-cola" title="2 más esperan"><span class="i">\u{ebd2}</span>2</span>');
    assert.equal(C.propsVentanaModulo(ventana({ ayuda: 'grupo de <trabajo>' })).ayuda, 'grupo de <trabajo>', 'la ayuda del módulo, si la da (la escapa ventana())');
    assert.equal(C.juntoHtml({ nuevos: 0 }, {}), '', 'sin nuevos ni cola, nada');
    assert.match(p.cuerpo, /&lt;b&gt;¿Llegaste\?&lt;\/b&gt;/, 'lo que dijeron otros, escapado');
    assert.ok(!p.cuerpo.includes('<b>'));
    // la raya de lo nuevo: una línea con el punto de no leídos, sin la palabra
    assert.match(p.cuerpo, /<div class="vm-raya" role="separator" aria-label="lo nuevo" title="lo nuevo"><span class="i">\u{ea71}<\/span><\/div><div class="vm-linea nueva">/u);
    assert.match(p.cuerpo, /vm-linea mia/);
    assert.match(p.cuerpo, /<textarea class="vm-caja"[^>]*maxlength="4000"[^>]*placeholder="responder a Ana…"/);
    // el pie: tecla + ícono, con el nombre en aria-label y title
    assert.match(p.pie, /data-tecla="⌘⏎" aria-keyshortcuts="Meta\+Enter" aria-label="enviar" title="enviar: responder con lo escrito \(⌘⏎\)">/);
    assert.match(p.pie, /<span class="boton-tecla">⌘⏎<\/span><span class="boton-texto boton-simbolo"><span class="i">\u{ec0f}<\/span><\/span><\/button>/u);
    assert.deepEqual([...p.pie.matchAll(/data-tecla="([^"]+)"/g)].map(m => m[1]), ['⌘⏎', '⎋', '1', '2', '3']);
    assert.match(p.pie, /aria-label="aplazar 15 min" title="aplazar 15 min \(⎋, o un clic fuera\): vuelve a salir entonces"><span class="boton-tecla">⎋<\/span>/,
        '⎋ dice lo que hace: aplazar lo más corto');
    assert.match(p.pie, /<span class="boton-tecla">⎋<\/span><span class="boton-texto boton-simbolo"><span class="i">\u{f00a0}<\/span><span class="boton-corto">15m<\/span>/u,
        'aplazar: la campana dormida y el plazo corto');
    assert.match(p.pie, /aria-label="aplazar 1 h" title="aplazar 1 h"><span class="boton-tecla">1<\/span><span class="boton-texto boton-simbolo"><span class="i">\u{f00a0}<\/span><span class="boton-corto">1h<\/span>/u);
    for (const b of p.pie.match(/<button[^>]*>/g)) assert.match(b, /aria-label="[^"]+" title="[^"]+"/, `cada botón de ícono, con su nombre: ${b}`);
    const visible = html => html.replace(/<[^>]*>/g, ' ').replace(/[\u{e000}-\u{f8ff}\u{f0000}-\u{ffffd}]/gu, ' ').split(/\s+/).filter(Boolean);
    assert.deepEqual(visible(p.pie), ['⌘⏎', '⎋', '15m', '1', '1h', '2', '3h', '3', 'mañana'], 'en el pie, solo teclas y plazos: ninguna palabra');
    // la cabecera: un ícono por acción, con su nombre en el title y el aria-label; quitar, en rojo al pasar el mouse
    for (const [texto, g, clase] of [['abrir el chat', '\u{eb14}', ''], ['mandar a…', '\u{ead2}', ''], ['quitar el foco', '\u{f0f45}', ' quitar']])
        assert.ok(p.herramientas.includes(`<a class="vm-herr con-icono${clase}" role="button" data-vm="${ventana().acciones.findIndex(a => a.texto === texto)}" title="${texto}" aria-label="${texto}"><span class="i">${g}</span></a>`), texto);
    assert.deepEqual(visible(p.herramientas), [], 'en la cabecera, ninguna palabra');
    // lo que no declara un ícono, o uno que la página no conoce, en palabras
    const sinIcono = ventana();
    sinIcono.acciones = sinIcono.acciones.map((a, i) => ({ ...a, icono: i % 2 ? 'noExiste' : undefined }));
    const w = C.propsVentanaModulo(sinIcono);
    assert.match(w.herramientas, /<a class="vm-herr" role="button" data-vm="4">abrir el chat<\/a>/);
    assert.match(w.herramientas, /<a class="vm-herr quitar" role="button" data-vm="6">quitar el foco<\/a>/);
    assert.match(w.pie, /<span class="boton-tecla">⎋<\/span><span class="boton-texto">aplazar 15 min<\/span>/);
    assert.match(w.pie, /<span class="boton-tecla">1<\/span><span class="boton-texto">aplazar 1 h<\/span>/, 'un nombre que no es de la casa: la palabra');
    assert.equal(C.iconoDeAccion('toString'), '', 'solo los íconos de la casa, no lo heredado');
    assert.equal(C.horaDeLinea('2026-11-23T10:42:00-03:00', AHORA), new Date('2026-11-23T10:42:00-03:00').toTimeString().slice(0, 5));
    assert.match(C.horaDeLinea('2026-11-21T10:42:00-03:00', AHORA), /^21-nov \d\d:\d\d$/);
    const q = C.propsVentanaModulo(ventana(), { quieta: true, envio: { texto: 'voy', estado: 'enviando' } });
    assert.match(q.junto, /<span class="vm-quieta i" title="clic para responder: no te quita el teclado" aria-label="[^"]+">\u{f0310}<\/span>$/u,
        'quieta: el teclado tachado, con lo que significa en el title');
    assert.match(q.cuerpo, /yo:<\/span> voy <span class="vm-estado">\(enviando…\)/);
    assert.match(C.propsVentanaModulo(ventana(), { envio: { texto: 'voy', estado: 'falla', error: 'sin conexión' } }).cuerpo, /no salió: sin conexión/);
    // sin nada nuevo antes, no hay raya
    assert.ok(!C.lineasHtml({ lineas: [{ ...ventana().lineas[2] }] }).includes('vm-raya'));
}

// ── 1b. la línea que aparta el chat de lo de abajo: antes de los borradores (si hay) y de la caja de responder, de borde a
//    borde (sin margen a los lados: la llevan los bloques del cuerpo, que no tiene relleno), del color de línea ──
{
    const conBorrador = ventana({ borradores: [{ id: 'b1', de: 'Asistente', motivo: '', texto: 'voy', editable: true, aprobar: true, descartar: true }] });
    const orden = c => [...c.matchAll(/class="(vm-lineas|vm-borradores|vm-responder)"/g)].map(m => m[1]);
    assert.deepEqual(orden(C.propsVentanaModulo(ventana()).cuerpo), ['vm-lineas', 'vm-responder']);
    assert.deepEqual(orden(C.propsVentanaModulo(conBorrador).cuerpo), ['vm-lineas', 'vm-borradores', 'vm-responder'],
        'los borradores y la caja van después de las líneas: el selector de hermanos les pone la línea');
    const css = n => readFileSync(path.join(aqui, '..', 'media', 'css', `${n}.css`), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
    const v = css('ventanas');
    assert.match(v, /& \.vm-lineas ~ \.vm-borradores, & \.vm-lineas ~ \.vm-responder \{ border-top: var\(--borde\); \}/);
    assert.match(css('tokens'), /--borde: 1px solid var\(--linea\);/, 'la línea es la de la casa: 1px del color de línea');
    const regla = sel => (v.match(new RegExp(`& \\.${sel} \\{([^}]*)\\}`)) ?? [])[1] ?? '';
    for (const sel of ['vm-responder', 'vm-borradores']) assert.ok(!/margin/.test(regla(sel)), `${sel}: sin margen a los lados, de borde a borde`);
    assert.match(regla('vm-responder'), /padding: var\(--e-1\)/, 'la caja no queda pegada a la línea');
    assert.match(regla('vm-borrador'), /margin-top: var\(--e-1\)/, 'el borrador tampoco');
    assert.match(regla('vm-lineas'), /padding: 0 var\(--item-pad-x\) var\(--e-1\)/, 'ni los mensajes, arriba de ella');
}

// ── el telar de mentira ──
function telar(o = {}) {
    const t = {
        hay: [ventana()], silencio: { a_mano: false, desde: '' }, mundo: 'personal', reunion: '', ahora: 1e12,
        pedidos: [], acciones: [], abiertos: [], instrucciones: [], respuestas: {}, seguimiento: ['enviando', 'hecho'], ...o,
    };
    t.deps = {
        pedir: async (mundo, solo) => {
            t.pedidos.push({ mundo, solo });
            const vs = t.hay.filter(v => !mundo || !v.mundo || v.mundo === mundo);
            // como telar: con «no molestar» a mano, solo cuántas, se pida lo que se pida
            const sinContenido = solo || t.silencio.a_mano;
            return { datos: { ventanas: sinContenido ? [] : vs, cuantas: vs.length, fallas: [], silencio: t.silencio, modulos: ['whatsapp'] } };
        },
        accion: async (modulo, verbo, params) => {
            t.acciones.push([modulo, verbo, params]);
            if (t.respuestas[verbo]) return t.respuestas[verbo](params);
            if (verbo === 'salida' && params.accion === 'enviar') return { datos: { enviado: { id: 'm1' }, seguir: { verbo: 'salida', params: { id: 'm1' } } } };
            if (verbo === 'salida' && params.id) return { datos: { seguimiento: { estado: t.seguimiento.shift() ?? 'hecho', error: 'sin conexión' } } };
            if (verbo === 'contexto') return { datos: { texto: 'WhatsApp · Ana\n10:42 Ana: ¿Llegaste?', titulo: 'WhatsApp · Ana' } };
            return { datos: { ok: true } };
        },
        silenciar: async si => { t.silencio = { a_mano: si, desde: si ? 'x' : '' }; return { datos: t.silencio }; },
        mundo: () => t.mundo, reunion: () => t.reunion,
        abrir: (d, item) => t.abiertos.push([d, item]),
        instruccion: async (c, desde) => { t.instrucciones.push([c, desde]); return t.mandar ?? true; },
        ahora: () => t.ahora, visible: () => true,
    };
    t.vigia = new V.Vigia(t.deps, { quieto: 1500, seguirCada: 2, hecho: 2, suprimir: 8000 }, document);
    return t;
}
const dialogo = () => document.querySelector('dialog.ventana-modulo-dialogo');
const caja = () => dialogo()?.querySelector('textarea.vm-caja');
const tecla = (el, key, o = {}) => el.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true, ...o }));
// un botón por su nombre: el aria-label de uno de ícono, o la palabra
const boton = texto => [...dialogo().querySelectorAll('button.boton, a.vm-herr')].find(b => b.getAttribute('aria-label') === texto || b.textContent.endsWith(texto));
async function limpiar(t) { dialogo()?.remove(); t.vigia.abierta = null; document.body.innerHTML = ''; await dormir(1); }

// ── 2. llega → sale, una sola ventana con todo lo que llegó junto; con el mundo puesto ──
{
    const t = telar();
    await t.vigia.revisar();
    const d = dialogo();
    assert.ok(d && d.open, 'llegó algo a un chat de foco: sale su ventana');
    assert.deepEqual(t.pedidos, [{ mundo: 'personal', solo: false }], 'se pide con el mundo puesto');
    assert.equal(d.querySelector('.ventana-titulo').textContent, 'Ana <Rojas>');
    assert.equal(d.querySelectorAll('.vm-linea').length, 3);
    assert.equal(d.querySelectorAll('.vm-linea.nueva').length, 1);
    assert.ok(!d.classList.contains('quieta'), 'nadie escribía: toma el teclado');
    assert.equal(document.activeElement, caja(), 'el foco en la caja de responder');
    // preguntar de nuevo con lo mismo no abre otra
    await t.vigia.revisar();
    assert.equal(document.querySelectorAll('dialog.ventana-modulo-dialogo').length, 1, 'sin duplicar');
    // llegó otro mensaje al mismo chat: la misma ventana, con lo nuevo, y lo escrito queda
    caja().value = 'voy en';
    const v2 = ventana({ version: 'a4:2', ayuda: '2 mensajes nuevos' });
    v2.lineas = [...v2.lineas, { de: 'Ana', ts: '2026-11-23T10:43:00-03:00', texto: '¿?', marca: 'nota de voz 0:12', nueva: true, mia: false }];
    t.hay = [v2];
    await t.vigia.revisar();
    assert.equal(document.querySelectorAll('dialog.ventana-modulo-dialogo').length, 1);
    assert.equal(dialogo().querySelectorAll('.vm-linea.nueva').length, 2);
    assert.match(dialogo().querySelector('.vm-marca').textContent, /nota de voz 0:12/);
    assert.equal(caja().value, 'voy en', 'lo escrito no se pierde');
    // dos chats esperando: una a la vez, y dice cuántas más
    t.hay = [v2, ventana({ id: 'grupo@g.us', titulo: 'Familia', desde: '2026-11-23T11:00:00-03:00' })];
    await t.vigia.revisar();
    assert.equal(dialogo().querySelector('.vm-cola').title, '1 más espera');
    await limpiar(t);
}

// ── 3. responder: ⌘⏎ manda lo escrito por la consulta de la persona, lo da por atendido y lo sigue hasta que sale ──
{
    const t = telar();
    await t.vigia.revisar();
    tecla(caja(), 'Enter', { metaKey: true });
    await dormir(1);
    assert.equal(t.acciones.length, 0, 'vacío no se envía');
    assert.match(dialogo().querySelector('.vm-falla').textContent, /escribe algo/);
    caja().value = '  ya llego  ';
    tecla(caja(), '1');
    assert.equal(t.acciones.length, 0, 'un número en la caja es del texto, no aplaza');
    tecla(caja(), 'Enter', { metaKey: true });
    await dormir(0);
    assert.deepEqual(t.acciones[0], ['whatsapp', 'salida', { accion: 'enviar', chat: JID, texto: 'ya llego' }]);
    assert.match(dialogo().querySelector('.vm-envio').textContent, /yo: ya llego \(enviando…\)/);
    await dormir(20);
    assert.deepEqual(t.acciones[1], ['whatsapp', 'foco', { accion: 'atender', chat: JID, hasta: 1 }], 'después, atendido');
    assert.ok(t.acciones.slice(2).every(a => a[1] === 'salida' && a[2].id === 'm1'), 'y lo sigue');
    assert.match(document.querySelector('.vm-envio')?.textContent ?? 'cerrada', /enviado|cerrada/);
    await dormir(20);
    assert.equal(dialogo(), null, 'salió: se cierra');
    assert.ok(!t.acciones.some(a => a[1] === 'salida' && a[2].accion && a[2].accion !== 'enviar'), 'nada más que enviar');
    // lo respondido no vuelve a abrirse aunque una respuesta vieja todavía lo traiga
    await t.vigia.revisar();
    assert.equal(dialogo(), null);
    await limpiar(t);
}
{
    // no salió: lo dice, y lo escrito vuelve a la caja
    const t = telar({ seguimiento: ['falla'] });
    await t.vigia.revisar();
    caja().value = 'hola';
    dialogo().querySelector('[data-vm="responder"]').click();
    await dormir(20);
    assert.ok(dialogo(), 'queda abierta');
    assert.match(dialogo().querySelector('.vm-falla').textContent, /no salió: sin conexión/);
    assert.equal(caja().value, 'hola');
    await limpiar(t);
    // la API no lo aceptó: igual
    const t2 = telar();
    t2.respuestas.salida = () => ({ error: 'el mensaje tiene 5000 letras' });
    await t2.vigia.revisar();
    caja().value = 'x';
    dialogo().querySelector('[data-vm="responder"]').click();
    await dormir(5);
    assert.match(dialogo().querySelector('.vm-falla').textContent, /no pude enviar: el mensaje tiene 5000 letras/);
    assert.equal(caja().value, 'x');
    assert.equal(t2.acciones.length, 1, 'sin atender lo que no salió');
    await limpiar(t2);
}

// ── 4. aplazar: el botón (o su número, con el foco fuera de la caja) y vuelve a su hora; ⎋ aplaza, nunca «visto» ──
{
    const t = telar();
    await t.vigia.revisar();
    boton('aplazar 1 h').focus();
    tecla(boton('aplazar 1 h'), '1');
    await dormir(1);
    assert.deepEqual(t.acciones, [['whatsapp', 'foco', { accion: 'aplazar', chat: JID, por: '1h' }]]);
    assert.equal(dialogo(), null, 'aplazada: se cierra');
    t.hay = [];
    await t.vigia.revisar();
    assert.equal(dialogo(), null);
    // a su hora el módulo la vuelve a dar
    t.hay = [ventana({ version: 'a5:2' })];
    t.ahora += 60 * 60 * 1000;
    await t.vigia.revisar();
    assert.ok(dialogo(), 'vuelve a salir, con lo de entretanto');
    // ⎋: el plazo más corto (`escape`), no atender
    t.acciones = [];
    dialogo().dispatchEvent(new Event('cancel', { cancelable: true }));
    await dormir(1);
    assert.deepEqual(t.acciones, [['whatsapp', 'foco', { accion: 'aplazar', chat: JID, por: '15m' }]]);
    assert.ok(!t.acciones.some(a => a[2].accion === 'atender'), '⎋ nunca es «visto»');
    await limpiar(t);
}

// ── 5. los mundos: se pide con el puesto; al cambiar, lo abierto de otro se cierra al tiro ──
{
    const t = telar({ mundo: 'trabajo', hay: [ventana({ mundo: 'personal' })] });
    await t.vigia.revisar();
    assert.equal(dialogo(), null, 'lo de personal no sale en trabajo');
    assert.equal(t.pedidos[0].mundo, 'trabajo');
    t.mundo = 'personal';
    t.vigia.alCambiarMundo();
    await dormir(1);
    assert.ok(dialogo(), 'en su mundo, sale');
    t.mundo = 'trabajo';
    t.vigia.alCambiarMundo();
    assert.equal(dialogo(), null, 'vuelta a trabajo: se cierra sin esperar respuesta');
    await t.vigia.revisar();
    assert.equal(dialogo(), null);
    t.mundo = '';
    await t.vigia.revisar();
    assert.ok(dialogo(), 'con ambos, sale');
    await limpiar(t);
}

// ── 6. el silencio: a mano o en una reunión no abre nada, pide solo cuántas, y al terminar sale lo que llegó ──
{
    const t = telar({ silencio: { a_mano: true, desde: 'x' } });
    await t.vigia.revisar();
    assert.equal(dialogo(), null, 'no molestar: nada');
    await t.vigia.revisar();
    assert.deepEqual(t.pedidos.at(-1), { mundo: 'personal', solo: true }, 'en silencio, solo cuántas');
    assert.equal(t.vigia.cuantas, 1);
    const s = V.silencioHtml(t.vigia);
    assert.ok(s.si);
    assert.match(s.html, /no molestar · 1/);
    assert.match(s.ayuda, /1 espera y salen al terminar/);
    await t.vigia.silenciar(false);
    assert.ok(dialogo(), 'al apagarlo, sale lo que llegó');
    // una reunión que empieza con la ventana abierta: se cierra
    t.reunion = 'en reunión';
    await t.vigia.revisar();
    assert.equal(dialogo(), null);
    assert.equal(t.vigia.enSilencio(), 'en reunión');
    assert.match(V.silencioHtml(t.vigia).html, /en reunión · 1/);
    t.reunion = '';
    await t.vigia.revisar();
    assert.ok(dialogo(), 'terminó la reunión: sale');
    assert.ok(!V.silencioHtml(t.vigia).si);
    await limpiar(t);
}

// ── 7. no robar teclas: mientras se escribe en otra parte sale quieta, sin el foco; un clic la toma ──
{
    const t = telar();
    const otra = document.createElement('textarea');
    otra.className = 'xterm-helper-textarea';
    document.body.appendChild(otra);
    otra.focus();
    t.vigia.montar();   // escucha las teclas
    for (const c of 'ls -l') { tecla(otra, c); otra.value += c; }
    await t.vigia.revisar();
    const d = dialogo();
    assert.ok(d && d.open, 'sale');
    assert.ok(d.classList.contains('quieta'), 'quieta: sin fondo ni foco');
    assert.equal(document.activeElement, otra, 'el foco sigue donde se escribía');
    assert.match(d.querySelector('.ventana-junto .vm-quieta').title, /no te quita el teclado/);
    for (const c of ' /tmp') { tecla(otra, c); otra.value += c; }
    assert.equal(otra.value, 'ls -l /tmp', 'todo lo escrito llegó a su caja');
    assert.equal(caja().value, '', 'nada a la de la ventana');
    // sin teclear un rato, pero con el foco en la terminal: sigue esperando un clic
    t.ahora += 5000;
    await dormir(300);
    assert.ok(d.classList.contains('quieta'), 'el foco en un campo: no se lo quita');
    // un clic en ella: modal, con el foco en su caja
    caja().dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
    assert.ok(!d.classList.contains('quieta'));
    assert.ok(d.open);
    assert.equal(document.activeElement, caja());
    await limpiar(t);
    // el foco fuera de los campos y sin teclear: la toma sola
    const t2 = telar();
    document.body.appendChild(otra);
    otra.focus();
    t2.vigia.montar();
    tecla(otra, 'x');
    await t2.vigia.revisar();
    assert.ok(dialogo().classList.contains('quieta'));
    otra.blur();
    t2.ahora += 2000;
    await dormir(300);
    assert.ok(!dialogo().classList.contains('quieta'), 'pasó el rato sin teclear y el foco salió del campo: la toma');
    assert.equal(document.activeElement, caja());
    await limpiar(t2);
    assert.equal(V.puedeTomar(null, 0, 10000, 1500, document), true);
    assert.equal(V.puedeTomar(document.body, 9000, 10000, 1500, document), false, 'una tecla hace un segundo');
    const marco = document.createElement('iframe');
    assert.equal(V.puedeTomar(marco, 0, 10000, 1500, document), false, 'un lienzo (la caja de la pestaña whatsapp) es un campo');
}

// ── 8. atendida en otra pestaña (o en el teléfono): se cierra sola ──
{
    const t = telar();
    await t.vigia.revisar();
    assert.ok(dialogo());
    t.hay = [];
    await t.vigia.revisar();
    assert.equal(dialogo(), null, 'el módulo ya no la da: se cierra');
    assert.equal(t.acciones.length, 0, 'sin hacer nada aquí');
    await limpiar(t);
}

// ── 8b. cerrada por el navegador sin pasar por la ventana (un ⎋ que no se deja cancelar): no queda una esperando ──
{
    const t = telar();
    await t.vigia.revisar();
    dialogo().close();
    await dormir(5);
    assert.equal(t.vigia.abierta, null, 'sin una ventana cerrada que tape a las que vienen');
    await t.vigia.revisar();
    assert.ok(dialogo()?.open, 'sigue esperando en el módulo: vuelve a salir');
    await limpiar(t);
}

// ── 9. abrir el chat, mandarlo a un agente, quitar el foco ──
{
    const t = telar();
    await t.vigia.revisar();
    boton('abrir el chat').click();
    await dormir(1);
    assert.deepEqual(t.abiertos, [['pestana:whatsapp', JID]]);
    assert.deepEqual(t.acciones, [['whatsapp', 'foco', { accion: 'atender', chat: JID }]]);
    assert.equal(dialogo(), null);
    await limpiar(t);
    const t2 = telar();
    await t2.vigia.revisar();
    boton('mandar a…').click();
    await dormir(5);
    assert.equal(t2.instrucciones.length, 1);
    assert.equal(t2.instrucciones[0][0].titulo, 'WhatsApp · Ana');
    assert.match(t2.instrucciones[0][1], /la ventana de «Ana <Rojas>»/);
    assert.deepEqual(t2.acciones.map(a => a[1]), ['contexto', 'foco'], 'mandado: atendido');
    await limpiar(t2);
    const t3 = telar({ mandar: false });
    await t3.vigia.revisar();
    boton('mandar a…').click();
    await dormir(5);
    assert.deepEqual(t3.acciones.map(a => a[1]), ['contexto'], 'cancelada la instrucción: no se atiende');
    await t3.vigia.revisar();
    assert.ok(dialogo(), 'y vuelve a salir');
    boton('quitar el foco').click();
    await dormir(1);
    assert.deepEqual(t3.acciones.at(-1), ['whatsapp', 'foco', { accion: 'quitar', chat: JID }]);
    assert.equal(dialogo(), null);
    await limpiar(t3);
}

// ── 10. el borrador de un agente para ese chat: se ve, se edita, se aprueba (por la consulta de la pestaña) o se descarta ──
{
    const borrador = (id, o = {}) => ({ id, de: 'Ana, nota de voz', texto: 'Agente: <llego> a las diez', motivo: 'preguntó la hora', sale: '', editable: true,
        aprobar: { verbo: 'salida', params: { accion: 'aprobar', id }, campo: 'texto', despues: { verbo: 'foco', params: { accion: 'atender', chat: JID, hasta: 1 } } },
        descartar: { verbo: 'salida', params: { accion: 'descartar', id } }, ...o });
    {
        const h = C.borradoresHtml([borrador('b1', { sale: '08:30' })]);
        // el ícono de borrador y quién; por qué, tenue; «borrador de» en el title
        assert.match(h, /<div class="vm-bcab" title="borrador de Ana, nota de voz: preguntó la hora; espera que lo apruebes"><span class="i" aria-label="borrador de">\u{ec0f}<\/span> Ana, nota de voz <span class="vm-bmotivo">· preguntó la hora<\/span><\/div>/u);
        assert.match(h, /&lt;llego&gt;/, 'escapado');
        // enviar: el ícono (fuera de su ventana, con la hora a la que sale); descartar: el basurero
        assert.match(h, /data-vm="aprobar:0" style="--c: var\(--verde\)" aria-label="aprobar: sale a las 08:30" title="aprobar: sale a las 08:30: [^"]+"><span class="boton-texto boton-simbolo"><span class="i">\u{ec0f}<\/span><span class="boton-corto">08:30<\/span>/u,
            'fuera de su ventana, dice cuándo sale');
        assert.match(h, /data-vm="descartar:0" aria-label="descartar" title="descartar: que no salga"><span class="boton-texto boton-simbolo"><span class="i">\u{ea81}<\/span><\/span>/u);
        assert.match(C.borradoresHtml([borrador('b1')]), /aria-label="enviar" title="enviar: [^"]+"><span class="boton-texto boton-simbolo"><span class="i">\u{ec0f}<\/span><\/span>/u);
        assert.equal(C.borradoresHtml([]), '');
    }
    const t = telar({ hay: [ventana({ borradores: [borrador('b1'), borrador('b2', { texto: 'Agente: otra' })] })] });
    await t.vigia.revisar();
    assert.equal(dialogo().querySelectorAll('.vm-borrador').length, 2, 'los borradores del chat, en su ventana');
    // descartar uno: la ventana queda, sin él
    dialogo().querySelector('[data-vm="descartar:1"]').click();
    await dormir(2);
    assert.deepEqual(t.acciones.at(-1), ['whatsapp', 'salida', { accion: 'descartar', id: 'b2' }]);
    assert.ok(dialogo(), 'descartar no la cierra: lo que llegó sigue sin respuesta');
    assert.equal(dialogo().querySelectorAll('.vm-borrador').length, 1);
    // lo editado sobrevive a lo que llega mientras tanto
    const editado = dialogo().querySelector('[data-vb="b1"] textarea.vm-btexto');
    editado.value = 'Agente: llego a las once';
    t.hay = [ventana({ version: 'a9:2', borradores: [borrador('b1')] })];
    await t.vigia.revisar();
    assert.equal(dialogo().querySelector('[data-vb="b1"] textarea.vm-btexto').value, 'Agente: llego a las once');
    // ⌘⏎ en el borrador lo aprueba a él (no la caja de responder), con lo editado; y es responder: atendida, se cierra
    tecla(dialogo().querySelector('[data-vb="b1"] textarea.vm-btexto'), 'Enter', { metaKey: true });
    await dormir(2);
    assert.deepEqual(t.acciones.slice(-2), [['whatsapp', 'salida', { accion: 'aprobar', id: 'b1', texto: 'Agente: llego a las once' }],
        ['whatsapp', 'foco', { accion: 'atender', chat: JID, hasta: 1 }]]);
    assert.ok(!t.acciones.some(a => a[2].accion === 'enviar'), 'aprobar no es escribir como la persona');
    assert.equal(dialogo(), null);
    await limpiar(t);
    // si no se pudo, lo dice y la ventana queda
    const t2 = telar({ hay: [ventana({ borradores: [borrador('b1')] })] });
    t2.respuestas.salida = () => ({ error: 'ese mensaje ya salió (o falló): no se cambia' });
    await t2.vigia.revisar();
    dialogo().querySelector('[data-vm="aprobar:0"]').click();
    await dormir(2);
    assert.match(dialogo().querySelector('.vm-falla').textContent, /no pude aprobarlo: ese mensaje ya salió/);
    await limpiar(t2);
}

console.log('ventanas: ok');
process.exit(0);
