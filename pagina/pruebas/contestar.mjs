// Prueba de la ventana de contestar (src/componentes/contestar.ts y src/web/contestar.ts): cómo se arma cada clase de
// espera (sus opciones, lo que hará cada una, «Otra cosa…», conversarlo o ir al hilo), cuándo se puede mandar y con qué
// verbo, qué se manda (la elección, la respuesta en vivo) y adónde va cada cosa por la API (con un fetch de mentira:
// nada sale); y su ficha (src/componentes/ficha-contestar.ts): de qué se trata, cómo llegamos aquí, qué está en juego y
// qué hay relacionado, y lo que se lee para armarla. Con las esperas de mentira del catálogo y del ensayo
// (componentes/muestras-contestar.ts).
// Corre en Node: npm run prueba:contestar
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const dir = mkdtempSync(path.join(tmpdir(), 'contestar-'));
const entrada = path.join(dir, 'entrada.ts');
const { writeFileSync } = await import('node:fs');
const src = path.join(aqui, '..', 'src');
writeFileSync(entrada, [
    `export * from ${JSON.stringify(path.join(src, 'componentes', 'contestar.ts'))};`,
    `export { esperasDeMuestra, detallesDeMuestra, fichaDeMuestra } from ${JSON.stringify(path.join(src, 'componentes', 'muestras-contestar.ts'))};`,
    `export { fichaDeTarea, fichaDePregunta, fichaHtml, hito, conexion, cuantoFalta, rutaCorta, estadoDeProyecto, otrasDelProyecto, HITOS_A_LA_VISTA } from ${JSON.stringify(path.join(src, 'componentes', 'ficha-contestar.ts'))};`,
    `export { HACER, alAgenteDe, descartarRetenidos, hacerDeEnsayo, quienPregunto, respuestasEnVivo } from ${JSON.stringify(path.join(src, 'web', 'contestar.ts'))};`,
    `export { enLinea, parrafos as parrafosEnLinea } from ${JSON.stringify(path.join(src, 'componentes', 'en-linea.ts'))};`,
].join('\n'));
const salida = path.join(dir, 'contestar.cjs');
await build({ entryPoints: [entrada], bundle: true, platform: 'node', format: 'cjs', outfile: salida, logLevel: 'warning' });
// lo de la página que se toca al cargar (web/guardado.ts escucha `pagehide` y `visibilitychange`): lo justo, sin DOM
globalThis.window ??= { addEventListener() {} };
globalThis.document ??= { addEventListener() {}, visibilityState: "visible" };
const C = require(salida);

const AHORA = Date.parse('2026-11-17T12:00:00');
const M = C.esperasDeMuestra(AHORA);
const elegir = (c, s, b, id) => ({ ...s, elegidas: s.elegidas.map((x, i) => (i === b ? [id] : x)) });
const escribir = (s, b, t) => ({ ...s, otras: s.otras.map((x, i) => (i === b ? t : x)) });

// 1. la pregunta de un módulo: sus opciones con la recomendada y lo que hará cada una; «Otra cosa…»; conversarlo
{
    const c = C.contestable(M.decide, AHORA);
    assert.equal(c.clase, 'decide');
    assert.equal(c.titulo, '¿Dónde sale la reseña de «El libro de la feria»?');
    assert.match(c.ayuda, /^boletin pregunta · casa · hace 3 d · vence el 24-nov · urgencia media$/);
    // su resumen entero, su porqué y su detalle van a la ficha, a la vista (ya no se pliegan)
    assert.deepEqual(c.detalle, []);
    assert.match(c.ficha.trata.texto, /^La reseña está lista y revisada\. .* que se rehace en diciembre\.$/);
    assert.deepEqual(c.ficha.trata.partes.map(x => x.titulo), ['detalle']);
    assert.match(c.ficha.juego.find(x => x.texto === 'por qué').parrafo, /340 personas/);
    assert.deepEqual(c.ficha.relacion[0].enlace, { texto: 'preguntas/2026-11-14-donde-sale-la-resena.md',
        direccion: 'archivo:casa/preguntas/2026-11-14-donde-sale-la-resena.md', titulo: 'casa/preguntas/2026-11-14-donde-sale-la-resena.md' });
    const [b] = c.bloques;
    assert.deepEqual(b.opciones.map(o => o.id), ['boletin', 'pagina', 'no']);
    assert.equal(b.opciones[0].recomendada, true);
    assert.equal(b.opciones[0].nota, undefined, 'a quién le avisa es igual para todas: no va bajo cada una');
    assert.equal(b.opciones[2].nota, 'corre tarea:T1 completar');
    assert.equal(b.opciones[2].efecto, 'tarea:T1 completar');
    assert.equal(b.otra.nombre, 'Otra cosa…');
    assert.equal(c.conversar, true);
    // conversarlo va de entrada al que preguntó, con el nombre con que lo lista la instrucción
    assert.equal(C.quienPregunto('agente:almacen', ['Cartero', 'Almacén']), 'Almacén');
    assert.equal(C.quienPregunto('agente:boletin', ['Cartero']), 'boletin');
    assert.equal(C.quienPregunto('hilo:Faro', []), 'Faro');
    assert.equal(C.quienPregunto('', ['Almacén']), '');
    // nada elegido: no se manda; una opción, o texto, sí; lo escrito gana sobre la opción en una de una sola
    const s0 = C.estadoInicial(c);
    assert.equal(C.listo(c, s0), false);
    const s1 = elegir(c, s0, 0, 'boletin');
    assert.equal(C.listo(c, s1), true);
    assert.equal(C.verbo(c, s1), 'responder');
    assert.deepEqual(C.eleccion(c, s1), [{ opciones: ['boletin'], texto: '' }]);
    assert.deepEqual(C.eleccion(c, escribir(s1, 0, ' que salga en enero ')), [{ opciones: [], texto: 'que salga en enero' }]);
    // el HTML: la recomendada marcada, lo que hará escrito, la elegida con el círculo del centro, el botón habilitado
    const h = C.ventanaContestar(c, s1);
    assert.match(h, /class="ventana centrada contestar contestar-decide con-ficha"/);
    assert.match(h, /contestar-op si rec" data-bloque="0" data-op="boletin" aria-pressed="true"/);
    assert.match(h, /recomendada/);
    // el texto de una opción, con su código como código (la acción que nombra)
    assert.match(C.ventanaContestar(C.contestable({ ...M.decide, campos: { ...M.decide.campos, opciones: [{ id: 'c', texto: 'Cerrarla `tarea:T1 completar`', accion: 'tarea:T1 completar' }] } }, AHORA)), /Cerrarla <code>tarea:T1 completar<\/code>/);
    assert.match(h, /corre tarea:T1 completar/);
    assert.match(h, /data-contestar="conversar"/);
    assert.match(h, /data-contestar="hacer"(?![^>]*disabled)[^>]*>/, 'con algo elegido, el botón no está apagado');
    assert.match(C.ventanaContestar(c, s0), /data-contestar="hacer"[^>]*disabled/);
    // el código del detalle, como código
    assert.match(h, /la tarea <code>T1<\/code> queda/);
    // un aviso (409) se ve; sin aviso, va escondido
    assert.match(C.ventanaContestar(c, { ...s1, aviso: { tono: 'falla', texto: 'Cambió mientras la mirabas' } }), /contestar-aviso falla" role="status">Cambió/);
    assert.match(h, /contestar-aviso info" role="status" hidden>/);
}

// 2. una tarea que propone cerrarse: cerrarla como propone, o responder; la tarea misma, plegada
{
    const c = C.contestable(M.tarea, AHORA);
    assert.equal(c.clase, 'tarea');
    assert.equal(c.marca, 'propone cerrarla: hecha');
    assert.match(c.resumen, /^Llegaron ayer: 500 bolsas/);
    assert.match(c.ayuda, /^tarea:T12 · compras · P2 · vence el 20-nov · hace 1 d$/);
    // la tarea misma ya no se pliega: va a su ficha, que la lee después de abrir (mientras, lo dice)
    assert.deepEqual(c.detalle, []);
    assert.equal(c.ficha.estado, 'leyendo');
    assert.match(C.ventanaContestar(c), /contestar-tarea con-ficha.*leyendo la tarea…/s);
    const [b] = c.bloques;
    assert.deepEqual(b.opciones.map(o => [o.id, o.texto, o.verbo]), [['cerrar', 'Cerrarla: hecha', 'cerrarla']]);
    assert.equal(b.otra.nombre, 'Otra cosa…');
    const s = C.estadoInicial(c);
    assert.equal(s.abierta, -1, 'con una opción, lo escrito no abre de entrada');
    assert.equal(C.verbo(c, elegir(c, s, 0, 'cerrar')), 'cerrarla');
    assert.equal(C.verbo(c, escribir(s, 0, 'falta la factura')), 'responder');
    // una que pregunta: sin opciones, la respuesta escrita es lo único, y está abierta de entrada
    const p = C.contestable({ ...M.tarea, clase: 'avance:pregunta', campos: { texto: '¿La parto en dos?', version: 'v' } }, AHORA);
    assert.equal(p.marca, 'pregunta');
    assert.deepEqual(p.bloques[0].opciones, []);
    assert.equal(p.bloques[0].otra.nombre, 'tu respuesta');
    assert.equal(C.estadoInicial(p).abierta, 0);
    assert.match(C.ventanaContestar(p), /<textarea class="contestar-campo" data-bloque="0"/);
}

// 3. un retenido: el mensaje entero, tal cual; soltarlo o descartarlo, cada uno con su ícono, su color y su globo;
//    descartarlo pregunta antes (con el foco en «cancelar»: web/contestar.ts) y el botón de abajo va en el rojo de quitar;
//    sin «Otra cosa…»
{
    const c = C.contestable(M.retenido, AHORA);
    assert.equal(c.clase, 'retenido');
    assert.equal(c.literal, true);
    assert.match(c.resumen, /1\. El libro de la feria\n2\. Cuentos/);
    assert.match(c.ayuda, /lo retuvo: cadena de 7 mensajes/);
    const [soltar, descartar] = c.bloques[0].opciones;
    assert.deepEqual(c.bloques[0].opciones.map(o => o.id), ['soltar', 'descartar']);
    assert.equal(c.bloques[0].otra, null);
    assert.deepEqual([soltar.tono, descartar.tono], ['verde', 'rojo'], 'en el color de lo que hace: descartar, el de quitar');
    assert.ok(soltar.icono && descartar.icono && soltar.icono !== descartar.icono, 'cada uno con su ícono');
    assert.match(descartar.ayuda, /no sale nunca.*pide confirmación/);
    assert.match(descartar.nota, /queda anotado como descartado, y a «Vitrina» le llega un aviso de que no se entregó \(no lo despierta\)/);
    assert.equal(soltar.confirmar, undefined, 'soltar no pregunta');
    assert.deepEqual(descartar.confirmar, { pregunta: '¿Descartar el mensaje de «Vitrina» a «Catálogo»?', boton: 'Descartar',
        detalle: 'No sale nunca: queda anotado como descartado, y a «Vitrina» le llega un aviso de que no se entregó (no lo despierta).' });
    // sin nada elegido no se manda; elegido, el botón dice lo que hará
    assert.equal(C.listo(c, C.estadoInicial(c)), false);
    assert.equal(C.verbo(c, C.estadoInicial(c)), 'soltarlo o descartarlo', 'no se responde: se suelta o se descarta');
    assert.equal(C.verbo(c, elegir(c, C.estadoInicial(c), 0, 'soltar')), 'soltarlo');
    assert.equal(C.verbo(c, elegir(c, C.estadoInicial(c), 0, 'descartar')), 'descartarlo');
    // lo que pide confirmación antes: solo descartar, y solo si es lo elegido
    assert.deepEqual(C.porConfirmar(c, elegir(c, C.estadoInicial(c), 0, 'soltar')), []);
    assert.deepEqual(C.porConfirmar(c, elegir(c, C.estadoInicial(c), 0, 'descartar')), [descartar.confirmar]);
    assert.deepEqual(C.porConfirmar(c, C.estadoInicial(c)), []);
    const h = C.ventanaContestar(c);
    assert.match(h, /contestar-literal">Te paso la lista[^<]*\n\n1\. El libro/, 'con sus saltos de línea');
    assert.doesNotMatch(h, /data-otra/);
    // las dos opciones, con su globo y su ícono en su color
    assert.match(h, /data-op="descartar"[^>]*title="descartarlo: no sale nunca[^"]*"[^>]*>.*?<span class="i contestar-icono tono-rojo">/s);
    assert.match(h, /data-op="soltar"[^>]*title="soltarlo: [^"]*"[^>]*>.*?<span class="i contestar-icono tono-verde">/s);
    // el botón de abajo (componentes/boton.ts), en el de peligro y con ⌘⌫ (no ⏎) solo con descartar elegido; cancelar, al último
    const conDescartar = C.ventanaContestar(c, elegir(c, C.estadoInicial(c), 0, 'descartar'));
    assert.match(conDescartar, /class="boton tono-peligro" data-contestar="hacer" data-tecla="⌘⌫"[^>]*>.*descartarlo/s);
    assert.ok(C.quita(c, elegir(c, C.estadoInicial(c), 0, 'descartar')), 'descartar quita');
    const conSoltar = C.ventanaContestar(c, elegir(c, C.estadoInicial(c), 0, 'soltar'));
    assert.doesNotMatch(conSoltar, /tono-peligro[^>]*data-contestar="hacer"/);
    assert.match(conSoltar, /data-contestar="hacer" data-tecla="⏎"/);
    assert.ok(conSoltar.indexOf('data-contestar="hacer"') < conSoltar.indexOf('data-contestar="cancelar"'), 'lo que hace, y cancelar al último');
    // descartar varios (todos los de su grupo en «te esperan»): cuántos y a quiénes les llega el aviso
    const otro = { ...M.retenido, direccion: 'mensaje:m-2', campos: { ...M.retenido.campos, de: 'Catálogo', para: 'Vitrina' } };
    assert.deepEqual(C.descarte([M.retenido, otro, { ...otro, direccion: 'mensaje:m-3' }]), { pregunta: '¿Descartar los 3 mensajes retenidos?',
        detalle: 'No sale ninguno: quedan anotados como descartados, y a quien mandó cada uno («Vitrina», «Catálogo») le llega un aviso de que no se entregó (no lo despierta).' });
}

// 4. la pregunta en vivo: sus opciones con su descripción, otra respuesta, ir al hilo (no conversarlo); varias preguntas
{
    const c = C.contestable(M['en-vivo'], AHORA);
    assert.equal(c.clase, 'en-vivo');
    assert.equal(c.titulo, '¿Qué foto va en la vitrina de diciembre?');
    assert.equal(c.conversar, false);
    assert.deepEqual(c.ir, { direccion: 'hilo:Vitrina', texto: 'ir al hilo' });
    assert.equal(c.bloques[0].encabezado, 'Foto');
    assert.equal(c.bloques[0].opciones[1].nota, 'con gente: hay que pedirles permiso a dos personas');
    const s = elegir(c, C.estadoInicial(c), 0, 'La de la feria');
    assert.deepEqual(C.respuestasEnVivo(M['en-vivo'], c, s), { '¿Qué foto va en la vitrina de diciembre?': 'La de la feria' });
    // dos preguntas, una de varias: cada una con su enunciado; las elegidas con coma y lo escrito al final
    const dos = { ...M['en-vivo'], campos: { hilo: 'Vitrina', pregunta: 'p-2', preguntas: [
        { pregunta: '¿Qué foto?', encabezado: 'Foto', varias: false, opciones: [{ etiqueta: 'Árbol' }, { etiqueta: 'Feria' }] },
        { pregunta: '¿Qué carteles?', encabezado: 'Carteles', varias: true, opciones: [{ etiqueta: 'Precios' }, { etiqueta: 'Autores' }] },
    ] } };
    const c2 = C.contestable(dos, AHORA);
    assert.equal(c2.titulo, '«Vitrina» te pregunta 2 cosas');
    assert.deepEqual(c2.bloques.map(b => [b.enunciado, b.varias]), [['¿Qué foto?', false], ['¿Qué carteles?', true]]);
    let s2 = elegir(c2, C.estadoInicial(c2), 0, 'Feria');
    assert.equal(C.listo(c2, s2), false, 'falta la segunda');
    s2 = { ...s2, elegidas: [['Feria'], ['Precios', 'Autores']], otras: ['', 'y uno de horario'] };
    assert.equal(C.listo(c2, s2), true);
    assert.deepEqual(C.respuestasEnVivo(dos, c2, s2), { '¿Qué foto?': 'Feria', '¿Qué carteles?': 'Precios, Autores, y uno de horario' });
    assert.match(C.ventanaContestar(c2, s2), /elige una o varias/);
    // sin su id (o de otra máquina, sin preguntas) no se contesta aquí: es un permiso
    assert.equal(C.contestable({ ...M['en-vivo'], campos: { ...M['en-vivo'].campos, pregunta: '' } }, AHORA).clase, 'permiso');
}

// 5. un permiso sin pregunta: no se contesta aquí; se dice y se ofrece ir al hilo
{
    const c = C.contestable(M.permiso, AHORA);
    assert.equal(c.clase, 'permiso');
    assert.deepEqual(c.bloques, []);
    assert.equal(c.ir.direccion, 'hilo:Inventario');
    assert.match(c.nota, /se da en la terminal del hilo/);
    const h = C.ventanaContestar(c);
    assert.doesNotMatch(h, /data-contestar="hacer"/);
    assert.match(h, /data-contestar="cancelar" data-tecla="⎋"[^>]*><span class="boton-tecla">⎋<\/span><span class="boton-texto">cerrar</);
    const lejos = C.contestable({ ...M.permiso, direccion: 'permiso:Inventario@servidor', maquina: 'servidor', campos: { hilo: 'Inventario' } }, AHORA);
    assert.match(lejos.nota, /de un hilo de servidor/);
    // lo de otro módulo, que no es una pregunta: se abre donde vive
    const otra = C.contestable({ direccion: 'correo:1a', tipo: 'correo', clase: 'archivar', desde: '', titulo: 'Un correo', resumen: 'hola', enlaces: [] }, AHORA);
    assert.deepEqual([otra.clase, otra.ir.direccion, otra.bloques.length], ['otra', 'correo:1a', 0]);
}

// 6. adónde va cada cosa, por la API (un fetch de mentira que anota y responde)
{
    const pedidos = [];
    let responde = () => ({ status: 200, json: { ok: true } });
    globalThis.fetch = async (url, init) => {
        const cuerpo = init?.body ? JSON.parse(init.body) : undefined;
        pedidos.push({ url, metodo: init?.method ?? 'GET', cuerpo });
        const r = responde(url);
        return { ok: r.status < 400, status: r.status, json: async () => r.json };
    };
    const mandar = async (e, s) => { const c = C.contestable(e, AHORA); return await C.HACER.contestar(e, c, s(c, C.estadoInicial(c))); };

    let r = await mandar(M.decide, (c, s) => elegir(c, s, 0, 'boletin'));
    assert.equal(r.ok, true);
    assert.deepEqual(pedidos.at(-1), { url: '/api/objetos/pregunta:casa/2026-11-14-donde-sale-la-resena/acciones/responder', metodo: 'POST',
        cuerpo: { params: { opcion: 'boletin' }, version: 'a1b2c3' } });
    await mandar(M.decide, (c, s) => escribir(s, 0, 'en enero'));
    assert.deepEqual(pedidos.at(-1).cuerpo, { params: { texto: 'en enero' }, version: 'a1b2c3' });

    await mandar(M.tarea, (c, s) => elegir(c, s, 0, 'cerrar'));
    assert.deepEqual(pedidos.at(-1), { url: '/api/objetos/tarea:T12/acciones/cerrar', metodo: 'POST', cuerpo: { params: { como: 'hecha', nota: '' }, version: 'v1' } });
    await mandar(M.tarea, (c, s) => escribir(s, 0, 'la cierro yo'));
    assert.deepEqual(pedidos.at(-1), { url: '/api/objetos/tarea:T12/acciones/responder', metodo: 'POST', cuerpo: { params: { texto: 'la cierro yo' }, version: 'v1' } });

    await mandar(M.retenido, (c, s) => elegir(c, s, 0, 'soltar'));
    assert.deepEqual(pedidos.at(-1), { url: '/api/mensajes/m-7f3a/soltar', metodo: 'POST', cuerpo: undefined });
    // descartarlo: a su ruta, y se dice si a quien lo mandó le llegó el aviso
    responde = () => ({ status: 200, json: { id: 'm-7f3a', de: 'Vitrina', para: 'Catálogo', estado: 'descartado', aviso: 'a-1' } });
    r = await mandar(M.retenido, (c, s) => elegir(c, s, 0, 'descartar'));
    assert.deepEqual(pedidos.at(-1), { url: '/api/mensajes/m-7f3a/descartar', metodo: 'POST', cuerpo: undefined });
    assert.deepEqual(r, { ok: true, dice: 'descartado: no va a «Catálogo»; a «Vitrina» le llegó un aviso' });
    responde = () => ({ status: 200, json: { id: 'm-7f3a', de: 'Vitrina', para: 'Catálogo', estado: 'descartado', sin_aviso: 'el bus no respondió' } });
    r = await mandar(M.retenido, (c, s) => elegir(c, s, 0, 'descartar'));
    assert.equal(r.dice, 'descartado: no va a «Catálogo»; a «Vitrina» no le llegó el aviso (el bus no respondió)');
    // ya no está (lo soltaron o descartaron en otro lado): no se hizo, y se dice por qué
    responde = () => ({ status: 404, json: { detail: 'no hay un mensaje retenido con id m-7f3a (¿ya se soltó o se descartó?)' } });
    r = await mandar(M.retenido, (c, s) => elegir(c, s, 0, 'descartar'));
    assert.deepEqual([r.ok, /ya se soltó o se descartó/.test(r.error)], [false, true]);
    // varios (los de su grupo en «te esperan»): uno tras otro; si uno falla, los demás siguen, y se dice cuántos
    const dos = { ...M.retenido, direccion: 'mensaje:m-2', campos: { ...M.retenido.campos, de: 'Catálogo' } };
    const tres = { ...M.retenido, direccion: 'mensaje:m-3' };
    responde = (url) => (url.includes('m-2') ? { status: 502, json: { detail: 'el bus no responde' } }
        : { status: 200, json: { id: 'x', de: 'Vitrina', para: 'Catálogo', estado: 'descartado', aviso: 'a' } });
    const antesVarios = pedidos.length;
    const v = await C.descartarRetenidos([M.retenido, dos, tres]);
    assert.deepEqual(pedidos.slice(antesVarios).map(x => x.url), ['/api/mensajes/m-7f3a/descartar', '/api/mensajes/m-2/descartar', '/api/mensajes/m-3/descartar']);
    assert.deepEqual(v, { hechos: ['mensaje:m-7f3a', 'mensaje:m-3'], dice: '2 descartados; a quien los mandó le llegó un aviso',
        falla: '1 no se pudo descartar: el bus no responde' });
    responde = () => ({ status: 200, json: { ok: true } });

    responde = () => ({ status: 200, json: { ok: true, tomada: true } });
    r = await mandar(M['en-vivo'], (c, s) => elegir(c, s, 0, 'La de la feria'));
    assert.equal(r.ok, true);
    assert.deepEqual(pedidos.at(-1), { url: '/api/hilos/responder', metodo: 'POST',
        cuerpo: { hilo: 'Vitrina', maquina: '', id: 'p-1', respuestas: { '¿Qué foto va en la vitrina de diciembre?': 'La de la feria' } } });
    // el agente no la tomó todavía: no se da por hecha
    responde = () => ({ status: 200, json: { ok: true, tomada: false } });
    r = await mandar(M['en-vivo'], (c, s) => elegir(c, s, 0, 'La de la feria'));
    assert.deepEqual([r.ok, /quedó en camino/.test(r.error)], [false, true]);
    // ya la contestaron en la terminal: hecho, y se dice
    responde = () => ({ status: 200, json: { ok: true, tomada: false, por: 'terminal' } });
    r = await mandar(M['en-vivo'], (c, s) => elegir(c, s, 0, 'La de la feria'));
    assert.deepEqual([r.ok, r.dice], [true, 'ya la habían contestado en la terminal']);

    // cambió desde que se leyó: 409, y se dice que cambió (la ventana relee)
    responde = () => ({ status: 409, json: { detail: 'la pregunta cambió desde que la leíste' } });
    r = await mandar(M.decide, (c, s) => elegir(c, s, 0, 'boletin'));
    assert.deepEqual(r, { ok: false, error: 'la pregunta cambió desde que la leíste', cambio: true });
    // otra falla: no es un cambio
    responde = () => ({ status: 502, json: { detail: 'el módulo se cayó' } });
    r = await mandar(M.tarea, (c, s) => elegir(c, s, 0, 'cerrar'));
    assert.deepEqual(r, { ok: false, error: 'el módulo se cayó', cambio: false });

    // releer: las esperas de ese tipo; la misma si sigue, null si ya no espera
    responde = () => ({ status: 200, json: { esperas: [M.decide], fallas: {} } });
    assert.equal((await C.HACER.releer(M.decide)).direccion, M.decide.direccion);
    assert.equal(pedidos.at(-1).url, '/api/esperas?tipo=pregunta');
    responde = () => ({ status: 200, json: { esperas: [], fallas: {} } });
    assert.equal(await C.HACER.releer(M.decide), null);
    responde = () => ({ status: 502, json: { detail: 'sin servidor' } });
    assert.equal(await C.HACER.releer(M.decide), undefined);

    // lo que declara el agente: una opción de decidir se contesta con su texto; de aprobar, enviar o «editar: …»
    responde = () => ({ status: 200, json: { ok: true } });
    const avance = (texto) => ({ ...M.tarea, clase: 'avance:preparado', campos: { ...M.tarea.campos, como: undefined, texto } });
    await mandar(avance('pide=decidir · opciones=el 12% | un 8%* · falta: ¿cuál?'), (c, s) => elegir(c, s, 0, 'un 8%'));
    assert.deepEqual(pedidos.at(-1).cuerpo, { params: { texto: 'un 8%' }, version: 'v1' });
    await mandar(avance('pide=aprobar · falta: el boletín'), (c, s) => elegir(c, s, 0, C.APROBAR.enviar));
    assert.deepEqual(pedidos.at(-1).cuerpo, { params: { texto: 'aprobado: envíalo' }, version: 'v1' });
    await mandar(avance('pide=aprobar · falta: el boletín'), (c, s) => escribir(s, 0, 'sin la tercera reseña'));
    assert.deepEqual(pedidos.at(-1).cuerpo, { params: { texto: 'editar: sin la tercera reseña' }, version: 'v1' });

    // para el agente: cada línea, una [respuesta] de la tarea (sin versión); con «prompt:», un aviso al agente, con la
    // dirección de la tarea; si no se sabe quién la propuso, el que escribe los avances (de la configuración)
    responde = (url) => (url === '/api/config' ? { status: 200, json: { agente_general: { clave: 'avances', nombre: 'Avances' } } } : { status: 200, json: { ok: true } });
    const c = C.contestable(M.tarea, AHORA);
    const hecho = { lineas: 0, mensaje: false };
    const antes = pedidos.length;
    r = await C.HACER.alAgente(M.tarea, c, ['prompt: pide la factura', 'meta: el número en el resumen'], hecho);
    assert.equal(r.ok, true);
    assert.match(r.dice, /las notas quedaron en la tarea para Avances, con un aviso para que lo atienda ya/);
    const nuevos = pedidos.slice(antes).filter(x => x.url !== '/api/config');
    assert.deepEqual(nuevos.map(x => [x.url, x.cuerpo]), [
        ['/api/objetos/tarea:T12/acciones/responder', { params: { texto: 'prompt: pide la factura' } }],
        ['/api/objetos/tarea:T12/acciones/responder', { params: { texto: 'meta: el número en el resumen' } }],
        ['/api/mensajes', { para: 'Avances', texto: 'tarea:T12 · prompt: pide la factura', tipo: 'persona', de: '' }],
    ]);
    // el que la propuso, si se sabe; sin «prompt:», sin aviso
    const propuesta = C.contestable({ ...M.tarea, campos: { ...M.tarea.campos, de: 'agente:compras' } }, AHORA);
    const n0 = pedidos.length;
    r = await C.HACER.alAgente(M.tarea, propuesta, ['instrucción: pide la factura'], { lineas: 0, mensaje: false });
    assert.equal(r.dice, 'la nota quedó en la tarea para compras');
    assert.ok(!pedidos.slice(n0).some(x => x.url === '/api/mensajes'));
    // si falla a medias, lo hecho no se repite: la segunda vez, solo lo que faltaba
    let fallar = true;
    responde = (url) => (url === '/api/mensajes' && fallar ? { status: 502, json: { detail: 'sin bus' } } : { status: 200, json: { ok: true } });
    const parcial = { lineas: 0, mensaje: false };
    r = await C.HACER.alAgente(M.tarea, propuesta, ['prompt: ya'], parcial);
    assert.deepEqual([r.ok, /quedó en la tarea, pero el aviso a compras no salió: sin bus/.test(r.error), parcial], [false, true, { lineas: 1, mensaje: false }]);
    fallar = false;
    const n1 = pedidos.length;
    r = await C.HACER.alAgente(M.tarea, propuesta, ['prompt: ya'], parcial);
    assert.deepEqual([r.ok, pedidos.slice(n1).map(x => x.url)], [true, ['/api/mensajes']], 'solo el aviso que faltaba');
    // «revisar ya» de Táctica va por el mismo camino, solo con la dirección: su prompt queda en la tarea y le llega al que
    // escribe los avances
    responde = (url) => (url === '/api/config' ? { status: 200, json: { agente_general: { clave: 'avances', nombre: 'Avances' } } } : { status: 200, json: { ok: true } });
    const n2 = pedidos.length;
    r = await C.alAgenteDe('tarea:T12', ['prompt: revisar ya: te contesté'], { lineas: 0, mensaje: false });
    assert.equal(r.ok, true);
    assert.deepEqual(pedidos.slice(n2).filter(x => x.url !== '/api/config').map(x => [x.url, x.cuerpo]), [
        ['/api/objetos/tarea:T12/acciones/responder', { params: { texto: 'prompt: revisar ya: te contesté' } }],
        ['/api/mensajes', { para: 'Avances', texto: 'tarea:T12 · prompt: revisar ya: te contesté', tipo: 'persona', de: '' }],
    ]);
}

// 7. para el agente (prototipo): lo que se le deja, con su marca, y a quién le llega; solo si el estado lo trae
{
    const c = C.contestable(M.tarea, AHORA);
    assert.deepEqual(c.agente, { a: '', propuso: false }, 'sin saber quién la propuso');
    assert.equal(C.aQuien(c.agente), 'al agente que escribe los avances');
    const conDe = C.contestable({ ...M.tarea, campos: { ...M.tarea.campos, de: 'agente:compras' } }, AHORA);
    assert.equal(C.aQuien(conDe.agente), 'a compras (la propuso)');
    assert.deepEqual(C.MARCAS_AGENTE, { revision: 'instrucción', ya: 'prompt', meta: 'meta' });
    const p = { cuando: 'revision', nota: ' pide la factura ', meta: '', abierto: true };
    assert.deepEqual(C.lineasAgente(p), ['instrucción: pide la factura']);
    assert.deepEqual(C.lineasAgente({ ...p, cuando: 'ya', meta: 'pon el número de factura' }), ['prompt: pide la factura', 'meta: pon el número de factura']);
    assert.deepEqual(C.lineasAgente({ ...p, nota: '  ' }), [], 'vacías, nada');
    assert.deepEqual(C.lineasAgente(undefined), []);
    assert.ok(!C.ventanaContestar(c).includes('contestar-agente'), 'sin el estado, no se ofrece (lo pone quien la abre, si el que la manda sabe dejárselo al agente)');
    const html = C.ventanaContestar(c, { ...C.estadoInicial(c), agente: { ...p, cuando: 'ya' } });
    assert.match(html, /<details class="contestar-agente" open>.*para el agente · 1 nota.*llega al agente que escribe los avances/s);
    assert.match(html, /data-agente-cuando="ya" aria-pressed="true"/, 'hazte cargo ya, elegido');
    assert.match(html, /<textarea class="contestar-agente-campo" data-agente="nota"[^>]*> pide la factura <\/textarea>/);
    assert.ok(!C.ventanaContestar(C.contestable(M.decide, AHORA), { ...C.estadoInicial(C.contestable(M.decide, AHORA)) }).includes('contestar-agente'));
    assert.equal(C.contestable(M.decide, AHORA).agente, undefined, 'una pregunta del módulo no lo lleva: no es una tarea');
}

// 8. lo que declara el agente, en la ventana: lo que propone sin lo declarado delante; de decidir, sus opciones con la
// recomendada; de aprobar, enviar, descartar y «Editar…»; de lo que pide hacer, «Hecho»; y solo lo del agente también se manda
{
    const av = (texto) => C.contestable({ ...M.tarea, clase: 'avance:preparado', campos: { ...M.tarea.campos, como: undefined, texto } }, AHORA);
    const dec = av('pide=decidir · peso=alto (x) · opciones=el 12% | un 8%* · falta: ¿cuál?');
    assert.equal(dec.resumen, 'falta: ¿cuál?', 'sin lo declarado delante');
    assert.equal(dec.marca, 'decide');
    assert.deepEqual(dec.bloques[0].opciones.map(o => [o.id, !!o.recomendada, o.nota]), [['el 12%', false, undefined], ['un 8%', true, undefined]], 'sin nota repetida');
    const ap = av('pide=aprobar · falta: el boletín');
    assert.deepEqual([ap.bloques[0].opciones.map(o => o.id), ap.bloques[0].otra.nombre, ap.prefijoOtra], [['aprobado: envíalo', 'descartado: no va'], 'Editar…', 'editar: ']);
    assert.equal(C.verbo(ap, { ...C.estadoInicial(ap), elegidas: [['descartado: no va']] }), 'descartar');
    assert.deepEqual(av('pide=hacer-tu · falta: firmarla').bloques[0].opciones.map(o => o.id), ['hecho: ya lo hice']);
    assert.deepEqual(av('falta: ¿la mando?').bloques[0].opciones, [], 'sin nada declarado, como antes: la respuesta escrita');
    // pide=cerrar en otra marca: cerrarla como dice su texto
    const ce = av('pide=cerrar · Cerrar como caduca: nadie la pidió');
    assert.deepEqual(ce.bloques[0].opciones.map(o => [o.id, o.texto]), [['cerrar', 'Cerrarla: caducó']]);
    assert.equal(C.comoCierre({ ...M.tarea, campos: { texto: 'pide=cerrar · como descartada' } }), 'descartada');
    assert.equal(C.comoCierre(M.tarea), 'hecha', 'el de su avance, primero');
    // solo lo del agente, sin contestar nada más: también se manda, y el botón lo dice
    const s = { ...C.estadoInicial(ap), agente: { cuando: 'revision', nota: 'mírala el lunes', meta: '', abierto: true } };
    assert.deepEqual([C.listo(ap, s), C.hayQueMandar(ap, s), C.verbo(ap, s)], [false, true, 'dejárselo']);
    assert.equal(C.hayQueMandar(ap, C.estadoInicial(ap)), false);
    assert.equal(C.aQuien({ a: 'Avances', propuso: false, general: true }), 'a Avances (escribe los avances)');
}

// 9. la ficha de una tarea: las cuatro preguntas, con la tarea entera, su proyecto y las otras del proyecto
{
    const D = C.detallesDeMuestra();
    const leida = (e) => { const d = D[e.direccion]; return { ...e, campos: { ...e.campos, tarea: d.tarea, proyecto_ficha: d.proyecto, otras: d.otras } }; };
    const c = C.contestable(leida(M.decision), AHORA);
    const f = c.ficha;
    assert.equal(f.estado, 'lista');
    // ¿de qué se trata? el contexto entero
    assert.equal(f.trata.escrito, true);
    assert.match(f.trata.texto, /^El Colegio del Valle compra .*\n\nEl colegio está comparando/s);
    // ¿cómo llegamos aquí? cada línea con quién: la reunión que la creó, tú, lo que aplicó el agente, lo que propone
    assert.equal(f.historia.length, 14);
    assert.deepEqual(f.historia.map(x => x.quien), ['reunion', 'nota', 'nota', 'cambio', 'agente', 'persona', 'aplico', 'nota', 'agente',
        'persona', 'aplico', 'cambio', 'nota', 'agente']);
    assert.deepEqual(f.historia[3], { fecha: '2026-10-09', hora: '11:20', quien: 'cambio', que: 'fecha', texto: 'vence 31-oct → 15-nov' });
    assert.deepEqual(f.historia[13].que, 'pregunta');
    assert.equal(f.historia[13].texto, 'el colegio pide 300 ejemplares y un 12% · falta: ¿aceptamos el 12% o contraofertamos un 8%?',
        'sin lo que declara el agente delante ni la fecha con que empieza');
    assert.equal(f.historia[6].texto, 'mandé la cotización al colegio, con precio de lista y entrega en marzo', 'lo que aplicó, sin «apliqué:»');
    // ¿qué está en juego? el peso con su porqué, quién espera (en color), la fecha (no es dura), el tamaño y lo que bloquea
    const j = Object.fromEntries(f.juego.map(x => [x.texto, x]));
    assert.equal(j['peso alto'].nota, 'el pedido más grande del año');
    assert.equal(j['el colegio espera la respuesta'].tono, 'atencion');
    assert.equal(j['vence el 17-nov'].nota, 'hoy · se puede mover');
    assert.ok(j['prioridad 1 · tamaño larga']);
    assert.deepEqual(j.bloquea.enlace, { texto: 'T71', direccion: 'tarea:T71' });
    assert.equal(j.bloquea.nota, 'la cotización se firma cuando se decida el descuento');
    assert.ok(j['depende de'], 'la conexión `depende_de`, en palabras');
    // ¿qué hay relacionado? de dónde salió y dónde se trabaja (enlaces a sus archivos), el proyecto con su estado, las
    // otras abiertas del proyecto (la que vence antes primero; tres a la vista y cuántas más) y sus etiquetas
    const r = Object.fromEntries(f.relacion.map(x => [x.texto, x]));
    assert.deepEqual(r['de dónde salió'].enlace, { texto: 'reuniones/2026-10-02-reunion-plan-lector.md',
        direccion: 'archivo:casa/colegio/reuniones/2026-10-02-reunion-plan-lector.md', titulo: 'casa/colegio/reuniones/2026-10-02-reunion-plan-lector.md' });
    assert.equal(r['dónde se trabaja'].enlace.direccion, 'archivo:casa/colegio/plan-lector.md');
    assert.deepEqual([r.proyecto.enlace.texto, r.proyecto.enlace.direccion, r.proyecto.nota],
        ['Colegio del Valle · Plan lector 2027', 'proyecto:casa/colegio', 'negociando el descuento · desarrollo · hasta el 15-mar']);
    const otras = r['4 tareas abiertas más en el proyecto'];
    assert.deepEqual(otras.lista.map(x => x.direccion), ['tarea:T71', 'tarea:T76', 'tarea:T77']);
    assert.equal(otras.mas, 1);
    assert.ok(r['colegios · ventas']);
    // el HTML: las cuatro, en orden; la creación y las últimas cuatro a la vista, lo del medio plegado con su conteo;
    // los enlaces se abren en la página (como «ir»)
    const h = C.ventanaContestar(c);
    const titulos = [...h.matchAll(/<div class="ficha-titulo">([^<]+)<\/div>/g)].map(m => m[1]);
    assert.deepEqual(titulos, ['De qué se trata', 'Cómo llegamos aquí', 'Qué está en juego', 'Qué hay relacionado']);
    assert.match(h, /<details class="ficha-mas"><summary>.*9 cosas más en el medio<\/summary>/s);
    assert.equal((h.match(/class="ficha-hito /g) ?? []).length, 14);
    assert.ok(h.indexOf('desde la minuta') < h.indexOf('9 cosas más') && h.indexOf('9 cosas más') < h.indexOf('hasta un 8%'), 'la creación, el medio, las últimas');
    assert.match(h, /class="ficha-hito quien-persona">.*?<span class="i">[^<]+<\/span> tú<\/span>/s);
    assert.match(h, /quien-aplico">.*?<span class="ficha-que">aplicó:<\/span> mandé la cotización/s);
    assert.match(h, /<a class="ficha-enlace" data-contestar="ir" data-valor="archivo:casa\/colegio\/reuniones\/2026-10-02-reunion-plan-lector\.md"/);
    assert.match(h, /<a class="ficha-enlace" data-contestar="ir" data-valor="tarea:T71"/);
    assert.match(C.ventanaContestar(c, { ...C.estadoInicial(c), historia: true }), /<details class="ficha-mas" open>/, 'desplegada, sigue así al repintar');
    // las opciones, enteras, a la derecha (lo que se pide)
    assert.deepEqual(c.bloques[0].opciones.map(o => o.texto), ['aceptar el 12%, que deja el margen en 9% y cierra hoy',
        'contraofertar un 8% por 300 ejemplares, con entrega en marzo y la factura a 60 días, como el año pasado',
        'consultarlo con la contadora antes de contestar']);
    assert.match(h, /<div class="contestar-dos"><div class="contestar-ficha">.*<\/div><div class="contestar-pedido">.*contraofertar un 8% por 300 ejemplares, con entrega en marzo y la factura a 60 días, como el año pasado/s);

    // para aprobar: lo que dejó hecho, y la fecha dura (en color) y la de la tarea, que se puede mover
    const a = C.contestable(leida(M.aprobar), AHORA).ficha;
    assert.deepEqual(a.relacion[0], { icono: a.relacion[0].icono, texto: 'lo que dejó hecho', enlace: { texto: 'feria/presupuesto.md',
        direccion: 'archivo:casa/feria/presupuesto.md', titulo: 'casa/feria/presupuesto.md' } });
    const dura = a.juego.find(x => x.texto === 'fecha dura: 19-nov');
    assert.deepEqual([dura.nota, dura.tono], ['en 2 d · no se mueve', 'atencion']);
    assert.equal(a.juego.find(x => x.texto === 'vence el 21-nov').nota, 'en 4 d · se puede mover (la dura no: es externa)');
    assert.equal(a.relacion.find(x => x.texto === 'proyecto').nota, 'reservando el stand · desarrollo · hasta el 14-dic · la reserva cierra el 19-nov');

    // sin contexto escrito: su título y la línea que lo dice; sin estado de proyecto ni otras tareas, también se dice
    const sc = C.contestable(leida(M['sin-contexto']), AHORA);
    assert.deepEqual([sc.ficha.trata.escrito, sc.ficha.trata.texto], [false, 'Inventario: partirlo en dos']);
    const hs = C.ventanaContestar(sc);
    assert.match(hs, /<p>Inventario: partirlo en dos<\/p><p class="ficha-nota">sin contexto escrito<\/p>/);
    assert.match(hs, /sin estado escrito/);
    assert.match(hs, /ninguna otra tarea abierta en el proyecto/);
    assert.doesNotMatch(hs, /ficha-mas/, 'con pocas, todas a la vista');

    // si no se pudo leer la tarea, se dice, con lo que trajo la espera
    const fa = C.contestable({ ...M.decision, campos: { ...M.decision.campos, tarea_falla: 'el servidor no contestó' } }, AHORA);
    assert.equal(fa.ficha.estado, 'falla');
    assert.match(C.ventanaContestar(fa), /No pude leer la tarea entera: el servidor no contestó\./);
    assert.ok(fa.ficha.juego.some(x => x.texto === 'peso alto'), 'lo que declaró el agente se ve igual');

    // las piezas
    assert.deepEqual(C.conexion('- `bloquea` [T276](T276.md) · la versión final recoge lo decidido'), { tipo: 'bloquea', id: 'T276', porque: 'la versión final recoge lo decidido' });
    assert.equal(C.conexion('una línea cualquiera'), null);
    assert.equal(C.cuantoFalta('2026-11-17', AHORA), 'hoy');
    assert.equal(C.cuantoFalta('2026-10-31', AHORA), 'hace 17 d');
    assert.equal(C.rutaCorta('casa/colegio/reuniones/minuta.md'), 'reuniones/minuta.md');
    assert.equal(C.estadoDeProyecto({ ruta: 'x', nombre: 'X', estado: '', estado_completo: '', plazo: null }), 'sin estado escrito');
    assert.deepEqual(C.hito({ fecha: '2026-11-17', hora: '11:33', tipo: 'nota', texto: '17-nov, triage: propongo esperar' }).texto, 'triage: propongo esperar',
        'sin la fecha con que empieza');
    assert.equal(C.hito({ fecha: '2026-09-08', tipo: 'creada', texto: 'a mano' }, 'casa/reuniones/2026-09-07.md').quien, 'reunion', 'de una minuta');
    assert.equal(C.hito({ fecha: '2026-09-08', tipo: 'creada', texto: 'desde whatsapp' }).quien, 'creada');
    assert.equal(C.hito({ fecha: '2026-09-08', tipo: 'creada', texto: 'desde whatsapp' }, 'casa/reuniones/2026-09-15.md').quien, 'creada',
        'lo que dice su línea gana sobre la carpeta de su origen');
}

// 10. lo que se lee después de abrirla: la tarea entera primero (parcial), y después su proyecto y las otras del proyecto
{
    const D = C.detallesDeMuestra();
    const pedidos = [];
    let falla = false;
    globalThis.fetch = async (url) => {
        pedidos.push(url);
        const r = falla ? { status: 502, json: { detail: 'sin servidor' } }
            : url.startsWith('/api/tipos/tarea/T12') ? { status: 200, json: D['tarea:T12'].tarea }
            : url.startsWith('/api/proyectos') ? { status: 200, json: { raiz: '/x', proyectos: [D['tarea:T12'].proyecto] } }
            : url.startsWith('/api/tipos/tarea?proyecto=') ? { status: 200, json: { tareas: D['tarea:T12'].otras, fallas: {} } }
            : url.startsWith('/api/tareas/T12?proveedor=tareas') ? { status: 200, json: C.fichaDeMuestra(D['tarea:T12'].tarea) }
            : { status: 404, json: { detail: 'no' } };
        return { ok: r.status < 400, status: r.status, json: async () => r.json };
    };
    const parciales = [];
    const mas = await C.HACER.completar(M.tarea, x => parciales.push(x));
    assert.deepEqual(pedidos, ['/api/tipos/tarea/T12', '/api/tareas/T12?proveedor=tareas', '/api/proyectos', '/api/tipos/tarea?proyecto=casa%2Fcompras'],
        'a la par de la tarea, su ficha del proveedor (las acciones de la barra), con el proveedor de siempre si el día no la tiene');
    assert.deepEqual(parciales.map(x => Object.keys(x)), [['tarea', 'version']], 'la tarea, en cuanto llega');
    assert.deepEqual(Object.keys(mas), ['tarea', 'version', 'ficha_tarea', 'proveedor', 'proyecto_ficha', 'otras']);
    assert.equal(mas.proveedor, 'tareas');
    assert.equal(mas.version, 'v1', 'la versión que se leyó al abrir (para no pisar lo que cambió)');
    const f = C.contestable({ ...M.tarea, campos: { ...M.tarea.campos, ...mas } }, AHORA).ficha;
    assert.equal(f.relacion.find(x => x.texto === 'proyecto').nota, 'pedido de diciembre en curso');
    // los proyectos se leen una vez por página
    await C.HACER.completar(M.tarea);
    assert.equal(pedidos.filter(x => x.startsWith('/api/proyectos')).length, 1);
    // si no se pudo leer la tarea, lo dice
    falla = true;
    assert.deepEqual(await C.HACER.completar(M.tarea), { tarea_falla: 'sin servidor' });
    // lo que no es una tarea no se completa
    assert.equal(await C.HACER.completar(M.decide), undefined);
}

// 11. la barra de una tarea en el encabezado: la de su ficha en la vista tareas (sus íconos, colores y globos), con la
// estrella y compartir delante del título, menos lo que la ventana ya hace a su manera; sin teclas
{
    const D = C.detallesDeMuestra();
    const conFicha = (e, mas = {}) => ({ ...e, campos: { ...e.campos, tarea: D[e.direccion]?.tarea, ficha_tarea: C.fichaDeMuestra({ ...D[e.direccion].tarea, ...mas }) } });
    const roles = c => c.barra.iconos.map(x => x.rol);
    const dec = C.contestable(conFicha(M.decision), AHORA);
    assert.deepEqual(roles(dec), ['fecha', 'espera', 'prioridad', 'dueno', 'tamano', 'hecha', 'descartar'], 'decidir: todas, en el orden de su ficha');
    assert.deepEqual(dec.barra.iconos.find(x => x.rol === 'fecha'), { k: 3, rol: 'fecha', icono: dec.barra.iconos[0].icono, tono: 'amarillo', ayuda: 'cambiar la fecha' });
    assert.equal(dec.barra.iconos.find(x => x.rol === 'hecha').ayuda, 'marcarla hecha · pide confirmación');
    assert.deepEqual(dec.barra.titulo.map(x => [x.rol, x.on, x.ayuda]), [['estrella', false, 'marcar con estrella'], ['equipo', false, 'compartir con el equipo']]);
    assert.deepEqual(C.contestable(conFicha(M.decision, { etiquetas: ['estrella'] }), AHORA).barra.titulo[0].on, true, 'con estrella, encendida');
    // al cerrar, hecha y descartar ya son «Cerrarla» y «Otra cosa…»; en lo que pide hacer, hecha es «Hecho»
    const cierre = { ...M.tarea, campos: { ...M.tarea.campos, ficha_tarea: C.fichaDeMuestra(D['tarea:T12'].tarea) } };
    assert.deepEqual(roles(C.contestable(cierre, AHORA)), ['fecha', 'espera', 'prioridad', 'dueno', 'tamano']);
    const hacerTu = { ...cierre, clase: 'avance:preparado', campos: { ...cierre.campos, avance: 'preparado', como: '', texto: 'pide=hacer-tu · falta: pagar la cuota' } };
    assert.deepEqual(roles(C.contestable(hacerTu, AHORA)), ['fecha', 'espera', 'prioridad', 'dueno', 'tamano', 'descartar']);
    assert.deepEqual([...C.fueraDeContestar('decidir', 'pregunta')], []);
    // con una fecha dura, el globo de la fecha dice que esa es de afuera
    const apr = C.contestable(conFicha(M.aprobar), AHORA);
    assert.equal(apr.barra.iconos.find(x => x.rol === 'fecha').ayuda, 'cambiar la fecha de la tarea · la fecha dura (19-nov) es externa: esa no se mueve con esto');
    // sin la ficha del proveedor (todavía no llega, o no se pudo leer), sin barra
    assert.equal(C.contestable(M.decision, AHORA).barra, undefined);
    // el HTML: la estrella y compartir delante del título, lo demás al final, como botones de una barra de pantalla, que
    // atiende la ventana (data-contestar: un data-accion la cerraría); mientras una corre, la barra espera
    const h = C.ventanaContestar(dec);
    assert.match(h, /<div class="ventana-linea"><span class="ventana-iconos"><span class="contestar-iconos"><a class="icono-t estrella" data-contestar="tarea" data-valor="8" title="marcar con estrella">/);
    assert.match(h, /<div class="ventana-titulo">Colegio del Valle: el pedido del plan lector 2027<\/div><span class="ventana-herramientas"><span class="contestar-barra">/);
    assert.match(h, /<a class="pantalla-boton pantalla-accion cuadrada tono-amarillo" data-contestar="tarea" data-valor="3" title="cambiar la fecha">/);
    assert.match(h, /tono-rojo" data-contestar="tarea" data-valor="11" title="descartarla: no se va a hacer · pide confirmación"/);
    assert.doesNotMatch(h.slice(0, h.indexOf('ventana-cuerpo')), /data-accion=/, 'nada del encabezado cierra la ventana');
    assert.match(C.ventanaContestar(dec, { ...C.estadoInicial(dec), haciendo: true }), /<span class="contestar-barra haciendo">.*<span class="contestar-haciendo">/s);
    assert.doesNotMatch(C.ventanaContestar(C.contestable(M.decide, AHORA)), /ventana-linea/, 'lo que no es una tarea, sin barra');
}

// 12. correr una de la barra: como en la ficha (correrAccion, vistas/dashboard/tareas.ts), con el proveedor de la tarea y la
// versión de su ficha; y en el ensayo, sin tocar nada, la fecha elegida queda en la tarea de mentira con su línea
{
    const D = C.detallesDeMuestra();
    const pedidos = [];
    globalThis.fetch = async (url, init) => {
        pedidos.push({ url, metodo: init?.method ?? 'GET', cuerpo: init?.body ? JSON.parse(init.body) : undefined });
        const r = url.startsWith('/api/tareas/T70/accion') ? { status: 200, json: { tipo: 'comando', hecho: 'editar' } } : { status: 404, json: { detail: 'no' } };
        return { ok: r.status < 400, status: r.status, json: async () => r.json };
    };
    globalThis.document.body ??= { dataset: { avisos: 'ninguno' } };
    const e = { ...M.decision, campos: { ...M.decision.campos, proveedor: 'propio', ficha_tarea: C.fichaDeMuestra({ ...D['tarea:T70'].tarea, version: 'v7' }) } };
    const r = await C.HACER.accionTarea(e, 8);
    assert.deepEqual(r, { ok: true, dice: 'marcar con estrella' });
    assert.deepEqual(pedidos.at(-1), { url: '/api/tareas/T70/accion', metodo: 'POST', cuerpo: { proveedor: 'propio', n: 8, texto: '', version: 'v7' } },
        'la acción de su ficha, por su número, con su proveedor y la versión que se miraba');
    assert.deepEqual(await C.HACER.accionTarea(M.decision, 3), { ok: false, error: 'todavía no llegan las acciones de la tarea' });

    const dicho = [];
    const ensayo = C.hacerDeEnsayo({ decir: t => dicho.push(t), elegirFecha: async () => '2026-11-30', pausa: 0 });
    const n = pedidos.length;
    const mas0 = await ensayo.completar(M.decision);
    assert.equal(mas0.ficha_tarea.acciones[3].rol, 'fecha', 'el ensayo trae la ficha de mentira, para la barra');
    const leida = { ...M.decision, campos: { ...M.decision.campos, ...mas0 } };
    assert.deepEqual(await ensayo.accionTarea(leida, 3), { ok: true, dice: 'nueva fecha: 2026-11-30' });
    assert.match(dicho.at(-1), /^\(ensayo\) movería tarea:T70 al 2026-11-30.*no se hizo nada$/);
    const mas = await ensayo.completar(M.decision);
    assert.equal(mas.tarea.vence, '2026-11-30');
    assert.equal(mas.tarea.avance, M.decision.campos.avance, 'la propuesta sigue esperando: la ventana no se cierra');
    const f = C.contestable({ ...M.decision, campos: { ...M.decision.campos, ...mas } }, AHORA).ficha;
    assert.deepEqual([f.historia.at(-1).que, f.historia.at(-1).texto], ['fecha', 'vence 17-nov → 30-nov'], 'su línea: vence X → Y');
    assert.ok(f.juego.some(x => x.texto === 'vence el 30-nov'));
    assert.deepEqual(await ensayo.accionTarea(leida, 5), { ok: true, dice: '(ensayo) prioridad…' });
    assert.equal(pedidos.length, n, 'el ensayo no pide nada');
}

// 13. Contestar abierto desde un ensayo (el de Táctica, el del catálogo, `window.telar.ensayoContestar`) no sale a la API: ni
// contestar, ni releer, ni leer la tarea, ni lo del agente, ni ninguna acción de la barra de la tarea
{
    const pedidos = [];
    globalThis.fetch = async (url) => { pedidos.push(url); throw new Error(`un ensayo pidió ${url}`); };
    const confirmadas = [];
    const ensayo = C.hacerDeEnsayo({ decir: () => {}, elegirFecha: async () => '2026-11-30', pausa: 0, confirmar: async p => { confirmadas.push(p.pregunta); return true; } });
    // descartar un retenido, en el ensayo: pregunta (la pregunta de mentira de la prueba) y no pide nada
    {
        const c = C.contestable(M.retenido, AHORA);
        for (const p of C.porConfirmar(c, elegir(c, C.estadoInicial(c), 0, 'descartar'))) assert.equal(await ensayo.confirmar(p), true);
        await ensayo.contestar(M.retenido, c, elegir(c, C.estadoInicial(c), 0, 'descartar'));
        assert.deepEqual(confirmadas, ['¿Descartar el mensaje de «Vitrina» a «Catálogo»?']);
    }
    for (const [nombre, e0] of Object.entries(M)) {
        const c0 = C.contestable(e0, AHORA);
        const mas = await ensayo.completar(e0);
        const e = mas ? { ...e0, campos: { ...e0.campos, ...mas } } : e0;
        const c = C.contestable(e, AHORA);
        const s = c.bloques[0]?.opciones[0] ? elegir(c, C.estadoInicial(c), 0, c.bloques[0].opciones[0].id) : C.estadoInicial(c);
        if (c.bloques.length) await ensayo.contestar(e, c, s);
        await ensayo.releer(e);
        await ensayo.alAgente(e, c0, ['instrucción: algo'], { lineas: 0, mensaje: false });
        ensayo.conversar(e, c);
        ensayo.ir('tarea:T1');
        for (const x of c.barra?.iconos ?? []) await ensayo.accionTarea(e, x.k);
        for (const x of c.barra?.titulo ?? []) await ensayo.accionTarea(e, x.k);
        assert.deepEqual(pedidos, [], `ensayo «${nombre}»: no pide nada`);
    }
}

// 14. lo que pide un hilo o una tarea (el resumen, el detalle, la ficha): `código`, **negrita** y enlaces. Un
// [texto](https://…) y una dirección suelta (sin el punto que cierra la frase) se abren en una pestaña nueva, sin acceso a
// esta página ni su dirección; en una opción (un botón), el texto, con la dirección en el globo; lo demás se escapa
{
    const a = (url, texto = url) => `<a class="contestar-enlace" href="${url}" target="_blank" rel="noopener noreferrer" title="${url}">${texto}</a>`;
    assert.equal(C.enLinea('mira [la propuesta](https://ejemplo.cl/p?a=1&b=2) y **ya**'),
        `mira ${a('https://ejemplo.cl/p?a=1&amp;b=2', 'la propuesta')} y <b>ya</b>`);
    assert.equal(C.enLinea('está en https://ejemplo.cl/doc.'), `está en ${a('https://ejemplo.cl/doc')}.`, 'sin el punto de la frase');
    assert.equal(C.enLinea('(ver https://ejemplo.cl/x_(y))'), `(ver ${a('https://ejemplo.cl/x_(y)')})`, 'el paréntesis que abrió adentro, sí');
    assert.equal(C.enLinea('`https://ejemplo.cl` y `x*y`'), `<code>${a('https://ejemplo.cl')}</code> y <code>x*y</code>`, 'entre comillas de código, también');
    assert.equal(C.enLinea('**[aquí](https://ejemplo.cl)**'), `<b>${a('https://ejemplo.cl', 'aquí')}</b>`, 'la negrita envuelve el enlace');
    assert.equal(C.enLinea('<b>no</b> [x](javascript:alert(1)) tarea:T1'), '&lt;b&gt;no&lt;/b&gt; [x](javascript:alert(1)) tarea:T1',
        'solo web: lo demás, texto escapado');
    assert.equal(C.enLinea('[la propuesta](https://ejemplo.cl/p) o https://otra.cl', false), '<span title="https://ejemplo.cl/p">la propuesta</span> o https://otra.cl',
        'en una opción, sin enlaces');
    assert.equal(C.parrafosEnLinea('uno\nhttps://ejemplo.cl\n\ndos'), `<p>uno ${a('https://ejemplo.cl')}</p><p>dos</p>`);
    // en la ventana: el resumen y el detalle de una tarea, y su ficha; las opciones, sin enlaces
    const e = { ...M.tarea, campos: { ...M.tarea.campos, texto: 'pide=decidir · opciones=[la A](https://ejemplo.cl/a)* | la B · ¿cuál? Detalle en https://ejemplo.cl/detalle' } };
    const c = C.contestable(e, AHORA);
    const h = C.ventanaContestar(c, C.estadoInicial(c));
    assert.ok(h.includes(a('https://ejemplo.cl/detalle')), 'lo que pide, con su enlace');
    assert.ok(!/<button[^>]*>(?:(?!<\/button>).)*<a /s.test(h), 'ningún enlace dentro de un botón');
    assert.match(h, /<span title="https:\/\/ejemplo\.cl\/a">la A<\/span>/, 'la opción, con su texto y la dirección en el globo');
}

console.log('contestar: 14 grupos de pruebas, bien');
