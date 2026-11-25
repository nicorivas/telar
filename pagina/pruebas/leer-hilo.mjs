// Prueba de abrir un hilo con una lectura (la ficha de una pestaña con `vista = "lectura"`, el feed «leer»): el ícono de
// la instrucción en la barra de su ficha (src/vistas/dashboard/tareas.ts, `marcoFicha`), con su tono y su ayuda; y lo que
// manda la ventana de la instrucción (src/web/instruccion.ts) al apretarlo: un hilo nuevo, llamado como la lectura, con
// lo que la ficha tiene como contexto libre (src/vistas/dashboard/leer.ts, `paraUnHilo`): el título, el original, de
// dónde viene, los temas, el resumen, el porqué, de dónde salió, lo respondido y lo escrito en «tu lectura». Sin fila ni
// dirección: una lectura no tiene «su hilo». La ficha de una tarea sigue como antes. Corre en Node, con un DOM mínimo
// hecho aquí y un fetch de mentira (nada sale ni se abre): npm run prueba:leer-hilo
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const src = path.join(aqui, '..', 'src');

// ── un DOM mínimo: lo que usa la ventana de la instrucción (elementos con hijos, clases, eventos, <dialog>, <template>) ──
class Nodo {
    constructor(tag = '') {
        this.tagName = tag.toUpperCase(); this.children = []; this.parentElement = null; this.oyentes = {}; this._texto = '';
        this.className = ''; this.title = ''; this.hidden = false; this.value = ''; this.open = false; this.dataset = {}; this.id = '';
        const estilos = {};
        this.style = { setProperty: (k, v) => { estilos[k] = v; }, getPropertyValue: k => estilos[k] ?? '' };
        this.classList = {
            add: (...cs) => { this.className = [...new Set([...this.className.split(' ').filter(Boolean), ...cs])].join(' '); },
            remove: (...cs) => { this.className = this.className.split(' ').filter(c => c && !cs.includes(c)).join(' '); },
            toggle: (c, si) => { (si ?? !this.classList.contains(c)) ? this.classList.add(c) : this.classList.remove(c); },
            contains: c => this.className.split(' ').includes(c),
        };
        if (this.tagName === 'TEMPLATE') this.content = new Nodo('#fragmento');
    }
    get textContent() { return this._texto + this.children.map(c => c.textContent).join(''); }
    set textContent(t) { this._texto = String(t); this.children = []; }
    // la barra de un buscador (componentes/buscador.ts), en un <template>: lo único que se lee de ella es su campo
    set innerHTML(h) {
        if (!this.content) return;
        const barra = new Nodo('div'); barra.className = 'barra-buscar';
        const campo = new Nodo('input'); campo.className = 'buscar';
        barra.appendChild(campo);
        this.content.children = []; this.content.appendChild(barra);
        this.content.html = h;
    }
    // los botones del pie (componentes/boton.ts): cada <button> con sus clases, sus data-* y su texto (sin las etiquetas)
    insertAdjacentHTML(_, h) {
        for (const m of h.matchAll(/<button\b([^>]*)>(.*?)<\/button>/g)) {
            const b = new Nodo('button');
            for (const at of m[1].matchAll(/([\w-]+)="([^"]*)"/g)) {
                if (at[1] === 'class') b.className = at[2];
                if (at[1].startsWith('data-')) b.dataset[at[1].slice(5)] = at[2];
            }
            b._texto = m[2].replace(/<[^>]+>/g, '');
            this.appendChild(b);
        }
    }
    get firstElementChild() { return this.children[0] ?? null; }
    appendChild(n) { n.parentElement?.children.splice(n.parentElement.children.indexOf(n), 1); n.parentElement = this; this.children.push(n); return n; }
    append(...ns) { for (const n of ns) this.appendChild(typeof n === 'string' ? Object.assign(new Nodo('#texto'), { _texto: n }) : n); }
    replaceChildren(...ns) { for (const c of this.children) c.parentElement = null; this.children = []; this.append(...ns); }
    remove() { if (this.parentElement) { this.parentElement.children.splice(this.parentElement.children.indexOf(this), 1); this.parentElement = null; } }
    addEventListener(tipo, fn) { (this.oyentes[tipo] ??= []).push(fn); }
    removeEventListener() {}
    todos() { return this.children.flatMap(c => [c, ...c.todos()]); }
    calza(sel) {
        const m = sel.trim().match(/^([a-z]*)((?:\.[\w-]+)*)((?:\[[^\]]+\])*)$/i);
        if (!m) return false;
        const [, tag, clases, atributos] = m;
        const datos = [...atributos.matchAll(/\[data-([\w-]+)(?:="([^"]*)")?\]/g)];
        return (!tag || this.tagName === tag.toUpperCase()) && clases.split('.').filter(Boolean).every(c => this.classList.contains(c))
            && datos.every(([, k, v]) => this.dataset[k] !== undefined && (v === undefined || this.dataset[k] === v));
    }
    querySelector(sel) { return this.todos().find(n => n.calza(sel)) ?? null; }
    querySelectorAll(sel) { return this.todos().filter(n => n.calza(sel)); }
    getBoundingClientRect() { return { left: 0, right: 100, top: 0, bottom: 100, width: 100, height: 100 }; }
    scrollIntoView() {}
    showModal() { this.open = true; }
    close() { this.open = false; }
    focus() { documento.activeElement = this; }
    setSelectionRange() {}
    click() { disparar(this, { type: 'click' }); }
}
const ventana = new Nodo('#window');
const documento = new Nodo('#document');
documento.body = new Nodo('body');
documento.appendChild(documento.body);
documento.parentElement = ventana;
documento.activeElement = documento.body;
documento.visibilityState = 'visible';
documento.createElement = tag => new Nodo(tag);
/** lo que la página tiene por id: la ficha de lectura deja el porqué que se va escribiendo en `#leer-porque` */
const porId = new Map();
documento.getElementById = id => porId.get(id) ?? null;
function disparar(blanco, datos) {
    let parado = false;
    const e = { ...datos, target: blanco, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }, stopPropagation() { parado = true; } };
    for (let n = blanco; n && !parado; n = n.parentElement) for (const fn of n.oyentes[e.type] ?? []) fn(e);
    return e;
}
ventana.matchMedia = () => ({ matches: false, addEventListener() {} });
ventana.location = { search: '', hash: '', pathname: '/', href: 'http://localhost/' };
globalThis.document = documento;
globalThis.window = ventana;
const almacen = () => { const m = new Map(); return { getItem: k => m.get(k) ?? null, setItem: (k, v) => m.set(k, String(v)), removeItem: k => m.delete(k) }; };
globalThis.sessionStorage = almacen();
globalThis.localStorage = almacen();
globalThis.requestAnimationFrame = fn => setTimeout(fn, 0);

// ── la API de mentira: la ficha de la lectura y la de una tarea, las skills, y lo que se manda a /actuar ──
const LECTURA = {
    titulo: 'Rojas (Instituto del Puerto): 11 millones cambiarían de ocupación a 2035',
    subtitulo: 'núcleo · empleo y economía de la IA · Publicación en LinkedIn · 2026-11-18',
    bloques: [
        { titulo: 'resumen', texto: 'EE. UU. podría tener más empleos en 2035.\nAlrededor de 11 millones cambiarían de ocupación.' },
        { titulo: 'relevancia · núcleo', texto: 'Tema 4, con `personal/obra/ia-empleo/`: el mapa ya tiene el informe.', destacado: true, color: 'verde' },
        { titulo: 'de dónde salió', items: [
            { titulo: 'el original: https://ejemplo.com/rojas', enlace: 'https://ejemplo.com/rojas' },
            { titulo: 'el ítem: personal/referencia/flujo/feed/rojas.md', enlace: '/raiz/personal/referencia/flujo/feed/rojas.md' },
        ] },
    ],
    acciones: [
        { nombre: 'abrir el original', tipo: 'abrir', enlace: 'https://ejemplo.com/rojas', principal: true },
        { nombre: '✓ me interesa', pide: 'por qué', comando: ['lecturas', 'marcar', 'k', 'interesa', '{texto}'] },
    ],
    temas: [{ nombre: 'empleo y economía de la IA', nota: 'personal/obra/ia-empleo/' }],
    fuente: 'Publicación de Ana Rojas en LinkedIn', fecha: '2026-11-18', estado: '✓ me interesa: el contrapunto optimista',
    conexiones: [], tipos: [],
};
const TAREA = { titulo: 'Pedir las bolsas', direccion: 'tarea:T84', bloques: [{ titulo: 'contexto', texto: 'Pedir 500.' }], acciones: [] };
const pedidos = [];
globalThis.fetch = async (url, init = {}) => {
    const u = new URL(String(url), 'http://localhost');
    const cuerpo = init.body ? JSON.parse(init.body) : undefined;
    pedidos.push({ metodo: init.method ?? 'GET', ruta: u.pathname, cuerpo });
    const json = (d, status = 200) => ({ ok: status < 400, status, json: async () => d, text: async () => JSON.stringify(d) });
    if (u.pathname === '/api/tareas/k') return json(LECTURA);
    if (u.pathname === '/api/tareas/T84') return json(TAREA);
    if (u.pathname === '/api/skills') return json({ hilo: '', conversacion: '', remoto: false, skills: [] });
    if (u.pathname === '/api/actuar') return json({ destino: cuerpo.nombre || 'Faro', como: 'abierto', prompt: '…' });
    if (u.pathname === '/api/actuar/adonde') return json({ destino: 'Faro', como: 'hilo', maquina: '', carpeta: 'casa', nuevo: true, contexto: '[contexto: T84]', falta: '', titulo: 'Pedir las bolsas', propio: false });
    return json({ error: 'no está en la prueba' }, 404);
};

const dir = mkdtempSync(path.join(tmpdir(), 'leer-hilo-'));
const entrada = path.join(dir, 'entrada.ts');
const de = (...r) => JSON.stringify(path.join(src, ...r));
writeFileSync(entrada, [
    `export { PantallaTareas } from ${de('vistas', 'dashboard', 'tareas.ts')};`,
    `export { paraUnHilo } from ${de('vistas', 'dashboard', 'leer.ts')};`,
    `export { I } from ${de('web', 'iconos.ts')};`,
    `export { NUEVO } from ${de('web', 'instruccion.ts')};`,
].join('\n'));
const salida = path.join(dir, 'leer-hilo.cjs');
await build({ entryPoints: [entrada], bundle: true, platform: 'node', format: 'cjs', outfile: salida, logLevel: 'warning', loader: { '.css': 'text' } });
const L = require(salida);

// el tablero de mentira: la pestaña «leer» de un proveedor de lectura, con una pieza; y una tarea en «tareas»
const fila = (id, proveedor, extra = {}) => ({ texto: id, hecho: false, en_curso: false, id, ref: id, origen: proveedor, proveedor, ficha: true,
    cuando: null, url: '', hilo: '', ruta: '', ...extra });
const DIA = { ahora: '2026-11-18T10:00:00', fecha: '2026-11-18', nombreDia: 'miércoles', semana: 47, agenda: [], declarados: ['lecturas', 'tareas'], fallas: [],
    pendientes: [fila('k', 'lecturas', { pestana: 'leer', etiquetas: ['nucleo'], avance: 'núcleo 2026-11-18', color: 'verde', url: 'https://ejemplo.com/rojas' }),
        fila('T84', 'tareas', { direccion: 'tarea:T84' })] };
let pintado = null;
const tablero = {
    pantalla: 'dashboard', teclas: new Map(),
    abrir() {}, montar() {}, alFrente() {}, render() {}, parcial() {}, atajosEnBarra: () => [],
    ir(p) { this.pantalla = p; },
    pintar(h, barra) { pintado = { h: h.join(''), barra }; },
    nombrePestana: k => (k.startsWith('pestana:') ? k.slice(8) : k === 'revisar' ? 'tareas' : k),
    dia: () => DIA, diaLeido: async () => DIA, actualizar: async () => {}, accion: async () => {}, bloqueAbierto: () => '',
    config: () => ({ pestanas: [{ nombre: 'leer', vista: 'lectura' }], bloques: [] }),
    proyectos: { asegurar: async () => false, nombreDe: () => '' }, planes: {}, paginas: { html: () => [] },
};
const pantalla = new L.PantallaTareas(tablero);
tablero.tareas = pantalla;
const espera = (ms = 20) => new Promise(r => setTimeout(r, ms));
const dialogo = () => documento.body.children.find(n => n.tagName === 'DIALOG' && n.open);
const instruccion = barra => barra.acciones.find(a => a.accion === 'instruccion-ficha');

// 1. lo que va como contexto: todo lo que la ficha tiene, en un texto con sus líneas
{
    const r = L.paraUnHilo({ pagina: LECTURA, fila: DIA.pendientes[0], clave: 'leer:lecturas:k' }, 'me hace pensar en el mapa', 'leer');
    assert.equal(r.nombre, LECTURA.titulo, 'el hilo se llama como la lectura');
    assert.equal(r.contexto.titulo, LECTURA.titulo);
    assert.equal(r.contexto.origen, 'la pestaña «leer»');
    const t = r.contexto.texto;
    assert.match(t, /^lectura: Rojas \(Instituto del Puerto\): 11 millones/);
    assert.match(t, /^original: https:\/\/ejemplo\.com\/rojas$/m);
    assert.match(t, /^de dónde viene: Publicación de Ana Rojas en LinkedIn · 2026-11-18$/m);
    assert.match(t, /^temas: empleo y economía de la IA \(personal\/obra\/ia-empleo\/\)$/m);
    assert.match(t, /^id en el feed: k$/m);
    assert.match(t, /^resumen:\nEE\. UU\. podría tener más empleos en 2035\.\nAlrededor de 11 millones/m, 'el resumen, con sus líneas');
    assert.match(t, /^relevancia · núcleo:\nTema 4/m, 'el porqué');
    assert.match(t, /^de dónde salió:\n- el original: https:\/\/ejemplo\.com\/rojas\n- el ítem: personal\/referencia\/flujo\/feed\/rojas\.md \(\/raiz\/personal/m,
        'los enlaces, sin repetir el que ya dice su título');
    assert.match(t, /^lo que respondí: ✓ me interesa: el contrapunto optimista$/m);
    assert.match(t, /^lo que escribí en «tu lectura», sin responder:\nme hace pensar en el mapa$/m);
    assert.doesNotMatch(t, /^dirección:/m, 'las lecturas no tienen dirección');
    // sin lo respondido ni lo escrito, no hay esas líneas; con dirección, va escrita
    const sin = L.paraUnHilo({ pagina: { ...LECTURA, estado: '' }, fila: { ...DIA.pendientes[0], direccion: 'lectura:k' }, clave: 'x' }).contexto.texto;
    assert.doesNotMatch(sin, /lo que respondí|lo que escribí/);
    assert.match(sin, /^dirección: lectura:k$/m);
    // lo anotado en esta pasada, si la ficha releída no lo trae
    assert.match(L.paraUnHilo({ pagina: { ...LECTURA, estado: '' }, anotado: '✗ no me interesa', clave: 'x' }).contexto.texto, /^lo que respondí: ✗ no me interesa$/m);
}

// 2. la ficha de la lectura: en su barra, el ícono de la instrucción, en violeta, con la ayuda de abrir un hilo con ella
{
    await pantalla.abrirPestana('leer');
    await espera();
    assert.equal(tablero.pantalla, 'tarea');
    assert.match(pintado.h, /id="leer"/, 'la ficha de lectura');
    const a = instruccion(pintado.barra);
    assert.ok(a, 'el ícono de la instrucción en la barra de la ficha');
    assert.equal(a.icono, L.I.instruccion);
    assert.equal(a.tono, 'violeta', 'el tono de la instrucción, como en la ficha de una tarea');
    assert.match(a.ayuda, /^instrucción: abrir un hilo con esta lectura/);
    // lo que va a la izquierda de las flechas: el ícono antes de ← →, como en la ficha de una tarea
    assert.deepEqual(pintado.barra.acciones.map(x => x.accion).slice(-1), ['instruccion-ficha'], 'una sola pieza: sin ← → no hay más');
}

// 3. apretarlo abre la ventana de la instrucción: «un hilo nuevo» elegido, con la lectura como contexto; mandar va a
//    POST /actuar con un hilo nuevo, su nombre y el contexto libre, sin fila ni dirección (no va a «su hilo»)
{
    const porque = new Nodo('textarea'); porque.value = 'me hace pensar en el mapa';
    porId.set('leer-porque', porque);
    pedidos.length = 0;
    const hecho = pantalla.acciones['instruccion-ficha']('', {});
    await espera();
    const c = dialogo();
    assert.ok(c, 'la ventana se abre');
    assert.ok(c.classList.contains('web-instruccion'), 'la de la instrucción, la de siempre');
    assert.ok(!c.todos().some(n => n.classList.contains('de') && !n.classList.contains('libre')),
        'sin entidad: no hay fila de «de qué se habla» con dirección');
    const libre = c.todos().find(n => n.classList.contains('libre'));
    assert.ok(libre, 'la lectura, como contexto libre');
    assert.match(libre.textContent, /Rojas \(Instituto del Puerto\)/);
    assert.match(libre.textContent, /desde la pestaña «leer»/);
    const elegida = c.todos().find(n => n.classList.contains('web-op') && n.classList.contains('sel') && /un hilo nuevo/.test(n.textContent));
    assert.ok(elegida, '«un hilo nuevo» viene elegido');
    assert.match(elegida.textContent, /«Rojas \(Instituto del Puerto\): 11 millones[^»]*», en la raíz/, 'llamado como la lectura');
    assert.ok(!pedidos.some(p => p.ruta === '/api/actuar/adonde'), 'no busca «su hilo»: una lectura no tiene');
    const nota = c.querySelector('textarea');
    nota.value = 'conversemos si cambia el mapa';
    disparar(nota, { type: 'input' });
    assert.match(c.querySelector('.llega').textContent, /^le llega: conversemos si cambia el mapa \[contexto: «Rojas/);
    c.todos().find(n => n.tagName === 'BUTTON' && n.dataset.mandar !== undefined && n.textContent === '⌘⏎mandar').click();
    await hecho;
    const mandado = pedidos.find(p => p.ruta === '/api/actuar');
    assert.ok(mandado, 'manda la instrucción');
    assert.equal(mandado.metodo, 'POST');
    const { contexto, ...resto } = mandado.cuerpo;
    assert.deepEqual(resto, { direccion: '', skill: '', nota: 'conversemos si cambia el mapa', escribir: false, nuevo: true, nombre: LECTURA.titulo },
        'un hilo nuevo con su nombre, sin fila ni dirección');
    assert.equal(contexto.titulo, LECTURA.titulo);
    assert.equal(contexto.origen, 'la pestaña «leer»');
    assert.match(contexto.texto, /^original: https:\/\/ejemplo\.com\/rojas$/m);
    assert.match(contexto.texto, /^relevancia · núcleo:\nTema 4/m);
    assert.match(contexto.texto, /^lo que respondí: ✓ me interesa/m);
    assert.match(contexto.texto, /^lo que escribí en «tu lectura», sin responder:\nme hace pensar en el mapa$/m, 'lo escrito sin responder también');
    assert.ok(!dialogo(), 'la ventana se cerró');
    porId.delete('leer-porque');
}

// 4. la ficha de una tarea, como antes: «su hilo», con /tarea, su fila y su dirección
{
    pedidos.length = 0;
    tablero.pantalla = 'revisar';
    await pantalla.abrirTarea(JSON.stringify(['tareas', 'T84', 'T84']));
    await espera();
    const a = instruccion(pintado.barra);
    assert.match(a.ayuda, /^instrucción: mandársela a su hilo/);
    const hecho = pantalla.acciones['instruccion-ficha']('', {});
    await espera();
    const c = dialogo();
    assert.ok(c);
    assert.ok(pedidos.some(p => p.ruta === '/api/actuar/adonde' && p.cuerpo.direccion === 'tarea:T84'), 'busca su hilo');
    c.querySelector('textarea').value = '¿quedó?';
    c.todos().find(n => n.tagName === 'BUTTON' && n.dataset.mandar !== undefined && n.textContent === '⌘⏎mandar').click();
    await hecho;
    const mandado = pedidos.find(p => p.ruta === '/api/actuar');
    assert.equal(mandado.cuerpo.direccion, 'tarea:T84');
    assert.equal(mandado.cuerpo.fila.ref, 'T84');
    assert.equal(mandado.cuerpo.contexto, undefined);
    assert.ok(!mandado.cuerpo.nuevo);
}

console.log('leer-hilo: ok');
process.exit(0);
