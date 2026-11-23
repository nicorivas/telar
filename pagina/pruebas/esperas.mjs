// Prueba de «te esperan» (src/vistas/dashboard/esperas.ts): en qué grupo va cada clase, cuánto lleva una espera, lo que
// dice la barra de la pestaña (cuántas preguntan: el número de su fila en DASHBOARD), cómo se dibuja una fila (adónde
// lleva el clic, qué palabra va y cuál no, el globo) y el cuerpo entero (los grupos en su orden, el de los hilos aunque
// esté vacío, lo plegado, las fallas, el buscador y los filtros). El clic abre la ventana de contestar (prueba:contestar).
// Corre en Node: npm run prueba:esperas
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const salida = path.join(mkdtempSync(path.join(tmpdir(), 'esperas-')), 'esperas.cjs');
globalThis.localStorage ??= { getItem: () => null, setItem() {}, removeItem() {} };
await build({ stdin: { contents: "export * from './vistas/dashboard/esperas'; export * as mundo from './web/mundo'; export { modelo } from './modelo';",
    resolveDir: path.join(aqui, '..', 'src'), loader: 'ts' }, bundle: true,
    platform: 'node', format: 'cjs', outfile: salida, logLevel: 'warning' });
const { GRUPOS, PREGUNTAN, cuerpo, diasA, edad, fila, grupoDe, resumen, PantallaEsperas, mundo, modelo } = require(salida);

const AHORA = Date.parse('2026-11-17T12:00:00');
const espera = (direccion, clase, desde, mas = {}) => ({ direccion, tipo: direccion.split(':')[0], clase, desde,
    titulo: `lo de ${direccion}`, resumen: '', enlaces: [], campos: {}, ...mas });
const LISTA = [
    espera('tarea:T93', 'avance:pregunta', '2026-10-05T22:43:00', { enlaces: ['proyecto:proyectos/faro'], resumen: '¿la parto en pasos?' }),
    espera('tarea:T375', 'avance:cerrar', '2026-10-27', { campos: { como: 'descartada' } }),
    espera('mensaje:m1', 'retenido', '2026-11-14T13:55:02', { titulo: '«Molino» → «Faro»', enlaces: ['hilo:Faro', 'hilo:Molino'] }),
    espera('tarea:T558', 'avance:preparado', '2026-11-17T09:01:00'),
    espera('permiso:Telar@servidor', 'permiso', '2026-11-17T11:30:00', { enlaces: ['hilo:Telar@servidor', 'proyecto:proyectos/telar'], maquina: 'servidor' }),
    espera('permiso:Viento', 'pregunta', '2026-11-17T11:50:00', { titulo: '¿Qué paleta?', enlaces: ['hilo:Viento'] }),
    espera('correo:1a2b', 'archivar', '2026-11-16T10:00:00'),
    espera('pregunta:casa/2026-11-14-resena', 'decide', '2026-11-14T09:30:00', { titulo: '¿Dónde sale la reseña?',
        enlaces: ['agente:biblioteca', 'archivo:casa/preguntas/2026-11-14-resena.md'] }),
];

// 1. los grupos: lo que bloquea un turno vivo primero; lo de un módulo, en «otras»
{
    assert.deepEqual(GRUPOS.map(g => g.clave), ['hilos', 'decisiones', 'preguntas', 'cerrar', 'preparado', 'retenidos', 'otras']);
    assert.equal(grupoDe('permiso'), 'hilos');
    assert.equal(grupoDe('pregunta'), 'hilos');
    assert.equal(grupoDe('avance:pregunta'), 'preguntas');
    assert.equal(grupoDe('avance:choca'), 'cerrar');
    assert.equal(grupoDe('retenido'), 'retenidos');
    assert.equal(grupoDe('archivar'), 'otras');
    // la pregunta de un módulo (el módulo preguntas) tiene su grupo, después de los hilos
    assert.equal(grupoDe('decide'), 'decisiones');
    // el número de la barra cuenta lo que pregunta: los hilos que esperan, las decisiones y las preguntas de las tareas
    assert.deepEqual(PREGUNTAN, ['permiso', 'pregunta', 'decide', 'avance:pregunta']);
}

// 2. cuánto lleva: minutos, horas, días y, desde dos semanas, semanas; una fecha sola es a medianoche de aquí
{
    assert.equal(edad('2026-11-17T11:48:00', AHORA), '12m');
    assert.equal(edad('2026-11-17T09:00:00', AHORA), '3h');
    assert.equal(edad('2026-11-12', AHORA), '5d');
    assert.equal(edad('2026-10-05T22:43:00', AHORA), '6sem');
    assert.equal(edad('', AHORA), '');
    assert.equal(edad('nunca', AHORA), '');
}

// 3. la barra: cuántas, cuántas preguntan y la más vieja
{
    assert.equal(resumen(LISTA, AHORA), '8 · 4 preguntan · la más vieja, hace 6 semanas');
    assert.equal(resumen([LISTA[3]], AHORA), '1 · 0 preguntan · la más vieja, hace 3 h');
    assert.equal(resumen([], AHORA), 'nada');
}

// 4. una fila: el clic abre la ventana para contestarla (por su dirección); al pasar el mouse, abrirla donde vive y, si
//    tiene hilo, ir a él
{
    const valor = html => html.match(/class="item[^"]*"[^>]*data-valor="([^"]*)"/)?.[1];
    const tarea = fila(LISTA[0], AHORA);
    assert.equal(valor(tarea), 'tarea:T93');
    assert.match(tarea, /data-accion="espera-contestar"/);
    assert.match(tarea, /data-grupo="preguntas"/);
    assert.match(tarea, /· faro/, 'dónde: el nombre corto de su proyecto');
    assert.match(tarea, />6sem</);
    assert.match(tarea, /¿la parto en pasos\?/, 'el resumen, en el globo');
    assert.match(tarea, /clic: contestarla/);
    assert.match(tarea, /data-accion="espera-abrir"[^>]*data-valor="tarea:T93"/, 'abrirla donde vive: su ficha');
    // su grupo ya dice «pregunta»: la fila no lo repite
    assert.doesNotMatch(tarea, /item-prefijo/);
    // un permiso: el clic abre la ventana (que dice que se contesta en la terminal y ofrece ir); al pasar, ir al hilo
    const hilo = fila(LISTA[4], AHORA);
    assert.equal(valor(hilo), 'permiso:Telar@servidor');
    assert.match(hilo, /data-accion="espera-abrir"[^>]*data-valor="hilo:Telar@servidor"/, 'ir al hilo');
    assert.match(hilo, /se contesta en la terminal del hilo/);
    assert.match(hilo, /item-prefijo[^>]*>permiso</);
    assert.match(hilo, /en servidor/, 'de otra máquina: lo dice');
    assert.match(fila(LISTA[5], AHORA), /item-prefijo[^>]*>pregunta</);
    assert.match(fila(LISTA[5], AHORA), /clic: contestarla/, 'la pregunta en vivo se contesta en la ventana');
    // de una que se propone cerrar, va cómo: el grupo ya dice «cerrar»
    assert.match(fila(LISTA[1], AHORA), /item-prefijo[^>]*>descartada</);
    // un retenido: su título ya dice de quién a quién; un clic lo contesta (soltarlo o descartarlo), y al pasar el mouse,
    // ir al hilo, soltarlo (abre la ventana con «Soltarlo» elegido) y descartarlo (en el rojo de quitar; pregunta)
    const retenido = fila(LISTA[2], AHORA);
    assert.equal(valor(retenido), 'mensaje:m1');
    assert.doesNotMatch(retenido, /· Faro/);
    assert.match(retenido, /data-valor="hilo:Faro"/);
    const conDe = fila({ ...LISTA[2], campos: { de: 'Molino', para: 'Faro' } }, AHORA);
    assert.match(conDe, /class="item-accion cuadrada tono-exito" data-accion="espera-soltar" data-valor="mensaje:m1" title="soltarlo: que salga a «Faro» \(lo confirmas en la ventana\)"/);
    assert.match(conDe, /class="item-accion cuadrada tono-peligro" data-accion="espera-descartar" data-valor="mensaje:m1" title="descartarlo: no sale nunca y a «Molino» le llega un aviso · pide confirmación"/);
    assert.ok(conDe.indexOf('espera-soltar') < conDe.indexOf('espera-descartar'), 'descartar, junto a soltar');
    for (const e of LISTA.filter(x => x.clase !== 'retenido')) assert.doesNotMatch(fila(e, AHORA), /espera-(soltar|descartar)/, `${e.direccion}: solo un retenido`);
    // lo de un módulo: su clase, como palabra
    assert.match(fila(LISTA[6], AHORA), /item-prefijo[^>]*>archivar</);
    // una decisión: su grupo ya lo dice; dónde, el que pregunta
    const decide = fila(LISTA[7], AHORA);
    assert.match(decide, /data-grupo="decisiones"/);
    assert.doesNotMatch(decide, /item-prefijo/);
    assert.match(decide, /· biblioteca/);
    // ninguna fila contesta por sí sola: el clic abre la ventana, y ahí se elige y se responde (dos clics)
    for (const e of LISTA) assert.doesNotMatch(fila(e, AHORA), /data-accion="(responder|soltar|cerrar|aceptar)"/);
}

// 5. el cuerpo: buscador, filtros con su cuenta, los grupos en orden; el de los hilos aunque esté vacío, los demás solo
//    con algo; lo plegado, sin sus filas. Las fallas ya no van aquí: las dice la franja de avisos (pruebas/avisos.mjs)
{
    const h = cuerpo(LISTA, new Set(), AHORA).join('');
    assert.match(h, /<div class="buscador-barra herram"><label class="buscador"[^>]*><span class="buscador-lupa i">[^<]*<\/span><input class="buscar" type="text" id="buscar-e"/,
        'el buscador, en su barra (componentes/buscador.ts)');
    assert.match(h, /aria-label="lo que te espera"/);
    assert.match(h, /<span class="buscador-cuenta" id="esperas-cuenta"><\/span>/);
    const grupos = [...h.matchAll(/class="grupo-esperas" data-grupo="([^"]+)"/g)].map(m => m[1]);
    assert.deepEqual(grupos, ['hilos', 'decisiones', 'preguntas', 'cerrar', 'preparado', 'retenidos', 'otras']);
    const ops = [...h.matchAll(/data-id="grupo:([^"]+)"[^>]*>.*?filtros-cuenta">(\d+)/g)].map(m => `${m[1]} ${m[2]}`);
    assert.deepEqual(ops, ['hilos 2', 'decisiones 1', 'preguntas 1', 'cerrar 1', 'preparado 1', 'retenidos 1', 'otras 1']);

    const sinHilos = cuerpo(LISTA.slice(0, 2), new Set(), AHORA).join('');
    assert.match(sinHilos, /ningún hilo te espera/);
    assert.doesNotMatch(sinHilos, /data-grupo="retenidos"/);

    const plegado = cuerpo(LISTA, new Set(['preguntas']), AHORA).join('');
    assert.doesNotMatch(plegado, /data-valor="tarea:T93"/);
    assert.match(plegado, /data-accion="esperas-plegar"[^>]*data-valor="preguntas"/);

    assert.doesNotMatch(cuerpo([], new Set(), AHORA).join(''), /no se pudo leer/);

    // los retenidos, si son varios: su cabecera ofrece descartarlos todos, en el rojo de quitar, y dice cuántos
    assert.doesNotMatch(h, /esperas-descartar-todos/, 'con uno solo, no');
    const otro = espera('mensaje:m2', 'retenido', '2026-11-15T09:00:00', { titulo: '«Faro» → «Molino»' });
    const varios = cuerpo([...LISTA, otro], new Set(), AHORA).join('');
    const cabecera = varios.slice(varios.indexOf('data-grupo="retenidos"'), varios.indexOf('data-valor="mensaje:m1"'));
    assert.match(cabecera, /class="item-accion cuadrada tono-peligro" data-accion="esperas-descartar-todos" data-valor="retenidos" title="descartar los 2: no sale ninguno, y a quien mandó cada uno le llega un aviso · pide confirmación"/);
    assert.equal((varios.match(/esperas-descartar-todos/g) ?? []).length, 1, 'solo en su grupo');
}

// 6. la prioridad y el vencimiento que trae una tarea, como en sus filas de «tareas»: el círculo chico de la prioridad al
//    comienzo (la urgente, en rojo; sin prioridad, un punto) y la fecha antes de cuánto lleva (lo vencido, en rojo)
{
    assert.equal(diasA('2026-11-14', AHORA), -3);
    assert.equal(diasA('2026-11-17', AHORA), 0);
    assert.equal(diasA('2026-11-20T10:00:00', AHORA), 3);
    assert.equal(diasA('', AHORA), null);
    assert.equal(diasA(undefined, AHORA), null);
    assert.equal(diasA('pronto', AHORA), null);

    const ranuras = html => [...html.matchAll(/<span class="item-ranura([^"]*)"/g)].map(m => m[1].trim());
    const p1 = fila(espera('tarea:T1', 'avance:pregunta', '2026-11-10', { campos: { prioridad: 1, vence: '2026-11-14' } }), AHORA);
    assert.match(p1, /title="P1 · alta"/, 'la prioridad, con su globo');
    assert.equal(ranuras(p1)[0], 'tono-p1');
    assert.match(p1, /item-vence tono-peligro"[^>]*title="venció hace 3 días">-3d</, 'vencida: en rojo, como en tareas');
    assert.match(p1, /-3d<\/span> · 7d</, 'la fecha y, después, cuánto lleva');
    assert.doesNotMatch(p1, /cambiarla/, 'se cambia en su ficha, no desde aquí');

    const p0 = fila(espera('tarea:T2', 'avance:preparado', '2026-11-17T09:00:00', { campos: { prioridad: 0, vence: '2026-11-17' } }), AHORA);
    assert.match(p0, /item-ranura tono-peligro"[^>]*title="P0 · urgente"/);
    assert.match(p0, /item-vence tono-atencion"[^>]*>hoy</);

    // sin prioridad, el punto; sin fecha, solo cuánto lleva
    const sin = fila(espera('tarea:T3', 'avance:pregunta', '2026-11-12', { campos: { prioridad: null } }), AHORA);
    assert.match(sin, /title="sin prioridad"/);
    assert.doesNotMatch(sin, /item-vence/);
    assert.match(sin, /item-meta"[^>]*>5d</);

    // lo que no es una tarea (un mensaje retenido, un hilo) no tiene prioridad: su ranura va vacía, y los títulos alinean
    const ret = fila(LISTA[2], AHORA);
    assert.equal(ranuras(ret).length, 3);
    assert.equal(ranuras(ret)[0], '');
    assert.equal(ranuras(p1).length, 3);
}

// 7. con mundos: lo de otro mundo se ve solo en el modo todo (al final); lo de un agente que pide esconderse fuera de su
// mundo (`agente`: su hilo, lo que pregunta; `fuera_de_su_mundo = "esconder"`), ni ahí: el 23-nov, en todo y en el
// trabajo, el Jardín no debía asomarse
{
    modelo.secciones = [{ clave: 'agente:jardin', nombre: 'Jardín', hilos: [], grupo: 'agentes', mundo: 'personal', fuera_de_su_mundo: 'esconder' }];
    mundo.recibir({ mundos: [{ nombre: 'trabajo', color: '', horario: [] }, { nombre: 'personal', color: '', horario: [] }], mundos_fuera: 'trabajo' });
    mundo.poner('trabajo');
    const p = new PantallaEsperas({});
    p.lista = [espera('tarea:T1', 'avance:pregunta', '2026-11-17', { mundo: 'trabajo' }),
        espera('tarea:T2', 'avance:pregunta', '2026-11-17', { mundo: 'personal' }),
        espera('permiso:Jardín', 'permiso', '2026-11-17', { mundo: 'personal', agente: 'jardin' }),
        espera('tarea:T3', 'avance:pregunta', '2026-11-17', { mundo: 'trabajo', agente: 'secretaria' })];
    const ver = () => p.visibles().map(e => e.direccion);
    assert.deepEqual(ver(), ['tarea:T1', 'tarea:T3'], 'en el trabajo, lo del trabajo');
    mundo.ordenarSolo(true);
    assert.deepEqual(ver(), ['tarea:T1', 'tarea:T2', 'tarea:T3'], 'en todo, lo de personal también; lo del agente de personal, no');
    mundo.ordenarSolo(false);
    mundo.poner('personal');
    assert.deepEqual(ver(), ['tarea:T2', 'permiso:Jardín'], 'en personal, lo suyo');
    mundo.poner('');
    assert.equal(ver().length, 4, 'con ambos, todo');
    // sin pedirlo (al-final, el de fábrica), lo suyo va como lo demás: en todo, sí
    modelo.secciones = [];
    mundo.poner('trabajo');
    mundo.ordenarSolo(true);
    assert.deepEqual(ver(), ['tarea:T1', 'tarea:T2', 'permiso:Jardín', 'tarea:T3'], 'al-final: en todo, todo');
    mundo.ordenarSolo(false);
}

console.log('esperas: 7 grupos de pruebas, bien');
