// Prueba de la pantalla de proyectos (src/vistas/dashboard/proyectos.ts, media/css/proyectos.css): lo que la auditoría
// (docs/propuestas/auditoria-proyectos.md) encontró y se arregló, para que no vuelva. Corre en Node, sin página:
// npm run prueba:proyectos
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
const salida = path.join(mkdtempSync(path.join(tmpdir(), 'proyectos-')), 'proyectos.cjs');
await build({ stdin: { contents: [
    "export { htmlListaProyectos, filtrosProyectos } from './vistas/dashboard/proyectos';",
    "export { htmlIniciativas, filtrosIniciativas, vocabularioDe } from './vistas/dashboard/iniciativas';",
    "export { htmlNegocios, etapaNegocio } from './vistas/dashboard/negocios';",
    "export { primeraCasilla, htmlDetalleProyecto, verReadme } from './vistas/dashboard/proyectos';",
    "export { fueraDeLaBarra } from './componentes/pantalla';",
    "export { montarDia } from './vistas/dashboard/vista';",
    "export { I } from './web/iconos';",
].join('\n'), resolveDir: src, loader: 'ts' }, bundle: true, platform: 'node', format: 'cjs', outfile: salida, logLevel: 'warning' });
// lo que la página toca al cargar, en un DOM de mentira (el de la página entera, para montar el dashboard)
const w = new Window({ url: 'http://localhost/' });
globalThis.window ??= w;
globalThis.document ??= w.document;
globalThis.localStorage ??= w.localStorage;
globalThis.CSS ??= { escape: (t) => String(t).replace(/["\\]/g, '\\$&') };
for (const k of ['HTMLElement', 'HTMLDetailsElement', 'HTMLTextAreaElement', 'HTMLInputElement', 'HTMLAnchorElement', 'Element', 'Node']) globalThis[k] ??= w[k];
globalThis.getComputedStyle ??= w.getComputedStyle.bind(w);
const P = require(salida);
/** El HTML, en un DOM: para preguntarle con selectores. */
const dom = (html) => { const d = w.document.createElement('div'); d.innerHTML = html; return d; };
const css = readFileSync(path.join(aqui, '..', 'media', 'css', 'proyectos.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');

/** Las reglas de un CSS, en orden: su selector (o su @-regla) y en qué @container va (o ''), sin bajar a las de adentro
 *  de una regla común. Basta para este archivo: llaves sin escapar, sin cadenas con llaves. */
function reglas(texto) {
    const salida = [];
    const pila = [];
    let desde = 0;
    for (let i = 0; i < texto.length; i++) {
        const c = texto[i];
        if (c === '{') {
            const cabeza = texto.slice(desde, i).trim().split(';').pop().trim();
            const contenedor = pila.findLast(x => x.startsWith('@container')) ?? '';
            salida.push({ cabeza, contenedor, pos: i, hondo: pila.length });
            pila.push(cabeza);
            desde = i + 1;
        } else if (c === '}') {
            pila.pop();
            desde = i + 1;
        } else if (c === ';') desde = i + 1;
    }
    return salida;
}

// 1. en una columna (el teléfono), el detalle se suelta: sin sticky, sin alto máximo y sin su scroll. La regla que lo
//    suelta (en el @container) tiene la misma especificidad que la de siempre de #proy-det: va después, o pierde (iba
//    antes, y en una columna el detalle seguía pegado, con su caja y su scroll)
{
    const rs = reglas(css);
    const siempre = rs.filter(r => !r.contenedor && r.cabeza.split(',').map(s => s.trim()).includes('#proy-det'));
    const suelta = rs.filter(r => r.contenedor && r.cabeza.split(',').map(s => s.trim()).includes('#proy-det'));
    assert.ok(siempre.length, 'la regla de siempre de #proy-det');
    assert.ok(suelta.length, 'la que lo suelta en una columna');
    for (const s of siempre) for (const u of suelta) {
        assert.ok(u.pos > s.pos, `la de una columna (${u.contenedor}) va después de la de siempre: si no, nunca rige`);
    }
}

// 2. la lista con las piezas de la casa: cada fila un ítem (componentes/item.ts), cada sección una seccion() con su
//    separador, el orden y los filtros estándar; sin la columna del estado (la dice la cabecera de la sección); el nombre
//    se lleva lo que sobra y lo que cede (el plazo, cuántos pendientes) va al final, en la meta
{
    const en = (dias) => new Date(Date.now() + dias * 864e5).toISOString().slice(0, 10);
    const p = (slug, nombre, o = {}) => ({ ruta: `casa/proyectos/${slug}`, nombre, arquetipo: 'proyecto', modificado: null, hilo: '', vivo: false,
        estado: 'Activo', estado_completo: 'Activo', area: 'Taller', ...o });
    const lista = [
        p('faro', 'Cliente Uno · Faro de la costa', { cliente: 'Cliente Uno', interno: false,
            plazo: { inicio: en(-30), fin: en(-2), etapa: 'desarrollo', avance: .5, aviso: 'sin horas cargadas' } }),
        p('molino', 'Molino', { plazo: { inicio: en(-10), fin: en(40), etapa: 'inicio', avance: .25 } }),
        p('puente', 'Puente', { area: 'Obras', plazo: { inicio: en(20), fin: en(60) } }),
        p('viejo', 'Muelle viejo', { arquetipo: 'proyecto cerrado', estado: 'Cerrado', estado_completo: 'Cerrado', area: 'Obras' }),
    ];
    const h = dom(P.htmlListaProyectos(lista, 'casa/proyectos/molino', new Map([['casa/proyectos/faro', 7]]), ['Taller', 'Obras']).join(''));
    const filas = [...h.querySelectorAll('#proyectos .proy')];
    assert.equal(filas.length, 4, 'una fila por proyecto');
    assert.ok(filas.every(f => f.classList.contains('item') && f.dataset.accion === 'proy-sel' && f.dataset.valor && f.dataset.sec && f.dataset.orden),
        'cada fila es un ítem, que se elige, con lo que la página ordena y filtra');
    assert.ok(!h.querySelector('.fila'), 'ninguna fila hecha a mano');
    assert.ok(!h.querySelector('#proyectos .estado-p, .proy-cols'), 'sin la columna del estado ni los nombres de columnas: el orden va en su grupo');
    const faro = h.querySelector('[data-valor="casa/proyectos/faro"]');
    assert.equal(faro.querySelector('.item-prefijo')?.textContent, 'Cliente Uno', 'el cliente, adelante');
    assert.equal(faro.querySelector('.item-titulo')?.textContent, '· Faro de la costa', 'el nombre, el título del ítem (lo que se estira)');
    assert.equal(faro.querySelectorAll('.item-inicio > .item-ranura').length, 2, 'la fase y la etapa, cada una en su ranura');
    assert.ok(faro.querySelector('.item-ranura .circulo'), 'la fase, un círculo');
    assert.ok(faro.querySelector('.item-aviso.tono-atencion')?.title.includes('sin horas cargadas'), 'lo que no cuadra, al final');
    const meta = faro.querySelector('.item-fin > .item-meta');
    assert.ok(meta?.querySelector('.cuando-p.tono-atencion')?.textContent.startsWith('venció'), 'el plazo, en la meta (vencido, en el color de cuidado)');
    assert.equal(meta?.querySelector('.tareas-p')?.textContent, '7', 'cuántos pendientes, en la meta');
    assert.ok(faro.querySelector('.item-fin > .item-acciones > .item-menu[data-accion="proy-menu"]'), 'el ⋯, el menú del ítem: aparece al pasar el mouse');
    assert.ok(h.querySelector('[data-valor="casa/proyectos/molino"]').classList.contains('activa'), 'la elegida, con el fondo del ítem activo');
    assert.ok(h.querySelector('[data-valor="casa/proyectos/viejo"]').classList.contains('apagada'), 'un cerrado, apagado');
    // las secciones: un separador (su línea de arriba) y la cabecera, que se pliega en la página; los dos se mueven con
    // las filas al ordenar (`data-orden`)
    const cabs = [...h.querySelectorAll('#proyectos > .item.cabecera.proy-sec-cab')];
    assert.deepEqual(cabs.map(c => [c.dataset.sec, c.querySelector('.item-titulo')?.textContent, c.querySelector('.item-sufijo')?.textContent]),
        [['curso', 'en ejecución', '2'], ['partir', 'por partir', '1'], ['cerrado', 'cerrados', '1']], 'cada estado, su sección, con cuántos tiene');
    assert.ok(cabs.every(c => c.dataset.accion === 'proy-seccion' && c.previousElementSibling?.classList.contains('sep')
        && c.previousElementSibling.dataset.sec === c.dataset.sec && c.previousElementSibling.dataset.orden), 'antes de cada cabecera, su separador');
    // las herramientas: el buscador con el orden (componentes/orden.ts) y la tabla extendida; debajo, los filtros
    const orden = [...h.querySelectorAll('.buscador-barra .orden [data-accion="proy-orden"]')].map(o => o.dataset.id);
    assert.deepEqual(orden, ['proyectos:nombre', 'proyectos:fase', 'proyectos:plazo', 'proyectos:pend'], 'el orden, en la barra del buscador');
    assert.ok(!h.querySelector('#ver-extendida, [data-accion="proy-tabla"]'), 'la tabla extendida ya no va en el buscador: es una vista de la barra');
    const fil = h.querySelector('.buscador-barra + .filtros.proy-filtros');
    assert.ok(fil, 'los filtros, la fila estándar bajo el buscador');
    const area = fil.querySelector('.filtros-grupo.plegado[data-grupo="area"]');
    assert.deepEqual([...area.querySelectorAll('.filtros-op')].map(o => [o.dataset.id, o.textContent]),
        [['area:', 'todas 4'], ['area:Taller', 'Taller 2'], ['area:Obras', 'Obras 2']], 'el área, plegada: «todas» primero, en el orden del perfil');
    assert.ok(area.querySelector('[data-id="area:"]').classList.contains('si'), 'sin área elegida, rige «todas»');
    assert.equal(fil.querySelector('.filtros-grupo[data-grupo="cerrados"] .filtros-op')?.textContent, 'cerrados 1', '«cerrados N», junto al área');
    assert.ok(!P.filtrosProyectos([lista[0]], [], 0), 'con una sola área y sin cerrados, ningún filtro');
    // la tabla extendida: a lo ancho y en palabras, con los nombres de sus columnas (que ordenan) y el estado
    const t = dom(P.htmlListaProyectos(lista, '', undefined, [], lista.length, true).join(''));
    assert.ok(t.querySelector('#proyectos > .proy-cols [data-orden-p="estado"]'), 'la tabla: sus columnas, con el estado');
    assert.equal(t.querySelectorAll('#proyectos > .fila.proy .estado-p').length, 4, 'y el estado de cada uno');
    assert.equal(t.querySelectorAll('#proyectos > .item.cabecera').length, 3, 'con las mismas secciones');
}

// 3. en el CSS: la lista va de borde a borde (sale del aire de la pantalla, sin hueco hasta el detalle); es un contenedor,
//    y sus columnas ceden por su ancho, en orden: primero cuántos pendientes, después el plazo; el nombre, nunca
{
    const rs = reglas(css);
    const cuerpo = (sel) => { const i = css.indexOf(`${sel} {`); return i < 0 ? '' : css.slice(i, css.indexOf('}', i)); };
    assert.match(cuerpo('.proy-dos'), /margin-inline:\s*calc\(-1 \* var\(--pantalla-margen\)\)/, 'la lista y el detalle, fuera del aire de la pantalla');
    assert.doesNotMatch(cuerpo('.proy-dos'), /\bgap:/, 'sin hueco entre la lista y el detalle');
    assert.match(cuerpo('.proy-lista'), /container:\s*proy-lista\s*\/\s*inline-size/, 'la lista es un contenedor');
    const cede = rs.filter(r => r.contenedor.startsWith('@container proy-lista'));
    const ancho = (r) => Number(/max-width:\s*(\d+)ch/.exec(r.contenedor)?.[1] ?? 0);
    const primero = Math.max(...cede.filter(r => r.cabeza.includes('.tareas-p')).map(ancho));
    const despues = Math.max(...cede.filter(r => r.cabeza.includes('.cuando-p')).map(ancho));
    assert.ok(primero > despues && despues > 0, `cuántos pendientes cede antes (${primero}ch) que el plazo (${despues}ch)`);
    assert.ok(!cede.some(r => /item-(titulo|texto)|\.que\b/.test(r.cabeza)), 'el nombre no cede');
    assert.ok(!rs.some(r => r.contenedor && !r.contenedor.includes('proy-lista') && /tareas-p|cuando-p/.test(r.cabeza)), 'sus columnas no miran el ancho de la pantalla');
}

// 4. en la página (vista.ts, con un DOM): plegar una sección esconde sus filas y se recuerda, el separador que sigue se va
//    (la línea de abajo de la cabecera plegada ya aparta); buscando, se ve lo que calza aunque esté plegado; «cerrados» los
//    muestra; ordenar por una opción deja las filas sueltas, sin secciones; las cuentas de los filtros, al día
{
    const en = (dias) => new Date(Date.now() + dias * 864e5).toISOString().slice(0, 10);
    const p = (slug, nombre, o = {}) => ({ ruta: `casa/proyectos/${slug}`, nombre, arquetipo: 'proyecto', modificado: null, hilo: '', vivo: false,
        estado: 'Activo', estado_completo: 'Activo', area: 'Taller', ...o });
    const lista = [
        p('faro', 'Faro', { plazo: { inicio: en(-30), fin: en(20), etapa: 'desarrollo', avance: .5 } }),
        p('molino', 'Molino', { area: 'Obras', plazo: { inicio: en(-10), fin: en(40), etapa: 'inicio', avance: .25 } }),
        p('puente', 'Puente', { area: 'Obras', plazo: { inicio: en(20), fin: en(60) } }),
        p('viejo', 'Aljibe viejo', { arquetipo: 'proyecto cerrado', estado: 'Cerrado', estado_completo: 'Cerrado' }),
    ];
    w.localStorage.clear();
    const raiz = w.document.createElement('div');
    w.document.body.appendChild(raiz);
    const enviados = [];
    const v = P.montarDia(raiz, m => enviados.push(m));
    v.pintar(`<div class="proy-dos"><div class="proy-lista">${P.htmlListaProyectos(lista, '', undefined, [], 5).join('')}</div><div id="proy-det"></div></div>`);
    const fila = (slug) => raiz.querySelector(`[data-valor="casa/proyectos/${slug}"]`);
    const cab = (sec) => raiz.querySelector(`.proy-sec-cab[data-sec="${sec}"]`);
    const sep = (sec) => raiz.querySelector(`#proyectos > .sep[data-sec="${sec}"]`);
    const visibles = () => [...raiz.querySelectorAll('#proyectos > .proy')].filter(f => !f.hidden).map(f => f.dataset.valor.split('/').pop());
    const clic = (el) => el.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
    assert.deepEqual(visibles(), ['faro', 'molino', 'puente'], 'los cerrados, escondidos');
    assert.ok(cab('cerrado').hidden && sep('cerrado').hidden, 'y su sección, con su separador');
    assert.ok(!sep('curso').hidden && !sep('partir').hidden, 'cada sección con filas, con su línea arriba');
    // plegar «en ejecución»
    clic(cab('curso').querySelector('.item-titulo'));
    assert.deepEqual(visibles(), ['puente'], 'plegada, sus filas se esconden');
    assert.ok(!cab('curso').hidden, 'y su cabecera queda');
    assert.equal(cab('curso').querySelector('.item-ranura .i').textContent, P.I.plegado, 'con la flecha de plegada');
    assert.ok(sep('partir').hidden, 'el separador de la que sigue se va: la línea de la plegada ya la aparta');
    assert.deepEqual(JSON.parse(w.localStorage.getItem('telar.dashboard.estado')).pl, ['curso'], 'y se recuerda');
    assert.ok(!enviados.some(m => m.accion === 'proy-seccion'), 'sin ir y volver: lo hace la página');
    // buscando, lo que calza se ve aunque esté plegado
    const b = raiz.querySelector('#buscar-p');
    b.value = 'faro'; b.dispatchEvent(new w.Event('input', { bubbles: true }));
    assert.deepEqual(visibles(), ['faro'], 'buscando, se abre lo que calza');
    b.value = ''; b.dispatchEvent(new w.Event('input', { bubbles: true }));
    clic(cab('curso').querySelector('.item-titulo'));
    assert.deepEqual(visibles(), ['faro', 'molino', 'puente'], 'abierta otra vez');
    // los filtros: «cerrados» los muestra; el área, la que rige y cuántas deja cada una
    clic(raiz.querySelector('.filtros-op[data-id="cerrados:si"]'));
    assert.deepEqual(visibles(), ['faro', 'molino', 'puente', 'viejo'], '«cerrados» los muestra');
    assert.ok(!cab('cerrado').hidden && !sep('cerrado').hidden, 'con su sección');
    assert.ok(raiz.querySelector('.filtros-op[data-id="cerrados:si"]').classList.contains('si'), 'y queda marcado');
    const cuenta = (id) => raiz.querySelector(`.filtros-op[data-id="${id}"] .filtros-cuenta`).textContent;
    assert.deepEqual(['area:', 'area:Taller', 'area:Obras'].map(cuenta), ['4', '2', '2'], 'cuántos deja cada área');
    // repintar (la lista que se relee) deja lo elegido
    v.pintar(`<div class="proy-dos"><div class="proy-lista">${P.htmlListaProyectos(lista, '', undefined, [], 5).join('')}</div><div id="proy-det"></div></div>`);
    assert.deepEqual(visibles(), ['faro', 'molino', 'puente', 'viejo'], 'repintada, siguen los cerrados a la vista');
    clic(raiz.querySelector('.filtros-op[data-id="cerrados:si"]'));
    assert.deepEqual(visibles(), ['faro', 'molino', 'puente'], 'otro clic los esconde');
    // ordenar: las filas sueltas, sin secciones ni separadores; otra vez, de vuelta
    clic(raiz.querySelector('.ord[data-id="proyectos:nombre"]'));
    assert.deepEqual(visibles(), ['faro', 'molino', 'puente'], 'por nombre');
    assert.ok([...raiz.querySelectorAll('#proyectos > :is(.proy-sec-cab, .sep)')].every(x => x.hidden), 'sin secciones');
    assert.ok(raiz.querySelector('.ord[data-id="proyectos:nombre"]').classList.contains('si'), 'el que rige, marcado');
    clic(raiz.querySelector('.ord[data-id="proyectos:nombre"]'));
    assert.ok(!cab('curso').hidden && !sep('curso').hidden, 'de vuelta al orden de siempre, con sus secciones');
    // el ⋯ de una fila: la elige y pide su menú
    clic(fila('molino').querySelector('.item-menu'));
    assert.ok(fila('molino').classList.contains('activa'), 'el ⋯ la elige');
    assert.ok(enviados.some(m => m.accion === 'proy-menu' && m.valor === 'casa/proyectos/molino'), 'y pide su menú');
    // en una columna, el detalle es una pantalla propia (proyectos.css): elegir uno la abre (`viendo-detalle`), un
    // repintado la deja, y su «‹» vuelve a la lista
    const pd = () => raiz.querySelector('.proy-dos');
    clic(fila('faro'));
    assert.ok(pd().classList.contains('viendo-detalle'), 'elegir uno abre su detalle');
    const det = { p: lista[0], pendientes: [], aviso: '', readme: '' };
    v.parcial('proy-det', P.htmlDetalleProyecto(det));
    assert.ok(pd().classList.contains('viendo-detalle') && raiz.querySelector('#proy-det [data-accion="proy-volver"]'), 'llega su detalle, con «‹»');
    v.pintar(`<div class="proy-dos"><div class="proy-lista">${P.htmlListaProyectos(lista, 'casa/proyectos/faro', undefined, [], 5).join('')}</div><div class="proy-divisor"></div><div id="proy-det">${P.htmlDetalleProyecto(det)}</div></div>`);
    assert.ok(pd().classList.contains('viendo-detalle'), 'repintada la pantalla, sigue en el detalle');
    const antes = enviados.length;
    clic(raiz.querySelector('#proy-det [data-accion="proy-volver"]'));
    assert.ok(!pd().classList.contains('viendo-detalle') && enviados.length === antes, '«‹» vuelve a la lista, sin ir y volver');
    w.localStorage.clear();
    raiz.remove();
}

// 5. proyectos › comercial: los negocios en secciones por cómo van según su documento, con las mismas piezas (y en el
//    mismo contenedor: buscar, ordenar y plegar los hace la página igual)
{
    assert.deepEqual(['Negociación', 'Propuesta enviada el 10', 'Borrador de propuesta', 'POC', 'Prospecto temprano', 'Pausado', 'Vencido sin responder',
        'Ganado', '', 'algo raro'].map(P.etapaNegocio),
    ['negociacion', 'propuesta', 'propuesta', 'diagnostico', 'prospecto', 'pausado', 'perdido', 'ganado', 'otro', 'otro'], 'la etapa, de su Estado');
    const n = (slug, estado, o = {}) => ({ ruta: `casa/negocios/${slug}`, nombre: `Cliente ${slug} · Venta`, cliente: `Cliente ${slug}`, interno: false,
        arquetipo: 'deal', estado, estado_completo: estado, modificado: '2026-11-20T10:00:00Z', hilo: '', vivo: false, ...o });
    const h = dom(P.htmlNegocios([n('a', 'Prospecto'), n('b', 'Negociación'), n('c', 'Propuesta enviada', { modificado: '2026-11-25T10:00:00Z' }), n('d', 'Perdido')], 'casa/negocios/b',
        new Map([['casa/negocios/b', 4]])).join(''));
    assert.deepEqual([...h.querySelectorAll('#proyectos > .item.cabecera')].map(c => [c.dataset.sec, c.querySelector('.item-titulo').textContent]),
        [['neg:negociacion', 'en negociación'], ['neg:propuesta', 'con propuesta'], ['neg:prospecto', 'prospectos'], ['neg:perdido', 'perdidos']],
        'lo más cerca de cerrarse arriba, cada etapa con su sección (`neg:` para recordar su plegado aparte)');
    const b = h.querySelector('[data-valor="casa/negocios/b"]');
    assert.ok(b.classList.contains('item') && b.classList.contains('activa') && b.dataset.accion === 'proy-sel', 'cada negocio, un ítem que se elige');
    assert.equal(b.querySelector('.item-prefijo').textContent, 'Cliente b', 'el cliente adelante');
    assert.match(b.querySelector('.item-ranura').title, /Negociación/, 'su círculo dice lo que dice su documento');
    assert.equal(b.querySelector('.item-meta .tareas-p').textContent, '4', 'cuántos pendientes, al final');
    assert.ok(b.querySelector('.item-meta .cuando-p').textContent.startsWith('hace '), 'y cuándo se tocó');
    assert.ok(h.querySelector('[data-valor="casa/negocios/d"]').classList.contains('apagada'), 'un perdido, apagado');
    assert.deepEqual([...h.querySelectorAll('.orden [data-accion="proy-orden"]')].map(o => o.dataset.id), ['proyectos:nombre', 'proyectos:plazo', 'proyectos:pend'],
        'su orden: el nombre, cuándo se tocó y los pendientes');
    assert.ok(!h.querySelector('.filtros'), 'sin filtros');
}

// 6. proyectos › interno: el próximo paso que sale del README (la primera casilla abierta, fuera del código), y en la
//    página las ideas plegadas de entrada (se abren y se recuerda) y los filtros «me toca» y «sin próximo paso»
{
    assert.equal(P.primeraCasilla('# X\n\n```\n- [ ] no, es código\n```\n- [x] hecha\n- [ ] **Llamar** a `alguien` <!-- id: c-1 -->\n- [ ] otra'), 'Llamar a alguien');
    assert.equal(P.primeraCasilla('- [>] en curso\n- [ ] después'), 'en curso', 'una en curso también');
    assert.equal(P.primeraCasilla('sin casillas'), '');
    const u = (slug, fm) => ({ ruta: `casa/iniciativas/${slug}`, nombre: slug, arquetipo: 'iniciativa', modificado: null, hilo: '', vivo: false, frontmatter: { programa: 'plan', ...fm } });
    const xs = [u('mia', { dueno: 'Yo Mismo', estado: 'en curso' }), u('ajena', { dueno: 'Otra', estado: 'en curso' }), u('idea', { estado: 'idea' })];
    const o = { voc: P.vocabularioDe({ estados: ['idea', 'en curso'] }), esMia: d => d === 'Yo Mismo',
        proximos: new Map([['casa/iniciativas/mia', { texto: 'llamar', de: 'tarea' }], ['casa/iniciativas/ajena', { texto: '', de: '' }], ['casa/iniciativas/idea', { texto: '', de: '' }]]) };
    w.localStorage.clear();
    const raiz = w.document.createElement('div');
    w.document.body.appendChild(raiz);
    const v = P.montarDia(raiz, () => {});
    v.pintar(`<div class="proy-dos" data-vista="interno"><div class="proy-lista"><div class="buscador-barra"><input id="buscar-p"></div>${P.filtrosIniciativas(xs, 'programa', o)}${P.htmlIniciativas(xs, 'programa', o)}</div><div id="proy-det"></div></div>`);
    const visibles = () => [...raiz.querySelectorAll('.ini')].filter(f => !f.hidden).map(f => f.dataset.valor.split('/').pop());
    const clic = (el) => el.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
    const ideas = raiz.querySelector('.ini-ideas');
    assert.deepEqual(visibles(), ['ajena', 'mia'], 'las ideas, plegadas de entrada');
    assert.equal(ideas.querySelector('.item-ranura:last-child .i').textContent, P.I.plegado, 'con la flecha de plegada');
    clic(ideas.querySelector('.item-titulo'));
    assert.deepEqual(visibles(), ['ajena', 'mia', 'idea'], 'un clic las abre');
    assert.deepEqual(JSON.parse(w.localStorage.getItem('telar.dashboard.estado')).pa, ['ideas:plan'], 'y se recuerda que se abrieron');
    clic(ideas.querySelector('.item-titulo'));
    assert.deepEqual(visibles(), ['ajena', 'mia'], 'otro, las pliega');
    clic(raiz.querySelector('.filtros-op[data-id="papel:llevo"]'));
    assert.deepEqual(visibles(), ['mia'], '«me toca»: las que llevo');
    clic(raiz.querySelector('.filtros-op[data-id="papel:llevo"]'));
    clic(raiz.querySelector('.filtros-op[data-id="proximo:sin"]'));
    assert.deepEqual(visibles(), ['ajena', 'idea'], '«sin próximo paso»: filtrando se abren las ideas que calzan');
    assert.equal(raiz.querySelector('.filtros-op[data-id="papel:llevo"] .filtros-cuenta').textContent, '0', 'cada uno cuenta lo que dejaría con lo demás');
    w.localStorage.clear();
    raiz.remove();
}

// 7. la barra del detalle: la de cada pantalla (componentes/pantalla.ts): el nombre tal cual, cortado con «…» y entero en
//    su globo; a la derecha, solo íconos (ir a su hilo, consolidar, abrir su README, ⋯); cómo va, en una línea; y entre la
//    lista y el detalle, el divisor: una línea propia, de alto completo (no el borde del detalle)
{
    const p = { ruta: 'casa/proyectos/faro', nombre: 'Cliente Uno · Faro de la costa, con un nombre largo', cliente: 'Cliente Uno', interno: false,
        arquetipo: 'proyecto', estado: 'Activo', estado_completo: 'Activo', modificado: null, hilo: 'Faro', vivo: false,
        plazo: { inicio: '2026-11-02', fin: '2026-12-09', etapa: 'desarrollo', avance: .5, aviso: 'sin horas', fuente: 'pmo', enlace: 'https://ejemplo.cl/pmo' } };
    const h = dom(P.htmlDetalleProyecto({ p, pendientes: [], aviso: '', readme: '' }));
    const cab = h.querySelector('.det-cab');
    const nav = cab.firstElementChild;
    assert.ok(nav?.matches('nav.pantalla-barra'), 'la primera fila del detalle es una barra');
    assert.deepEqual(P.fueraDeLaBarra(nav), [], 'con solo su título y sus botones');
    const nombre = nav.querySelector('.pantalla-nombre');
    assert.ok(nombre.classList.contains('literal') && nombre.textContent === p.nombre, 'el nombre tal cual (se corta con «…»: pantalla.css)');
    assert.ok(nombre.title.includes(p.nombre) && nombre.title.includes(p.ruta), 'entero en su globo, con su ruta');
    assert.deepEqual([...nav.querySelectorAll('.pantalla-acciones .pantalla-boton')].map(b => [b.dataset.accion, b.classList.contains('cuadrada')]),
        [['proyecto', true], ['proy-consolidar', true], ['abrir-ruta', true], ['proy-menu', true]], 'a la derecha, íconos: su hilo, consolidar, su README y el ⋯');
    assert.match(nav.querySelector('[data-accion="proyecto"]').title, /^retomar su hilo: «Faro» \(dormido\)/, 'retomar su hilo, con su nombre en el globo');
    assert.ok(!h.querySelector('h3, .det-ir, .det-titulo'), 'sin el título en negrita ni la palabra «retomar su hilo»');
    const va = cab.querySelector('.det-va');
    assert.ok(va && va.previousElementSibling === nav && va.nextElementSibling?.classList.contains('pestanas'), 'cómo va, entre la barra y las pestañas');
    assert.ok(va.querySelector('.det-va-marca .circulo'), 'con el círculo de su fase en su ranura');
    assert.match(va.querySelector('.det-va-texto').title, /^en ejecución · desarrollo · 2-nov → 9-dic · sin horas · pmo$/, 'en una línea, entera en su globo');
    assert.ok(!h.querySelector('[data-pane] [data-accion="proy-consolidar"]') && !/abrir el README/.test(h.querySelector('[data-pane="documento"]').textContent),
        'consolidar y abrir el README ya no van en palabras abajo: son íconos de la barra');
    const cuerpo = (sel) => { const i = css.indexOf(`${sel} {`); return i < 0 ? '' : css.slice(i, css.indexOf('}', i)); };
    assert.match(cuerpo('.proy-dos'), /grid-template-columns:[^;]*\s1px\s/, 'una columna de un píxel para el divisor');
    assert.match(cuerpo('.proy-divisor'), /align-self:\s*stretch/, 'que se estira al alto de la grilla');
    assert.match(cuerpo('.proy-dos'), /min-height:\s*calc\(100cqh/, 'y la grilla, a lo menos la pantalla entera');
    assert.doesNotMatch(cuerpo('#proy-det'), /border-left/, 'el divisor no es el borde del detalle');
    // 8. en una columna, el detalle es una pantalla propia: con uno elegido, solo él (y su «‹»); sin él, solo la lista
    const angosta = reglas(css).filter(r => r.contenedor.startsWith('@container (max-width'));
    const en = (sel) => angosta.some(r => r.cabeza.split(',').map(x => x.trim()).includes(sel));
    assert.ok(en('.proy-dos.viendo-detalle:has(#proy-det .det-cab) .proy-lista'), 'viendo un detalle, la lista no se ve');
    assert.ok(en('.proy-dos:not(.viendo-detalle) #proy-det'), 'sin él, el detalle no se ve');
    assert.ok(en('#proy-det .pantalla-barra > [data-accion="proy-volver"]'), '«‹», solo en una columna');
    assert.ok(Number(/max-width:\s*(\d+)px/.exec(angosta[0].contenedor)?.[1]) >= 780, 'una columna antes que en el teléfono: a 1024 también');
    assert.ok(h.querySelector('.pantalla-barra > [data-accion="proy-volver"]'), 'la barra del detalle trae su «‹»');
}

// 9. el cuerpo del detalle: las secciones del resumen como las de una pantalla (su línea, su tinta, la cuenta tenue), sin
//    «los N pendientes» (lo dice su pestaña); el documento entero con la prosa compartida, sin <details> a mano ni su
//    frontmatter; las casillas del documento sin la ranura vacía del código; y el CSS, con tokens y colores semánticos
{
    const md = (t) => `<p>${t.trim().replace(/\n+/g, ' ')}</p>`;
    const r = P.verReadme('---\ntitulo: Faro\n---\n# Faro\n\nUn faro en la costa.\n\n## Estado\n\nVa bien.\n\n## Notas\n\nAlgo más.\n', md, t => t);
    assert.ok(r.todo && !r.todo.includes('titulo: Faro') && r.todo.includes('Un faro en la costa'), 'el documento entero, sin su frontmatter');
    const fila = (ref, texto, o = {}) => ({ fila: { ref, id: o.ficha ? ref : '', texto, ruta: 'casa/proyectos/faro', ...o }, ref, texto, hilo: '', cuando: '', dias: null,
        enCurso: false, avance: '', urgencia: 0, urgente: false });
    const casillas = [1, 2, 3, 4].map(i => fila(`faro:${i}`, `casilla ${i}`));
    const p = { ruta: 'casa/proyectos/faro', nombre: 'Faro', arquetipo: 'proyecto', estado: 'Activo', estado_completo: 'Activo', modificado: null, hilo: '', vivo: false };
    const h = dom(P.htmlDetalleProyecto({ p, pendientes: casillas, aviso: '', readme: r }));
    const res = h.querySelector('[data-pane="resumen"]');
    const secs = [...res.querySelectorAll(':scope > .bloque.det-r > h2.sec')];
    assert.deepEqual(secs.map(x => x.firstChild.textContent.trim()), ['Estado', 'próximos', 'qué es'], 'cada sección del resumen, una sección de pantalla (h2.sec)');
    assert.equal(secs[1].querySelector('.cuenta')?.textContent, '3 de 4', 'con su cuenta tenue');
    assert.ok(!res.querySelector('h4, .det-ver') && !/los 4 pendientes/.test(res.textContent), 'sin <h4> a mano ni «los N pendientes»');
    const doc = h.querySelector('[data-pane="documento"]');
    assert.ok(doc.querySelector('.prosa.prosa-md.det-doc[data-base="casa/proyectos/faro"]'), 'el documento, con la prosa compartida');
    assert.ok(!doc.querySelector('details'), 'sin secciones plegadas a mano');
    const ranuras = (x) => x.querySelectorAll('.item-inicio > .item-ranura').length;
    const pend = [...h.querySelectorAll('[data-pane="pendientes"] .item.tarea')];
    assert.equal(pend.length, 4);
    assert.ok(pend.every(x => ranuras(x) === 2), 'las casillas del documento, sin la ranura del código');
    const mixto = dom(P.htmlDetalleProyecto({ p, pendientes: [fila('T7', 'una tarea', { ficha: true, proveedor: 'tareas' }), ...casillas], aviso: '', readme: r }));
    assert.ok([...mixto.querySelectorAll('[data-pane="pendientes"] .item.tarea')].every(x => ranuras(x) === 3), 'con alguna tarea que lo tiene, todas con la ranura');
    assert.doesNotMatch(css, /var\(--(dim|fg|azul|bg)\)/, 'los colores, los semánticos (--texto-tenue, --texto, --acento, --superficie), no las tintas');
    assert.doesNotMatch(css, /--celda-cuadrada|\d\.\d+lh|\b1\.5ch\b/, 'los espacios, los tokens (--e-…, --h-…, --item-…)');
    assert.ok(reglas(css).some(r => r.cabeza.includes('.item.activa .item-acciones')), 'el ⋯ de la fila elegida, a la vista');
}

console.log('proyectos: ok');
