// Prueba de lo que el lienzo de un módulo pide y la página atiende sola (src/vistas/dashboard/pedidos-locales.ts):
// `abrir` abre la dirección en la página (lo mismo que un clic en un enlace a ella), `menu` abre su menú e `instruccion`
// abre la ventana de la instrucción con un contexto, sin llegar al servidor ni pedir permiso; lo demás (fecha, idea,
// consulta) sigue al servidor. Y que el panel lo use, con `ui.abrirDireccion` para abrir. Corre en Node:
// npm run prueba:lienzo
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const dashboard = path.join(aqui, '..', 'src', 'vistas', 'dashboard');
const salida = path.join(mkdtempSync(path.join(tmpdir(), 'lienzo-')), 'pedidos.cjs');
await build({ entryPoints: [path.join(dashboard, 'pedidos-locales.ts')], bundle: true, platform: 'node', format: 'cjs',
    outfile: salida, logLevel: 'warning' });
const { LOCALES, atender, direccionDe, nombreDeDestino, pedidoDeInstruccion } = require(salida);

/** Lo que pasa con un pedido: lo que la página hizo y lo que le contestó al lienzo (undefined: fue al servidor).
 *  `ventana`: lo que hace la ventana de la instrucción con lo que recibe (lo que devuelve es lo que pasó al cerrarse). */
async function pedir(orden, datos, donde, ventana = async () => ({ destino: 'Vigía', como: 'encargado', maquina: '' })) {
    const hecho = [], respuestas = [];
    const p = atender(orden, datos, donde, {
        menu: async (d, donde) => { hecho.push(['menu', d, donde]); },
        abrir: async d => { hecho.push(['abrir', d]); },
        instruccion: async p => { hecho.push(['instruccion', p]); return await ventana(p); },
    }, r => respuestas.push(r));
    if (p === undefined) return { alServidor: true, hecho, respuestas };
    await p;
    return { alServidor: false, hecho, respuestas };
}

// 1. abrir: la dirección, tal cual, a lo que abre un enlace; el lienzo recibe ok
{
    for (const d of ['decision:casa/D-001', 'tarea:T84', 'hilo:Faro', 'hilo:Faro@servidor', 'hilo:◌%20a%20solas']) {
        const r = await pedir('abrir', { direccion: d });
        assert.equal(r.alServidor, false, `${d}: abrir no va al servidor`);
        assert.deepEqual(r.hecho, [['abrir', d]]);
        assert.deepEqual(r.respuestas, [{ ok: true }]);
    }
    // los espacios de los bordes no son de la dirección
    assert.deepEqual((await pedir('abrir', { direccion: '  tarea:T84 ' })).hecho, [['abrir', 'tarea:T84']]);
}

// 2. abrir sin dirección, o con algo que no es una: no abre nada y el lienzo sabe por qué
{
    for (const datos of [undefined, null, {}, { direccion: '' }, { direccion: 42 }]) {
        const r = await pedir('abrir', datos);
        assert.equal(r.alServidor, false);
        assert.deepEqual(r.hecho, []);
        assert.deepEqual(r.respuestas, [{ ok: false, error: 'falta la dirección' }]);
    }
    for (const d of ['T84', 'Tarea:T84', 'tarea:', 'tarea: T84', ':T84']) {
        const r = await pedir('abrir', { direccion: d });
        assert.deepEqual(r.hecho, [], `${d}: no es una dirección`);
        assert.equal(r.respuestas.length, 1);
        assert.equal(r.respuestas[0].ok, false);
        assert.match(r.respuestas[0].error, /no es una dirección/);
    }
}

// 3. menu: igual que antes, junto al punto donde se hizo clic
{
    const r = await pedir('menu', { direccion: 'hipotesis:casa/H-001', x: 3, y: 4 }, { x: 103, y: 204 });
    assert.equal(r.alServidor, false);
    assert.deepEqual(r.hecho, [['menu', 'hipotesis:casa/H-001', { x: 103, y: 204 }]]);
    assert.deepEqual(r.respuestas, [{ ok: true }]);
    const sin = await pedir('menu', {});
    assert.deepEqual(sin.hecho, []);
    assert.deepEqual(sin.respuestas, [{ ok: false, error: 'falta la dirección' }]);
}

// 4. lo demás va al servidor (que pide permiso para lo que cambia tus documentos), sin contestar aquí
{
    for (const orden of ['fecha', 'idea', 'consulta', 'abrir-enlace', '']) {
        const r = await pedir(orden, { direccion: 'tarea:T84' });
        assert.equal(r.alServidor, true, `${orden} va al servidor`);
        assert.deepEqual(r.hecho, []);
        assert.deepEqual(r.respuestas, []);
    }
    assert.deepEqual([...LOCALES], ['menu', 'abrir', 'instruccion']);
    assert.equal(direccionDe({ direccion: ' x:y ' }), 'x:y');
}

// 5. instruccion: abre la ventana con el contexto (un texto, o {texto, titulo, direccion}), el destino pedido y lo escrito;
//    el lienzo recibe lo que pasó al cerrarse la ventana: a quién llegó, o null si se canceló
{
    const chat = Array.from({ length: 80 }, (_, i) => `[12:${String(i % 60).padStart(2, '0')}] alguien: mensaje ${i}`).join('\n');
    const r = await pedir('instruccion', { contexto: chat });
    assert.equal(r.alServidor, false, 'la instrucción no va al servidor: la manda la persona en la ventana');
    assert.deepEqual(r.hecho, [['instruccion', { contexto: { texto: chat, titulo: '', direccion: '' }, destino: '', texto: '' }]]);
    assert.equal(r.hecho[0][1].contexto.texto.split('\n').length, 80, 'el contexto llega entero, con sus líneas');
    assert.deepEqual(r.respuestas, [{ ok: true, datos: { destino: 'Vigía', como: 'encargado', maquina: '' } }]);

    const conTodo = await pedir('instruccion', { contexto: { texto: 'hola', titulo: ' Chat del equipo ', direccion: 'tarea:T84' },
        destino: 'agente:vigia', texto: 'resúmelo' });
    assert.deepEqual(conTodo.hecho[0][1], { contexto: { texto: 'hola', titulo: 'Chat del equipo', direccion: 'tarea:T84' },
        destino: 'agente:vigia', texto: 'resúmelo' });
    // solo una entidad, sin texto, también sirve
    assert.equal((await pedir('instruccion', { contexto: { direccion: 'hilo:Faro' } })).respuestas[0].ok, true);

    // cancelada: se cumple con null (no es un error); si no se pudo mandar, falla con el porqué
    assert.deepEqual((await pedir('instruccion', { contexto: 'x' }, undefined, async () => undefined)).respuestas, [{ ok: true, datos: null }]);
    const falla = await pedir('instruccion', { contexto: 'x' }, undefined, async () => { throw new Error('el bus no responde'); });
    assert.deepEqual(falla.respuestas, [{ ok: false, error: 'el bus no responde' }]);

    // lo que no sirve no abre nada, y el lienzo sabe por qué
    for (const [datos, motivo] of [
        [undefined, /falta el contexto/], [{}, /falta el contexto/], [{ contexto: 3 }, /falta el contexto/],
        [{ contexto: '  ' }, /vacío/], [{ contexto: { titulo: 'solo título' } }, /vacío/],
        [{ contexto: { texto: 4 } }, /todos textos/],
        [{ contexto: { texto: 'x', direccion: 'T84' } }, /no es una dirección/],
        [{ contexto: 'x', destino: 'tarea:T84' }, /no es un destino/], [{ contexto: 'x', destino: 7 }, /el destino es un texto/],
        [{ contexto: 'x', texto: ['no'] }, /es un texto/],
    ]) {
        const r = await pedir('instruccion', datos);
        assert.deepEqual(r.hecho, [], `${JSON.stringify(datos)} no abre la ventana`);
        assert.equal(r.respuestas.length, 1);
        assert.equal(r.respuestas[0].ok, false);
        assert.match(r.respuestas[0].error, motivo);
    }
    assert.equal(typeof pedidoDeInstruccion({ contexto: 'x', destino: 'Vigía' }), 'object', 'un nombre suelto es un destino');
}

// 6. el destino, como se nombra en la ventana: un agente por su carpeta o su nombre, un hilo por el suyo
{
    const agentes = [{ clave: 'agente:vigia', nombre: 'Vigía' }, { clave: 'agente:molino', nombre: 'Molino' }];
    assert.equal(nombreDeDestino('agente:vigia', agentes), 'Vigía');
    assert.equal(nombreDeDestino('agente:Vigía', agentes), 'Vigía');
    assert.equal(nombreDeDestino('agente:nadie', agentes), 'nadie', 'uno que no está queda como vino: la ventana lo dice');
    assert.equal(nombreDeDestino('hilo:Faro Norte', agentes), 'Faro Norte');
    assert.equal(nombreDeDestino(' Faro ', agentes), 'Faro');
}

// 7. el panel lo usa: lo local antes de ir al servidor, y abrir es lo que abre un enlace a una dirección
{
    const panel = readFileSync(path.join(dashboard, 'panel.ts'), 'utf8');
    assert.match(panel, /from '\.\/pedidos-locales'/);
    assert.match(panel, /abrir:\s*d\s*=>\s*ui\.abrirDireccion\(d\)/);
    const i = panel.indexOf('atenderLocal(m.accion'), j = panel.indexOf('this.paginas.pedir(');
    assert.ok(i > 0 && j > i, 'lo local se atiende antes de pedírselo al servidor');
    // la instrucción: con el destino pedido o el de la configuración, y de dónde viene lo pone la página
    assert.match(panel, /instruccion:\s*p\s*=>\s*this\.instruccionDeLienzo\(p,/);
    assert.match(panel, /modelo\.instruccionA/);
    assert.match(panel, /origenDe\(llave\)/);
}

console.log('lienzo: abrir, menu e instruccion se atienden en la página, sin permiso; lo demás va al servidor');
