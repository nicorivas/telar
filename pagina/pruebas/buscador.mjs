// Prueba del buscador (src/componentes/buscador.ts): sus partes en orden (la lupa, el campo, la cuenta, la tecla, el ✕), la
// regla del texto de ayuda (en qué se busca, sin el verbo, y sin dibujarse en el campo: solo la lupa, a un carácter de lo escrito), lo que se escapa, su barra (la fila propia, con sus herramientas a
// la derecha), el ✕ que lo borra (web/buscadores.ts, con un DOM de mentira) y que cada buscador de la página lo use: los del
// inventario del catálogo (componentes/catalogo-buscador.ts, DONDE) lo importan, ninguno se arma a mano, y los que se
// dibujan sin la página (la sección de lista, la paleta, Todo, lo que te espera) salen en su barra. Y lo que ⌘K pregunta
// afuera (web/buscador.ts, `Remotas`; los proyectos, las tareas y los documentos, web/hallados.ts, en un pedido): cuándo
// se pide, lo tardío que se descarta, y que abrir uno es lo mismo que en Todo. Corre en Node, sin página: npm run prueba:buscador
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const src = path.join(aqui, '..', 'src');
const carpeta = mkdtempSync(path.join(tmpdir(), 'buscador-'));
const armar = async (ruta) => {
    const outfile = path.join(carpeta, `${ruta.replace(/\W/g, '_')}.cjs`);
    await build({ entryPoints: [path.join(src, `${ruta}.ts`)], bundle: true, platform: 'node', format: 'cjs', outfile, logLevel: 'warning' });
    return require(outfile);
};
const B = await armar('componentes/buscador');
const { I } = await armar('web/iconos');

// 1. el campo: la lupa, el input, y al final la cuenta, la tecla y el ✕, en ese orden
{
    const h = B.buscador({ placeholder: 'hilos', grupo: 'hilos', id: 'b', clase: 'x', datos: { bloque: 'correo' }, valor: 'far', atajo: '/',
        ayuda: 'buscar por nombre · ⎋ borra', cuenta: { id: 'n', clase: 'c', texto: '2 de 14' } });
    assert.ok(h.startsWith('<label class="buscador" title="hilos · buscar por nombre · ⎋ borra">'),
        'un label: un clic en la lupa enfoca el campo; al pasar el mouse, en qué se busca y la ayuda');
    assert.ok(h.includes(`<span class="buscador-lupa i">${I.buscar}</span><input class="buscar x" type="text" id="b" data-grupo="hilos" data-bloque="correo" value="far" placeholder=" "`),
        'la lupa delante, y el campo con lo que la vista usa para encontrarlo');
    assert.ok(h.includes('aria-label="hilos" spellcheck="false" autocomplete="off">'), 'en qué se busca, para el lector de pantalla; sin corrector ni autocompletar');
    const en = k => h.indexOf(k);
    assert.ok(en('buscador-lupa') < en('<input') && en('<input') < en('buscador-cuenta') && en('buscador-cuenta') < en('buscador-atajo')
        && en('buscador-atajo') < en('buscador-borrar'), 'lupa · campo · cuenta · tecla · ✕');
    assert.ok(h.includes('<span class="buscador-cuenta c" id="n">2 de 14</span>'), 'la cuenta, ya puesta');
    assert.ok(h.includes('<span class="buscador-atajo" title="/: buscar aquí">/</span>'), 'la tecla que lo enfoca, al final');
    assert.ok(h.endsWith(`<span class="buscador-borrar i" data-buscador-borrar title="borrar lo escrito · ⎋">${I.cerrar}</span></label>`), 'el ✕, al último');
}
// lo mínimo: sin cuenta ni tecla no van sus lugares; el ✕ y la lupa, siempre (el CSS los muestra según lo escrito)
{
    const h = B.buscador({ placeholder: 'tareas' });
    assert.ok(!h.includes('buscador-cuenta') && !h.includes('buscador-atajo'), 'sin cuenta ni tecla');
    assert.ok(h.includes('buscador-lupa') && h.includes('data-buscador-borrar'), 'la lupa y el ✕, siempre');
    assert.ok(h.startsWith('<label class="buscador" title="tareas">'), 'sin ayuda, el globo dice en qué se busca');
    assert.ok(B.buscador({ placeholder: 'x', cuenta: {} }).includes('<span class="buscador-cuenta"></span>'), 'la cuenta vacía: la llena la vista');
    assert.ok(B.buscador({ placeholder: 'x', enfocado: true }).startsWith('<label class="buscador enfocado" title="x">'), 'el foco quieto, del catálogo');
    // sin placeholder visible: siempre un espacio (sin placeholder no hay `:placeholder-shown`, y el CSS no sabría si hay algo
    // escrito); en qué se busca no se dibuja en el campo
    for (const ph of ['', 'hilos', 'lo que te espera']) {
        const c = B.buscador({ placeholder: ph, ayuda: 'a' });
        assert.deepEqual([...c.matchAll(/placeholder="([^"]*)"/g)].map(m => m[1]), [' '], `«${ph}»: el placeholder, un espacio`);
    }
    assert.ok(B.buscador({ placeholder: '' }).startsWith('<label class="buscador">'), 'sin nada que decir, sin globo');
}
// lo escrito se escapa
{
    const h = B.buscador({ placeholder: '<b>"x"</b>', valor: '"><i>', ayuda: 'a "b"', datos: { k: '<' }, cuenta: { texto: '<c>' } });
    assert.ok(!h.includes('<b>') && !h.includes('<i>') && !h.includes('<c>'), 'nada de lo escrito entra como HTML');
    assert.ok(h.includes('aria-label="&lt;b&gt;&quot;x&quot;&lt;/b&gt;"') && h.includes('value="&quot;&gt;&lt;i&gt;"') && h.includes('data-k="&lt;"'));
}

// 2. la barra: la fila propia, con sus herramientas a la derecha
{
    const sola = B.barraBuscar({ placeholder: 'hilos' });
    assert.ok(sola.startsWith('<div class="buscador-barra"><label class="buscador" title="hilos">') && sola.endsWith('</label></div>'), 'sin herramientas, solo el campo');
    const con = B.barraBuscar({ placeholder: 'hilos', claseBarra: 'herram propia', estilo: '--lugar: 3ch', herramientas: '<i class="h"></i>' });
    assert.ok(con.startsWith('<div class="buscador-barra herram propia" style="--lugar: 3ch">'), 'sus clases y su estilo');
    assert.ok(con.endsWith('</label><span class="buscador-herramientas"><i class="h"></i></span></div>'), 'las herramientas, tras el campo');
}

// 3. las cuatro maneras de dibujar el campo que se probaron: una sola elegida, cada una con su nota
{
    assert.equal(B.BORDES.length, 4);
    assert.deepEqual(B.BORDES.filter(b => b.elegida).map(b => b.clave), ['foco'], 'la elegida: la línea de la barra, en el acento con el foco');
    assert.ok(B.BORDES.every(b => b.nombre && b.nota), 'cada una dice qué es');
    // la elegida es la de buscador.css: la línea de la barra toma el acento con el foco; las otras, solo en el catálogo
    const css = readFileSync(path.join(aqui, '..', 'media', 'css', 'buscador.css'), 'utf8');
    assert.match(css, /&:has\(\.buscador:is\(:focus-within, \.enfocado\)\) \{ border-bottom-color: var\(--buscador-linea-foco\); \}/);
    assert.doesNotMatch(css, /\.borde-/, 'las otras no van en la página');
    const cat = readFileSync(path.join(aqui, '..', 'media', 'css', 'catalogo.css'), 'utf8');
    for (const b of B.BORDES.filter(x => !x.elegida)) assert.ok(cat.includes(`.borde-${b.clave} `), `«${b.nombre}», en el catálogo`);
    // entre la lupa y el primer carácter, un carácter (--buscador-lupa-hueco, 1ch), y ningún placeholder que dibujar
    assert.match(css, /\.buscador > input\.buscar \{[^}]*padding: 0 0 0 var\(--buscador-lupa-hueco\);/, 'el hueco, del token');
    assert.doesNotMatch(css, /::placeholder/, 'sin texto de ayuda que pintar');
    // sus colores, de sus tokens (no fijos): el tema los pone
    assert.doesNotMatch(css, /#[0-9a-f]{3,8}\b|rgb\(/i, 'sin colores fijos');
    const tokens = readFileSync(path.join(aqui, '..', 'media', 'css', 'tokens.css'), 'utf8');
    for (const t of new Set(css.match(/--buscador-[a-z-]+/g))) assert.ok(tokens.includes(`${t}:`), `${t}, en tokens.css`);
    assert.match(tokens, /--buscador-lupa-hueco: 1ch;/, 'el hueco: un carácter, el espacio de la grilla');
}

// 4. el ✕ (web/buscadores.ts): vacía su campo, le devuelve el foco y avisa con un `input` que sube; fuera de un ✕, nada
{
    const { borrar } = await armar('web/buscadores');
    const eventos = [];
    const campo = { value: 'far', enfocado: false, focus() { this.enfocado = true; }, dispatchEvent(e) { eventos.push(e); return true; } };
    const caja = { querySelector: s => (s === 'input.buscar' ? campo : null) };
    const x = { closest: s => (s === '[data-buscador-borrar]' ? x : s === '.buscador' ? caja : null) };
    globalThis.Event = class { constructor(tipo, o = {}) { this.type = tipo; this.bubbles = !!o.bubbles; } };
    assert.equal(borrar(x), true);
    assert.equal(campo.value, '', 'vacío');
    assert.ok(campo.enfocado, 'con el foco');
    assert.deepEqual(eventos.map(e => [e.type, e.bubbles]), [['input', true]], 'un input que sube: la vista filtra con lo que ya escucha');
    const otro = { closest: () => null };
    assert.equal(borrar(otro), false, 'un clic en otra cosa no es suyo');
    assert.equal(borrar(null), false);
}

// 5. cada buscador de la página lo usa
const ts = [];
const recorrer = d => { for (const f of readdirSync(d)) { const p = path.join(d, f); if (statSync(p).isDirectory()) recorrer(p); else if (f.endsWith('.ts')) ts.push(p); } };
recorrer(src);
const leer = p => readFileSync(p, 'utf8');
{
    // los del inventario del catálogo («dónde está»): cada archivo importa el componente (o su barra en el DOM)
    const { DONDE } = await armar('componentes/catalogo-buscador');
    const archivos = DONDE.flatMap(d => d.archivo.split(' → ')).filter(a => a.endsWith('.ts'));
    assert.ok(archivos.length >= 14, 'el inventario nombra los buscadores de la página');
    for (const a of archivos) {
        const t = leer(path.join(src, a));
        assert.match(t, /\b(barraBuscar|barraDeBuscar|herramientas as herramientasLista)\b/, `${a}: usa el buscador (componentes/buscador.ts)`);
    }
    // y ningún archivo arma uno a mano: ni un <input> de tipo search, ni un campo cuyo texto de ayuda diga buscar o filtrar,
    // ni un `el('input')` / `createElement('input')` que no sea una casilla
    for (const p of ts) {
        const rel = path.relative(src, p), t = leer(p);
        if (rel === 'componentes/buscador.ts') continue;
        assert.doesNotMatch(t, /type="search"/, `${rel}: un input de búsqueda a mano`);
        for (const m of t.matchAll(/placeholder(?:="|: ?['`]|\s*=\s*['`])([^"'`]*)/g)) {
            assert.doesNotMatch(m[1], /^\/?\s*(buscar|filtrar)\b|escribe para buscar/i, `${rel}: el texto de ayuda dice en qué se busca, no el verbo («${m[1]}»)`);
        }
        for (const linea of t.split('\n').filter(l => /el\('input'\)|createElement\('input'\)/.test(l))) {
            assert.match(linea, /checkbox/, `${rel}: un campo armado a mano («${linea.trim()}»)`);
        }
    }
}
// los que se dibujan sin la página salen en su barra: la sección de lista (HILOS), la paleta, Todo y lo que te espera
{
    const { herramientas } = await armar('componentes/seccion');
    assert.match(herramientas({ grupo: 'hilos', placeholder: 'hilos', ayuda: 'a' }), /^<div class="buscador-barra herram">/);
    const { paleta } = await armar('componentes/ventana');
    assert.match(paleta({ filas: [] }), /<div class="ventana-campo"><div class="buscador-barra">.*aria-label="opciones"/, 'la paleta, sin decir en qué: «opciones»');
    const { cuerpo } = await armar('vistas/dashboard/esperas');
    assert.match(cuerpo([], new Set()).join(''), /<div class="buscador-barra herram">.*id="buscar-e"/);
    const { todo } = await armar('componentes/todo');
    const t = todo({ fuentes: [], puesto: 'trabajo', mundos: [], buscado: 'far', halladas: [], total: 3 });
    assert.match(t, /<div class="buscador-barra todo-buscar">.*id="todo-q".*value="far".*<span class="buscador-cuenta" id="todo-cuenta">0 de 3<\/span>/, 'Todo: su barra, con lo buscado y su cuenta ya puesta');
}

// 6. ⌘K y lo que pregunta afuera (web/buscador.ts, `Remotas`): se pide con dos letras o más, al dejar de escribir; lo que
// llega de algo escrito antes se descarta; lo de antes se sigue viendo hasta que llega lo nuevo; con la ventana cerrada,
// nada. Y las fuentes de telar (web/hallados.ts): los proyectos, las tareas y los documentos, en un solo pedido por lo
// escrito (cli.buscar, solo esas tres, con el mundo puesto primero), cada una en su grupo y en el orden en que viene, y
// abrir una es lo de Todo: un documento en el visor, una tarea o un proyecto por su dirección
{
    const K = await armar('web/buscador');
    const dormir = ms => new Promise(ok => setTimeout(ok, ms));
    // una remota de mentira: cada pedido queda esperando hasta que la prueba lo contesta
    const pedidos = [];
    const remota = { clave: 'docs', nombre: 'documentos', orden: 6, remota: true,
        resultados: q => new Promise((ok, mal) => pedidos.push({ q, ok: rs => ok(rs.map(t => ({ titulo: t, abrir() {} }))), mal })) };
    let localPreguntada = 0;
    const local = { clave: 'hilos', nombre: 'hilos', orden: 1, resultados: () => { localPreguntada++; return []; } };
    let avisos = 0;
    const r = new K.Remotas(() => [local, remota], () => { avisos++; }, 10);
    const titulos = () => r.de('docs').map(x => x.titulo);
    const ultimo = q => pedidos.findLast(p => p.q === q);

    r.escribir('t'); await dormir(30);
    assert.equal(pedidos.length, 0, 'con una letra no se pregunta');
    r.escribir('te'); r.escribir('tel'); await dormir(30);
    assert.deepEqual(pedidos.map(p => p.q), ['tel'], 'al dejar de escribir, una vez, con lo último');
    assert.ok(r.esperando.has('docs'), 'esperando su respuesta');
    assert.equal(localPreguntada, 0, 'a las de la página no les pregunta: las filtra la ventana');
    ultimo('tel').ok(['telar', 'tela']); await dormir(0);
    assert.deepEqual(titulos(), ['telar', 'tela'], 'en el orden en que vino, sin puntaje');
    assert.ok(!r.esperando.size);

    r.escribir('tela'); await dormir(30);
    assert.deepEqual(titulos(), ['telar', 'tela'], 'mientras llega lo nuevo, lo de antes sigue: no parpadea');
    assert.ok(r.esperando.has('docs'), 'y su grupo dice que sigue preguntando');
    r.escribir('telar'); await dormir(30);
    const antes = avisos;
    ultimo('telar').ok(['telar']); await dormir(0);
    assert.deepEqual(titulos(), ['telar'], 'lo último escrito');
    ultimo('tela').ok(['tela vieja']); await dormir(0);
    assert.deepEqual(titulos(), ['telar'], 'la respuesta tardía de algo escrito antes se descarta');
    assert.equal(avisos, antes + 1, 'y no repinta');
    assert.equal(r.dadas.get('docs').q, 'telar');

    r.escribir('telar '); await dormir(30);
    assert.equal(pedidos.filter(p => p.q === 'telar').length, 1, 'lo mismo escrito (con espacios) no se vuelve a pedir');
    r.escribir('zz'); await dormir(30);
    ultimo('zz').mal(new Error('la API no respondió')); await dormir(0);
    assert.deepEqual(titulos(), [], 'una que falla no muestra nada');
    r.escribir('x');
    assert.ok(!r.dadas.size && !r.esperando.size, 'con menos de dos letras se vacía al tiro');

    r.escribir('vitrina'); await dormir(30);
    r.cerrar();
    ultimo('vitrina').ok(['vitrina']); await dormir(0);
    assert.deepEqual(titulos(), [], 'con la ventana cerrada, lo que llega no entra');
    r.escribir('otra'); await dormir(30);
    assert.ok(!pedidos.some(p => p.q === 'otra'), 'ni se pide nada más');

    // las fuentes de telar (proyectos, tareas, documentos), con un buscar de mentira: lo que piden y lo que dan
    // hallados y la navegación de ui, en un mismo paquete: lo que abre un clic se mira en la navegación que usa
    const salidaH = path.join(carpeta, 'hallados-ui.cjs');
    await build({ stdin: { contents: "export * from './web/hallados'; export { usarNavegacion } from './web/ui'; export { Remotas } from './web/buscador'; export * as mundo from './web/mundo'; export { modelo } from './modelo';",
        resolveDir: src, loader: 'ts' }, bundle: true, platform: 'node', format: 'cjs', outfile: salidaH, logLevel: 'warning' });
    const H = require(salidaH);
    const doc = (titulo, mundo, ruta) => ({ fuente: 'objeto:doc', direccion: `doc:${ruta}`, id: ruta, titulo, donde: ruta, cuando: '', estado: '3 conexiones',
        pasada: false, mundo, datos: { ruta_abs: `/casa/${ruta}` } });
    const tarea = (id, titulo, mundo, o = {}) => ({ fuente: 'tareas', direccion: `tarea:${id}`, id, titulo, donde: 'trabajo/vitrina', cuando: '2026-03-21',
        estado: 'abierta', pasada: false, mundo, ...o });
    const proyecto = (ruta, titulo, mundo) => ({ fuente: 'proyectos', direccion: `proyecto:${ruta}`, id: '', titulo, donde: ruta, cuando: '2026-11-20T10:00',
        estado: 'activo', pasada: false, mundo });
    const fuente = (clave, hallados, o = {}) => ({ clave, nombre: clave, total: hallados.length, falla: '', hallados, ...o });
    const llamadas = [];
    let respuestas = [];
    const buscar = async (...args) => { llamadas.push(args); return respuestas.shift(); };
    let preparadas = 0;
    const fs = H.fuentesDeTelar({ buscar, primero: () => 'trabajo', nombreMundo: c => c[0].toUpperCase() + c.slice(1), preparar: () => { preparadas++; }, pausa: 1 });
    const [fp, ft, fd] = fs;
    assert.deepEqual(fs.map(f => [f.clave, f.nombre, f.orden, f.remota]), [['proyectos', 'proyectos', 6, true], ['tareas', 'tareas', 7, true],
        ['documentos', 'documentos', 8, true]], 'tres grupos remotos: los proyectos, las tareas y los documentos, después de lo de la página');
    assert.deepEqual(fs.map(f => f.color), ['verde', 'cian', 'amarillo'], 'la tinta de cada una, la de Todo');
    for (const f of fs) f.preparar?.();
    assert.equal(preparadas, 1, 'que telar empiece a leer, una vez para las tres');
    respuestas = [{ datos: { q: 'vitrina', mundos: ['trabajo', 'personal'], primero: 'trabajo', fuentes: [
        fuente('proyectos', [proyecto('trabajo/vitrina', 'Vitrina', 'trabajo'), proyecto('personal/vitrina', 'Vitrina de casa', 'personal')]),
        fuente('tareas', [tarea('T84', 'Revisar la vitrina', 'trabajo'), tarea('T12', 'Vitrina vieja', 'trabajo', { pasada: true, estado: 'hecha' }),
            tarea('T90', 'Vitrina del living', 'personal', { donde: '' })]),
        fuente('objeto:doc', [doc('Grafo del trabajo', 'trabajo', 'trabajo/GRAFO.md'), doc('Núcleo', '', 'comun/grafo/nucleo.md'), doc('Grafo personal', 'personal', 'personal/grafo.md')]),
    ] } }];
    const [rp, rt, rd] = await Promise.all(fs.map(f => f.resultados('vitrina')));
    assert.deepEqual(llamadas, [['vitrina', H.POR_PEDIDO, false, 'trabajo', ['proyectos', 'tareas', 'objeto:doc'], true]],
        'un solo pedido para las tres: la búsqueda de Todo, solo esas fuentes, con el mundo puesto primero, y sin error por la que falte');
    assert.deepEqual(rp.map(x => [x.titulo, x.detalle]), [['Vitrina', 'trabajo/vitrina'], ['Vitrina de casa', 'personal/vitrina · Personal']],
        'un proyecto: su ruta; el de otro mundo, al final (el orden lo da telar) y lo dice');
    assert.deepEqual(rt.map(x => [x.titulo, x.detalle]), [['Revisar la vitrina', 'T84 · trabajo/vitrina · 21-mar'], ['Vitrina vieja', 'T12 · trabajo/vitrina · hecha'],
        ['Vitrina del living', 'T90 · 21-mar · Personal']], 'una tarea: su número, su proyecto y cuándo (o su estado, si ya pasó), como en Todo');
    assert.deepEqual(rd.map(x => x.titulo), ['Grafo del trabajo', 'Núcleo', 'Grafo personal'], 'el orden lo da telar');
    assert.deepEqual(rd.map(x => x.detalle), ['trabajo/GRAFO.md', 'comun/grafo/nucleo.md', 'personal/grafo.md · Personal'],
        'la ruta como detalle; el de otro mundo lo dice (lo sin clasificar, no)');
    // con un mundo que filtra (el puesto, que no es ambos ni el modo todo), lo de otro mundo no sale en ⌘K: se busca en Todo
    {
        const llamadasAntes = llamadas.length;
        const [fp2, ft2, fd2] = H.fuentesDeTelar({ buscar, primero: () => 'trabajo', nombreMundo: c => c, ve: m => !m || m === 'trabajo', preparar() {}, pausa: 1 });
        respuestas = [{ datos: { q: 'vitrina2', mundos: ['trabajo', 'personal'], primero: 'trabajo', fuentes: [
            fuente('proyectos', [proyecto('trabajo/vitrina', 'Vitrina', 'trabajo'), proyecto('agentes/jardin', 'Jardín', 'personal')]),
            fuente('tareas', [tarea('T90', 'Vitrina del living', 'personal', { donde: '' })]),
            fuente('objeto:doc', [doc('Núcleo', '', 'comun/grafo/nucleo.md'), doc('Registro', 'personal', 'agentes/jardin/registro/x.md')]),
        ] } }];
        const [p2, t2, d2] = await Promise.all([fp2, ft2, fd2].map(f => f.resultados('vitrina2')));
        assert.deepEqual([p2, t2, d2].map(r => r.map(x => x.titulo)), [['Vitrina'], [], ['Núcleo']],
            'lo de personal no sale con trabajo puesto; lo sin clasificar, sí');
        llamadas.length = llamadasAntes;
    }
    // en el modo todo (el mundo ordena y no esconde) con el trabajo puesto: lo de personal sale, al final; lo de un agente
    // de personal que pide esconderse fuera de su mundo (`agente`, lo de su carpeta: el Jardín, con
    // `fuera_de_su_mundo = "esconder"`), no, ni ahí (el 23-nov, con la pantalla compartida); el de uno que no lo pide, sí
    {
        const W = H.mundo;
        H.modelo.secciones = [{ clave: 'agente:jardin', nombre: 'Jardín', hilos: [], grupo: 'agentes', mundo: 'personal', fuera_de_su_mundo: 'esconder' },
            { clave: 'agente:huerta', nombre: 'Huerta', hilos: [], grupo: 'agentes', mundo: 'personal' }];
        W.recibir({ mundos: [{ nombre: 'trabajo', color: '', horario: [] }, { nombre: 'personal', color: '', horario: [] }], mundos_fuera: 'trabajo' });
        W.poner('trabajo');
        W.ordenarSolo(true);
        try {
            const llamadasAntes = llamadas.length;
            const [fp3, ft3, fd3] = H.fuentesDeTelar({ buscar, primero: () => 'trabajo', nombreMundo: c => c, preparar() {}, pausa: 1 });
            respuestas = [{ datos: { q: 'vitrina3', mundos: ['trabajo', 'personal'], primero: 'trabajo', fuentes: [
                fuente('proyectos', [proyecto('trabajo/vitrina', 'Vitrina', 'trabajo'), { ...proyecto('agentes/jardin', 'Jardín', 'personal'), agente: 'jardin' }]),
                fuente('tareas', [tarea('T90', 'Vitrina del living', 'personal', { donde: '' }), tarea('T91', 'Poda del martes', 'personal', { agente: 'jardin' }),
                    tarea('T92', 'Regar', 'personal', { agente: 'huerta' })]),
                fuente('objeto:doc', [doc('Núcleo', '', 'comun/grafo/nucleo.md'), { ...doc('Registro', 'personal', 'agentes/jardin/registro/x.md'), agente: 'jardin' },
                    { ...doc('Bitácora de Secretaría', 'trabajo', 'agentes/secretaria/bitacora.md'), agente: 'secretaria' }]),
            ] } }];
            const [p3, t3, d3] = await Promise.all([fp3, ft3, fd3].map(f => f.resultados('vitrina3')));
            assert.deepEqual([p3, t3, d3].map(r => r.map(x => x.titulo)), [['Vitrina'], ['Vitrina del living', 'Regar'], ['Núcleo', 'Bitácora de Secretaría']],
                'en todo, lo de personal sale (al final), también lo de un agente de personal que no se esconde; lo del que se esconde, no');
            W.poner('');
            const [p4] = await Promise.all([fp3].map(f => f.resultados('vitrina3')));
            assert.deepEqual(p4.map(x => x.titulo), ['Vitrina', 'Jardín'], 'con ambos, lo del agente se ve');
            llamadas.length = llamadasAntes;
        } finally { W.ordenarSolo(false); W.poner(''); W.recibir({ mundos: [], mundos_fuera: '' }); H.modelo.secciones = []; }
    }
    assert.deepEqual([rp[0], rt[0], rd[0]].map(x => x.icono), ['proyectos', 'tareas', 'objeto:doc'].map(c => H.deFuente(c)[0]), 'el ícono de cada una, el de Todo');
    // abrir: lo de Todo. Un documento, el visor con sus conexiones; una tarea y un proyecto, su dirección
    const abiertos = [];
    H.usarNavegacion({ mostrar: v => abiertos.push(v) });
    await rd[0].abrir(); await rt[0].abrir(); await rp[0].abrir();
    assert.deepEqual(abiertos, ['arch:/casa/trabajo/GRAFO.md', 'obj:tarea:T84', 'obj:proyecto:trabajo/vitrina'], 'un clic: donde vive, como en Todo');
    // por el buscador: escribir pregunta a las tres, y es un pedido
    llamadas.length = 0;
    respuestas = [{ datos: { q: 'casa', mundos: [], fuentes: [fuente('proyectos', [proyecto('personal/casa', 'Casa', '')]), fuente('tareas', []), fuente('objeto:doc', [])] } }];
    const rem = new H.Remotas(() => fs, () => {}, 5);
    rem.escribir('cas'); rem.escribir('casa'); await dormir(30);
    assert.equal(llamadas.length, 1, 'un pedido por lo escrito, no uno por fuente');
    assert.deepEqual([rem.de('proyectos').map(x => x.titulo), rem.de('tareas'), rem.de('documentos')], [['Casa'], [], []]);
    rem.cerrar();
    // telar no alcanzó a leer los documentos: las tareas salen al tiro, y se vuelve a preguntar solo por los documentos
    llamadas.length = 0;
    const tarde = { datos: { q: 'ya', mundos: [], fuentes: [fuente('proyectos', []), fuente('tareas', [tarea('T1', 'Ya', '')]), fuente('objeto:doc', [], { tarde: true })] } };
    respuestas = [tarde, { datos: { q: 'ya', mundos: [], fuentes: [fuente('objeto:doc', [doc('Ya', '', 'ya.md')])] } }];
    const [tp, tt, td] = await Promise.all(fs.map(f => f.resultados('ya')));
    assert.deepEqual([tp, tt.map(x => x.titulo), td.map(x => x.titulo)], [[], ['Ya'], ['Ya']], 'lo que vino tarde se vuelve a pedir');
    assert.deepEqual(llamadas.map(a => a[4]), [['proyectos', 'tareas', 'objeto:doc'], ['objeto:doc']], 'la segunda vez, solo lo que faltó');
    // una máquina sin tareas, o sin módulo que liste documentos: esa no muestra nada, las otras sí
    respuestas = [{ datos: { q: 'yo', mundos: [], fuentes: [fuente('proyectos', [proyecto('a', 'Yo', '')])] } }];
    const sin = await Promise.all(fs.map(f => f.resultados('yo')));
    assert.deepEqual(sin.map(rs => rs.length), [1, 0, 0], 'la que no hay, nada');
    // una falla del pedido es un error para las tres (el buscador no muestra nada de ella); volver a escribirlo, pregunta otra vez
    llamadas.length = 0;
    respuestas = [{ error: 'la API no respondió' }];
    for (const r of await Promise.allSettled(fs.map(f => f.resultados('mal')))) assert.match(String(r.reason), /la API no respondió/);
    respuestas = [{ datos: { q: 'mal', mundos: [], fuentes: [fuente('proyectos', []), fuente('tareas', []), fuente('objeto:doc', [], { falla: 'sin grafo' })] } }];
    await assert.rejects(fd.resultados('mal'), /sin grafo/, 'la falla de una fuente, sin nada, es un error de esa');
    assert.deepEqual(await ft.resultados('mal'), [], 'y no de las otras');
    assert.equal(llamadas.length, 2, 'lo que falló no se recuerda');
    // el pedido: el mismo GET /buscar de Todo, con `fuente`
    const C = await armar('cli');
    const urls = [];
    globalThis.fetch = async url => { urls.push(url); return { ok: true, status: 200, json: async () => ({ q: 'a', mundos: [], fuentes: [] }) }; };
    await C.buscar('a b', 8, false, 'trabajo', ['tareas', 'objeto:doc'], true);
    await C.buscar('a', 30, false, 'trabajo');
    assert.deepEqual(urls, ['/api/buscar?q=a%20b&limite=8&primero=trabajo&fuente=tareas&fuente=objeto%3Adoc&si_hay=true', '/api/buscar?q=a&limite=30&primero=trabajo'],
        'solo esas, y la que no haya se deja fuera; sin `fuentes`, todas, como siempre');
    // Todo abre con lo mismo, sin repetirlo
    const todoTs = leer(path.join(src, 'vistas', 'dashboard', 'todo.ts'));
    assert.match(todoTs, /abrirHallado\(h\)/, 'Todo abre lo hallado con web/hallados.ts');
    assert.doesNotMatch(todoTs, /ruta_abs/, 'y no lo repite');
}

// 7. una pestaña se encuentra por su nombre y por su clave: la del módulo registro se llama «decisiones» (su [pestana]
// nombre) y su clave sigue siendo bloque:registro, así que ⌘K la encuentra escribiendo cualquiera de los dos
{
    const K = await armar('web/buscador');
    const app = readFileSync(path.join(src, 'navegador', 'app.ts'), 'utf8');
    assert.match(app, /hoy\.pestanas\(\)\.map\(\(p, i\) => \(\{\s*titulo: p\.nombre,[^\n]*claves: p\.clave\b/,
        'las pestañas de ⌘K: el nombre a la vista y la clave entre lo que se busca');
    const decisiones = { titulo: 'decisiones', detalle: 'pestaña', claves: 'bloque:registro', abrir() {} };
    assert.ok(K.puntaje('decisiones', decisiones) >= 100, 'por su nombre');
    assert.ok(K.puntaje('registro', decisiones) > 0, 'y por su clave, el nombre de antes');
    assert.ok(K.puntaje('regis', decisiones) > 0, 'también a medio escribir');
}

console.log('prueba:buscador ok');
