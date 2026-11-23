// Prueba de una máquina fuera de línea vista desde la página (src/web/alcance.ts, telar.alcance): desde cuándo en palabras
// («14:02», «ayer 14:02»), lo que dice la franja («laptop fuera de línea desde 14:02», con sus hilos inalcanzables y lo que
// les espera en cola), lo que se hizo de esa cola al volver, la ayuda de un hilo inalcanzable y el cuadro de su terminal,
// con la banda de botones de la casa (componentes/boton.ts). Corre en Node, sin página: npm run prueba:alcance
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const outfile = path.join(mkdtempSync(path.join(tmpdir(), 'alcance-')), 'alcance.cjs');
await build({ entryPoints: [path.join(aqui, '..', 'src', 'web', 'alcance.ts')], bundle: true, platform: 'node', format: 'cjs', outfile,
    logLevel: 'warning' });
const A = require(outfile);

// el reloj: 22-nov, 16:30 (hora local de quien corre la prueba)
const AHORA = new Date(2026, 10, 22, 16, 30).getTime();
const a = (d, h, m) => new Date(2026, 10, d, h, m).getTime();

// ── desde cuándo, como lo dice telar ──
assert.equal(A.desdeTexto(a(22, 14, 2), AHORA), '14:02');
assert.equal(A.desdeTexto(a(21, 23, 50), AHORA), 'ayer 23:50');
assert.equal(A.desdeTexto(a(2, 9, 5), AHORA), 'el 2-nov 09:05');
assert.equal(A.desdeTexto(undefined, AHORA), '?');

// la máquina, con la edad de su foto (la mide el servidor): 2 h 28 min → desde las 14:02
const laptop = { nombre: 'laptop', en_linea: false, fuera: true, edad: (AHORA - a(22, 14, 2)) / 1000, cola: [], hechos: [],
    hilos: [{ nombre: 'Catedral', vivo: true, dormido: true }, { nombre: 'Nave', vivo: true, atencion: 'trabajando' }, { nombre: 'Viejo', vivo: false }] };
assert.equal(A.fueraDeLinea(laptop, AHORA), 'laptop fuera de línea desde 14:02');
assert.equal(A.fueraDe('laptop', [laptop])?.nombre, 'laptop');
assert.equal(A.fueraDe('laptop', [{ ...laptop, fuera: false }]), undefined, 'sin saberlo (el nodo de aquí sin noticias), no');
assert.equal(A.fueraDe('servidor', [laptop]), undefined);

// ── un hilo inalcanzable: lo que hacía cuando se fue, y qué se puede hacer igual ──
assert.equal(A.antes({ vivo: true, dormido: true }), 'dormía');
assert.equal(A.antes({ vivo: true, atencion: 'espera' }), 'te esperaba');
assert.equal(A.antes({ vivo: true, atencion: 'ninguna' }), '');
assert.equal(A.antes({ vivo: false, dormido: true }), '', 'uno cerrado no hacía nada');
assert.equal(A.ayudaInalcanzable(laptop, laptop.hilos[0], AHORA),
    'laptop fuera de línea desde 14:02: inalcanzable (cuando se fue, dormía).\nDespertarlo o escribirle queda en cola y se hace cuando vuelva.');

// ── la franja: una nota que dice desde cuándo, sus hilos abiertos y lo que les espera en cola ──
{
    const f = A.avisoFuera(laptop, AHORA);
    assert.equal(f.clave, 'maquina:laptop');
    assert.equal(f.nivel, 'nota', 'apagada es lo normal: una nota, no una falla');
    assert.equal(f.texto, 'laptop fuera de línea desde 14:02');
    assert.equal(f.desde, a(22, 14, 2));
    assert.match(f.detalle, /^Sus 2 hilos abiertos cuando se fue se ven como estaban, inalcanzables: no se sabe si siguen vivos o dormidos\./);
    assert.match(f.hacer, /queda en cola y se hace cuando vuelva/);
    const conCola = A.avisoFuera({ ...laptop, cola: [{ id: 'p1', hilo: 'Catedral', texto: 'sigue', cuando: a(22, 14, 5) / 1000 }] }, AHORA);
    assert.match(conCola.detalle, /en cola desde 14:05: despertar a «Catedral», con un texto\.$/);
    // sin hilos abiertos ni cola, nada que decir
    assert.equal(A.avisoFuera({ ...laptop, hilos: [{ nombre: 'Viejo', vivo: false }] }, AHORA), null);
    // sin hilos abiertos pero con cola: se dice
    assert.ok(A.avisoFuera({ ...laptop, hilos: [], cola: conCola ? [{ id: 'p1', hilo: 'Catedral', cuando: a(22, 14, 5) / 1000 }] : [] }, AHORA));
}

// ── lo que se hizo de la cola al volver: una nota (o una falla) por cada uno, la última media hora ──
{
    const hechos = [
        { id: 'p1', hilo: 'Catedral', cuando: a(22, 14, 5) / 1000, hecho_en: a(22, 16, 20) / 1000, ok: true, resultado: '«Catedral» despertó (conversación c4t3)' },
        { id: 'p2', hilo: 'Nave', cuando: a(22, 14, 6) / 1000, hecho_en: a(22, 16, 21) / 1000, ok: false, resultado: 'no se pudo despertar a «Nave» en laptop: aquí no hay un hilo «Nave»' },
        { id: 'p3', hilo: 'Viejo', cuando: a(22, 9, 0) / 1000, hecho_en: a(22, 10, 0) / 1000, ok: true, resultado: 'hace rato' },
    ];
    const l = A.avisosHechos({ ...laptop, en_linea: true, fuera: false, hechos }, AHORA);
    assert.deepEqual(l.map(x => [x.clave, x.nivel]), [['cola:laptop:p1', 'nota'], ['cola:laptop:p2', 'falla']], 'lo de hace horas ya no');
    assert.equal(l[0].texto, '«Catedral» despertó en laptop al volver');
    assert.match(l[0].detalle, /^Lo pediste a las 14:05, con laptop fuera de línea: «Catedral» despertó/);
    assert.equal(l[1].texto, '«Nave» no se pudo despertar en laptop');
}

// ── el cuadro de su terminal: qué pasa, lo que le espera en cola y la banda de botones de la casa ──
{
    const html = A.panelFuera('Catedral', laptop, AHORA);
    assert.match(html, /^<div class="titulo"><span class="i">[^<]+<\/span> laptop fuera de línea desde 14:02<\/div>/);
    assert.match(html, /«Catedral» vive allá: su terminal vuelve cuando vuelva laptop/);
    assert.match(html, /<div class="ventana-pie botonera">/, 'la tecla en el pie: pieBotones');
    const botones = [...html.matchAll(/<button type="button" class="boton tono-accion"[^>]*data-accion="([a-z]+)"[^>]*>/g)].map(m => m[1]);
    assert.deepEqual(botones, ['despertar', 'escribirle', 'reintentar']);
    assert.match(html, /<span class="boton-texto">despertar al volver<\/span>/);
    assert.doesNotMatch(html, /disabled/, 'nada en cola: se puede pedir');
    // ya en cola: dice desde cuándo, y el botón se apaga
    const enCola = A.panelFuera('Catedral', { ...laptop, cola: [{ id: 'p1', hilo: 'Catedral', cuando: a(22, 14, 5) / 1000 },
        { id: 'p2', hilo: 'Otro', cuando: a(22, 14, 6) / 1000 }] }, AHORA);
    assert.match(enCola, /<div class="motivo cola">en cola desde 14:05: despertar a «Catedral»<\/div>/);
    assert.doesNotMatch(enCola, /«Otro»/, 'solo lo suyo');
    assert.match(enCola, /data-accion="despertar"[^>]* disabled><span class="boton-tecla boton-icono i">[^<]+<\/span><span class="boton-texto">ya en cola</);
    // en su conversación (la vista del teléfono): la caja de abajo ya le escribe, así que solo despertarlo
    const conv = A.panelFuera('Catedral', laptop, AHORA, { conversacion: true });
    assert.deepEqual([...conv.matchAll(/data-accion="([a-z]+)"/g)].map(m => m[1]), ['despertar']);
    assert.match(conv, /su conversación se ve cuando vuelva laptop\. Lo que le escribas abajo espera en el bus y le llega al volver/);
    // lo que se escribe va escapado
    assert.match(A.panelFuera('<b>', laptop, AHORA), /«&lt;b&gt;» vive allá/);
}

console.log('prueba:alcance ok');
