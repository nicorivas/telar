// Prueba de las dos piezas nuevas de la ficha de una tarea en foco y de la ficha misma, con un DOM (happy-dom), un modelo
// de mentira y un fetch que anota lo que se le pide (nada sale):
//
// · las pestañas (componentes/pestanas.ts, web/pestanas.ts): ← → Inicio y Fin pasan de una a otra y la abren, con el
//   foco en la de al lado; solo con el foco en una (las teclas no siguen de largo a los atajos de la página); una fila
//   que la vista marca sin repintar (`marcar`); y las que no caben (`acomodar`, con anchos de mentira): al «⋯», la
//   abierta siempre a la vista, lo nuevo y la cuenta que pide de una escondida en el «⋯», las flechas que llegan al «⋯»
//   sin abrir nada, su menú con ⏎ y lo elegido en él, abierto y a la vista; y al ensancharse, todas de nuevo.
// · la barra de mensaje (componentes/mensaje.ts, web/mensaje.ts): el destino de fábrica (su hilo, mientras telar lo dice
//   «buscando»; sin hilo propio, el primer agente; sin cosa, `[instruccion] destino` o uno nuevo), lo que manda (lo de
//   la instrucción: `POST /actuar` con la dirección, la fila y lo escrito), ⏎ envía y ⇧⏎ no, ⎋ suelta el campo, lo que
//   dice después (a quién, con enlace; si falla, por qué y lo escrito vuelve), el borrador compartido con la ventana de
//   la instrucción, que no le roba teclas a nadie (no toma el foco sola y las letras escritas en ella no llegan a los
//   atajos; ⌘K sí) y que repintar la deje con lo escrito y el foco donde estaban.
// · el mundo en el selector: solo los hilos y los agentes del mundo puesto, también en el modo todo (donde ⌘K muestra lo
//   demás al final); nunca uno que pide esconderse; en el orden y con los íconos de ⌘K.
// · la ficha en foco (vistas/dashboard/foco.ts): de arriba abajo, las pestañas, las tarjetas, las acciones de la elegida
//   y la barra de mensaje con ella como contexto; elegir otra tarjeta cambia la barra; cambiar de pestaña, la abierta.
//
// Corre en Node: npm run prueba:mensaje
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { Window } from 'happy-dom';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const src = path.join(aqui, '..', 'src');
const outfile = path.join(mkdtempSync(path.join(tmpdir(), 'mensaje-')), 'mensaje.cjs');

const w = new Window({ url: 'http://localhost/' });
for (const k of ['window', 'document', 'CSS', 'Element', 'HTMLElement', 'HTMLInputElement', 'HTMLTextAreaElement', 'HTMLDialogElement', 'Node', 'Event',
    'KeyboardEvent', 'MouseEvent', 'PointerEvent', 'getComputedStyle', 'requestAnimationFrame', 'innerWidth', 'innerHeight', 'sessionStorage', 'localStorage'])
    globalThis[k] = k === 'window' ? w : w[k] ?? globalThis[k];
globalThis.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {}, addListener() {} });

// ── la API de mentira: adónde iría su hilo y lo que se manda ──
const pedidos = [];
let adonde = { destino: 'Faro', como: 'hilo', maquina: '', carpeta: 'casa/faro', nuevo: true, contexto: '[contexto: T84]', falta: '', titulo: 'Pedir las bolsas', propio: false };
let actuar = cuerpo => ({ destino: cuerpo.a || (cuerpo.nuevo ? 'T84 · nuevo' : 'Faro'), como: 'enviado', prompt: '…' });
globalThis.fetch = async (url, init = {}) => {
    const u = new URL(String(url), 'http://localhost');
    const cuerpo = init.body ? JSON.parse(init.body) : undefined;
    pedidos.push({ metodo: init.method ?? 'GET', ruta: u.pathname, cuerpo });
    const json = (d, status = 200) => ({ ok: status < 400, status, json: async () => d, text: async () => JSON.stringify(d) });
    if (u.pathname === '/api/actuar/adonde') return json(adonde);
    if (u.pathname === '/api/actuar') { const r = actuar(cuerpo); return r.error ? json({ detail: r.error }, 503) : json(r); }
    return json({});
};

await build({
    stdin: { contents: `export * as P from './componentes/pestanas'; export * as PW from './web/pestanas';
        export * as M from './componentes/mensaje'; export * as MW from './web/mensaje';
        export { modelo } from './modelo'; export * as mundo from './web/mundo'; export * as buscadorHilos from './web/buscador-hilos';
        export { I } from './web/iconos'; export { PantallaFoco } from './vistas/dashboard/foco'; export { yo } from './vistas/dashboard/dia';`,
    resolveDir: src, loader: 'ts' },
    bundle: true, platform: 'node', format: 'cjs', outfile, logLevel: 'warning', loader: { '.css': 'text' },
});
const { P, PW, M, MW, modelo, mundo, buscadorHilos, I, PantallaFoco, yo } = require(outfile);
const dormir = ms => new Promise(r => setTimeout(r, ms));
const q = s => document.querySelector(s);
const tecla = (el, key, o = {}) => el.dispatchEvent(new w.KeyboardEvent('keydown', { key, bubbles: true, cancelable: true, ...o }));
/** lo que le llega a la página (los atajos del dashboard escuchan en window) */
const aLaPagina = [];
w.addEventListener('keydown', e => aLaPagina.push(e.key));

PW.atender(document);
MW.atender(document);

// ── 1. las pestañas: el HTML ──
{
    const h = P.pestanas({ nombre: 'foco', accion: 'foco-modo', activa: 'b', fin: '<a class="releer">↻</a>', clases: ['x'], pestanas: [
        { valor: 'a', nombre: 'gestión', icono: 'G', cuenta: 50, ayuda: 'lo rápido' },
        { valor: 'b', nombre: 'concentración', icono: 'C', color: 'verde', cuenta: 3, cuentaAtencion: true, nuevo: 'exito' },
        { valor: 'c', nombre: '<otra>', apagada: true, ayuda: 'por hacer' },
        { valor: 'd', nombre: 'enlace', href: '#item/anatomia', datos: { hoja: 'codigos' } },
    ] });
    assert.match(h, /^<nav class="pestanas x" data-pestanas="foco"><span class="pestanas-lista" role="tablist" aria-label="foco">/, 'una fila, con su lista');
    assert.match(h, /<a class="pestana con-icono" role="tab" aria-selected="false" tabindex="-1" data-accion="foco-modo" data-valor="a" title="gestión \(50\): lo rápido">/,
        'las demás: fuera del tabulador, con su orden y su globo');
    assert.match(h, /<a class="pestana si con-icono" role="tab" aria-selected="true" tabindex="0" data-accion="foco-modo" data-valor="b"[^>]* style="--pestana-c: var\(--verde\)">/,
        'la abierta: en el tabulador, con su tinta');
    assert.match(h, /<span class="i pestana-icono">G<\/span><span class="pestana-nombre">gestión<\/span><span class="pestana-cuenta">50<\/span>/, 'ícono, nombre y cuenta');
    assert.match(h, /<span class="pestana-cuenta atencion">3<\/span><span class="pestana-nuevo tono-exito"/, 'la cuenta que pide y lo nuevo');
    assert.match(h, /class="pestana apagada" role="tab" aria-selected="false" aria-disabled="true" tabindex="-1" title="&lt;otra&gt;: por hacer">/,
        'la apagada: sin orden, escapada');
    assert.match(h, /data-hoja="codigos" href="#item\/anatomia"/, 'un enlace, y lo que lleva además');
    assert.match(h, /<span class="pestanas-fin"><a class="releer">↻<\/a><\/span><\/nav>$/, 'lo del extremo, al final');
    // sin abierta todavía (la marca la vista): la primera, en el tabulador
    const sin = P.pestanas({ nombre: 'p', activa: '', pestanas: [{ valor: 'a', nombre: 'a' }, { valor: 'b', nombre: 'b' }] });
    assert.deepEqual([...sin.matchAll(/role="tab" aria-selected="\w+" tabindex="(-?\d)"/g)].map(m => m[1]), ['0', '-1']);
    assert.ok(!sin.includes('data-accion'), 'sin orden, no la pone');
}

// ── 2. las pestañas: el teclado y marcarlas ──
{
    document.body.innerHTML = '<input id="otra">' + P.pestanas({ nombre: 'foco', accion: 'foco-modo', activa: 'a', pestanas: ['a', 'b', 'c'].map(v => ({ valor: v, nombre: v })) });
    const abiertas = [];
    // la vista la abre (aquí, sin repintar: la marca)
    document.addEventListener('click', e => { const t = e.target.closest('[data-accion="foco-modo"]'); if (t) { abiertas.push(t.dataset.valor); PW.marcar(q('.pestanas'), t.dataset.valor); } });
    const tab = v => q(`.pestana[data-valor="${v}"]`);
    tab('a').focus();
    aLaPagina.length = 0;
    tecla(tab('a'), 'ArrowRight');
    assert.deepEqual(abiertas, ['b'], '→ abre la de al lado');
    assert.equal(document.activeElement, tab('b'), 'y el foco va con ella');
    tecla(tab('b'), 'End'); tecla(tab('c'), 'ArrowRight'); tecla(tab('a'), 'ArrowLeft'); tecla(tab('c'), 'Home');
    assert.deepEqual(abiertas, ['b', 'c', 'a', 'c', 'a'], 'Fin, la vuelta, ← y Inicio');
    assert.deepEqual(aLaPagina, [], 'las flechas no siguen a la página (el calendario y la ficha tienen las suyas)');
    // con el foco en otra parte, las flechas no son suyas
    q('#otra').focus();
    tecla(q('#otra'), 'ArrowRight');
    assert.equal(abiertas.length, 5, 'sin el foco en una pestaña, nada');
    assert.deepEqual(aLaPagina, ['ArrowRight'], 'y siguen su camino');
    // una fila que la vista marca sin repintar (el detalle de un proyecto)
    PW.marcar(q('.pestanas'), 'c');
    assert.equal(tab('c').getAttribute('aria-selected'), 'true');
    assert.ok(tab('c').classList.contains('si') && !tab('a').classList.contains('si'));
    assert.deepEqual(['a', 'b', 'c'].map(v => tab(v).tabIndex), [-1, -1, 0], 'en el tabulador, solo la abierta');
}

// ── 2b. las pestañas que no caben: al «⋯» ──
{
    const MUCHAS = [
        { valor: 'resumen', nombre: 'resumen', icono: 'R' },
        { valor: 'pendientes', nombre: 'pendientes', icono: 'P', cuenta: 9, cuentaAtencion: true },
        { valor: 'documento', nombre: 'documento', icono: 'D' },
        { valor: 'historia', nombre: 'historia', icono: 'H', nuevo: 'exito' },
        { valor: 'conexiones', nombre: 'conexiones', icono: 'C', color: 'azul', cuenta: 4 },
    ];
    // sin dibujo, los anchos de mentira: cada pestaña 50, el «⋯» 20, la lista lo que le deje la fila
    let fila = 1000;
    PW.medir.ancho = el => el.classList.contains('pestanas-lista') ? Math.min(fila - 20, 250) : el.classList.contains('pestanas-mas') ? 20
        : el.classList.contains('pestana') ? 50 : el.classList.contains('pestanas') ? fila : 0;
    let activa = 'resumen';
    const pintar = () => {
        document.body.innerHTML = P.pestanas({ nombre: 'proyecto', accion: 'proy', activa, pestanas: MUCHAS, fin: '<a class="fin">›</a>' });
        PW.acomodar(q('.pestanas'));
    };
    const abiertas = [];
    const alClic = e => { const t = e.target.closest('[data-accion="proy"]'); if (t) { abiertas.push(t.dataset.valor); activa = t.dataset.valor; pintar(); } };
    document.addEventListener('click', alClic);
    const tab = v => q(`.pestana[data-valor="${v}"]`);
    const mas = () => q('.pestanas-mas');
    const fuera = () => [...document.querySelectorAll('.pestana.fuera')].map(p => p.dataset.valor);

    // ancha: todas, sin «⋯»
    pintar();
    assert.deepEqual(fuera(), []);
    assert.ok(mas().hidden, 'con lugar, sin «⋯»');
    // angosta: caben dos (120 − 20 del «⋯» = 100); el resto, al «⋯», que lo nuevo y la cuenta que pide de ellas lo dicen
    fila = 120;
    pintar();
    assert.deepEqual(fuera(), ['documento', 'historia', 'conexiones'], 'las que no caben, fuera de la fila');
    assert.ok(!mas().hidden, 'y el «⋯»');
    assert.ok(mas().querySelector('.pestana-nuevo.tono-exito'), 'algo nuevo en una escondida: su punto, en el «⋯»');
    assert.ok(!mas().classList.contains('atencion'), 'la cuenta que pide está a la vista: el «⋯», normal');
    assert.match(mas().title, /historia/, 'su globo dice cuáles lleva');
    // la abierta, escondida: toma el lugar de la última que cabía
    activa = 'conexiones';
    pintar();
    assert.deepEqual(fuera(), ['pendientes', 'documento', 'historia'], 'la abierta, en el lugar de la última que cabía');
    assert.ok(!tab('conexiones').classList.contains('fuera') && tab('conexiones').classList.contains('si'));
    assert.ok(mas().classList.contains('atencion'), 'una cuenta que pide, escondida: el «⋯» en el de cuidado');
    // el teclado: → recorre las que se ven y llega al «⋯» sin abrir nada; → desde el «⋯» vuelve a la primera
    tab('conexiones').focus();
    tecla(tab('conexiones'), 'ArrowRight');
    assert.equal(document.activeElement, mas(), '→ llega al «⋯»');
    assert.deepEqual(abiertas, [], 'sin abrir nada');
    tecla(mas(), 'ArrowLeft');
    assert.deepEqual(abiertas, [], '← vuelve a la abierta, que ya lo está');
    mas().focus();
    tecla(mas(), 'ArrowRight');
    assert.deepEqual(abiertas, ['resumen'], 'desde el «⋯», → da la vuelta y abre la primera');
    // su menú, con ⏎: cada escondida con su ícono, su nombre y su cuenta; elegir una la abre y la trae a la vista
    mas().focus();
    tecla(mas(), 'Enter');
    await dormir(30);
    const menu = q('dialog');
    assert.ok(menu?.open, '⏎ abre su menú');
    const opciones = [...menu.querySelectorAll('.item')];
    assert.deepEqual(opciones.map(x => x.querySelector('.item-titulo').textContent), ['documento', 'historia', 'conexiones'], 'las escondidas, en orden');
    const con = opciones.find(x => x.textContent.includes('conexiones'));
    assert.ok(con.querySelector('.item-ranura .i')?.textContent === 'C' && /4/.test(con.textContent), 'con su ícono y su cuenta');
    assert.match(con.closest('.m-fila').getAttribute('style') ?? '', /--c: var\(--azul\)/, 'el ícono, en su tinta');
    assert.ok(/algo nuevo/.test(opciones.find(x => x.textContent.includes('historia')).textContent), 'lo nuevo, dicho');
    tecla(menu.querySelector('input'), 'ArrowDown');
    tecla(menu.querySelector('input'), 'Enter');
    await dormir(80);
    assert.equal(abiertas.at(-1), 'historia', 'lo elegido se abre');
    assert.ok(!tab('historia').classList.contains('fuera'), 'y queda a la vista');
    assert.equal(document.activeElement, tab('historia'), 'con el foco en ella, para seguir con las flechas');
    // ⎋ cierra el menú sin abrir nada, y el foco vuelve al «⋯»
    mas().focus();
    tecla(mas(), ' ');
    await dormir(30);
    tecla(q('dialog input'), 'Escape');
    await dormir(30);
    assert.equal(abiertas.at(-1), 'historia');
    assert.equal(document.activeElement, mas(), '⎋: el foco, de vuelta en el «⋯»');
    // al ensancharse, todas de nuevo
    fila = 1000;
    PW.acomodar(q('.pestanas'));
    assert.deepEqual(fuera(), []);
    assert.ok(mas().hidden && !mas().querySelector('.pestana-nuevo'));
    document.removeEventListener('click', alClic);
    PW.medir.ancho = el => el.getBoundingClientRect().width;
    aLaPagina.length = 0;
}

// ── el modelo de mentira: dos mundos, hilos de cada uno, agentes y uno que pide esconderse ──
const hilo = (nombre, o = {}) => ({ id: `@${nombre.length}`, nombre, vivo: true, activo: false, archivado: false, vinculado: true,
    ruta: `/casa/${nombre}`, relativa: nombre.toLowerCase(), prioridad: 0, atencion: 'ninguna', visto: null, tiempo: 0, sesiones: [], ...o });
modelo.leido = true; modelo.viva = true;
// (después de enviar, la página relee los hilos: aquí no hay a quién)
modelo.sondear = async () => {};
modelo.secciones = [
    { clave: 'agente:cartero', nombre: 'Cartero', hilos: ['Cartero'], grupo: 'agentes', mundo: 'trabajo' },
    { clave: 'agente:archivista', nombre: 'Archivista', hilos: ['Archivista'], grupo: 'agentes' },
    { clave: 'agente:huerta', nombre: 'Huerta', hilos: ['Huerta'], grupo: 'agentes', mundo: 'personal' },
    { clave: 'agente:jardin', nombre: 'Jardín', hilos: ['Jardín'], grupo: 'agentes', mundo: 'personal', fuera_de_su_mundo: 'esconder' },
];
const reciente = new Date(Date.now() - 3600_000).toISOString();
modelo.hilos = [
    hilo('Faro', { mundo: 'trabajo', actividad: reciente }),
    hilo('Molino', { mundo: 'trabajo', vivo: false }),
    hilo('Viejo', { mundo: 'trabajo', archivado: true }),
    hilo('Libre'),
    hilo('Casa', { mundo: 'personal', actividad: reciente }),
    hilo('Cartero', { mundo: 'trabajo', agente: 'cartero' }),
    hilo('Jardín', { mundo: 'personal', agente: 'jardin' }),
    hilo('Jardín › T12 la poda', { mundo: 'personal', agente: 'jardin', padre: 'Jardín' }),
    hilo('Lejano', { mundo: 'trabajo', remoto: 'servidor' }),
];
mundo.recibir({ mundos: [{ nombre: 'trabajo', color: '', horario: [] }, { nombre: 'personal', color: '', horario: [] }], mundos_fuera: 'trabajo' });
assert.equal(mundo.puesto().mundo, 'trabajo');

const FILA = { texto: 'Pedir las bolsas', id: 'T84', ref: 'T84', proveedor: 'tareas', direccion: 'tarea:T84', ficha: true, hecho: false, en_curso: false,
    origen: 'tareas', cuando: null, url: '', hilo: '', ruta: '' };
const montar = c => { document.body.innerHTML = MW.barra(c); return q('.mensaje'); };
const campo = () => q('.mensaje-campo');
const escribir = t => { campo().value = t; campo().dispatchEvent(new w.Event('input', { bubbles: true })); };

// ── 3. el selector respeta el mundo: lo del puesto, también en el modo todo; en el orden y con los íconos de ⌘K ──
{
    montar({ direccion: 'tarea:T84', fila: FILA, sobre: 'T84' });
    await dormir(20);
    const nombres = () => MW.opciones(MW.estado('tarea:T84')).map(o => (o.separador ? `[${o.label}]` : o.label));
    const esperado = ['su hilo · Faro', 'hilo nuevo', '[hilos]', 'Libre', 'Molino', 'Viejo', '[agentes]', 'Cartero', 'Archivista'];
    assert.deepEqual(nombres(), esperado, 'su hilo, uno nuevo, los hilos (abiertos y recientes primero) y los agentes: los del trabajo y los sin mundo');
    // ⌘K, en el modo todo, muestra lo de otro mundo (al final); la barra no
    mundo.ordenarSolo(true);
    try {
        const [fh, fa] = buscadorHilos.fuentes({ otras: () => [], mostrar() {}, orden() {} });
        const k = [...fh.resultados(''), ...fa.resultados('')].map(r => r.titulo);
        assert.ok(k.includes('Casa') && k.includes('Huerta'), 'en todo, ⌘K nombra lo de otro mundo');
        assert.ok(!k.includes('Jardín') && !k.some(t => t.startsWith('Jardín')), 'menos lo de un agente que pide esconderse');
        assert.deepEqual(nombres(), esperado, 'la barra, en todo, igual: solo lo del mundo puesto');
    } finally { mundo.ordenarSolo(false); }
    // los íconos de ⌘K: abierto lleno, sin ventana vacío, archivado su ícono, el agente el suyo; y sus tintas
    const op = Object.fromEntries(MW.opciones(MW.estado('tarea:T84')).map(o => [o.label, o]));
    assert.equal(op.Libre.icono, I.lleno); assert.equal(op.Molino.icono, I.vacio); assert.equal(op.Viejo.icono, I.archivar);
    assert.equal(op.Cartero.icono, I.agente);
    assert.deepEqual([op.Libre.color, op.Cartero.color, op['hilo nuevo'].color], ['azul', 'violeta', 'verde']);
    // en personal, lo de personal (y el que pide esconderse, en su mundo, sí)
    mundo.poner('personal');
    assert.deepEqual(nombres().filter(n => !n.startsWith('su hilo') && n !== 'hilo nuevo'),
        ['[hilos]', 'Casa', 'Libre', 'Jardín › T12 la poda', '[agentes]', 'Jardín', 'Archivista', 'Huerta'],
        'en personal, lo suyo (el hijo de un agente, como en ⌘K; el agente con su hilo abierto, primero)');
    mundo.poner('trabajo');
    // uno de otra máquina, solo con bus
    modelo.hayBus = true;
    assert.ok(nombres().includes('Lejano'), 'con bus, el de otra máquina');
    modelo.hayBus = false;
}

// ── 4. la barra: de fábrica, lo que manda, las teclas y lo que dice ──
{
    MW.olvidar(); pedidos.length = 0;
    const el = montar({ direccion: 'tarea:T84', fila: FILA, sobre: 'T84' });
    assert.ok(el.classList.contains('buscando'), 'mientras telar dice cuál es su hilo, «buscando»');
    assert.equal(q('.mensaje-destino-nombre').textContent, 'su hilo');
    assert.equal(document.activeElement, document.body, 'no toma el foco al pintarse');
    await dormir(20);
    assert.deepEqual(pedidos.map(p => p.ruta), ['/api/actuar/adonde'], 'le pregunta a telar adónde, una vez');
    assert.deepEqual(pedidos[0].cuerpo, { direccion: 'tarea:T84', fila: FILA }, 'con la dirección y la fila');
    assert.equal(q('.mensaje-destino-nombre').textContent, 'Faro', 'llegó: su hilo es Faro');
    assert.ok(!q('.mensaje').classList.contains('buscando'));
    assert.match(campo().placeholder, /^escríbele a Faro sobre T84 · ⏎ envía, ⇧⏎ línea nueva$/);
    assert.equal(document.activeElement, document.body, 'ni al llegar su hilo');
    // escribir: el borrador de la tarea (el mismo de la ventana de la instrucción) y enviar, encendido
    campo().focus();
    escribir('revisa si contestó');
    assert.ok(q('.mensaje-enviar').classList.contains('listo'));
    assert.equal(JSON.parse(sessionStorage.getItem('telar.escrito.instruccion:tarea:T84')).texto, 'revisa si contestó', 'el borrador de la instrucción');
    // las letras son del campo: no llegan a los atajos del dashboard; ⌘K sí
    aLaPagina.length = 0;
    tecla(campo(), 'a'); tecla(campo(), '/'); tecla(campo(), 'k', { metaKey: true });
    assert.deepEqual(aLaPagina, ['k'], 'una letra no es un atajo mientras se escribe aquí; ⌘K, sí');
    // ⇧⏎ es una línea nueva (no envía); ⏎ envía
    tecla(campo(), 'Enter', { shiftKey: true });
    await dormir(10);
    assert.ok(!pedidos.some(p => p.ruta === '/api/actuar'), '⇧⏎ no envía');
    const t0 = pedidos.length;
    tecla(campo(), 'Enter');
    assert.equal(campo().value, '', 'lo escrito sale del campo al tiro');
    assert.match(q('.mensaje-dijo').textContent, /enviando a «Faro»/);
    await dormir(20);
    const enviado = pedidos.slice(t0).find(p => p.ruta === '/api/actuar');
    assert.deepEqual(enviado.cuerpo, { nota: 'revisa si contestó', direccion: 'tarea:T84', fila: FILA }, 'lo de la instrucción: la cosa y lo escrito, a su hilo');
    assert.ok(q('.mensaje-dijo.estado-llego'), 'llegó');
    assert.equal(q('.mensaje-dijo .mensaje-a').dataset.mensajeAbrir, 'hilo:Faro', 'a quién, con enlace a su hilo');
    assert.equal(sessionStorage.getItem('telar.escrito.instruccion:tarea:T84'), null, 'sin borrador');
    assert.equal(document.activeElement, campo(), 'el foco sigue en el campo');
    // ⎋ suelta el campo (y no sigue a la página: ahí sería «volver»)
    aLaPagina.length = 0;
    tecla(campo(), 'Escape');
    assert.notEqual(document.activeElement, campo());
    assert.deepEqual(aLaPagina, []);
}

// ── 5. si no llega: por qué, y lo escrito vuelve; repintar no pierde nada ──
{
    actuar = () => ({ error: 'telar no contesta' });
    campo().focus(); escribir('otra cosa');
    q('.mensaje-enviar').click();
    await dormir(20);
    assert.ok(q('.mensaje-dijo.estado-error'));
    assert.match(q('.mensaje-dijo').textContent, /no se envió a «Faro».*telar no contesta/);
    assert.equal(campo().value, 'otra cosa', 'lo escrito vuelve');
    actuar = cuerpo => ({ destino: cuerpo.a || 'Faro', como: 'enviado', prompt: '…', maquina: cuerpo.a === 'Lejano' ? 'servidor' : '' });
    // repintar (el dashboard, cada minuto): lo escrito, el foco y el cursor, donde estaban
    campo().focus(); campo().setSelectionRange(2, 4);
    const antes = MW.foco(document.body);
    document.body.innerHTML = MW.barra({ direccion: 'tarea:T84', fila: FILA, sobre: 'T84' });
    MW.alPintar(document.body, antes);
    assert.equal(campo().value, 'otra cosa');
    assert.equal(document.activeElement, campo());
    assert.deepEqual([campo().selectionStart, campo().selectionEnd], [2, 4]);
    assert.ok(q('.mensaje-dijo.estado-error'), 'y lo último que pasó');
    // sin el foco antes, repintar no lo toma
    campo().blur();
    const nada = MW.foco(document.body);
    document.body.innerHTML = MW.barra({ direccion: 'tarea:T84', fila: FILA, sobre: 'T84' });
    MW.alPintar(document.body, nada);
    assert.notEqual(document.activeElement, campo());
}

// ── 6. elegir a quién: un agente, uno nuevo; lo que manda cambia ──
{
    MW.olvidar(); pedidos.length = 0; sessionStorage.clear();
    montar({ direccion: 'tarea:T84', fila: FILA, sobre: 'T84' });
    await dormir(20);
    q('.mensaje-destino').click();
    await dormir(20);
    const menu = document.querySelector('dialog[open]');
    assert.ok(menu, 'un clic en el destino abre la lista');
    const titulo = f => f.querySelector('.item-titulo').textContent;
    const filas = [...menu.querySelectorAll('.item[data-k]')].map(titulo);
    assert.deepEqual(filas, ['su hilo · Faro', 'hilo nuevo', 'Libre', 'Molino', 'Viejo', 'Cartero', 'Archivista'], 'la lista (ui.menu, filas item()), del mundo puesto');
    [...menu.querySelectorAll('.item[data-k]')].find(f => titulo(f) === 'Cartero').click();
    await dormir(20);
    assert.equal(q('.mensaje-destino-nombre').textContent, 'Cartero', 'elegido');
    assert.equal(document.activeElement, campo(), 'el foco, al campo: se eligió para escribir');
    escribir('ordénalo');
    tecla(campo(), 'Enter', { metaKey: true });
    await dormir(20);
    assert.deepEqual(pedidos.find(p => p.ruta === '/api/actuar').cuerpo, { nota: 'ordénalo', direccion: 'tarea:T84', fila: FILA, a: 'Cartero' }, '⌘⏎ también envía, al agente');
    assert.equal(q('.mensaje-dijo .mensaje-a').dataset.mensajeAbrir, 'hilo:Cartero');
    // lo elegido queda para esa tarea al repintar
    document.body.innerHTML = MW.barra({ direccion: 'tarea:T84', fila: FILA, sobre: 'T84' });
    assert.equal(q('.mensaje-destino-nombre').textContent, 'Cartero');
}

// ── 7. sin hilo propio, sin cosa, y otro mundo pedido ──
{
    MW.olvidar(); sessionStorage.clear();
    adonde = { ...adonde, destino: '', como: '', falta: 'no encuentro el pendiente «T9»', nuevo: false };
    montar({ direccion: 'tarea:T9', fila: { ...FILA, id: 'T9', ref: 'T9', direccion: 'tarea:T9' }, sobre: 'T9' });
    await dormir(20);
    assert.equal(q('.mensaje-destino-nombre').textContent, 'Cartero', 'sin su hilo: el primer agente del mundo puesto, como la ventana');
    assert.match(q('.mensaje-destino').title, /no encuentro el pendiente/, 'y dice por qué');
    assert.ok(!MW.opciones(MW.estado('tarea:T9')).some(o => o.label.startsWith('su hilo') || o.label === 'hilo nuevo'), 'sin su hilo ni uno nuevo en la lista');
    // sin cosa: `[instruccion] destino`, si se ve; si no, uno nuevo
    modelo.instruccionA = 'Archivista';
    montar({ contexto: { texto: 'un chat\ncon líneas', titulo: 'Ana', origen: 'la pestaña «chat»' }, nombre: 'Chat con Ana' });
    assert.equal(q('.mensaje-destino-nombre').textContent, 'Archivista');
    modelo.instruccionA = 'Huerta';
    montar({ contexto: { texto: 'otro', titulo: 'Bea', origen: 'x' }, nombre: 'Chat con Bea' });
    assert.equal(q('.mensaje-destino-nombre').textContent, 'hilo nuevo', 'el de `[instruccion] destino` es de otro mundo: uno nuevo');
    pedidos.length = 0;
    escribir('resúmelo'); tecla(campo(), 'Enter');
    await dormir(20);
    assert.deepEqual(pedidos.find(p => p.ruta === '/api/actuar').cuerpo,
        { nota: 'resúmelo', nuevo: true, nombre: 'Chat con Bea', contexto: { texto: 'otro', titulo: 'Bea', origen: 'x' } }, 'un hilo nuevo con su nombre y el contexto libre');
    // uno pedido que no está en ninguna parte: no cae en otro; se espera y, si no aparece, se pide elegir
    MW.olvidar(); pedidos.length = 0;
    montar({ contexto: { texto: 'algo', titulo: 'x', origen: 'y' }, a: 'Fantasma', llave: 'fantasma' });
    assert.equal(q('.mensaje-destino-nombre').textContent, 'Fantasma');
    assert.ok(q('.mensaje').classList.contains('buscando'));
    escribir('hola'); tecla(campo(), 'Enter');
    await dormir(10_500);
    assert.ok(!pedidos.some(p => p.ruta === '/api/actuar'), 'no se envía a nadie');
    assert.match(q('.mensaje-dijo').textContent, /no encuentro a «Fantasma»: elige a quién/);
    // un destino pedido de otro mundo no se respeta: el de fábrica
    MW.olvidar();
    adonde = { ...adonde, destino: 'Faro', como: 'hilo', falta: '' };
    montar({ direccion: 'tarea:T84', fila: FILA, a: 'Casa' });
    await dormir(20);
    assert.equal(q('.mensaje-destino-nombre').textContent, 'Faro', 'pedir uno de otro mundo no lo trae');
}

// ── 7b. recién abierta la página (sin los hilos leídos): no cae en otro; espera, y envía al pedido ──
{
    MW.olvidar(); sessionStorage.clear(); pedidos.length = 0;
    modelo.leido = false;
    montar({ contexto: { texto: 'algo', titulo: 'x', origen: 'y' }, a: 'Libre', llave: 'recien' });
    assert.ok(q('.mensaje').classList.contains('buscando'), 'sin los hilos leídos, «buscando»');
    assert.equal(q('.mensaje-destino-nombre').textContent, 'Libre', 'con el nombre pedido');
    escribir('hola'); tecla(campo(), 'Enter');
    await dormir(300);
    assert.ok(!pedidos.some(p => p.ruta === '/api/actuar'), 'enviar espera a saber a quién (no abre uno nuevo)');
    modelo.leido = true;
    await dormir(400);
    assert.deepEqual(pedidos.find(p => p.ruta === '/api/actuar')?.cuerpo, { nota: 'hola', a: 'Libre', contexto: { texto: 'algo', titulo: 'x', origen: 'y' } },
        'leídos, al pedido');
}

// ── 8. la ficha en foco: arriba las pestañas, al medio las tarjetas, abajo las acciones y la barra de mensaje ──
{
    MW.olvidar();
    yo.persona = 'ana';
    const fila = (id, o = {}) => ({ ...FILA, texto: `la tarea ${id}`, id, ref: id, direccion: `tarea:${id}`, ...o });
    const DIA = { ahora: '2026-11-24T10:00:00', fecha: '2026-11-24', nombreDia: 'martes', semana: 48, agenda: [], declarados: ['tareas'], fallas: [],
        pendientes: [fila('T1', { cuando: '2026-11-23' }), fila('T2'), fila('T3', { tamano: 'larga' })] };
    let pintado = '';
    const tablero = {
        pantalla: 'foco', teclas: new Map(), ir(p) { this.pantalla = p; }, pintar(h) { pintado = h.join(''); },
        dia: () => DIA, actualizar: async () => {}, tareas: { decididas: new Set(), olvidarFicha() {} },
        proyectos: { deFila: () => undefined },
    };
    const f = new PantallaFoco(tablero);
    f.pintar();
    const i = s => pintado.indexOf(s);
    assert.ok(i('class="pestanas foco-modos"') >= 0 && i('class="pestanas foco-modos"') < i('foco-cuerpo') && i('foco-cuerpo') < i('foco-acciones')
        && i('foco-acciones') < i('class="mensaje'), 'de arriba abajo: pestañas, tarjetas, acciones, mensaje');
    document.body.innerHTML = pintado;
    assert.deepEqual([...document.querySelectorAll('.foco-modos .pestana')].map(p => `${p.dataset.valor}:${p.getAttribute('aria-selected')}:${p.querySelector('.pestana-cuenta').textContent}`),
        ['gestion:true:2', 'concentracion:false:1'], 'gestión abierta, con cuántas hay en cada una');
    assert.equal(q('.mensaje').dataset.mensaje, 'tarea:T1', 'la barra es de la elegida (la primera: venció)');
    assert.match(campo().placeholder, /sobre T1/);
    // elegir otra tarjeta: la barra es de ella
    const otra = [...document.querySelectorAll('[data-accion="foco-elegir"]')].find(t => t.dataset.valor.includes('"T2"'));
    f.acciones['foco-elegir'](otra.dataset.valor);
    document.body.innerHTML = pintado;
    assert.equal(q('.mensaje').dataset.mensaje, 'tarea:T2');
    // la otra pestaña: concentración abierta, sus tarjetas y su barra
    f.acciones['foco-modo']('concentracion');
    document.body.innerHTML = pintado;
    assert.equal(q('.foco-modos .pestana.si').dataset.valor, 'concentracion');
    assert.equal(q('.mensaje').dataset.mensaje, 'tarea:T3');
    // sin tarjetas, ni acciones ni barra
    DIA.pendientes = [];
    f.pintar();
    assert.ok(!pintado.includes('foco-acciones') && !pintado.includes('class="mensaje'), 'nada que decidir: sin acciones ni barra');
}

console.log('mensaje: ok');
await w.happyDOM.close();
process.exit(0);
