// Prueba de los hilos dormidos vistos desde la página (src/web/dormidos.ts, telar.dormir): qué hilo muestra cada cosa
// que se muestra, cuándo un hilo que se abre está dormido (aquí, por la lista; en otra máquina, por su foto), que lo que
// se muestra se diga al cambiar y cada 30 s (oculta, nada), y que abrir uno dormido pida despertarlo una vez, con su
// máquina; y que escribirle a un agente residente cerrado lo abra. Corre en Node, con un reloj y una API de mentira:
// npm run prueba:dormidos
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const outfile = path.join(mkdtempSync(path.join(tmpdir(), 'dormidos-')), 'dormidos.cjs');
await build({ entryPoints: [path.join(aqui, '..', 'src', 'web', 'dormidos.ts')], bundle: true, platform: 'node', format: 'cjs', outfile,
    logLevel: 'warning' });
const D = require(outfile);

// ── qué hilo es lo que se muestra ──
assert.deepEqual(D.hiloDe('Faro'), { hilo: 'Faro', maquina: '' });
assert.deepEqual(D.hiloDe('rem:servidor:Secretaría'), { hilo: 'Secretaría', maquina: 'servidor' });
assert.deepEqual(D.hiloDe('rem:servidor:Secretaría › T5 a:b'), { hilo: 'Secretaría › T5 a:b', maquina: 'servidor' }, 'un «:» en el nombre');
for (const nada of ['dashboard', 'compartir', 'config', 'doc:Faro', 'arch:/x/README.md', 'obj:tarea:T84', ''])
    assert.deepEqual(D.hiloDe(nada), { hilo: '', maquina: '' }, nada);

// ── cuándo está dormido ──
const hilos = [
    { nombre: 'Faro', vivo: true, dormido: { desde: '2026-11-19T14:32:00', conversacion: 'abc' } },
    { nombre: 'Molino', vivo: true, dormido: null },
    { nombre: 'Viejo', vivo: false, dormido: { desde: '', conversacion: '' } },   // sin ventana: no se despierta, se retoma
];
const otras = [{ nombre: 'servidor', hilos: [{ nombre: 'Secretaría', vivo: true, dormido: true }, { nombre: 'Huerto', vivo: true }] }];
assert.deepEqual(D.dormidoEn('Faro', hilos, otras), { hilo: 'Faro', maquina: '' });
assert.equal(D.dormidoEn('Molino', hilos, otras), null);
assert.equal(D.dormidoEn('Viejo', hilos, otras), null);
assert.deepEqual(D.dormidoEn('rem:servidor:Secretaría', hilos, otras), { hilo: 'Secretaría', maquina: 'servidor' });
assert.equal(D.dormidoEn('rem:servidor:Huerto', hilos, otras), null);
assert.equal(D.dormidoEn('dashboard', hilos, otras), null);

// ── decir lo que se muestra, y despertar al abrir ──
let reloj = 0;
const dichos = [], despertados = [];
const m = new D.Mirador(async (pagina, hilo, maquina) => dichos.push([hilo, maquina]),
    async (hilo, maquina) => despertados.push([hilo, maquina]), () => reloj);
assert.ok(m.pagina.length >= 4, 'cada página con su id');
assert.ok(m.decir('Faro'));
assert.ok(!m.decir('Faro'), 'lo mismo al rato: no se repite');
reloj += D.CADA;
assert.ok(m.decir('Faro'), 'a los 30 s, de nuevo');
assert.ok(m.decir('rem:servidor:Secretaría'), 'al cambiar, al tiro');
assert.ok(m.decir('rem:servidor:Secretaría', true), 'oculta: nada');
assert.ok(m.decir('dashboard', false, true), 'forzado');
assert.deepEqual(dichos, [['Faro', ''], ['Faro', ''], ['Secretaría', 'servidor'], ['', ''], ['', '']]);

assert.ok(m.alMostrar('Faro', hilos, otras), 'abrir uno dormido lo despierta');
assert.ok(!m.alMostrar('Faro', hilos, otras), 'una vez: la lista todavía no se entera');
assert.ok(!m.alMostrar('Molino', hilos, otras), 'uno despierto, nada');
assert.ok(m.alMostrar('rem:servidor:Secretaría', hilos, otras), 'el de otra máquina, a ella');
assert.deepEqual(despertados, [['Faro', ''], ['Secretaría', 'servidor']]);
reloj += D.CADA;
assert.ok(m.alMostrar('Faro', hilos, otras), 'si sigue dormido al rato, se pide de nuevo');

// ── una máquina fuera de línea (telar.alcance): que duerma allá es lo último que dijo antes de irse, y mirarlo no deja
// nada en cola (eso es el botón «despertar al volver») ──
{
    const fuera = [{ nombre: 'laptop', en_linea: false, hilos: [{ nombre: 'Catedral', vivo: true, dormido: true }] }];
    assert.equal(D.dormidoEn('rem:laptop:Catedral', hilos, fuera), null, 'su máquina no está: no se pide nada');
    const en = [{ ...fuera[0], en_linea: true }];
    assert.deepEqual(D.dormidoEn('rem:laptop:Catedral', hilos, en), { hilo: 'Catedral', maquina: 'laptop' }, 'en línea, sí');
    // la ventana de aquí de uno de allá, con su máquina fuera de línea (la lista lo dice: `alcanzable: false`)
    const vista = [{ nombre: 'Catedral', vivo: true, remoto: 'laptop', alcanzable: false, dormido: { desde: ' ', conversacion: '' } }];
    assert.equal(D.dormidoEn('Catedral', vista, []), null);
    const pedidos = [];
    const m2 = new D.Mirador(async () => undefined, async (hilo, maquina) => pedidos.push([hilo, maquina]), () => 0);
    assert.ok(!m2.alMostrar('rem:laptop:Catedral', hilos, fuera));
    assert.ok(!m2.alMostrar('Catedral', vista, []));
    assert.deepEqual(pedidos, [], 'abrirlo no lo deja en cola');
}


// ── un agente cerrado: escribirle lo abre (la caja queda en su conversación y lo escrito va como mensaje) ──
{
    const secciones = [
        { clave: 'agente:jardin', nombre: 'Jardín', hilos: ['Jardín'], home: true, grupo: 'agentes', presencia: 'a-pedido' },
        { clave: 'agente:cuaderno', nombre: 'Cuaderno', hilos: ['Cuaderno'], home: true, grupo: 'agentes', presencia: 'siempre' },
        { clave: 'agente:quieto', nombre: 'Quieto', hilos: ['Quieto'], home: true, grupo: 'agentes', presencia: 'no' },
        { clave: 'agente:viejo', nombre: 'Viejo', hilos: ['Viejo'], home: true, grupo: 'agentes' },   // un telar de antes: sin presencia
    ];
    const cerrado = nombre => ({ nombre, vivo: false, archivado: false });
    assert.ok(D.abreAlEscribir(cerrado('Jardín'), secciones, true), 'a-pedido y cerrado: escribirle lo abre');
    assert.ok(D.abreAlEscribir({ nombre: 'Jardín', vivo: false, archivado: true }, secciones, true), 'archivado, igual');
    assert.ok(D.abreAlEscribir(cerrado('Cuaderno'), secciones, true), 'siempre, si justo está cerrado');
    assert.ok(D.abreAlEscribir(cerrado('Viejo'), secciones, true), 'sin presencia: la de fábrica, a-pedido');
    assert.ok(!D.abreAlEscribir(cerrado('Quieto'), secciones, true), 'residente = no: lo que le llega espera; se retoma a mano');
    assert.ok(!D.abreAlEscribir(cerrado('Jardín'), secciones, false), 'sin bus no hay quién lo abra');
    assert.ok(!D.abreAlEscribir({ nombre: 'Jardín', vivo: true, archivado: false }, secciones, true), 'abierto: su terminal, como siempre');
    assert.ok(!D.abreAlEscribir(cerrado('Faro'), secciones, true), 'un hilo que no es de un agente: retomarlo');
    assert.ok(!D.abreAlEscribir(undefined, secciones, true));
}

console.log('prueba:dormidos ok');
