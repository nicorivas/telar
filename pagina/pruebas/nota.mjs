// Prueba de lo que dice una nota (src/vistas/dashboard/nota.ts): lo que muestran de cada nota las tarjetas de
// «conexiones» de una lectura, sacado de su markdown con sus palabras, y cuál es el documento de una carpeta (la misma
// regla que el servidor: pruebas/test_ordenes.py, «test_el_documento_de_una_carpeta»). Corre en Node:
// npm run prueba:nota
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const salida = path.join(mkdtempSync(path.join(tmpdir(), 'nota-')), 'nota.cjs');
await build({ entryPoints: [path.join(aqui, '..', 'src', 'vistas', 'dashboard', 'nota.ts')], bundle: true,
    platform: 'node', format: 'cjs', outfile: salida, logLevel: 'warning' });
const { deLaNota, documentoDeCarpeta } = require(salida);

// 1. el título del frontmatter; los metadatos (cada línea, `**Clave**: valor`), la raya y el comentario no son lo que dice
{
    const d = deLaNota(['---', 'titulo: "El sistema operativo"', 'fecha: 2026-02-24', '---', '', '# Otro título', '',
        '**Estado**: Borrador v2', '**Fecha:** 2026-02-24', '', '---', '', '<!-- una nota para mí -->',
        'En la mayoría de las empresas, cada persona usa la IA a su manera.', '', 'Lo que falta es la capa de en medio.'].join('\n'));
    assert.equal(d.titulo, 'El sistema operativo');
    assert.equal(d.resumen, 'En la mayoría de las empresas, cada persona usa la IA a su manera.');
    assert.equal(d.comienzo, 'En la mayoría de las empresas, cada persona usa la IA a su manera.\n\nLo que falta es la capa de en medio.');
    assert.equal(d.sigue, false);
}

// 2. sin frontmatter, el `#`; la línea `>` bajo él es el resumen y no se repite al leerla; un párrafo que solo abre con
//    una clave en negrita es texto
{
    const d = deLaNota('# La frontera\n> Lo que se representa y lo que se porta.\n\n**Qué es**: una exploración\nsistemática de la frontera.');
    assert.equal(d.titulo, 'La frontera');
    assert.equal(d.resumen, 'Lo que se representa y lo que se porta.');
    assert.equal(d.comienzo, '**Qué es**: una exploración\nsistemática de la frontera.');
}

// 3. una cita de metadatos bajo el título no es el resumen
{
    const d = deLaNota('# Algo\n\n> **Estado:** pausado\n\nEl texto de verdad.');
    assert.equal(d.resumen, 'El texto de verdad.');
}

// 4. los enlaces quedan en su texto; las imágenes, el código, las tablas y el HTML, fuera
{
    const d = deLaNota('# X\n\n![un dibujo](a.png)\n\n```js\nconst a = 1;\n```\n\n| a | b |\n|---|---|\n\n<div>caja</div>\n\n'
        + 'Ver [el mapa](../mapa.md) y [[otra nota|la otra]], con `código`.');
    assert.equal(d.comienzo, 'Ver el mapa y la otra, con `código`.');
}

// 5. un título de sección va en negrita cuando ya hay texto (antes, no; dos seguidos, el segundo); una lista pegada a su
//    título es texto; las secciones del grafo cierran el comienzo
{
    const d = deLaNota('# X\n\n## Antes\n\nUno.\n\n## Vacía\n## Ideas\n- una\n- dos\n\n## Conexiones\n\n- `informa` → [a](a.md)');
    assert.equal(d.comienzo, 'Uno.\n\n**Ideas**\n\n- una\n- dos');
    assert.equal(d.sigue, true);
    assert.equal(deLaNota('# X\n\n- una\n- dos').resumen, 'una · dos');
}

// 6. el comienzo, hasta 180 palabras: el párrafo que se pasa, cortado con «…», sin una **negrita** abierta
{
    const largo = Array.from({ length: 150 }, (_, i) => `p${i}`).join(' ');
    const d = deLaNota(`# X\n\n${largo}\n\n**uno dos** ${Array.from({ length: 60 }, (_, i) => `q${i}`).join(' ')}\n\nY otro.`);
    const palabras = d.comienzo.match(/\S+/g);
    assert.equal(palabras.length, 180);
    assert.ok(d.comienzo.endsWith('q27…'), d.comienzo.slice(-20));
    assert.equal(d.sigue, true);
    const abierta = deLaNota(`# X\n\n${largo} y **${Array.from({ length: 40 }, (_, i) => `r${i}`).join(' ')}** fin`);
    assert.equal((abierta.comienzo.match(/\*\*/g) ?? []).length % 2, 0);
}

// 7. una nota sin texto: nada que decir
{
    const d = deLaNota('---\nname: x\n---\n');
    assert.deepEqual(d, { titulo: '', resumen: '', comienzo: '', sigue: false });
}

// 8. el documento de una carpeta: README.md; si no, index.md; si no, el único .md; si no, ninguno
assert.equal(documentoDeCarpeta(['README.md', 'index.md', 'b.md']), 'README.md');
assert.equal(documentoDeCarpeta(['readme.md', 'otra.md']), 'readme.md');
assert.equal(documentoDeCarpeta(['index.md', 'b.md']), 'index.md');
assert.equal(documentoDeCarpeta(['draft.md', 'datos.csv', 'sub/', '.oculto.md']), 'draft.md');
assert.equal(documentoDeCarpeta(['a.md', 'b.md']), '');
assert.equal(documentoDeCarpeta(['sub/']), '');

console.log('nota: bien');
