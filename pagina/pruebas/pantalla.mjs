// Prueba de la barra de una pantalla (componentes/pantalla.ts): la primera fila de cada pantalla del dashboard, de un
// hilo y del visor lleva a la izquierda solo el título (el nombre, con su ícono si tiene) y a la derecha solo botones (las
// vistas y las acciones). Ni una cuenta, ni la fecha, ni «leyendo…», ni un estado: lo que la pantalla resume va en el
// globo del título. Lo revisa `fueraDeLaBarra`, que también corre en la página (medir.py --js), sobre:
// · la barra misma, con todo lo que acepta, y una armada a mano con texto suelto (que sí se detecta);
// · la barra de cada pantalla que se puede armar sin página: todo (y una fuente abierta), táctica, ahora (también
//   simulando otro momento) y el calendario en el día (las demás las arma su pantalla con la página: medir.py);
// · el código: nadie arma una barra a mano (`class="pantalla-barra"` fuera de pantalla.ts), ni vuelve la clase del
//   resumen, ni le pasa un `resumen` a la barra.
// Corre en Node, con un DOM (happy-dom): npm run prueba:pantalla
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { Window } from 'happy-dom';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const src = path.join(aqui, '..', 'src');
const salida = path.join(mkdtempSync(path.join(tmpdir(), 'pantalla-')), 'pantalla.cjs');
globalThis.localStorage ??= { getItem: () => null, setItem() {}, removeItem() {} };
await build({ stdin: { contents: [
    "export { barra, fueraDeLaBarra } from './componentes/pantalla';",
    "export { barraTodo } from './componentes/todo';",
    "export { barraTactica } from './componentes/tactica';",
    "export { barraAhora, textoSimulado, htmlAhora } from './vistas/dashboard/ahora';",
    "export { barraDia, htmlCalendario } from './vistas/dashboard/plan';",
    "export { pieDeOtros } from './vistas/dashboard/esperas';",
    "export { I } from './web/iconos';",
].join('\n'), resolveDir: src, loader: 'ts' }, bundle: true, platform: 'node', format: 'cjs', outfile: salida, logLevel: 'warning' });
// lo que la página toca al cargar (los guardados, al salir), en un DOM de mentira
const w = new Window({ url: 'http://localhost/' });
globalThis.window ??= w;
globalThis.document ??= w.document;
const P = require(salida);

/** La barra dibujada, en un DOM: el <nav>. */
const nav = (html) => {
    const div = w.document.createElement('div');
    div.innerHTML = html;
    const n = div.querySelector('nav.pantalla-barra');
    assert.ok(n, `una barra: ${html.slice(0, 80)}`);
    return n;
};
/** Que una barra (lo que se le pasa a barra()) lleve solo título y botones. */
const limpia = (b, que) => {
    const n = nav(P.barra(b));
    assert.deepEqual(P.fueraDeLaBarra(n), [], `${que}: nada fuera del título y los botones`);
    return n;
};

// 1. la barra con todo lo que acepta: a la izquierda «‹» y el título (con su ícono y su globo), a la derecha las vistas
//    y las acciones; nada más
{
    const n = limpia({ volver: { accion: 'v', icono: 'A', ayuda: 'volver' }, nombre: 'tareas', icono: 'T', color: 'cian', ayuda: '56 tareas',
        vistas: [{ accion: 'x', icono: 'F', nombre: 'foco', si: true }, { accion: 'x', nombre: 'gantt' }],
        acciones: [{ accion: 'r', icono: 'R', ayuda: 'releer' }, { accion: 'c', icono: 'C', texto: 'proyectos/faro', ayuda: 'la carpeta' }] }, 'entera');
    const hijos = [...n.children].map(e => e.className.split(' ')[0]);
    assert.deepEqual(hijos, ['pantalla-boton', 'pantalla-nombre', 'pantalla-lleno', 'pantalla-vistas', 'pantalla-acciones'],
        'el título a la izquierda; lo que llena; y a la derecha, los botones');
    const titulo = n.querySelector('.pantalla-nombre');
    assert.equal(titulo.getAttribute('title'), '56 tareas', 'lo que resume, en el globo del título');
    assert.equal(titulo.textContent, 'T tareas', 'el título: su ícono y su nombre');
    // un nombre tal cual (el de un archivo): la misma pieza, con su clase
    assert.match(P.barra({ nombre: 'README.md', literal: true, ayuda: 'casa/README.md' }), /<span class="pantalla-nombre literal" title="casa\/README\.md">README\.md<\/span>/);
    // un hilo: sin título, solo botones
    limpia({ vistas: [{ accion: 'vista', valor: 'term', icono: 'T', nombre: 'terminal' }], acciones: [{ accion: 'carpeta', icono: 'C', texto: '~', ayuda: 'la raíz' }] }, 'un hilo');
}

// 2. lo que no es título ni botón se detecta: el texto suelto, un resumen de antes, un elemento cualquiera, dos títulos
{
    const malo = (dentro) => P.fueraDeLaBarra(nav(`<nav class="pantalla-barra"><span class="pantalla-nombre">todo</span>${dentro}<span class="pantalla-lleno"></span></nav>`));
    assert.deepEqual(malo('568 en trabajo'), ['568 en trabajo']);
    assert.deepEqual(malo('<span class="pantalla-resumen">568 en trabajo · y 111 en los otros</span>'), ['pantalla-resumen: 568 en trabajo · y 111 en los otros']);
    assert.equal(malo('<b>3</b>').length, 1);
    assert.equal(malo('<span class="pantalla-acciones">hola<a class="pantalla-boton">x</a></span>').length, 1, 'texto entre las acciones');
    assert.ok(malo('<span class="pantalla-nombre">otro</span>').includes('más de un título'));
    // y barra() no dibuja lo que no declara: un `resumen` pasado sin tipo se queda afuera
    const conResumen = P.barra({ nombre: 'todo', resumen: '568 en trabajo', resumenHtml: '<b>3</b> por decidir' });
    assert.ok(!conResumen.includes('568') && !conResumen.includes('por decidir'), 'la barra no lleva resumen, ni pasado a la fuerza');
}

// 3. la barra de cada pantalla que se arma sin página
{
    const mundos = [{ clave: 'trabajo', nombre: 'trabajo', color: 'azul' }, { clave: 'personal', nombre: 'personal', color: 'verde' }];
    const fuentes = [{ clave: 'tareas', nombre: 'tareas', color: 'cian', cuenta: { trabajo: 568, personal: 111 }, dice: {} }];
    // todo: «568 en trabajo · y 111 en los otros» ya no va a la vista; queda en el globo
    const bt = P.barraTodo({ fuentes, mundos, puesto: 'trabajo' });
    const n = limpia(bt, 'todo');
    assert.ok(!n.textContent.includes('568'), 'todo: sin la cuenta a la vista');
    assert.match(n.querySelector('.pantalla-nombre').getAttribute('title'), /568 en trabajo · y 111 en los otros/, 'todo: la cuenta, en el globo');
    limpia(P.barraTodo({ fuentes, mundos, puesto: 'trabajo', abierta: { fuente: 'tareas', total: 568, cosas: [] } }), 'todo, una fuente abierta');

    // táctica: sin «N por decidir» a la vista
    const via = (clave) => ({ clave, cuentas: [] });
    const tac = P.barraTactica({ vias: [via('decidir')], vivo: [] });
    const nt = limpia(tac, 'táctica');
    assert.ok(!/por decidir/.test(nt.textContent), 'táctica: sin el número a la vista');
    assert.equal(nt.querySelector('.pantalla-nombre').getAttribute('title'), 'nada por decidir');

    // ahora: «3 de 5» en el globo de las flechas; simulando, lo dice la pantalla, no la barra
    const ev = (i) => ({ id: `e${i}`, titulo: `bloque ${i}`, inicio: Date.parse('2026-11-25T09:00:00') + i * 3600000, fin: Date.parse('2026-11-25T10:00:00') + i * 3600000, asistentes: [] });
    const evs = [ev(0), ev(1), ev(2)];
    const ahora = Date.parse('2026-11-25T10:30:00');
    const ba = P.barraAhora({ evs, i: 1, ahora, fijo: false, simulado: true });
    const na = limpia({ nombre: 'ahora', ...ba }, 'ahora, simulando');
    assert.ok(!na.textContent.includes('simulando') && !na.textContent.includes('2 de 3'));
    assert.match(na.querySelector('[data-valor="1"]').getAttribute('title'), /este es el 2 de 3/, 'cuál de cuántos, en el globo de la flecha');
    const cuerpoAhora = P.htmlAhora({ evs, i: 1, ahora, fijo: false, simulado: true, cargando: false, urgentes: [], propuestas: [], aviso: '' }).join('');
    assert.match(cuerpoAhora, /class="fila dim ahora-simulado">simulando mié 25 · 10:30/, 'simulando: la primera línea de la pantalla');
    limpia({ nombre: 'ahora', ...P.barraAhora({ evs: [], i: 0, ahora, fijo: false }) }, 'ahora, sin nada');

    // el calendario: la fecha no va en la barra; si no es hoy, en la primera línea del día
    const bd = P.barraDia('2026-11-26', '2026-11-25');
    const nd = limpia({ nombre: 'calendario', ...bd }, 'calendario, otro día');
    assert.ok(!nd.textContent.includes('26 nov'));
    assert.equal(nd.querySelector('.pantalla-nombre').getAttribute('title'), 'jue 26 nov');
    const dia = (fecha) => ({ fecha, agenda: [], pendientes: [] });
    assert.match(P.htmlCalendario(dia('2026-11-26'), [], undefined, '', new Date(ahora), '', '', '2026-11-25').join(''), /<div class="cal-dia-fecha">jue 26 nov<\/div>/, 'otro día: su fecha arriba');
    assert.ok(!P.htmlCalendario(dia('2026-11-25'), [], undefined, '', new Date(ahora), '', '', '2026-11-25').join('').includes('cal-dia-fecha'), 'hoy: sin fecha');

    // te esperan: las de otros mundos, al pie de la lista
    assert.match(P.pieDeOtros(111), /111 más, de otros mundos/);
}

// 4. el código: ninguna barra armada a mano, ni la clase del resumen, ni un `resumen` que se le pase a la barra
{
    const archivos = [];
    const recorrer = (d) => { for (const x of readdirSync(d)) { const r = path.join(d, x); if (statSync(r).isDirectory()) recorrer(r); else if (/\.(ts|css)$/.test(x)) archivos.push(r); } };
    recorrer(src);
    recorrer(path.join(aqui, '..', 'media', 'css'));
    for (const f of archivos) {
        const s = readFileSync(f, 'utf8');
        const rel = path.relative(path.join(aqui, '..'), f);
        assert.ok(!s.includes('pantalla-resumen'), `${rel}: la clase del resumen de la barra ya no existe`);
        if (!rel.endsWith(path.join('componentes', 'pantalla.ts'))) {
            assert.ok(!/class="pantalla-barra/.test(s), `${rel}: la barra se arma con componentes/pantalla.ts, no a mano`);
        }
    }
}

console.log('pantalla: la barra lleva solo el título y los botones');
