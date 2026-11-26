// Prueba de los componentes de la página en el lienzo de un módulo (src/lienzo/componentes.ts, vistas/dashboard/pagina.ts):
//
// · lo que recibe el lienzo que dice `"componentes": true`: la hoja de los componentes antes de su HTML, los tokens que
//   usa con el valor del tema, y su código después de `window.lienzo`; nada que cierre su <script> o su <style> antes de
//   tiempo; se leen una vez; si no se pudieron leer, el lienzo no los recibe (dibuja lo suyo) y se vuelve a probar; un
//   lienzo que no los pide, no los recibe.
// · ya en el lienzo, con un DOM (happy-dom) y un `window.lienzo.pedir` de mentira: `window.lienzo.componentes` arma el
//   mismo HTML que la página; las pestañas que no caben van al «⋯» solas al dibujarse (con anchos de mentira), y su menú
//   es el de la casa, pedido a la página (`opciones`), con lo elegido abierto como un clic; un grupo de filtros plegado
//   abre sus opciones igual, y lo elegido le llega al lienzo como el clic en su opción; el ✕ del buscador lo borra; sin
//   `pedir`, el menú no se abre y nada se cae.
// · lo empaquetado (src/telar/web/lienzo-componentes.*): la letra de íconos como `telar-iconos`, sin capa, sin la página.
//
// Corre en Node: npm run prueba:lienzo-componentes
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
const web = path.join(aqui, '..', '..', 'src', 'telar', 'web');
const tmp = mkdtempSync(path.join(tmpdir(), 'lienzo-componentes-'));
const dormir = ms => new Promise(r => setTimeout(r, ms));

const w = new Window({ url: 'http://localhost/' });
for (const k of ['window', 'document', 'CSS', 'Element', 'HTMLElement', 'HTMLInputElement', 'HTMLIFrameElement', 'Node', 'Event',
    'KeyboardEvent', 'MouseEvent', 'MutationObserver', 'getComputedStyle', 'requestAnimationFrame', 'innerWidth', 'innerHeight',
    'sessionStorage', 'localStorage'])
    globalThis[k] = k === 'window' ? w : w[k] ?? globalThis[k];
globalThis.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {}, addListener() {} });
const document = w.document;
const q = s => document.querySelector(s);

// ── 1. lo que va en el lienzo que los pide (vistas/dashboard/pagina.ts) ──
{
    // el disco de mentira: la página del lienzo
    globalThis.fetch = async url => {
        const u = new URL(String(url), 'http://localhost');
        if (u.pathname === '/api/archivos') return new Response(JSON.stringify({ texto: '<p id="suyo">hola</p>' }), { status: 200 });
        return new Response('', { status: 404 });
    };
    const outfile = path.join(tmp, 'pagina.cjs');
    await build({ entryPoints: [path.join(src, 'vistas', 'dashboard', 'pagina.ts')], bundle: true, platform: 'node', format: 'cjs',
        outfile, logLevel: 'warning', loader: { '.css': 'text' } });
    const { Paginas, kitLienzo, armarKit } = require(outfile);
    document.documentElement.style.setProperty('--acento', '#abcdef');
    document.documentElement.style.setProperty('--pestana-color', 'rgb(1, 2, 3)');

    let leidas = 0, falla = false;
    kitLienzo.leer = async () => {
        leidas++;
        if (falla) return undefined;
        return armarKit('window.lienzo.componentes={version:1};console.log("</script><b>")',
            '.pestana{color:var(--pestana-color);background:var(--acento)}/* </style><i> */');
    };
    const srcdoc = html => { const d = document.createElement('div'); d.innerHTML = html; return d.querySelector('iframe')?.getAttribute('srcdoc') ?? ''; };

    const p = new Paginas();
    const con = { archivo: '/m/plantilla.html', alto: 'lleno', componentes: true };
    await p.precargar([{ lienzo: con }]);
    const doc = srcdoc(p.lienzo(con, 'bloque:mod'));
    const en = t => doc.indexOf(t);
    assert.ok(en('.pestana{color:var(--pestana-color)') > 0, 'la hoja de los componentes');
    assert.ok(en(':root:root{') < en('.pestana{'), 'después de los tokens');
    assert.ok(en('.pestana{') < en('window.lienzo={params:'), 'antes del código de window.lienzo');
    assert.ok(en('window.lienzo={params:') < en('window.lienzo.componentes={version:1}'), 'el código de los componentes, después de window.lienzo');
    assert.ok(en('window.lienzo.componentes=') < en('<p id="suyo">'), 'y todo antes del HTML del lienzo');
    assert.match(doc, /--pestana-color:rgb\(1, 2, 3\)/, 'los tokens que usa su hoja, con el valor del tema');
    assert.match(doc, /--acento:#abcdef/);
    assert.ok(!/<\/script><b>/.test(doc) && /<\\\/script><b>/.test(doc), 'su código no cierra su <script> antes de tiempo');
    assert.ok(!/<\/style><i>/.test(doc), 'ni su hoja el <style>');
    // con el DOM del iframe: el HTML del lienzo sigue entero
    const d2 = new w.DOMParser().parseFromString(doc, 'text/html');
    assert.equal(d2.querySelector('#suyo')?.textContent, 'hola', 'el lienzo, intacto');
    assert.equal(d2.querySelectorAll('script').length, 2, 'dos scripts: window.lienzo y los componentes');

    // se leen una vez
    await p.precargar([{ lienzo: con }]);
    assert.equal(leidas, 1, 'una vez por página');

    // un lienzo que no los pide no los recibe
    const sin = srcdoc(p.lienzo({ archivo: '/m/plantilla.html' }, 'bloque:otro'));
    assert.ok(!sin.includes('.pestana{') && !sin.includes('componentes={') && !sin.includes('--pestana-color'), 'sin pedirlos, nada');

    // si no se pudieron leer: el lienzo no los recibe (dibuja lo suyo), y la próxima página vuelve a probar
    falla = true; leidas = 0;
    const p2 = new Paginas();
    await p2.precargar([{ lienzo: con }]);
    const sinKit = srcdoc(p2.lienzo(con, 'bloque:mod'));
    assert.ok(sinKit.includes('<p id="suyo">') && !sinKit.includes('componentes={'), 'sin los componentes, el lienzo de siempre');
    falla = false;
    await p2.precargar([{ lienzo: con }]);
    assert.equal(leidas, 2, 'se vuelve a probar');
    assert.ok(srcdoc(p2.lienzo(con, 'bloque:mod')).includes('componentes={'), 'y ahora sí');

    // los tokens: los que nombra la hoja, una vez cada uno
    assert.deepEqual(armarKit('', 'a{color:var(--x);b:var(--y, var(--x))}').tokens, ['--x', '--y']);
}

// ── 2. en el lienzo: window.lienzo.componentes ──
const pedidos = [];
let responder = () => null;
w.lienzo = { params: {}, pedir: async (orden, datos) => { pedidos.push([orden, datos]); return responder(orden, datos); } };
{
    const outfile = path.join(tmp, 'kit.cjs');
    await build({ stdin: { contents: `export * as PW from './web/pestanas-fila'; export * as P from './componentes/pestanas';
        export * as F from './componentes/filtros'; export * as K from './lienzo/componentes';`, resolveDir: src, loader: 'ts' },
        bundle: true, platform: 'node', format: 'cjs', outfile, logLevel: 'warning' });
    const { PW, P, F, K } = require(outfile);
    const C = w.lienzo.componentes;
    assert.ok(C && C === K.componentes, 'queda en window.lienzo.componentes al cargarse');
    assert.equal(typeof w.lienzo.pedir, 'function', 'sin tocar lo demás de window.lienzo');
    assert.equal(C.version, 2);
    for (const f of ['pestanas', 'pestana', 'buscador', 'barraBuscar', 'filtros', 'marcarFiltros', 'contarFiltro', 'leerGrupo', 'acomodar', 'marcar', 'elegir', 'prosa'])
        assert.equal(typeof C[f], 'function', `${f}`);
    assert.equal(C.iconos.buscar, '\u{ea6d}', 'los íconos de la página');

    // el mismo HTML que la página
    const props = { nombre: 'vistas', accion: 'vista', activa: 'b', fin: '<a class="nueva">+</a>',
        pestanas: ['a', 'b', 'c', 'd', 'e'].map(v => ({ valor: v, nombre: `vista ${v}`, cuenta: v === 'e' ? 3 : undefined, nuevo: v === 'e' ? 'exito' : undefined })) };
    assert.equal(C.pestanas(props), P.pestanas(props));
    const grupos = [{ clave: 'area', nombre: 'área', plegado: true, activa: 'todas', siempre: 'todas',
        opciones: [{ clave: 'todas', nombre: 'todas', cuenta: 9 }, { clave: 'norte', nombre: 'norte', cuenta: 4 }, { clave: 'sur', nombre: 'sur', cuenta: 5 }] }];
    assert.equal(C.filtros({ grupos }), F.filtros({ grupos }));

    // las pestañas que no caben: al «⋯» solas, al aparecer (el lienzo solo pone el HTML)
    const clics = [];
    document.addEventListener('click', e => {
        const t = e.target.closest?.('[data-accion]');
        if (t) clics.push([t.dataset.accion, t.dataset.valor ?? t.dataset.id]);
    });
    let fila = 180;
    PW.medir.ancho = el => el.classList.contains('pestanas-lista') ? fila - 30 : el.classList.contains('pestanas-mas') ? 20
        : el.classList.contains('pestana') ? 50 : el.classList.contains('pestanas') ? fila : 0;
    document.body.innerHTML = `<header>${C.pestanas(props)}</header>`;
    await dormir(10);
    const fuera = () => [...document.querySelectorAll('.pestana.fuera')].map(x => x.dataset.valor);
    assert.deepEqual(fuera(), ['d', 'e'], 'las que no caben, al «⋯», sin que el lienzo lo pida');
    const mas = q('.pestanas-mas');
    assert.ok(!mas.hidden, 'el «⋯» a la vista');
    assert.ok(mas.querySelector('.pestana-nuevo.tono-exito'), 'lo nuevo de una escondida, en el «⋯»');
    // repintar la cabecera (lo que hace un lienzo con cada cambio): la fila nueva también
    document.querySelector('header').innerHTML = C.pestanas({ ...props, activa: 'e' });
    await dormir(10);
    assert.deepEqual(fuera(), ['c', 'd'], 'la abierta, a la vista, también en la fila repintada');

    // el menú del «⋯»: el de la casa, pedido a la página; lo elegido se abre como un clic
    responder = (orden, datos) => (orden === 'opciones' ? { indice: datos.opciones.findIndex(o => o.nombre === 'vista c') } : null);
    q('.pestanas-mas').click();
    await dormir(10);
    const [orden, datos] = pedidos.at(-1);
    assert.equal(orden, 'opciones');
    assert.deepEqual(datos.opciones.map(o => o.nombre), ['vista c', 'vista d'], 'las escondidas');
    assert.equal(datos.titulo, 'vistas', 'de qué son');
    assert.ok(typeof datos.x === 'number' && typeof datos.y === 'number', 'junto al «⋯», en las coordenadas del lienzo');
    assert.deepEqual(clics.at(-1), ['vista', 'c'], 'lo elegido le llega al lienzo como el clic en esa pestaña');
    // sin elegir: nada
    const antes = clics.length;
    responder = () => null;
    q('.pestanas-mas').click();
    await dormir(10);
    assert.equal(clics.length, antes, 'sin elegir, nada');

    // un filtro plegado: sus opciones en el menú, la que rige con ✓; lo elegido, como el clic en su opción
    document.body.innerHTML = C.barraBuscar({ placeholder: 'ideas', valor: 'algo', herramientas: C.filtros({ accion: 'filtro', grupos }) });
    responder = (orden, d) => (orden === 'opciones' ? { indice: d.opciones.findIndex(o => o.nombre === 'sur') } : null);
    q('.filtros-grupo.plegado').click();
    await dormir(10);
    const [, op] = pedidos.at(-1);
    assert.deepEqual(op.opciones.map(o => o.nombre), ['todas', 'norte', 'sur']);
    assert.equal(op.titulo, 'área');
    assert.deepEqual(op.opciones[0], { nombre: 'todas', ayuda: '9 · clic: soltarlo', icono: C.iconos.hecha, color: 'acento' }, 'la que rige, con ✓ en el acento');
    assert.deepEqual(clics.filter(c => c[0] === 'filtro-abrir'), [], 'el grupo no le llega al lienzo: lo abre el componente');
    assert.deepEqual(clics.at(-1), ['filtro', 'area:sur'], 'lo elegido, como el clic en su opción');

    // el ✕ del buscador: lo borra y avisa con un input
    let escrito = null;
    document.addEventListener('input', e => { escrito = e.target.value; });
    q('[data-buscador-borrar]').click();
    assert.equal(q('input.buscar').value, '');
    assert.equal(escrito, '', 'el lienzo filtra de nuevo con lo que ya escucha');

    // la prosa: el markdown lo dibuja la página (`prosa`), en un .prosa.prosa-md que sabe de qué archivo es
    responder = (orden, d) => (orden === 'prosa' ? { html: `<h2>Para quién es</h2><p>${d.markdown}</p>`
        + '<p><a href="../sprint/">sprint</a> <a href="metodologia.md#x">m</a> <a href="/empresa/x.md">abs</a>'
        + ' <a href="https://example.org">web</a> <a href="#para-quien-es">arriba</a></p>' } : null);
    const html = await C.prosa('hola', { ruta: 'empresa/servicios/ia/cursos/README.md' });
    assert.match(html, /^<div class="prosa prosa-md" data-base="empresa\/servicios\/ia\/cursos\/README\.md"><h2>/);
    assert.deepEqual(pedidos.at(-1), ['prosa', { markdown: 'hola' }]);
    document.body.innerHTML = html;
    const abiertos = () => pedidos.filter(p => p[0] === 'abrir').map(p => p[1].direccion);
    for (const a of document.querySelectorAll('.prosa-md a')) a.click();
    await dormir(10);
    assert.deepEqual(abiertos(), ['archivo:empresa/servicios/ia/sprint/README.md', 'archivo:empresa/servicios/ia/cursos/metodologia.md',
        'archivo:/empresa/x.md'], 'lo relativo, desde su carpeta (una carpeta, su README); lo de afuera y lo de la página, no');
    assert.match(document.querySelector('a[href^="https"]').title, /afuera/, 'lo de afuera dice adónde va');
    assert.equal(K.destinoDe('a b.md', 'r/x.md'), 'r/a b.md');
    assert.equal(K.destinoDe('%C3%A9/', 'r/x.md'), 'r/é/README.md');
    // si la página no lo dibuja: el texto tal cual, escapado, en la misma prosa
    responder = () => { throw new Error('no'); };
    assert.equal(await C.prosa('<b>', {}), '<div class="prosa prosa-md"><pre style="white-space: pre-wrap">&lt;b&gt;</pre></div>');
    responder = () => null;

    // sin pedir (un lienzo que no es de un módulo): el menú no se abre, y nada se cae
    const pedir = w.lienzo.pedir;
    delete w.lienzo.pedir;
    assert.equal(await C.elegir([{ nombre: 'x' }], document.body), undefined);
    w.lienzo.pedir = async () => { throw new Error('no'); };
    assert.equal(await C.elegir([{ nombre: 'x' }], document.body), undefined, 'si la página dice que no, tampoco');
    w.lienzo.pedir = pedir;
}

// ── 3. lo empaquetado ──
{
    const css = readFileSync(path.join(web, 'lienzo-componentes.css'), 'utf8');
    const js = readFileSync(path.join(web, 'lienzo-componentes.js'), 'utf8');
    assert.match(css, /@font-face \{ font-family: telar-iconos; src: url\("data:font\/woff2;base64,/, 'la letra de la página, como telar-iconos');
    assert.ok(!/font-family: iconos;/.test(css), 'sin tapar la del lienzo');
    assert.ok(!/@layer/.test(css), 'sin capa: entra antes que la del lienzo');
    for (const c of ['.pestanas {', '.pestanas-mas', '.buscador-barra', '.filtros {', '.circulo', '.prosa {', '.prosa-md {']) assert.ok(css.includes(c), `con ${c}`);
    assert.match(css, /:is\(\.pestanas, \.buscador-barra, \.buscador, \.filtros\) \.i \{ font-family: telar-iconos, iconos, monospace; \}/);
    assert.ok(js.includes('opciones') && js.includes('lienzo'), 'su código');
    assert.ok(!/markdown-it|xterm/i.test(js.replace(/markdown:"/g, '')), 'sin la página');
    assert.ok(js.length < 40_000, `chico: ${js.length} bytes`);
    const attrs = readFileSync(path.join(aqui, '..', '..', '.gitattributes'), 'utf8');
    assert.match(attrs, /lienzo-componentes\.js\s+merge=telar-compilado/);
    assert.match(attrs, /lienzo-componentes\.css\s+merge=telar-compilado/);
}

console.log('lienzo-componentes: el lienzo que los pide los recibe en línea, y en él las pestañas, el buscador, los filtros y la prosa andan solos');
