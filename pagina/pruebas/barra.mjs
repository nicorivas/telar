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
    export { PantallaAgentes } from './src/vistas/dashboard/agentes';`);
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
// uno suyo (la lista dice `alcanzable: false`)
{
    modelo.hilos = [hilo('Molino', { mundo: 'trabajo' }),
        hilo('Vista', { mundo: 'trabajo', remoto: 'laptop', alcanzable: false, atencion: 'trabajando', fuera_de_linea_desde: new Date(Date.now() - 7200e3).toISOString() })];
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
        assert.match(fila(id), /laptop fuera de línea desde \d\d:\d\d: inalcanzable/, `${id}: desde cuándo`);
        assert.doesNotMatch(fila(id), /circulo tam-grande[^"]*" style="--lleno: 0%"|trabajando/, `${id}: ni dormido ni trabajando`);
    }
    assert.match(fila('data-id="laptop|Catedral"'), /cuando se fue, dormía/);
    assert.match(fila('data-id="laptop|Nave"'), /cuando se fue, trabajaba/);
    assert.match(fila('data-id="laptop|Nave"'), /class="item[^"]*apagada/, 'apagada, como antes');
}

console.log('prueba:barra ok');
