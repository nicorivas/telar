// Prueba de cómo se parte el README de un proyecto para su detalle (src/vistas/dashboard/readme.ts): el título, la
// entrada, las secciones y las suyas, cuáles están vacías (la plantilla sin llenar), lo que se lee de cada una plegada,
// qué es cada una para el resumen y los datos de la ficha. Con README de formas distintas: el de una plantilla con
// ficha y bloques que escribe una máquina, uno libre con código, uno sin secciones, uno sin título. Corre en Node,
// sin página: npm run prueba:readme
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const salida = path.join(mkdtempSync(path.join(tmpdir(), 'readme-')), 'readme.cjs');
await build({ entryPoints: [path.join(aqui, '..', 'src', 'vistas', 'dashboard', 'readme.ts')], bundle: true, platform: 'node',
    format: 'cjs', outfile: salida, logLevel: 'warning' });
const { partir, vacia, vistazo, claseDe, datos, generada, sinAyuda } = require(salida);

// 1. el de una plantilla: encabezado YAML, título, una cita de entrada, la ficha, un bloque generado y secciones con
//    solo la ayuda de la plantilla
const plantilla = `---
titulo: Taller de prueba
vigencia: vigente
---

# Taller de prueba

> Un cliente compró un taller de tres sesiones. Esta ficha resume qué se vendió.

## **Info General**

| Campo | Valor |
|-------|-------|
| **Cliente** | Empresa Uno |
| **Código** | — |
| **Estado** | Activo |
| **Contacto** | Ana Pérez, [correo](mailto:ana@ejemplo.cl) |
| **NPS** | Pendiente |
| **Precio** | 250 \\| 300 |

<!-- ALTA:START -->
| Campo | Valor | De dónde sale |
|---|---|---|
| Director | — | sin evidencia |
<!-- ALTA:END -->

## Estado PMO

<!-- PMO:auto | id=1 -->
> Proyección del gestor de proyectos — no editar.

| Métrica | Valor |
|---|---|
| Fase | desarrollo |

## Esperando

> Bloqueos externos. No son tareas, son dependencias.

## Cronograma

> Actividades del proyecto.

| Actividad | Inicio | Fin |
|-----------|--------|-----|
| Sesión 1 | 2026-10-26 | 2026-10-26 |
| Sesión 2 | 2026-11-09 | 2026-11-09 |

## Equipo y Dedicación

> Asignación del equipo.

| Persona | Rol | Dedicación |
|---------|-----|------------|

## Notas

> Ideas, contexto, decisiones.

---
*Actualizado: 2026-10-16*
`;
const a = partir(plantilla);
assert.equal(a.titulo, 'Taller de prueba');
assert.match(a.intro, /^> Un cliente compró/, 'la entrada, sin el YAML ni el título');
assert.deepEqual(a.partes.map(p => p.titulo), ['Info General', 'Estado PMO', 'Esperando', 'Cronograma', 'Equipo y Dedicación', 'Notas'],
    'los títulos, sin el énfasis');
const por = t => a.partes.find(p => p.titulo === t);
assert.deepEqual(a.partes.map(vacia), [false, false, true, false, true, true], 'vacías: solo la ayuda de la plantilla, o una tabla sin filas');
// la raya y la fecha del final son el pie del documento, no de «Notas»
assert.equal(a.pie, '*Actualizado: 2026-10-16*');
assert.equal(por('Notas').md, '> Ideas, contexto, decisiones.');
assert.equal(claseDe(por('Info General')), 'datos');
assert.equal(claseDe(por('Estado PMO')), '', 'el estado que escribe una máquina no es «cómo va» en palabras de su documento');
assert.ok(generada(por('Estado PMO')));
assert.equal(claseDe(por('Esperando')), 'abierto');
assert.equal(vistazo(por('Cronograma')), 'tabla · 2 filas');
assert.equal(vistazo(por('Estado PMO')), 'Fase: desarrollo', 'una tabla de campo y valor se lee por sus primeros datos');
assert.equal(vistazo(por('Info General')), 'Cliente: Empresa Uno · Estado: Activo · Contacto: Ana Pérez, correo', 'sin los que no dicen nada');
assert.equal(vistazo(por('Esperando')), 'Bloqueos externos. No son tareas, son dependencias.', 'si solo hay una cita, la cita');
assert.deepEqual(datos(por('Info General'), ['estado']), [
    ['Cliente', 'Empresa Uno'],
    ['Contacto', 'Ana Pérez, [correo](mailto:ana@ejemplo.cl)'],
    ['Precio', '250 | 300'],
], 'la primera tabla de dos columnas, sin lo vacío («—», «Pendiente») ni lo que ya está arriba; la barra escapada queda en su celda');

// 2. uno libre: párrafos de entrada, un bloque de código con algo que parece título, casillas, y las suyas (###)
const libre = `# cubos

Juego de construir con cubos. El foco es que poner uno sea satisfactorio.

Tiene dos modos.

## Cómo correrlo

\`\`\`sh
## esto no es un título
npm run dev
\`\`\`

Abre el navegador en el puerto 5173.

## Pendientes

- [ ] sombras suaves
- [x] el modo libre
- [ ] guardar la escena

## Cómo funciona

### La grilla

Cada cubo ocupa una celda.

### Las piezas

Se generan por procedimiento.
`;
const b = partir(libre);
assert.equal(b.titulo, 'cubos');
assert.match(b.intro, /Tiene dos modos\.$/, 'la entrada son los dos párrafos');
assert.deepEqual(b.partes.map(p => p.titulo), ['Cómo correrlo', 'Pendientes', 'Cómo funciona'], 'un ## dentro de un bloque de código no parte');
assert.match(b.partes[0].md, /## esto no es un título/);
assert.equal(vistazo(b.partes[0]), 'Abre el navegador en el puerto 5173.', 'el código no se lee como texto');
assert.equal(vistazo(b.partes[1]), '2 abiertas · 1 hecha');
assert.deepEqual(b.partes[2].subs.map(s => s.titulo), ['La grilla', 'Las piezas']);
assert.equal(b.partes[2].md, '');
assert.equal(vistazo(b.partes[2]), 'La grilla · Las piezas', 'sin texto propio, el nombre de las suyas');
assert.equal(vacia(b.partes[2]), false, 'sin texto propio pero con las suyas llenas');

// 3. sin secciones: todo queda en la entrada
const c = partir('# Salud\n\nSolo un párrafo, sin secciones.\n');
assert.equal(c.titulo, 'Salud');
assert.equal(c.partes.length, 0);
assert.equal(c.intro, 'Solo un párrafo, sin secciones.');

// 4. sin título y con secciones de nivel 3: el nivel más alto que hay manda
const d = partir('Antes de todo.\n\n### Estado\n\nAl día.\n\n### Qué falta\n\n- cerrar\n');
assert.equal(d.titulo, '');
assert.equal(d.intro, 'Antes de todo.');
assert.deepEqual(d.partes.map(p => [p.titulo, claseDe(p)]), [['Estado', 'estado'], ['Qué falta', 'abierto']]);

// 5. un estado escrito a mano, uno de foco y uno con fecha cuentan como «cómo va»
for (const t of ['Estado', 'Estado C3', 'Foco al cierre del programa', 'Al 9-nov', 'Situación actual']) {
    assert.equal(claseDe({ titulo: t, md: 'algo', subs: [] }), 'estado', t);
}
for (const t of ['Preguntas abiertas', 'Próximos pasos', 'Lo que queda abierto', 'Por resolver']) {
    assert.equal(claseDe({ titulo: t, md: 'algo', subs: [] }), 'abierto', t);
}
assert.equal(claseDe({ titulo: 'Estrategia comercial', md: 'algo', subs: [] }), '', 'empieza parecido, pero no es estado');
assert.equal(claseDe({ titulo: 'Información general', md: '', subs: [] }), 'datos');
assert.equal(partir('## Estado actual (enero 2026\\)\n\nbien\n').partes[0].titulo, 'Estado actual (enero 2026)', 'sin el escape');

// 6. en el resumen, lo que espera de otros va sin la ayuda de la plantilla; si solo está la cita, queda la cita
assert.equal(sinAyuda('> Bloqueos externos.\n> Formato: @Persona.\n\n- @Ana: la orden de compra'), '- @Ana: la orden de compra');
assert.equal(sinAyuda('> Solo esto.'), '> Solo esto.');
assert.equal(sinAyuda('Primero texto.\n\n> y una cita'), 'Primero texto.\n\n> y una cita');

// 7. una sección con solo un comentario o solo una raya está vacía
assert.ok(vacia({ titulo: 'x', md: '<!-- generado -->\n\n---', subs: [] }));
assert.ok(!vacia({ titulo: 'x', md: 'Sin contexto escrito todavía.', subs: [] }));

console.log('readme: ok');
