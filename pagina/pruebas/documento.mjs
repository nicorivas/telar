// Prueba del visor de un documento (src/web/carpeta.ts) y de cómo se ancla un comentario (src/web/fuente.ts): la persona
// selecciona sobre el markdown dibujado y el ancla va contra el texto fuente, donde los ** y los enlaces cambian el texto.
// Con un .md lleno de markdown (negritas, enlaces con paréntesis en el destino, listas, una lista numerada con una
// referencia, una tabla, un bloque de código, una cita con una entidad, una frase repetida), cada selección tiene que caer
// en su lugar de la fuente, y de vuelta: el tramo de la fuente, en lo dibujado. Y el visor: la primera fila con el nombre
// del archivo y la ✕, sin la lista de la carpeta; una carpeta como su lista; un .html dibujado con «código»; uno de otra
// máquina con ella delante. Corre en Node: lo dibujado se lee de los tokens de markdown-it; y al final, con un DOM
// (happy-dom), la barra de la derecha del visor (web/documento-lado.ts) con sus comentarios: plegar y desplegar, las
// pestañas, el número en el texto y en la barra, el clic en los dos sentidos, comentar desde la selección, el modo foco y
// el teléfono. npm run prueba:documento
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { copyFileSync, readFileSync } from 'node:fs';
import { Window } from 'happy-dom';

const require = createRequire(import.meta.url);
const MarkdownIt = require('markdown-it');
const aqui = path.dirname(fileURLToPath(import.meta.url));
const src = path.join(aqui, '..', 'src');

// lo de la página que no se prueba aquí, de mentira: la lista de hilos, la API de la página y la ventana
const MENTIRAS = {
    [path.join(src, 'modelo.ts')]: `export const modelo = { aqui: 'laptop', porNombre: n => (n === 'Faro' ? { nombre: n, ruta: '/casa/faro' } : undefined) };`,
    [path.join(src, 'web', 'ui.ts')]: `export async function aviso() {} export function estado() {} export async function abrirArchivo() {} export async function menu() {}`,
    [path.join(src, 'web', 'ventana.ts')]: 'export async function abrirVentana() {}',
};
const mentira = { name: 'mentira', setup(b) {
    b.onResolve({ filter: /^\.\.?\// }, a => {
        const p = path.join(a.resolveDir, a.path) + '.ts';
        return MENTIRAS[p] ? { path: p, namespace: 'mentira' } : undefined;
    });
    b.onLoad({ filter: /.*/, namespace: 'mentira' }, a => ({ contents: MENTIRAS[a.path], loader: 'js' }));
} };
const salida = path.join(mkdtempSync(path.join(tmpdir(), 'documento-')), 'documento.cjs');
await build({
    stdin: { contents: `export * as fuente from './web/fuente'; export * as frontmatter from './web/frontmatter'; export * as carpeta from './web/carpeta'; export { notaDe, ordenar, cuentaDe } from './web/comentarios';`
        + ` export * as lado from './web/documento-lado'; export { I } from './web/iconos';`,
        resolveDir: src, loader: 'ts' },
    bundle: true, platform: 'node', format: 'cjs', outfile: salida, logLevel: 'warning', plugins: [mentira],
});
globalThis.window = { addEventListener() {} };
const { fuente, frontmatter, carpeta, notaDe, ordenar, cuentaDe, lado: ladoMod, I } = require(salida);

const DOC = `# Informe **de** adopción

El **62%** de los encuestados declara usar la [herramienta](https://x.example/a_(b) "título") a diario (¿o no?). La cifra viene de la encuesta interna de junio, y se repite: la cifra viene de la encuesta.

## Recomendaciones

- uno con *énfasis* y \`código\`
- dos con un [enlace relativo](otro.md)
  que sigue en otra línea

1. primero
2. segundo [ref][r] y ![una imagen](foto.png) al lado

| col a | col **b** |
|---|:---:|
| celda 1 | celda [dos](http://y.example) |

\`\`\`python
print("hola")  # la cifra viene
\`\`\`

> una cita con &amp; entidad, y __subrayado__ de otro modo

Se recomienda avanzar en ~~cuatro~~ tres frentes antes de cerrar el trimestre.

[r]: http://ref.example
`;

// ── lo dibujado, sin DOM: cada bloque de markdown-it con sus líneas y lo que se ve de él ──
const md = new MarkdownIt({ html: false, linkify: true });
const decodificar = s => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&');
const visibleDe = html => decodificar(html.replace(/<[^>]+>/g, ''));
/** Los bloques hoja (un párrafo, un título, una celda con su fila, un bloque de código): sus líneas y su texto visible. */
function bloques(texto) {
    const tokens = md.parse(texto, {}), r = [];
    const abiertos = [];
    for (const t of tokens) {
        if (t.nesting === 1 && t.map) abiertos.push(t);
        if (t.nesting === -1 && t.type !== 'th_close' && t.type !== 'td_close') { const a = abiertos.pop(); void a; }
        if (t.type === 'inline') {
            const dueño = [...abiertos].reverse().find(x => x.map);
            r.push({ lineas: dueño.map, texto: visibleDe(md.renderer.renderInline(t.children, md.options, {})) });
        }
        if (t.type === 'fence' || t.type === 'code_block') r.push({ lineas: t.map, texto: t.content });
    }
    return r;
}
const BLOQUES = bloques(DOC);
/** Selecciona `trozo` en el bloque cuyo texto visible lo tiene (la `n`-ésima vez), y lo ubica en la fuente. */
function seleccionar(trozo, n = 0) {
    for (const b of BLOQUES) {
        let i = -1;
        for (let k = 0; k <= n; k++) { i = b.texto.indexOf(trozo, i + 1); if (i < 0) break; }
        if (i < 0) continue;
        const r = fuente.ubicarSeleccion(DOC, trozo, b.lineas, b.texto.slice(0, i));
        return r && DOC.slice(r[0], r[1]);
    }
    throw new Error(`«${trozo}» no se ve en ningún bloque`);
}

// 1. dibujar: cada bloque lleva sus líneas de la fuente
{
    const html = fuente.dibujar(DOC);
    for (const [etiqueta, lineas] of [['h1', '0-1'], ['p', '2-3'], ['h2', '4-5'], ['li', '6-7'], ['li', '7-10'], ['ol', '10-13'], ['tr', '13-14'],
        ['tr', '15-16'], ['code', '17-20'], ['blockquote', '21-22'], ['p', '23-24']]) {
        assert.match(html, new RegExp(`<${etiqueta}[^>]* data-src="${lineas}"`), `<${etiqueta}> con data-src="${lineas}"`);
    }
    assert.deepEqual(fuente.lineas('3-5'), [3, 5]);
    assert.equal(fuente.lineas('x'), undefined);
    // el markdown se dibuja como en la página: sin el HTML que traiga
    assert.match(fuente.dibujar('a <b>c</b>'), /&lt;b&gt;/);
}

// 2. del dibujado a la fuente: la cita queda entera y en su lugar, aunque haya formato de por medio
{
    const casos = [
        ['62% de los encuestados', '**62%** de los encuestados'],
        ['El 62%', 'El **62%**'],
        ['usar la herramienta a diario', 'usar la [herramienta](https://x.example/a_(b) "título") a diario'],
        ['herramienta', 'herramienta'],
        ['a diario (¿o no?).', 'a diario (¿o no?).'],
        ['(¿o no?)', '(¿o no?)'],
        ['Informe de adopción', 'Informe **de** adopción'],
        ['énfasis y código', '*énfasis* y `código`'],
        ['enlace relativo\nque sigue', '[enlace relativo](otro.md)\n  que sigue'],
        ['segundo ref y', 'segundo [ref][r] y'],
        ['y  al lado', 'y ![una imagen](foto.png) al lado'],
        ['celda 1', 'celda 1'],
        ['col b', 'col **b**'],
        ['celda dos', 'celda [dos](http://y.example)'],
        ['print("hola")', 'print("hola")'],
        ['una cita con & entidad', 'una cita con &amp; entidad'],
        ['subrayado de otro', '__subrayado__ de otro'],
        ['cuatro tres frentes', '~~cuatro~~ tres frentes'],
    ];
    for (const [sel, cita] of casos) assert.equal(seleccionar(sel), cita, `«${sel}»`);
    // una frase repetida en el mismo párrafo: la que se seleccionó, no la primera (tal cual, y por sus letras)
    const primera = DOC.indexOf('de la encuesta'), segunda = DOC.indexOf('de la encuesta', primera + 1);
    const p = BLOQUES.find(b => b.texto.includes('se repite'));
    const r = fuente.ubicarSeleccion(DOC, 'de la encuesta', p.lineas, p.texto.slice(0, p.texto.lastIndexOf('de la encuesta')));
    assert.deepEqual(r, [segunda, segunda + 'de la encuesta'.length], 'la segunda vez, como se seleccionó');
    const r0 = fuente.ubicarSeleccion(DOC, 'de la encuesta', p.lineas, p.texto.slice(0, p.texto.indexOf('de la encuesta')));
    assert.deepEqual(r0, [primera, primera + 'de la encuesta'.length], 'y la primera');
    const r2 = fuente.ubicarSeleccion(DOC, 'de la  encuesta.', p.lineas, p.texto.slice(0, p.texto.lastIndexOf('de la encuesta')));
    assert.deepEqual(r2, [segunda, segunda + 'de la encuesta.'.length], 'por sus letras, la segunda también');
    // y la del bloque de código, que dice lo mismo, no se confunde con la del párrafo
    const codigo = BLOQUES.find(b => b.texto.includes('print'));
    const rc = fuente.ubicarSeleccion(DOC, 'la cifra viene', codigo.lineas, codigo.texto.slice(0, codigo.texto.indexOf('la cifra')));
    assert.ok(rc[0] > DOC.indexOf('```python'), 'en el bloque de código');
    // de un bloque a otro: desde un ítem hasta el siguiente
    assert.equal(fuente.ubicarSeleccion(DOC, 'código\ndos con un enlace', [6, 9]) && DOC.slice(...fuente.ubicarSeleccion(DOC, 'código\ndos con un enlace', [6, 9])),
        '`código`\n- dos con un [enlace');
    // sin letras ni números no hay qué buscar; lo que no está, no se inventa
    assert.equal(fuente.ubicarSeleccion(DOC, '¿?', [2, 3]), undefined);
    assert.equal(fuente.ubicarSeleccion(DOC, 'esto no está en ninguna parte', [2, 3]), undefined);
    // en un texto que no es markdown (`fuera` vacío) se busca tal cual, y una marca de lista es texto
    const plano = '- una línea\notra línea\n';
    assert.deepEqual(fuente.ubicarSeleccion(plano, '- una', [0, 2], '', []), [0, 5]);
}

// 2b. el frontmatter: no se dibuja, y lo dibujado guarda las líneas del archivo entero (los comentarios se anclan igual)
{
    // sin frontmatter: nada cambia
    assert.equal(frontmatter.leer(DOC), undefined, 'sin frontmatter');
    assert.equal(frontmatter.sinFrontmatter(DOC), DOC);
    // YAML, en la primera línea
    const CUERPO = '# Política de prueba\n\nUn párrafo que se comenta, con **negrita**.\n\nOtro párrafo.\n';
    const YAML = '---\ntitulo: Política de prueba\nestandar: "1.0"\nvigencia: borrador # por ahora\netiquetas:\n  - uno\n  - dos\n---\n' + CUERPO;
    const y = frontmatter.leer(YAML);
    assert.equal(y.formato, 'yaml');
    assert.deepEqual(y.datos, [['titulo', 'Política de prueba'], ['estandar', '1.0'], ['vigencia', 'borrador'], ['etiquetas', '- uno\n- dos']],
        'cada clave con su valor, sin comillas ni comentario; una lista, con su clave');
    assert.equal(y.lineas, 8);
    assert.equal(frontmatter.sinFrontmatter(YAML), CUERPO);
    const hy = fuente.dibujar(YAML);
    assert.doesNotMatch(hy, /titulo|estandar|vigencia|<hr/, 'en el texto no queda nada del frontmatter (ni una raya)');
    assert.match(hy, /<h1 data-src="8-9">Política de prueba<\/h1>/, 'el título: su línea del archivo entero');
    assert.match(hy, /<p data-src="10-11">Un párrafo/, 'el párrafo, también corrido');
    // TOML, en la primera línea
    const TOML = '+++\ntitle = "Una nota"\ndraft = true\n\n[autor]\nnombre = \'Alguien\'\n+++\n' + CUERPO;
    const t = frontmatter.leer(TOML);
    assert.equal(t.formato, 'toml');
    assert.deepEqual(t.datos, [['title', 'Una nota'], ['draft', 'true'], ['autor.nombre', 'Alguien']], 'en TOML, la tabla delante de sus claves');
    const ht = fuente.dibujar(TOML);
    assert.doesNotMatch(ht, /Una nota|draft|\+\+\+/);
    assert.match(ht, /<h1 data-src="7-8">/);
    // un --- que no está en la primera línea sigue siendo una raya (y lo de arriba, texto)
    const RAYA = 'Antes de la raya.\n\n---\n\nclave: valor\n\n---\n';
    assert.equal(frontmatter.leer(RAYA), undefined, 'un --- más abajo no es frontmatter');
    const hr = fuente.dibujar(RAYA);
    assert.match(hr, /<p data-src="0-1">Antes de la raya.<\/p>/);
    assert.equal((hr.match(/<hr/g) ?? []).length, 2, 'las dos rayas, rayas');
    assert.match(hr, /<p data-src="4-5">clave: valor<\/p>/);
    // uno que no se cierra no es frontmatter: se dibuja como siempre
    assert.equal(frontmatter.leer('---\ntitulo: x\n\nUn párrafo.\n'), undefined, 'sin raya de cierre, no es frontmatter');
    // ni una raya sola: «---» seguido de texto en la misma línea
    assert.equal(frontmatter.leer('--- no\nx: y\n---\n'), undefined);
    // el anclaje: una selección en lo dibujado cae en su lugar del archivo entero, y de vuelta
    const tokens = md.parse(frontmatter.sinFrontmatter(YAML), {});
    const inline = tokens.find(x => x.type === 'inline' && x.content.startsWith('Un párrafo'));
    const lin = /<p data-src="(\d+)-(\d+)">Un párrafo/.exec(hy).slice(1).map(Number);
    const visto = visibleDe(md.renderer.renderInline(inline.children, md.options, {}));
    const r = fuente.ubicarSeleccion(YAML, 'comenta, con negrita', lin, visto.slice(0, visto.indexOf('comenta')));
    assert.equal(YAML.slice(r[0], r[1]), 'comenta, con **negrita**', 'la cita, contra el texto del archivo con su frontmatter');
    assert.equal(YAML.slice(0, r[0]).split('\n').length, 11, 'en la línea 11 del archivo, la misma que dice marginalia');
    const ini = fuente.inicios(YAML);
    const [a, b] = fuente.tramoDeLineas(YAML, lin[0], lin[1], ini);
    const ida = fuente.ubicarEnPiezas(YAML, r[0], r[1], [{ texto: visto }], a);
    assert.equal(visto.slice(ida.de[1], ida.a[1]), 'comenta, con negrita', 'y de vuelta, sobre lo dibujado');
    assert.ok(a <= r[0] && r[1] <= b);
}

// 3. de la fuente a lo dibujado: el tramo de un hilo se marca sobre lo que se ve (en las piezas: los nodos de texto)
{
    const piezasDe = html => html.split(/<[^>]+>/).filter(Boolean).map(t => ({ texto: decodificar(t) }));
    const ini = fuente.inicios(DOC);
    const comprobar = (cita, vista, bloque) => {
        const i = DOC.indexOf(cita);
        const piezas = piezasDe(bloque.html);
        const lugar = fuente.ubicarEnPiezas(DOC, i, i + cita.length, piezas, ini[bloque.lineas[0]]);
        assert.ok(lugar, `«${cita}» no se encontró en lo dibujado`);
        const { de, a } = lugar;
        const texto = de[0] === a[0] ? piezas[de[0]].texto.slice(de[1], a[1])
            : piezas[de[0]].texto.slice(de[1]) + piezas.slice(de[0] + 1, a[0]).map(p => p.texto).join('') + piezas[a[0]].texto.slice(0, a[1]);
        assert.equal(texto, vista, `«${cita}» se marca sobre «${vista}»`);
    };
    const parrafo = { lineas: [2, 3], html: md.renderInline(DOC.split('\n')[2]) };
    comprobar('**62%** de los encuestados', '62% de los encuestados', parrafo);
    comprobar('[herramienta](https://x.example/a_(b) "título") a diario', 'herramienta a diario', parrafo);
    const fila = { lineas: [15, 16], html: '<td>celda 1</td><td>celda <a href="http://y.example">dos</a></td>' };
    comprobar('celda [dos](http://y.example)', 'celda dos', fila);
    // sin ancho (lo comentado se reescribió y quedó un lado): antes de la primera letra que le sigue
    const i = DOC.indexOf('declara');
    const vacio = fuente.ubicarEnPiezas(DOC, i, i, piezasDe(parrafo.html), ini[2]);
    assert.deepEqual(vacio.de, vacio.a);
    assert.ok(piezasDe(parrafo.html)[vacio.de[0]].texto.slice(vacio.de[1]).startsWith('declara'));
}

// 4. cómo se dice un ancla que no fue exacta
{
    assert.equal(notaDe({ anclado: true, metodo: 'exacto', confianza: 1 }), '');
    assert.match(notaDe({ anclado: true, metodo: 'aproximado', confianza: 0.72 }), /parecido \(72%\)/);
    assert.match(notaDe({ anclado: true, metodo: 'vecindario', confianza: 0.5 }), /ya no está/);
    assert.match(notaDe({ anclado: false, metodo: null, confianza: null }), /sin ancla/);
}

// 5. el visor: la primera fila con el nombre del archivo (gris) y la ✕; abajo el contenido, sin la lista de la carpeta
{
    let contestar = () => ({ status: 404, cuerpo: {} });
    const pedidos = [];
    globalThis.fetch = async url => {
        const u = new URL(url, 'http://pagina');
        pedidos.push(u);
        const { status, cuerpo } = contestar(u);
        return { ok: status === 200, status, json: async () => cuerpo };
    };
    const nuevoEl = () => ({ classList: { add() {} }, dataset: {}, innerHTML: '', scrollTop: 0, addEventListener() {} });
    const archivos = [{ nombre: 'docs/', ruta: 'proyectos/faro/docs' }, { nombre: 'README.md', ruta: 'proyectos/faro/README.md' }];
    contestar = u => (u.pathname === '/api/hilos/documento'
        ? { status: 200, cuerpo: { hilo: '', titulo: 'faro/README.md', carpeta: 'proyectos/faro', archivo: 'proyectos/faro/README.md', archivos,
            markdown: '# Faro\n\nUn **faro** [ver](docs/a.md).\n', texto: '' } } : { status: 404, cuerpo: {} });
    const el = nuevoEl();
    await carpeta.montar(el, '', 'proyectos/faro/README.md', t => t, { cerrar() {} });
    assert.match(el.innerHTML, /<span class="pantalla-nombre literal" title="proyectos\/faro\/README\.md">README\.md<\/span>/, 'el nombre es el título, tal cual, con su ruta al pasar el mouse');
    assert.match(el.innerHTML, /data-accion="doc-cerrar"/, 'la ✕');
    assert.doesNotMatch(el.innerHTML, /data-accion="doc-atras"/, 'nada a qué volver');
    assert.doesNotMatch(el.innerHTML, /class="carpeta"|>docs\/</, 'sin la lista de la carpeta');
    assert.match(el.innerHTML, /<h1 data-src="0-1">Faro<\/h1>/, 'el markdown, con las líneas de cada bloque');
    assert.doesNotMatch(el.innerHTML, /coment-lista|class="conexiones"|doc-cuentas/, 'ni comentarios ni conexiones al final ni cuentas arriba: van en la barra');
    assert.equal(el.dataset.listo, '1');
    // una carpeta: su lista, una por línea, con la de arriba
    contestar = u => (u.pathname === '/api/hilos/documento'
        ? { status: 200, cuerpo: { hilo: '', titulo: 'faro', carpeta: 'proyectos/faro', archivo: '', archivos, subir: 'proyectos', markdown: '', texto: '' } }
        : { status: 404, cuerpo: {} });
    const c = nuevoEl();
    await carpeta.montar(c, '', 'proyectos/faro', t => t, {});
    assert.match(c.innerHTML, /<span class="pantalla-nombre literal"[^>]*>faro\/<\/span>/);
    assert.match(c.innerHTML, /<nav class="carpeta"><a class="dir" data-hilo="" data-archivo="proyectos">\.\.\/<\/a><a class="dir"[^>]*>docs\/<\/a><a class=""[^>]*>README\.md<\/a><\/nav>/);
    // un .html: dibujado en su iframe aislado, y «código» en la barra
    contestar = u => (u.pathname === '/api/hilos/documento'
        ? { status: 200, cuerpo: { hilo: '', titulo: 'x.html', carpeta: '.', archivo: 'x.html', archivos: [], markdown: '', texto: '<p>hola</p>' } }
        : { status: 404, cuerpo: {} });
    const h = nuevoEl();
    await carpeta.montar(h, '', 'x.html', t => t, {});
    assert.match(h.innerHTML, /<iframe sandbox="allow-scripts allow-popups" src="\/api\/archivos\/ver\?ruta=x\.html"/);
    assert.match(h.innerHTML, /data-accion="doc-codigo"[^>]*>.*código/);
    assert.match(h.innerHTML, /<pre class="doc-texto" hidden>&lt;p&gt;hola&lt;\/p&gt;<\/pre>/);
    // uno de otra máquina: con ella delante
    contestar = u => (u.pathname === '/api/hilos/documento'
        ? { status: 200, cuerpo: { hilo: '', titulo: 'x.md · en servidor', archivo: 'servidor:docs/x.md', archivos: [], markdown: 'hola\n', texto: '', maquina: 'servidor' } }
        : { status: 404, cuerpo: {} });
    const o = nuevoEl();
    await carpeta.montar(o, '', 'servidor:docs/x.md', t => t, {});
    assert.match(o.innerHTML, /<span class="pantalla-nombre literal"[^>]*>servidor:x\.md<\/span>/);
    // un texto: tal cual, en un <pre> con sus líneas (también se comenta)
    contestar = u => (u.pathname === '/api/hilos/documento'
        ? { status: 200, cuerpo: { hilo: 'Faro', titulo: 'Faro', carpeta: '.', archivo: 'notas.txt', archivos: [], markdown: '', texto: 'a\nb\n' } }
        : { status: 404, cuerpo: {} });
    const t = nuevoEl();
    await carpeta.montar(t, 'Faro', 'notas.txt', x => x, {});
    assert.match(t.innerHTML, /<pre class="doc-texto doc-contenido" data-src="0-3">a\nb\n<\/pre>/);
    assert.ok(pedidos.some(u => u.pathname === '/api/hilos/documento' && u.searchParams.get('hilo') === 'Faro'));
}

// 6. el modo lectura (el modo revisión): en foco, de entrada; fuera de foco, no; y lo elegido en cada uno se recuerda
{
    const guardado = new Map();
    globalThis.localStorage = { getItem: k => guardado.get(k) ?? null, setItem: (k, v) => guardado.set(k, v) };
    globalThis.document = { body: { dataset: { modo: 'tactica' } } };
    assert.equal(carpeta.lecturaPuesta(), false, 'fuera de foco, la letra de la página');
    globalThis.document.body.dataset.modo = 'foco';
    assert.equal(carpeta.lecturaPuesta(), true, 'en foco, la prosa');
    guardado.set('telar.visor.lectura.foco', 'no');
    assert.equal(carpeta.lecturaPuesta(), false, 'en foco, si se sacó');
    guardado.set('telar.visor.lectura.otro', 'si');
    globalThis.document.body.dataset.modo = 'estrategia';
    assert.equal(carpeta.lecturaPuesta(), true, 'fuera de foco, si se puso');
    globalThis.fetch = async url => {
        const u = new URL(url, 'http://pagina');
        return u.pathname === '/api/hilos/documento'
            ? { ok: true, status: 200, json: async () => ({ hilo: '', titulo: 'a.md', carpeta: '.', archivo: 'a.md', archivos: [], markdown: '# A\n', texto: '' }) }
            : { ok: false, status: 404, json: async () => ({}) };
    };
    const el = { classList: { add() {} }, dataset: {}, innerHTML: '', scrollTop: 0, addEventListener() {} };
    await carpeta.montar(el, '', 'a.md', t => t, {});
    assert.match(el.innerHTML, /<div class="md doc-contenido prosa prosa-md">/, 'el markdown, en la prosa (la de la lectura de un hilo)');
    assert.match(el.innerHTML, /data-accion="doc-lectura"[^>]*class|class="[^"]*si[^"]*" data-accion="doc-lectura"/, 'su ícono, encendido');
    guardado.set('telar.visor.lectura.otro', 'no');
    await carpeta.montar(el, '', 'a.md', t => t, {});
    assert.match(el.innerHTML, /<div class="md doc-contenido">/);
    delete globalThis.localStorage; delete globalThis.document;
}

// 7. la barra de la derecha, sin DOM: con qué abre, el orden y la cuenta
{
    const { inicial, leerRecordado, DE_FABRICA } = ladoMod;
    assert.deepEqual(DE_FABRICA, { plegada: true, hoja: 'conexiones' }, 'de fábrica, plegada');
    assert.deepEqual(inicial(2, { plegada: true, hoja: 'conexiones' }, false), { plegada: false, hoja: 'comentarios' }, 'con abiertos, en comentarios');
    assert.deepEqual(inicial(0, { plegada: false, hoja: 'conexiones' }, false), { plegada: false, hoja: 'conexiones' }, 'sin abiertos, lo recordado');
    assert.deepEqual(inicial(3, { plegada: false, hoja: 'conexiones' }, true), { plegada: true, hoja: 'comentarios' }, 'en el teléfono, siempre plegada');
    assert.deepEqual(leerRecordado({ getItem: () => '{"plegada":false,"hoja":"x"}' }), { plegada: false, hoja: 'conexiones' }, 'una hoja que no hay: la de fábrica');
    assert.deepEqual(leerRecordado({ getItem: () => 'no es json' }), DE_FABRICA);
    const hs = [{ id: 'a', anclado: true, inicio: 50, creado: '2', estado: 'abierto' }, { id: 'b', anclado: false, inicio: null, creado: '1', estado: 'abierto' },
        { id: 'c', anclado: true, inicio: 10, creado: '3', estado: 'resuelto' }, { id: 'd', anclado: true, inicio: 50, creado: '1', estado: 'abierto' }];
    assert.deepEqual(ordenar(hs).map(h => h.id), ['c', 'd', 'a', 'b'], 'en el orden del documento; a la par, el más viejo; sin ancla, al final');
    assert.deepEqual([cuentaDe(hs).n, cuentaDe(hs).tinta], [3, true], 'la cuenta: los abiertos, en la tinta');
    assert.deepEqual([cuentaDe([hs[2]]).n, cuentaDe([hs[2]]).tinta], [1, false], 'sin abiertos, cuántos hay, tenue');
    // en foco, la columna de la prosa va centrada en el visor entero y se corre solo si la barra la taparía
    const css = readFileSync(path.join(aqui, '..', 'media', 'css', 'documento.css'), 'utf8');
    assert.match(css, /\.md\.prosa \{\s*margin-left: max\(0px, min\(\(100cqw - var\(--prosa-ancho\)\) \/ 2 - var\(--pantalla-margen\),\s*100cqw - var\(--doc-lado-ocupa\)/);
}

// 8. la barra de verdad, con un DOM: el visor con un documento comentado, sus comentarios y sus conexiones
{
    // el visor recién cargado (lo de arriba ya le dijo que esta máquina no tiene el grafo, y lo recuerda)
    const otra = salida.replace(/\.cjs$/, '-2.cjs');
    copyFileSync(salida, otra);
    const { carpeta } = require(otra);
    const w = new Window({ url: 'http://pagina/', width: 1440, height: 900 });
    const g = globalThis;
    const antes = { window: g.window, document: g.document, fetch: g.fetch };
    for (const k of ['Node', 'NodeFilter', 'HTMLElement', 'HTMLInputElement', 'HTMLTextAreaElement', 'Element', 'CSS', 'KeyboardEvent', 'MouseEvent', 'Event', 'localStorage', 'screen'])
        g[k] = w[k];
    g.window = w; g.document = w.document; g.getSelection = () => w.getSelection();
    const desplazados = [];
    w.HTMLElement.prototype.scrollIntoView = function () { desplazados.push(this); };

    const DOC2 = `# Plan

Este documento ordena las cuatro sesiones del taller, de modo que al final el proyecto exista.

> Las cuatro sesiones giran en torno a los grupos. **Propuesta para que se decida**; lo demás sale de lo pendiente.

La primera sesión parte por el repositorio. El entregable es un README que se entienda.
`;
    const tramo = t => { const i = DOC2.indexOf(t); assert.ok(i >= 0, t); return { inicio: i, fin: i + t.length, cita: t }; };
    const hilo = (id, t, estado, cuerpo, creado = '2026-11-23T10:00:00') => ({ id, estado, antes: '', despues: '', creado, anclado: true, metodo: 'exacto', confianza: 1,
        linea: DOC2.slice(0, DOC2.indexOf(t)).split('\n').length, linea_fin: null, actual: null, ...tramo(t),
        comentarios: [{ id: 'c1', autor: 'Persona', cuerpo, fecha: creado }] });
    const PARRAFO = 'Este documento ordena las cuatro sesiones del taller, de modo que al final el proyecto exista.';
    const CITA = 'Las cuatro sesiones giran en torno a los grupos. **Propuesta para que se decida**; lo demás sale de lo pendiente.';
    let hilos = [
        hilo('h1', CITA, 'abierto', 'la cita repite el párrafo'),
        hilo('h2', PARRAFO, 'abierto', 'acortarlo'),
        hilo('h3', 'un README', 'resuelto', 'una plantilla'),
        { ...hilo('h4', 'el repositorio', 'abierto', 'se fue'), anclado: false, inicio: null, fin: null, linea: null, creado: '2026-11-22T10:00:00' },
    ];
    const posts = [];
    let docActual = DOC2;
    g.fetch = async (url, o = {}) => {
        const u = new URL(url, 'http://pagina');
        const json = (status, cuerpo) => ({ ok: status === 200, status, json: async () => cuerpo });
        if (u.pathname === '/api/hilos/documento') return json(200, { hilo: '', titulo: 'plan.md', carpeta: '.', archivo: 'plan.md', archivos: [], markdown: docActual, texto: '' });
        if (u.pathname === '/api/comentarios' && o.method === 'POST') {
            const b = JSON.parse(o.body);
            posts.push(b);
            if (b.accion === 'comentar') hilos = [...hilos, { ...hilo('h5', b.cita, 'abierto', b.texto, '2026-11-23T11:00:00'), inicio: b.inicio, fin: b.fin }];
            return json(200, { ruta: 'plan.md', archivo: 'plan.md', lateral: '', maquina: '', autor: 'Persona', hilos, hecho: 'h5' });
        }
        if (u.pathname === '/api/comentarios') return json(200, { ruta: 'plan.md', archivo: 'plan.md', lateral: '', maquina: '', autor: 'Persona', hilos, hecho: '' });
        if (u.pathname === '/api/modulos/grafo/vecinos') return json(200, { nodo: { titulo: 'Plan' },
            salientes: [{ origen: 'plan.md', tipo: 'detalla', destino: 'a.md', estado: 'ok' }, { origen: 'plan.md', tipo: 'usa', destino: 'b.md', estado: 'ok' }],
            entrantes: [{ origen: 'c.md', tipo: 'resume', destino: 'plan.md', estado: 'ok' }] });
        return json(404, {});
    };
    const calma = async () => { for (let k = 0; k < 6; k++) await new Promise(r => setTimeout(r, 0)); };
    const d = w.document;
    const montar = async (archivo = 'plan.md') => {
        d.body.innerHTML = `<div class="ventana ventana-documento">${carpeta.ESQUELETO}</div>`;
        const el = d.querySelector('.v-documento');
        await carpeta.montar(el, '', archivo, t => md.render(t), { cerrar() {} });
        await calma();
        return el;
    };
    const q = (s, r = d) => r.querySelector(s), qq = (s, r = d) => [...r.querySelectorAll(s)];
    const clic = x => x.dispatchEvent(new w.MouseEvent('click', { bubbles: true, cancelable: true }));
    const pasar = x => x.dispatchEvent(new w.MouseEvent('mouseover', { bubbles: true }));

    let el = await montar();
    const aside = q('aside.doc-lado'), ventana = q('.ventana');
    // con comentarios abiertos abre en ellos; la barra de arriba ya no cuenta: la cuenta es la pestaña
    assert.equal(aside.hidden, false, 'la barra, a la vista');
    assert.ok(!aside.classList.contains('plegada'), 'con abiertos, desplegada');
    assert.equal(q('[data-hoja="comentarios"].doc-lado-hoja').hidden, false, 'en comentarios');
    assert.equal(q('[data-hoja="conexiones"].doc-lado-hoja').hidden, true);
    assert.ok(!q('.doc-barra .doc-cuentas') && !q('.doc-barra [data-accion="coment-lista"]') && !q('.doc-barra [data-accion="doc-conexiones"]'), 'sin cuentas arriba');
    assert.ok(!q('.doc-cuerpo .coment-lista') && !q('.doc-cuerpo .conexiones') && !q('.doc-cuerpo .coment-tarjeta'), 'ni la lista ni las conexiones ni una tarjeta en el texto');
    const pestana = h => q(`.doc-lado-barra [data-hoja="${h}"]`);
    // abierta, las pestañas de la casa (componentes/pestanas.ts): la cuenta, `.pestana-cuenta`; la de los abiertos, en el de cuidado
    assert.equal(pestana('comentarios').querySelector('.pestana-cuenta').textContent, '3', 'la pestaña cuenta los abiertos (también el sin ancla)');
    assert.ok(pestana('comentarios').querySelector('.pestana-cuenta').classList.contains('atencion'), 'en la tinta de los comentarios');
    assert.equal(pestana('conexiones').querySelector('.pestana-cuenta').textContent, '3', 'y la de conexiones, las suyas');
    assert.ok(!pestana('datos'), 'sin frontmatter, sin la pestaña de datos');
    assert.ok(pestana('comentarios').classList.contains('si'));
    for (const x of [el, ventana]) assert.ok(x.classList.contains('con-lado') && !x.classList.contains('lado-plegado'), 'el visor y su ventana saben de la barra');

    // el número: en el texto, al final de cada tramo, el mismo que en la barra, en el orden del documento
    const enTexto = qq('.doc-cuerpo sup.coment-n').map(x => [x.dataset.hilo, x.textContent]);
    assert.deepEqual(enTexto, [['h2', '1'], ['h1', '2'], ['h3', '3']], 'en el texto: 1 el párrafo, 2 la cita, 3 el README');
    const enBarra = qq('.coment-fila').map(f => [f.dataset.hilo, q('.coment-num', f).textContent]);
    assert.deepEqual(enBarra, [['h2', '1'], ['h1', '2'], ['h3', '3'], ['h4', '4']], 'en la barra, los mismos; sin ancla al final, sin número en el texto');
    assert.match(q('.coment-grupo').textContent, /sin ancla/);
    assert.ok(q('sup.coment-n[data-hilo="h3"]').classList.contains('resuelto') && q('mark.coment[data-hilo="h3"]').classList.contains('resuelto'), 'el resuelto, tenue, con su número');
    for (const [id, n] of enTexto) {
        const marcas = qq(`mark.coment[data-hilo="${id}"]`);
        assert.equal(marcas.at(-1).nextSibling, q(`sup.coment-n[data-hilo="${id}"]`), `el ${n}, justo después de su tramo`);
    }
    // (la marca va de la primera a la última letra o número: el punto final queda afuera, y el número antes de él, como
    // una llamada de nota)
    assert.equal(qq('mark.coment[data-hilo="h2"]').map(m => m.textContent).join(''), PARRAFO.slice(0, -1), 'un párrafo entero, marcado entero');
    assert.equal(q('sup.coment-n[data-hilo="h2"]').nextSibling.textContent, '.', 'el número, antes del punto');
    assert.equal(qq('mark.coment[data-hilo="h1"]').map(m => m.textContent).join(''), 'Las cuatro sesiones giran en torno a los grupos. Propuesta para que se decida; lo demás sale de lo pendiente',
        'la cita, con la negrita adentro');
    assert.ok(q('blockquote strong mark.coment[data-hilo="h1"]'), 'la negrita sigue siendo negrita (la marca va adentro)');
    const sinNumeros = x => { const c = x.cloneNode(true); for (const n of c.querySelectorAll('sup.coment-n')) n.remove(); return c.textContent.trim(); };
    assert.equal(sinNumeros(q('.doc-cuerpo blockquote')),
        'Las cuatro sesiones giran en torno a los grupos. Propuesta para que se decida; lo demás sale de lo pendiente.', 'el texto, intacto');

    // pasar el mouse: el tramo enciende su fila, y la fila su tramo
    pasar(q('mark.coment[data-hilo="h1"]'));
    assert.ok(q('.coment-fila[data-hilo="h1"]').classList.contains('encendida'), 'el tramo enciende su fila');
    assert.ok(q('sup.coment-n[data-hilo="h1"]').classList.contains('encendida'));
    pasar(q('.coment-fila[data-hilo="h2"]'));
    assert.ok(qq('mark.coment[data-hilo="h2"]').every(m => m.classList.contains('encendida')), 'la fila enciende su tramo');
    assert.ok(!q('.coment-fila[data-hilo="h1"]').classList.contains('encendida'), 'y apaga el otro');

    // clic en el número del texto: la barra se abre en él (con lo suyo y su campo), y el tramo queda marcado
    desplazados.length = 0;
    clic(q('sup.coment-n[data-hilo="h1"]'));
    let fila = q('.coment-fila[data-hilo="h1"]');
    assert.ok(fila.classList.contains('activa') && q('.coment-tarjeta[data-hilo="h1"]', fila), 'abierto en la barra, con lo suyo');
    assert.ok(q('[data-coment="responder"]', fila) && q('[data-coment="resolver"]', fila) && q('[data-coment="editar"]', fila) && q('[data-coment="borrar"]', fila),
        'responder, resolver, editar y borrar, en la barra');
    assert.ok(qq('mark.coment[data-hilo="h1"]').every(m => m.classList.contains('activa')), 'el tramo, marcado');
    assert.ok(desplazados.includes(fila), 'la barra lo muestra');
    assert.equal(qq('.coment-tarjeta').length, 1, 'uno abierto a la vez');
    // clic en una fila: el documento va a su tramo
    desplazados.length = 0;
    clic(q('.coment-fila[data-hilo="h2"] .coment-cita'));
    assert.ok(q('.coment-fila[data-hilo="h2"]').classList.contains('activa') && !q('.coment-fila[data-hilo="h1"]').classList.contains('activa'));
    assert.ok(desplazados.includes(q('mark.coment[data-hilo="h2"]')), 'el documento va al tramo');
    assert.ok(q('mark.coment[data-hilo="h2"]').classList.contains('activa') && !q('mark.coment[data-hilo="h1"]').classList.contains('activa'));
    // ⎋ lo cierra (y no al visor)
    const esc = new w.KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true });
    q('.coment-tarjeta textarea').dispatchEvent(esc);
    assert.ok(esc.defaultPrevented && !q('.coment-tarjeta'), '⎋ cierra el abierto');

    // plegar y desplegar: la flecha la pliega en una franja con cada hoja y su cuenta; se recuerda
    clic(q('[data-doc-lado="plegar"]'));
    assert.ok(aside.classList.contains('plegada') && el.classList.contains('lado-plegado') && ventana.classList.contains('lado-plegado'), 'plegada');
    assert.ok(qq('.doc-lado-hoja').every(h => h.hidden), 'sin hojas a la vista');
    assert.equal(q('.doc-lado-barra .doc-lado-pliegue').innerHTML, I.atras, 'con ‹ arriba, como la ficha');
    assert.deepEqual(qq('.doc-lado-vertical').map(v => [v.dataset.hoja, q('.doc-lado-n', v).textContent]), [['comentarios', '3'], ['conexiones', '3']], 'cada hoja en vertical, con su cuenta');
    assert.deepEqual(JSON.parse(w.localStorage.getItem('telar.visor.lado')), { plegada: true, hoja: 'comentarios' }, 'se recuerda');
    clic(q('.doc-lado-vertical[data-hoja="conexiones"]'));
    assert.ok(!aside.classList.contains('plegada') && pestana('conexiones').classList.contains('si'), 'un clic en una hoja la abre en ella');
    assert.equal(q('[data-hoja="conexiones"].doc-lado-hoja').hidden, false);
    assert.match(q('[data-hoja="conexiones"].doc-lado-hoja').textContent, /salen →.*llegan ←/s, 'las conexiones, en su pestaña');
    assert.equal(q('[data-hoja="comentarios"].doc-lado-hoja').hidden, true);
    // las pestañas
    clic(pestana('comentarios'));
    assert.ok(pestana('comentarios').classList.contains('si') && q('[data-hoja="comentarios"].doc-lado-hoja').hidden === false, 'la pestaña de comentarios');
    assert.deepEqual(JSON.parse(w.localStorage.getItem('telar.visor.lado')), { plegada: false, hoja: 'comentarios' });

    // comentar desde la selección: con la barra plegada, c la abre en comentarios con la caja nueva arriba, lo
    // seleccionado sigue marcado mientras se escribe y ⌘⏎ (el botón «comentar») lo guarda
    clic(q('[data-doc-lado="plegar"]'));
    const p = qq('.doc-cuerpo p').find(x => x.textContent.startsWith('La primera'));
    const r = d.createRange();
    r.setStart(p.firstChild, 3); r.setEnd(p.firstChild, 17);
    w.getSelection().removeAllRanges(); w.getSelection().addRange(r);
    q('.doc-cuerpo').dispatchEvent(new w.KeyboardEvent('keydown', { key: 'c', bubbles: true, cancelable: true }));
    assert.ok(!aside.classList.contains('plegada') && pestana('comentarios').classList.contains('si'), 'c abre la barra en comentarios');
    const caja = q('[data-hoja="comentarios"].doc-lado-hoja').firstElementChild;
    assert.ok(caja.classList.contains('coment-tarjeta') && caja.classList.contains('nuevo'), 'la caja nueva, arriba');
    assert.match(q('.coment-cita', caja).textContent, /primera sesión/);
    assert.equal(d.activeElement, q('textarea', caja), 'con el foco en su campo');
    assert.equal(qq('mark.coment.nuevo').map(m => m.textContent).join(''), 'primera sesión', 'lo seleccionado, marcado en el texto');
    assert.equal(q('button[data-tecla="⌘⏎"]', caja).dataset.coment, 'guardar', '⌘⏎ guarda');
    q('textarea', caja).value = 'cambiar el orden';
    clic(q('button[data-coment="guardar"]', caja));
    await calma();
    assert.equal(posts.at(-1).accion, 'comentar');
    assert.equal(posts.at(-1).cita, 'primera sesión');
    assert.equal(posts.at(-1).texto, 'cambiar el orden');
    assert.ok(!q('mark.coment.nuevo') && !q('.coment-tarjeta.nuevo'), 'guardado: ya no es nuevo');
    assert.deepEqual(qq('.doc-cuerpo sup.coment-n').map(x => [x.dataset.hilo, x.textContent]), [['h2', '1'], ['h1', '2'], ['h5', '3'], ['h3', '4']],
        'el nuevo toma su lugar en el orden del documento, y los de después se corren');
    assert.ok(q('.coment-fila[data-hilo="h5"]').classList.contains('activa'), 'y queda abierto en la barra');
    assert.equal(pestana('comentarios').querySelector('.pestana-cuenta').textContent, '4');

    // sin comentarios abiertos: como se dejó la última vez (plegada, de fábrica)
    w.localStorage.clear();
    hilos = hilos.map(h => ({ ...h, estado: 'resuelto' }));
    el = await montar();
    assert.ok(q('aside.doc-lado').classList.contains('plegada'), 'sin abiertos, plegada de fábrica');
    assert.equal(q('.doc-lado-vertical[data-hoja="comentarios"] .doc-lado-n').textContent, '5', 'la cuenta: cuántos hay');
    assert.ok(!q('.doc-lado-vertical[data-hoja="comentarios"] .doc-lado-n').classList.contains('tinta'), 'tenue');
    w.localStorage.setItem('telar.visor.lado', JSON.stringify({ plegada: false, hoja: 'conexiones' }));
    el = await montar();
    assert.ok(!q('aside.doc-lado').classList.contains('plegada') && pestana('conexiones').classList.contains('si'), 'o abierta en conexiones, si así se dejó');

    // en foco (modo lectura): la prosa, y la barra igual a la derecha (la columna se centra por CSS: lo de arriba)
    d.body.dataset.modo = 'foco';
    hilos = hilos.map((h, k) => ({ ...h, estado: k === 0 ? 'abierto' : h.estado }));
    el = await montar();
    assert.ok(q('.doc-cuerpo .md').classList.contains('prosa'), 'en foco, la prosa');
    assert.ok(el.classList.contains('lectura') && el.classList.contains('con-lado') && !q('aside.doc-lado').classList.contains('plegada'), 'con la barra al lado');
    assert.ok(q('.doc-medio > .doc-cuerpo + aside.doc-lado'), 'la barra, a la derecha del texto');
    delete d.body.dataset.modo;

    // el ancho: el recordado para esta pantalla, en el visor y su ventana
    w.localStorage.setItem('telar.anchos', JSON.stringify({ [`${w.screen.width}x${w.screen.height}`]: { documento: 410 } }));
    d.body.innerHTML = `<div class="ventana ventana-documento">${carpeta.ESQUELETO}</div>`;
    await carpeta.montar(q('.v-documento'), '', 'plan.md', t => md.render(t), { cerrar() {} });
    await calma();
    assert.equal(q('.ventana').style.getPropertyValue('--doc-lado-ancho'), '410px', 'el ancho recordado');

    // en el teléfono: una hoja que sube desde abajo; empieza plegada (una franja con las dos pestañas), un toque en un tramo
    // la sube, ⌄ la baja, y nada de eso se recuerda
    d.body.classList.add('angosto');
    w.localStorage.clear();
    el = await montar();
    const a2 = q('aside.doc-lado');
    assert.ok(a2.classList.contains('plegada'), 'en el teléfono, plegada aunque haya abiertos');
    assert.equal(q('.doc-lado-pliegue').innerHTML, I.subir, 'con ⌃ para subirla');
    assert.equal(qq('.doc-lado-vertical.v').length, 0, 'las pestañas en fila, no en vertical');
    clic(q('mark.coment[data-hilo="h1"]'));
    assert.ok(!a2.classList.contains('plegada') && q('.coment-fila[data-hilo="h1"]').classList.contains('activa'), 'un toque en un tramo la sube en él');
    assert.notEqual(d.activeElement?.tagName, 'TEXTAREA', 'sin abrir el teclado');
    assert.equal(q('.doc-lado-pliegue').innerHTML, I.abierto, '⌄ la baja');
    clic(q('.doc-lado-pliegue'));
    assert.ok(a2.classList.contains('plegada'));
    assert.equal(w.localStorage.getItem('telar.visor.lado'), null, 'no se recuerda');
    d.body.classList.remove('angosto');

    // un .md con frontmatter: el texto, sin él; sus datos, en su pestaña; y los comentarios, anclados contra el archivo
    // entero (con el frontmatter), en el mismo lugar
    const FM = '---\ntitulo: Plan\nestandar: "1.0"\nvigencia: borrador\n---\n';
    docActual = FM + DOC2;
    const corre = FM.length, lineasFm = 5;
    hilos = [{ ...hilo('h1', CITA, 'abierto', 'la cita repite el párrafo'), inicio: tramo(CITA).inicio + corre, fin: tramo(CITA).fin + corre,
        linea: DOC2.slice(0, DOC2.indexOf(CITA)).split('\n').length + lineasFm }];
    w.localStorage.clear();
    el = await montar();
    const cuerpo = q('.doc-cuerpo');
    assert.doesNotMatch(cuerpo.textContent, /titulo:|estandar|vigencia/, 'en el texto no queda nada del frontmatter');
    assert.equal(q('.doc-cuerpo h1').textContent.trim(), 'Plan', 'el título es el título, no el frontmatter');
    assert.equal(q('.doc-cuerpo h1').dataset.src, '5-6', 'con su línea del archivo entero');
    assert.ok(!q('.doc-cuerpo hr'), 'sin una raya');
    assert.deepEqual(qq('.doc-lado-barra [data-hoja]').map(x => x.dataset.hoja), ['comentarios', 'conexiones', 'datos'], 'la tercera pestaña, datos');
    assert.equal(pestana('datos').querySelector('.pestana-cuenta').textContent, '3', 'con su cuenta');
    assert.equal(qq('mark.coment[data-hilo="h1"]').map(m => m.textContent).join(''), 'Las cuatro sesiones giran en torno a los grupos. Propuesta para que se decida; lo demás sale de lo pendiente',
        'el comentario, en su lugar');
    clic(pestana('datos'));
    assert.ok(pestana('datos').classList.contains('si') && q('[data-hoja="datos"].doc-lado-hoja').hidden === false, 'la pestaña de datos, abierta');
    assert.deepEqual(qq('.doc-datos dt').map((x, k) => [x.textContent, qq('.doc-datos dd')[k].textContent]),
        [['titulo', 'Plan'], ['estandar', '1.0'], ['vigencia', 'borrador']], 'clave: valor');
    // comentar con frontmatter: la cita va contra el archivo entero
    clic(q('[data-doc-lado="plegar"]'));
    const p2 = qq('.doc-cuerpo p').find(x => x.textContent.startsWith('La primera'));
    const r2 = d.createRange();
    r2.setStart(p2.firstChild, 3); r2.setEnd(p2.firstChild, 17);
    w.getSelection().removeAllRanges(); w.getSelection().addRange(r2);
    q('.doc-cuerpo').dispatchEvent(new w.KeyboardEvent('keydown', { key: 'c', bubbles: true, cancelable: true }));
    const caja2 = q('[data-hoja="comentarios"].doc-lado-hoja').firstElementChild;
    q('textarea', caja2).value = 'con frontmatter';
    clic(q('button[data-coment="guardar"]', caja2));
    await calma();
    const b = posts.at(-1);
    assert.equal(docActual.slice(b.inicio, b.fin), 'primera sesión', 'el ancla nueva, contra el archivo con su frontmatter');
    assert.equal(b.inicio, DOC2.indexOf('primera sesión') + corre);
    // recargar: los dos calzan
    el = await montar();
    assert.equal(qq('mark.coment[data-hilo="h5"]').map(m => m.textContent).join(''), 'primera sesión', 'recargado, el nuevo calza exacto');
    assert.ok(q('mark.coment[data-hilo="h1"]'), 'y el viejo también');
    // recordada en datos, un documento sin frontmatter abre en conexiones (sin perder lo recordado)
    clic(q('.doc-lado-vertical[data-hoja="datos"]') ?? pestana('datos'));
    docActual = DOC2;
    hilos = [];
    el = await montar();
    assert.ok(!pestana('datos') && pestana('conexiones').classList.contains('si'), 'sin datos, en conexiones');
    assert.equal(JSON.parse(w.localStorage.getItem('telar.visor.lado')).hoja, 'datos');
    // en foco y en el teléfono, igual
    docActual = FM + DOC2;
    d.body.dataset.modo = 'foco';
    el = await montar();
    assert.ok(q('.doc-cuerpo .md').classList.contains('prosa') && pestana('datos') && !/titulo:/.test(q('.doc-cuerpo').textContent), 'en foco');
    delete d.body.dataset.modo;
    d.body.classList.add('angosto');
    el = await montar();
    assert.deepEqual(qq('.doc-lado-vertical').map(v => v.dataset.hoja), ['comentarios', 'conexiones', 'datos'], 'en el teléfono, la franja con datos');
    clic(q('.doc-lado-vertical[data-hoja="datos"]'));
    assert.ok(!q('aside.doc-lado').classList.contains('plegada') && q('.doc-datos'), 'un toque la sube en datos');
    d.body.classList.remove('angosto');
    // un .txt que empieza con --- no cambia: se ve entero
    g.fetch = async (url) => {
        const u = new URL(url, 'http://pagina');
        const json = (status, cuerpo) => ({ ok: status === 200, status, json: async () => cuerpo });
        if (u.pathname === '/api/hilos/documento') return json(200, { hilo: '', titulo: 'n.txt', carpeta: '.', archivo: 'n.txt', archivos: [], texto: FM + 'hola' });
        if (u.pathname === '/api/comentarios') return json(200, { ruta: 'n.txt', archivo: 'n.txt', lateral: '', maquina: '', autor: 'Persona', hilos: [], hecho: '' });
        return json(404, {});
    };
    el = await montar('n.txt');
    assert.match(q('.doc-cuerpo pre').textContent, /^---\ntitulo: Plan/, 'un texto, entero');
    assert.ok(!pestana('datos') && !q('.doc-lado-vertical[data-hoja="datos"]'), 'y sin datos');

    // una carpeta: sin barra
    g.fetch = async () => ({ ok: true, status: 200, json: async () => ({ hilo: '', titulo: 'x', carpeta: 'x', archivo: '', archivos: [], markdown: '', texto: '' }) });
    el = await montar('x');
    assert.ok(q('aside.doc-lado').hidden && !el.classList.contains('con-lado'), 'una carpeta, sin barra');

    await w.happyDOM.close();
    for (const k of ['Node', 'NodeFilter', 'HTMLElement', 'HTMLInputElement', 'HTMLTextAreaElement', 'Element', 'CSS', 'KeyboardEvent', 'MouseEvent', 'Event', 'localStorage', 'screen', 'getSelection']) delete g[k];
    Object.assign(g, antes);
}

console.log('documento: bien');
