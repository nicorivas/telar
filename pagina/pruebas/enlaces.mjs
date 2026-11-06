// Prueba de las rutas y direcciones que se encuentran en la terminal (src/web/enlaces.ts), sobre todo las largas que
// llegan partidas en varias filas: por la terminal (al llegar al borde) o por Claude Code, que corta él el texto al
// ancho de su caja y escribe cada pedazo en su fila. Corre en Node con xterm sin pantalla (@xterm/headless):
// npm run prueba:enlaces
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
const salida = path.join(mkdtempSync(path.join(tmpdir(), 'enlaces-')), 'enlaces.cjs');
await build({ entryPoints: [path.join(aqui, '..', 'src', 'web', 'enlaces.ts')], bundle: true,
    platform: 'node', format: 'cjs', outfile: salida, logLevel: 'warning' });
const { hallar, usarTipos, buscar } = require(salida);

const COLS = 60;
/** Una pantalla nueva con estas filas, cada una con su salto (como las escribe Ink); o con `crudo`, tal cual. */
async function pantalla(filas, crudo) {
    const term = new Terminal({ cols: COLS, rows: 24, allowProposedApi: true });
    await new Promise(r => term.write(crudo ?? filas.join('\r\n'), r));
    return term;
}
/** Lo que se encuentra en la fila `y` (desde 1), como «tipo texto (desde-hasta)». */
const en = (term, y) => hallar(term.buffer.active, COLS, y)
    .map(h => `${h.tipo} ${h.texto} (${h.desde.x},${h.desde.y}-${h.hasta.x},${h.hasta.y})`).sort();
/** Una palabra de `n` letras partida como la parte Ink: en pedazos de `ancho`, cada uno con su sangría. */
const partir = (palabra, ancho, sangria = '') => palabra.match(new RegExp(`.{1,${ancho}}`, 'g')).map(p => sangria + p);

// 1. la dirección del inicio de sesión de Claude Code: cuatro filas, sin sangría; se encuentra entera desde cualquiera
const larga = 'https://claude.com/cai/oauth/authorize?code=true&client_id=9d1c250a&response_type=code&redirect_uri=https%3A%2F%2Fplatform.claude.com%2Foauth%2Fcode%2Fcallback&scope=org%3Acreate_api_key&state=GLYLWpkUB';
{
    const filas = partir(larga, COLS);
    const term = await pantalla(['Browser didn\'t open? Use the url below', '', ...filas, '', 'Hold Shift']);
    const fin = 2 + filas.length, ultima = filas.at(-1).length;
    for (let y = 3; y <= fin; y++) assert.deepEqual(en(term, y), [`web ${larga} (1,3-${ultima},${fin})`], `fila ${y}`);
    assert.deepEqual(en(term, 1), [], 'la de arriba no es parte');
    assert.deepEqual(en(term, fin + 2), [], 'la de abajo tampoco');
}

// 2. con sangría (la caja de Ink empieza más adentro) y con margen a la derecha: también
{
    const filas = partir(larga, COLS - 4, '  ');
    const term = await pantalla(filas);
    assert.deepEqual(en(term, 2), [`web ${larga} (3,1-${2 + filas.at(-1).length - 2},${filas.length})`]);
}

// 3. una dirección corta que termina justo en el borde y una palabra abajo: no se pegan. Ink no la partió (cabía en
// una fila), y la palabra de abajo empieza con el espacio que la separaba
{
    const corta = 'https://ejemplo.cl/notas';
    const arriba = `  ver ${corta}`.padStart(COLS, '.');
    const term = await pantalla([arriba, '   y además otra cosa']);
    assert.deepEqual(en(term, 1), [`web ${corta} (${COLS - corta.length + 1},1-${COLS},1)`]);
    assert.deepEqual(en(term, 2), []);
}

// 4. prosa que llega al borde y una ruta al empezar la fila de abajo: la ruta, sin lo de arriba
{
    const arriba = 'x'.repeat(COLS - 4) + ' ver';
    const term = await pantalla([arriba, '  docs/arquitectura.md y lo demás']);
    assert.deepEqual(en(term, 2), ['ruta docs/arquitectura.md (3,2-22,2)']);
    assert.deepEqual(en(term, 1), []);
}

// 5. una ruta más larga que la fila (en el teléfono), partida por Ink con sangría
{
    const ruta = '/Users/ana/proyectos/faro/pagina/src/web/rutas-agente.ts:12';
    const filas = partir(ruta, COLS - 30, '  ').map(f => f.padStart(COLS, ' '));
    // la sangría deja cada pedazo pegado al borde derecho, como si la caja fuera angosta y estuviera a la derecha
    const term = await pantalla(filas);
    assert.equal(en(term, 1).length, 1, `una sola: ${en(term, 1)}`);
    assert.match(en(term, 1)[0], new RegExp(`^ruta ${ruta.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')} `));
}

// 6. la terminal la partió (escrita de corrido, sin saltos): como antes
{
    const term = await pantalla(null, `mira ${larga}. Listo`);
    assert.deepEqual(en(term, 2).map(h => h.split(' ').slice(0, 2).join(' ')), [`web ${larga}`]);
}

// 7. el último pedazo termina a media fila y sigue la frase: la dirección termina ahí, sin el punto
{
    const filas = partir(`${larga}.`, COLS);
    filas[filas.length - 1] += ' Y después otra cosa';
    const term = await pantalla(filas);
    assert.deepEqual(en(term, 1).map(h => h.split(' ').slice(0, 2).join(' ')), [`web ${larga}`]);
}

// 8. la dirección de un objeto: sin el punto de la frase; la de una web que la contiene no cuenta, ni una pegada a
// una palabra
{
    const term = await pantalla(['  ver tarea:T366. y hilo:Telar@telar, o https://x.cl/tarea:T1 y subtarea:T2']);
    assert.deepEqual(en(term, 1).map(h => h.split(' ').slice(0, 2).join(' ')),
        ['direccion hilo:Telar@telar', 'direccion tarea:T366', 'web https://x.cl/tarea:T1']);
}

// 9. una dirección larga partida por Ink, como una ruta: entera
{
    const dir = 'archivo:servidor:empresa/operacion/programas/faro/comparacion-del-mapa-de-cargos.md';
    const filas = partir(dir, COLS - 4, '  ');
    const term = await pantalla(filas);
    assert.deepEqual(en(term, 2).map(h => h.split(' ').slice(0, 2).join(' ')), [`direccion ${dir}`]);
}

// 10. los tipos de un módulo, cuando la página los sabe
{
    const term = await pantalla(['correo:abc123 llegó']);
    assert.deepEqual(en(term, 1), [], 'sin saber el tipo, no es una dirección');
    usarTipos(['archivo', 'hilo', 'proyecto', 'tarea', 'correo']);
    assert.deepEqual(en(term, 1).map(h => h.split(' ').slice(0, 2).join(' ')), ['direccion correo:abc123']);
}

// 11. los códigos que la hoja conoce para el hilo: solo esos, sueltos, y no el pedazo de una ruta o de una dirección
{
    const conocidos = new Set(['PEN-07', 'H3', 'T84', 'D-007']);
    const texto = 'Cerré PEN-07 y H3. Falta H4; ver decisiones/D-007-catalogo.md y tarea:T84 (aH3, H3-b, PEN-077)';
    assert.deepEqual(buscar(texto, conocidos).map(h => `${h.tipo} ${h.texto}`),
        ['codigo PEN-07', 'codigo H3', 'ruta decisiones/D-007-catalogo.md', 'direccion tarea:T84']);
    assert.deepEqual(buscar('Cerré PEN-07').map(h => h.tipo), []);  // sin códigos conocidos, nada
    const term = await pantalla(['  T84 y PEN-07, en la terminal']);
    const h = hallar(term.buffer.active, COLS, 1, conocidos).map(x => `${x.tipo} ${x.texto} (${x.desde.x}-${x.hasta.x})`);
    assert.deepEqual(h, ['codigo T84 (3-5)', 'codigo PEN-07 (9-14)']);
}

console.log('enlaces: bien');
