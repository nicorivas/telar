// Prueba de lo que se lee de un archivo arrastrado a la terminal de un hilo (src/web/arrastre.ts): qué rutas trae
// cada arrastre (VS Code, Safari con el Finder, una terminal, Linux, Chrome con el Finder), cómo se decodifica un
// `file://`, cómo se cita una ruta y cómo se dice un tamaño. Corre en Node, sin navegador: npm run prueba:arrastre
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const salida = path.join(mkdtempSync(path.join(tmpdir(), 'arrastre-')), 'arrastre.cjs');
await build({ entryPoints: [path.join(aqui, '..', 'src', 'web', 'arrastre.ts')], bundle: true,
    platform: 'node', format: 'cjs', outfile: salida, logLevel: 'warning' });
const { rutaDeUrl, pareceRuta, rutasDe, traeArchivos, citar, juntar, tamano, insertar } = require(salida);

/** Un arrastre de prueba, como un DataTransfer: sus tipos y su contenido por tipo. */
const arrastre = (datos, otros = []) => ({ types: [...Object.keys(datos), ...otros], getData: t => datos[t] ?? '' });

// 1. file:// a ruta: decodificada, sin host vacío ni localhost; con otro host no es de aquí
assert.equal(rutaDeUrl('file:///Users/ana/mis%20notas/informe%C3%B1.pdf'), '/Users/ana/mis notas/informeñ.pdf');
assert.equal(rutaDeUrl('file://localhost/etc/hosts'), '/etc/hosts');
assert.equal(rutaDeUrl('FILE:///tmp/x'), '/tmp/x');
assert.equal(rutaDeUrl('file:///C:/Users/ana/x.txt'), 'C:/Users/ana/x.txt');
assert.equal(rutaDeUrl('file://servidor/home/x'), null, 'otro host');
assert.equal(rutaDeUrl('https://ejemplo.cl/x'), null);
assert.equal(rutaDeUrl('file:///%E0%A4%A'), null, 'mal codificada');

// 2. qué parece ruta
for (const r of ['/tmp/x', '~/notas.md', 'C:\\Users\\x', 'c:/x']) assert.ok(pareceRuta(r), r);
for (const r of ['hola', 'notas.md', '~ana', 'https://x.cl', './x']) assert.ok(!pareceRuta(r), r);

// 3. VS Code: text/uri-list (con CRLF) y text/plain; vale la lista, también con varias
{
    const a = arrastre({ 'text/uri-list': 'file:///Users/ana/repo/a%20b.md\r\nfile:///Users/ana/repo/c.ts\r\n',
        'text/plain': '/Users/ana/repo/a b.md\n/Users/ana/repo/c.ts', codefiles: '[]' });
    assert.deepEqual(rutasDe(a), ['/Users/ana/repo/a b.md', '/Users/ana/repo/c.ts']);
}

// 4. Safari con el Finder: public.file-url (y Files)
assert.deepEqual(rutasDe(arrastre({ 'public.file-url': 'file:///Users/ana/Desktop/foto.png' }, ['Files'])),
    ['/Users/ana/Desktop/foto.png']);

// 5. Linux (Nautilus, Dolphin): text/uri-list con comentarios
assert.deepEqual(rutasDe(arrastre({ 'text/uri-list': '# de nautilus\nfile:///home/ana/x.txt\n' })), ['/home/ana/x.txt']);

// 6. una terminal: text/plain con rutas absolutas, una por línea; un texto cualquiera no es una ruta
assert.deepEqual(rutasDe(arrastre({ 'text/plain': '/home/ana/x.txt\n~/y.md\n' })), ['/home/ana/x.txt', '~/y.md']);
assert.deepEqual(rutasDe(arrastre({ 'text/plain': 'file:///tmp/z' })), ['/tmp/z']);
assert.deepEqual(rutasDe(arrastre({ 'text/plain': 'hola mundo' })), []);
assert.deepEqual(rutasDe(arrastre({ 'text/plain': '/tmp/x\ny una frase' })), [], 'si una línea no es ruta, no vale ninguna');

// 7. un enlace web: no es un archivo
assert.deepEqual(rutasDe(arrastre({ 'text/uri-list': 'https://ejemplo.cl/x', 'text/plain': 'https://ejemplo.cl/x' })), []);

// 8. Chrome con el Finder, el Explorador de Windows: solo Files, sin ruta (hay que preguntar y subir)
assert.deepEqual(rutasDe(arrastre({}, ['Files'])), []);
assert.ok(traeArchivos(['Files']));
assert.ok(traeArchivos(['text/uri-list', 'text/plain']));
assert.ok(!traeArchivos(['text/plain']), 'un texto suelto no es un arrastre de archivo');

// 9. citar como la terminal de VS Code: tal cual si es simple; entre comillas simples si no
assert.equal(citar('/Users/ana/repo/notas.md'), '/Users/ana/repo/notas.md');
assert.equal(citar('~/telar-entrada/a_b-1.tar.gz'), '~/telar-entrada/a_b-1.tar.gz');
assert.equal(citar('/Users/ana/mis notas.md'), "'/Users/ana/mis notas.md'");
assert.equal(citar("/tmp/it's.txt"), "'/tmp/it'\\''s.txt'");
assert.equal(citar('/tmp/$HOME;rm'), "'/tmp/$HOME;rm'");
assert.equal(citar('/tmp/año.pdf'), "'/tmp/año.pdf'");
assert.equal(juntar(['/a', '/b c']), "/a '/b c'");

// 10. el tamaño, legible
assert.equal(tamano(0), '0 B');
assert.equal(tamano(512), '512 B');
assert.equal(tamano(1536), '1,5 KB');
assert.equal(tamano(200 * 1024), '200 KB');
assert.equal(tamano(3.4 * 1024 * 1024), '3,4 MB');
assert.equal(tamano(150 * 1024 * 1024), '150 MB');

// 11. insertar en la caja donde está el cursor, sin pegarse a lo escrito
assert.deepEqual(insertar('', 0, 0, '/a'), { valor: '/a', cursor: 2 });
assert.deepEqual(insertar('mira esto', 9, 9, '/a'), { valor: 'mira esto /a', cursor: 12 });
assert.deepEqual(insertar('mira y dime', 5, 5, '/a'), { valor: 'mira /a y dime', cursor: 8 });
assert.deepEqual(insertar('miraX', 4, 5, '/a'), { valor: 'mira /a', cursor: 7 }, 'reemplaza la selección');
assert.deepEqual(insertar('ver:y', 4, 4, '/a'), { valor: 'ver: /a y', cursor: 8 });

console.log('arrastre: bien');
