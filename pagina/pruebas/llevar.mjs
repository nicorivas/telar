// Prueba de llevar un hilo a otra máquina desde su menú (src/web/llevar-destinos.ts, y el menú de web/interfaz.ts con
// filas apagadas), y de seguirlo a donde vive después (src/web/donde-vive.ts: su registro en el bus dice su dueño): desde cualquier máquina, a cualquier otra de la persona, una fila por máquina con su nombre; la que no
// contesta, apagada y con su porqué, nunca escondida. Un hilo de aquí se lleva; uno de otra máquina se trae aquí o su
// máquina lo lleva a una tercera. En el menú (con un DOM, happy-dom): las filas de llevar van arriba, a la vista, se
// encuentran escribiendo la máquina o «pasar», y una apagada no se elige ni con un clic ni con ⏎.
// Y lo que dice el panel de la mudanza en cada paso (src/web/mudanza-texto.ts): esperar su turno, subir lo suyo, y al
// copiar cuánto va, de cuánto, y cuánto ya estaba allá; y lo que muestra antes de llevarlo, si tiene algo sin subir.
// Corre en Node: npm run prueba:llevar
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
const outfile = path.join(mkdtempSync(path.join(tmpdir(), 'llevar-')), 'llevar.cjs');
await build({
    stdin: { contents: "export * as L from './web/llevar-destinos'; export * as interfaz from './web/interfaz'; export * as D from './web/donde-vive'; export * as T from './web/mudanza-texto';",
        resolveDir: src, loader: 'ts' },
    bundle: true, platform: 'node', format: 'cjs', outfile, logLevel: 'warning',
});

// el DOM antes de cargar lo que lo usa
const w = new Window({ url: 'http://localhost/' });
for (const k of ['window', 'document', 'Element', 'HTMLElement', 'HTMLInputElement', 'Node', 'Event', 'KeyboardEvent', 'MouseEvent', 'getComputedStyle', 'requestAnimationFrame', 'innerWidth', 'innerHeight'])
    globalThis[k] = k === 'window' ? w : w[k] ?? globalThis[k];
const { L, interfaz, D, T } = require(outfile);

// el reloj: 23-nov, 19:00 (hora local de quien corre la prueba)
const AHORA = new Date(2026, 10, 23, 19, 0).getTime();
const haceS = (h, m) => (AHORA - new Date(2026, 10, 23, h, m).getTime()) / 1000;
const enLinea = nombre => ({ nombre, en_linea: true, edad: 3, fuera: false });
const fuera = (nombre, h, m) => ({ nombre, en_linea: false, edad: haceS(h, m), fuera: true });

// ── un hilo que vive aquí: una fila por cada otra máquina, con su nombre ──
{
    // desde el servidor, sin [remotos]: el laptop, por el bus (lo que no se veía: «llevar a otra máquina», al final)
    const f = L.filasLlevar({ aqui: 'servidor', vive: '', remotos: [], otras: [enLinea('laptop')], ahora: AHORA });
    assert.deepEqual(f.map(x => [x.modo, x.a, x.por, x.label, x.apagado]), [['llevar', 'laptop', 'bus', 'llevar a laptop', '']]);
    assert.match(f[0].description, /su conversación viaja; los archivos no · por el bus/);
    // `vive` igual a esta máquina es lo mismo que vacío
    assert.deepEqual(L.filasLlevar({ aqui: 'servidor', vive: 'servidor', remotos: [], otras: [enLinea('laptop')], ahora: AHORA }).map(x => x.a), ['laptop']);
}
{
    // desde el laptop: el servidor ([remotos], primero) y otra del bus; esta máquina nunca es destino. El servidor también
    // está en el bus: por el bus (un dueño por hilo, telar.dueno); por ssh, solo una de [remotos] sin foto en el bus
    const f = L.filasLlevar({ aqui: 'laptop', vive: '', remotos: [{ nombre: 'servidor', destino: 'ana@servidor' }, { nombre: 'viejo' }],
        otras: [enLinea('servidor'), enLinea('escritorio'), enLinea('laptop')], ahora: AHORA });
    assert.deepEqual(f.map(x => [x.a, x.por]), [['servidor', 'bus'], ['viejo', 'ssh'], ['escritorio', 'bus']]);
    assert.match(f[0].description, /por el bus$/);
    assert.match(f[1].description, /por ssh$/);
}
{
    // una fuera de línea: se ve, apagada, y dice desde cuándo y por qué; las demás siguen encendidas
    const f = L.filasLlevar({ aqui: 'servidor', vive: '', remotos: [], otras: [fuera('laptop', 14, 2), enLinea('escritorio')], ahora: AHORA });
    assert.equal(f.length, 2, 'la que no contesta no desaparece');
    assert.equal(f[0].apagado, 'laptop fuera de línea desde 14:02: no tiene dónde recibirlo');
    assert.equal(f[0].description, f[0].apagado);
    assert.equal(f[1].apagado, '');
    // sin noticias, sin que se sepa que se fue (el nodo de aquí no está al día): apagada igual, por el bus hace falta su nodo
    const vieja = L.filasLlevar({ aqui: 'servidor', vive: '', remotos: [], otras: [{ nombre: 'laptop', en_linea: false, edad: 600, fuera: false }], ahora: AHORA });
    assert.equal(vieja[0].apagado, 'laptop no da noticias hace 10 min: no tiene dónde recibirlo');
    // una de [remotos] que está en el bus va por el bus, aunque haya ssh: con su foto vieja (su nodo caído), apagada, porque
    // allá nadie lo tomaría; una de [remotos] que el bus no conoce (sin foto) va por ssh y se intenta
    const ssh = o => L.filasLlevar({ aqui: 'laptop', vive: '', remotos: [{ nombre: 'servidor' }], otras: o ? [o] : [], ahora: AHORA })[0];
    assert.equal(ssh({ nombre: 'servidor', en_linea: false, edad: 600, fuera: false }).apagado, 'servidor no da noticias hace 10 min: no tiene dónde recibirlo');
    assert.match(ssh(fuera('servidor', 18, 30)).apagado, /^servidor fuera de línea desde 18:30/);
    assert.deepEqual([ssh().por, ssh().apagado], ['ssh', '']);
}
{
    // sin otra máquina: nada que ofrecer (el menú no muestra una fila que no lleva a ninguna parte)
    assert.deepEqual(L.filasLlevar({ aqui: 'laptop', vive: '', remotos: [], otras: [], ahora: AHORA }), []);
}

// ── un hilo que vive en otra máquina: traerlo aquí, o que su máquina lo lleve a una tercera ──
{
    const f = L.filasLlevar({ aqui: 'laptop', vive: 'servidor', remotos: [{ nombre: 'servidor' }],
        otras: [enLinea('servidor'), enLinea('escritorio')], ahora: AHORA });
    assert.deepEqual(f.map(x => [x.modo, x.desde, x.a, x.label]), [
        ['traer', 'servidor', 'laptop', 'traer a laptop (esta máquina)'],
        ['llevar-desde', 'servidor', 'escritorio', 'llevar a escritorio'],
    ]);
    assert.match(f[0].description, /^vive en servidor: su conversación viaja/);
    // la tercera fuera de línea: esa fila apagada; traerlo aquí sigue
    const g = L.filasLlevar({ aqui: 'laptop', vive: 'servidor', remotos: [], otras: [enLinea('servidor'), fuera('escritorio', 9, 5)], ahora: AHORA });
    assert.deepEqual(g.map(x => !!x.apagado), [false, true]);
    assert.match(g[1].apagado, /^escritorio fuera de línea desde 09:05: no tiene dónde recibirlo$/);
    // su máquina fuera de línea: todo apagado, porque su conversación vive allá
    const h = L.filasLlevar({ aqui: 'laptop', vive: 'servidor', remotos: [], otras: [fuera('servidor', 18, 0), enLinea('escritorio')], ahora: AHORA });
    assert.deepEqual(h.map(x => x.apagado), ['servidor fuera de línea desde 18:00: su conversación vive allá', 'servidor fuera de línea desde 18:00: su conversación vive allá']);
    // remoto sin saber adónde («?»): nada que ofrecer
    assert.deepEqual(L.filasLlevar({ aqui: 'laptop', vive: '?', remotos: [], otras: [enLinea('servidor')], ahora: AHORA }), []);
    // su máquina fuera de línea y aquí una copia (telar.seguir, la etapa 4): en lugar de traer, seguir aquí, con de cuándo
    // es la copia y cuánto falta; las otras filas siguen apagadas (su conversación vive allá)
    const conCopia = { puede: true, aqui: { bytes: 61.2e6, fecha: new Date(AHORA - 3 * 3600e3).toISOString() }, alla: { bytes: 63.8e6 } };
    const s = L.filasLlevar({ aqui: 'laptop', vive: 'servidor', remotos: [], otras: [fuera('servidor', 18, 0), enLinea('escritorio')], ahora: AHORA, seguir: conCopia });
    assert.equal(s[0].modo, 'seguir');
    assert.equal(s[0].label, 'seguir aquí, desde la copia de aquí');
    assert.equal(s[0].apagado, '');
    assert.match(s[0].description, /^servidor fuera de línea desde 18:00: la copia de aquí, de hoy \d\d:\d\d \(61,2 MB\); faltan unos 2,6 MB$/);
    assert.ok(s[1].apagado, 'llevarlo a una tercera no se puede: su conversación vive allá');
    // al día, o sin saber cuánto pesaba allá
    const al = L.filasLlevar({ aqui: 'laptop', vive: 'servidor', remotos: [], otras: [fuera('servidor', 18, 0)], ahora: AHORA, seguir: { ...conCopia, alla: { bytes: 61.2e6 } } });
    assert.match(al[0].description, /no debería faltar nada$/);
    const sin = L.filasLlevar({ aqui: 'laptop', vive: 'servidor', remotos: [], otras: [fuera('servidor', 18, 0)], ahora: AHORA, seguir: { ...conCopia, alla: null } });
    assert.match(sin[0].description, /no se sabe cuánto pesaba en servidor$/);
    // sin copia aquí: traer apagado, con el porqué que dijo telar
    const no = L.filasLlevar({ aqui: 'laptop', vive: 'servidor', remotos: [], otras: [fuera('servidor', 18, 0)], ahora: AHORA,
        seguir: { puede: false, por_que_no: 'servidor fuera de línea desde 18:00, y aquí no hay copia de su conversación: vuelve cuando vuelva servidor' } });
    assert.equal(no[0].modo, 'traer');
    assert.match(no[0].apagado, /vuelve cuando vuelva servidor$/);
    // con su máquina en línea, lo de seguir no cambia nada: se trae
    assert.equal(L.filasLlevar({ aqui: 'laptop', vive: 'servidor', remotos: [], otras: [enLinea('servidor')], ahora: AHORA, seguir: conCopia })[0].modo, 'traer');
}

// ── dónde vive ahora (web/donde-vive.ts): la página sigue al hilo que se llevó, sin decir «retómalo» ──
{
    const S = 1795470000; // segundos
    const foto = (nombre, ...hilos) => ({ nombre, en_linea: true, hilos: hilos.map(h => (typeof h === 'string' ? { nombre: h, vivo: true } : h)) });
    const donde = o => D.dondeVive('Faro', { aqui: 'laptop', otras: [], ahora: S, ...o });
    // abierto aquí, con su propia ventana
    assert.deepEqual(donde({ local: { nombre: 'Faro', vivo: true } }), { a: 'aqui' });
    // lo que se vio en la página tras llevarlo del servidor al laptop: la lista recordaba «vive en servidor» (su ventana de
    // aquí miraba allá) y el servidor ya no lo tenía: antes, «esperándola…» y «retómalo». Ahora: abierto aquí, o se espera
    // si allá todavía lo tiene; y si se fue a una tercera, a esa
    const espejo = { nombre: 'Faro', vivo: false, remoto: 'servidor' };
    assert.deepEqual(donde({ local: espejo, otras: [foto('servidor', 'Faro')] }), { a: 'espejo', maquina: 'servidor' });
    assert.deepEqual(donde({ local: espejo, otras: [foto('servidor')] }), { a: 'espejo', maquina: 'servidor' },
        'ni allá ni en otra: se espera (la lista de aquí se pone al día en segundos)');
    assert.deepEqual(donde({ local: espejo, otras: [foto('servidor'), foto('escritorio', 'Faro')] }), { a: 'alla', maquina: 'escritorio' });
    assert.deepEqual(donde({ local: espejo }), { a: 'espejo', maquina: 'servidor' }, 'sin foto del servidor: lo de antes, esperar');
    // la ventana que mira a otra máquina (la de una foto, `remoto`) no cuenta como abierto allá
    assert.deepEqual(donde({ local: espejo, otras: [foto('servidor'), foto('escritorio', { nombre: 'Faro', vivo: true, remoto: 'servidor' })] }),
        { a: 'espejo', maquina: 'servidor' });
    // su registro en el bus (telar.dueno) dice de quién es: la página lo sigue al dueño, sin conjeturas ni minutos
    const cerrado = { nombre: 'Faro', vivo: false };
    assert.deepEqual(donde({ local: cerrado, registro: { dueno: 'servidor', vivo: true } }), { a: 'alla', maquina: 'servidor' });
    // en camino: cediéndose (su agente se detuvo aquí), o ya tomado y abriéndose allá
    assert.deepEqual(donde({ local: cerrado, registro: { dueno: 'laptop', cede: 'servidor', mudanza: { paso: 'copiar', hora: S - 5 } } }),
        { a: 'viajando', maquina: 'servidor' });
    assert.deepEqual(donde({ local: cerrado, registro: { dueno: 'servidor', vivo: false, mudanza: { paso: 'abrir', hora: S - 5 } } }),
        { a: 'viajando', maquina: 'servidor' });
    // uno colgado hace una hora ya no dice «en camino»: lo que valga lo dice su dueño
    assert.deepEqual(donde({ local: cerrado, registro: { dueno: 'laptop', cede: 'servidor', mudanza: { paso: 'copiar', hora: S - 3600 } } }),
        { a: 'cerrado' });
    // es de aquí y no está abierto: cerrado aquí, aunque otra máquina tenga uno abierto con su nombre
    assert.deepEqual(donde({ local: cerrado, registro: { dueno: 'laptop' }, otras: [foto('servidor', 'Faro')] }), { a: 'cerrado' });
    // un registro de antes, sin dueño: su máquina
    assert.deepEqual(donde({ local: cerrado, registro: { maquina: 'servidor', vivo: true } }), { a: 'alla', maquina: 'servidor' });
    // llevado a una de [remotos]: aquí queda su ventana que lo mira allá, y esa es la que se mira
    assert.deepEqual(donde({ local: { nombre: 'Faro', vivo: true, remoto: 'servidor' }, registro: { dueno: 'servidor', vivo: true } }),
        { a: 'espejo', maquina: 'servidor' });
    // cerrado allá: no hay dónde mirarlo abierto
    assert.deepEqual(donde({ local: cerrado, registro: { dueno: 'servidor', vivo: false } }), { a: 'cerrado' });
    assert.deepEqual(donde({ registro: { dueno: 'servidor', vivo: false } }), { a: 'nada' });
    // sin registro (sin bus), otro abierto con el mismo nombre en otra máquina no es este
    const archivado = { nombre: 'Faro', vivo: false, archivado: true };
    assert.deepEqual(donde({ local: archivado, otras: [foto('servidor', 'Faro')] }), { a: 'cerrado' });
    // lo que se miraba en otra máquina: si sigue allá, ahí; si se fue, aquí o a donde esté
    assert.deepEqual(donde({ mirando: 'servidor', otras: [foto('servidor', 'Faro')] }), { a: 'alla', maquina: 'servidor' });
    assert.deepEqual(donde({ mirando: 'servidor', local: { nombre: 'Faro', vivo: true }, otras: [foto('servidor')] }), { a: 'aqui' });
    assert.deepEqual(donde({ mirando: 'servidor', otras: [foto('servidor'), foto('escritorio', 'Faro')] }), { a: 'alla', maquina: 'escritorio' });
    assert.deepEqual(donde({ mirando: 'servidor', otras: [foto('servidor')] }), { a: 'nada' });
    assert.deepEqual(D.partirVista('rem:servidor:Faro: dos'), { hilo: 'Faro: dos', maquina: 'servidor' });

    // seguir lo que se mira: solo si se lo vio abierto donde se lo mira y se fue de ahí
    const seg = new D.Seguidor();
    assert.equal(seg.mirar('Faro', { a: 'espejo', maquina: 'servidor' }, 0), '', 'abierto donde se lo mira: quedarse');
    assert.equal(seg.mirar('Faro', { a: 'aqui' }, 1000), '', 'llegó aquí: la misma vista, la terminal se reconecta sola');
    assert.equal(seg.mirar('Faro', { a: 'cerrado' }, 2000), '');
    assert.equal(seg.sefue('Faro'), true, 'se fue: se pregunta por su registro en el bus');
    assert.equal(seg.mirar('Faro', { a: 'alla', maquina: 'servidor' }, 3000), 'rem:servidor:Faro');
    assert.equal(seg.mirar('rem:servidor:Faro', { a: 'alla', maquina: 'servidor' }, 4000), '');
    assert.equal(seg.mirar('rem:servidor:Faro', { a: 'aqui' }, 5000), 'Faro', 'y si vuelve, de vuelta a la de aquí');
    // uno archivado que se abrió para leerlo (nunca se lo vio abierto aquí) no se mueve, aunque viva en otra
    const otro = new D.Seguidor();
    assert.equal(otro.mirar('Viejo', { a: 'cerrado' }, 0), '');
    assert.equal(otro.mirar('Viejo', { a: 'alla', maquina: 'servidor' }, 1000), '');
    // pasados unos minutos sin encontrarlo, se deja de buscar
    const tarde = new D.Seguidor();
    tarde.mirar('Faro', { a: 'aqui' }, 0);
    tarde.mirar('Faro', { a: 'cerrado' }, 1000);
    assert.equal(tarde.mirar('Faro', { a: 'alla', maquina: 'servidor' }, 1000 + 4 * 60_000), '');
}

// ── el menú: una fila apagada se ve y no se elige ──
const esperar = (ms = 0) => new Promise(r => setTimeout(r, ms));
const filas = () => [...document.querySelectorAll('.m-lista .item')];
const tecla = (k) => document.querySelector('input.buscar').dispatchEvent(new w.KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true }));
{
    const opciones = [
        { label: 'llevar a laptop', description: 'laptop fuera de línea desde 14:02: no tiene dónde recibirlo', apagada: true, detail: 'pasar, mover o mudar' },
        { label: 'llevar a escritorio', description: 'su conversación viaja; los archivos no', detail: 'pasar, mover o mudar' },
        { label: 'renombrar' },
    ];
    let elegida = interfaz.menu(opciones, { x: 10, y: 10 }, { titulo: 'Faro' });
    await esperar();
    assert.equal(filas().length, 3);
    assert.ok(filas()[0].classList.contains('apagada'), 'la apagada se ve, apagada');
    assert.match(filas()[0].getAttribute('title') ?? '', /fuera de línea desde 14:02/, 'y dice por qué al pasar el mouse');
    assert.ok(!filas()[1].classList.contains('apagada'));
    // un clic en la apagada no hace nada: el menú sigue abierto
    filas()[0].dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
    await esperar();
    assert.ok(document.querySelector('.m-lista'), 'sigue abierto');
    // ⏎ sobre la apagada (la primera, marcada al abrir) tampoco
    tecla('Enter');
    await esperar();
    assert.ok(document.querySelector('.m-lista'), 'sigue abierto tras ⏎ en la apagada');
    // la encendida sí
    filas()[1].dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
    assert.equal(await elegida, 1);

    // se encuentra escribiendo la máquina, o «pasar» (lo que decía la persona), aunque la fila no lo diga
    elegida = interfaz.menu(opciones, { x: 10, y: 10 });
    await esperar();
    const buscar = document.querySelector('input.buscar');
    for (const [q, n] of [['escritorio', 1], ['pasar', 2], ['laptop', 1]]) {
        buscar.value = q;
        buscar.dispatchEvent(new w.Event('input', { bubbles: true }));
        assert.equal(filas().length, n, q);
    }
    tecla('Escape');
    assert.equal(await elegida, undefined);
}
{
    // en el menú del centro (sin dónde: ⌘K, una tecla) también
    const elegida = interfaz.elegir([{ label: 'llevar a laptop', description: 'fuera de línea', apagada: true }, { label: 'llevar a escritorio' }]);
    await esperar();
    const ops = [...document.querySelectorAll('.e-lista .item')];
    assert.ok(ops[0].classList.contains('apagada'));
    ops[0].dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
    tecla('Enter');
    await esperar();
    assert.ok(document.querySelector('.e-lista'), 'la apagada no cierra el menú');
    ops[1].dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
    assert.equal(await elegida, 1);
}

// ── lo que dice el panel de la mudanza (web/mudanza-texto.ts) ──
{
    assert.equal(T.detalle({ paso: 'revisar' }, 'Faro', 'servidor'), 'preguntándole a servidor si lo puede recibir…');
    assert.match(T.detalle({ paso: 'esperar' }, 'Faro', 'servidor'), /esperando que «Faro» termine su turno/);
    // de un telar de antes (va entera), como antes
    assert.equal(T.detalle({ paso: 'copiar', bytes: 2.3e6 }, 'Faro', 'servidor'), 'copiando 2,3 MB…');
    // de vuelta: allá había casi todo, y se dice
    assert.equal(T.detalle({ paso: 'copiar', total: 65e6, por_mandar: 1.2e6, mandados: 6e5 }, 'Faro', 'laptop'),
        'copiando 600 KB de 1,2 MB · 63,8 MB ya estaban en laptop…');
    // la primera vez: nada estaba allá
    assert.equal(T.detalle({ paso: 'copiar', total: 4e7, por_mandar: 4e7, mandados: 0 }, 'Faro', 'servidor'), 'copiando 0 KB de 40,0 MB…');
    assert.match(T.detalle({ paso: 'copiar', total: 4e7, por_mandar: 0, mandados: 0 }, 'Faro', 'servidor'), /servidor ya tenía su conversación entera \(40,0 MB\)/);
    assert.equal(T.detalle({ paso: 'listo' }, 'Faro', 'servidor'), '');
    assert.match(T.detalle({ paso: 'detener' }, 'Faro', 'servidor'), /deteniendo a su agente aquí/);
    assert.match(T.detalle({ paso: 'cerrar' }, 'Faro', 'servidor'), /servidor ya lo tomó/);
    // la barra avanza con lo que viajó
    assert.equal(T.fraccion({ paso: 'copiar', por_mandar: 1e6, mandados: 2.5e5 }), 0.25);
    assert.equal(T.fraccion({ paso: 'copiar', bytes: 1e6 }), undefined);
    assert.equal(T.fraccion({ paso: 'abrir', por_mandar: 1e6, mandados: 1e6 }), undefined);
}
// ── antes de llevarlo: lo que tiene sin subir (web/mudanza-texto.ts, `antes`) ──
{
    assert.equal(T.detalle({ paso: 'subir' }, 'Faro', 'servidor'), 'subiendo lo suyo: commiteando solo lo que escribió «Faro»…');
    assert.equal(T.detalle({ paso: 'subir', subido: 'faro: subido' }, 'Faro', 'servidor'), 'subido: faro: subido');
    const repo = { nombre: 'proyectos/faro', relativa: 'proyectos/faro', rama: 'main', commit: 'a1b2c3d4e5', pendiente: true,
        puede_subir: true, por_que_no: '', del_hilo: ['plan.md', 'mapa.ts'], n_del_hilo: 2, en_su_carpeta: ['mapa.png'],
        n_en_su_carpeta: 1, commits: ['9f8e7d6 el mapa'], n_commits: 1 };
    // nada sin subir y allá al día: ni se pregunta
    const nada = T.antes({ pendiente: { repos: [{ ...repo, pendiente: false, del_hilo: [], n_del_hilo: 0, en_su_carpeta: [],
        n_en_su_carpeta: 0, commits: [], n_commits: 0 }] }, destino: [{ relativa: 'proyectos/faro', existe: true, tiene: true }] }, 'servidor');
    assert.deepEqual(nada, { grupos: [], avisos: [], puedeSubir: false, hay: false });
    // lo suyo se sube, lo de su carpeta se queda, y allá va atrás
    const a = T.antes({ pendiente: { repos: [repo] }, destino: [{ relativa: 'proyectos/faro', existe: true, tiene: false }],
        avisos: ['sus hijos con rama (Calendario) se quedan aquí'] }, 'servidor');
    assert.equal(a.hay, true);
    assert.equal(a.puedeSubir, true);
    assert.equal(a.grupos[0].repo, 'proyectos/faro · main');
    assert.deepEqual(a.grupos[0].secciones.map(s => [s.tono, s.titulo]), [
        ['sube', '2 archivos de este hilo sin commitear: se commitean y se suben'],
        ['sube', '1 commit sin subir: se sube'],
        ['queda', '1 archivo más sin commitear en su carpeta: no sé si es suyo, no se sube'],
        ['info', 'servidor va atrás (no tiene a1b2c3d): al llegar se trae de arriba'],
    ]);
    assert.deepEqual(a.grupos[0].secciones[0].items, ['plan.md', 'mapa.ts']);
    assert.deepEqual(a.avisos, ['sus hijos con rama (Calendario) se quedan aquí']);
    // solo lo de su carpeta, que no se sabe de quién es: se muestra, y no se ofrece subir
    const solo = T.antes({ pendiente: { repos: [{ ...repo, puede_subir: false, del_hilo: [], n_del_hilo: 0, commits: [], n_commits: 0 }] } }, 'laptop');
    assert.equal(solo.hay, true);
    assert.equal(solo.puedeSubir, false);
    assert.deepEqual(solo.grupos[0].secciones.map(s => s.titulo), ['1 archivo sin commitear en su carpeta: no sé si es suyo, no se sube']);
    // su rama sin una de arriba: lo suyo se queda, y se dice por qué
    const sin = T.antes({ pendiente: { repos: [{ ...repo, puede_subir: false, por_que_no: 'la rama main no tiene una de arriba' }] } }, 'laptop');
    assert.equal(sin.puedeSubir, false);
    assert.deepEqual(sin.grupos[0].secciones.map(s => s.tono), ['queda', 'queda', 'queda', 'queda']);
    assert.equal(sin.grupos[0].secciones.at(-1).titulo, 'no se puede subir: la rama main no tiene una de arriba');
    // una lista larga, cortada
    const larga = T.antes({ pendiente: { repos: [{ ...repo, del_hilo: Array.from({ length: 40 }, (_, i) => `f${i}.md`), n_del_hilo: 57 }] } }, 'x');
    assert.equal(larga.grupos[0].secciones[0].items.length, T.MOSTRAR);
    assert.equal(larga.grupos[0].secciones[0].mas, 57 - T.MOSTRAR);
    // solo lo que llegaría a medias, sin nada sin subir: se pregunta igual
    assert.equal(T.antes({ avisos: ['su carpeta no existe allá'] }, 'x').hay, true);
}

await w.happyDOM.close();
console.log('llevar: ok');
