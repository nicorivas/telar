// Prueba de las notas del hilo que se ve (web/borradores.ts): los próximos prompts que la persona guarda mientras su
// agente trabaja, en su pestaña «notas» de la barra de la derecha (web/lado.ts). Con un DOM (happy-dom) y una API de
// mentira que guarda en memoria lo que le piden (nada sale):
//
// · «notas» es una pestaña más de la barra (con ficha, códigos y contexto): su ícono y su cuenta; abrirla muestra la lista
//   y la caja; ⌥B la abre desde otra hoja (o con la barra plegada) con el foco en la caja; si no cabe, va al «⋯» y desde
//   su menú se abre;
// · la lista en orden, con el número, la primera línea, cuántas más, el reloj de uno en espera y sus cuatro acciones;
// · escribir guarda solo (un nuevo al final, después el mismo con su id), y «nuevo» empieza otro;
// · ⌥⏎ lo deja en la entrada de su hilo sin ⏎ y ⌘⏎ lo envía; sale de la lista;
// · con el agente trabajando no se mezcla con su turno: pregunta, y «esperar a que termine» lo deja en espera;
// · borrar pregunta (la confirmación de la casa, ⌘⌫), y uno vacío se va sin preguntar;
// · lo escrito en la caja no llega a los atajos de la página ni a la terminal (⌘K sí), y ⎋ suelta el campo;
// · el hilo que termina su turno con guardados: el punto de «algo nuevo» en su pestaña y «terminó» sobre la caja, sin ventana;
// · la vuelta a la página (lo que guarda telar, no el navegador): otra raíz arma lo mismo con lo que la API da;
// · y en el teléfono, ⌥B (o su botón) lo abre en una ventana;
// · lo que dibuja marco.css (happy-dom no mide: se lee la regla): la caja con un solo token de espacio arriba y abajo y otro
//   a los lados, el pie pegado a ella (sin aire propio que descuadre), y en la barra la línea bajo el pie, de borde a borde.
//   Medido en un navegador (scripts/medir.py): 8,44 px arriba y abajo (--e-2), 15,6 a los lados (--h-2).
// La fila de la barra de hilos (el ícono y la cuenta, tenues), en npm run prueba:barra.
//
// Corre en Node: npm run prueba:borradores
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
const outfile = path.join(mkdtempSync(path.join(tmpdir(), 'borradores-')), 'borradores.cjs');

const w = new Window({ url: 'http://localhost/' });
for (const k of ['window', 'document', 'CSS', 'Element', 'HTMLElement', 'HTMLInputElement', 'HTMLTextAreaElement', 'HTMLDialogElement', 'Node', 'Event',
    'KeyboardEvent', 'MouseEvent', 'PointerEvent', 'CustomEvent', 'getComputedStyle', 'requestAnimationFrame', 'innerWidth', 'innerHeight', 'sessionStorage', 'localStorage', 'FocusEvent'])
    globalThis[k] = k === 'window' ? w : w[k] ?? globalThis[k];
globalThis.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {}, addListener() {} });

// ── la API de mentira: los borradores de cada hilo, en memoria, como los guarda telar ──
const pedidos = [];
const guardados = { Faro: [] };
let ocupado = '';
let n = 0;
/** cuánto tarda en contestar una lectura (ms): lo que se guarda mientras tanto no lo pisa lo leído antes */
let lento = 0;
/** cuánto tarda en guardar (ms): «nuevo» mientras se crea el anterior, y lo que se sigue escribiendo, no se pierden */
let lentoGuardar = 0;
const dormir = ms => new Promise(r => setTimeout(r, ms));
globalThis.fetch = async (url, init = {}) => {
    const u = new URL(String(url), 'http://localhost');
    const metodo = init.method ?? 'GET';
    const cuerpo = init.body ? JSON.parse(init.body) : undefined;
    pedidos.push({ metodo, ruta: u.pathname, cuerpo, q: Object.fromEntries(u.searchParams) });
    const json = (d, status = 200) => ({ ok: status < 400, status, json: async () => d, text: async () => JSON.stringify(d) });
    // la ficha del agente del hilo (web/lado.ts): Faro es un agente; los códigos y el contexto, ninguno
    if (u.pathname === '/api/agentes/del-hilo') {
        if (u.searchParams.get('hilo') !== 'Faro') return json({ detail: 'no es de un agente' }, 404);
        return json({ agente: { nombre: 'Faro', clave: 'faro', carpeta: 'casa/faro', hilos: ['Faro'], problemas: [] }, aqui: true, claude_md: '' });
    }
    if (u.pathname !== '/api/hilos/borradores' && u.pathname !== '/api/hilos/borradores/mandar') return json({ detail: 'aquí no' }, 404);
    if (u.pathname === '/api/hilos/borradores') {
        const hilo = cuerpo?.hilo ?? u.searchParams.get('hilo');
        const lista = guardados[hilo] ??= [];
        if (metodo === 'GET') { const foto = { hilo, borradores: lista.map(b => ({ ...b })), ocupado }; if (lento) await dormir(lento); return json(foto); }
        if (metodo === 'DELETE') {
            const i = lista.findIndex(b => b.id === u.searchParams.get('id'));
            if (i < 0) return json({ detail: 'ya no está' }, 404);
            return json(lista.splice(i, 1)[0]);
        }
        if (lentoGuardar) await dormir(lentoGuardar);
        if (cuerpo.id) {
            const b = lista.find(x => x.id === cuerpo.id);
            if (!b) return json({ detail: 'ya no está' }, 404);
            b.texto = cuerpo.texto;
            return json({ ...b });
        }
        const b = { id: `b${++n}`, texto: cuerpo.texto, creado: '2026-11-25T10:00:00' };
        lista.push(b);
        return json({ ...b });
    }
    if (u.pathname === '/api/hilos/borradores/mandar') {
        const lista = guardados[cuerpo.hilo] ?? [];
        const b = lista.find(x => x.id === cuerpo.id);
        if (!b) return json({ detail: 'ya no está' }, 404);
        if (cuerpo.no_esperar) { delete b.al_terminar; return json({ ...b, al_terminar: '' }); }
        if (ocupado && !cuerpo.esperar) return json({ detail: `«${cuerpo.hilo}» está trabajando`, ocupado }, 409);
        if (ocupado) { b.al_terminar = cuerpo.enviar ? 'enviar' : 'escribir'; return json({ hilo: cuerpo.hilo, id: b.id, como: 'en espera', al_terminar: b.al_terminar }); }
        lista.splice(lista.indexOf(b), 1);
        return json({ hilo: cuerpo.hilo, id: b.id, como: cuerpo.enviar ? 'enviado' : 'escrito' });
    }
    return json({});
};

await build({
    stdin: { contents: `export * as B from './web/borradores'; export * as L from './web/lado'; export * as PW from './web/pestanas';
        export { modelo } from './modelo';`, resolveDir: src, loader: 'ts' },
    bundle: true, platform: 'node', format: 'cjs', outfile, logLevel: 'warning', loader: { '.css': 'text' },
});
const { B, L, PW } = require(outfile);
const tecla = (el, key, o = {}) => el.dispatchEvent(new w.KeyboardEvent('keydown', { key, bubbles: true, cancelable: true, ...o }));
const escribir = (c, texto) => { c.value = texto; c.dispatchEvent(new w.Event('input', { bubbles: true })); };
const clic = (el, o = {}) => el.dispatchEvent(new w.MouseEvent('click', { bubbles: true, cancelable: true, ...o }));
const deLaApi = (metodo, ruta) => pedidos.filter(p => p.metodo === metodo && p.ruta === ruta);
/** lo que le llega a la página (los atajos del dashboard y la terminal escuchan afuera del bloque) */
const aLaPagina = [];
w.addEventListener('keydown', e => aLaPagina.push(e.key));
/** la ventana abierta (las confirmaciones, la del teléfono), y apretar uno de sus botones */
const ventana = () => document.querySelector('dialog');
const apretar = async texto => {
    const b = [...ventana().querySelectorAll('button')].find(x => x.textContent.toLowerCase().includes(texto));
    assert.ok(b, `la ventana tiene «${texto}»: ${ventana().textContent}`);
    clic(b);
    await dormir(20);
};

// la barra de la derecha de verdad (web/lado.ts), que arma la hoja de las notas
const barra = document.createElement('aside');
barra.id = 'lado';
document.body.appendChild(barra);
PW.atender(document);
L.montar();
const lado = barra.querySelector('.lado-notas');
const caja = () => lado.querySelector('.bor-campo');
const filas = () => [...lado.querySelectorAll('.bor-lista .item')];
const pestana = v => barra.querySelector(`.lado-cabeza .pestana[data-valor="${v}"]`);

// ── 0. «notas», una pestaña más de la barra: su ícono y su cuenta; abrirla muestra la lista y la caja ──
guardados.Faro = [
    { id: 'a', texto: 'revisa el plan\ny dime qué falta\ncon fechas' },
    { id: 'b', texto: 'después: el README', al_terminar: 'enviar' },
];
await L.mostrar('Faro', true);
await dormir(20);
assert.equal(barra.hidden, false);
assert.ok(!barra.querySelector('.bor-cab') && !barra.querySelector('.lado-hoja .borradores'), 'ya no hay un bloque fijo al pie');
assert.deepEqual([...barra.querySelectorAll('.lado-cabeza .pestana')].map(p => p.dataset.valor), ['ficha', 'notas', 'contexto'], 'la ficha del agente, sus notas y su contexto');
assert.ok(pestana('ficha').classList.contains('si') && lado.hidden && !barra.querySelector('.lado-hoja').hidden, 'abierta en la ficha: las notas, escondidas');
assert.equal(pestana('notas').querySelector('.pestana-nombre').textContent, 'notas');
assert.equal(pestana('notas').querySelector('.pestana-icono').textContent, '\u{eb26}', 'el ícono de la fila del hilo');
assert.equal(pestana('notas').querySelector('.pestana-cuenta').textContent, '2', 'y cuántas');
clic(pestana('notas'));
assert.ok(pestana('notas').classList.contains('si') && !lado.hidden && barra.querySelector('.lado-hoja').hidden, 'un clic la abre');
// un hilo que no es de un agente: sin ficha, las notas (y la barra sigue: las notas valen para cualquiera)
guardados.Suelto = [];
await L.mostrar('Suelto', true);
await dormir(20);
assert.equal(barra.hidden, false, 'la barra, en todo hilo');
assert.deepEqual([...barra.querySelectorAll('.lado-cabeza .pestana')].map(p => p.dataset.valor), ['notas', 'contexto']);
assert.ok(pestana('notas').classList.contains('si'), 'sin ficha, sigue en las notas');
assert.equal(pestana('notas').querySelector('.pestana-cuenta'), null, 'sin notas, sin cuenta');
await L.mostrar('Faro', true);
await dormir(20);

// ── 1. la lista, en orden, con lo de cada uno ──
await B.cargar('Faro', 'Faro', '', true);
assert.deepEqual(filas().map(f => f.querySelector('.item-titulo').textContent), ['revisa el plan', 'después: el README']);
assert.equal(filas()[0].querySelector('.item-ranura').textContent, '1');
assert.equal(filas()[0].querySelector('.item-sufijo').textContent, '+2', 'cuántas líneas más');
assert.ok(filas()[1].querySelector('.item-aviso').title.includes('sale cuando termine su turno, con ⏎'), 'el reloj del que espera');
assert.deepEqual([...filas()[0].querySelectorAll('.item-accion')].map(a => a.dataset.accion), ['bor-mandar', 'bor-editar', 'bor-copiar', 'bor-borrar']);
assert.equal(B.cuantos(), 2);

// un clic en el reloj le quita la espera (y no lo edita)
clic(filas()[1].querySelector('.item-aviso'));
await dormir(20);
assert.equal(deLaApi('POST', '/api/hilos/borradores/mandar').at(-1).cuerpo.no_esperar, true);
assert.equal(filas()[1].querySelector('.item-aviso'), null);
assert.equal(caja().value, '', 'el clic en el reloj no lo puso en la caja');

// ── 2. escribir guarda solo: un nuevo al final, después el mismo ──
escribir(caja(), 'el tercero');
await dormir(700);
let posts = deLaApi('POST', '/api/hilos/borradores');
assert.equal(posts.length, 1);
assert.deepEqual(posts[0].cuerpo, { hilo: 'Faro', maquina: '', texto: 'el tercero', id: '' });
escribir(caja(), 'el tercero, mejor');
caja().dispatchEvent(new w.FocusEvent('focusout', { bubbles: true }));   // soltar la caja guarda al tiro
await dormir(20);
posts = deLaApi('POST', '/api/hilos/borradores');
assert.equal(posts.length, 2);
assert.deepEqual(posts[1].cuerpo, { hilo: 'Faro', maquina: '', texto: 'el tercero, mejor', id: 'b1' });
assert.deepEqual(guardados.Faro.map(b => b.texto), ['revisa el plan\ny dime qué falta\ncon fechas', 'después: el README', 'el tercero, mejor']);
assert.ok(filas()[2].classList.contains('activa'), 'el que está en la caja, marcado');
assert.match(lado.querySelector('.bor-estado').textContent, /^guardado \d\d:\d\d$/);

// «nuevo»: la caja queda vacía y lo siguiente es otro
clic(lado.querySelector('[data-accion="bor-nuevo"]'));
await dormir(20);
assert.equal(caja().value, '');
escribir(caja(), 'el cuarto');
await dormir(700);
assert.equal(guardados.Faro.length, 4);

// ── 3. lo escrito no llega a la página ni a la terminal; ⌘K sí; ⎋ suelta el campo ──
caja().focus();
aLaPagina.length = 0;
for (const k of ['a', 'm', 'n', 'Enter']) tecla(caja(), k);
assert.deepEqual(aLaPagina, [], 'las letras se quedan en la caja');
tecla(caja(), 'k', { metaKey: true });
assert.deepEqual(aLaPagina, ['k'], '⌘K sigue');
tecla(caja(), 'Escape');
assert.notEqual(document.activeElement, caja(), '⎋ suelta el campo');
assert.deepEqual(aLaPagina, ['k']);

// ── 4. mandar: ⌥⏎ sin ⏎, ⌘⏎ enviado; sale de la lista ──
caja().focus();
tecla(caja(), 'Enter', { altKey: true });
await dormir(30);
let mandado = deLaApi('POST', '/api/hilos/borradores/mandar').at(-1).cuerpo;
assert.deepEqual([mandado.id, mandado.enviar], ['b2', false], '⌥⏎: escrito en su entrada, sin ⏎');
assert.equal(caja().value, '', 'la caja queda para el siguiente');
assert.deepEqual(filas().map(f => f.dataset.id), ['a', 'b', 'b1']);
// ▷ en una fila, con ⌘: enviado
clic(filas()[2].querySelector('[data-accion="bor-mandar"]'), { metaKey: true });
await dormir(30);
mandado = deLaApi('POST', '/api/hilos/borradores/mandar').at(-1).cuerpo;
assert.deepEqual([mandado.id, mandado.enviar], ['b1', true]);
assert.deepEqual(filas().map(f => f.dataset.id), ['a', 'b']);

// ── 5. con el agente trabajando: pregunta, y esperar lo deja en espera ──
ocupado = 'trabajando';
await B.cargar('Faro', 'Faro', '', true);
assert.match(lado.querySelector('.bor-turno').textContent, /trabajando/, 'sobre la caja, que trabaja');
clic(filas()[0].querySelector('[data-accion="bor-mandar"]'));
await dormir(30);
assert.ok(ventana()?.open, 'pregunta antes');
assert.match(ventana().textContent, /está trabajando: si se lo mandas ahora, se mezcla con su turno/);
await apretar('esperar a que termine');
mandado = deLaApi('POST', '/api/hilos/borradores/mandar').at(-1).cuerpo;
assert.deepEqual([mandado.id, mandado.esperar, mandado.enviar], ['a', true, false]);
assert.ok(filas()[0].querySelector('.item-aviso'), 'queda con su reloj');
assert.equal(filas().length, 2, 'sigue en la lista hasta que salga');

// ── 6. el hilo termina su turno con guardados: la cabecera lo recuerda ──
ocupado = '';
guardados.Faro.shift();   // lo que estaba en espera salió (lo hizo telar)
await B.cargar('Faro', 'Faro', '', true);
assert.ok(lado.classList.contains('recuerda'), 'terminó y tiene guardados');
assert.match(lado.querySelector('.bor-turno').textContent, /terminó/, 'sobre la caja lo dice');
assert.ok(pestana('notas').querySelector('.pestana-nuevo.tono-termino'), 'y su pestaña, con el punto en el color de lo que terminó');
assert.equal(document.querySelectorAll('dialog').length, 0, 'sin ventana');
assert.ok(B.recordando());
escribir(caja(), 'x');
assert.ok(!lado.classList.contains('recuerda') && !B.recordando(), 'escribir aquí lo da por visto');
assert.equal(pestana('notas').querySelector('.pestana-nuevo'), null, 'y la pestaña lo suelta');
escribir(caja(), '');
await dormir(700);

// ── 7. borrar: pregunta con la confirmación de la casa; uno vacío se va sin preguntar ──
clic(filas()[0].querySelector('[data-accion="bor-borrar"]'));
await dormir(20);
assert.ok(ventana()?.open);
const peligro = ventana().querySelector('button.tono-peligro');
assert.equal(peligro?.dataset.tecla, '⌘⌫', 'borrar va con ⌘⌫, en el de peligro');
await apretar('cancelar');
assert.equal(filas().length, 1, 'cancelado, sigue');
clic(filas()[0].querySelector('[data-accion="bor-borrar"]'));
await dormir(20);
await apretar('borrar');
assert.equal(filas().length, 0);
assert.equal(guardados.Faro.length, 0);
guardados.Faro.push({ id: 'v', texto: '  ' });
await B.cargar('Faro', 'Faro', '', true);
clic(filas()[0].querySelector('[data-accion="bor-borrar"]'));
await dormir(20);
assert.equal(document.querySelectorAll('dialog').length, 0, 'vacío: sin preguntar');
assert.equal(guardados.Faro.length, 0);

// ── 8. lo guarda telar: otra raíz (una recarga, el teléfono) arma lo mismo con lo que da la API ──
guardados.Faro.push({ id: 'r', texto: 'lo que escribí en el laptop' });
await B.cargar('Faro', 'Faro', '', true);
const otra = document.createElement('section');
document.body.appendChild(otra);
const soltarOtra = B.montarEn(otra);
assert.deepEqual([...otra.querySelectorAll('.bor-lista .item-titulo')].map(x => x.textContent), ['lo que escribí en el laptop']);
soltarOtra(); otra.remove();

// otro hilo: lo suyo, y al volver, lo de antes
guardados.Molino = [{ id: 'm', texto: 'del molino' }];
await B.cargar('Molino', 'Molino', '');
assert.deepEqual(filas().map(f => f.dataset.id), ['m']);
assert.equal(deLaApi('GET', '/api/hilos/borradores').at(-1).q.hilo, 'Molino');
await B.cargar('Faro', 'Faro', '');
assert.deepEqual(filas().map(f => f.dataset.id), ['r']);
// uno de otra máquina: se le pide a la suya
await B.cargar('rem:servidor:Telar', 'Telar', 'servidor');
assert.equal(deLaApi('GET', '/api/hilos/borradores').at(-1).q.maquina, 'servidor');
await B.cargar('Faro', 'Faro', '');

// ── 8b. al abrir la página se pasa por «ningún hilo» y después por el que se ve, sin esperar: queda el último pedido ──
await Promise.all([B.cargar('', '', ''), B.cargar('Faro', 'Faro', '')]);
assert.equal(B.deHilo(), 'Faro');
assert.equal(lado.hidden, false);
// una lectura lenta que empezó antes de guardar no borra lo recién guardado (ni lo que está en la caja)
lento = 300;
const lectura = B.cargar('Faro', 'Faro', '', true);
await dormir(10);
escribir(caja(), 'escrito mientras se leía');
caja().dispatchEvent(new w.FocusEvent('focusout', { bubbles: true }));
await lectura;
lento = 0;
await dormir(20);
assert.ok(filas().some(f => f.querySelector('.item-titulo').textContent === 'escrito mientras se leía'), 'sigue en la lista');
assert.equal(caja().value, 'escrito mientras se leía', 'y en la caja');
assert.ok(guardados.Faro.some(b => b.texto === 'escrito mientras se leía'));
clic(lado.querySelector('[data-accion="bor-nuevo"]'));
await dormir(20);

// con el servidor lento: «nuevo» mientras se crea el de antes, y se sigue escribiendo al tiro
lentoGuardar = 250;
const antesLento = guardados.Faro.length;
escribir(caja(), 'uno, lento');
caja().dispatchEvent(new w.FocusEvent('focusout', { bubbles: true }));
await dormir(20);
clic(lado.querySelector('[data-accion="bor-nuevo"]'));
escribir(caja(), 'dos, mientras');
await dormir(40);
escribir(caja(), 'dos, mientras se guardaba el uno');
await dormir(1400);
lentoGuardar = 0;
assert.equal(caja().value, 'dos, mientras se guardaba el uno', 'lo que se sigue escribiendo queda en la caja');
assert.deepEqual(guardados.Faro.slice(antesLento).map(b => b.texto), ['uno, lento', 'dos, mientras se guardaba el uno']);
assert.deepEqual(filas().slice(-2).map(f => f.querySelector('.item-titulo').textContent), ['uno, lento', 'dos, mientras se guardaba el uno']);
assert.ok(filas().at(-1).classList.contains('activa'));
clic(lado.querySelector('[data-accion="bor-nuevo"]'));
await dormir(20);

// ── 8c. ⌥B desde otra hoja: abre las notas con el foco en la caja; plegada, la despliega ──
const altB = () => w.dispatchEvent(new w.KeyboardEvent('keydown', { key: '∫', code: 'KeyB', altKey: true, bubbles: true, cancelable: true }));
caja().blur();
clic(pestana('ficha'));
assert.ok(lado.hidden);
altB();
await dormir(30);
assert.ok(pestana('notas').classList.contains('si') && !lado.hidden, '⌥B abre la pestaña de las notas');
assert.equal(document.activeElement, caja(), 'con el foco en la caja');
altB();
assert.notEqual(document.activeElement, caja(), 'otro ⌥B vuelve a donde estaba');
clic(pestana('ficha'));
clic(barra.querySelector('[data-lado="plegar"]'));
assert.ok(barra.classList.contains('plegado') && barra.querySelector('.lado-bor'), 'plegada: la franja dice cuántas');
altB();
await dormir(30);
assert.ok(!barra.classList.contains('plegado') && pestana('notas').classList.contains('si') && document.activeElement === caja(), 'plegada, ⌥B la despliega en las notas');
caja().blur();

// ── 8d. angosta: las que no caben van al «⋯»; la abierta queda; desde su menú se abre la escondida ──
// (sin dibujo, los anchos de mentira: cada pestaña 60, el «⋯» 20, la lista lo que deje la barra)
let anchoLista = 1000;
PW.medir.ancho = el => el.classList.contains('pestanas-lista') ? anchoLista : el.classList.contains('pestanas-mas') ? 20
    : el.classList.contains('pestana') ? 60 : el.classList.contains('pestanas') ? anchoLista + 30 : 0;
anchoLista = 90;
clic(pestana('ficha'));
clic(pestana('notas'));
const mas = () => barra.querySelector('.lado-cabeza .pestanas-mas');
assert.ok(!mas().hidden, 'no caben: el «⋯»');
assert.ok(pestana('ficha').classList.contains('fuera') && !pestana('notas').classList.contains('fuera'), 'la abierta queda; la otra, al «⋯»');
clic(mas());
await dormir(30);
const menuFicha = [...(ventana()?.querySelectorAll('.item') ?? [])].find(x => x.textContent.includes('ficha'));
assert.ok(menuFicha, `su menú, con la ficha: ${ventana()?.textContent}`);
clic(menuFicha);
await dormir(30);
assert.ok(pestana('ficha').classList.contains('si') && !pestana('ficha').classList.contains('fuera') && pestana('notas').classList.contains('fuera'),
    'elegida en el menú: abierta, y a la vista');
// el hilo terminó con notas guardadas y la pestaña está en el «⋯»: el punto, en el «⋯»
ocupado = 'trabajando';
await B.cargar('Faro', 'Faro', '', true);
ocupado = '';
await B.cargar('Faro', 'Faro', '', true);
assert.ok(B.recordando() && mas().querySelector('.pestana-nuevo.tono-termino'), 'lo nuevo de una escondida se nota en el «⋯»');
anchoLista = 1000;
clic(pestana('notas'));
assert.ok(mas().hidden && !pestana('ficha').classList.contains('fuera'), 'con lugar, todas y sin «⋯»');
PW.medir.ancho = el => el.getBoundingClientRect().width;

// ── 9. en el teléfono, ⌥B lo abre en una ventana ──
caja().blur();   // con el foco en la caja, ⌥B vuelve a donde se estaba
document.body.classList.add('angosto');
w.dispatchEvent(new w.KeyboardEvent('keydown', { key: '∫', code: 'KeyB', altKey: true, bubbles: true, cancelable: true }));
await dormir(30);
assert.ok(ventana()?.querySelector('.bor-ventana .borradores'), 'su ventana, con el bloque');
assert.match(ventana().textContent, /lo que escribí en el laptop/);
assert.ok(ventana().querySelector('.bor-campo'), 'con su caja');
ventana().querySelector('.bor-campo').focus();
tecla(ventana().querySelector('.bor-campo'), 'Escape');
document.body.classList.remove('angosto');

// ── 10. el dibujo (marco.css): la caja centrada en su aire, con tokens de la casa, y la línea bajo el pie ──
{
    const sinComentarios = t => t.replace(/\/\*[\s\S]*?\*\//g, '');
    const css = sinComentarios(readFileSync(path.join(aqui, '..', 'media', 'css', 'marco.css'), 'utf8'));
    const tokens = sinComentarios(readFileSync(path.join(aqui, '..', 'media', 'css', 'tokens.css'), 'utf8'));
    const regla = sel => {
        const m = css.match(new RegExp(`${sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*\\{([^}]*)\\}`));
        assert.ok(m, `marco.css tiene la regla ${sel}`);
        return Object.fromEntries(m[1].split(';').map(d => d.split(':').map(x => x.trim())).filter(d => d[0]));
    };
    const esToken = (v, familia) => {
        const m = v.match(new RegExp(`^var\\((--${familia}-\\d)\\)$`));
        assert.ok(m && new RegExp(`${m[1]}:`).test(tokens), `«${v}» es un token de espacio de la casa (--${familia}-N, en tokens.css)`);
        return m[1];
    };
    // la caja: un valor arriba y abajo (el mismo token) y uno a los lados; sin margen que lo descuadre
    const caja = regla('& .bor-caja');
    const [vertical, lados, ...resto] = caja.padding.split(/\s+/);
    assert.equal(resto.length, 0, `el relleno de la caja, dos valores (arriba = abajo, izquierda = derecha): ${caja.padding}`);
    esToken(vertical, 'e');
    esToken(lados, 'h');
    assert.ok(!caja.margin, 'la caja no suma margen');
    // el campo, sin margen; el pie, pegado a la caja: el aire de abajo es solo el de la caja
    assert.ok(!regla('& .bor-campo').margin, 'el campo no suma margen');
    assert.equal(regla('& .bor-pie')['margin-top'], '0', 'el pie no suma aire sobre el de la caja (botonera trae --boton-pie-aire)');
    // en la barra, la línea bajo el pie, la de la casa; en la ventana del teléfono la pone el borde de la ventana
    assert.equal(regla('& > .lado-notas .bor-pie')['border-bottom'], 'var(--borde)', 'la línea bajo las acciones, con --borde');
    // y que el pie, de borde a borde, lo sea: ni la hoja de las notas ni su cuerpo tienen relleno a los lados
    assert.ok(!regla('& > .lado-notas').padding && !regla('& .bor-cuerpo').padding, 'el pie va de borde a borde de la barra');
}

console.log('borradores: ok');
process.exit(0);
