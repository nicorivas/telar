// Prueba de quién se ve en la barra de hilos y cómo se anida (src/vistas/hilos-familia.ts), y de la barra de verdad que lo
// usa (src/vistas/hilos.ts), dibujada en Node con hilos de mentira. El hilo que se mira (el mostrado) se ve aunque el mundo
// o el modo puestos lo dejen afuera, y con él su familia: sus padres, para quedar anidado, y sus descendientes, que salen
// de «de personal». Ahí adentro, cada hijo va bajo su padre, como en HILOS. Y el agente de un hijo que se mira, aunque su
// hilo sea de otro mundo. Corre en Node, sin página: npm run prueba:barra
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const carpeta = mkdtempSync(path.join(tmpdir(), 'barra-'));
const armar = async (nombre, contents) => {
    const outfile = path.join(carpeta, `${nombre}.cjs`);
    await build({ stdin: { contents, resolveDir: path.join(aqui, '..'), loader: 'ts' }, bundle: true, platform: 'node', format: 'cjs',
        outfile, logLevel: 'warning' });
    return require(outfile);
};
const F = await armar('familia', `export * from './src/vistas/hilos-familia';`);

// ── 1. la familia del mostrado ──

// Telar (personal) con sus hijos Links y Contestadas, y Nieto bajo Links; Faro, del trabajo; Molino, personal y suelto
const PADRES = new Map([['Telar', ''], ['Links', 'Telar'], ['Contestadas', 'Telar'], ['Nieto', 'Links'], ['Faro', ''], ['Molino', '']]);
const orden = s => [...s].sort();
assert.deepEqual(orden(F.familiaDe('Telar', PADRES)), ['Contestadas', 'Links', 'Nieto', 'Telar'], 'el mostrado y sus descendientes');
assert.deepEqual(orden(F.familiaDe('Links', PADRES)), ['Links', 'Nieto', 'Telar'], 'un hijo: su cadena de padres y los suyos, no sus hermanos');
assert.deepEqual(orden(F.familiaDe('Nieto', PADRES)), ['Links', 'Nieto', 'Telar'], 'un nieto: hasta arriba');
assert.deepEqual([...F.familiaDe(undefined, PADRES)], [], 'sin mostrado, nadie');
assert.deepEqual([...F.familiaDe('Otro', PADRES)], ['Otro'], 'uno que no se conoce: él solo');
// un ciclo de padres no la cuelga
assert.deepEqual(orden(F.familiaDe('a', new Map([['a', 'b'], ['b', 'a'], ['c', 'a']]))), ['a', 'b', 'c']);
assert.deepEqual(orden(F.familiaDe('a', new Map([['a', 'a']]))), ['a'], 'padre de sí mismo');

// ── 2. dónde va cada uno: el mundo puesto es el trabajo; el modo muestra solo «cliente» (y lo sin etiquetas) ──

const MUNDO = { Telar: 'personal', Links: 'personal', Contestadas: 'personal', Nieto: 'personal', Faro: 'trabajo', Molino: 'personal' };
const criterio = (mostrado, o = {}) => ({ mostrado, padres: PADRES, etiquetas: o.etiquetas ?? new Map(), agentes: o.agentes,
    modo: et => !et.length || et.includes('cliente'), mundo: mu => !mu || mu === 'trabajo' });
const lugares = (mostrado, o) => {
    const r = F.repartir(criterio(mostrado, o));
    return Object.fromEntries(Object.keys(MUNDO).map(n => [n, r.donde(n, undefined, MUNDO[n])]));
};
assert.deepEqual(lugares(undefined), { Telar: 'fuera', Links: 'fuera', Contestadas: 'fuera', Nieto: 'fuera', Faro: 'lista', Molino: 'fuera' },
    'sin mostrado: lo personal, en «de personal»');
assert.deepEqual(lugares('Telar'), { Telar: 'lista', Links: 'lista', Contestadas: 'lista', Nieto: 'lista', Faro: 'lista', Molino: 'fuera' },
    'Telar se mira: sube con sus hijos y su nieto (el caso real)');
assert.deepEqual(lugares('Links'), { Telar: 'lista', Links: 'lista', Contestadas: 'fuera', Nieto: 'lista', Faro: 'lista', Molino: 'fuera' },
    'un hijo se mira: sube con su padre (para quedar anidado) y su hijo; su hermano no');
// el modo: Links con etiquetas propias que el modo no muestra, y Nieto sin propias, que hereda las de Links
{
    const etiquetas = new Map([['Links', ['casa']]]);
    assert.deepEqual(lugares(undefined, { etiquetas }), { Telar: 'fuera', Links: '', Contestadas: 'fuera', Nieto: '', Faro: 'lista', Molino: 'fuera' },
        'el modo esconde a Links y a Nieto, que hereda sus etiquetas');
    assert.deepEqual(lugares('Telar', { etiquetas }), { Telar: 'lista', Links: 'lista', Contestadas: 'lista', Nieto: 'lista', Faro: 'lista', Molino: 'fuera' },
        'mirando a Telar, el modo tampoco los esconde');
    const r = F.repartir(criterio(undefined, { etiquetas }));
    assert.equal(r.donde('Links', ['cliente'], 'personal'), 'fuera', 'las etiquetas que se le pasan mandan sobre las sabidas');
}
// los hijos de un agente cuelgan de él (diga lo que diga su `padre`): mirar uno trae al agente
{
    const padres = new Map([...PADRES, ['Secretaría', ''], ['Secretaría › T454 el test', 'Telar'], ['Encargo', 'Secretaría › T454 el test']]);
    const familia = m => orden(F.repartir({ ...criterio(m, { agentes: ['Secretaría'] }), padres }).familia);
    assert.deepEqual(familia('Secretaría › T454 el test'), ['Encargo', 'Secretaría', 'Secretaría › T454 el test'], 'el hijo de un agente: el agente, no Telar');
    assert.deepEqual(familia('Encargo'), ['Encargo', 'Secretaría', 'Secretaría › T454 el test'], 'el hijo del hijo: hasta el agente');
    assert.deepEqual(familia('Secretaría › T9 nuevo'), ['Secretaría', 'Secretaría › T9 nuevo'], 'uno que todavía no está en la lista');
    assert.ok(!familia('Telar').includes('Secretaría › T454 el test'), 'se dibuja bajo su agente, no bajo Telar');
}

// ── 3. anidar: cada fila bajo su padre ──

{
    const fila = (nombre, padre) => ({ nombre, padre });
    const ver = filas => F.anidar(filas, f => f.nombre, f => f.padre).map(a => `${'·'.repeat(a.hondo)}${a.fila.nombre}${a.padre ? `<${a.padre.nombre}` : ''}`);
    assert.deepEqual(ver([fila('Faro'), fila('Links', 'Telar'), fila('Telar'), fila('Nieto', 'Links'), fila('Contestadas', 'Telar'),
        fila('Huérfano', 'No está'), fila('Yo', 'Yo')]),
    ['Faro', 'Telar', '·Links<Telar', '··Nieto<Links', '·Contestadas<Telar', 'Huérfano', 'Yo'],
    'los de arriba en su orden; los hijos bajo su padre, en el suyo; un padre que no está o él mismo: arriba');
    assert.deepEqual(ver([fila('A', 'B'), fila('B', 'A'), fila('C')]), ['C', '·A', '··B<A'], 'un ciclo: al final, colgado un nivel');
    assert.deepEqual(ver([fila('X'), fila('X', 'Y'), fila('Y')]), ['X', 'Y'], 'dos con el mismo nombre: el primero');
}

// ── 4. la barra de verdad (src/vistas/hilos.ts), en Node ──

const almacen = new Map();
globalThis.localStorage = { getItem: k => almacen.get(k) ?? null, setItem: (k, v) => almacen.set(k, String(v)), removeItem: k => almacen.delete(k) };
globalThis.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {}, addListener() {} });
const P = await armar('pagina', `export { BarraHilos } from './src/vistas/hilos'; export { modelo } from './src/modelo';
    export * as mundo from './src/web/mundo'; export * as buscadorHilos from './src/web/buscador-hilos';
    export { PantallaAgentes } from './src/vistas/dashboard/agentes'; export { I } from './src/web/iconos';`);
const { modelo, mundo } = P;

const hilo = (nombre, o = {}) => ({ id: `@${nombre.length}`, nombre, vivo: true, activo: false, archivado: false, vinculado: true,
    ruta: `/casa/${nombre}`, relativa: nombre.toLowerCase(), prioridad: 0, atencion: 'ninguna', visto: null, tiempo: 0, sesiones: [], ...o });
modelo.leido = true; modelo.viva = true;
modelo.secciones = [{ clave: 'agente:secretaria', nombre: 'Secretaría', hilos: ['Secretaría'], grupo: 'agentes' }];
modelo.hilos = [
    hilo('Faro', { mundo: 'trabajo' }),
    hilo('Telar', { mundo: 'personal' }),
    hilo('Links', { mundo: 'personal', padre: 'Telar' }),
    hilo('Contestadas', { mundo: 'personal', padre: 'Telar' }),
    hilo('Nieto', { mundo: 'personal', padre: 'Links' }),
    hilo('Molino', { mundo: 'personal' }),
    hilo('Secretaría', { mundo: 'personal', agente: 'secretaria' }),
    hilo('Secretaría › T454 el test', { mundo: 'personal', agente: 'secretaria' }),
];
mundo.recibir({ mundos: [{ nombre: 'trabajo', color: '', horario: [] }, { nombre: 'personal', color: '', horario: [] }], mundos_fuera: 'trabajo' });
assert.equal(mundo.puesto().mundo, 'trabajo');

/** La barra como texto: una línea por fila, con un «·» por nivel; las de otra máquina con su «máquina:»; las cabeceras y
 *  los submenús entre corchetes. */
const barra = (mostrado, otras = []) => {
    const recordado = { 'telar.cabeceras': { __otros_mundos: true } };
    const b = new P.BarraHilos();
    b.estado = { get: k => recordado[k], update: async () => {} };
    b.mostrado = mostrado; b.otras = otras;
    const filas = [];
    for (const [, clases, attrs] of b.html().matchAll(/<div class="item([^"]*)"([^>]*)>/g)) {
        const a = Object.fromEntries([...attrs.matchAll(/data-([a-z]+)="([^"]*)"/g)].map(x => [x[1], x[2]]));
        const hondo = Number(/hondo(\d)/.exec(clases)?.[1] ?? 0);
        const nombre = a.hilo ?? (a.accion === 'ir-remoto' ? a.id.replace('|', ':') : a.accion === 'seccion' ? `[${a.id}]` : '');
        if (nombre) filas.push(`${'·'.repeat(hondo)}${nombre}`);
    }
    return filas;
};
const desde = (filas, desdeAqui) => filas.slice(filas.indexOf(desdeAqui));

// sin mirar nada de lo personal: HILOS trae a Faro; «de personal», a Telar con sus hijos anidados (antes iban planos), y
// el agente, de otro mundo, no se ve (ni su hijo)
assert.deepEqual(desde(barra('Faro'), '[__hilos]'),
    ['[__hilos]', 'Faro', '[__otros_mundos]', 'Telar', '·Links', '··Nieto', '·Contestadas', 'Molino']);
assert.ok(!barra('Faro').includes('Secretaría'), 'el agente de otro mundo no se ve');

// el caso real: mirando a Telar, sube a HILOS con sus hijos y su nieto, anidados, y salen de «de personal»
assert.deepEqual(desde(barra('Telar'), '[__hilos]'),
    ['[__hilos]', 'Faro', 'Telar', '·Links', '··Nieto', '·Contestadas', '[__otros_mundos]', 'Molino']);
// mirando a Links: sube su padre (para que quede anidado) y su hijo; Contestadas se queda abajo, arriba de su lista
assert.deepEqual(desde(barra('Links'), '[__hilos]'),
    ['[__hilos]', 'Faro', 'Telar', '·Links', '··Nieto', '[__otros_mundos]', 'Contestadas', 'Molino']);

// los de otra máquina, igual: un hijo de Telar en el servidor sube con él, anidado; sin mirar, va bajo Telar abajo
const servidor = [{ nombre: 'servidor', en_linea: true, edad: 0, hilos: [
    { nombre: 'Rama', vivo: true, padre: 'Telar', mundo: 'personal' },
    { nombre: 'Lejano', vivo: true, mundo: 'personal' }] }];
assert.deepEqual(desde(barra('Telar', servidor), '[__hilos]'),
    ['[__hilos]', 'Faro', 'Telar', '·Links', '··Nieto', '·Contestadas', '·servidor:Rama', '[__otros_mundos]', 'Molino', 'servidor:Lejano']);
assert.deepEqual(desde(barra('Faro', servidor), '[__otros_mundos]'),
    ['[__otros_mundos]', 'Telar', '·Links', '··Nieto', '·Contestadas', '·servidor:Rama', 'Molino', 'servidor:Lejano']);
// y mirando uno de allá, su padre de aquí sube con él
assert.deepEqual(desde(barra('Rama', servidor), '[__hilos]'),
    ['[__hilos]', 'Faro', 'Telar', '·servidor:Rama', '[__otros_mundos]', 'Links', '·Nieto', 'Contestadas', 'Molino', 'servidor:Lejano']);

// el hijo de un agente de otro mundo: mirarlo trae al agente, con el hijo colgado de él (antes no se veía en ninguna parte)
{
    const filas = barra('Secretaría › T454 el test');
    const i = filas.indexOf('Secretaría');
    assert.ok(i >= 0 && i < filas.indexOf('[__hilos]'), 'el agente, en AGENTES');
    assert.equal(filas[i + 1], '·Secretaría › T454 el test', 'su hijo, colgado de él');
}

// un agente sin hilo abierto va por el mundo de su carpeta (o la etiqueta de su hilo: `GET /mundos`, lo que dicen las
// grillas de ⚙ modos y ⚙ mundos): el de otro mundo no se ve; el de este y el sin clasificar, sí; y sin saberlo, se ve
{
    const sinHilo = clave => new RegExp(`data-accion="abrir-agente"[^>]*data-id="agente:${clave}"`);
    const html = () => { const b = new P.BarraHilos(); b.estado = { get: () => undefined, update: async () => {} }; b.mostrado = 'Faro'; b.otras = []; return b.html(); };
    modelo.secciones = [...modelo.secciones, ...['oficina', 'huerta', 'archivista'].map(c => ({ clave: `agente:${c}`, nombre: c, hilos: [c], grupo: 'agentes' }))];
    assert.ok(['oficina', 'huerta', 'archivista'].every(c => sinHilo(c).test(html())), 'sin saber de qué mundo son, se ven');
    mundo.recibirDetalle({ mundos: [{ nombre: 'trabajo', color: '', horario: [], areas: [], rutas: [], etiquetas: [], color_propio: '' },
        { nombre: 'personal', color: '', horario: [], areas: [], rutas: [], etiquetas: [], color_propio: '' }], fuera: 'trabajo', tintas: [],
        agentes: [{ clave: 'oficina', nombre: 'oficina', carpeta: 'agentes/oficina/', mundo: 'trabajo', por: 'ruta', valor: 'agentes/oficina/' },
            { clave: 'huerta', nombre: 'huerta', carpeta: 'agentes/huerta/', mundo: 'personal', por: 'ruta', valor: 'agentes/huerta/' },
            { clave: 'archivista', nombre: 'archivista', carpeta: 'agentes/archivista/', mundo: '', por: '', valor: '' }] });
    const h = html();
    assert.ok(sinHilo('oficina').test(h) && sinHilo('archivista').test(h), 'el de este mundo y el sin clasificar, sí');
    assert.ok(!sinHilo('huerta').test(h), 'el de otro mundo por su carpeta, no');
    // el mundo que trae su sección (`telar config`: el de su agente.toml, aquí «personal») vale antes de leer `GET /mundos`,
    // y le gana a lo que diga ahí: un agente privado no se asoma ni un momento al abrir la página en el trabajo
    modelo.secciones = [...modelo.secciones, { clave: 'agente:jardin', nombre: 'Jardín', hilos: ['Jardín'], grupo: 'agentes', mundo: 'personal' }];
    assert.ok(!sinHilo('jardin').test(html()), 'su sección dice personal: no se ve en el trabajo');
    mundo.poner('');
    assert.ok(sinHilo('jardin').test(html()), 'con ambos, sí');
    mundo.poner('personal');
    assert.ok(sinHilo('jardin').test(html()) && !sinHilo('oficina').test(html()), 'en personal, él sí y el del trabajo no');
    mundo.poner('trabajo');
    // con un hilo suyo abierto va por el mundo de su hilo (el que derivó telar, que también mira su agente.toml)
    modelo.hilos = [...modelo.hilos, hilo('Jardín', { mundo: 'personal', agente: 'jardin' })];
    assert.ok(!barra('Faro').includes('Jardín'), 'abierto, tampoco se ve en el trabajo');
    // en el modo todo (donde el mundo solo ordena), la barra igual obedece al mundo: el 23-nov, en todo y en el trabajo,
    // la barra mostraba un agente personal con la pantalla compartida. Lo de otro mundo va al final, plegado; el agente, no sale
    mundo.ordenarSolo(true);
    try {
        assert.ok(mundo.seVe('personal'), 'en todo, las listas siguen viendo todo');
        const filas = barra('Faro');
        assert.ok(!filas.includes('Jardín'), 'en todo, el agente abierto de otro mundo no se ve en el trabajo');
        modelo.hilos = modelo.hilos.filter(x => x.nombre !== 'Jardín');
        assert.ok(!sinHilo('jardin').test(html()) && !sinHilo('huerta').test(html()), 'ni cerrado');
        assert.ok(sinHilo('oficina').test(html()), 'el del trabajo, sí');
        assert.deepEqual(desde(barra('Faro'), '[__hilos]'),
            ['[__hilos]', 'Faro', '[__otros_mundos]', 'Telar', '·Links', '··Nieto', '·Contestadas', 'Molino'], 'los hilos de otro mundo, al final, plegados');
    } finally { mundo.ordenarSolo(false); }
    modelo.hilos = modelo.hilos.filter(x => x.nombre !== 'Jardín');
    modelo.secciones = modelo.secciones.filter(x => x.clave !== 'agente:jardin');
}

// lo de un agente de otro mundo, fuera de la barra: ⌘K (sus hilos y sus agentes, web/buscador-hilos.ts), la vista de
// agentes y los destinos de la instrucción (`agentesQueSeVen`, `hiloDeAgenteAjeno`), según lo que pide su agente.toml
// (`fuera_de_su_mundo`): al-final, el de fábrica (en todo, sale al final, como lo demás); esconder (ni en todo: el 23-nov,
// en todo y en el trabajo, los tres nombraban a un agente personal, y se quiso así para él); ver (en todos los mundos)
{
    const secciones = modelo.secciones, hilos = modelo.hilos;
    const conFuera = f => {
        modelo.secciones = [...secciones, { clave: 'agente:jardin', nombre: 'Jardín', hilos: ['Jardín'], grupo: 'agentes', mundo: 'personal',
            ...(f ? { fuera_de_su_mundo: f } : {}) }, { clave: 'agente:bodega', nombre: 'Bodega', hilos: ['Bodega'], grupo: 'agentes' }];
    };
    modelo.hilos = [...hilos, hilo('Jardín', { mundo: 'personal', agente: 'jardin' }),
        hilo('Jardín › T12 la poda', { mundo: 'personal', padre: 'Jardín' }),
        hilo('Registro', { mundo: 'personal', padre: 'Jardín › T12 la poda' })];
    const otras = [{ nombre: 'servidor', hilos: [{ nombre: 'Jardín › T13', vivo: true, mundo: 'personal', agente: 'jardin' },
        { nombre: 'Huerto', vivo: true, mundo: 'personal' }] }];
    const [fh, fa] = P.buscadorHilos.fuentes({ otras: () => otras, mostrar() {}, orden() {} });
    const k = () => [...fh.resultados(''), ...fa.resultados('')].map(r => r.titulo);
    const vista = () => {
        let pintado = [];
        const v = new P.PantallaAgentes({ pintar: h => { pintado = h; } });
        v.lista = [{ agente: { clave: 'secretaria', nombre: 'Secretaría' }, mundo: 'trabajo', encargos: [] },
            { agente: { clave: 'jardin', nombre: 'Jardín' }, mundo: 'personal', encargos: [] }];
        v.pintar();
        return pintado.join('');
    };
    const destinos = () => [...P.mundo.agentesQueSeVen(modelo.secciones.filter(x => x.grupo === 'agentes'), modelo.hilos).map(a => a.nombre),
        // (los hilos, sin el de cada agente, que va como agente: como en web/instruccion.ts)
        ...modelo.hilos.filter(h => !modelo.secciones.some(a => a.grupo === 'agentes' && a.hilos.includes(h.nombre))
            && !P.mundo.hiloDeAgenteAjeno(h, modelo.hilos)).map(h => h.nombre)];
    const suyo = t => t.startsWith('Jardín') || t === 'Registro';
    const enTodo = f => { mundo.ordenarSolo(true); try { return f(); } finally { mundo.ordenarSolo(false); } };
    mundo.poner('trabajo');

    // de fábrica (sin la línea, o al-final): lo de hoy
    conFuera(undefined);
    assert.equal(P.mundo.fueraDe('jardin'), 'al-final', 'sin la línea, al-final');
    assert.ok(!k().includes('Jardín') && !k().includes('Jardín › T13') && !vista().includes('Jardín'), 'en el trabajo, ni en ⌘K ni en la vista');
    assert.ok(!destinos().includes('Jardín'), 'ni en los destinos');
    assert.ok(!barra('Faro').includes('Jardín'), 'ni en la barra');
    enTodo(() => {
        assert.ok(k().includes('Jardín') && k().includes('Jardín › T13'), 'en todo, en ⌘K (al final, por su mundo)');
        assert.ok(vista().includes('Jardín') && destinos().includes('Jardín'), 'en todo, en la vista y en los destinos');
        assert.ok(!barra('Faro').includes('Jardín'), 'la barra, ni en todo');
    });

    // esconder: ni en todo, ni sus hijos (de aquí o de otra máquina), ni el hijo de un hijo
    conFuera('esconder');
    enTodo(() => {
        const enK = k();
        assert.ok(!enK.some(suyo), 'en todo y en el trabajo, ⌘K no nombra al que se esconde, ni a los suyos');
        assert.ok(enK.includes('Telar') && enK.includes('Huerto'), 'lo demás de personal sí sale: en todo, el mundo ordena');
        assert.ok(enK.includes('Bodega') && enK.includes('huerta'), 'un agente sin mundo sabido, sí; el de personal que no se esconde, también');
        const v = vista();
        assert.ok(v.includes('Secretaría') && !v.includes('Jardín'), 'la vista de agentes, sin él');
        assert.match(v, /uno más, de otro mundo/, 'contado, sin nombre');
        const d = destinos();
        assert.ok(!d.some(suyo), 'los destinos de la instrucción, sin él ni los suyos');
        assert.ok(d.includes('oficina') && d.includes('huerta') && d.includes('Telar'), 'los demás, sí');
    });
    mundo.poner('personal');
    assert.ok(k().includes('Jardín') && k().includes('Jardín › T13') && vista().includes('Jardín') && destinos().includes('Jardín'),
        'en su mundo, en los tres');
    mundo.poner('');
    assert.ok(k().includes('Jardín') && vista().includes('Jardín'), 'con ambos, también');
    mundo.poner('trabajo');

    // ver: en todos los mundos, también en la barra
    conFuera('ver');
    assert.ok(k().includes('Jardín') && vista().includes('Jardín') && destinos().includes('Jardín'), 'en el trabajo, en los tres');
    assert.ok(barra('Faro').includes('Jardín'), 'y en la barra');

    // lo que escribe ⚙ mundos (`GET /mundos`, lo último) le gana a la sección (de cuando se leyó `telar config`)
    conFuera('esconder');
    const detalle = P.mundo.detalles();
    P.mundo.recibirDetalle({ ...detalle, agentes: [...detalle.agentes, { clave: 'jardin', nombre: 'Jardín', carpeta: '', mundo: 'personal',
        por: 'agente.toml', valor: '', fuera_de_su_mundo: 'al-final' }] });
    assert.equal(P.mundo.fueraDe('agente:jardin'), 'al-final');
    P.mundo.recibirDetalle(detalle);
    mundo.poner('trabajo');
    modelo.secciones = secciones; modelo.hilos = hilos;
}

// un agente que vive en otra máquina y cuya carpeta todavía no llega a esta (su sección trae `maquina`, de la foto de
// allá): sale en AGENTES con su hilo de allá, una sola vez (no también en HILOS), sin casa, y por su mundo
{
    const secciones = modelo.secciones;
    modelo.secciones = [...secciones, { clave: 'agente:lejano', nombre: 'Lejano', hilos: ['Lejano'], home: false, grupo: 'agentes',
        mundo: 'personal', maquina: 'servidor' }];
    const servidor = [{ nombre: 'servidor', en_linea: true, edad: 0, hilos: [{ nombre: 'Lejano', vivo: true, mundo: 'personal' }] }];
    mundo.poner('personal');
    const filas = barra('Faro', servidor);
    assert.equal(filas.filter(f => f === 'servidor:Lejano').length, 1, 'una sola vez');
    assert.ok(filas.indexOf('servidor:Lejano') < filas.indexOf('[__hilos]'), 'en AGENTES');
    const b = new P.BarraHilos(); b.estado = { get: () => undefined, update: async () => {} }; b.mostrado = 'Faro'; b.otras = [];
    const sinHilo = b.html();
    assert.ok(/data-accion="abrir-agente"[^>]*data-id="agente:lejano"/.test(sinHilo), 'sin hilo vivo allá: se abre (allá)');
    assert.ok(!/data-accion="home"[^>]*data-id="agente:lejano"/.test(sinHilo), 'sin casa aquí');
    mundo.poner('trabajo');
    assert.ok(!barra('Faro', servidor).includes('servidor:Lejano'), 'de personal: en el trabajo no sale');
    modelo.secciones = secciones;
}

// ── 4b. el «↳» y la sangría, solo bajo el padre de verdad, y visible en la misma sección ──
// El 24-nov, en la página del servidor, «Vitrina flujo» (padre: un agente) se veía «↳» justo bajo «Vitrina»
// (otro hilo, del laptop), y tres hilos sueltos con «↳» bajo otro hilo: el «↳» de quién lo abrió, puesto
// aunque su padre no estuviera a la vista, parecía colgarlos del de arriba. Ahora: bajo su padre si se ve; bajo su agente,
// en AGENTES, si el padre es un agente; si no, suelto y sin «↳» (quién lo abrió y de quién cuelga, en la ayuda)
{
    const secciones = modelo.secciones, hilos = modelo.hilos;
    modelo.secciones = [...secciones, { clave: 'agente:cartero', nombre: 'Cartero', hilos: ['Cartero'], grupo: 'agentes', mundo: 'trabajo' }];
    const abrio = (por, o = {}) => ({ padre: por, abierto_por: { por, agente: '', cuando: '2026-11-24T21:00:00', icono: '', ...o } });
    const ficha = { etiqueta: 'Tienda · Vitrina nueva' };
    modelo.hilos = [...hilos,
        hilo('Cartero', { mundo: 'trabajo', agente: 'cartero', icono: '◆' }),
        // padre agente, con un hijo suyo debajo (tres niveles: Cartero › flujo › Momentos)
        hilo('Vitrina', { mundo: 'trabajo', ficha }),
        hilo('Vitrina flujo', { mundo: 'trabajo', ficha, ...abrio('Cartero') }),
        hilo('Momentos', { mundo: 'trabajo', ...abrio('Vitrina flujo') }),
        // padre archivado
        hilo('Archivista › T458 Aspas', { mundo: 'trabajo', vivo: false, archivado: true }),
        hilo('Aspas', { mundo: 'trabajo', ...abrio('Archivista › T458 Aspas') }),
        // lo abrió un agente (su letra) desde un hijo suyo que ya no está
        hilo('Cartas', { mundo: 'trabajo', ...abrio('Archivista › T532 Cartas', { agente: 'archivista', icono: 'A' }) }),
        // padre de otro mundo (Telar, personal, sin mirarlo)
        hilo('Cruce', { mundo: 'trabajo', padre: 'Telar' }),
        // tres niveles reales en HILOS
        hilo('F1', { mundo: 'trabajo', padre: 'Faro' }),
        hilo('F2', { mundo: 'trabajo', ...abrio('F1') }),
    ];
    // en otra máquina: uno cuyo padre no tiene ventana aquí, y uno bajo «Vitrina flujo», que va con él bajo Cartero
    const servidor = [{ nombre: 'servidor', en_linea: true, edad: 0, hilos: [
        { nombre: 'Lejos', vivo: true, mundo: 'trabajo', padre: 'Nadie de aquí' },
        { nombre: 'Bajo flujo', vivo: true, mundo: 'trabajo', padre: 'Vitrina flujo' }] }];
    const b = new P.BarraHilos();
    b.estado = { get: () => undefined, update: async () => {} };
    b.mostrado = 'Faro'; b.otras = servidor;
    const html = b.html();
    const filas = [];
    for (const m of html.matchAll(/<div class="item([^"]*)"([^>]*)>/g)) {
        const a = Object.fromEntries([...m[2].matchAll(/data-([a-z]+)="([^"]*)"/g)].map(x => [x[1], x[2]]));
        const nombre = a.hilo ?? (a.accion === 'ir-remoto' ? a.id.replace('|', ':') : a.accion === 'seccion' ? `[${a.id}]` : '');
        const fin = html.indexOf('<div class="item', m.index + 1);
        const suyo = html.slice(m.index, fin < 0 ? undefined : fin);
        if (nombre) filas.push({ nombre, hondo: Number(/hondo(\d)/.exec(m[1])?.[1] ?? 0), html: suyo,
            titulo: /<span class="item-titulo">([^<]*)</.exec(suyo)?.[1] ?? '' });
    }
    const de = n => { const f = filas.find(x => x.nombre === n); assert.ok(f, `está ${n}`); return f; };
    const linea = filas.map(f => `${'·'.repeat(f.hondo)}${f.nombre}`);
    const agentes = linea.slice(linea.indexOf('[__agentes]'), linea.indexOf('[__hilos]'));
    const enHilos = linea.slice(linea.indexOf('[__hilos]'));
    // padre agente: bajo él, en AGENTES, con los suyos debajo (también el de otra máquina), y no en HILOS
    const g = agentes.indexOf('Cartero');
    assert.deepEqual(agentes.slice(g, g + 4), ['Cartero', '·Vitrina flujo', '··Momentos', '··servidor:Bajo flujo'], 'bajo su agente, tres niveles');
    assert.ok(!enHilos.some(x => /Vitrina flujo|Momentos|Bajo flujo/.test(x)), 'y no se repiten en HILOS');
    const cuenta = Number(/data-id="__hilos"[^]*?item-sufijo[^>]*>(\d+)</.exec(html)?.[1]);
    assert.equal(cuenta, enHilos.slice(1).findIndex(x => x.startsWith('[')), 'la cuenta de HILOS, sin los que van bajo su agente');
    // tres niveles reales en HILOS
    const f = enHilos.indexOf('Faro');
    assert.deepEqual(enHilos.slice(f, f + 3), ['Faro', '·F1', '··F2'], 'abuelo, padre e hijo, cada uno visible');
    // padre archivado, de otro mundo, en otra máquina sin ventana aquí, o un hijo de agente que ya no está: sueltos
    for (const n of ['Aspas', 'Cartas', 'Cruce', 'servidor:Lejos', 'Vitrina']) {
        assert.equal(de(n).hondo, 0, `${n}: sin sangría`);
        assert.ok(!de(n).html.includes(P.I.hijo), `${n}: sin «↳»`);
    }
    assert.match(de('Aspas').html, /lo abrió «Archivista › T458 Aspas»/, 'quién lo abrió, en la ayuda');
    assert.match(de('Cruce').html, /cuelga de «Telar»/, 'de quién cuelga, en la ayuda');
    assert.match(de('servidor:Lejos').html, /cuelga de «Nadie de aquí»/, 'también el de otra máquina');
    assert.match(de('Cartas').html, /item-prefijo[^>]*>A</, 'el que abrió un agente lleva su letra, no un «↳»');
    // los que sí cuelgan, con su «↳»
    for (const n of ['Vitrina flujo', 'Momentos', 'F1', 'F2']) assert.ok(de(n).html.includes(P.I.hijo), `${n}: con «↳»`);
    // dos con el mismo título (el de la ficha de su carpeta): cada uno con su nombre, para no confundirlos
    assert.equal(de('Vitrina').titulo, 'Vitrina');
    assert.equal(de('Vitrina flujo').titulo, 'Vitrina flujo');
    // el agente plegado o escondido: su hijo vuelve a HILOS, suelto
    {
        const b2 = new P.BarraHilos();
        b2.estado = { get: k => k === 'telar.cabeceras' ? { __agentes: false } : undefined, update: async () => {} };
        b2.mostrado = 'Faro'; b2.otras = servidor;
        const h2 = b2.html();
        assert.match(h2, /<div class="item(?![^"]*hondo)[^"]*"[^>]*data-hilo="Vitrina flujo"/, 'AGENTES plegado: suelto en HILOS');
        assert.match(h2, /<div class="item[^"]*hondo1[^"]*"[^>]*data-hilo="Momentos"/, 'y su hijo, bajo él');
    }
    modelo.secciones = secciones; modelo.hilos = hilos;
}

// ── 4c. ARCHIVO: los de esta máquina y los de las otras, de su foto, marcados con su máquina ──
// El 24-nov, la página del servidor decía «archivo 36»: solo los suyos. Los del laptop (215) no viajaban en su foto.
// Ahora viajan (`archivados`) y van aquí, con su máquina y «retomar en M»; con el filtro de mundo de siempre
{
    const hilos = modelo.hilos;
    modelo.hilos = [...hilos,
        hilo('Propio', { mundo: 'trabajo', vivo: false, archivado: true }),
        hilo('Propio personal', { mundo: 'personal', vivo: false, archivado: true }),
        // archivado aquí siendo del laptop (su conversación vive allá): sale una vez, el de aquí, con «retomar en laptop»
        hilo('Mudado', { mundo: 'trabajo', vivo: false, archivado: true, dueno: 'laptop' })];
    const laptop = [{ nombre: 'laptop', en_linea: true, edad: 0, hilos: [{ nombre: 'Vivo allá', vivo: true, mundo: 'trabajo' }],
        archivados: [
            { nombre: 'Del laptop', relativa: 'empresa/x', mundo: 'trabajo', actividad: '2026-11-20T10:00:00' },
            { nombre: 'Del laptop personal', mundo: 'personal' },
            { nombre: 'Sin mundo', mundo: '' },
            { nombre: 'Mudado', mundo: 'trabajo' },
            { nombre: 'Vivo allá', mundo: 'trabajo' },
            { nombre: 'Faro', mundo: 'trabajo' }] }];
    const b = new P.BarraHilos();
    b.estado = { get: k => k === 'telar.cabeceras' ? { __archivo: true, __otros_mundos: true } : undefined, update: async () => {} };
    b.mostrado = 'Faro'; b.otras = laptop;
    const html = b.html();
    const enArchivo = html.slice(html.indexOf('data-id="__archivo"'), html.indexOf('data-id="__otros_mundos"'));
    const ids = [...enArchivo.matchAll(/<div class="item[^"]*"[^>]*?(?:data-hilo="([^"]*)"|data-id="([^"]*)")/g)].map(m => m[1] ?? m[2]);
    for (const n of ['Propio', 'Mudado', 'laptop|Del laptop', 'laptop|Sin mundo']) assert.ok(ids.includes(n), `en ARCHIVO: ${n}`);
    for (const n of ['Propio personal', 'laptop|Del laptop personal']) assert.ok(!ids.includes(n), `de otro mundo, no: ${n}`);
    assert.ok(!ids.includes('laptop|Mudado'), 'el que aquí ya está (archivado aquí siendo de allá) no se repite');
    assert.ok(!ids.includes('laptop|Vivo allá'), 'uno que vive allá no va al archivo');
    assert.ok(!ids.includes('laptop|Faro'), 'uno con el mismo nombre que uno de aquí, tampoco');
    const cuenta = Number(/data-id="__archivo"[^]*?item-sufijo[^>]*>(\d+)</.exec(html)?.[1]);
    assert.equal(cuenta, ids.length, 'la cuenta, con los de allá');
    const fila = id => { const i = enArchivo.indexOf(`data-id="${id}"`); return enArchivo.slice(enArchivo.lastIndexOf('<div class="item', i), enArchivo.indexOf('<div class="item', i + 1)); };
    assert.match(fila('laptop|Del laptop'), /data-accion="retomar-remoto"[^>]*data-id="laptop\|Del laptop"[^>]*title="retomar en laptop/, '«retomar en laptop»');
    assert.match(fila('laptop|Del laptop'), /class="item[^"]*apagada/, 'tenue, como los archivados de aquí');
    assert.match(fila('laptop|Del laptop'), /archivado en laptop/, 'su máquina, en la ayuda y en su columna');
    assert.ok(b.archivadoAlla('laptop:Del laptop') && !b.archivadoAlla('laptop:Vivo allá'), 'se mira en su conversación, no en una terminal');
    // el buscador de HILOS los filtra también
    almacen.set('telar.barra.buscado', JSON.stringify({ hilos: 'empresa/x' }));
    const b2 = new P.BarraHilos();
    b2.estado = b.estado; b2.mostrado = 'Faro'; b2.otras = laptop;
    const h2 = b2.html();
    assert.ok(h2.includes('data-id="laptop|Del laptop"') && !h2.includes('data-id="laptop|Sin mundo"'), 'lo buscado, también en los de allá');
    almacen.delete('telar.barra.buscado');
    modelo.hilos = hilos;
}

// ── 4d. la fila elegida: la que se mira lleva el fondo de selección (.activa), y ninguna otra ──
// El 25-nov la barra dejó de marcar la fila del hilo que se miraba. La página llama lo que se mira por su clave
// (navegador/app.ts, `mostrar`): el nombre a secas si vive aquí, «rem:<máquina>:<hilo>» si se mira en otra; y desde la
// mudanza la página sigue al hilo a donde vive (web/donde-vive.ts), así que uno llevado al servidor se mira como
// «rem:servidor:X» y su fila es la de la foto. La barra comparaba el nombre a secas, y solo en las filas de aquí: las de
// otra máquina, los hijos de un agente de allá y los archivados de allá nunca quedaban marcados. Aquí, con las claves
// de verdad, en cada sección
{
    const hilos = modelo.hilos;
    modelo.hilos = [...hilos,
        // una ventana de aquí que mira un hilo del servidor
        hilo('Ventana', { mundo: 'trabajo', remoto: 'servidor' }),
        // archivado aquí siendo del laptop
        hilo('Mudado', { mundo: 'trabajo', vivo: false, archivado: true, dueno: 'laptop' })];
    const otras = [
        { nombre: 'servidor', en_linea: true, edad: 0, hilos: [
            { nombre: 'Llevado', vivo: true, mundo: 'trabajo' },
            { nombre: 'Rama', vivo: true, padre: 'Telar', mundo: 'personal' },
            { nombre: 'Secretaría › T9 lejos', vivo: true, mundo: 'personal', agente: 'secretaria' },
            // el mismo nombre que uno de aquí: mirar el de aquí no marca este
            { nombre: 'Molino', vivo: true, mundo: 'personal' }] },
        { nombre: 'laptop', en_linea: true, edad: 0, hilos: [], archivados: [{ nombre: 'Del laptop', mundo: 'trabajo' }] }];
    const activas = (mostrado, dashboard = false) => {
        const b = new P.BarraHilos();
        b.estado = { get: k => k === 'telar.cabeceras' ? { __archivo: true, __otros_mundos: true } : undefined, update: async () => {} };
        b.aqui = 'laptop2'; b.mostrado = mostrado; b.otras = otras; b.dashboardActivo = dashboard;
        return [...b.html().matchAll(/<div class="item([^"]*)"([^>]*)>/g)].filter(([, c]) => /\bactiva\b/.test(c))
            .map(([, , a]) => /data-hilo="([^"]*)"/.exec(a)?.[1] ?? /data-id="([^"]*)"/.exec(a)?.[1]);
    };
    assert.deepEqual(activas('Faro'), ['Faro'], 'uno de aquí: su fila');
    assert.deepEqual(activas('Links'), ['Links'], 'un hijo de aquí, bajo su padre');
    assert.deepEqual(activas('Secretaría'), ['Secretaría'], 'un agente, en AGENTES');
    assert.deepEqual(activas('Secretaría › T454 el test'), ['Secretaría › T454 el test'], 'el hijo de un agente, bajo él');
    assert.deepEqual(activas('rem:servidor:Llevado'), ['servidor|Llevado'], 'uno de otra máquina (llevado allá): su fila de la foto');
    assert.deepEqual(activas('rem:servidor:Rama'), ['servidor|Rama'], 'uno de allá que cuelga de uno de aquí');
    assert.deepEqual(activas('rem:servidor:Secretaría › T9 lejos'), ['servidor|Secretaría › T9 lejos'], 'el hijo de un agente, de allá, bajo él');
    assert.deepEqual(activas('rem:laptop:Del laptop'), ['laptop|Del laptop'], 'un archivado de otra máquina, abierto');
    assert.deepEqual(activas('Ventana'), ['Ventana'], 'una ventana de aquí que mira allá, por su nombre');
    assert.deepEqual(activas('rem:servidor:Ventana'), ['Ventana'], 'y por la clave de allá');
    assert.deepEqual(activas('rem:laptop:Mudado'), ['Mudado'], 'uno archivado aquí siendo de allá, por la clave de allá');
    assert.deepEqual(activas('Molino'), ['Molino'], 'el de aquí, no el de allá con el mismo nombre');
    assert.deepEqual(activas('rem:laptop2:Faro'), ['Faro'], 'la clave de otra máquina que es esta: el de aquí');
    assert.deepEqual(activas('Faro', true), [], 'en el dashboard, ninguna');
    // mirar uno de allá con su clave de verdad trae a su familia, como uno de aquí: Rama sube a HILOS bajo Telar
    {
        const b = new P.BarraHilos();
        b.estado = { get: k => k === 'telar.cabeceras' ? { __otros_mundos: true } : undefined, update: async () => {} };
        b.mostrado = 'rem:servidor:Rama'; b.otras = otras;
        const html = b.html();
        const hilosA = html.slice(html.indexOf('data-id="__hilos"'), html.indexOf('data-id="__otros_mundos"'));
        assert.ok(hilosA.includes('data-id="servidor|Rama"') && hilosA.includes('data-hilo="Telar"'), 'Rama y Telar, en HILOS');
    }
    modelo.hilos = hilos;
}

// ── 4e. dónde vive: el satélite solo si vive en otra máquina, y al pasar el mouse, en cuál ──
// El 25-nov la persona vio «Bitácora» marcado como si viviera en el servidor. En la página del laptop no lo lleva; en la del
// servidor sí, porque allá vive en otra máquina (el laptop), y lo dice al pasar el mouse. Las dos páginas, aquí: la del
// laptop con ventanas que miran al servidor, y la del servidor con los del laptop en su foto
{
    const hilos = modelo.hilos;
    const lugar = (html, clave) => {
        const i = html.indexOf(clave);
        assert.ok(i >= 0, `está: ${clave}`);
        const fila = html.slice(html.lastIndexOf('<div class="item', i), html.indexOf('<div class="item', i + 1));
        const ranuras = fila.slice(fila.indexOf('item-inicio')).split('item-ranura').slice(1, 4);
        const ultima = ranuras[2] ?? '';
        return /tono-remoto/.test(ultima) ? (/title="([^"]*)"/.exec(ultima)?.[1] ?? 'sin ayuda') : '';
    };
    const pagina = (aqui, locales, otras) => {
        modelo.hilos = locales;
        const b = new P.BarraHilos();
        b.estado = { get: k => k === 'telar.cabeceras' ? { __otros_mundos: true } : undefined, update: async () => {} };
        b.aqui = aqui; b.mostrado = 'Faro'; b.otras = otras;
        return b.html();
    };
    // la del laptop: Bitácora y Aspas viven aquí; Cartero es una ventana que mira al servidor
    const enLaptop = pagina('laptop', [
        hilo('Faro', { mundo: 'trabajo', maquina: 'laptop' }),
        hilo('Bitácora', { mundo: 'trabajo', maquina: 'laptop' }),
        hilo('Aspas', { mundo: 'trabajo', maquina: 'laptop', padre: 'Cartero' }),
        hilo('Cartero', { mundo: 'trabajo', maquina: 'servidor', remoto: 'servidor' })],
    [{ nombre: 'servidor', en_linea: true, edad: 0, hilos: [{ nombre: 'Cartero', vivo: true, mundo: 'trabajo' }] }]);
    assert.equal(lugar(enLaptop, 'data-hilo="Bitácora"'), '', 'en el laptop, Bitácora vive aquí: sin satélite');
    assert.equal(lugar(enLaptop, 'data-hilo="Aspas"'), '', 'Aspas, tampoco');
    assert.equal(lugar(enLaptop, 'data-hilo="Cartero"'), 'vive en servidor', 'la ventana que mira al servidor: con satélite, y dice cuál');
    // la del servidor: Cartero vive aquí; Bitácora y Aspas, en el laptop (de su foto)
    const enServidor = pagina('servidor', [hilo('Cartero', { mundo: 'trabajo', maquina: 'servidor' })],
        [{ nombre: 'laptop', en_linea: true, edad: 0, hilos: [
            { nombre: 'Faro', vivo: true, mundo: 'trabajo' }, { nombre: 'Bitácora', vivo: true, mundo: 'trabajo' },
            { nombre: 'Aspas', vivo: true, mundo: 'trabajo', padre: 'Cartero' }] }]);
    assert.equal(lugar(enServidor, 'data-hilo="Cartero"'), '', 'en el servidor, Cartero vive aquí: sin satélite');
    assert.equal(lugar(enServidor, 'data-id="laptop|Bitácora"'), 'vive en laptop', 'Bitácora vive en el laptop: con satélite, y dice cuál');
    assert.equal(lugar(enServidor, 'data-id="laptop|Aspas"'), 'vive en laptop', 'Aspas, igual');
    modelo.hilos = hilos;
}

// ── 5. un solo buscador, el de HILOS: filtra los vivos y los archivados ──
// Escribir abre ARCHIVO con solo los archivados que calzan (y su número), sin tocar lo que la persona dejó recordado;
// plegarlo mientras se busca dura lo que dura lo escrito; al borrar, vuelve a como estaba. ARCHIVO ya no tiene buscador
// ni orden propios
{
    modelo.secciones = [{ clave: 'agente:secretaria', nombre: 'Secretaría', hilos: ['Secretaría'], grupo: 'agentes' }];
    modelo.hilos = [
        hilo('Faro', { mundo: 'trabajo' }),
        hilo('Faroles', { mundo: 'trabajo' }),
        hilo('Molino', { mundo: 'trabajo' }),
        hilo('Farola vieja', { mundo: 'trabajo', vivo: false, archivado: true }),
        hilo('Puente', { mundo: 'trabajo', vivo: false, archivado: true }),
        hilo('Huerto', { mundo: 'trabajo', vivo: false, archivado: true }),
    ];
    almacen.set('telar.barra.buscado', JSON.stringify({ archivo: 'puente' }));
    const recordado = {};
    const b = new P.BarraHilos();
    b.estado = { get: k => recordado[k], update: async (k, v) => { recordado[k] = v; } };
    b.mostrado = 'Faro'; b.otras = [];
    // las filas como en `barra`, y cada una con su grupo (el buscador que la filtra)
    const ver = () => {
        const html = b.html(), filas = [];
        for (const [, , attrs] of html.matchAll(/<div class="item([^"]*)"([^>]*)>/g)) {
            const a = Object.fromEntries([...attrs.matchAll(/data-([a-z]+)="([^"]*)"/g)].map(x => [x[1], x[2]]));
            if (a.hilo) filas.push(`${a.hilo}${a.grupo ? `/${a.grupo}` : ''}`);
            else if (a.accion === 'seccion') filas.push(`[${a.id}]`);
        }
        const cuenta = /data-id="__archivo".*?<\/div>/s.exec(html)?.[0].match(/>(\d+)</)?.[1];
        return { filas: desde(filas, '[__hilos]'), buscadores: [...html.matchAll(/<input class="buscar"[^>]*data-grupo="([^"]*)"/g)].map(x => x[1]),
            ordenes: [...html.matchAll(/data-accion="orden-grupo" data-id="([^:"]*):/g)].map(x => x[1]), cuenta };
    };
    let v = ver();
    assert.deepEqual(v.filas, ['[__hilos]', 'Faro/hilos', 'Faroles/hilos', 'Molino/hilos', '[__archivo]'], 'sin buscar: el archivo plegado, como empieza');
    assert.equal(v.cuenta, '3', 'con todos los archivados contados');
    assert.deepEqual(v.buscadores, ['hilos'], 'un solo buscador');
    assert.ok(v.ordenes.every(g => g === 'hilos'), 'y un solo orden');

    b.buscar('hilos', 'FARO');
    v = ver();
    assert.deepEqual(v.filas, ['[__hilos]', 'Faro/hilos', 'Faroles/hilos', 'Molino/hilos', '[__archivo]', 'Farola vieja/hilos'],
        'buscando: el archivo abierto con solo el que calza, y lo filtra el mismo buscador (los vivos los esconde la vista, sin redibujar)');
    assert.equal(v.cuenta, '1', 'su número es el de los que calzan');
    assert.deepEqual(v.buscadores, ['hilos'], 'abierto, tampoco trae buscador propio');
    assert.equal(recordado['telar.cabeceras'], undefined, 'abrirlo así no se recuerda');

    b.buscar('hilos', 'molino');
    assert.ok(!ver().filas.includes('[__archivo]'), 'si no calza ningún archivado, el archivo no sale');

    // plegarlo mientras se busca: solo mientras dure lo escrito
    // (en la página, escribir redibuja la lista; aquí, sin DOM, la dibuja `ver`: lo que el pliegue mira es lo dibujado)
    b.buscar('hilos', 'faro'); ver();
    b.alternarArchivo();
    assert.deepEqual(ver().filas.slice(-1), ['[__archivo]'], 'plegado a mano mientras se busca');
    assert.equal(recordado['telar.cabeceras'], undefined, 'tampoco se recuerda');
    b.buscar('hilos', 'farol');
    assert.deepEqual(ver().filas.slice(-1), ['[__archivo]'], 'sigue plegado mientras se escribe');

    b.buscar('hilos', '');
    v = ver();
    assert.deepEqual(v.filas.slice(-1), ['[__archivo]'], 'al borrar: plegado, como lo dejó la persona');
    assert.equal(v.cuenta, '3');

    // si la persona lo dejó abierto, al borrar vuelve abierto con todos; buscando, igual solo los que calzan
    b.alternarArchivo();
    assert.deepEqual(recordado['telar.cabeceras'], { __archivo: true }, 'abierto a mano sin buscar: se recuerda');
    assert.deepEqual(ver().filas.slice(4), ['[__archivo]', 'Farola vieja/hilos', 'Puente/hilos', 'Huerto/hilos']);
    b.buscar('hilos', 'puen');
    assert.deepEqual(ver().filas.slice(4), ['[__archivo]', 'Puente/hilos'], 'buscando, solo el que calza');
    b.alternarArchivo(); b.buscar('hilos', '');
    assert.deepEqual(ver().filas.slice(4), ['[__archivo]', 'Farola vieja/hilos', 'Puente/hilos', 'Huerto/hilos'],
        'plegarlo buscando no toca lo recordado: al borrar, abierto otra vez');
    assert.deepEqual(recordado['telar.cabeceras'], { __archivo: true });
    assert.ok(!JSON.parse(almacen.get('telar.barra.buscado')).archivo, 'lo que quedó escrito en el buscador viejo del archivo, se olvida');
}

// ── 6. los dormidos (telar.dormir): su aro tenue en la ranura de la atención, en HILOS, en AGENTES y los de otra máquina;
// si terminó y no lo has visto, su diana, tenue; y la ayuda dice desde cuándo duerme y que abrirlo lo despierta ──
{
    modelo.secciones = [{ clave: 'agente:secretaria', nombre: 'Secretaría', hilos: ['Secretaría'], grupo: 'agentes' }];
    const dormido = { desde: '2026-11-19T14:32:00', conversacion: 'abc12345' };
    modelo.hilos = [
        hilo('Faro', { mundo: 'trabajo', dormido }),
        hilo('Puente', { mundo: 'trabajo', dormido, atencion: 'termino', sin_ver: true }),
        hilo('Molino', { mundo: 'trabajo', atencion: 'termino', sin_ver: true }),
        hilo('Secretaría', { mundo: 'trabajo', agente: 'secretaria', dormido }),
    ];
    const b = new P.BarraHilos();
    b.estado = { get: () => undefined, update: async () => {} };
    b.mostrado = 'Molino';
    b.otras = [{ nombre: 'servidor', en_linea: true, edad: 0, hilos: [{ nombre: 'Lejano', vivo: true, dormido: true, mundo: 'trabajo' }] }];
    const html = b.html();
    // la ranura de la atención de cada fila: el segundo círculo del inicio (el primero es la prioridad)
    const fila = id => {
        const i = html.indexOf(id);
        assert.ok(i >= 0, `está ${id}`);
        const desde = html.lastIndexOf('<div class="item', i);
        return html.slice(desde, html.indexOf('<div class="item', i));
    };
    const aro = /tono-tenue[^"]*"[^>]*><span class="circulo tam-grande" style="--lleno: 0%"/;
    const diana = /tono-tenue[^"]*"[^>]*><span class="circulo tam-grande fig-diana"/;
    assert.match(fila('data-hilo="Faro"'), aro, 'dormido: un aro tenue');
    assert.match(fila('data-hilo="Faro"'), /duerme desde las 14:32: su agente se cerró por estar quieto; abrirlo o escribirle lo despierta/);
    assert.match(fila('data-hilo="Puente"'), diana, 'dormido y sin ver: su diana, tenue');
    assert.match(fila('data-hilo="Puente"'), /terminó y no lo has visto · duerme/);
    assert.doesNotMatch(fila('data-hilo="Molino"'), /tono-tenue[^"]*"[^>]*><span class="circulo tam-grande/, 'despierto, como siempre');
    assert.match(fila('data-hilo="Secretaría"'), aro, 'en AGENTES, igual');
    assert.match(fila('data-id="servidor|Lejano"'), aro, 'el de otra máquina, por su foto');
    assert.match(fila('data-id="servidor|Lejano"'), /duerme en servidor/);
}

// una máquina fuera de línea (telar.alcance): sus hilos, inalcanzables. Ni el aro de dormido ni la atención de antes: el
// aro chico de «sin noticias», y en la ayuda desde cuándo y lo que hacía cuando se fue. Lo mismo la ventana de aquí de
// uno suyo (la lista dice `alcanzable: false`). Con el reloj fijo (Date.now, que es lo que la barra lee): se fue hace dos
// horas; a las 15:00 eso es «desde 13:00», y a la 1:01 de la madrugada, del día anterior: «desde ayer 23:01»
const conReloj = (ahora, f) => {
    const real = Date.now;
    Date.now = () => ahora;
    try { return f(); } finally { Date.now = real; }
};
for (const [ahora, esperado] of [[new Date(2026, 10, 24, 15, 0).getTime(), '13:00'], [new Date(2026, 10, 24, 1, 1).getTime(), 'ayer 23:01']]) conReloj(ahora, () => {
    modelo.hilos = [hilo('Molino', { mundo: 'trabajo' }),
        hilo('Vista', { mundo: 'trabajo', remoto: 'laptop', alcanzable: false, atencion: 'trabajando', fuera_de_linea_desde: new Date(ahora - 7200e3).toISOString() })];
    const b = new P.BarraHilos();
    b.estado = { get: () => undefined, update: async () => {} };
    b.mostrado = 'Molino';
    b.otras = [{ nombre: 'laptop', en_linea: false, fuera: true, edad: 7200, cola: [], hechos: [], hilos: [
        { nombre: 'Catedral', vivo: true, dormido: true, mundo: 'trabajo' },
        { nombre: 'Nave', vivo: true, atencion: 'trabajando', mundo: 'trabajo' }] }];
    const html = b.html();
    const fila = id => {
        const i = html.indexOf(id);
        assert.ok(i >= 0, `está ${id}`);
        return html.slice(html.lastIndexOf('<div class="item', i), html.indexOf('<div class="item', i));
    };
    const chico = /tono-tenue[^"]*"[^>]*><span class="circulo tam-chico" style="--lleno: 0%"/;
    for (const id of ['data-id="laptop|Catedral"', 'data-id="laptop|Nave"', 'data-hilo="Vista"']) {
        assert.match(fila(id), chico, `${id}: inalcanzable`);
        assert.ok(fila(id).includes(`laptop fuera de línea desde ${esperado}: inalcanzable`), `${id}: desde cuándo (${esperado})`);
        assert.doesNotMatch(fila(id), /circulo tam-grande[^"]*" style="--lleno: 0%"|trabajando/, `${id}: ni dormido ni trabajando`);
    }
    assert.match(fila('data-id="laptop|Catedral"'), /cuando se fue, dormía/);
    assert.match(fila('data-id="laptop|Nave"'), /cuando se fue, trabajaba/);
    assert.match(fila('data-id="laptop|Nave"'), /class="item[^"]*apagada/, 'apagada, como antes');
});

// las notas (los próximos prompts) que le guardó la persona (web/borradores.ts): al final de su fila, tenues, el ícono y cuántos; también
// el de otra máquina, de su foto
{
    const antes = modelo.hilos;
    modelo.hilos = antes.map(h => h.nombre === 'Molino' ? { ...h, borradores: 2 } : h);
    const b = new P.BarraHilos();
    b.estado = { get: () => undefined, update: async () => {} }; b.mostrado = 'Vista';
    b.otras = [{ nombre: 'servidor', en_linea: true, fuera: false, edad: 0, hilos: [{ nombre: 'Nave', atencion: 'termino', vivo: true, borradores: 1 }] }];
    const html = b.html();
    const filaDe = re => html.split('<div class="item').find(f => re.test(f)) ?? '';
    assert.match(filaDe(/data-hilo="Molino"/), /<span class="item-aviso tono-tenue" title="2 notas: prompts guardados para mandarle[^"]*"><span class="i">\u{eb26}<\/span>2<\/span>/u);
    assert.doesNotMatch(filaDe(/data-hilo="Vista"/), /\u{eb26}/u, 'sin guardados, nada');
    assert.match(filaDe(/data-id="servidor\|Nave"/), /title="1 nota: un prompt guardado[^"]*"><span class="i">\u{eb26}<\/span>1</u);
    modelo.hilos = antes;
}

console.log('prueba:barra ok');
