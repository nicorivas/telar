// Prueba de la línea del pulso y su ventana (src/componentes/pulso.ts dibuja; src/web/pulso.ts lee, muestra y marca lo
// visto): qué dice la línea (la última con cambios sin ver, lo que cambió, seco, lo que falló, «+N»), qué lleva la ventana
// (cada pasada con su resumen, lo que falló y cada cambio con su causa, enlazado a su dirección; la que no cambió nada, en
// una línea; lo que te espera y las vencidas, no), y lo que se pide a la API (con un fetch de mentira: nada sale): leer lo
// sin ver, y al cerrar, marcar vistas hasta la más nueva que se mostró. Y con un mundo puesto (trabajo, personal o
// ambos): solo lo de ese mundo y lo sin clasificar, las cuentas de lo que se ve, el resumen de las de antes y lo visto por
// mundo. Corre en Node, sin página: npm run prueba:pulso
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const dir = mkdtempSync(path.join(tmpdir(), 'pulso-'));
const src = path.join(aqui, '..', 'src');
const entrada = path.join(dir, 'entrada.ts');
writeFileSync(entrada, [
    `export * from ${JSON.stringify(path.join(src, 'componentes', 'pulso.ts'))};`,
    `export { pasadasDeMuestra } from ${JSON.stringify(path.join(src, 'componentes', 'muestras-pulso.ts'))};`,
    `export { Pulso, HACER } from ${JSON.stringify(path.join(src, 'web', 'pulso.ts'))};`,
].join('\n'));
const salida = path.join(dir, 'pulso.cjs');
await build({ entryPoints: [entrada], bundle: true, platform: 'node', format: 'cjs', outfile: salida, logLevel: 'warning' });

// el fetch de mentira: anota cada pedido y responde lo que diga `responder` (por defecto, nada sin ver)
const pedidos = [];
let responder = () => ({ ok: true, total: 0, pasadas: [] });
globalThis.fetch = async (url, init = {}) => {
    const p = { url: String(url), metodo: init.method ?? 'GET', cuerpo: init.body ? JSON.parse(init.body) : undefined };
    pedidos.push(p);
    const r = responder(p);
    if (r instanceof Error) throw r;
    const [cuerpo, estado] = Array.isArray(r) ? r : [r, 200];
    return new Response(JSON.stringify(cuerpo), { status: estado, headers: { 'Content-Type': 'application/json' } });
};
const P = require(salida);

const AHORA = new Date('2026-11-18T15:20:00').getTime();
const HOY = '2026-11-18';
const M = P.pasadasDeMuestra(AHORA);
const [nueva, seca, quieta, noche] = M.pasadas;
const texto = l => l.replace(/^.*?<span class="pulso-texto">/s, '').replace(/<\/span><span class="pulso-mas">.*$/s, '').replace(/<[^>]+>/g, '');

// 1. cuándo: la hora de hoy, «ayer», otro día; y lo que tardó
{
    assert.equal(P.hoyLocal(AHORA), HOY);
    assert.equal(P.cuando('2026-11-18T13:00', HOY), '13:00');
    assert.equal(P.cuando('2026-11-17T23:30', HOY), 'ayer 23:30');
    assert.equal(P.cuando('2026-11-03T08:00', HOY), '3-nov 08:00');
    assert.equal(P.diaCorto('2026-11-19', HOY), 'mañana');
    assert.equal(P.tramo(nueva, HOY), '15:00–15:09');
    assert.equal(P.tramo(noche, HOY), 'ayer 23:30–00:12', 'la de anoche pasa la medianoche');
    assert.equal(P.tramo({ id: '2026-11-18T13:00' }, HOY), '13:00', 'sin término, solo cuándo empezó');
}

// 2. la línea: la última con cambios sin ver, lo que cambió, lo que falló y cuántas más con cambios hay
{
    const l = P.linea({ pasadas: M.pasadas, total: M.total, cambios: M.con_cambios, nombre: 'pulso', hoy: HOY });
    assert.match(l, /^<div class="pulso-linea" data-accion="pulso-abrir" role="button" title="la última pasada de pulso con cambios que no has visto: 15:00–15:09\n/);
    assert.match(l, /<span class="pulso-icono"><span class="i">\u{eb31}<\/span><\/span>/u, 'el ícono del pulso, en su ranura');
    assert.equal(texto(l), 'pulso 15:00 · 1 nueva · 2 avanzadas · 1 cerrada · 1 borrador · falló whatsapp', 'solo cambios: ni lo que te espera ni las vencidas');
    assert.doesNotMatch(l, /espera|vencida|T405/);
    assert.match(l, /<span class="pulso-falla">falló whatsapp<\/span>/, 'lo que falló, en su color');
    assert.match(l, /<span class="pulso-mas">\+2<\/span><\/div>$/, 'la que no cambió nada no cuenta');
    assert.match(l, /y 2 pasadas más con cambios\nclic: verlas \(al cerrar, quedan vistas\)/);
    // en seco: marcada, y el ícono tenue (la clase)
    const s = P.linea({ pasadas: [seca], hoy: HOY });
    assert.match(s, /^<div class="pulso-linea seco"/);
    assert.match(s, /pulso 14:00<\/span> <span class="pulso-marca">seco<\/span> · 2 nuevas · 1 avanzada</);
    assert.doesNotMatch(s, /pulso-mas/, 'una sola: sin «+N»');
    // `cambios` manda sobre las que llegaron enteras (vienen hasta 40)
    assert.match(P.linea({ pasadas: [seca], cambios: 41, hoy: HOY }), /\+40</);
    // de anoche, con su día y su marca
    assert.match(P.linea({ pasadas: [noche], hoy: HOY }), /pulso ayer 23:30<\/span> <span class="pulso-marca">noche<\/span> · 1 nueva</);
    assert.deepEqual(P.cuentas({ id: 'x', tareas: { avanzadas: [{}, {}], cerradas: [{}] } }), ['2 avanzadas', '1 cerrada']);
    assert.deepEqual(P.cuentas({ id: 'x', te_esperan: [{}] }), ['sin cambios']);
    // la más nueva sin cambios no es la de la línea: es la de antes que sí cambió; y solo con las que no cambiaron, nada
    assert.match(P.linea({ pasadas: [quieta, noche], hoy: HOY }), /pulso ayer 23:30/);
    assert.equal(P.linea({ pasadas: [quieta], total: 1, hoy: HOY }), '');
    // sin pasadas sin ver, nada
    assert.equal(P.linea({ pasadas: [], total: 0, hoy: HOY }), '');
    // lo que viene de la pasada va escapado
    assert.doesNotMatch(P.linea({ pasadas: [{ ...seca, resumen: '<b>x</b>' }], hoy: HOY }), /<b>/);
}

// 3. la ventana: las sin ver, la más nueva arriba; cada cambio con su causa; la que no cambió nada, en una línea
{
    const v = P.ventanaPulso({ pasadas: M.pasadas, total: M.total, cambios: M.con_cambios, nombre: 'pulso', visto: M.visto, hoy: HOY });
    assert.equal(v.titulo, 'pulso · 3 pasadas con cambios');
    assert.equal(v.ayuda, 'visto hasta ayer 22:00 · al cerrar, quedan vistas');
    assert.equal(v.clase, 'pulso');
    assert.match(v.pie, /data-accion="listo"/);
    const c = v.cuerpo;
    const orden = [...c.matchAll(/<span class="pulso-cuando">([^<]+)<\/span>/g)].map(m => m[1]);
    assert.deepEqual(orden, ['15:00–15:09', '14:00–14:25', '13:00–13:04', 'ayer 23:30–00:12']);
    const [s1, s2, s3, s4] = c.split('<section').slice(1);
    // ni las fuentes, ni lo que te espera, ni las vencidas sin propuesta
    assert.doesNotMatch(c, /te esperan|vencidas|T405|T566|T591|Lumbre|correo-trabajo <span|archivados/);
    // lo que falló, con por qué
    assert.match(s1, /<div class="pulso-fallo"><span class="pulso-falla">falló whatsapp<\/span> <span class="pulso-tenue">la sesión de WhatsApp Web se cerró<\/span><\/div>/);
    // cada cambio enlazado a su dirección y, debajo, su causa: el ícono de su fuente, por qué y su enlace
    assert.match(s1, /<div class="pulso-grupo-nombre">nuevas<\/div><div class="pulso-grupo-filas"><div class="pulso-cambio"><div class="pulso-fila"><a class="pulso-dir" data-direccion="tarea:T580" title="abrir tarea:T580">tarea:T580<\/a> Arcilla: retrospectiva[^<]*<\/div><div class="pulso-causa"><span class="i" title="correo-trabajo">\u{eb1c}<\/span> correo de Carla Rojas <a class="pulso-dir" data-web="https:\/\/mail.google.com\/mail\/u\/0\/#inbox\/r-580" title="https:\/\/mail.google.com\/mail\/u\/0\/#inbox\/r-580">mail.google.com<\/a><\/div>/u, 'una web, por su sitio');
    assert.match(s1, /Molino[^<]*<\/div><div class="pulso-causa"><span class="i" title="minutas">\u{eaa4}<\/span> minuta del 17-nov <a class="pulso-dir" data-direccion="archivo:trabajo\/minutas\/2026-11-17.md"/u);
    assert.match(s1, /data-direccion="tarea:T512"[^>]*>tarea:T512<\/a> <span class="pulso-tenue">hecha<\/span> el correo a Tomás[^<]*<\/div><div class="pulso-causa"><span class="i" title="persona">\u{ea67}<\/span> respuesta de Ana<\/div>/u);
    // los borradores: para quién, el asunto y su tarea; su causa sin enlace (el del borrador va en su fila)
    assert.match(s1, /borradores<\/div><div class="pulso-grupo-filas"><div class="pulso-cambio"><div class="pulso-fila">Inés Vega · Informe: revisión de literatura <a class="pulso-dir" data-direccion="tarea:T470"[^>]*>tarea:T470<\/a><\/div><div class="pulso-causa"><span class="i" title="correo-trabajo">\u{eb1c}<\/span> correo de Inés<\/div>/u);
    assert.ok(s1.indexOf('>nuevas<') < s1.indexOf('>avanzadas<') && s1.indexOf('>avanzadas<') < s1.indexOf('>cerradas<') && s1.indexOf('>cerradas<') < s1.indexOf('>borradores<'));
    // en seco: marcada; un id que todavía no es una tarea, tenue y sin enlace; uno vacío, nada; la del WhatsApp, su ícono
    assert.match(s2, /^ class="pulso-pasada seco">/);
    assert.match(s2, /<span class="pulso-cuando">14:00–14:25<\/span><span class="pulso-marca">seco<\/span>/);
    assert.match(s2, /<div class="pulso-fila">Nevada: contestarle[^<]*<\/div><div class="pulso-causa"><span class="i" title="whatsapp">\u{eac7}<\/span> WhatsApp de Dani<\/div>/u);
    assert.match(s2, /<span class="pulso-id">HABRIA tarea nueva<\/span> Arcilla/);
    assert.doesNotMatch(s2, /cerradas|borradores|pulso-fallo/, 'un grupo vacío no se muestra');
    // la que no cambió nada: una línea, con lo que llegó de cada fuente
    assert.equal(s3, ' class="pulso-pasada sin-cambios"><div class="pulso-cab"><span class="pulso-icono"><span class="i">\u{eb31}</span></span><span class="pulso-cuando">13:00–13:04</span><span class="pulso-sin">sin cambios</span><span class="pulso-tenue">correo-trabajo 2 · whatsapp 4</span></div></section>');
    assert.match(P.pasada({ ...quieta, fuentes: [{ fuente: 'whatsapp', llegaron: 0, archivados: 0, error: 'se cerró' }] }, HOY), /whatsapp 0<\/span><span class="pulso-falla">falló whatsapp<\/span>/);
    assert.match(s4, /<span class="pulso-marca">noche<\/span>/);
    assert.match(s4, /<span class="i" title="dictado">\u{ea67}<\/span> lo que te dictaste/u);
    // una de antes de la causa: sus cambios, sin causa; una fuente desconocida, un punto
    const sinCausa = P.pasada({ ...seca, tareas: { nuevas: [{ id: 'tarea:T1', linea: 'x' }] } }, HOY);
    assert.match(sinCausa, /<div class="pulso-cambio"><div class="pulso-fila"><a [^>]*>tarea:T1<\/a> x<\/div><\/div>/);
    assert.equal(P.iconoFuente('calendario'), P.iconoFuente(''));
    // una web, como enlace aparte; lo demás que no es dirección, texto
    assert.match(P.enlace('https://mail.google.com/x'), /data-web="https:\/\/mail.google.com\/x"/);
    assert.equal(P.enlace('gmail:r-1'), '<span class="pulso-id">gmail:r-1</span>', 'un tipo que la página no conoce no es enlace');
    assert.equal(P.enlace(''), '');
    // cuando vienen menos que las que hay
    assert.match(P.ventanaPulso({ pasadas: [seca], total: 41, hoy: HOY }).ayuda, /aquí las 1 más nuevas de 41/);
    assert.doesNotMatch(P.ventanaPulso({ pasadas: [{ ...seca, resumen: '<img src=x onerror=alert(1)>' }], hoy: HOY }).cuerpo, /<img/);
    assert.doesNotMatch(P.pasada({ ...seca, tareas: { nuevas: [{ id: '', linea: 'x', por: '<img src=x>' }] } }, HOY), /<img/);
}

// 4. en la página, con el fetch de mentira: leer lo sin ver y, al cerrar, marcar vistas hasta la más nueva que se mostró
{
    const dichos = [];
    const hacer = { ...P.HACER, decir: t => dichos.push(t), ir() {}, web() {}, mundo: () => '' };
    const p = new P.Pulso(hacer, 'pulso', 'pulso');
    responder = () => M;
    assert.equal(await p.leer(), true);
    assert.deepEqual(pedidos.at(-1), { url: '/api/resultados/pulso/visto', metodo: 'GET', cuerpo: undefined });
    assert.match(p.linea(HOY), /pulso 15:00/);
    assert.equal(await p.leer(), false, 'lo mismo otra vez: no cambió');

    // la ventana abierta: lo que llega mientras no cambia lo que se muestra, y al cerrarla quedan vistas hasta la 15:00
    p.abrir();
    const mas = { ...M, total: 5, con_cambios: 4, pasadas: [{ ...nueva, id: '2026-11-18T16:00', termino: '2026-11-18T16:05' }, ...M.pasadas] };
    responder = () => mas;
    assert.equal(await p.leer(), false);
    assert.equal(p.masNueva, '2026-11-18T15:00');
    responder = r => (r.metodo === 'POST' ? { ok: true, visto: { id: r.cuerpo.id, dia: HOY }, movio: true } : mas);
    assert.equal(await p.cerrada(), true);
    assert.deepEqual(pedidos.at(-1), { url: '/api/resultados/pulso/visto', metodo: 'POST', cuerpo: { id: '2026-11-18T15:00' } });
    assert.equal(p.linea(HOY), '', 'vistas: la línea se va');
    // al releer, la que llegó mientras se miraba sigue sin ver
    responder = () => ({ ...M, total: 1, con_cambios: 1, pasadas: [mas.pasadas[0]], visto: { id: '2026-11-18T15:00' } });
    await p.leer();
    assert.match(p.linea(HOY), /pulso 16:00/);
    assert.doesNotMatch(p.linea(HOY), /pulso-mas/);

    // si no se pudo marcar, se dice y la línea queda
    responder = r => (r.metodo === 'POST' ? [{ detail: 'servidor no respondió' }, 502] : M);
    assert.equal(await p.cerrada(), false);
    assert.deepEqual(dichos, ['no quedaron vistas: servidor no respondió']);
    assert.match(p.linea(HOY), /pulso 16:00/);
    // allá contestó que no (la pasada ya no está): también
    responder = r => (r.metodo === 'POST' ? { ok: false, error: 'no hay una pasada 2026-11-18T16:00 en el 2026-11-18' } : M);
    assert.equal(await p.cerrada(), false);
    assert.match(dichos.at(-1), /no hay una pasada/);

    // si no se pudo leer, se sabe por qué y lo que se mostraba queda
    responder = () => new Error('se cortó');
    assert.equal(await p.leer(), false);
    assert.match(p.error, /la API no respondió: se cortó/);
    assert.match(p.linea(HOY), /pulso 16:00/);
    responder = () => ({ ok: false, error: 'servidor no atiende «resultado-sin-ver»' });
    await p.leer();
    assert.equal(p.error, 'servidor no atiende «resultado-sin-ver»');
    responder = () => M;
    await p.leer();
    assert.equal(p.error, '', 'volvió: el error se va');

    // sin nada sin ver no se marca nada
    const vacio = new P.Pulso(hacer, 'pulso');
    const antes = pedidos.length;
    assert.equal(await vacio.cerrada(), true);
    assert.equal(pedidos.length, antes);
    // solo las que no cambiaron nada: no hay línea ni se abre
    responder = () => ({ ...M, total: 1, con_cambios: 0, pasadas: [quieta] });
    await vacio.leer();
    assert.equal(vacio.conCambios, false);
    assert.equal(vacio.linea(HOY), '');
    // la clave va en la ruta, escapada
    const otra = new P.Pulso(hacer, 'mi pulso');
    responder = () => ({ ok: true, total: 0, pasadas: [] });
    await otra.leer();
    assert.equal(pedidos.at(-1).url, '/api/resultados/mi%20pulso/visto');
}

// 5. con un mundo puesto: solo lo de ese mundo y lo sin clasificar; las cuentas, de lo que se ve
{
    const conMundo = mundo => ({ ...P.delMundo(M, mundo), nombre: 'pulso', hoy: HOY, mundo });
    // trabajo: la de las 15:00 sin lo personal, la seca entera, la que no cambió nada; la de anoche (solo personal), ni
    // aparece ni cuenta
    const t = conMundo('trabajo');
    assert.deepEqual(t.pasadas.map(p => p.id), ['2026-11-18T15:00', '2026-11-18T14:00', '2026-11-18T13:00']);
    assert.equal(t.cambios, 2);
    assert.equal(texto(P.linea(t)), 'pulso 15:00 · 1 nueva · 1 avanzada · 1 cerrada · 1 borrador · falló whatsapp', 'lo sin clasificar (whatsapp) también');
    assert.match(P.linea(t), /<span class="pulso-mas">\+1<\/span>/);
    const vt = P.ventanaPulso(t);
    assert.equal(vt.titulo, 'pulso · trabajo · 2 pasadas con cambios');
    assert.equal(vt.ayuda, 'visto hasta ayer 22:00 · al cerrar, queda visto lo de trabajo y lo sin clasificar');
    assert.doesNotMatch(vt.cuerpo, /T588|T579|riego|vivero|correo-personal|gasfíter|dictaste/, 'nada personal');
    // los resúmenes: el de trabajo, sin su nombre (es el puesto), y no el neutro (cuenta lo de los dos: las cuentas son las
    // de la línea); el de la seca (de antes, sin `resumenes`), porque no trae nada de otro mundo
    const [t1, t2, t3] = vt.cuerpo.split('<section').slice(1);
    assert.deepEqual([...t1.matchAll(/<div class="pulso-resumen">(.*?)<\/div>/g)].map(m => m[1]),
        ['Llegó la confirmación de Arcilla para el jueves y una pregunta de Molino; dejé un borrador a Inés.']);
    assert.match(t2, /<div class="pulso-resumen">Seco: habría creado/);
    assert.match(t3, /sin cambios<\/span><span class="pulso-tenue">correo-trabajo 2 · whatsapp 4</);
    assert.doesNotMatch(P.linea(t), /riego/, 'tampoco en la ayuda de la línea');

    // personal: la de las 15:00 con lo suyo, la que no cambió nada (sin clasificar) y la de anoche; la seca, que solo
    // trajo cambios de trabajo, no
    const p = conMundo('personal');
    assert.deepEqual(p.pasadas.map(x => x.id), ['2026-11-18T15:00', '2026-11-18T13:00', '2026-11-17T23:30']);
    assert.equal(p.cambios, 2);
    assert.equal(texto(P.linea(p)), 'pulso 15:00 · 1 avanzada · falló whatsapp');
    const vp = P.ventanaPulso(p);
    assert.doesNotMatch(vp.cuerpo, /Arcilla|Molino|T540|T580|T512|Inés|Carla|Seco: habría/, 'nada de trabajo');
    assert.match(vp.cuerpo, /data-direccion="tarea:T588"/);
    assert.match(vp.cuerpo, /Llegó la cotización del riego/);
    assert.match(vp.cuerpo, /sin cambios<\/span><span class="pulso-tenue">whatsapp 4</, 'de la que no cambió nada, lo que llegó de lo que se ve');

    // ambos: todo, y el resumen de cada mundo con su nombre en su color
    const a = { ...P.delMundo(M, ''), nombre: 'pulso', hoy: HOY, mundo: '', colores: { trabajo: 'cian', personal: 'magenta' } };
    assert.equal(a.pasadas.length, 4);
    assert.equal(a.cambios, 3);
    assert.equal(texto(P.linea(a)), 'pulso 15:00 · 1 nueva · 2 avanzadas · 1 cerrada · 1 borrador · falló whatsapp');
    const va = P.ventanaPulso(a);
    assert.equal(va.titulo, 'pulso · 3 pasadas con cambios');
    assert.match(va.cuerpo, /<div class="pulso-resumen">1 nueva, 2 avanzadas, 1 cerrada, 1 borrador. WhatsApp no respondió.<\/div><div class="pulso-resumen"><span class="pulso-mundo" style="--mundo-c: var\(--cian\)">trabajo<\/span> Llegó la confirmación/, 'el neutro, y después el de cada mundo');
    assert.match(va.cuerpo, /<span class="pulso-mundo" style="--mundo-c: var\(--magenta\)">personal<\/span> Llegó la cotización/);
    assert.match(P.linea(a), /title="[^"]*\npersonal: Llegó la cotización/, 'en la ayuda de la línea, con su nombre');

    // una de antes que nombra lo de los dos, sin `resumenes`: con un mundo, solo las cuentas; con ambos, el resumen. Lo que
    // te espera de otro mundo también cuenta: el resumen pudo nombrarlo
    const vieja = { id: '2026-11-18T13:00', resumen: 'Carla confirmó; Luis pidió el auto', mundos: ['trabajo', 'personal', ''], sin_ver_en: ['trabajo', ''],
        tareas: { nuevas: [{ id: 'tarea:T1', linea: 'x', mundo: 'trabajo' }] }, te_esperan: [{ id: 'tarea:T2', linea: 'y', mundo: 'personal' }] };
    assert.equal(P.paraMundo(vieja, 'trabajo').resumen, '');
    assert.equal(P.paraMundo(vieja, '').resumen, vieja.resumen);
    assert.doesNotMatch(P.pasada(P.paraMundo(vieja, 'trabajo'), HOY), /Luis/);
    // sin los mundos dichos (de un telar de antes), los saca de sus cosas
    assert.equal(P.paraMundo({ ...vieja, mundos: undefined }, 'trabajo').resumen, '');
    assert.equal(P.paraMundo({ ...vieja, mundos: undefined, te_esperan: [] }, 'trabajo').resumen, vieja.resumen);
    // lo sin clasificar que ya se vio (con otro mundo) no vuelve; lo de ese mundo sin ver, sí
    const mixta = { id: '2026-11-18T12:00', sin_ver_en: ['personal'], mundos_cambios: ['trabajo', 'personal', ''],
        tareas: { nuevas: [{ id: 'a', linea: 'a', mundo: '' }, { id: 'b', linea: 'b', mundo: 'personal' }, { id: 'c', linea: 'c', mundo: 'trabajo' }] } };
    assert.deepEqual(P.paraMundo(mixta, 'personal').tareas.nuevas.map(x => x.id), ['b']);
    assert.deepEqual(P.paraMundo(mixta, '').tareas.nuevas.map(x => x.id), ['b']);
    assert.deepEqual(P.paraMundo({ ...mixta, sin_ver_en: ['personal', ''] }, 'personal').tareas.nuevas.map(x => x.id), ['a', 'b']);
    // de un telar de antes, sin `sin_ver_en` ni mundos: se ve con cualquiera, entera
    assert.equal(P.delMundo({ ok: true, total: 1, pasadas: [{ id: 'x', resumen: 'r' }] }, 'trabajo').pasadas[0].resumen, 'r');
    // lo visto que se dice es el más nuevo: el de ambos o el del mundo puesto
    const vistos = { ...M, visto: { id: '2026-11-18T09:00' }, vistos: { trabajo: { id: '2026-11-18T12:00' } } };
    assert.equal(P.delMundo(vistos, 'trabajo').visto.id, '2026-11-18T12:00');
    assert.equal(P.delMundo(vistos, 'personal').visto.id, '2026-11-18T09:00');
}

// 6. lo visto por mundo: cerrar con trabajo marca lo de trabajo; lo personal de esas pasadas sigue hasta mirarlo con personal
{
    let mundo = 'trabajo';
    const hacer = { ...P.HACER, decir() {}, ir() {}, web() {}, mundo: () => mundo };
    const p = new P.Pulso(hacer, 'pulso', 'pulso');
    responder = () => M;
    await p.leer();
    assert.match(p.linea(HOY), /pulso 15:00.*\+1/s);
    // se abre con trabajo y, mientras está abierta, el horario pasa a personal: se marca con trabajo, lo que se miró
    p.abrir();
    mundo = 'personal';
    assert.equal(p.ventana(HOY).titulo, 'pulso · trabajo · 2 pasadas con cambios');
    responder = r => (r.metodo === 'POST'
        ? { ok: true, visto: M.visto, vistos: { trabajo: { id: r.cuerpo.id }, '': { id: r.cuerpo.id } }, movio: true, mundo: r.cuerpo.mundo } : M);
    assert.equal(await p.cerrada(), true);
    assert.deepEqual(pedidos.at(-1), { url: '/api/resultados/pulso/visto', metodo: 'POST', cuerpo: { id: '2026-11-18T15:00', mundo: 'trabajo' } });
    // con trabajo ya no hay nada; con personal, lo personal de las 15:00 y la de anoche (la que no cambió nada ya se vio)
    mundo = 'trabajo';
    assert.equal(p.linea(HOY), '');
    mundo = 'personal';
    assert.deepEqual(p.vista().pasadas.map(x => x.id), ['2026-11-18T15:00', '2026-11-17T23:30']);
    assert.equal(p.vista().cambios, 2);
    assert.match(p.linea(HOY), /pulso 15:00.*1 avanzada.*\+1/s);
    assert.deepEqual([p.datos.por_mundo, p.datos.con_cambios], [{ trabajo: 0, personal: 2 }, 2]);
    // con ambos, de esas pasadas solo lo que falta ver (lo personal), sin el resumen neutro (contaba también lo ya visto)
    mundo = '';
    const [a1] = p.ventana(HOY).cuerpo.split('<section').slice(1);
    assert.doesNotMatch(a1, /T580|T540|T512|Inés|Arcilla|1 nueva, 2 avanzadas/);
    assert.match(a1, /tarea:T588/);
    assert.match(a1, /<span class="pulso-mundo">personal<\/span> Llegó la cotización/);
    assert.equal(texto(p.linea(HOY)), 'pulso 15:00 · 1 avanzada · falló whatsapp');
    mundo = 'personal';
    // cerrar con personal: no queda nada
    responder = r => (r.metodo === 'POST' ? { ok: true, movio: true } : M);
    assert.equal(await p.cerrada(), true);
    assert.deepEqual(pedidos.at(-1).cuerpo, { id: '2026-11-18T15:00', mundo: 'personal' });
    assert.equal(p.linea(HOY), '');
    assert.deepEqual([p.datos.total, p.datos.con_cambios], [0, 0]);
    // con ambos, todo: lo marca sin mundo
    mundo = '';
    await p.leer();
    assert.equal(p.vista().cambios, 3);
    responder = r => (r.metodo === 'POST' ? { ok: true, visto: { id: r.cuerpo.id }, movio: true } : M);
    assert.equal(await p.cerrada(), true);
    assert.deepEqual(pedidos.at(-1).cuerpo, { id: '2026-11-18T15:00' });
    for (mundo of ['', 'trabajo', 'personal']) assert.equal(p.linea(HOY), '', mundo);
    // lo que no trae nada del mundo puesto no se marca: sin nada que ver con trabajo, cerrar no pide nada
    responder = () => ({ ...M, total: 1, con_cambios: 1, por_mundo: { trabajo: 0, personal: 1 }, pasadas: [noche] });
    mundo = 'trabajo';
    await p.leer();
    assert.equal(p.linea(HOY), '');
    const antes = pedidos.length;
    assert.equal(await p.cerrada(), true);
    assert.equal(pedidos.length, antes);
    // al releer, un cambio solo de dónde falta ver (otra página marcó trabajo) también cuenta como cambio
    responder = () => M;
    await p.leer();
    responder = () => ({ ...M, pasadas: M.pasadas.map(x => ({ ...x, sin_ver_en: x.sin_ver_en.filter(k => k === 'personal') })) });
    assert.equal(await p.leer(), true);
    assert.equal(p.linea(HOY), '');
}

console.log('pulso: la línea, la ventana, lo visto y los mundos, bien');
