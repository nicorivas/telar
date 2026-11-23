// Prueba del ítem (src/componentes/item.ts): sus tres secciones, que una ranura vacía ocupa su lugar, que lo escrito se
// escapa, y dónde va cada acción (las fijas, y las que aparecen al pasar el mouse con el ⋯ al último). Y que la lámina del
// catálogo (componentes/anatomia.ts) nombra todas sus piezas, y que la gramática visual (componentes/gramatica.ts) se
// sostiene. Y la urgencia (vistas/dashboard/urgencia.ts), Táctica (componentes/tactica.ts, vistas/dashboard/tactica.ts), el
// prototipo de los modos y los mundos (componentes/modos-mundos.ts, componentes/todo.ts) y las iniciativas de la
// pantalla de proyectos (vistas/dashboard/iniciativas.ts). Corre en Node, sin página: npm run prueba:componentes
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const salida = path.join(mkdtempSync(path.join(tmpdir(), 'componentes-')), 'item.cjs');
const armar = async (nombre) => {
    const outfile = path.join(path.dirname(salida), `${nombre}.cjs`);
    await build({ entryPoints: [path.join(aqui, '..', 'src', 'componentes', `${nombre}.ts`)], bundle: true, platform: 'node', format: 'cjs', outfile, logLevel: 'warning' });
    return require(outfile);
};
const { item } = await armar('item');
const { SECCIONES, EJEMPLO, SECCIONES_TARJETA, EJEMPLO_TARJETA } = await armar('anatomia');
const { tarjeta } = await armar('tarjeta');
const { partes } = await armar('partes');

// 1. solo el título: sin inicio ni fin
const solo = item({ titulo: 'faro' });
assert.equal(solo, '<div class="item"><span class="item-texto"><span class="item-titulo">faro</span></span></div>');

// 2. las tres secciones, en orden; una ranura vacía ocupa su lugar
const todo = item({
    inicio: [{ icono: 'P', tono: 'p1' }, null, { texto: 'servidor', ancho: 8, tono: 'atencion', ayuda: 'vive en servidor' }],
    prefijo: [{ texto: 'A', tono: 'agente' }], titulo: 'faro', sufijo: [{ texto: '◇', tono: 'tenue' }],
    aviso: { texto: '●', tono: 'exito', ayuda: '3 sin leer' }, meta: { texto: '49m' },
    fijas: [{ accion: 'home', id: 'x', texto: 'home', ayuda: 'su casa' }],
    menu: { accion: 'menu', id: 'faro', icono: 'M', ayuda: 'más' },
    acciones: [{ accion: 'cerrar', id: 'faro', icono: 'X', peligro: true, ayuda: 'descartar' }],
    variante: 'agente', activa: true, hondo: 7, arrastrable: true, accion: 'ir', id: 'faro', datos: { hilo: 'faro', grupo: 'hilos' }, ayuda: 'el faro',
});
const i = (s) => todo.indexOf(s);
assert.ok(i('item-inicio') < i('item-texto') && i('item-texto') < i('item-fin'), 'inicio · texto · fin');
assert.match(todo, /^<div class="item agente activa hondo3" data-accion="ir" data-id="faro" data-hilo="faro" data-grupo="hilos" draggable="true" title="el faro">/,
    'la variante, los estados y el hondo (hasta 3), y lo que lleva el clic');
assert.match(todo, /<span class="item-inicio"><span class="item-ranura tono-p1"><span class="i">P<\/span><\/span><span class="item-ranura"><\/span>/,
    'la ranura vacía queda, sin nada');
assert.match(todo, /<span class="item-ranura tono-atencion ancha" title="vive en servidor" style="width: 8ch">servidor<\/span>/, 'una ranura ancha, con texto');
assert.match(todo, /<span class="item-prefijo tono-agente">A<\/span> <span class="item-titulo">faro<\/span> <span class="item-sufijo tono-tenue">◇<\/span>/,
    'prefijo, título y sufijo, separados por un espacio');
assert.ok(i('item-aviso') < i('item-meta') && i('item-meta') < i('data-accion="home"') && i('data-accion="home"') < i('item-acciones'),
    'al final: el aviso, la meta, las fijas y después las que flotan');
assert.match(todo, /<span class="item-acciones"><span class="item-accion cuadrada peligro" data-accion="cerrar".*<span class="item-accion item-menu cuadrada" data-accion="menu" data-id="faro" title="más">.*<\/span><\/span><\/span><\/div>$/,
    'el ⋯ al último, en el borde (y lo que borra, marcado)');

// un botón de solo un ícono es cuadrado (su celda, la misma para todos: item.css); con palabra, no
assert.ok(todo.includes('<span class="item-accion" data-accion="home" data-id="x" title="su casa">home</span>'), 'con palabra, sin celda cuadrada');

// 3. lo escrito se escapa; el HTML de confianza va tal cual
const raro = item({ titulo: '<b>"x"</b>', ayuda: 'a "b" <c>', meta: { texto: '<i>' }, prefijo: [{ html: '<canvas class="glifo-hilo"></canvas>' }] });
assert.ok(!raro.includes('<b>') && raro.includes('&lt;b&gt;&quot;x&quot;&lt;/b&gt;'), 'el título');
assert.ok(raro.includes('title="a &quot;b&quot; &lt;c&gt;"'), 'la ayuda');
assert.ok(raro.includes('&lt;i&gt;'), 'la meta');
assert.ok(raro.includes('<canvas class="glifo-hilo"></canvas>'), 'el html');
assert.ok(item({ tituloHtml: 'uno · <a>dos</a>' }).includes('<span class="item-titulo">uno · <a>dos</a></span>'), 'tituloHtml');

// 4. lo que está en curso: un círculo que se mueve en su ranura (y nada más se mueve); y la cabecera
const { circulo } = await armar('circulo');
assert.match(item({ titulo: 'x', inicio: [{ circulo: { mov: 'gira' }, tono: 'remoto', ayuda: 'viajando' }] }),
    /<span class="item-ranura tono-remoto" title="viajando"><span class="circulo tam-grande mov-gira" style="--lleno: 50%"><\/span><\/span>/, 'gira, a medias');
assert.equal(circulo({ mov: 'vacia' }), '<span class="circulo tam-grande mov-vacia"></span>', 'al vaciarse, el llenado es del movimiento');
assert.equal(circulo({ lleno: .25, tam: 'chico' }), '<span class="circulo tam-chico" style="--lleno: 25%"></span>');
assert.equal(circulo({ lleno: 7 }), '<span class="circulo tam-grande" style="--lleno: 100%"></span>', 'el llenado, entre 0 y 1');
assert.ok(!item({ titulo: 'x', meta: { texto: 'cerrando' } }).includes('puntos'), 'la meta en curso, quieta');
assert.match(item({ variante: 'cabecera', titulo: 'hilos', ancla: 'archivo' }), /^<div class="item cabecera" id="archivo">/);
// un submenú (ARCHIVO dentro de HILOS): una fila más, con su clase, su ancla y la flecha en su última ranura
assert.match(item({ variante: 'submenu', titulo: 'archivo', ancla: 'archivo', inicio: [null, null, { icono: 'v' }] }),
    /^<div class="item submenu" id="archivo"><span class="item-inicio"><span class="item-ranura"><\/span><span class="item-ranura"><\/span><span class="item-ranura"><span class="i">v<\/span><\/span><\/span>/);
assert.equal(item({ variante: 'normal', titulo: 'x' }).startsWith('<div class="item">'), true, '«normal» no agrega clase');

// 5. la lámina nombra cada pieza que dibuja item(), y su ejemplo las tiene todas: si el ítem gana una, la lámina la pide
const dibujo = item(EJEMPLO);
const clases = (html) => new Set([...html.matchAll(/class="([^"]*)"/g)].flatMap(m => m[1].split(' ')).filter(c => c.startsWith('item-')));
const nombradas = new Set(SECCIONES.flatMap(x => [x.selector, ...x.partes.map(p => p.selector)]).flatMap(sel => [...sel.matchAll(/\.(item-[a-z-]+)/g)].map(m => m[1])));
assert.deepEqual([...clases(dibujo)].sort(), [...nombradas].sort(), 'las piezas del ejemplo y las de la lámina');
const ranuras = (dibujo.match(/class="item-ranura/g) ?? []).length;
for (const p of SECCIONES.flatMap(x => x.partes)) {
    assert.ok(p.nombre && p.prop && p.intencion, `${p.selector}: nombre, prop e intención`);
    if (p.selector === '.item-ranura') assert.ok((p.n ?? 0) < ranuras, `la ranura ${p.n} está en el ejemplo`);
}
assert.deepEqual(SECCIONES.map(x => x.clave), ['inicio', 'texto', 'fin'], 'las tres secciones, en orden');

// 5b. la tarjeta: cabecera (inicio, título, acciones), cuerpo y pie, en ese orden; su lámina nombra cada pieza que dibuja
const tj = tarjeta(EJEMPLO_TARJETA);
const en = (s) => tj.indexOf(s);
assert.ok(en('tarjeta-cabecera') < en('item-inicio') && en('item-inicio') < en('tarjeta-titulo') && en('tarjeta-titulo') < en('tarjeta-acciones')
    && en('tarjeta-acciones') < en('tarjeta-cuerpo') && en('tarjeta-cuerpo') < en('tarjeta-pie'), 'cabecera (inicio, título, acciones) · cuerpo · pie');
assert.ok(tarjeta({ titulo: 'x' }).startsWith('<div class="item tarjeta"><div class="tarjeta-cabecera">'), 'la cabecera va siempre');
assert.ok(en('item-menu') > en('tarjeta-acciones') && en('item-menu') < en('tarjeta-cuerpo'), 'el ⋯, al último de las acciones, arriba');
assert.match(tj, /^<div class="item tarjeta">/, 'lleva la clase del ítem');
assert.ok(!tarjeta({ titulo: 'x' }).includes('tarjeta-pie') && !tarjeta({ titulo: 'x' }).includes('tarjeta-cuerpo'), 'sin datos ni cuerpo, sin pie ni cuerpo');
assert.ok(tarjeta({ titulo: '<b>' }).includes('&lt;b&gt;'), 'el título se escapa');
const clasesTj = new Set([...tj.matchAll(/class="([^"]*)"/g)].flatMap(m => m[1].split(' ')).filter(c => /^(item|tarjeta)-/.test(c)));
const nombradasTj = new Set(SECCIONES_TARJETA.flatMap(x => [x.selector, ...x.partes.map(p => p.selector)])
    .flatMap(sel => [...sel.matchAll(/\.((?:item|tarjeta)-[a-z-]+)/g)].map(m => m[1])));
assert.deepEqual([...clasesTj].sort(), [...nombradasTj].sort(), 'las piezas de la tarjeta de ejemplo y las de su lámina');
for (const p of SECCIONES_TARJETA.flatMap(x => x.partes)) assert.ok(p.nombre && p.prop && p.intencion, `${p.selector}: nombre, prop e intención`);
assert.deepEqual(SECCIONES_TARJETA.map(x => x.clave), ['cabecera', 'cuerpo', 'pie'], 'las tres partes de la tarjeta, en orden');

// 6. la densidad «auto»: amplia si se apunta con el dedo, compacta con mouse; una que no se conoce, la de fábrica
let tactil = false;
globalThis.matchMedia = (q) => ({ matches: q === '(pointer: coarse)' && tactil, addEventListener() {} });
const densidades = await armar('densidades');
assert.equal(densidades.resolver('auto'), 'compacta', 'con mouse');
tactil = true;
assert.equal(densidades.resolver('auto'), 'amplia', 'con el dedo');
assert.equal(densidades.resolver('comoda'), 'comoda', 'la pedida, tal cual');
assert.equal(densidades.resolver('enorme'), 'compacta', 'una que no existe');
delete globalThis.matchMedia;


// 6. la gramática visual (componentes/gramatica.ts): cada variable responde una pregunta distinta, ningún concepto se
// repite (ni su clave ni lo que dice), cada figura del círculo tiene el suyo, cada derivada apunta a conceptos que existen
// y nada pide un cuarto tamaño ni pone llenado a un punto o a una figura
const { FIGURAS, TAMANOS } = await armar('circulo');
const G = await armar('gramatica');
const variables = [...G.REDONDO, ...G.RECTO];
assert.equal(new Set(variables.map(x => x.pregunta)).size, variables.length, 'cada variable, su pregunta');
const valores = variables.flatMap(x => x.valores);
assert.equal(new Set(valores.map(v => v.clave)).size, valores.length, 'cada concepto con su clave, sin repetir');
assert.equal(new Set(valores.map(v => v.dice)).size, valores.length, 'dos conceptos no dicen lo mismo');
for (const x of variables) assert.ok(x.valores.length >= 2, `${x.clave}: al menos dos valores`);
for (const v of valores) assert.ok(v.nombre && v.dice && v.sirve.length, `${v.clave}: nombre, concepto y para qué sirve`);
const conFigura = new Set(G.REDONDO.flatMap(x => x.valores).flatMap(v => (v.dibujo ?? []).map(d => d.figura)).filter(Boolean));
for (const f of FIGURAS) assert.ok(conFigura.has(f.figura), `la figura ${f.figura} tiene su concepto`);
const claves = new Set(valores.map(v => v.clave));
for (const d of G.DERIVADAS) for (const c of d.conceptos) assert.ok(claves.has(c), `${d.uso}: su concepto ${c} existe`);
for (const t of [...valores.flatMap(v => v.dibujo ?? []), ...G.DERIVADAS.flatMap(d => d.dibujo)]) {
    assert.ok(!t.tam || TAMANOS.includes(t.tam), `solo los tres tamaños (no «${t.tam}»)`);
    assert.ok(!(t.figura && (t.tam || t.lleno !== undefined)), 'una figura no lleva tamaño ni llenado: ocupa lo de uno grande');
    assert.ok(!(t.tam === 'punto' && (t.figura || (t.lleno ?? 1) !== 1)), 'un punto no lleva llenado ni figura');
}

// cómo se parte un rectángulo: cada parte una vez, con qué es, cómo se marca y un ejemplo
assert.equal(new Set(G.PARTES.map(p => p.clave)).size, G.PARTES.length, 'cada parte, una vez');
for (const p of G.PARTES) assert.ok(p.nombre && p.es && p.marca && p.ejemplo, `${p.clave}: qué es, cómo se marca y un ejemplo`);
assert.ok(G.REGLAS_PARTIR.length, 'las reglas de cómo se parte');

// 7. las señales (componentes/senales.ts): los estados son círculos, nunca un ícono de la letra
const S = await armar('senales');
assert.deepEqual(S.atencion('termino'), { circulo: { figura: 'diana' }, tono: 'termino' }, 'terminó: con algo adentro');
assert.equal(S.atencion('termino', true), null, 'terminó y ya lo viste: nada que decir');
assert.equal(S.atencion('ninguna'), null, 'sin atención, la ranura vacía');
assert.deepEqual([0, 1, 2, 3, 7, null].map(p => S.prioridad(p).circulo), [{ tam: 'punto' }, { tam: 'chico', lleno: 1 }, { tam: 'chico', lleno: .5 }, { tam: 'chico', lleno: 0 }, { tam: 'punto' }, { tam: 'punto' }]);
for (const p of [S.atencion('trabajando'), S.atencion('espera'), S.prioridad(1), S.remoto(), S.viaja(), S.sale(), S.publico(), S.nuevo(), S.presente(true)]) {
    assert.ok(p.circulo && !p.icono && !p.texto, 'una señal es un círculo');
}
assert.match(S.enLinea(S.publico('a "b"')), /^<span class="senal tono-tenue" title="a &quot;b&quot;"><span class="circulo tam-grande fig-enlace"><\/span><\/span>$/);

// 8. el orden (componentes/orden.ts): ícono padre, las opciones, entre dos cortes; una rige; lo escrito se escapa
const { orden, esIcono, CORTE_ORDEN } = await armar('orden');
const ops = [{ clave: 'nombre', icono: '\u{eb73}', ayuda: 'nombre' }, { clave: 'x', icono: 'ab', ayuda: 'a "b"' }];
const o = orden({ grupo: 'hilos', opciones: ops, activa: 'nombre' });
assert.ok(o.startsWith(CORTE_ORDEN) && o.endsWith(CORTE_ORDEN), 'entre dos cortes');
assert.ok(o.indexOf('orden-padre') < o.indexOf('data-id="hilos:nombre"') && o.indexOf('hilos:nombre') < o.indexOf('hilos:x'), 'padre, y las opciones en su orden');
assert.match(o, /class="ord si i" data-accion="orden-grupo" data-id="hilos:nombre" title="ordenar por nombre \(clic: volver al orden de telar\)"/, 'la que rige, marcada, con su letra');
assert.match(o, /class="ord" data-accion="orden-grupo" data-id="hilos:x" title="ordenar por a &quot;b&quot;"/, 'las otras, sin marca; el texto se escapa');
assert.equal((orden({ grupo: 'g', opciones: ops, activa: '' }).match(/ord si/g) ?? []).length, 0, 'sin activa, ninguna marcada');
assert.ok(esIcono('\u{eb73}') && !esIcono('a') && !esIcono('ab'), 'un ícono es un solo carácter del área privada');

// 9. el buscador (componentes/buscador.ts): su prueba es la suya, npm run prueba:buscador (pruebas/buscador.mjs)


// las partes (componentes/partes.ts): una por valor, con su ancho y su color; la que no pesa no se dibuja; sin nada, la
// franja vacía; lo escrito se escapa
{
    const p = partes({ accion: 'abrir', partes: [{ clave: 'inicio', valor: 30, tinta: 'carga-inicio', activa: true },
        { clave: 'nada', valor: 0, tinta: 'carga-hilos' }, { clave: 'leido', valor: 10, tinta: 'carga-leido', ayuda: '<b>' }] });
    assert.equal((p.match(/class="parte[ "]/g) ?? []).length, 2, 'una parte por valor que pesa');
    assert.ok(p.includes('flex-grow: 30; --parte: var(--carga-inicio)'), 'su ancho y su color');
    assert.ok(p.includes('class="parte activa"'), 'la abierta');
    assert.ok(p.includes('data-accion="abrir" data-id="leido"'), 'su clic');
    assert.ok(p.includes('&lt;b&gt;') && !p.includes('<b>'), 'lo escrito se escapa');
    assert.ok(partes({ partes: [] }).includes('partes vacia'), 'sin nada');
}



// 10. la sección de lista (componentes/seccion.ts): la banda de herramientas, la fila «nada calza» y el separador
{
    const { herramientas, separador } = await armar('seccion');
    assert.equal(separador(), '<div class="sep"></div>');
    const solo = herramientas({ grupo: 'g', placeholder: 'hilos', ayuda: 'a' });
    assert.match(solo, /^<div class="buscador-barra herram"><label class="buscador" title="hilos · a">.*<input class="buscar" type="text" data-grupo="g" placeholder=" " aria-label="hilos"/,
        'la barra del buscador, con su clase');
    assert.ok(solo.endsWith('</label></div><div class="vacia" data-grupo="g" hidden>nada calza</div>'), 'solo el buscador (sin herramientas), y su fila oculta');
    const sub = herramientas({ grupo: 'g', placeholder: 'hilos', ayuda: 'a', estilo: '--lugar: 3ch', extra: '<i></i>', orden: { opciones: [{ clave: 'x', icono: 'a', ayuda: 'x' }], activa: 'x' }, vacia: 'nada' });
    assert.ok(sub.startsWith('<div class="buscador-barra herram" style="--lugar: 3ch">'), 'con su estilo');
    assert.ok(sub.indexOf('class="buscador-herramientas"') > sub.indexOf('</label>'), 'el orden y lo extra, a la derecha, en sus herramientas');
    assert.ok(sub.includes('class="vacia" style="--lugar: 3ch" data-grupo="g" hidden>nada<'), 'la fila, igual');
    assert.ok(sub.indexOf('data-id="g:x"') > sub.indexOf('class="buscar"') && sub.indexOf('<i></i>') > sub.indexOf('data-id="g:x"'), 'buscador, orden y lo extra, en ese orden');
}

// 11. la ventana (componentes/ventana.ts): cabecera, campo, cuerpo y pie en ese orden, solo lo que se pide; la paleta
{
    const { ventana, paleta, pieVentana } = await armar('ventana');
    assert.equal(ventana({}), '<div class="ventana centrada"></div>', 'sin nada pedido, solo el marco');
    const v = ventana({ lugar: 'arriba', titulo: 'a<b', ayuda: 'x', campo: '<i id="c"></i>', cuerpo: '<i id="u"></i>', pie: pieVentana([{ texto: 'ok', tecla: '⏎', accion: 'ok' }]) });
    assert.ok(v.startsWith('<div class="ventana arriba">'), 'su lugar');
    assert.ok(v.includes('a&lt;b') && !v.includes('a<b'), 'lo escrito se escapa');
    const en = k => v.indexOf(k);
    assert.ok(en('ventana-titulo') < en('ventana-ayuda') && en('ventana-ayuda') < en('id="c"') && en('id="c"') < en('id="u"') && en('id="u"') < en('ventana-pie'), 'cabecera · campo · cuerpo · pie');
    assert.ok(v.includes('data-accion="ok"') && v.includes('class="boton-tecla">⏎') && v.includes('botonera'), 'el pie: la banda de botones, con su tecla y su acción');
    const p = paleta({ lugar: 'junto', filas: [{ titulo: 'uno' }, { titulo: 'dos' }], sel: 1, detalle: 'd' });
    assert.ok(/<div class="ventana-campo"><div class="buscador-barra">/.test(p) && p.includes('aria-label="opciones"')
        && (p.match(/class="item( |")/g) ?? []).length === 2, 'el campo, la barra de un buscador; y una fila por ítem');
    assert.equal((p.match(/class="item activa/g) ?? []).length, 1, 'una marcada');
    assert.ok(p.indexOf('uno') < p.indexOf('dos') && p.includes('ventana-detalle'), 'en orden, con su detalle');
    assert.ok(paleta({ filas: [], vacia: 'nada' }).includes('ventana-vacia">nada<'), 'sin filas, lo que dice');
}
// 12. el día en una línea (componentes/jornada.ts): qué dice a cada hora; sin reuniones, o con el día terminado, nada
{
    const { jornada, leer, texto, duracion, hora } = await armar('jornada');
    const hm = (h, m = 0) => h * 60 + m;
    const tramos = [
        { inicio: hm(9), fin: hm(9, 30), titulo: 'Daily', clase: 'reunion' },
        { inicio: hm(9, 30), fin: hm(11), titulo: 'Foco', clase: 'bloque' },
        { inicio: hm(11, 30), fin: hm(12, 30), titulo: 'Revisión <b>', clase: 'reunion' },
        { inicio: hm(15), fin: hm(16), titulo: 'Comité', clase: 'reunion' },
        { inicio: hm(16), fin: hm(16, 30), titulo: 'Llamada', clase: 'reunion' },
    ];
    const j = (ahora, ts = tramos) => ({ desde: hm(8, 30), hasta: hm(18), ahora, tramos: ts });
    // la unidad, pegada al número
    assert.equal(duracion(80), '1h 20'); assert.equal(duracion(40), '40min'); assert.equal(duracion(120), '2h'); assert.equal(duracion(65), '1h 05');
    assert.equal(hora(hm(9)), '9:00'); assert.equal(hora(hm(13, 5)), '13:05');
    // libre: el bloque propio no corta lo libre; lo que viene, hasta dos más
    let l = leer(j(hm(10, 10)));
    assert.equal(l.estado, 'libre'); assert.equal(l.dura, 80); assert.equal(l.siguiente.titulo, 'Revisión <b>');
    assert.deepEqual(l.resto.map(r => r.titulo), ['Comité', 'Llamada']);
    // en una reunión: lo que le queda y lo libre que sigue
    l = leer(j(hm(11, 45)));
    assert.equal(l.estado, 'reunion'); assert.equal(l.dura, 45); assert.equal(l.hasta, hm(12, 30)); assert.equal(l.libreDespues, 150);
    // pegadas: la que sigue empieza cuando termina
    l = leer(j(hm(15, 40)));
    assert.equal(l.siguiente.titulo, 'Llamada'); assert.equal(l.libreDespues, 0); assert.equal(l.hasta, hm(16));
    // las que se pisan son un solo rato ocupado
    l = leer(j(hm(9, 10), [...tramos, { inicio: hm(9, 15), fin: hm(10), titulo: 'Otra', clase: 'reunion' }]));
    assert.equal(l.hasta, hm(10));
    // temprano: lo libre hasta la primera
    assert.equal(leer(j(hm(7, 50))).dura, 70);
    // pasada la última, con la jornada andando: libre el resto del día; pasada también la jornada, nada
    assert.equal(leer(j(hm(17))).estado, 'fin');
    assert.equal(leer(j(hm(18, 10))), null);
    assert.equal(jornada(j(hm(18, 10))), '');
    // sin reuniones: nada
    assert.equal(leer(j(hm(10), tramos.filter(t => t.clase !== 'reunion'))), null);
    // el texto: cada parte con su clase (el ancho decide cuáles quedan), lo escrito escapado, y poco libre avisado
    const html = jornada(j(hm(10, 10)));
    assert.ok(html.startsWith('<div class="jornada libre">'), 'su estado');
    for (const c of ['j-que', 'j-dura libre', 'j-hasta', 'j-luego', 'j-mas', 'jornada-barra', 'j-hecho', 'j-tramo reunion pasado', 'j-tramo bloque', 'j-ahora']) assert.ok(html.includes(`class="${c}`), c);
    assert.ok(html.includes('>1h 20<') && html.includes('>11:30<'), 'cuánto y hasta cuándo');
    // la barra: ahora, a 100 de 570 minutos
    assert.ok(html.includes('class="j-ahora" style="inset-inline-start: 17.54%"'), 'ahora, en su lugar');
    assert.ok(html.includes('Revisión &lt;b&gt;') && !html.includes('<b>'), 'lo escrito se escapa');
    assert.ok(jornada(j(hm(11, 25))).includes('j-dura libre poco'), 'queda poco');
    // lo que la persona respondió a cada invitación: la rechazada no se dibuja ni cuenta; la aceptada, la tentativa y
    // la que organiza ella (sin respuesta) son reuniones; la sin responder también, solo con su borde y dicho en el texto
    const resp = [
        { inicio: hm(9), fin: hm(9, 30), titulo: 'Daily', clase: 'reunion', respuesta: 'aceptada' },
        { inicio: hm(10, 30), fin: hm(11), titulo: 'Trimestre', clase: 'reunion', respuesta: 'rechazada' },
        { inicio: hm(11, 30), fin: hm(12, 30), titulo: 'Diseño', clase: 'reunion', respuesta: 'tentativa' },
        { inicio: hm(14), fin: hm(15), titulo: 'Presentación', clase: 'reunion', respuesta: 'sin_responder' },
        { inicio: hm(15), fin: hm(16), titulo: 'Comité', clase: 'reunion', respuesta: '' },
    ];
    l = leer(j(hm(10, 10), resp));
    assert.equal(l.siguiente.titulo, 'Diseño', 'la rechazada no corta lo libre'); assert.equal(l.dura, 80);
    assert.deepEqual(l.resto.map(r => r.titulo), ['Presentación', 'Comité'], 'la rechazada no viene después; la sin responder, sí');
    l = leer(j(hm(11, 45), resp));
    assert.equal(l.estado, 'reunion', 'la tentativa es una reunión'); assert.equal(l.actual.titulo, 'Diseño');
    assert.equal(l.siguiente.titulo, 'Presentación', 'después de ella, la sin responder'); assert.equal(l.libreDespues, 90);
    l = leer(j(hm(13, 40), resp));
    assert.equal(l.estado, 'libre'); assert.equal(l.dura, 20, 'la sin responder corta lo libre'); assert.equal(l.siguiente.titulo, 'Presentación');
    assert.ok(texto(l).includes('Presentación<span class="j-sin"> (sin responder)</span>'), 'y el texto lo dice cuando es la próxima');
    l = leer(j(hm(14, 20), resp));
    assert.equal(l.estado, 'reunion', 'en una sin responder, en una reunión'); assert.equal(l.dura, 40); assert.equal(l.siguiente.titulo, 'Comité');
    assert.ok(texto(l).includes('en Presentación<span class="j-sin"> (sin responder)</span>'), 'y lo dice cuando es la de ahora');
    assert.ok(!texto(leer(j(hm(10, 10), resp))).includes('j-sin'), 'una aceptada o tentativa, sin marca');
    const conResp = jornada(j(hm(10, 10), resp));
    assert.equal((conResp.match(/class="j-tramo /g) ?? []).length, 4, 'la rechazada no se dibuja');
    assert.equal((conResp.match(/class="j-tramo reunion sin-responder"/g) ?? []).length, 1, 'la sin responder, una reunión con su marca');
    assert.equal((conResp.match(/class="j-tramo reunion/g) ?? []).length, 4, 'la aceptada, la tentativa, la que organiza y la sin responder');
    assert.ok(!conResp.includes('Trimestre'), 'ni en el globo');
    assert.ok(conResp.includes('Presentación (sin responder)') && conResp.includes('Diseño (tentativa)'), 'el globo dice cuáles no están firmes');
    assert.equal(leer(j(hm(10), resp.filter(t => t.respuesta === 'rechazada'))), null, 'solo rechazadas: nada');
    const juntas = [{ inicio: hm(12), fin: hm(13), titulo: 'Sin', clase: 'reunion', respuesta: 'sin_responder' },
        { inicio: hm(12), fin: hm(13), titulo: 'Con', clase: 'reunion', respuesta: 'aceptada' }];
    assert.equal(leer(j(hm(11), juntas)).siguiente.titulo, 'Con', 'a la misma hora, se nombra la que respondió');
    assert.equal(leer(j(hm(12, 10), juntas)).actual.titulo, 'Con', 'también cuando es la de ahora');
    assert.equal(leer(j(hm(10), resp.filter(t => t.respuesta === 'sin_responder'))).siguiente.titulo, 'Presentación', 'solo sin responder: la dice');
}
// 13. el día en la cabecera (web/jornada.ts): de la agenda de `telar hoy` a los tramos (una cita con otras personas es
// una reunión; sin gente ni dónde conectarse, un bloque propio; el almuerzo, rutina), y la jornada que abarca la barra
{
    const outfile = path.join(path.dirname(salida), 'web-jornada.cjs');
    await build({ entryPoints: [path.join(aqui, '..', 'src', 'web', 'jornada.ts')], bundle: true, platform: 'node', format: 'cjs', outfile, logLevel: 'warning' });
    const { tramosDe, abarca } = require(outfile);
    const medianoche = new Date(2026, 10, 17).getTime();
    const ev = (h1, h2, texto, gente, respuesta) => ({ texto, cuando: `2026-11-17T${h1}:00`, fin: `2026-11-17T${h2}:00`, asistentes: gente ? ['a@x'] : [],
        url: gente ? 'https://x' : '', ...(respuesta === undefined ? {} : { respuesta }) });
    const d = { fecha: '2026-11-17', agenda: [ev('07:30', '08:00', 'Temprano', true), ev('09:30', '11:00', 'Foco', false), ev('13:00', '14:00', 'Almuerzo', false), ev('18:10', '18:40', 'Tarde', true)] };
    const ts = tramosDe(d, medianoche);
    assert.deepEqual(ts.map(t => [t.titulo, t.clase, t.inicio, t.fin]), [['Temprano', 'reunion', 450, 480], ['Foco', 'bloque', 570, 660],
        ['Almuerzo', 'rutina', 780, 840], ['Tarde', 'reunion', 1090, 1120]], 'cada evento, con lo que es y sus minutos');
    assert.deepEqual(abarca(ts), { desde: 450, hasta: 1140 }, 'la jornada, estirada a la media hora por las reuniones de afuera');
    assert.deepEqual(abarca(ts.filter(t => t.clase !== 'reunion')), { desde: 510, hasta: 1080 }, 'sin reuniones afuera: de 8:30 a 18:00');
    assert.deepEqual(tramosDe({ ...d, agenda: null }, medianoche), [], 'sin calendario, nada');
    // la respuesta viaja hasta el tramo (sin ella, vacía); lo que no ocupa el tiempo no estira la jornada
    assert.deepEqual(ts.map(t => t.respuesta), ['', '', '', ''], 'sin respuesta en la agenda, vacía');
    const afuera = tramosDe({ ...d, agenda: [ev('07:30', '08:00', 'Temprano', true, 'rechazada'), ev('18:10', '18:40', 'Tarde', true, 'sin_responder'),
        ev('10:00', '11:00', 'Comité', true, 'tentativa')] }, medianoche);
    assert.deepEqual(afuera.map(t => [t.titulo, t.clase, t.respuesta]), [['Temprano', 'reunion', 'rechazada'], ['Comité', 'reunion', 'tentativa'],
        ['Tarde', 'reunion', 'sin_responder']], 'cada cita con su respuesta');
    assert.deepEqual(abarca(afuera), { desde: 510, hasta: 1140 }, 'una rechazada fuera de la jornada no la estira; una sin responder, sí');
}
// 14. la urgencia (vistas/dashboard/urgencia.ts): un hilo detenido > el peso que declara el agente > una persona espera >
// la fecha dura > el orden de hoy (vence hoy, o venció hace 30 días o menos > el plan la puso hoy > vence esta semana >
// lo demás; dentro, lo que vence antes y lo que espera hace más). Sin nada declarado, el orden de hoy. La deuda (vencida
// hace más de 30 días) no entra. Y lo declarado: cómo se lee de una línea [avance] y del resumen de una pregunta
{
    const outfile = path.join(path.dirname(salida), 'urgencia.cjs');
    await build({ entryPoints: [path.join(aqui, '..', 'src', 'vistas', 'dashboard', 'urgencia.ts')], bundle: true, platform: 'node', format: 'cjs', outfile, logLevel: 'warning' });
    const { NIVELES, nivel, comparar, ordenar, porque, cuando, delPlan, deEspera, dePendiente, esDeudaDe, ALGUIEN_ESPERA, CAMPOS, PIDES, declarado,
        declaradoEnResumen, declaradoDe, viaDe } = require(outfile);
    assert.deepEqual(NIVELES, ['espera', 'hoy', 'plan', 'semana', 'resto']);
    // el nivel del orden de hoy: el primero que cumple
    assert.equal(nivel({ espera: true, dias: 5, plan: true }), 'espera', 'un hilo detenido gana a todo');
    assert.equal(nivel({ dias: 0, plan: true }), 'hoy', 'vence hoy gana al plan');
    assert.equal(nivel({ dias: -3 }), 'hoy', 'lo vencido (sin ser deuda) también es para hoy');
    assert.equal(nivel({ dias: -30 }), 'hoy', 'vencida hace 30 días todavía no es deuda');
    assert.equal(nivel({ dias: 3, plan: true }), 'plan', 'el plan gana a la semana');
    assert.equal(nivel({ dias: 1 }), 'semana');
    assert.equal(nivel({ dias: 7 }), 'semana', 'siete días es esta semana, como el filtro de «tareas»');
    assert.equal(nivel({ dias: 8 }), 'resto');
    assert.equal(nivel({}), 'resto', 'sin señales: lo demás');
    assert.equal(nivel({ dias: null, desde: 1 }), 'resto');
    // la deuda no entra, salvo con estrella, si alguien espera (un hilo o una persona), con peso alto o con fecha dura
    assert.equal(nivel({ dias: -31 }), null, 'vencida hace más de 30 días: deuda');
    assert.equal(nivel({ dias: -31, plan: true }), null, 'ni el plan la saca de la deuda');
    assert.equal(nivel({ dias: -31, peso: 'medio' }), null, 'ni un peso medio');
    assert.equal(nivel({ dias: -31, estrella: true }), 'hoy', 'con estrella (la pone la persona), entra');
    assert.equal(nivel({ dias: -90, espera: true }), 'espera', 'un hilo detenido no se esconde');
    for (const s of [{ persona: 'el colegio' }, { peso: 'alto' }, { dura: 3 }]) assert.equal(esDeudaDe({ dias: -31, ...s }), false, JSON.stringify(s));
    assert.equal(esDeudaDe({ dias: -31 }), true);
    assert.equal(esDeudaDe({ dias: -31, estrella: true }), false);
    // sin nada declarado, el orden de hoy: lo que vence antes; a igual fecha, lo que espera hace más; lo que no lo dice, al final
    assert.ok(comparar({ dias: -3 }, { dias: 0 }) < 0, 'lo más vencido primero');
    assert.ok(comparar({ dias: 2, desde: 100 }, { dias: 5, desde: 1 }) < 0, 'en la semana, lo que vence antes aunque sea más nuevo');
    assert.ok(comparar({ espera: true, desde: 1 }, { espera: true, desde: 2 }) < 0, 'quien espera hace más, primero');
    assert.ok(comparar({ desde: 5 }, {}) < 0, 'sin desde, al final');
    assert.ok(comparar({ plan: true, dias: 4 }, { plan: true }) < 0, 'en el plan, lo que tiene fecha antes');
    assert.equal(comparar({ dias: 2, desde: 3 }, { dias: 2, desde: 3 }), 0);
    // con lo declarado: el peso primero (sin peso, como medio), después una persona, después la fecha dura más próxima
    assert.ok(comparar({ peso: 'alto' }, { dias: -20 }) < 0, 'el peso alto gana a lo vencido');
    assert.ok(comparar({ espera: true }, { peso: 'alto' }) < 0, 'un hilo detenido gana al peso');
    assert.ok(comparar({}, { peso: 'bajo', dias: -5 }) < 0, 'sin peso cuenta como medio: antes que uno bajo');
    assert.equal(comparar({ peso: 'medio', desde: 1 }, { desde: 1 }), 0, 'medio y sin peso empatan');
    assert.ok(comparar({ persona: 'el colegio' }, { dias: 0, plan: true }) < 0, 'una persona espera, antes que lo de hoy');
    assert.ok(comparar({ peso: 'alto' }, { persona: 'el colegio' }) < 0, 'el peso antes que la persona');
    assert.ok(comparar({ dura: 5 }, { dias: -10 }) < 0, 'una fecha dura antes que lo vencido sin dura');
    assert.ok(comparar({ dura: 2 }, { dura: 5 }) < 0, 'la dura más próxima primero');
    assert.ok(comparar({ persona: 'x', dura: 9 }, { dura: 1 }) < 0, 'la persona antes que la fecha dura');
    // ordenar: sin la deuda, estable en lo que empata
    const cosas = [
        { n: 'vieja sin nada', s: { desde: 1 } }, { n: 'deuda', s: { dias: -45 } }, { n: 'semana', s: { dias: 4 } },
        { n: 'plan', s: { plan: true } }, { n: 'hoy', s: { dias: 0 } }, { n: 'espera', s: { espera: true, desde: 50 } },
        { n: 'vencida', s: { dias: -2 } }, { n: 'nueva sin nada', s: { desde: 9 } }, { n: 'empata a', s: {} }, { n: 'empata b', s: {} },
    ];
    assert.deepEqual(ordenar(cosas, c => c.s).map(c => c.n),
        ['espera', 'vencida', 'hoy', 'plan', 'semana', 'vieja sin nada', 'nueva sin nada', 'empata a', 'empata b'], 'sin nada declarado, el orden de hoy');
    const declaradas = [{ n: 'bajo', s: { peso: 'bajo', dias: -3 } }, { n: 'persona', s: { persona: 'p' } }, { n: 'vencida', s: { dias: -2 } },
        { n: 'alto', s: { peso: 'alto', desde: 5 } }, { n: 'dura', s: { dura: 4 } }, { n: 'alto viejo', s: { peso: 'alto', desde: 1 } }];
    assert.deepEqual(ordenar(declaradas, c => c.s).map(c => c.n), ['alto viejo', 'alto', 'persona', 'dura', 'vencida', 'bajo']);
    // por qué está ahí: lo que va al final de su fila. Color solo un hilo detenido, una persona que espera hoy y una fecha dura
    const AHORA = Date.parse('2026-11-17T12:00:00');  // un martes
    assert.deepEqual(porque({ espera: true }, AHORA), { nivel: 'espera', texto: 'te espera', tono: 'espera' });
    assert.deepEqual(porque({ dias: 0 }, AHORA), { nivel: 'hoy', texto: 'vence hoy' }, 'vence hoy, sin color');
    assert.deepEqual(porque({ dias: -3 }, AHORA), { nivel: 'hoy', texto: 'venció el 14-nov' }, 'lo vencido dice su fecha, sin rojo');
    assert.deepEqual(porque({ plan: true }, AHORA), { nivel: 'plan', texto: 'el plan: hoy' });
    assert.equal(porque({ dias: 1 }, AHORA).texto, 'vence mañana');
    assert.equal(porque({ dias: 3 }, AHORA).texto, 'vence el vie');
    assert.equal(porque({ dias: 7 }, AHORA).texto, 'vence el 24-nov', 'a una semana, la fecha (el día de la semana sería el de hoy)');
    assert.deepEqual(porque({ desde: AHORA - 6 * 86400000 }, AHORA), { nivel: 'resto', texto: 'hace 6d', tono: 'tenue' });
    assert.equal(porque({}, AHORA).texto, 'sin fecha');
    assert.equal(porque({ dias: -40 }, AHORA), null, 'la deuda no tiene porqué: no entra');
    assert.deepEqual(porque({ persona: 'el colegio', dias: 0 }, AHORA), { nivel: 'hoy', texto: 'el colegio espera hoy', tono: 'espera' });
    assert.deepEqual(porque({ persona: 'el colegio', dias: 4 }, AHORA), { nivel: 'semana', texto: 'espera el colegio' }, 'otro día, sin color');
    assert.deepEqual(porque({ persona: 'el colegio', dura: 0 }, AHORA).tono, 'espera', 'con la fecha dura hoy, también');
    assert.deepEqual(porque({ dura: 2 }, AHORA), { nivel: 'resto', texto: 'vence el jue', tono: 'atencion' }, 'una fecha dura, siempre con color');
    assert.deepEqual(porque({ dura: 0 }, AHORA).tono, 'peligro');
    assert.deepEqual(porque({ dura: -1, dias: -1 }, AHORA), { nivel: 'hoy', texto: 'venció el 16-nov', tono: 'peligro' });
    assert.deepEqual([cuando(0, AHORA), cuando(1, AHORA), cuando(6, AHORA), cuando(-1, AHORA), cuando(20, AHORA)], ['hoy', 'mañana', 'el lun', 'el 16-nov', 'el 7-dic']);
    // lo que el plan pone hoy: sus tácticos de hoy y las tareas de los bloques de su agenda, en mayúsculas
    assert.deepEqual([...delPlan({ tacticos: { hoy: [{ ref: 't28' }, 'T42', { texto: 'sin ref' }], no_hoy: [{ ref: 'T9' }] },
        agenda: [{ titulo: 'Foco', tareas: ['T44', ''] }, { titulo: 'Daily' }, { tareas: 'T1' }] })].sort(), ['T28', 'T42', 'T44']);
    assert.deepEqual([...delPlan(undefined)], [], 'sin plan, nada');
    assert.deepEqual([...delPlan({ tacticos: 'nada', agenda: {} })], [], 'un plan con otra forma: nada, sin romperse');
    // lo declarado: los nombres en un solo lugar
    assert.deepEqual(CAMPOS, { pide: 'pide', peso: 'peso', persona: 'espera', dura: 'dura', opciones: 'opciones', artefacto: 'artefacto' });
    // las opciones de una decisión, separadas por « | », la recomendada con «*»; lo que dejó hecho, una ruta o un enlace
    assert.deepEqual(declarado('pide=decidir · opciones=el 12% | un 8%* | consultarlo · artefacto=casa/cotizacion.md · falta: ¿cuál?'),
        { pide: 'decidir', opciones: [{ texto: 'el 12%' }, { texto: 'un 8%', recomendada: true }, { texto: 'consultarlo' }], artefacto: 'casa/cotizacion.md', resto: 'falta: ¿cuál?' });
    assert.equal(declarado('opciones= | * · x').opciones, undefined, 'sin opciones de verdad, nada');
    // en una línea [avance]: el formato de los agentes, con la marca delante o sin ella (como lo da `telar esperas`)
    const linea = 'preparado: pide=aprobar · peso=alto (renueva el contrato) · 17-nov: la propuesta está lista · falta: ¿la mando?';
    assert.deepEqual(declarado(linea), { pide: 'aprobar', peso: 'alto', porque: 'renueva el contrato', resto: '17-nov: la propuesta está lista · falta: ¿la mando?' });
    assert.deepEqual(declarado(linea.replace('preparado: ', '')), declarado(linea), 'sin la marca, igual');
    assert.match(linea, /^(\S+): pide=([\w-]+) · peso=(alto|medio|bajo)(?: \(([^)]*)\))? · /, 'la línea calza con la regex del formato acordado');
    assert.deepEqual(PIDES, ['decidir', 'aprobar', 'hacer-tu', 'cerrar'], 'una por vía');
    assert.deepEqual(declarado('cerrar:hecha: pide=cerrar · peso=bajo · ya llegó'), { pide: 'cerrar', peso: 'bajo', resto: 'ya llegó' }, 'la marca con dos puntos');
    assert.equal(declarado('pide=hacer-tu · la firma').pide, 'hacer-tu', 'el valor puede llevar guion');
    assert.equal(declarado('pide=hacer · x').pide, undefined, 'lo de antes (hacer, delegar, esperar) ya no es una vía');
    assert.deepEqual(declarado('pide=decidir · peso=medio · espera=el colegio · dura=2026-11-20 · ¿12%?'),
        { pide: 'decidir', peso: 'medio', persona: 'el colegio', dura: '2026-11-20', resto: '¿12%?' }, 'quién espera y la fecha dura (provisorios)');
    assert.deepEqual(declarado('peso=alto · pide=hacer-tu · lo demás'), { peso: 'alto', pide: 'hacer-tu', resto: 'lo demás' }, 'en cualquier orden');
    assert.deepEqual(declarado('pide=quizás · peso=enorme · dura=pronto · resto'), { resto: 'resto' }, 'lo que no se entiende no cuenta, pero no corta');
    assert.deepEqual(declarado('16-nov 11:00: sin cambios · falta: ¿la cierro?'), { resto: '16-nov 11:00: sin cambios · falta: ¿la cierro?' }, 'sin nada declarado: todo es resto');
    assert.deepEqual(declarado('nota: x=1 · y'), { resto: 'nota: x=1 · y' }, 'un clave=valor que no es de los nuestros no es lo declarado');
    assert.deepEqual(declarado(''), { resto: '' });
    // en el resumen de una pregunta: «peso: alto (porqué)» en las primeras líneas
    assert.deepEqual(declaradoEnResumen('peso: alto (cierra el trimestre)\nLa reseña está lista.'), { peso: 'alto', porque: 'cierra el trimestre', resto: 'La reseña está lista.' });
    assert.deepEqual(declaradoEnResumen('Nota: algo\npeso: alto'), { resto: 'Nota: algo\npeso: alto' }, 'solo al principio');
    // de una espera: de su línea [avance] (campos.texto) o del resumen de su pregunta; lo demás no declara nada
    const e = (direccion, clase, desde, campos = {}, mas = {}) => ({ direccion, tipo: direccion.split(':')[0], clase, desde, titulo: '', resumen: '', enlaces: [], campos, ...mas });
    assert.equal(declaradoDe(e('tarea:T1', 'avance:preparado', '', { texto: 'peso=alto · listo' })).peso, 'alto');
    assert.equal(declaradoDe(e('pregunta:r/x', 'decide', '', { secciones: { resumen: 'peso: bajo\nx' } }, { resumen: 'x' })).peso, 'bajo', 'del resumen entero');
    assert.equal(declaradoDe(e('pregunta:r/x', 'decide', '', {}, { resumen: 'peso: medio\nx' })).peso, 'medio', 'o del corto');
    assert.equal(declaradoDe(e('mensaje:m', 'retenido', '', { texto: 'peso=alto · x' })).peso, undefined, 'un retenido no declara');
    // la vía: la que declara el agente; sin declararla, solo lo que su forma ya dice (un cierre propuesto, una pregunta del
    // módulo); lo demás no se adivina (null: sin clasificar)
    assert.deepEqual(['avance:pregunta', 'avance:preparado', 'avance:cerrar', 'avance:choca', 'decide', 'archivar'].map(c => viaDe(e('x:1', c, ''))),
        [null, null, 'cerrar', null, 'decidir', null]);
    assert.equal(viaDe(e('tarea:T1', 'avance:preparado', '', { texto: 'pide=decidir · falta: ¿a o b?' })), 'decidir', 'lo declarado manda');
    assert.equal(viaDe(e('tarea:T1', 'avance:cerrar', '', { texto: 'pide=aprobar · x' })), 'aprobar');
    // las señales de una espera: un hilo espera si es un hilo detenido o un retenido; lo que un agente dejó, no
    assert.deepEqual([...ALGUIEN_ESPERA], ['permiso', 'pregunta', 'retenido']);
    const plan = new Set(['T28']);
    assert.equal(deEspera(e('permiso:Faro', 'permiso', '2026-11-17T11:00:00'), plan, AHORA).espera, true);
    assert.equal(deEspera(e('mensaje:m1', 'retenido', '2026-11-17T11:00:00'), plan, AHORA).espera, true);
    assert.equal(deEspera(e('tarea:T3', 'avance:pregunta', '2026-11-17'), plan, AHORA).espera, false, 'una pregunta en una tarea no bloquea a nadie');
    assert.equal(deEspera(e('pregunta:casa/x', 'decide', '2026-11-17'), plan, AHORA).espera, false);
    const t28 = deEspera(e('tarea:t28@servidor', 'avance:preparado', '2026-11-16T09:00:00', { vence: '2026-11-20', prioridad: 0 }), plan, AHORA);
    assert.deepEqual(t28, { espera: false, dias: 3, plan: true, desde: Date.parse('2026-11-16T09:00:00') }, 'su vence, el plan por su código, desde cuándo');
    assert.equal(deEspera(e('tarea:T5', 'avance:pregunta', ''), plan, AHORA).desde, null, 'sin desde: no se sabe');
    const conTodo = deEspera(e('tarea:T6', 'avance:pregunta', '2026-11-16', { texto: 'pide=decidir · peso=alto (x) · espera=el colegio · dura=2026-11-19 · ¿sí?' }), plan, AHORA);
    assert.deepEqual([conTodo.peso, conTodo.persona, conTodo.dura], ['alto', 'el colegio', 2], 'lo declarado: el peso, quién espera y en cuántos días es la fecha dura');
    // la prioridad de una tarea ni la urgencia que declara una pregunta saltan la fila: solo el peso
    const declarada = e('pregunta:casa/nueva', 'decide', '2026-11-17T10:00:00', { urgencia: 'alta' });
    const vieja = e('tarea:T7', 'avance:pregunta', '2026-11-10T10:00:00', { prioridad: 1 });
    assert.deepEqual(ordenar([declarada, vieja], x => deEspera(x, plan, AHORA)).map(x => x.direccion), ['tarea:T7', 'pregunta:casa/nueva']);
    const pesada = e('pregunta:casa/pesada', 'decide', '2026-11-17T10:00:00', {}, { resumen: 'peso: alto (x)\ny' });
    assert.deepEqual(ordenar([vieja, pesada], x => deEspera(x, plan, AHORA)).map(x => x.direccion), ['pregunta:casa/pesada', 'tarea:T7'], 'el peso, sí');
    // las de un pendiente (`telar hoy`): sus días, el plan por su código o su id, su estrella
    const pend = (ref, id, dias, estrella = false) => ({ ref, dias, fila: { id, estrella }, texto: '', hilo: '', cuando: '', enCurso: false, avance: '', urgencia: 0, urgente: false });
    assert.deepEqual(dePendiente(pend('T28', 'x', 2), plan), { dias: 2, plan: true, estrella: false, desde: null });
    assert.equal(dePendiente(pend('', 't28', null), plan).plan, true, 'por su id');
    assert.equal(nivel(dePendiente(pend('T1', 'T1', -60, true), plan)), 'hoy', 'con estrella, la deuda entra');
}
// 15. Táctica (componentes/tactica.ts): las cuatro vías (cada una con su tecla) y lo sin clasificar, por cuenta (la cabecera
// y la primera, o todas desplegada), con su tope y «+N cuentas más»; lo de cada vía bajo su fila (las opciones, lo que dejó
// hecho, la prueba); lo contestado que espera al agente (con la próxima pasada y «revisar ya»); el único número; Hacer, lo
// libre, sin plan, las disposiciones y el pie
{
    const T = await armar('tactica');
    const { tactica, barraTactica, porDecidir, queCabe, filaDecision, filaCuenta, filaContestada, filaQuehacer, piezaPeso, TOPE_DECIDIR, TOPE_HACER,
        TOPE_CONTESTADAS, CONTESTADAS, DISPOSICIONES, VIAS, SIN_CLASIFICAR, minutos } = T;
    assert.equal(TOPE_DECIDIR, 3, 'tres cuentas por vía');
    assert.equal(TOPE_HACER, 3);
    assert.deepEqual(DISPOSICIONES.map(d => d.clave), ['columna', 'lado', 'franja']);
    assert.deepEqual(VIAS.map(v => `${v.clave}:${v.tecla}`), ['decidir:1', 'aprobar:2', 'cerrar:3'], 'las tres vías, cada una con su tecla');
    assert.equal(`${T.VIA_HACER.clave}:${T.VIA_HACER.tecla}`, 'hacer-tu:4', 'lo que pide hacer, la 4: va en Hacer');
    const d = (i, mas = {}) => ({ id: `tarea:T${i}`, titulo: `decisión ${i}`, porque: { texto: 'vence hoy' }, ...mas });
    const cu = (i, n = 1, mas = {}) => ({ clave: `casa/c${i}`, nombre: `cuenta ${i}`, decisiones: Array.from({ length: n }, (_, j) => d(i * 10 + j)), ...mas });
    const vias = (decidir = [], resto = {}) => [...VIAS.map(v => ({ clave: v.clave, cuentas: v.clave === 'decidir' ? decidir : resto[v.clave] ?? [] })),
        { clave: SIN_CLASIFICAR, cuentas: resto[SIN_CLASIFICAR] ?? [] }];
    const q = (i, mas = {}) => ({ tipo: 'tarea', id: `tarea:T${50 + i}`, titulo: `tarea ${i}`, porque: { texto: 'el plan: hoy' }, ...mas });
    const ahora = { tipo: 'reunion', titulo: 'Comité', cuando: '15:00–16:00', queda: 40, que: 'se decide: el presupuesto', datos: [{ texto: '4 personas' }] };
    const resto = [{ clave: 'tareas', nombre: 'tareas', cuenta: 54 }, { clave: 'correo', nombre: 'correos', cuenta: 0 }];
    const base = { ahora, vias: vias([cu(1, 2), cu(2)]), hacer: [q(1)], resto };
    const cuenta = (html, clase) => html.split(`class="item ${clase}`).length - 1;
    // las vías: cada una su bloque con su cabecera (cuántas y su tecla: un clic la recorre); vacía, solo la cabecera; lo sin
    // clasificar, solo si hay, al final y sin tecla
    const lado = tactica(base);
    assert.match(lado, /<section class="tac-bloque tac-via tac-via-decidir"><div class="tac-cab tac-via-cab" data-accion="tactica-via" data-valor="decidir"[^>]*>.*· 3<\/span><span class="tac-tope tac-tecla">1<\/span>/s);
    assert.match(lado, /tac-via tac-via-aprobar vacia"><div class="tac-cab tac-via-cab" title="[^"]*"><span class="tac-nombre">aprobar<\/span><span class="tac-cuantas">· nada/, 'vacía: sin clic');
    assert.ok(!lado.includes('tac-via-sin-clasificar'), 'sin nada sin clasificar, no se ve');
    const sin = tactica({ ...base, vias: vias([], { [SIN_CLASIFICAR]: [cu(7)] }) });
    assert.match(sin, /tac-via-sin-clasificar.*sin clasificar<\/span><span class="tac-cuantas">· 1<\/span><\/div>/s, 'sin tecla');
    assert.ok(lado.indexOf('tac-via-decidir') < lado.indexOf('tac-via-aprobar') && lado.indexOf('tac-via-aprobar') < lado.indexOf('tac-via-cerrar'), 'en su orden');
    assert.ok(!lado.includes('tac-via-hacer-tu'), 'lo que pide hacer no es una vía');
    // Hacer: primero lo que un agente pide que hagas, por cuenta y con su tecla; después lo de hoy, bajo su cabecera
    const conPedido = tactica({ ...base, hacerTu: [cu(8, 2)] });
    const hc = conPedido.slice(conPedido.indexOf('tac-hacer'));
    assert.match(hc, /^tac-hacer"><div class="tac-cab tac-via-cab" data-accion="tactica-via" data-valor="hacer-tu"[^>]*><span class="tac-nombre">hacer<\/span><span class="tac-cuantas">· 2 te piden<\/span><span class="tac-tope tac-tecla">4</);
    assert.ok(hc.indexOf('data-valor="hacer-tu|casa/c8"') < hc.indexOf('tac-hoy') && hc.indexOf('tac-hoy') < hc.indexOf('tarea 1'), 'lo pedido, después lo de hoy');
    assert.ok(!lado.includes('tac-hoy') && lado.includes('<span class="tac-tope">hasta 3</span>'), 'sin nada pedido, Hacer como siempre');
    // el tope: tres cuentas por vía, cada una con su primera; las demás en «+N cuentas más»
    const muchas = tactica({ ...base, vias: vias(Array.from({ length: 5 }, (_, i) => cu(i, 2))), hacer: Array.from({ length: 5 }, (_, i) => q(i)) });
    assert.equal(cuenta(muchas, 'submenu tac-cuenta'), 3, 'hasta tres cuentas');
    assert.equal(cuenta(muchas, 'tac-decision'), 3, 'de cada una, la primera');
    assert.equal(cuenta(muchas, 'tac-quehacer'), 3, 'hasta tres por hacer');
    assert.match(muchas, /data-accion="tactica-todo" data-valor="decidir".*\+2 cuentas más/s);
    assert.match(muchas, /data-accion="tactica-todo" data-valor="hacer".*\+2 más/s, '+2 más por hacer');
    assert.ok(!tactica(base).includes('más</span>'), 'bajo el tope, sin «+N más»');
    // una cuenta: su cabecera (un submenú con su nombre y cuántas), y debajo la primera; desplegada (`<vía>|<cuenta>`), todas
    assert.match(lado, /<div class="tac-grupo"><div class="item submenu tac-cuenta" data-accion="tactica-cuenta" data-valor="decidir\|casa\/c1".*cuenta 1<\/span> <span class="item-sufijo tono-tenue">· 2<\/span>/s);
    assert.ok(lado.includes('decisión 10') && !lado.includes('decisión 11'), 'plegada, solo la primera');
    assert.ok(tactica({ ...base, abiertas: ['decidir|casa/c1'] }).includes('decisión 11'), 'desplegada, todas');
    assert.match(filaCuenta(cu(1, 2), false, 'aprobar'), /data-accion="tactica-contestar" data-valor="cuenta:aprobar\|casa\/c1"/, 'contestarlas una tras otra');
    assert.match(filaCuenta(cu(2)), /^<div class="item submenu tac-cuenta" data-accion="tactica-contestar" data-valor="tarea:T20"/, 'con una sola, un clic la contesta');
    assert.match(filaCuenta({ clave: '', nombre: 'sin cuenta', decisiones: [d(1)] }), /tac-cuenta sin-cuenta/);
    // los hilos detenidos van arriba de las vías, en vivo, con su clase
    const conVivo = tactica({ ...base, vivo: [d(99, { palabra: 'permiso', tono: 'espera', porque: { texto: 'te espera', tono: 'espera' }, edad: '4m' })] });
    assert.ok(conVivo.indexOf('tac-vivo') < conVivo.indexOf('tac-via-decidir') && conVivo.includes('item-prefijo tono-espera">permiso'), 'el hilo detenido, primero');
    // cada fila: abre «Contestar», lo que hay que decidir y su porqué; sin la palabra de su clase (la dice la vía)
    const f = filaDecision(d(9, { edad: '2h', porque: { texto: 'te espera', tono: 'espera' } }), 'decidir');
    assert.match(f, /^<div class="item tac-decision" data-accion="tactica-contestar" data-valor="tarea:T9"/);
    assert.ok(!f.includes('item-prefijo'), 'sin prefijo');
    assert.match(f, /<span class="tac-porque tono-espera">te espera<\/span><span class="tac-edad"> · 2h<\/span>/, 'si un hilo espera, también hace cuánto');
    assert.match(filaDecision(d(9)), /<span class="tac-porque">vence hoy<\/span>/, 'sin tono: el de siempre (sin color)');
    // de una tarea, lo de su fila antes de «abrirla donde vive» (otra fecha)
    const conAcciones = filaDecision(d(9, { acciones: [{ accion: 'tactica-fecha', icono: 'F', datos: { valor: 'v' }, ayuda: 'otra fecha' }] }), 'decidir');
    assert.ok(conAcciones.indexOf('data-accion="tactica-fecha"') < conAcciones.indexOf('data-accion="tactica-ver"'), 'la fecha, y abrirla');
    // lo de cada vía: decidir, sus opciones con la recomendada; aprobar, lo que dejó hecho y enviar, editar o descartar;
    // hacer tú, el tamaño delante; cerrar, cómo delante y su prueba con confirmar
    const op = filaDecision(d(3, { opciones: [{ id: 'a', texto: 'En el boletín', recomendada: true }, { id: 'b', texto: 'En la página' }] }), 'decidir');
    assert.match(op, /tac-detalle tac-opciones.*class="tac-accion recomendada" data-accion="tactica-opcion" data-valor="\[&quot;tarea:T3&quot;,&quot;a&quot;\]".*En el boletín <span class="tac-reco">recomendada/s);
    assert.ok(!filaDecision(d(3), 'decidir').includes('tac-detalle'), 'sin opciones, nada debajo');
    const ap = filaDecision(d(4, { artefacto: { nombre: 'presupuesto.md', direccion: 'archivo:casa/presupuesto.md' } }), 'aprobar');
    assert.match(ap, /tac-detalle tac-aprobar.*data-accion="tactica-ver" data-valor="archivo:casa\/presupuesto.md".*presupuesto.md.*>enviar<.*>editar<.*>descartar</s);
    assert.ok(!filaDecision(d(4), 'aprobar').includes('tac-artefacto') && filaDecision(d(4), 'aprobar').includes('>enviar<'), 'sin lo hecho a la vista, igual se aprueba');
    assert.match(filaDecision(d(5, { tamano: 'rapida' }), 'hacer-tu'), /item-prefijo tono-tenue">rápida<\/span> <span class="item-titulo">decisión 5/);
    const ce = filaDecision(d(6, { como: 'hecha', prueba: 'llegaron ayer' }), 'cerrar');
    assert.match(ce, /item-prefijo tono-tenue">hecha<.*tac-detalle tac-cerrar"><span class="tac-prueba"[^>]*>llegaron ayer<\/span>.*data-accion="tactica-cerrar" data-valor="tarea:T6"/s);
    // el peso: un círculo chico en la primera ranura, sin color (alto lleno, medio a medias, bajo un aro); sin peso, nada
    assert.deepEqual(['alto', 'medio', 'bajo'].map(n => piezaPeso({ nivel: n }).circulo), [{ tam: 'chico', lleno: 1 }, { tam: 'chico', lleno: .5 }, { tam: 'chico', lleno: 0 }]);
    assert.equal(piezaPeso({ nivel: 'alto', porque: 'el pedido del año' }).ayuda, 'peso alto: el pedido del año');
    assert.equal(piezaPeso({ nivel: 'alto' }).tono, undefined, 'sin color: el color es para la urgencia');
    assert.equal(piezaPeso(undefined), null);
    // lo contestado que espera al agente: la tarea, lo que se contestó y cuándo; un aro violeta (le toca al agente) y, al
    // final y siempre a la vista, «revisar ya» en violeta. Un clic en la fila la abre donde vive
    const k = (i, mas = {}) => ({ id: `tarea:T${i}`, titulo: `tarea ${i}`, respuesta: `dije ${i}`, cuando: '11:20', ...mas });
    const fc = filaContestada(k(1), 'Avances');
    assert.match(fc, /^<div class="item tac-contestada" data-accion="tactica-ver" data-valor="tarea:T1"/);
    assert.match(fc, /<span class="item-ranura tono-agente" title="contestada: le toca al agente"><span class="circulo[^"]*" style="--lleno: 0%">/, 'un aro violeta');
    assert.match(fc, /item-titulo">tarea 1<\/span> <span class="item-sufijo tono-tenue">· dije 1<\/span>.*item-meta"[^>]*>11:20</s, 'la tarea, lo contestado y la hora');
    assert.match(fc, /<span class="item-accion cuadrada tono-agente" data-accion="tactica-revisar" data-valor="tarea:T1" title="revisar ya: encargársela a Avances ahora, sin esperar la próxima pasada">/,
        'revisar ya: un ícono violeta, fijo, con su globo');
    assert.ok(!fc.includes('item-acciones'), 'nada que aparezca solo al pasar el mouse');
    // encargada: a medias, la hora en violeta, y «revisar ya» apagado (no se encarga dos veces seguidas); en camino, gira;
    // si no salió, un aro rojo y se puede volver a apretar
    const enc = filaContestada(k(2, { encargada: '11:42' }));
    assert.match(enc, /item-ranura tono-agente" title="encargada a las 11:42: el agente la tiene"><span class="circulo[^"]*" style="--lleno: 50%">/);
    assert.match(enc, /item-meta tono-agente"[^>]*>encargada 11:42</);
    assert.match(enc, /item-accion cuadrada tono-tenue" data-accion="tactica-revisar"[^>]*title="ya se la encargaste a las 11:42: no se encarga dos veces seguidas"/);
    assert.match(filaContestada(k(3, { encargando: true })), /class="circulo[^"]* mov-gira".*item-meta tono-tenue">encargando</s);
    const fallo = filaContestada(k(4, { fallo: 'sin bus' }));
    assert.match(fallo, /item-ranura tono-peligro" title="«revisar ya» no salió: sin bus".*item-meta tono-peligro" title="sin bus">no salió<.*tono-agente" data-accion="tactica-revisar"/s);
    // el grupo: al final de las vías, con cuántas y la próxima pasada (su color si importa); hasta el tope, y lo demás al desplegar
    const pasada = { texto: 'próxima pasada 13:00', ayuda: 'la próxima vez que corre «avanzar»' };
    const conC = tactica({ ...base, contestadas: [k(1), k(2)], pasada });
    assert.match(conC, /<section class="tac-bloque tac-contestadas"><div class="tac-cab tac-contestadas-cab"[^>]*><span class="tac-nombre">contestadas<\/span><span class="tac-cuantas">· 2 esperando al agente<\/span><span class="tac-tope tac-pasada" title="la próxima vez que corre «avanzar»">próxima pasada 13:00<\/span><\/div>/);
    assert.ok(conC.indexOf('tac-via-cerrar') < conC.indexOf('tac-contestadas') && conC.indexOf('tac-contestadas') < conC.indexOf('tac-hacer'), 'al final de las vías');
    assert.match(tactica({ ...base, contestadas: [k(1)], pasada: { texto: 'pasando ahora', tono: 'agente', ayuda: 'x' } }), /tac-tope tac-pasada tono-agente"/);
    assert.ok(!tactica({ ...base, contestadas: [k(1)] }).includes('tac-pasada'), 'sin leer la pasada, no dice nada');
    assert.ok(!lado.includes('tac-contestadas'), 'sin nada contestado, no se ve');
    const siete = Array.from({ length: TOPE_CONTESTADAS + 2 }, (_, i) => k(i));
    assert.equal(cuenta(tactica({ ...base, contestadas: siete }), 'tac-contestada'), TOPE_CONTESTADAS);
    assert.match(tactica({ ...base, contestadas: siete }), new RegExp(`data-accion="tactica-cuenta" data-valor="${CONTESTADAS}".*\\+2 más`, 's'));
    const todas = tactica({ ...base, contestadas: siete, abiertas: [CONTESTADAS] });
    assert.equal(cuenta(todas, 'tac-contestada'), TOPE_CONTESTADAS + 2, 'desplegadas, todas');
    assert.match(todas, /data-valor="contestadas".*>menos</s);
    // el único número: todo lo de todas las vías y los hilos detenidos
    assert.equal(porDecidir(vias([cu(1, 3)], { cerrar: [cu(2)], [SIN_CLASIFICAR]: [cu(3, 2)] }), [d(1)]), 7, 'lo que pide hacer no cuenta: no se decide');
    assert.match(barraTactica(base).resumenHtml, /<span class="tac-numero tono-espera"[^>]*>3<\/span> por decidir/);
    assert.equal(barraTactica({ ...base, vias: vias() }).resumenHtml, 'nada por decidir', 'sin nada, sin número');
    assert.match(tactica({ ...base, vias: vias() }), /tac-nada.*nada por decidir/s, 'lo dice en una fila');
    // Hacer: una reunión con su hora y lo que pide; una tarea con su tamaño delante (no se corta con el título)
    const reunion = filaQuehacer({ tipo: 'reunion', id: 'evento:15:00', titulo: 'Comité', hora: '15:00', nota: 'prepararla' });
    assert.match(reunion, /data-accion="tactica-evento".*item-prefijo tono-acento">15:00<\/span> <span class="item-titulo">Comité/s);
    assert.match(reunion, /item-meta tono-atencion">prepararla/, 'lo que pide, al final');
    assert.match(filaQuehacer(q(1, { tamano: 'rapida' })), /item-prefijo tono-tenue">rápida<\/span> <span class="item-titulo">tarea 1/);
    assert.match(filaQuehacer(q(1, { tamano: 'larga' })), /item-prefijo tono-tenue">larga</);
    // sin plan, lo dice
    assert.match(tactica({ ...base, sinPlan: true }), /tac-sin-plan.*sin plan de hoy/s);
    assert.ok(!tactica({ ...base, sinPlan: true }).includes('tactica-planear'), 'sin pestaña del plan, la línea no lleva a ninguna parte');
    assert.ok(!tactica(base).includes('sin plan de hoy'));
    // las disposiciones: en columna y lado a lado, Ahora con su cabecera y su ficha (una tarjeta); en la franja, una línea
    // que se abre
    assert.match(tactica({ ...base, disposicion: 'columna' }), /^<div class="tactica disp-columna">/);
    assert.match(lado, /^<div class="tactica disp-lado"><section class="tac-bloque tac-ahora"><div class="tac-cab"><span class="tac-nombre">ahora/, 'de fábrica, lado a lado');
    assert.match(lado, /class="item tarjeta tac-ficha".*se decide: el presupuesto.*quedan 40min/s, 'la ficha: lo que se decide y cuánto queda');
    assert.ok(lado.indexOf('tac-vias') < lado.indexOf('tac-hacer') && lado.indexOf('tac-hacer') < lado.indexOf('tac-pie'), 'las vías, Hacer y el pie');
    const franja = tactica({ ...base, disposicion: 'franja' });
    assert.match(franja, /tac-ahora en-franja.*class="item tac-franja" data-accion="tactica-franja" data-valor="abrir"/s);
    assert.ok(!franja.includes('tac-ficha'), 'cerrada, sin la ficha');
    assert.ok(tactica({ ...base, disposicion: 'franja', abierta: true }).includes('tac-ficha'), 'abierta, con la ficha');
    // lo libre: cuánto, hasta qué, y lo que cabe
    const libre = tactica({ ...base, ahora: { tipo: 'libre', queda: 45, luego: '15:00 Comité', caben: 'las 3 decisiones (≈6min)' } });
    assert.match(libre, /libre<\/span> <span class="item-titulo">45min → 15:00 Comité.*caben<\/span> las 3 decisiones/s);
    // lo que cabe: primero decidir (dos minutos cada una), después las rápidas en su orden
    const rapida = (i) => q(i, { tamano: 'rapida', titulo: `rápida ${i}` });
    assert.equal(queCabe(45, 3, [q(0, { tamano: 'larga' }), rapida(1), rapida(2)]), 'las 3 decisiones (≈6min) y «rápida 1» (rápida)');
    assert.equal(queCabe(5, 4, []), '2 de las 4 decisiones (≈4min)', 'no caben todas');
    assert.equal(queCabe(70, 0, [rapida(1), rapida(2), rapida(3)]), '«rápida 1» (rápida) y «rápida 2» (rápida)');
    assert.equal(queCabe(30, 1, []), 'la decisión (≈2min)');
    assert.equal(queCabe(1, 1, [rapida(1)]), '', 'nada');
    assert.deepEqual([minutos(45), minutos(60), minutos(80)], ['45min', '1h', '1h 20']);
    // el pie: cada fuente con su cuenta (las vacías no), y ver todo
    assert.match(lado, /<div class="tac-pie">.*data-valor="tareas">54 tareas<\/a> · <a class="tac-ver-todo" data-accion="tactica-todo" data-valor=""/s);
    assert.ok(!lado.includes('0 correos'));
    // lo escrito se escapa
    const raro = tactica({ ...base, vias: vias([{ clave: 'x', nombre: '<u>c</u>', decisiones: [d(1, { titulo: '<b>x</b>', opciones: [{ id: '"', texto: '<s>o</s>' }] })] }]),
        ahora: { ...ahora, que: '<i>y</i>' } });
    assert.ok(!raro.includes('<b>x') && !raro.includes('<i>y') && !raro.includes('<u>c') && !raro.includes('<s>o') && raro.includes('&lt;b&gt;x'),
        'el título, la cuenta, las opciones y la ficha');
}
// 16. táctica en la página (vistas/dashboard/tactica.ts): de qué cuenta es cada espera, lo que hay que decidir (no el
// título), el reparto (Decidir por cuenta, los hilos detenidos arriba, lo que pide hacer a Hacer, los retenidos y lo que
// espera a otros al pie), lo que pide una reunión antes, Hacer (la próxima reunión solo si hay algo que preparar), Ahora,
// el pie, y todo junto con el día de mentira del catálogo
{
    const outfile = path.join(path.dirname(salida), 'tactica-vista.cjs');
    await build({ entryPoints: [path.join(aqui, '..', 'src', 'vistas', 'dashboard', 'tactica.ts')], bundle: true, platform: 'node', format: 'cjs', outfile, logLevel: 'warning' });
    const { proyectoDe, cuentaDe, pedido, artefactoDe, pruebaDe, decision, decisiones, porPreparar, quehaceres, ahoraDe, resto, SIN_CUENTA,
        contestadasDe, horaDesde, pasadaDe, pasadaVieja, procesoDePasada, PASADA, RESPALDO, REVISAR_YA, armar: armarTactica } = require(outfile);
    const e = (direccion, clase, desde, mas = {}) => ({ direccion, tipo: direccion.split(':')[0], clase, desde, titulo: `lo de ${direccion}`, resumen: '', enlaces: [], campos: {}, ...mas });
    const AHORA = Date.parse('2026-11-17T12:00:00');
    // el proyecto de una espera: su enlace; el que contiene un archivo que toca (el más hondo); el de una tarea que toca
    const PROY = [{ ruta: 'casa/feria', nombre: 'Feria · Stand', cliente: 'Feria' }, { ruta: 'casa/feria-charlas', nombre: 'Feria · Charlas', cliente: 'Feria' },
        { ruta: 'casa', nombre: 'Casa', interno: true }, { ruta: 'casa/boletin', nombre: 'Boletín', interno: true }];
    assert.equal(proyectoDe(e('tarea:T1', 'avance:pregunta', '', { enlaces: ['hilo:X', 'proyecto:casa/feria'] }), PROY), 'casa/feria');
    assert.equal(proyectoDe(e('pregunta:r/a', 'decide', '', { enlaces: ['agente:b', 'archivo:casa/boletin/preguntas/a.md'] }), PROY), 'casa/boletin', 'el más hondo que lo contiene');
    assert.equal(proyectoDe(e('pregunta:r/a', 'decide', '', { enlaces: ['tarea:T9@servidor'] }), PROY, new Map([['tarea:T9', 'casa/feria']])), 'casa/feria', 'por la tarea que toca');
    assert.equal(proyectoDe(e('tarea:T1', 'avance:pregunta', '')), '', 'sin nada, sin proyecto');
    // su cuenta: el cliente (los proyectos de un cliente, juntos); un proyecto de la casa, por su nombre; sin proyecto, sin cuenta
    assert.deepEqual(cuentaDe('casa/feria', PROY), { clave: 'cliente:feria', nombre: 'Feria' });
    assert.deepEqual(cuentaDe('casa/feria-charlas', PROY), cuentaDe('casa/feria', PROY), 'el mismo cliente, la misma cuenta');
    assert.deepEqual(cuentaDe('casa/boletin', PROY), { clave: 'casa/boletin', nombre: 'Boletín' });
    assert.deepEqual(cuentaDe('taller/vitrina', PROY), { clave: 'taller/vitrina', nombre: 'vitrina' }, 'sin saber de él, el final de su ruta');
    // una carpeta dentro de una unidad es de ella (la más honda); una unidad sin cliente, o con el de la casa, por su
    // nombre sin ese cliente delante: una iniciativa es su propia cuenta («Club de lectura · 2»)
    assert.deepEqual(cuentaDe('casa/boletin/numeros/12', PROY), { clave: 'casa/boletin', nombre: 'Boletín' });
    assert.deepEqual(cuentaDe('casa/otro/vitrina', PROY), { clave: 'casa', nombre: 'Casa' }, 'la más honda que la contiene');
    const INI = [...PROY, { ruta: 'casa/iniciativas/club', nombre: 'Club de lectura', cliente: '', interno: true },
        { ruta: 'casa/proyectos/club', nombre: 'Casa · Club de lectura', cliente: 'Casa', interno: true }];
    assert.deepEqual(cuentaDe('casa/iniciativas/club', INI), { clave: 'casa/iniciativas/club', nombre: 'Club de lectura' }, 'sin cliente: su nombre');
    assert.deepEqual(cuentaDe('casa/proyectos/club', INI), { clave: 'casa/proyectos/club', nombre: 'Club de lectura' },
        'con el cliente de la casa (a medio mudar): su nombre, sin él');
    const rIni = decisiones([e('tarea:T7', 'avance:pregunta', '2026-11-17T09:00:00', { enlaces: ['proyecto:casa/iniciativas/club'], campos: { texto: 'pide=decidir · falta: ¿a o b?' } }),
        e('tarea:T8', 'avance:pregunta', '2026-11-17T10:00:00', { enlaces: ['tarea:T8'], campos: { texto: 'pide=decidir · falta: ¿c?' } })],
        new Set(), AHORA, INI, new Map([['tarea:T8', 'casa/iniciativas/club/canales']]));
    const decidir = rIni.vias.find(v => v.clave === 'decidir');
    assert.deepEqual(decidir.cuentas.map(c => [c.nombre, c.decisiones.length]), [['Club de lectura', 2]], 'las dos, en la cuenta de la iniciativa');
    assert.deepEqual(cuentaDe('', PROY), { clave: '', nombre: SIN_CUENTA });
    // lo que hay que decidir: lo que falta, o el texto sin su fecha; de una pregunta, su asunto; de un cierre, la tarea
    const av = (clase, texto, mas = {}) => e('tarea:T1', clase, '', { titulo: 'El título de la tarea', campos: { texto, ...mas } });
    assert.equal(pedido(av('avance:pregunta', '16-nov 11:00: revisé el correo · falta: ¿la mandas hoy o la descartas?')), '¿La mandas hoy o la descartas?');
    assert.equal(pedido(av('avance:preparado', '17-nov: la propuesta lista para tu revisión.')), 'La propuesta lista para tu revisión', 'sin «falta», el texto sin la fecha');
    assert.equal(pedido(av('avance:preparado', 'pide=aprobar · 16-nov 09:00: borrador · falta: aprobar el stand doble ($2,4M)')), 'el stand doble ($2,4M)',
        'sin repetir lo que dice su vía');
    assert.equal(pedido(av('avance:preparado', 'pide=hacer-tu · falta: hacer la transferencia')), 'la transferencia');
    assert.equal(pedido(av('avance:preparado', 'falta: aprobar el stand')), 'Aprobar el stand', 'sin vía declarada, tal cual');
    assert.equal(pedido(av('avance:pregunta', 'pide=decidir · peso=alto (x) · falta: ¿12%?')), '¿12%?', 'sin lo declarado');
    assert.equal(pedido(av('avance:pregunta', '')), 'El título de la tarea', 'sin texto, el título');
    assert.equal(pedido(av('avance:cerrar', 'llegaron ayer', { como: 'hecha' })), 'El título de la tarea', 'un cierre: la tarea (cómo y la prueba, aparte)');
    assert.equal(pedido(e('pregunta:r/x', 'decide', '', { titulo: '¿Dónde sale la reseña?' })), '¿Dónde sale la reseña?');
    // lo que dejó hecho (de aprobar): el primer enlace o la primera ruta de un archivo; lo demás no se adivina
    assert.deepEqual(artefactoDe('borrador en casa/feria/presupuesto.md, con tres escenarios'), { nombre: 'presupuesto.md', direccion: 'archivo:casa/feria/presupuesto.md' });
    assert.deepEqual(artefactoDe('en https://docs.ejemplo.org/d/123/edit, para revisar.'), { nombre: 'docs.ejemplo.org', direccion: 'https://docs.ejemplo.org/d/123/edit' });
    assert.equal(artefactoDe('dejé un borrador en el correo (id r123)'), undefined);
    // la prueba de un cierre: lo que dice el agente, sin la fecha ni lo que pide
    assert.equal(pruebaDe('16-nov 15:00: la reunión existe (correo del 12-nov) · falta: confirmar el cierre'), 'la reunión existe (correo del 12-nov)');
    assert.equal(pruebaDe('Llegaron ayer: 500 bolsas.'), 'Llegaron ayer: 500 bolsas');
    assert.equal(pruebaDe('Cerrar como hecha: la reunión fue el 30-oct'), 'la reunión fue el 30-oct', 'sin cómo delante: va en la fila');
    // pide=cerrar en otra marca: la tarea, cómo (de su texto) y su prueba
    const otraMarca = decision(av('avance:preparado', 'pide=cerrar · peso=bajo · Cerrar como caduca: nadie la pidió'), new Set(), AHORA);
    assert.deepEqual([otraMarca.titulo, otraMarca.como, otraMarca.prueba], ['El título de la tarea', 'caduca', 'nadie la pidió']);
    // una fila: lo que hay que decidir, el título en el globo, su peso, y lo de su vía
    const una = decision(av('avance:preparado', 'pide=decidir · peso=medio (la feria lo pide) · falta: ¿quién la da?', { vence: '2026-11-14' }), new Set(), AHORA);
    assert.deepEqual([una.palabra, una.titulo, una.peso, una.porque], [undefined, '¿Quién la da?', { nivel: 'medio', porque: 'la feria lo pide' },
        { texto: 'venció el 14-nov', tono: undefined }]);
    assert.match(una.ayuda, /^El título de la tarea\n\npeso medio: la feria lo pide\n\nfalta: ¿quién la da\?/);
    const ap = decision(av('avance:preparado', 'pide=aprobar · quedó en casa/b/diciembre.md · falta: el boletín'), new Set(), AHORA);
    assert.deepEqual(ap.artefacto, { nombre: 'diciembre.md', direccion: 'archivo:casa/b/diciembre.md' });
    const ht = decision(av('avance:pregunta', 'pide=hacer-tu · falta: pagar la cuota'), new Set(), AHORA, new Map([['tarea:T1', 'rapida']]));
    assert.equal(ht.tamano, 'rapida', 'lo que pide hacer: el tamaño de su tarea');
    // de una tarea: otra fecha al pasar el mouse, con lo que lleva su fila (de otra máquina, por su número); si no está en
    // el día, la del proveedor de siempre. Lo de un hilo o de una pregunta del módulo, no
    const conFecha = decision({ ...av('avance:pregunta', 'falta: ¿la mando?', { vence: '2026-11-20' }), direccion: 'tarea:T1@servidor' }, new Set(), AHORA,
        new Map(), new Map([['tarea:T1', JSON.stringify(['propio', 'T1', 'T1'])]]));
    assert.deepEqual(conFecha.acciones.map(a => [a.accion, a.datos.valor, a.ayuda]), [['tactica-fecha', JSON.stringify(['propio', 'T1', 'T1']), 'otra fecha']]);
    const sinFecha = decision(av('avance:pregunta', 'falta: ¿la mando?'), new Set(), AHORA);
    assert.deepEqual([sinFecha.acciones[0].datos.valor, sinFecha.acciones[0].ayuda], [JSON.stringify(['tareas', 'T1', 'T1']), 'ponerle fecha']);
    assert.equal(decision(e('pregunta:r/x', 'decide', ''), new Set(), AHORA).acciones, undefined, 'una pregunta del módulo no tiene fecha que mover');
    assert.equal(decision(e('permiso:Faro', 'permiso', ''), new Set(), AHORA).acciones, undefined, 'ni un hilo detenido');
    const dec = decision(av('avance:pregunta', 'pide=decidir · opciones=a | b* · falta: ¿cuál?'), new Set(), AHORA);
    assert.deepEqual(dec.opciones, [{ id: 'a', texto: 'a' }, { id: 'b', texto: 'b', recomendada: true }], 'las que declara: su texto es lo que se contesta');
    const decl = decision(av('avance:preparado', 'pide=aprobar · artefacto=https://docs.ejemplo.org/d/9 · lo dejé en casa/otro.md · falta: x'), new Set(), AHORA);
    assert.equal(decl.artefacto.direccion, 'https://docs.ejemplo.org/d/9', 'lo hecho que declara, antes que lo que nombra el texto');
    assert.deepEqual(decision(av('avance:preparado', 'pide=aprobar · artefacto=casa/carpeta · x'), new Set(), AHORA).artefacto,
        { nombre: 'carpeta', direccion: 'archivo:casa/carpeta' }, 'una ruta sin extensión, tal cual');
    const ce = decision(av('avance:cerrar', '16-nov: llegó la factura · falta: confirmar el cierre', { como: 'hecha' }), new Set(), AHORA);
    assert.deepEqual([ce.titulo, ce.como, ce.prueba], ['El título de la tarea', 'hecha', 'llegó la factura']);
    const op = decision(e('pregunta:r/x', 'decide', '', { campos: { opciones: [{ id: 'a', texto: 'A', recomendada: true }, { id: 'b', texto: 'B', recomendada: false }, { texto: 'sin id' }] } }),
        new Set(), AHORA);
    assert.deepEqual(op.opciones, [{ id: 'a', texto: 'A', recomendada: true }, { id: 'b', texto: 'B' }], 'decidir: sus opciones, con la recomendada');
    const vivo = decision(e('permiso:Faro', 'permiso', '2026-11-17T11:56:00'), new Set(), AHORA);
    assert.deepEqual([vivo.palabra, vivo.tono, vivo.edad, vivo.porque.texto], ['permiso', 'espera', '4m', 'te espera'], 'un hilo detenido dice su clase y cuánto lleva');
    // el reparto: cada una en su vía (la declarada; sin declarar, sin clasificar, salvo un cierre o una pregunta del módulo),
    // por cuenta (cada una en el lugar de su más urgente; sin cuenta al final); hilos detenidos arriba; retenidos, contados
    const feria = { enlaces: ['proyecto:casa/feria'] }, charlas = { enlaces: ['proyecto:casa/feria-charlas'] }, boletin = { enlaces: ['proyecto:casa/boletin'] };
    const rep = decisiones([
        e('tarea:T1', 'avance:pregunta', '2026-11-10T10:00:00', { campos: { texto: 'pide=decidir · falta: ¿a?' } }),
        e('tarea:T2', 'avance:preparado', '2026-11-12T10:00:00', { ...boletin, campos: { texto: 'pide=decidir · falta: ¿b?' } }),
        e('tarea:T3', 'avance:pregunta', '2026-11-16T10:00:00', { ...feria, campos: { texto: 'pide=decidir · peso=alto · falta: ¿c?' } }),
        e('tarea:T4', 'avance:preparado', '2026-11-11T10:00:00', { ...charlas, campos: { texto: 'pide=decidir · falta: ¿d?' } }),
        e('tarea:T5', 'avance:preparado', '2026-11-11T10:00:00', { ...boletin, campos: { texto: 'pide=hacer-tu · falta: firmarlo' } }),
        e('tarea:T6', 'avance:preparado', '2026-11-11T10:00:00', { ...boletin, campos: { texto: 'falta: ¿lo mando?' } }),
        e('tarea:T8', 'avance:cerrar', '2026-11-11T10:00:00', { ...feria, campos: { texto: 'listo', como: 'hecha' } }),
        e('pregunta:r/x', 'decide', '2026-11-15T10:00:00', { enlaces: ['archivo:casa/boletin/p/x.md'] }),
        e('mensaje:m1', 'retenido', '2026-11-17T09:00:00'), e('mensaje:m2', 'retenido', '2026-11-17T09:05:00'),
        e('permiso:Faro', 'permiso', '2026-11-17T11:00:00', feria),
        e('tarea:T7', 'avance:pregunta', '2026-11-10T10:00:00', { ...feria, campos: { vence: '2026-09-01', texto: 'pide=decidir · x' } }),
    ], new Set(), AHORA, PROY);
    const ver = v => rep.vias.find(x => x.clave === v).cuentas.map(c => [c.nombre, c.decisiones.map(x => x.id)]);
    assert.deepEqual(rep.vias.map(v => v.clave), ['decidir', 'aprobar', 'cerrar', 'sin-clasificar'], 'las tres vías y lo sin clasificar, en su orden');
    assert.deepEqual(ver('decidir'), [['Feria', ['tarea:T3', 'tarea:T4']], ['Boletín', ['tarea:T2', 'pregunta:r/x']], ['sin cuenta', ['tarea:T1']]],
        'la de peso alto arrastra a su cuenta arriba; los dos proyectos de la feria juntos; la pregunta del módulo, por su carpeta; sin cuenta al final; la deuda no entra');
    assert.deepEqual([ver('aprobar'), ver('cerrar'), ver('sin-clasificar')], [[], [['Feria', ['tarea:T8']]], [['Boletín', ['tarea:T6']]]],
        'lo no declarado, sin clasificar (no se adivina)');
    assert.deepEqual(rep.hacerTu.map(c => [c.nombre, c.decisiones.map(x => x.id)]), [['Boletín', ['tarea:T5']]], 'lo que pide hacer, aparte: va a Hacer');
    assert.deepEqual(rep.grupos.get('via:hacer-tu').map(x => x.direccion), ['tarea:T5'], 'y se recorre con su tecla');
    assert.deepEqual(rep.vivo.map(x => x.id), ['permiso:Faro'], 'el hilo detenido, aparte (no en su cuenta)');
    assert.equal(rep.retenidos, 2);
    assert.deepEqual(rep.grupos.get('cuenta:decidir|cliente:feria').map(x => x.direccion), ['tarea:T3', 'tarea:T4'], 'una cuenta se contesta una tras otra');
    assert.deepEqual(rep.grupos.get('via:decidir').map(x => x.direccion), ['tarea:T3', 'tarea:T4', 'tarea:T2', 'pregunta:r/x', 'tarea:T1'], 'y una vía, en su orden');
    assert.ok(!rep.grupos.has('mensaje:m1'), 'los retenidos, no: se sueltan en «te esperan»');
    // lo contestado que espera al agente (`telar esperas`, `contestadas`): lo más reciente primero, la hora desde hoy, y si
    // se la encargó (lo dice la tarea; o, recién, lo de aquí: en camino, hecho o que no salió, mientras sea la misma respuesta)
    assert.deepEqual(['2026-11-17T11:20:00', '2026-11-16T18:30:00', '2026-11-14T09:00:00', '2026-11-17', '2026-11-16', '', 'nunca'].map(x => horaDesde(x, AHORA)),
        ['11:20', 'ayer 18:30', '14-nov', 'hoy', 'ayer', '', '']);
    const jc = (n, cuando, mas = {}) => ({ direccion: `tarea:T${n}`, titulo: `**la** T${n}`, cuando, respuesta: `dije ${n}`, enlaces: [], ...mas });
    const cs = [jc(1, '2026-11-16T18:30:00'), jc(2, '2026-11-17T11:20:00', { encargada: '2026-11-17T11:42:00' }), jc(3, '2026-11-17T09:00:00')];
    const vistas = contestadasDe(cs, AHORA);
    assert.deepEqual(vistas.map(c => [c.id, c.titulo, c.cuando, c.encargada ?? '']),
        [['tarea:T2', 'la T2', '11:20', '11:42'], ['tarea:T3', 'la T3', '09:00', ''], ['tarea:T1', 'la T1', 'ayer 18:30', '']]);
    assert.match(vistas[0].ayuda, /^la T2\n\ncontestaste \(11:20\): dije 2\n\nse la encargaste al agente: 11:42\n\ntarea:T2$/);
    const hecho = { lineas: 0, mensaje: false };
    const local = new Map([['tarea:T3', { estado: 'enviando', para: '2026-11-17T09:00:00', hecho }],
        ['tarea:T1', { estado: 'hecho', para: '2026-11-16T18:30:00', hora: '12:01', hecho }],
        ['tarea:T2', { estado: 'fallo', para: '2026-11-17T11:20:00', error: 'sin bus', hecho }]]);
    assert.deepEqual(contestadasDe(cs, AHORA, local).map(c => [c.id, !!c.encargando, c.encargada ?? '', c.fallo ?? '']),
        [['tarea:T2', false, '', 'sin bus'], ['tarea:T3', true, '', ''], ['tarea:T1', false, '12:01', '']],
        'en camino; hecho recién (la tarea todavía no lo dice); y lo que no salió se puede reintentar aunque la línea haya quedado');
    assert.deepEqual(contestadasDe([jc(1, '2026-11-17T11:50:00')], AHORA, local).map(c => c.encargada ?? ''), [''],
        'contestada de nuevo: lo de antes ya no vale');
    assert.match(REVISAR_YA, /^prompt: revisar ya\b/, 'telar.objetos la reconoce por «prompt: revisar ya» (_REVISAR_YA)');
    // la próxima pasada: el periódico PASADA (por su nombre o su skill), su próxima corrida en la hora de aquí; corriendo,
    // pausado, sin él o sin poder leer, lo dice sin inventar
    const proc = (mas = {}) => ({ nombre: PASADA, cuando: '0 7-22 * * *', tipo: 'mensaje', comando: '', mensaje: '/pulso --seco', hilo: '', max_abiertos: 1,
        argumentos: [], carpeta: '', descripcion: '', activo: true, proxima: '2026-11-17T13:00:00', ultima: {}, ...mas });
    const per = (...procesos) => ({ maquina: 'servidor', archivo: '', zona: 'America/Santiago', procesos });
    assert.deepEqual([PASADA, RESPALDO], ['pulso', 'avanzar'], 'desde el 18-nov pasa pulso; avanzar, si no hay pulso');
    assert.deepEqual(pasadaDe(per(proc({ nombre: 'otro', proxima: '2026-11-17T12:30:00', mensaje: '/correo' }), proc()), AHORA),
        { texto: 'próxima pasada 13:00', ayuda: 'la próxima vez que corre «pulso» (en servidor), con el horario 0 7-22 * * *: 13:00. Retoma lo contestado primero; «revisar ya» no la espera' });
    assert.equal(procesoDePasada([proc({ nombre: 'tareas', mensaje: '/pulso correo' })]).nombre, 'tareas', 'sin uno que se llame así, el que pide la skill');
    assert.equal(procesoDePasada([proc({ nombre: 'otro', mensaje: '/pulsos' })]), undefined);
    // pulso-noche cuenta solo cuando es la próxima: de día, la de la hora que viene; de noche, la de las 23:30
    const noche = (mas = {}) => proc({ nombre: 'pulso-noche', cuando: '30 23 * * *', mensaje: '/pulso noche --seco', proxima: '2026-11-17T23:30:00', ...mas });
    const avanzar = (mas = {}) => proc({ nombre: 'avanzar', cuando: '0 7-19/2 * * 1-5', mensaje: '/avanzar', proxima: '2026-11-17T12:00:00', ...mas });
    assert.equal(procesoDePasada([noche(), avanzar(), proc()]).nombre, 'pulso');
    assert.equal(procesoDePasada([noche(), proc({ proxima: '2026-11-18T07:00:00' })]).nombre, 'pulso-noche', 'después de la de las 22:00');
    assert.equal(procesoDePasada([noche({ ultima: { corriendo: true } }), proc()]).nombre, 'pulso-noche', 'la que está corriendo, aunque otra sea antes');
    assert.equal(procesoDePasada([noche({ activo: false }), proc({ activo: false }), avanzar()]).nombre, 'pulso', 'pulso pausado: lo dice, no vuelve a avanzar');
    assert.equal(procesoDePasada([noche(), proc({ activo: false })]).nombre, 'pulso-noche', 'una activa le gana a una pausada');
    // sin ningún pulso, avanzar (pausado o no), como antes
    assert.equal(procesoDePasada([avanzar({ activo: false })]).nombre, 'avanzar');
    assert.equal(pasadaDe(per(avanzar({ activo: false })), AHORA).texto, 'pasada pausada');
    assert.equal(procesoDePasada([avanzar({ nombre: 'tareas-noche', mensaje: '/avanzar T84' })]).nombre, 'tareas-noche');
    assert.equal(pasadaDe(per(proc({ proxima: '2026-11-18T07:00:00' })), AHORA).texto, 'próxima pasada mañana 07:00');
    assert.equal(pasadaDe(per(proc({ proxima: '2026-11-20T07:00:00' })), AHORA).texto, 'próxima pasada el vie 07:00');
    assert.equal(pasadaDe(per(proc({ proxima: '2026-11-17T13:00-03:00' })), Date.parse('2026-11-17T12:00:00-03:00')).ayuda.includes(': '), true, 'con la zona de allá, se lee');
    assert.deepEqual(pasadaDe(per(proc({ ultima: { corriendo: true, inicio: '2026-11-17T11:00:03' } })), AHORA),
        { texto: 'pasando ahora', tono: 'agente', ayuda: '«pulso» (en servidor) está corriendo desde las 11:00: puede que ya vaya por ellas' });
    assert.deepEqual([pasadaDe(per(proc({ activo: false, proxima: '' })), AHORA).texto, pasadaDe(per(proc({ activo: false })), AHORA).tono], ['pasada pausada', 'atencion'],
        'pausada: nadie va a pasar, un cuidado');
    assert.deepEqual([pasadaDe(per(), AHORA).texto, pasadaDe(per(), AHORA).tono], ['sin pasada', 'atencion']);
    assert.match(pasadaDe(per(), AHORA).ayuda, /falta «pulso» \(o «avanzar»\) en telar periodicos/);
    assert.deepEqual(pasadaDe({ error: 'los periódicos viven en servidor y no respondió' }, AHORA),
        { texto: 'próxima pasada: no se sabe', ayuda: 'no pude leer los periódicos desde aquí, así que no sé cuándo pasa el agente: los periódicos viven en servidor y no respondió' });
    assert.equal(pasadaDe(per(proc({ proxima: '' })), AHORA).texto, 'próxima pasada: no se sabe');
    assert.equal(pasadaDe(undefined, AHORA), undefined, 'sin leer, nada');
    // cuándo se relee: sin nada, sí; recién leída, no; pasada la hora que se sabía, o corriendo, o con un rato, sí
    const p13 = per(proc());
    assert.equal(pasadaVieja(undefined, 0, AHORA), true);
    assert.equal(pasadaVieja(p13, AHORA - 30000, AHORA), false, 'menos de un minuto: no');
    assert.equal(pasadaVieja(p13, AHORA - 5 * 60000, AHORA), false, 'la de las 13:00 todavía no llega');
    assert.equal(pasadaVieja(p13, AHORA - 5 * 60000, Date.parse('2026-11-17T13:00:30')), true, 'ya pasó: a ver la siguiente');
    assert.equal(pasadaVieja(per(proc({ ultima: { corriendo: true } })), AHORA - 2 * 60000, AHORA), true, 'corriendo: a ver cuándo termina');
    assert.equal(pasadaVieja(p13, AHORA - 16 * 60000, AHORA), true, 'un cuarto de hora: de nuevo');
    assert.equal(pasadaVieja({ error: 'x' }, AHORA - 5 * 60000, AHORA), false, 'lo que falló, no a cada minuto');
    // todo junto: Táctica las trae con su pasada; una que todavía espera a la persona no está (Python ya las separa)
    const tc = armarTactica({ dia: { fecha: '2026-11-17', pendientes: [], eventos: [] }, esperas: [], ahora: AHORA, pestanas: [], contestadas: cs,
        periodicos: per(proc()), agente: 'Avances' }).tactica;
    assert.deepEqual([tc.contestadas.map(c => c.id), tc.pasada.texto, tc.agente], [['tarea:T2', 'tarea:T3', 'tarea:T1'], 'próxima pasada 13:00', 'Avances']);
    assert.match(decision(e('tarea:T1', 'avance:pregunta', '', { campos: { texto: 'falta: ¿y ahora?', aplique: 'mandé la contraoferta' } }), new Set(), AHORA).ayuda,
        /con tu respuesta anterior, apliqué: mandé la contraoferta/, 'en el globo, lo que hizo con la respuesta anterior');
    // lo que pide una reunión antes: responderla, lo que hay que llevar, prepararla si se decide algo; si no, nada
    const ev = (id, h1, h2, titulo, mas = {}) => ({ id, titulo, inicio: Date.parse(`2026-11-17T${h1}:00`), fin: Date.parse(`2026-11-17T${h2}:00`),
        lugar: '', url: '', asistentes: ['a@x'], respuesta: 'aceptada', soloPlan: false, ...mas });
    assert.equal(porPreparar(ev('r', '15:00', '16:00', 'Comité', { respuesta: 'sin_responder' })), 'responderla');
    assert.equal(porPreparar(ev('r', '15:00', '16:00', 'Comité', { plan: { ficha: { llevar: ['el presupuesto'] } } })), 'llevar 1 cosa', 'corto: va al final de la fila');
    assert.equal(porPreparar(ev('r', '15:00', '16:00', 'Comité', { plan: { ficha: { llevar: ['a', 'b'], decision: 'x' } } })), 'llevar 2 cosas');
    assert.equal(porPreparar(ev('r', '15:00', '16:00', 'Comité', { plan: { ficha: { decision: 'el presupuesto' } } })), 'prepararla');
    assert.equal(porPreparar(ev('r', '15:00', '16:00', 'Comité', { plan: { nota: 'de siempre' } })), '', 'sin nada que preparar');
    // Hacer: la próxima reunión solo si hay algo que preparar; el próximo bloque estratégico; las tareas propias de hoy
    const t = (id, mas = {}) => ({ texto: `tarea ${id}`, hecho: false, en_curso: false, id, origen: 'tareas', ref: id, hilo: '', ruta: '', proveedor: 'tareas',
        cuando: null, url: '', ficha: true, direccion: `tarea:${id}`, ...mas });
    const d = { ahora: '', fecha: '2026-11-17', nombreDia: 'martes', semana: 47, agenda: [], declarados: [], fallas: [], pendientes: [
        t('T1', { cuando: '2026-11-17' }), t('T2', { cuando: '2026-11-12' }), t('T3'), t('T4', { cuando: '2026-11-19' }), t('T5', { cuando: '2026-09-01' }),
        t('T6', { cuando: '2026-11-17', dueno: 'Otra Persona' }), t('T7', { cuando: '2026-11-17', avance: 'pregunta 2026-11-16' }), t('T8', { hecho: true, cuando: '2026-11-17' })] };
    const sinNada = ev('c', '15:00', '16:00', 'Comité', { plan: { nota: 'de siempre' } });
    const foco = ev('f', '16:30', '17:30', 'Foco: el informe', { asistentes: [], soloPlan: true, plan: { tipo: 'bloque', clase: 'estrategico' } });
    const h1 = quehaceres(d, [sinNada, foco], { foco: { paso: 'el índice' } }, new Set(['T3']), AHORA);
    assert.match(h1.lista[0].ayuda, /el paso: el índice/, 'el paso del foco, en el globo');
    assert.deepEqual(h1.lista.map(q => [q.tipo, q.id, q.nota ?? q.porque?.texto]), [['bloque', 'f', 'el foco del día'],
        ['tarea', 'tarea:T2', 'venció el 12-nov'], ['tarea', 'tarea:T1', 'vence hoy'], ['tarea', 'tarea:T3', 'el plan: hoy']],
        'sin nada que preparar, la reunión no ocupa lugar; el bloque, y las tareas de hoy en su orden');
    assert.equal(h1.resto, 2, 'quedan fuera, para el pie: la de esta semana y la deuda (no las de otros, ni las con algo de un agente, ni las hechas)');
    const conAlgo = { ...sinNada, plan: { ficha: { decision: 'el presupuesto' } } };
    const h2 = quehaceres(d, [conAlgo], undefined, new Set(), AHORA);
    assert.deepEqual([h2.lista[0].tipo, h2.lista[0].hora, h2.lista[0].nota, h2.lista[0].clic.accion], ['reunion', '15:00', 'prepararla', 'reunion'], 'con algo que preparar, primero');
    assert.deepEqual(JSON.parse(h2.lista[0].clic.valor).slice(0, 2), ['Comité', '15:00'], 'un clic la prepara, como en «ahora»');
    assert.deepEqual(h2.lista[1].clic, { accion: 'tarea', valor: JSON.stringify(['tareas', 'T2', 'T2']) }, 'una tarea: su ficha, como en su fila de siempre');
    assert.deepEqual(h2.lista[1].acciones.map(a => a.accion), ['tactica-fecha', 'instruccion-fila', 'hecha-fila'],
        'de su fila: otra fecha (por Táctica, que relee lo que espera), la instrucción y hecha');
    assert.deepEqual([h2.lista[1].acciones[0].datos.valor, h2.lista[1].acciones[0].ayuda], [JSON.stringify(['tareas', 'T2', 'T2']), 'otra fecha'],
        'la fecha: lo mismo que en la lista de tareas');
    assert.equal(h2.lista[1].menu.accion, 'menu-tarea', 'su ⋯, el de la lista (en el teléfono, la fecha va ahí)');
    const pasada = { ...conAlgo, inicio: Date.parse('2026-11-17T09:00:00'), fin: Date.parse('2026-11-17T10:00:00') };
    assert.ok(!quehaceres(d, [pasada], undefined, new Set(), AHORA).lista.some(q => q.tipo === 'reunion'), 'la que ya pasó, no');
    const rechazada = { ...conAlgo, respuesta: 'rechazada' };
    assert.ok(!quehaceres(d, [rechazada], undefined, new Set(), AHORA).lista.some(q => q.tipo === 'reunion'), 'la rechazada, no');
    // Ahora: en una reunión, su ficha; en un bloque, su paso; libre hasta lo próximo (una reserva es libre) y lo que cabe
    const fin = Date.parse('2026-11-17T18:00:00');
    const en = ahoraDe([ev('r', '11:30', '12:30', 'Revisión', { url: 'https://x', plan: { ficha: { decision: 'la foto', llevar: ['el boceto'] } } })],
        Date.parse('2026-11-17T11:45:00'), fin, undefined, 0, []);
    assert.deepEqual([en.tipo, en.titulo, en.cuando, en.queda, en.que], ['reunion', 'Revisión', '11:30–12:30', 45, 'se decide: la foto']);
    assert.deepEqual(en.datos.map(x => x.texto), ['llevar: el boceto', '1 persona']);
    assert.deepEqual(en.acciones.map(a => a.accion), ['tactica-entrar', 'reunion'], 'entrar (su dirección) y prepararla o la minuta');
    assert.equal(en.acciones[0].datos.url, 'https://x');
    const bloque = ahoraDe([{ ...foco, inicio: Date.parse('2026-11-17T11:00:00'), fin: Date.parse('2026-11-17T12:00:00') }], Date.parse('2026-11-17T11:40:00'), fin,
        { foco: { paso: 'el índice', terminado: 'aprobado' } }, 0, []);
    assert.deepEqual([bloque.tipo, bloque.queda, bloque.que, bloque.datos[0].texto], ['bloque', 20, 'el paso: el índice', 'terminado si: aprobado']);
    const reserva = ev('s', '12:00', '13:00', 'Reserva', { asistentes: [], soloPlan: true, plan: { tipo: 'bloque', clase: 'reserva' } });
    const libre = ahoraDe([reserva, sinNada], Date.parse('2026-11-17T12:15:00'), fin, undefined, 1, [{ tipo: 'tarea', id: 't', titulo: 'llamar', tamano: 'rapida' }]);
    assert.deepEqual([libre.tipo, libre.queda, libre.luego, libre.caben], ['libre', 165, '15:00 Comité', 'la decisión (≈2min) y «llamar» (rápida)'],
        'en una reserva se está libre, hasta la próxima');
    const tarde = ahoraDe([sinNada], Date.parse('2026-11-17T16:30:00'), fin, undefined, 0, []);
    assert.deepEqual([tarde.tipo, tarde.queda, tarde.luego], ['fin', 90, undefined], 'sin nada más: libre hasta el fin de la jornada');
    // el pie: cuántas tareas quedan, y las fuentes (los bloques, los feeds) con lo que dicen de sí; las fijas, no
    assert.deepEqual(resto(4, [{ clave: 'ahora', accion: 'ahora', valor: '', nombre: 'ahora', aviso: '' },
        { clave: 'bloque:mensajes', accion: 'bloque', valor: 'mensajes', nombre: 'mensajes', aviso: '3 sin leer' },
        { clave: 'pestana:leer', accion: 'pestana', valor: 'leer', nombre: 'leer', aviso: '' }]).map(r => [r.texto ?? `${r.cuenta} ${r.nombre}`, r.clic.accion, r.clic.valor ?? '']),
        [['4 tareas más', 'revisar', ''], ['mensajes: 3 sin leer', 'bloque', 'mensajes'], ['leer', 'pestana', 'leer']]);
    assert.deepEqual(resto(1, [], 2).map(r => [`${r.cuenta} ${r.nombre}`, r.clic.accion, r.clic.valor]),
        [['2 mensajes entre hilos retenidos', 'tactica-todo', 'esperas'], ['1 tarea más', 'revisar', undefined]], 'los retenidos, primero, a «te esperan»');
    // todo junto, con el día de mentira del catálogo (componentes/muestras-tactica.ts)
    const { ESTADOS } = await armar('muestras-tactica');
    const de = c => ESTADOS.find(x => x.clave === c).tactica('lado');
    const { porDecidir } = await armar('tactica');
    const r = de('reunion');
    assert.deepEqual([r.ahora.tipo, r.ahora.titulo, r.hacer[0].titulo, r.hacer[0].nota], ['reunion', 'Revisión de diseño', 'Comité', 'llevar 1 cosa']);
    assert.match(r.hacer[0].ayuda, /llevar: los tres escenarios del presupuesto/);
    assert.deepEqual(r.vivo.map(x => x.id), ['permiso:Vitrina'], 'la pregunta en vivo de un hilo, arriba');
    const via = (t, v) => t.vias.find(x => x.clave === v).cuentas.map(c => `${c.nombre} · ${c.decisiones.length}`);
    assert.deepEqual(via(r, 'decidir'), ['Colegio del Valle · 1', 'Inventario · 1', 'Boletín · 2', 'Feria del Libro · 1', 'sin cuenta · 1'],
        'por peso: el colegio (alto, espera hoy) arriba; sin cuenta al final');
    assert.deepEqual(via(r, 'aprobar'), ['Feria del Libro · 1', 'Boletín · 1', 'sin cuenta · 1']);
    assert.deepEqual(r.hacerTu.map(c => `${c.nombre} · ${c.decisiones.length}`), ['Colegio del Valle · 1', 'Feria del Libro · 1'], 'lo que pide hacer, en Hacer');
    assert.deepEqual(via(r, 'cerrar'), ['Distribuidora del Sur · 2', 'Tienda · 1']);
    assert.deepEqual(via(r, 'sin-clasificar'), [], 'todo declarado');
    assert.deepEqual(r.vias[0].cuentas[0].decisiones[0].porque, { texto: 'el colegio espera hoy', tono: 'espera' });
    assert.deepEqual(r.vias[1].cuentas[0].decisiones[0].porque, { texto: 'vence el jue', tono: 'atencion' }, 'la fecha dura, con color');
    assert.equal(r.hacerTu[0].decisiones[0].tamano, 'rapida', 'lo que pide hacer, con el tamaño de su tarea');
    assert.deepEqual(r.vias[0].cuentas[0].decisiones[0].opciones.map(o => `${o.texto}${o.recomendada ? '*' : ''}`),
        ['aceptar el 12%', 'contraofertar un 8%*', 'consultarlo con la contadora'], 'decidir, con las opciones que declara');
    assert.deepEqual(r.vias[1].cuentas[0].decisiones[0].artefacto, { nombre: 'presupuesto.md', direccion: 'archivo:casa/feria/presupuesto.md' });
    assert.equal(porDecidir(r.vias, r.vivo), 13);
    assert.deepEqual(r.contestadas.map(c => [c.id, c.cuando, c.encargada ?? '']), [['tarea:T15', '11:20', '11:42'], ['tarea:T27', '10:05', ''], ['tarea:T33', 'ayer 18:30', '']],
        'lo contestado en la mañana de mentira (una ya encargada) y ayer');
    assert.equal(r.pasada.texto, 'próxima pasada 12:00', 'a las 11:45, la de las 12:00 (pulso pasa cada hora)');
    assert.equal(ESTADOS.find(x => x.clave === 'reunion').datos.agente, 'Avances');
    assert.equal(`${r.resto[0].cuenta} ${r.resto[0].nombre}`, '2 mensajes entre hilos retenidos');
    const hoy = de('hoy');
    assert.deepEqual([...['decidir', 'aprobar', 'cerrar'].map(v => via(hoy, v).length), hoy.hacerTu.length], [1, 0, 2, 0],
        'sin nada declarado: solo las preguntas del módulo (decidir) y los cierres propuestos (cerrar)');
    assert.ok(via(hoy, 'sin-clasificar').length > 3, 'lo demás, sin clasificar');
    assert.equal(de('libre').ahora.caben, 'las 4 decisiones (≈8min) y «Mandar el pedido de diciembre a la distribuidora» (rápida)', 'el retenido no es una decisión');
    assert.equal(porDecidir(de('nada').vias), 0);
    assert.ok(via(de('muchas'), 'aprobar').length > 3, 'más cuentas que el tope');
    const sp = de('sinplan');
    assert.deepEqual([sp.sinPlan, sp.hacer.map(q => q.id)], [true, ['tarea:T40']], 'sin plan: lo que vence hoy, sin la reunión');
}
// 17. Modos y mundos (componentes/modos-mundos.ts, el prototipo): el horario de un mundo y el mundo puesto (por su horario,
// fuera de él, a mano hasta el próximo cambio), los cuatro modos y sus controles. Y Todo (componentes/todo.ts): lo del
// mundo puesto primero, lo de los otros al final (el mundo ordena, no esconde), los topes por fuente y una fuente entera.
{
    const M = await armar('modos-mundos');
    const { leerTramo, leerHorario, enTramo, mundoAhora, MODOS, alAbrir, modosEnFila, mundoBoton, decirMundo, decirTramo, opcionesMundo } = M;
    // los tramos: días y horas, cualquiera puede faltar; un tramo puede pasar la medianoche
    assert.deepEqual(leerTramo('lun-vie 9:00-19:00'), { dias: [1, 2, 3, 4, 5], desde: 540, hasta: 1140 });
    assert.deepEqual(leerTramo('sáb-dom'), { dias: [0, 6], desde: 0, hasta: 1440 }, 'el día entero');
    assert.deepEqual(leerTramo('lun,miércoles,vie 8:30-12'), { dias: [1, 3, 5], desde: 510, hasta: 720 });
    assert.deepEqual(leerTramo('20:00-23:00').dias, [0, 1, 2, 3, 4, 5, 6], 'sin días: todos');
    assert.deepEqual(leerTramo('todos'), { dias: [0, 1, 2, 3, 4, 5, 6], desde: 0, hasta: 1440 });
    assert.deepEqual(leerTramo('vie-lun 22-2'), { dias: [0, 1, 5, 6], desde: 1320, hasta: 120 }, 'un rango que da la vuelta a la semana');
    for (const malo of ['', 'lunes a viernes', 'lun 25:00-26:00', 'lun 9-9', 'xyz 9-10', 'lu 9-10', '9:00']) {
        assert.throws(() => leerTramo(malo), /«/, `no se entiende: «${malo}»`);
    }
    assert.equal(leerHorario(['lun-vie 9-13', 'lun-vie 14-19']).length, 2, 'una lista de tramos');
    assert.deepEqual(leerHorario(undefined), []);
    assert.equal(decirTramo(leerTramo('lun-vie 9:00-19:00')), 'lun–vie 9:00–19:00');
    assert.equal(decirTramo(leerTramo('sáb-dom')), 'sáb, dom');
    // la noche de un viernes y la madrugada del sábado son del tramo; la del jueves y el sábado a las 3, no
    const noche = leerTramo('vie 22:00-2:00');
    const d = (dia, hh, mm = 0) => new Date(2026, 10, 15 + dia, hh, mm);   // 15-nov-2026 es domingo: d(2) es martes
    assert.ok(enTramo(noche, d(5, 23)) && enTramo(noche, d(6, 1)), 'viernes 23:00 y sábado 1:00');
    assert.ok(!enTramo(noche, d(6, 3)) && !enTramo(noche, d(4, 23)), 'sábado 3:00 y jueves 23:00');

    // el mundo puesto: trabajo de lunes a viernes de 9 a 19; fuera, lo personal
    const mundos = [{ clave: 'trabajo', nombre: 'trabajo', color: 'cian', horario: leerHorario('lun-vie 9:00-19:00') },
        { clave: 'personal', nombre: 'personal', color: 'magenta' }];
    const o = { fuera: 'personal' };
    const ver = (p) => [p.mundo, p.por, p.hasta && `${p.hasta.getDate()} ${p.hasta.getHours()}:${String(p.hasta.getMinutes()).padStart(2, '0')}`, p.luego];
    assert.deepEqual(ver(mundoAhora(mundos, d(2, 11, 45), o)), ['trabajo', 'horario', '17 19:00', 'personal'], 'martes 11:45');
    assert.deepEqual(ver(mundoAhora(mundos, d(2, 20, 30), o)), ['personal', 'fuera', '18 9:00', 'trabajo'], 'martes 20:30: hasta mañana');
    assert.deepEqual(ver(mundoAhora(mundos, d(6, 11), o)), ['personal', 'fuera', '23 9:00', 'trabajo'], 'el sábado: hasta el lunes');
    assert.deepEqual(ver(mundoAhora(mundos, d(2, 8, 59), o)), ['personal', 'fuera', '17 9:00', 'trabajo'], 'un minuto antes');
    assert.deepEqual(ver(mundoAhora(mundos, d(2, 19), o)), ['personal', 'fuera', '18 9:00', 'trabajo'], 'el borde es del siguiente');
    // a mano: dura hasta el próximo cambio del horario que había al elegirlo, y después vuelve solo
    const aMano = { mundo: 'personal', desde: d(2, 11, 40) };
    assert.deepEqual(ver(mundoAhora(mundos, d(2, 11, 45), { ...o, aMano })), ['personal', 'a-mano', '17 19:00', 'personal']);
    assert.deepEqual(ver(mundoAhora(mundos, d(2, 19, 10), { ...o, aMano })), ['personal', 'fuera', '18 9:00', 'trabajo'], 'ya venció');
    assert.deepEqual(ver(mundoAhora(mundos, d(2, 21), { ...o, aMano: { mundo: 'trabajo', desde: d(2, 20) } })), ['trabajo', 'a-mano', '18 9:00', 'trabajo'],
        'trabajo a mano de noche: hasta mañana a las 9');
    assert.deepEqual(ver(mundoAhora(mundos, d(2, 11, 45), { ...o, aMano: { mundo: '', desde: d(2, 11) } })).slice(0, 2), ['', 'a-mano'], 'ambos, a mano');
    // sin `fuera`, fuera de todo horario es ambos; dos horarios que se pisan, también
    assert.deepEqual(ver(mundoAhora(mundos, d(2, 20, 30))).slice(0, 2), ['', 'fuera']);
    const pisan = [mundos[0], { ...mundos[1], horario: leerHorario('mar 11:00-12:00') }];
    assert.equal(mundoAhora(pisan, d(2, 11, 30), o).mundo, 'personal', 'en los dos: ninguno manda, rige el de fuera');
    // sin horarios: el de a mano, o el de fuera (ambos)
    const sin = mundos.map(m => ({ ...m, horario: undefined }));
    assert.deepEqual(ver(mundoAhora(sin, d(2, 11))), ['', 'sin-horario', undefined, undefined]);
    assert.deepEqual(ver(mundoAhora(sin, d(2, 11), { aMano: { mundo: 'trabajo', desde: d(2, 10) } })).slice(0, 3), ['trabajo', 'a-mano', undefined]);

    // los cuatro modos: sus teclas, y al abrir Todo nunca es la de partida
    assert.deepEqual(MODOS.map(m => `${m.clave}:${m.tecla}`), ['tactica:1', 'estrategia:2', 'foco:3', 'todo:4']);
    assert.deepEqual(['todo', 'foco', 'estrategia', 'tactica', 'estandar', ''].map(alAbrir), ['tactica', 'foco', 'estrategia', 'tactica', 'tactica', 'tactica']);
    // la fila de los modos: el puesto marcado; ninguno lleva número, tampoco táctica
    const fila = modosEnFila('todo');
    assert.match(fila, /class="modos-modo si" data-accion="modos-modo" data-id="todo"/);
    assert.match(fila, /data-id="tactica"[^>]*><span class="i">.*?<\/span><span class="txt">táctica<\/span><\/a>/);
    assert.ok(!fila.includes('modos-numero'), 'táctica sin número');
    // el mundo: el planeta y su nombre en su color (hasta cuándo, en la ayuda); con ambos, sin color
    const martes = d(2, 11, 45);
    const boton = mundoBoton(mundoAhora(mundos, martes, o), mundos, martes);
    assert.match(boton, /style="--mundo-c: var\(--cian\)"><span class="i mundo-icono">.<\/span><span class="mundo-nombre">trabajo<\/span><\/a>$/u);
    assert.match(boton, /title="el mundo: trabajo \(por su horario\) · a las 19:00 pasa a/);
    const ambos = mundoBoton({ mundo: '', por: 'a-mano' }, mundos, martes);
    assert.match(ambos, /class="mundo-boton ambos"/);
    assert.ok(!ambos.includes('--mundo-c'), 'ambos, en el color del texto');
    assert.equal(decirMundo(mundoAhora(mundos, martes, { ...o, aMano }), mundos, martes).como, 'a mano, hasta las 19:00');
    // su menú (el del prototipo; en la página, la ventana de mundos): volver al horario solo si se eligió a mano; lo sin
    // clasificar, si hay
    const ids = (p, n) => opcionesMundo(p, mundos, n).filter(x => !x.separador).map(x => x.id);
    assert.deepEqual(ids(mundoAhora(mundos, martes, o), 0), ['trabajo', 'personal', '', '__editar']);
    assert.deepEqual(ids(mundoAhora(mundos, martes, { ...o, aMano }), 4), ['trabajo', 'personal', '', '__horario', '__sin', '__editar']);
    assert.equal(opcionesMundo(mundoAhora(mundos, martes, o), mundos, 0, 'personal')[1].description, 'fuera de todo horario');

    // Todo
    const T = await armar('todo');
    const { todo, barraTodo, cuantas, enOtros, resaltar, POR_FUENTE } = T;
    const f = (clave, cuenta) => ({ clave, nombre: clave, icono: 'I', color: 'cian', cuenta, dice: { trabajo: 'algo', '': 'todo' } });
    const fuentes = [f('tareas', { trabajo: 10, personal: 4, 'sin-clasificar': 2 }), f('correo', { trabajo: 3, personal: 1, 'sin-clasificar': 0 })];
    assert.deepEqual([cuantas(fuentes[0], 'trabajo'), enOtros(fuentes[0], 'trabajo'), cuantas(fuentes[0], ''), enOtros(fuentes[0], '')], [12, 4, 16, 0],
        'con un mundo: lo suyo y lo sin clasificar; lo de los otros, aparte');
    assert.equal(resaltar('Armar la Vitrina', 'vitrina'), 'Armar la <span class="todo-hallado">Vitrina</span>');
    assert.equal(resaltar('La vitrína', 'vitrina'), 'La <span class="todo-hallado">vitrína</span>', 'sin tildes ni mayúsculas');
    assert.ok(resaltar('<b>vitrina', 'vitrina').startsWith('&lt;b&gt;'), 'lo escrito se escapa');
    // sin buscar: una fila por fuente, con lo que queda en el otro mundo
    const sinBuscar = todo({ fuentes, mundos, puesto: 'trabajo' });
    assert.equal((sinBuscar.match(/class="item todo-fuente"/g) ?? []).length, 2);
    assert.match(sinBuscar, /data-valor="tareas".*tareas<\/span> <span class="item-sufijo">12<\/span>.*\+4 en personal/s);
    assert.match(sinBuscar, /id="todo-cuenta">15</, 'la cuenta del buscador: todo lo del mundo');
    // buscando: por fuente, hasta el tope y «+N más»; lo de los otros mundos, al final; lo sin clasificar, con su marca
    const c = (fuente, i, mundo = 'trabajo') => ({ fuente, id: `${fuente}:${i}`, titulo: `vitrina ${i}`, mundo });
    const halladas = [...[1, 2, 3, 4, 5, 6].map(i => c('tareas', i)), c('tareas', 7, 'personal'), c('correo', 8, 'sin-clasificar')];
    const buscando = todo({ fuentes, mundos, puesto: 'trabajo', buscado: 'vitrina', halladas });
    assert.equal((buscando.match(/data-valor="tareas:\d"/g) ?? []).length, POR_FUENTE + 1, `${POR_FUENTE} del mundo y la del otro, al final`);
    assert.match(buscando, /\+2 más<\/span> <span class="item-sufijo tono-tenue">en tareas, con «vitrina»/);
    assert.ok(buscando.indexOf('data-valor="correo:8"') < buscando.indexOf('en otros mundos'), 'lo sin clasificar va con lo del mundo');
    assert.match(buscando, /data-valor="correo:8".*todo-mundo sin">sin clasificar/s);
    assert.match(buscando, /en otros mundos.*data-valor="tareas:7".*style="--mundo-c: var\(--magenta\)">personal/s);
    assert.match(buscando, /id="todo-cuenta">7 de 15</);
    assert.match(buscando, /data-accion="todo-filtro" data-id="fuente:tareas".*filtros-cuenta">6</s, 'cuántas de cada fuente');
    // con ambos, nada va a «otros mundos»: cada una dice el suyo
    const conAmbos = todo({ fuentes, mundos, puesto: '', buscado: 'vitrina', halladas });
    assert.ok(!conAmbos.includes('en otros mundos'));
    // una fuente entera: lo hecho, al final; la barra vuelve a Todo
    const entera = todo({ fuentes, mundos, puesto: 'trabajo', abierta: { fuente: 'tareas', total: 12,
        cosas: [{ ...c('tareas', 1), pasada: true }, c('tareas', 2)] } });
    assert.ok(entera.indexOf('tareas:2') < entera.indexOf('hechas y descartadas') && entera.indexOf('hechas y descartadas') < entera.indexOf('tareas:1'));
    assert.match(entera, /… y 10 más/);
    assert.equal(barraTodo({ fuentes, mundos, puesto: 'trabajo' }).resumen, '15 en trabajo · y 5 en los otros');
    const bt = barraTodo({ fuentes, mundos, puesto: 'trabajo', abierta: { fuente: 'tareas', total: 12, cosas: [] } });
    assert.deepEqual([bt.nombre, bt.volver?.accion, bt.resumen], ['tareas', 'todo-volver', '12 · todas, sin filtros · trabajo']);
    // filtrado a una fuente, todo lo suyo, sin «+N más» (una sin pestaña, como los objetos de un módulo, se ve entera así)
    const filtrado = todo({ fuentes, mundos, puesto: 'trabajo', buscado: 'vitrina', halladas, filtro: 'tareas' });
    assert.equal((filtrado.match(/data-valor="tareas:\d"/g) ?? []).length, 7, 'las seis del mundo y la del otro');
    assert.ok(!filtrado.includes('más</span>'));
    assert.ok(!filtrado.includes('correo:8'), 'solo la fuente filtrada');
    // en la página (vistas/dashboard/todo.ts): los documentos de un grafo, una fuente más (`objeto:doc`), con su ícono y
    // su tinta; lo que no tiene fecha dice su estado al final («12 conexiones»); el mundo ordena: el del otro, al final
    const outfile = path.join(path.dirname(salida), 'todo-vista.cjs');
    await build({ entryPoints: [path.join(aqui, '..', 'src', 'vistas', 'dashboard', 'todo.ts')], bundle: true, platform: 'node', format: 'cjs', outfile, logLevel: 'warning' });
    const { cosaDe, deFuente } = require(outfile);
    const iconos = path.join(path.dirname(salida), 'iconos.cjs');
    await build({ entryPoints: [path.join(aqui, '..', 'src', 'web', 'iconos.ts')], bundle: true, platform: 'node', format: 'cjs', outfile: iconos, logLevel: 'warning' });
    const { I } = require(iconos);
    assert.deepEqual(deFuente('objeto:doc'), [I.documento, 'amarillo']);
    assert.deepEqual(deFuente('objeto:decision'), [I.ficha, 'blanco'], 'el tipo de otro módulo: el de los objetos');
    assert.deepEqual(deFuente('bloque:correo'), [I.ventana, 'violeta']);
    const doc = (titulo, mundo, n) => ({ fuente: 'objeto:doc', direccion: `doc:${titulo}.md`, id: `${titulo}.md`, titulo, donde: `notas/${titulo}.md`,
        cuando: '', estado: `${n} conexiones`, pasada: false, mundo, datos: { ruta_abs: `/casa/notas/${titulo}.md` } });
    const unDoc = cosaDe(doc('vitrina', 'trabajo', 12), 'objeto:doc|0');
    assert.deepEqual([unDoc.titulo, unDoc.donde, unDoc.meta, unDoc.mundo], ['vitrina', 'notas/vitrina.md', '12 conexiones', 'trabajo']);
    assert.equal(cosaDe({ ...doc('x', 'trabajo', 1), fuente: 'tareas', estado: 'activa' }, 'tareas|0').meta, '', 'una tarea sin fecha no dice su estado');
    const conDocs = todo({ fuentes: [...fuentes, { clave: 'objeto:doc', nombre: 'documentos', icono: I.documento, color: 'amarillo', cuenta: {}, dice: {} }],
        mundos, puesto: 'trabajo', buscado: 'vitrina',
        halladas: [cosaDe(doc('vitrina vieja', 'personal', 3), 'objeto:doc|0'), cosaDe(doc('vitrina', 'trabajo', 12), 'objeto:doc|1')] });
    assert.match(conDocs, /data-fuente="objeto:doc">.*documentos.*data-valor="objeto:doc\|1".*12 conexiones/s);
    assert.ok(conDocs.indexOf('objeto:doc|1') < conDocs.indexOf('en otros mundos') && conDocs.indexOf('en otros mundos') < conDocs.indexOf('objeto:doc|0'),
        'el documento personal, al final, en otros mundos');
}
// 18. el mundo puesto de la página (web/mundo.ts): lo elegido a mano, el siguiente, lo que se ve (lo suyo y lo sin
// clasificar), y en todo (el modo), que solo ordena. Sin horarios, para no depender de la hora en que corre la prueba
{
    const outfile = path.join(path.dirname(salida), 'mundo-web.cjs');
    await build({ entryPoints: [path.join(aqui, '..', 'src', 'web', 'mundo.ts')], bundle: true, platform: 'node', format: 'cjs', outfile, logLevel: 'warning' });
    const W = require(outfile);
    const avisos = [];
    W.alCambiar(() => avisos.push(W.puesto().mundo));
    assert.ok(W.seVe('trabajo') && W.seVe(''), 'sin [mundos], todo se ve');
    W.recibir({ mundos: [{ nombre: 'trabajo', color: 'cian', horario: [] }, { nombre: 'personal', color: 'magenta', horario: [] }], mundos_fuera: '' });
    assert.deepEqual([W.puesto().mundo, W.puesto().por], ['', 'sin-horario'], 'sin horarios ni nada elegido: ambos');
    W.poner('personal');
    assert.deepEqual([W.puesto().mundo, W.puesto().por, W.filtrando()], ['personal', 'a-mano', 'personal']);
    assert.ok(W.seVe('personal') && W.seVe('') && W.seVe(undefined) && !W.seVe('trabajo'), 'lo suyo y lo sin clasificar');
    W.poner('casa');
    assert.equal(W.puesto().mundo, 'personal', 'uno que no se declara no se pone');
    W.ordenarSolo(true);
    assert.ok(W.seVe('trabajo') && W.filtrando() === '', 'en todo, el mundo ordena y no esconde');
    assert.ok(!W.enElPuesto('trabajo') && W.enElPuesto('personal') && W.enElPuesto(''), 'pero la barra obedece al mundo también en todo');
    W.ordenarSolo(false);
    W.siguiente();
    assert.equal(W.puesto().mundo, '', 'después de personal (el último), ambos');
    W.siguiente();
    assert.deepEqual([W.puesto().mundo, W.puesto().por], ['', 'sin-horario'], 'y de ambos, de vuelta al horario');
    W.siguiente();
    assert.equal(W.puesto().mundo, 'trabajo');
    W.volverAlHorario();
    assert.equal(W.puesto().por, 'sin-horario');
    assert.ok(avisos.length >= 6, 'cada cambio avisa');
    assert.equal(W.mundo(), undefined);
}
// 19. las iniciativas en la pantalla de proyectos (vistas/dashboard/iniciativas.ts): lo que se lee de su frontmatter, sus
// grupos por programa (la que se llama como el programa lo encabeza; las sin programa ni hijas, en «sin programa», al final) y
// sus filas, que se eligen como las de un proyecto
{
    const outfile = path.join(path.dirname(salida), 'iniciativas.cjs');
    await build({ entryPoints: [path.join(aqui, '..', 'src', 'vistas', 'dashboard', 'iniciativas.ts')], bundle: true, platform: 'node', format: 'cjs', outfile, logLevel: 'warning' });
    const N = require(outfile);
    const u = (slug, nombre, fm = {}, o = {}) => ({ ruta: `casa/iniciativas/${slug}`, nombre, arquetipo: 'iniciativa', modificado: null, hilo: '', vivo: false, frontmatter: fm, ...o });
    const club = u('club-lectura', 'Club de lectura', { estado: 'en curso', dueno: 'Ana', peso: 'alto' });
    const canales = u('canales', 'Canales', { programa: 'club-lectura', dueno: 'Ana', peso: 'medio', proxima_decision: '¿Abrimos <el> canal?' });
    const boletin = u('boletin', 'Boletín', { programa: 'Club-Lectura' }, { estado: 'Activo' });
    const encuentros = u('encuentros', 'Encuentros', { programa: 'club-lectura', peso: 'alto' });
    const costos = u('costos', 'Tablero de costos', { programa: 'gestion', peso: 'Bajo' });
    const inventario = u('inventario', 'Inventario', { dueno: 'Bruno' });
    const bodega = u('bodega', 'Bodega', { peso: 'enorme' });
    const todas = [inventario, costos, boletin, canales, club, encuentros, bodega];
    // lo que se lee: el estado del frontmatter o, si no lo dice, el de su tabla; un peso que no es alto, medio ni bajo no va
    assert.deepEqual(N.deIniciativa(canales, 'programa'), { dueno: 'Ana', estado: '', proxima: '¿Abrimos <el> canal?', peso: 'medio', grupo: 'club-lectura', programa: 'club-lectura',
        visto: { escrito: '', valor: '', fuera: false, fuente: '', cambia: false } });
    assert.equal(N.deIniciativa(boletin, 'programa').estado, 'Activo');
    assert.equal(N.deIniciativa(costos, 'programa').peso, 'bajo');
    assert.equal(N.deIniciativa(bodega, 'programa').peso, undefined);
    assert.equal(N.deIniciativa(canales, '').grupo, '', 'sin campo, sin grupo');
    // los grupos: el programa con la suya primero (sus hijas por peso y nombre), el que no la tiene después, y las sin programa
    const gs = N.agrupar(todas, 'programa');
    assert.deepEqual(gs.map(g => [g.clave, g.nombre, g.cabeza?.nombre ?? null, g.hijas.map(x => x.nombre)]), [
        ['club-lectura', 'Club de lectura', 'Club de lectura', ['Encuentros', 'Canales', 'Boletín']],
        ['gestion', 'gestion', null, ['Tablero de costos']],
        ['', 'sin programa', null, ['Bodega', 'Inventario']],
    ]);
    assert.equal(N.programas(gs), 2);
    assert.deepEqual(N.agrupar(todas, '').map(g => [g.nombre, g.hijas.length]), [['', 7]], 'sin agrupar, todas juntas');
    assert.deepEqual(N.agrupar([], 'programa'), []);
    // la que encabeza no va dentro de su grupo aunque diga ser de él
    const propia = u('club-lectura', 'Club', { programa: 'club-lectura' });
    assert.deepEqual(N.agrupar([propia, canales], 'programa').map(g => [g.cabeza?.nombre, g.hijas.map(x => x.nombre)]), [['Club', ['Canales']]]);
    // la sección: su cabecera (un clic la deja sola), las columnas, la que encabeza con cuántas tiene, las suyas corridas
    const h = N.htmlIniciativas(todas, 'programa', { sel: canales.ruta, cuentas: new Map([[canales.ruta, 3]]) });
    assert.match(h, /^<div id="iniciativas" style="--ini-estado: 11ch"><div class="fila proy-sec-cab ini-sec-cab clic" data-accion="proy-iniciativas"/,
        'el ancho del estado, el de lo más largo que muestra («sin estado»)');
    assert.match(h, /iniciativas <span class="proy-sec-n">7<\/span> <span class="ini-programas">· 2 programas<\/span>/);
    assert.match(h, /class="fila clic proy ini ini-cabeza" data-accion="proy-sel" data-valor="casa\/iniciativas\/club-lectura" data-grupo="club-lectura"/);
    assert.match(h, /Club de lectura<\/span><span class="ini-n" title="3 en este programa">3<\/span>/);
    assert.match(h, /class="fila clic proy ini sel ini-hija" data-accion="proy-sel" data-valor="casa\/iniciativas\/canales"[^>]*data-pend="3"/, 'la elegida, con sus pendientes');
    assert.match(h, /<div class="fila ini-grupo" data-grupo="gestion"/, 'un programa sin la suya: su nombre');
    assert.match(h, /<div class="fila ini-grupo ini-sueltas" data-grupo=""[^>]*><span class="at"><\/span><span class="que"><span class="ini-nombre">sin programa<\/span><span class="ini-n">2<\/span>/);
    assert.ok(h.indexOf('ini-cabeza') < h.indexOf('data-grupo="gestion"') && h.indexOf('data-grupo="gestion"') < h.indexOf('ini-sueltas'), 'en su orden');
    assert.ok(h.includes('&lt;el&gt;') && !h.includes('<el>'), 'lo escrito se escapa');
    assert.match(h, /<span class="senal" title="peso medio"><span class="circulo tam-chico" style="--lleno: 50%"><\/span><\/span>/, 'el peso, el círculo de Táctica');
    const sola = N.htmlIniciativas(todas, 'programa', { solo: true });
    assert.ok(!sola.includes('ini-sec-cab') && sola.includes('ini-cols'), 'sola, sin su cabecera: la dice la barra');
    assert.equal(N.htmlIniciativas([], 'programa'), '', 'sin iniciativas, nada');
    // cómo va, para el detalle
    assert.deepEqual(N.comoVaIniciativa(canales, 'programa').partes, ['<span class="ini-estado" title="sin estado"><span class="ini-e-txt dim">sin estado</span></span>',
        'Ana', 'próxima decisión: ¿Abrimos &lt;el&gt; canal?', 'peso medio', 'programa club-lectura']);

    // el estado, con el vocabulario de `[iniciativas]`: su círculo y su color, un sinónimo como el suyo, uno fuera del
    // vocabulario marcado, y las de una fuente externa (su ficha dice `estado_fuente`) con «fuente: …» y sin el clic que
    // lo cambia; con vocabulario, el estado es el de su frontmatter (el de su tabla no cuenta), y su nota va al pasar
    const VOC = N.vocabularioDe({ estados: ['idea', 'diseño', 'en curso', 'en pausa', 'terminada', 'descartada'],
        sinonimos: { activo: 'en curso', activa: 'en curso' }, clases: {}, fuentes: { sheet: 'Sheet' } });
    assert.deepEqual(N.vocabularioDe(undefined), N.SIN_VOCABULARIO, 'un telar sin [iniciativas]: sin vocabulario');
    assert.deepEqual(['idea', 'Diseño', 'en curso', 'En pausa', 'terminada', 'descartada', 'piloto'].map(e => N.claseDe(e, VOC)),
        ['idea', 'preparacion', 'curso', 'pausa', 'terminada', 'descartada', undefined], 'la clase, de su nombre');
    assert.equal(N.claseDe('piloto', { ...VOC, clases: { piloto: 'curso' } }), 'curso', 'o la que declara `clases`');
    const plan = u('plan-anual', 'Plan anual', { estado: 'activo' });
    const activa = u('activa', 'Activa', { programa: 'plan-anual', estado: 'Activa' });
    const p01 = u('p01-encuesta', 'Encuesta', { programa: 'Plan-Anual', estado: 'idea', estado_fuente: 'sheet', estado_nota: 'la sincroniza la planilla' });
    const p02 = u('p02-base', 'Base común', { programa: 'plan-anual', estado: 'En curso', estado_fuente: 'pmo' });
    const piloto = u('piloto', 'Piloto', { estado: 'piloto', estado_nota: 'espera <la> reunión' });
    const sinEstado = u('suelta', 'Suelta');
    const e = x => N.estadoDe(x, VOC);
    assert.deepEqual(e(club), { escrito: 'en curso', valor: 'en curso', fuera: false, clase: 'curso', fuente: '', cambia: true }, 'del vocabulario: se cambia aquí');
    assert.deepEqual(e(activa), { escrito: 'Activa', valor: 'en curso', fuera: false, clase: 'curso', fuente: '', cambia: true },
        'un sinónimo: se ve como el suyo, y lo escrito queda dicho; de un programa, sin estado_fuente: se cambia aquí');
    assert.deepEqual(e(boletin), { escrito: '', valor: '', fuera: false, fuente: '', cambia: true }, 'el Estado de su tabla no cuenta: sin estado, se le pone uno');
    assert.deepEqual(e(piloto), { escrito: 'piloto', valor: 'piloto', fuera: true, fuente: '', cambia: true, nota: 'espera <la> reunión' },
        'fuera del vocabulario: tal cual, y se cambia; con su nota');
    assert.deepEqual(e(p01), { escrito: 'idea', valor: 'idea', fuera: false, clase: 'idea', fuente: 'Sheet', cambia: false, nota: 'la sincroniza la planilla' },
        'su ficha dice su fuente: no se cambia aquí, con el nombre que le da la configuración');
    assert.deepEqual([e(p02).valor, e(p02).fuente, e(p02).cambia], ['en curso', 'pmo', false], 'una fuente que la configuración no nombra: tal cual');
    assert.deepEqual([e(plan).fuente, e(plan).cambia], ['', true]);
    assert.deepEqual(e(sinEstado), { escrito: '', valor: '', fuera: false, fuente: '', cambia: true }, 'sin estado: se elige uno');
    assert.deepEqual([N.estadoDe(boletin).valor, N.estadoDe(boletin).cambia, N.estadoDe(piloto).fuera, N.estadoDe(p01).fuente], ['Activo', false, false, 'sheet'],
        'sin vocabulario: lo escrito (o el de su tabla), nada está fuera y no se cambia aquí; la fuente, como la dice');
    const hv = N.htmlIniciativas([club, boletin, piloto, plan, activa, p01, p02, sinEstado], 'programa', { voc: VOC });
    const fila = ruta => hv.slice(hv.indexOf(`data-valor="casa/iniciativas/${ruta}"`), hv.indexOf('</div>', hv.indexOf(`data-valor="casa/iniciativas/${ruta}"`)));
    const celda = ruta => /<span class="estado-p ini-estado[^"]*"[^>]*>.*?<\/span><span class="ini-fuente"[^>]*>[^<]*<\/span>/s.exec(fila(ruta))?.[0] ?? '';
    assert.match(hv, /^<div id="iniciativas" class="con-fuente" style="--ini-estado: 11ch; --ini-fuente: 14ch">/,
        'con alguna de fuente externa, su columna, del ancho de «fuente: Sheet»; el estado, del de «○ piloto ⚠»');
    assert.match(celda('club-lectura'), /^<span class="estado-p ini-estado cambia" data-accion="ini-estado" data-valor="casa\/iniciativas\/club-lectura" data-estado="en curso" data-clase="curso" title="estado: en curso\nclic: cambiarlo">/,
        'del vocabulario: el clic lo cambia (no elige la fila)');
    assert.match(celda('club-lectura'), /<span class="senal tono-trabajando"><span class="circulo tam-chico" style="--lleno: 50%"><\/span><\/span><span class="ini-e-txt">en curso<\/span>/,
        'su círculo, en el color de su clase');
    assert.match(celda('activa'), /data-estado="en curso" data-clase="curso" title="estado: en curso\nsu ficha dice «Activa», que vale como «en curso»/, 'el sinónimo, como el suyo');
    assert.match(celda('piloto'), /class="estado-p ini-estado cambia fuera" data-accion="ini-estado"[^>]*title="estado: piloto\nespera &lt;la&gt; reunión\nfuera del vocabulario/,
        'fuera del vocabulario: marcado, y se cambia; su nota, al pasar');
    assert.match(celda('piloto'), /<span class="senal tono-atencion"><span class="circulo tam-chico" style="--lleno: 0%"><\/span><\/span><span class="ini-e-txt tono-atencion">piloto<\/span><span class="i ini-fuera tono-atencion" title="fuera del vocabulario: idea, diseño, en curso, en pausa, terminada, descartada">/);
    assert.ok(!celda('p01-encuesta').includes('data-accion'), 'la de fuente externa no tiene el clic que lo cambia');
    assert.match(celda('p01-encuesta'), /title="estado: idea\nla sincroniza la planilla\nfuente: Sheet: se cambia allá, no aquí">.*<span class="ini-fuente" title="su estado lo manda Sheet: se cambia allá">fuente: Sheet<\/span>$/s);
    assert.match(celda('p02-base'), /data-clase="curso"[\s\S]*fuente: pmo/);
    assert.match(celda('suelta'), /data-accion="ini-estado"[\s\S]*<span class="ini-e-txt dim">sin estado<\/span>/, 'sin estado: se elige uno');
    assert.match(celda('boletin'), /data-accion="ini-estado"[\s\S]*<span class="ini-e-txt dim">sin estado<\/span>/, 'solo en su tabla: sin estado');
    assert.match(celda('plan-anual'), /data-accion="ini-estado"[\s\S]*<span class="ini-fuente" title="">/, 'la que encabeza, sin fuente');
    assert.ok(!N.htmlIniciativas([club, piloto], 'programa', { voc: VOC }).includes('con-fuente'), 'sin ninguna de fuente externa, sin su columna');
    assert.ok(!N.htmlIniciativas([club], 'programa').includes('data-accion="ini-estado"'), 'sin vocabulario, no se cambia aquí');
    // el detalle: el estado (un clic lo cambia), desde cuándo, su nota y la fuente
    const conDesde = u('club-lectura', 'Club', { estado: 'activa', estado_desde: '2026-11-02', estado_nota: 'abrió la <segunda> cohorte' });
    assert.match(N.comoVaIniciativa(conDesde, 'programa', VOC).partes[0],
        /^<a class="ini-estado cambia" data-accion="ini-estado" data-valor="casa\/iniciativas\/club-lectura"[\s\S]*<b>en curso<\/b><\/span><\/a> <span class="dim">desde 2026-11-02<\/span> <span class="dim ini-nota">\(abrió la &lt;segunda&gt; cohorte\)<\/span>$/);
    assert.deepEqual(N.comoVaIniciativa(p01, 'programa', VOC).partes.slice(0, 2).map(x => x.replace(/<[^>]+>/g, '')), ['idea (la sincroniza la planilla)', 'fuente: Sheet']);
}
// un ensayo de Táctica (`window.telar.ensayoTactica`) no sale a la API que escribe: sus tareas son de mentira y sus números
// pueden ser los de tareas de verdad. Cada acción de su HTML es de las que Táctica atiende sin tocarla (DE_ENSAYO); lo demás
// (hecha, la instrucción, el ⋯, abrir su ficha, llevarla a su hilo, preparar la reunión, entrar a la llamada) va como
// `tactica-ensayo`, que solo lo dice
{
    const dir = path.dirname(salida);
    const entrada = path.join(dir, 'ensayo-tactica.ts');
    const src = path.join(aqui, '..', 'src');
    (await import('node:fs')).writeFileSync(entrada, [
        `export { ESTADOS } from ${JSON.stringify(path.join(src, 'componentes', 'muestras-tactica.ts'))};`,
        `export { tactica, DISPOSICIONES } from ${JSON.stringify(path.join(src, 'componentes', 'tactica.ts'))};`,
        `export { deEnsayo, DE_ENSAYO } from ${JSON.stringify(path.join(src, 'vistas', 'dashboard', 'tactica.ts'))};`,
    ].join('\n'));
    const outfile = path.join(dir, 'ensayo-tactica.cjs');
    await build({ entryPoints: [entrada], bundle: true, platform: 'node', format: 'cjs', outfile, logLevel: 'warning' });
    const E = require(outfile);
    const acciones = h => [...h.matchAll(/data-accion="([^"]+)"/g)].map(m => m[1]);
    let afuera = 0;
    for (const est of E.ESTADOS) {
        for (const d of E.DISPOSICIONES) {
            const t = est.tactica(d.clave, ['decidir|cliente:feria']);
            afuera += acciones(E.tactica(t)).filter(a => !E.DE_ENSAYO.has(a)).length;
            const h = E.tactica(E.deEnsayo(t));
            const fuera = [...new Set(acciones(h).filter(a => !E.DE_ENSAYO.has(a)))];
            assert.deepEqual(fuera, [], `ensayo «${est.clave}» (${d.clave}): estas acciones saldrían a la API: ${fuera.join(', ')}`);
            assert.ok(!/data-url=/.test(h), `ensayo «${est.clave}»: nada abre una dirección de verdad`);
        }
    }
    assert.ok(afuera > 0, 'sin deEnsayo, las filas sí llevan lo que sale a la API (hecha, la instrucción, el ⋯): la prueba lo vería');
    // lo que habría hecho queda en su valor, para decirlo
    const t = E.ESTADOS[0].tactica('lado');
    const hecha = E.deEnsayo(t).hacer.flatMap(q => q.acciones ?? []).find(a => JSON.parse(a.datos.valor)[0] === 'hecha-fila');
    assert.equal(hecha.accion, 'tactica-ensayo');
    assert.equal(JSON.parse(JSON.parse(hecha.datos.valor)[1])[1], JSON.parse(t.hacer.flatMap(q => q.acciones ?? []).find(a => a.accion === 'hecha-fila').datos.valor)[1]);
}

// 20. las barras de arriba (la de una pantalla, la franja de avisos, la del lado) miden --pantalla-barra-alto con su relleno y
// su línea, para que sus líneas de abajo calcen como una sola: cada una lo dice (border-box), y la vista que pone
// content-box a todo lo suyo (el dashboard, dia.css, en la capa que gana) se lo devuelve a la barra de la pantalla. Sin
// esto, la barra del dashboard medía 2 × --e-1 y un píxel más que la franja de al lado (18-nov-2026).
{
    const { readFileSync, readdirSync } = await import('node:fs');
    const carpetaCss = path.join(aqui, '..', 'media', 'css');
    const hojas = Object.fromEntries(readdirSync(carpetaCss).filter(f => f.endsWith('.css')).map(f => [f, readFileSync(path.join(carpetaCss, f), 'utf8')]));
    // los bloques que fijan el alto de una barra: el selector que abre la llave y lo que va hasta su primera regla anidada o su cierre
    const conAlto = [];
    for (const [f, css] of Object.entries(hojas)) {
        for (const m of css.matchAll(/([^{};\n]+)\{([^{}]*?height:\s*var\(--pantalla-barra-alto\)[^{}]*)/g)) conAlto.push([f, m[1].trim(), m[2]]);
    }
    const selectores = conAlto.map(([, sel]) => sel);
    for (const quien of ['.pantalla-barra', '.franja', '& .lado-barra', '.buscador-barra']) assert.ok(selectores.includes(quien), `${quien} mide --pantalla-barra-alto`);
    for (const [f, sel, cuerpo] of conAlto) assert.match(cuerpo, /box-sizing:\s*border-box/, `${f} ${sel}: el alto cuenta el relleno y la línea (border-box)`);
    for (const [f, css] of Object.entries(hojas)) {
        if (!/\*\s*\{\s*box-sizing:\s*content-box;?\s*\}/.test(css)) continue;
        assert.match(css, /\.pantalla-barra\s*\{\s*box-sizing:\s*border-box;?\s*\}/, `${f} pone content-box a todo: le devuelve border-box a la barra de la pantalla`);
        assert.match(css, /\.buscador-barra\s*\{\s*box-sizing:\s*border-box;/, `${f} pone content-box a todo: le devuelve border-box a la barra de un buscador`);
    }
}

// 21. el botón con texto (componentes/boton.ts, «la tecla en el pie», elegida el 22-nov-2026) y su página en el catálogo
// (catalogo-botones.ts): un <button> de verdad, en minúscula, con el color de lo que hace; la tecla (o, sin ella, el ícono)
// delante de la palabra; los estados puestos a mano son clases; y en una ventana de confirmar, lo que destruye nunca lleva ⏎
// y el foco parte en cancelar. Las teclas y cada confirmación de la página, en prueba:confirmar.
{
    const { boton, pieBotones, minuscula, cancelar } = await armar('boton');
    const B = { texto: 'Borrar', accion: 'borrar', tono: 'peligro', tecla: '⌘⌫', icono: 'X', ayuda: 'borra' };
    assert.equal(boton(B), '<button type="button" class="boton tono-peligro" data-accion="borrar" data-tecla="⌘⌫" aria-keyshortcuts="Meta+Backspace" title="borra">'
        + '<span class="boton-tecla">⌘⌫</span><span class="boton-texto">borrar</span></button>', 'un <button>, en minúscula, con la tecla delante');
    assert.match(boton({ ...B, tecla: undefined }), /<span class="boton-tecla boton-icono i">X<\/span><span class="boton-texto">borrar<\/span>/, 'sin tecla, su ícono en su lugar');
    assert.match(boton({ ...B, tecla: '⏎' }), /data-tecla="⌘⌫"/, 'lo que destruye nunca dice ⏎');
    assert.match(boton({ texto: 'cancelar', accion: 'no' }), /class="boton tono-accion"/, 'sin tono, el de una acción');
    assert.match(boton({ ...B, estado: 'hover' }), /class="boton tono-peligro es-hover"/);
    assert.match(boton({ ...B, estado: 'foco' }), /class="boton tono-peligro es-foco"/);
    assert.match(boton({ ...B, estado: 'deshabilitado' }), /class="boton tono-peligro"[^>]* disabled>/, 'apagado: disabled, no una clase');
    assert.match(boton({ ...B, enCurso: '<i>o</i>' }), /disabled><span class="boton-tecla boton-gira"><i>o<\/i><\/span>/, 'mientras se hace: apagado, y lo que gira en el lugar de la tecla');
    assert.match(boton({ texto: 'archivar', accion: 'a', color: 'amarillo' }), /style="--c: var\(--amarillo\)"/, 'el color de su clase');
    assert.match(boton({ texto: 'x', datos: { contestar: 'hacer' } }), /^<button type="button" class="boton tono-accion" data-contestar="hacer">/, 'otros data-*, sin data-accion');
    assert.match(boton({ texto: '<b>', accion: '"x"' }), /data-accion="&quot;x&quot;".*&lt;b&gt;/, 'lo escrito se escapa');
    assert.equal(minuscula('Sí'), 'sí'); assert.equal(minuscula('Cancelar el encargo'), 'cancelar el encargo');
    assert.equal(minuscula('T84'), 'T84', 'una sigla queda'); assert.equal(minuscula('OK'), 'OK');
    assert.match(pieBotones([B]), /^<div class="ventana-pie botonera"><button /, 'el pie de una ventana: la banda');
    assert.match(pieBotones([B], { izq: '<a>x</a>', clase: 'c' }), /^<div class="ventana-pie botonera c"><span class="botonera-izq"><a>x<\/a><\/span><button /, 'lo de la izquierda, antes de las celdas');
    assert.deepEqual([cancelar().accion, cancelar().tecla, cancelar().tono, 'accion' in cancelar('no', null)], ['no', '⎋', 'callado', false], 'cancelar: ⎋, callado');

    const BT = await armar('catalogo-botones');
    assert.notEqual(BT.BORRAR.tecla, '⏎', 'lo que destruye nunca se hace con ⏎ solo');
    const botones = html => [...html.matchAll(/<button [^>]*class="([^"]+)" data-accion="([^"]+)"/g)].map(m => ({ clase: m[1], accion: m[2] }));
    for (const e of BT.ESCENAS) {
        const bs = botones(e.html());
        assert.ok(['cancelar', 'no'].includes(bs.at(-1).accion), `${e.clave}: cancelar, al último`);
        const foco = bs.filter(b => /\bes-foco\b/.test(b.clase));
        assert.equal(foco.length, 1, `${e.clave}: un solo botón con el foco`);
        const peligro = bs.some(b => /tono-peligro/.test(b.clase));
        if (peligro) assert.equal(foco[0].accion, bs.at(-1).accion, `${e.clave}: en lo que destruye, el foco en cancelar`);
    }
    const estados = BT.filasEstados();
    assert.deepEqual(estados.slice(0, 4).map(x => x.nombre), ['normal', 'al pasar el mouse', 'con el foco', 'apagado'], 'los cuatro estados');
    assert.equal((estados[3].html.match(/ disabled>/g) ?? []).length, 3, 'apagados, los tres');
    assert.equal(BT.DESCARTADAS.length, 3, 'las tres formas descartadas, con por qué');
    assert.ok(BT.CONFIRMACIONES.length >= 25 && BT.CONFIRMACIONES.every(c => c.archivo && c.clase && c.por), 'el catastro: cada confirmación con su archivo, su clase y por qué');

    // su CSS: sin esquinas redondeadas ni otro tamaño de letra; el foco con :focus (no :focus-visible), con sus estados
    const { readFileSync } = await import('node:fs');
    const css = readFileSync(path.join(aqui, '..', 'media', 'css', 'boton.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
    assert.ok(!/border-radius:(?!\s*0\s*;)/.test(css), 'sin esquinas redondeadas');
    assert.ok(!/font-size|font-weight:\s*bold/.test(css), 'nunca otro tamaño ni otro peso');
    assert.ok(!/:focus-visible/.test(css), 'el foco se marca con :focus: tiene que verse aunque se haya abierto con el mouse');
    assert.ok(css.includes('.es-hover') && css.includes(':focus, &.es-foco'), 'al pasar y con el foco, de verdad y puestos a mano');
    assert.ok(!/forma-(palabra|borde|icono|tecla)/.test(css), 'una sola forma: las descartadas no quedan');
}

console.log('componentes: ok');
