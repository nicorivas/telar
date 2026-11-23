// Prueba de la franja de avisos: el componente (src/componentes/franja.ts: el orden, lo que dice tranquila, el más grave con
// «+N», la barra plegada, la lista y el punto), el almacén de los avisos (src/web/avisos.ts: uno por clave, desde cuándo,
// lo que se va solo, lo que se calla sin conexión), las escenas del catálogo (componentes/muestras-avisos.ts) y que una
// fuente de lo que espera que falla se dice en un solo lugar (dashboard/esperas.ts la pone; Táctica no la repite). Corre
// en Node, sin página: npm run prueba:avisos
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const carpeta = mkdtempSync(path.join(tmpdir(), 'avisos-'));
const armar = async (ruta) => {
    const outfile = path.join(carpeta, `${path.basename(ruta)}.cjs`);
    await build({ entryPoints: [path.join(aqui, '..', 'src', `${ruta}.ts`)], bundle: true, platform: 'node', format: 'cjs', outfile, logLevel: 'warning' });
    return require(outfile);
};
const F = await armar('componentes/franja');
const A = await armar('web/avisos');
const M = await armar('componentes/muestras-avisos');
const C = await armar('componentes/catalogo-avisos');

const aviso = (clave, nivel, o = {}) => ({ clave, nivel, icono: 'X', texto: `${clave}`, ...o });

// 1. el orden: de lo más grave a lo menos (sin conexión, falla, aviso, nota); a igual nivel, como llegaron
{
    const l = [aviso('n', 'nota'), aviso('a1', 'aviso'), aviso('f1', 'falla'), aviso('c', 'conexion'), aviso('f2', 'falla'), aviso('a2', 'aviso')];
    assert.deepEqual(F.ordenar(l).map(x => x.clave), ['c', 'f1', 'f2', 'a1', 'a2', 'n']);
    assert.deepEqual(F.masGrave(l), { aviso: l[3], mas: 5 });
    assert.deepEqual(F.masGrave([]), { aviso: undefined, mas: 0 });
}

// 2. la franja: tranquila, solo su texto tenue y sin clic; con avisos, el más grave en su nivel, con su ícono y «+N»
{
    const calma = F.franja({ avisos: [], calma: 'al día · 18:42', calmaAyuda: 'sin avisos' });
    assert.equal(calma, '<div class="franja calma" title="sin avisos"><span class="franja-texto">al día · 18:42</span></div>');
    assert.doesNotMatch(calma, /data-accion/, 'tranquila no se aprieta');

    const uno = F.franja({ avisos: [aviso('conexion', 'conexion', { texto: 'sin conexión con telar', cuando: 'desde las 11:32' })] });
    assert.match(uno, /^<div class="franja nivel-conexion" data-accion="franja-abrir" role="button" aria-expanded="false"/);
    assert.match(uno, /<span class="franja-icono"><span class="i">X<\/span><\/span><span class="franja-texto">sin conexión con telar<\/span><\/div>$/);
    assert.doesNotMatch(uno, /franja-mas/, 'uno solo, sin «+N»');

    const varios = F.franja({ avisos: [aviso('v', 'aviso'), aviso('f', 'falla', { texto: 'una <falla>' }), aviso('n', 'nota')] });
    assert.match(varios, /class="franja nivel-falla"/, 'la más grave manda');
    assert.match(varios, /<span class="franja-texto">una &lt;falla&gt;<\/span><span class="franja-mas">\+2<\/span>/, 'escapado, y los demás contados');
    assert.match(varios, /title="una &lt;falla&gt;\ny 2 avisos más\nclic: qué pasa y qué hacer"/);

    // plegada: solo el ícono; tranquila y plegada, vacía (el lugar queda)
    const plegada = F.franja({ avisos: [aviso('f', 'falla'), aviso('n', 'nota')], plegada: true });
    assert.match(plegada, /class="franja nivel-falla plegada"/);
    assert.doesNotMatch(plegada, /franja-texto|franja-mas/);
    assert.equal(F.franja({ avisos: [], calma: 'al día', plegada: true }), '<div class="franja calma plegada"></div>');

    // en curso (instalando): el círculo de su movimiento en vez del ícono
    assert.match(F.franja({ avisos: [aviso('version', 'aviso', { curso: 'llena' })] }), /<span class="franja-icono"><span class="circulo tam-grande mov-llena"><\/span><\/span>/);
}

// 3. la lista: abierta, debajo; cada aviso con su nivel, lo que pasa (un clic va a su lugar si tiene uno), desde cuándo,
//    qué pasó, qué hacer, sus acciones y adónde lleva
{
    const l = [aviso('pagina-nueva', 'aviso', { texto: 'página nueva', detalle: 'Se desplegó otra.', hacer: 'Recargarla.', acciones: [{ id: 'recargar', texto: 'recargar' }] }),
        aviso('fuente:calendario', 'falla', { texto: 'no se pudo leer el calendario', cuando: 'desde las 11:40', ir: '⚙ calendario' })];
    const abierta = F.franja({ avisos: l, abierta: true });
    assert.match(abierta, /class="franja nivel-falla abierta"[^>]*aria-expanded="true"/);
    const lista = abierta.slice(abierta.indexOf('<div class="franja-lista"'));
    assert.ok(lista.indexOf('fuente:calendario') < lista.indexOf('pagina-nueva'), 'de lo más grave a lo menos');
    assert.match(lista, /<a class="franja-aviso-tit" data-accion="franja-ir" data-clave="fuente:calendario" title="falla · clic: ⚙ calendario">/);
    assert.match(lista, /<span class="franja-cuando">desde las 11:40<\/span>/);
    assert.match(lista, /<a class="franja-boton ir" data-accion="franja-ir" data-clave="fuente:calendario"[^>]*>⚙ calendario ›<\/a>/);
    assert.match(lista, /<div class="franja-aviso-tit" title="aviso">/, 'sin lugar adonde ir, el título no se aprieta');
    assert.match(lista, /<div class="franja-aviso-det">Se desplegó otra.<\/div><div class="franja-aviso-hacer"><span class="franja-que">qué hacer<\/span> Recargarla.<\/div>/);
    assert.match(lista, /<a class="franja-boton" data-accion="franja-accion" data-clave="pagina-nueva" data-valor="recargar">recargar<\/a>/);
    assert.doesNotMatch(F.franja({ avisos: l }), /franja-lista/, 'cerrada, sin lista');
}

// 4. el punto, donde la franja no se ve: el color del más grave; nada sin avisos ni con solo una nota
{
    assert.equal(F.punto([]), '');
    assert.equal(F.punto([aviso('m', 'nota')]), '');
    assert.match(F.punto([aviso('m', 'nota'), aviso('c', 'conexion')]), /<span class="senal tono-peligro" title="c \(y 1 más\)"><span class="circulo tam-punto"/);
    assert.match(F.punto([aviso('f', 'falla')]), /tono-atencion/);
    assert.match(F.punto([aviso('v', 'aviso')]), /tono-acento/);
}

// 5. el almacén: uno por clave, conserva desde cuándo, avisa solo si algo cambió, y lo que se va se va
{
    let veces = 0;
    const dejar = A.alCambiar(() => { veces++; });
    A.poner({ clave: 'x', nivel: 'falla', icono: 'X', texto: 'uno', desde: 1000 });
    A.poner({ clave: 'x', nivel: 'falla', icono: 'X', texto: 'uno, otra vez' });
    assert.equal(A.de('x').desde, 1000, 'ponerlo de nuevo no cambia desde cuándo pasa');
    assert.equal(A.de('x').texto, 'uno, otra vez');
    const antes = veces;
    A.poner({ clave: 'x', nivel: 'falla', icono: 'X', texto: 'uno, otra vez' });
    assert.equal(veces, antes, 'lo mismo no avisa');
    A.quitar('x');
    assert.equal(A.hay('x'), false);
    A.quitar('x');
    assert.equal(veces, antes + 1, 'quitar lo que no está no avisa');
    dejar();
}

// 6. un grupo: los que siguen quedan (con su desde), los demás se van
{
    A.soloEstos('fuente:', [{ clave: 'fuente:a', nivel: 'falla', icono: 'X', texto: 'a', desde: 5 }, { clave: 'fuente:b', nivel: 'falla', icono: 'X', texto: 'b' }]);
    A.poner({ clave: 'otro', nivel: 'aviso', icono: 'X', texto: 'otro' });
    A.soloEstos('fuente:', [{ clave: 'fuente:a', nivel: 'falla', icono: 'X', texto: 'a de nuevo' }]);
    assert.deepEqual(A.vigentes().map(a => a.clave).sort(), ['fuente:a', 'otro']);
    assert.equal(A.de('fuente:a').desde, 5);
    A.soloEstos('fuente:', []);
    A.quitar('otro');
    assert.deepEqual(A.vigentes(), []);
}

// 7. sin conexión, lo que solo vale con ella se calla (la falla es la misma); lo oculto por el modo, también
{
    A.poner({ clave: 'terminal:faro', nivel: 'falla', icono: 'X', texto: 'se cortó', conConexion: true });
    A.poner({ clave: 'version', nivel: 'aviso', icono: 'X', texto: 'telar 0.13.1' });
    assert.deepEqual(A.vigentes().map(a => a.clave), ['terminal:faro', 'version']);
    A.poner({ clave: 'conexion', nivel: 'conexion', icono: 'X', texto: 'sin conexión con telar' });
    assert.deepEqual(A.vigentes().map(a => a.clave), ['version', 'conexion']);
    assert.deepEqual(A.vigentes(k => k === 'version').map(a => a.clave), ['conexion']);
    A.quitar('conexion');
    assert.deepEqual(A.vigentes().map(a => a.clave), ['terminal:faro', 'version'], 'reconectó: vuelve lo que se callaba');
    A.quitar('terminal:faro'); A.quitar('version');
}

// 8. lo que se dibuja: desde cuándo, dicho (hoy con la hora, otro día cuánto hace; o «hace…»), y los botones sin lo que hacen
{
    const ahora = new Date(2026, 10, 17, 11, 45).getTime();
    const hecho = [];
    const a = { clave: 'k', nivel: 'falla', icono: 'X', texto: 't', desde: new Date(2026, 10, 17, 11, 32).getTime(),
        ir: { texto: 'el hilo faro', hacer: () => hecho.push('ir') }, acciones: [{ id: 'r', texto: 'reintentar', hacer: () => hecho.push('r') }] };
    const d = A.paraDibujar(a, ahora);
    assert.equal(d.cuando, 'desde las 11:32');
    assert.equal(d.ir, 'el hilo faro');
    assert.deepEqual(d.acciones, [{ id: 'r', texto: 'reintentar' }]);
    assert.equal(A.paraDibujar({ ...a, cuando: 'hace' }, ahora).cuando, 'hace 13 min');
    assert.equal(A.paraDibujar({ ...a, cuando: 'nada' }, ahora).cuando, undefined);
    assert.equal(A.paraDibujar({ ...a, desde: ahora - 2 * 86400000 }, ahora).cuando, 'hace 2 d', 'de otro día, cuánto hace');
    A.poner(a);
    assert.equal(A.hacer('k', 'r'), true);
    assert.equal(A.hacer('k'), true);
    assert.equal(A.hacer('k', 'nada'), false);
    assert.equal(A.hacer('no-esta'), false);
    assert.deepEqual(hecho, ['r', 'ir']);
    A.quitar('k');
}

// 9. las escenas del catálogo: cada aviso con lo que necesita, una clave por aviso, y «sin conexión» solo en rojo
{
    const claves = Object.values(M.AVISOS).map(a => a.clave);
    assert.equal(new Set(claves).size, claves.length, 'una clave por aviso');
    for (const a of Object.values(M.AVISOS)) {
        assert.ok(a.icono && a.texto && a.detalle, `${a.clave}: ícono, texto y detalle`);
        assert.ok(F.NIVELES.some(n => n.nivel === a.nivel), `${a.clave}: su nivel existe`);
    }
    assert.deepEqual(Object.values(M.AVISOS).filter(a => a.nivel === 'conexion').map(a => a.clave), ['conexion'], 'el nivel de la conexión, solo ella');
    assert.deepEqual(M.ESCENAS.map(e => e.clave), ['ninguno', 'sin-conexion', 'fuente', 'varios']);
    assert.equal(M.escena('no-existe').clave, 'ninguno');
    // el catálogo las arma todas, y la página entera de cada una
    assert.ok(C.filasEstados().length >= M.ESCENAS.length + 3);
    for (const e of M.ESCENAS) for (const extra of ['', 'abierta', 'plegada', 'hilo']) assert.ok(C.enLaPagina(e.clave, extra), `${e.clave}/${extra}`);
    assert.equal(C.enLaPagina('no-existe'), null);
    assert.match(C.enLaPagina('varios', 'abierta').franja, /franja-lista/);
    assert.equal(C.enLaPagina('ninguno').punto, '');
}

// 10. una fuente de lo que espera que falla, en un solo lugar: «te esperan» (dashboard/esperas.ts, que la lee siempre, para el
//     número de la barra) la pone en la franja, y Táctica, que lee lo mismo, ya no la repite arriba de lo suyo
{
    const outfile = path.join(carpeta, 'pantallas.cjs');
    await build({ stdin: { contents: "export { PantallaEsperas } from './src/vistas/dashboard/esperas'; export { PantallaTactica } from './src/vistas/dashboard/tactica'; "
        + "export * as avisos from './src/web/avisos'; export { ESTADOS } from './src/componentes/muestras-tactica';", resolveDir: path.join(aqui, '..'), loader: 'ts' },
        bundle: true, platform: 'node', format: 'cjs', outfile, logLevel: 'warning' });
    const P = require(outfile);
    const claves = () => P.avisos.vigentes().map(a => a.clave).sort();
    const esperas = new P.PantallaEsperas({ pantalla: '' });
    esperas.avisar({ datos: { esperas: [], fallas: { correo: 'no contestó' } } });
    assert.deepEqual(claves(), ['fuente:esperas:correo']);
    assert.match(P.avisos.de('fuente:esperas:correo').detalle, /correo: no contestó/);
    esperas.avisar({ error: 'la API no respondió' });
    assert.deepEqual(claves(), ['fuente:esperas:correo'], 'sin respuesta de telar, lo que se sabía sigue (lo dice el aviso de la conexión)');
    esperas.avisar({ error: 'se cayó', estado: 500 });
    assert.deepEqual(claves(), ['fuente:esperas'], 'telar contestó con un error: la bandeja entera');
    esperas.avisar({ datos: { esperas: [] } });
    assert.deepEqual(claves(), [], 'se leyó entera: se va');

    // Táctica, con una fuente que falla: lo suyo, sin la línea de la falla
    const datos = P.ESTADOS[0].datos;
    globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => ({ esperas: datos.esperas, fallas: { correo: 'no contestó' } }) });
    let pintado = '';
    const tablero = { panel: {}, pantalla: 'otra', teclas: new Map(), dia: () => datos.dia, planes: { planDe: () => datos.plan },
        pintar: h => { pintado = h.join(''); } };
    const tactica = new P.PantallaTactica(tablero, () => []);
    await tactica.leer();
    tactica.pintar();
    assert.match(pintado, /tac-/, 'Táctica se pintó');
    assert.doesNotMatch(pintado, /no se pudo leer|fila falla/, 'la falla no se repite en Táctica');

    // un mensaje retenido, al leer «te esperan», también en la franja; soltado (ya no viene), se va
    const reciente = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => ({ esperas: [{ direccion: 'mensaje:m-1', tipo: 'mensaje',
        clase: 'retenido', desde: reciente, titulo: '«Ritmo» → «Telar»', resumen: 'listo', enlaces: [] }] }) });
    await esperas.leer();
    assert.deepEqual(claves(), ['retenidos']);
    assert.equal(P.avisos.de('retenidos').texto, 'retenido: «Ritmo» → «Telar»');
    globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => ({ esperas: [] }) });
    await esperas.leer();
    assert.deepEqual(claves(), [], 'soltado: se va');
}

// 11. lo que quedó detenido sin que nada lo diga (web/detenidos.ts): los mensajes retenidos de las últimas 24 h, en un
//     aviso (uno, con su título; varios, contados y con el último), que lleva a «te esperan»
{
    const D = await armar('web/detenidos');
    const ahora = Date.parse('2026-11-18T15:00:00');
    const ret = (id, desde, o = {}) => ({ direccion: `mensaje:${id}`, tipo: 'mensaje', clase: 'retenido', desde, titulo: '«Ritmo» → «Telar»',
        resumen: 'listo', enlaces: [], campos: { motivo: 'cadena de 7 mensajes entre hilos sin que hablara la persona (tope 6)' }, ...o });
    assert.equal(D.avisoRetenidos([], () => {}, ahora), null);
    assert.equal(D.avisoRetenidos([ret('a', '2026-11-16T10:00:00')], () => {}, ahora), null, 'de hace días: solo en «te esperan»');
    const uno = D.avisoRetenidos([ret('a', '2026-11-18T14:40:00'), { ...ret('p', '2026-11-18T14:50:00'), clase: 'permiso' }], () => {}, ahora);
    assert.deepEqual([uno.clave, uno.nivel, uno.texto, uno.cuando, uno.desde],
        ['retenidos', 'aviso', 'retenido: «Ritmo» → «Telar»', 'hace', Date.parse('2026-11-18T14:40:00')]);
    assert.match(uno.detalle, /retuvo el mensaje de «Ritmo» → «Telar» \(cadena de 7/);
    let fue = false;
    const dos = D.avisoRetenidos([ret('a', '2026-11-18T14:40:00'), ret('b', '2026-11-18T14:55:00', { titulo: '«Telar» → «Ritmo»' })],
        () => { fue = true; }, ahora);
    assert.equal(dos.texto, '2 mensajes retenidos');
    assert.match(dos.detalle, /2 mensajes entre hilos; el último, de «Telar» → «Ritmo»/);
    assert.equal(dos.ir.texto, 'te esperan');
    dos.ir.hacer();
    assert.ok(fue, 'lleva a «te esperan»');
}

// 12. un hilo detenido en la pregunta de confiar en una carpeta (telar.confiar lo marca: espera, clase «confiar»): un aviso
//     por hilo, con qué pide y cómo ir; los demás que esperan (un permiso), los dormidos y los de otra máquina, no
{
    const D = await armar('web/detenidos');
    const hilo = (nombre, o = {}) => ({ id: `@${nombre}`, nombre, vivo: true, activo: false, archivado: false, vinculado: true, ruta: '',
        relativa: '', arquetipo: '', prioridad: null, atencion: 'espera', visto: null, tiempo: 0, sesiones: [],
        atencion_desde: '2026-11-18T14:30:00', espera: { clase: 'confiar', pide: 'Claude Code pregunta si confías en /w/codigo-ritmo (--add-dir) antes de arrancar' }, ...o });
    const fuimos = [];
    const l = D.avisosConfiar([
        hilo('Ritmo'),
        hilo('Permiso', { espera: { clase: 'permiso', pide: 'Claude needs your permission to use Bash' } }),
        hilo('Dormido', { vivo: false }),
        hilo('Allá', { remoto: 'servidor' }),
        hilo('Trabaja', { atencion: 'trabajando' }),
    ], h => fuimos.push(h));
    assert.deepEqual(l.map(a => a.clave), ['confiar:Ritmo']);
    const [a] = l;
    assert.deepEqual([a.nivel, a.texto, a.cuando, a.desde], ['aviso', '«Ritmo» espera que confíes en una carpeta', 'hace', Date.parse('2026-11-18T14:30:00')]);
    assert.match(a.detalle, /confías en \/w\/codigo-ritmo \(--add-dir\) antes de arrancar\. Mientras nadie la conteste/);
    assert.match(a.hacer, /telar no la contesta/);
    assert.equal(a.ir.texto, 'el hilo Ritmo');
    a.ir.hacer();
    assert.deepEqual(fuimos, ['Ritmo']);
    // en el almacén, con soloEstos: el que contestó se va
    A.soloEstos('confiar:', l);
    assert.ok(A.hay('confiar:Ritmo'));
    A.soloEstos('confiar:', D.avisosConfiar([hilo('Ritmo', { atencion: 'trabajando', espera: null })], () => {}));
    assert.ok(!A.hay('confiar:Ritmo'), 'contestó: se va');
}

// 13. lo que dice un archivo de aviso (`[avisos]`, web/avisos-archivos.ts): su línea, en cuidado (aviso) o en rojo (mal,
//     el nivel «problema», que no calla a los demás como la conexión), con cuándo se midió, y un clic abre el informe,
//     con la máquina delante si vive en otra; sin informe, sin adónde ir
{
    const AA = await armar('web/avisos-archivos');
    const abiertos = [];
    const a = (clave, nivel, o = {}) => ({ clave, maquina: '', nivel, linea: `${clave} no está bien`, fecha: '2026-11-18T15:30:00',
        informe: '', sugerencias: null, ...o });
    const l = AA.avisosDeArchivos([
        a('equipo', 'aviso', { informe: '/casa/.local/state/equipo/informe.md', sugerencias: 3 }),
        a('respaldo', 'mal', { maquina: 'servidor', informe: '~/respaldo/informe.md', sugerencias: 1 }),
        a('sin-informe', 'aviso'),
        a('raro', 'ok'),
        a('mudo', 'mal', { linea: '' }),
    ], r => abiertos.push(r));
    assert.deepEqual(l.map(x => [x.clave, x.nivel, x.texto]), [
        ['archivo:equipo', 'falla', 'equipo no está bien'], ['archivo:respaldo', 'problema', 'respaldo no está bien'],
        ['archivo:sin-informe', 'falla', 'sin-informe no está bien']]);
    assert.equal(l[0].desde, Date.parse('2026-11-18T15:30:00'));
    assert.equal(l[0].cuando, 'hace');
    assert.equal(l[0].detalle, 'equipo · medido a las 15:30 · 3 sugerencias en el informe.');
    assert.equal(l[1].detalle, 'respaldo, en servidor · medido a las 15:30 · 1 sugerencia en el informe.');
    l[0].ir.hacer();
    l[1].ir.hacer();
    assert.deepEqual(abiertos, ['/casa/.local/state/equipo/informe.md', 'servidor:~/respaldo/informe.md']);
    assert.equal(l[2].ir, undefined, 'sin informe, no lleva a ninguna parte');
    // «problema» va entre la conexión y la falla, y no calla a los que necesitan a telar
    assert.deepEqual(F.NIVELES.map(n => n.nivel), ['conexion', 'problema', 'falla', 'aviso', 'nota']);
    assert.deepEqual(F.ordenar([aviso('f', 'falla'), aviso('p', 'problema'), aviso('c', 'conexion')]).map(x => x.clave), ['c', 'p', 'f']);
    A.soloEstos('archivo:', l);
    A.poner({ clave: 'terminal:x', nivel: 'falla', icono: 'X', texto: 't', conConexion: true });
    assert.ok(A.vigentes().some(x => x.clave === 'terminal:x'), 'un problema no calla lo demás');
    assert.match(F.franja({ avisos: [l[1]] }), /class="franja nivel-problema"/);
    A.soloEstos('archivo:', AA.avisosDeArchivos([], () => {}));
    A.quitar('terminal:x');
    assert.deepEqual(A.vigentes().filter(x => x.clave.startsWith('archivo:')), [], 'lo que deja de venir se va');
}

// 14. lo visto (`[avisos]`): lo que telar dice `visto` no sale; abrir el informe lo marca (con lo que se vio: su nivel y
//     sus problemas), y el ✓ de la lista también, con su globo; sin informe, solo el ✓
{
    const AA = await armar('web/avisos-archivos');
    const abiertos = [], marcados = [];
    const a = (clave, o = {}) => ({ clave, maquina: '', nivel: 'mal', linea: `${clave} al límite`, fecha: '2026-11-18T15:30:00',
        informe: `/casa/${clave}.md`, sugerencias: null, problemas: ['memoria'], visto: false, ...o });
    const l = AA.avisosDeArchivos([a('laptop'), a('visto', { visto: true }), a('sin-informe', { informe: '' })],
        r => abiertos.push(r), x => marcados.push([x.clave, x.nivel, x.problemas]));
    assert.deepEqual(l.map(x => x.clave), ['archivo:laptop', 'archivo:sin-informe'], 'lo visto no sale');
    l[0].ir.hacer();
    assert.deepEqual(abiertos, ['/casa/laptop.md']);
    assert.deepEqual(marcados, [['laptop', 'mal', ['memoria']]], 'abrir el informe lo da por visto');
    assert.deepEqual(l[1].acciones.map(x => [x.id, x.texto]), [['visto', '✓ visto']]);
    l[1].acciones[0].hacer();
    assert.deepEqual(marcados.at(-1), ['sin-informe', 'mal', ['memoria']], 'el ✓ también');
    // el ✓ lleva su globo hasta la lista
    A.soloEstos('archivo:', l);
    const html = F.lista(A.vigentes().map(x => A.paraDibujar(x)));
    assert.match(html, /data-valor="visto" title="dar por visto: [^"]+">✓ visto</);
    assert.ok(A.hacer('archivo:sin-informe', 'visto'), 'el botón de la franja llega al ✓');
    assert.equal(marcados.length, 3);
    A.soloEstos('archivo:', []);
}

console.log('avisos: 14 grupos de pruebas, bien');
