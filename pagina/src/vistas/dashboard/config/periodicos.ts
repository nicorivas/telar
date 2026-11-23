// Los procesos que corren solos (`telar periodicos`), de esta máquina o de la de `[periodicos] en`. Se ven en un
// calendario, de un día o de una semana (config/corridas.ts: qué corrió, cómo salió, qué viene, a quién le llega y de
// qué depende), o en la lista de siempre. Elegir uno muestra debajo lo que es y lo que se le hace; su ficha tiene el log
// (⏎ correrlo ahora, 1 pausarlo, 2 editarlo, 3 borrarlo). El formulario crea o edita uno: una skill y lo que va
// después de ella (uno de los dos, o los dos), a quién se le encarga (un agente residente, o un hilo nuevo cada vez),
// cuándo, y de qué otros usa lo que dejan.

import * as cli from '../../../cli';
import { esc, haceCorto, normalizar } from '../../../estilo';
import * as ui from '../../../web/ui';
import type { MensajeDia } from '../vista';
import type { FabricaSeccion } from './seccion';
import { I } from '../../../web/iconos';
import { barraBuscar } from '../../../componentes/buscador';
import * as S from '../../../componentes/senales';
import { type Calendario, type Modo, calendario, fechaCorta, horasDe, htmlCalendario, htmlLeyenda, lunesDe, relaciones, sumarDias } from './corridas';

/** La frase del estado de un proceso, para su ficha y su fila. */
function dicePeriodico(p: cli.JsonPeriodico): string {
    if (p.ultima.corriendo) return 'corriendo ahora';
    if (!p.activo) return 'pausado: no corre hasta que lo actives';
    if (p.ultima.codigo !== undefined && p.ultima.codigo !== 0) return `la última vez: ${p.ultima.resultado ?? 'falló'}`;
    if (p.ultima.inicio) return `la última vez: ${p.ultima.resultado ?? 'bien'}`;
    return 'todavía no ha corrido';
}

/** «2 h 10», «35 min», «3 d»: cuánto falta hasta esa hora. */
function enCuanto(iso: string): string {
    const min = Math.max(0, Math.round((Date.parse(iso) - Date.now()) / 60000));
    if (min < 60) return `${min} min`;
    if (min < 60 * 24) return `${Math.floor(min / 60)} h${min % 60 ? ` ${min % 60}` : ''}`;
    return `${Math.round(min / 1440)} d`;
}

/** «vie 2 10:00»: una corrida, corta. */
function diaHora(iso: string): string {
    return `${fechaCorta(iso.slice(0, 10), false)} ${iso.slice(11, 16)}`;
}

const PRESETS: [string, string][] = [['0 9 * * *', 'todos los días 9:00'], ['0 9 * * 1-5', 'lun–vie 9:00'],
    ['0 8-20/2 * * *', 'cada 2 h, 8–20'], ['0 * * * *', 'cada hora'], ['*/30 * * * *', 'cada 30 min'],
    ['30 18 * * 5', 'viernes 18:30'], ['0 9 1 * *', 'el 1 de cada mes']];

/** Una skill al principio del prompt («/correo personal» → correo, personal). */
const SKILL = /^\/([\w:.-]+)(?:\s+([\s\S]*))?$/;

/** El prompt de un proceso: la skill (si hay) y lo que va después, o solo el texto. */
export const armarPrompt = (skill: string, texto: string): string => {
    const s = skill.trim().replace(/^\//, ''), t = texto.trim();
    return s ? `/${s}${t ? ` ${t}` : ''}` : t;
};

/** Al revés: la skill del principio y lo que sigue; sin skill, todo es texto. */
export const leerPrompt = (mensaje: string): [string, string] => {
    const m = SKILL.exec(mensaje.trim());
    return m ? [m[1], m[2] ?? ''] : ['', mensaje.trim()];
};

/** A quién se le encarga: `agente:<clave>` o `hilo` (uno nuevo cada vez). */
type Destino = string;

interface Formulario {
    original: string; p: cli.JsonPeriodico; skills?: cli.JsonSkill[]; skillsDe?: string;
    destino: Destino; skill: string; texto: string;
}

const MODOS: [Modo | 'lista', string][] = [['dia', 'día'], ['semana', 'semana'], ['lista', 'lista']];

/** El modo que se eligió la última vez (en este navegador). */
const recordado = (): Modo | 'lista' => {
    try { const m = localStorage.getItem('telar.periodicos.modo'); return m === 'semana' || m === 'lista' ? m : 'dia'; } catch { return 'dia'; }
};

export const periodicos: FabricaSeccion = ctx => {
    /** lo leído (con las corridas de la ventana), y por qué no llegó */
    let datos: cli.JsonCalendarioPer | undefined;
    let cal: Calendario | undefined;
    let error = '';
    let cargando = false;
    let modo: Modo | 'lista' = recordado();
    /** el día que se mira (en semana, cualquiera de la semana); vacío hasta la primera lectura: el de allá */
    let fecha = '';
    /** el proceso elegido en el calendario */
    let sel = '';
    /** el abierto (con su log), si hay uno; el formulario de crear o editar, si está abierto */
    let abierto: { nombre: string; log: string } | undefined;
    let form: Formulario | undefined;
    const seVe = () => ctx.seVe('periodicos');

    const ventana = (): [string, number] => (modo === 'semana' ? [fecha ? lunesDe(fecha) : '', 7] : [fecha, 1]);

    const leer = async () => {
        if (!datos) ctx.pintar(['<div class="vacio">leyendo los procesos periódicos…</div>']);
        cargando = true;
        const [desde, dias] = ventana();
        const r = await cli.periodicosCalendario(desde, dias);
        cargando = false;
        // en semana sin fecha todavía: la de allá, y otra vez con su lunes
        if (r.datos && modo === 'semana' && !desde) { fecha = r.datos.ahora.slice(0, 10); await leer(); return; }
        if (r.datos) {
            datos = r.datos;
            cal = calendario(r.datos);
            if (!fecha) fecha = r.datos.desde;
        }
        error = r.datos ? '' : (r.error ?? 'no contestó');
        if (seVe()) seccion.pintar();
    };

    const mover = async (valor: string) => {
        const hoy = datos?.ahora.slice(0, 10) ?? fecha;
        fecha = valor === 'hoy' ? hoy : sumarDias(fecha || hoy, Number(valor) * (modo === 'semana' ? 7 : 1));
        await leer();
    };

    const cambiarModo = async (m: string) => {
        if (m !== 'dia' && m !== 'semana' && m !== 'lista') return;
        modo = m;
        try { localStorage.setItem('telar.periodicos.modo', m); } catch { /* sin almacenamiento: no se recuerda */ }
        await leer();
    };

    const ver = async (nombre: string) => {
        abierto = { nombre, log: 'leyendo…' };
        seccion.pintar();
        const r = await cli.periodicosLog(nombre);
        if (abierto?.nombre !== nombre) return;
        abierto.log = r.datos ? (r.datos.log || '(todavía no ha corrido)') : (r.error ?? 'no contestó');
        if (seVe()) seccion.pintar();
    };

    /** Corre una orden de `telar periodicos` y relee: la lista cambia (o el log, si se corrió). */
    const orden = async (args: string[]) => {
        if (args[0] === 'borrar') {
            const si = await ui.aviso(`¿Borrar el proceso «${args[1]}»? Deja de correr; el archivo anterior queda en periodicos.toml.anterior.`, 'Borrar', { destruye: true });
            if (si !== 'Borrar') return;
        }
        const r = await cli.periodicosOrden(args);
        if (!r.datos) { void ui.aviso(`telar: ${r.error ?? 'no se pudo'}`); return; }
        ui.estado(`telar: ${r.datos.hecho}`, 5000);
        if (args[0] === 'borrar') { abierto = undefined; sel = ''; }
        await leer();
        // «ahora» corre suelto: lo de recién (el log, la corrida en el calendario) se relee en unos segundos
        if (args[0] === 'ahora') {
            const nombre = args[1];
            setTimeout(() => { void leer().then(() => (abierto?.nombre === nombre ? ver(nombre) : undefined)); }, 4000);
        } else if (abierto) await ver(abierto.nombre);
    };

    const agentes = () => datos?.agentes ?? [];
    const agenteDe = (clave: string) => agentes().find(a => a.clave === clave);
    /** Dónde corre el agente de ese destino: sus skills son las de su carpeta. */
    const carpetaDe = (destino: Destino, carpeta: string) => (destino.startsWith('agente:') ? agenteDe(destino.slice(7))?.carpeta ?? '' : carpeta);

    const abrirForm = async (original: string, p: cli.JsonPeriodico) => {
        const [skill, texto] = leerPrompt(p.mensaje);
        // uno nuevo va al agente que más usan los que ya hay; uno que existe, al suyo
        const veces = new Map<string, number>();
        for (const x of datos?.procesos ?? []) if (x.agente) veces.set(x.agente, (veces.get(x.agente) ?? 0) + 1);
        const usado = [...veces].sort((a, b) => b[1] - a[1]).map(([k]) => k).find(k => agenteDe(k));
        const destino = original ? (p.agente ? `agente:${p.agente}` : 'hilo') : (usado ? `agente:${usado}` : 'hilo');
        form = { original, p, destino, skill, texto };
        seccion.pintar();
        await Promise.all([previaHorario(p.cuando), cargarSkills(carpetaDe(destino, p.carpeta))]);
    };

    /** Uno nuevo: el formulario, con lo que suelen llevar los que ya hay (carpeta, argumentos). */
    const nuevo = () => {
        const parecido = (datos?.procesos ?? []).find(x => x.tipo === 'mensaje' && !x.agente);
        return abrirForm('', {
            nombre: '', cuando: '0 9 * * 1-5', tipo: 'mensaje', comando: '', mensaje: '', hilo: '', max_abiertos: 1,
            argumentos: parecido?.argumentos ?? ['--permission-mode', 'acceptEdits'], carpeta: parecido?.carpeta ?? '',
            descripcion: '', activo: true, proxima: '', ultima: {}, despues: [],
        });
    };

    const editar = async (nombre: string) => {
        const p = datos?.procesos.find(x => x.nombre === nombre);
        if (p) await abrirForm(nombre, { ...p, argumentos: [...p.argumentos] });
    };

    const htmlSkills = () => {
        if (!form?.skills) return '<div class="dim">leyendo las skills de allá…</div>';
        const ninguna = `<a class="skill${form.skill ? '' : ' activa'}" data-skill="" data-texto=""><b>sin skill</b><span class="dim">solo lo que escribas abajo</span></a>`;
        if (!form.skills.length) return `${ninguna}<div class="dim">no hay skills en esa carpeta</div>`;
        return ninguna + form.skills.map(x => `<a class="skill${x.nombre === form?.skill ? ' activa' : ''}" data-skill="${esc(x.nombre)}" data-texto="${esc(normalizar(`${x.nombre} ${x.descripcion}`))}" title="${esc(x.descripcion)}">`
            + `<b>/${esc(x.nombre)}</b><span class="dim">${esc(x.descripcion)}</span></a>`).join('');
    };

    /** Las próximas corridas de lo que se está escribiendo, o por qué no se entiende. */
    const previaHorario = async (cuando: string) => {
        const r = await cli.periodicosHorario(cuando);
        const d = r.datos;
        const html = !d ? `<span class="falla">${esc(r.error ?? 'no contestó')}</span>`
            : !d.valido ? `<span class="falla">${esc(d.error)}</span>`
            : 'las próximas: ' + d.proximas.map(x => `<b>${esc(diaHora(x))}</b>`).join(' · ')
              + (d.proximas[0] ? ` <span class="dim">(en ${esc(enCuanto(d.proximas[0]))})</span>` : '');
        ctx.parcial('per-previa', html);
    };

    const cargarSkills = async (carpeta: string) => {
        const f = form;
        if (!f || (f.skills && f.skillsDe === carpeta)) return;
        f.skills = undefined;
        ctx.parcial('per-skills', htmlSkills());
        const r = await cli.periodicosSkills(carpeta);
        if (form !== f) return;
        f.skills = r.datos?.skills ?? [];
        f.skillsDe = carpeta;
        ctx.parcial('per-skills', r.datos ? htmlSkills() : `<div class="falla">${esc(r.error ?? 'no contestó')}</div>`);
    };

    const guardar = async (valor: string) => {
        const f = form;
        if (!f) return;
        const d = JSON.parse(valor) as { nombre: string; descripcion: string; tipo: string; skill: string; texto: string; destino: string;
            comando: string; hilo: string; padre: string; max: string; args: string; cuando: string; carpeta: string; activo: boolean; despues: string[] };
        const nombre = f.original || d.nombre.trim();
        const args = d.args.split('\n').map(x => x.trim()).filter(Boolean);
        const mensaje = armarPrompt(d.skill, d.texto);
        if (!nombre) { ctx.parcial('per-error', 'falta el nombre'); return; }
        if (d.tipo === 'mensaje' && !mensaje) { ctx.parcial('per-error', 'elige una skill o escribe qué pedirle (o las dos)'); return; }
        const lista = [f.original ? 'editar' : 'nuevo', nombre, '--cuando', d.cuando.trim(), '--descripcion', d.descripcion.trim()];
        if (d.tipo === 'mensaje') {
            lista.push('--mensaje', mensaje);
            if (d.destino.startsWith('agente:')) lista.push('--agente', d.destino.slice(7));
            else {
                lista.push('--agente', '', '--hilo', d.hilo.trim(), '--padre', d.padre.trim(), '--max', d.max.trim() || '1', '--carpeta', d.carpeta.trim());
                if (args.length) lista.push(...args.map(a => `--arg=${a}`));
                else if (f.original) lista.push('--sin-args');
            }
        } else {
            lista.push('--comando', d.comando.trim(), '--carpeta', d.carpeta.trim());
            if (f.original) lista.push('--sin-args');
        }
        if (d.despues.length) lista.push('--despues', d.despues.join(','));
        else if (f.original) lista.push('--sin-despues');
        if (f.original) lista.push('--activo', d.activo ? 'si' : 'no');
        else if (!d.activo) lista.push('--pausado');
        ctx.parcial('per-error', '<span class="dim">guardando…</span>');
        const r = await cli.periodicosOrden(lista);
        if (!r.datos) { ctx.parcial('per-error', esc(r.error ?? 'no se pudo')); return; }
        ui.estado(`telar: ${r.datos.hecho}`, 5000);
        form = undefined;
        sel = nombre;
        await leer();
    };

    /** La banda de arriba: ir a otro día o semana, el modo, la máquina y el + de crear. */
    const banda = () => {
        const hoy = datos?.ahora.slice(0, 10) ?? '';
        const [desde] = ventana();
        const cuando = modo === 'semana' && desde ? `${fechaCorta(desde, false)} – ${fechaCorta(sumarDias(desde, 6))}` : fecha ? fechaCorta(fecha) : '';
        const esHoy = modo === 'semana' ? lunesDe(hoy) === desde : fecha === hoy;
        const que = modo === 'semana' ? 'semana' : 'día';
        const ir = modo === 'lista' ? '' : `<a class="cr-ir i" data-accion="per-mover" data-valor="-1" title="${que} anterior ([)">${I.atras}</a>`
            + `<span class="cr-fecha">${esc(cuando)}${cargando ? ' …' : ''}</span>`
            + `<a class="cr-ir i" data-accion="per-mover" data-valor="1" title="${que} siguiente (])">${I.siguiente}</a>`
            + (esHoy ? '' : `<a class="cr-palabra" data-accion="per-mover" data-valor="hoy">${modo === 'semana' ? 'esta semana' : 'hoy'}</a>`)
            + '<span class="corte"></span>';
        const modos = MODOS.map(([m, n]) => `<a class="cr-palabra${m === modo ? ' si' : ''}" data-accion="per-modo" data-valor="${m}">${n}</a>`).join('');
        const lista = datos?.procesos ?? [];
        return `<div class="cr-banda">${ir}${modos}<span class="der dim">${datos?.maquina ? `${esc(datos.maquina)} · ` : ''}`
            + `${lista.filter(p => p.activo).length} de ${lista.length} activos${datos?.zona ? ` · hora de ${esc(datos.zona)}` : ''}</span>`
            + `<a class="cr-ir i" data-accion="per-nuevo" title="un proceso nuevo (+): una skill o un prompt para un agente, o un comando">${I.nuevo}</a></div>`;
    };

    /** Lo que es el elegido, de qué depende y lo que se le hace, debajo del calendario. */
    const htmlDetalle = (c: Calendario, nombre: string) => {
        const p = c.d.procesos.find(x => x.nombre === nombre);
        if (!p) return '<div class="cr-det dim">elige un proceso (su nombre o uno de sus círculos) para ver qué es, de qué depende y qué hacerle</div>';
        const dst = p.destino;
        const ag = dst?.agente ? agenteDe(dst.agente)?.nombre ?? dst.agente : '';
        const [skill, texto] = leerPrompt(p.mensaje);
        const r = relaciones(c, p.nombre);
        const filas: [string, string][] = [
            ['qué', p.tipo === 'mensaje' ? (skill ? `/${skill}${texto ? ` · y después: ${texto}` : ''}` : `prompt: ${texto}`) : `$ ${p.comando}`],
            ['a quién', dst?.tipo === 'agente' ? `${ag}${dst.inferido ? ' (se lo encarga el comando)' : ''}: comparte su casilla con los de su grupo`
                : dst?.tipo === 'hilo' ? `un hilo nuevo, «${p.hilo || p.nombre}»${p.padre ? `, hijo de ${p.padre}` : ''}, en ${p.carpeta || '~'} · hasta ${p.max_abiertos} abierto(s)` : 'nadie: el comando corre solo'],
            ['cuándo', `${horasDe(c, p) || '—'} · cron ${p.cuando}`],
            ...(p.proxima ? [['la próxima', `${diaHora(p.proxima)} (en ${enCuanto(p.proxima)})`] as [string, string]] : []),
            ['la última', p.ultima.inicio ? `${diaHora(p.ultima.inicio)} · ${p.ultima.resultado ?? 'corriendo'} · hace ${haceCorto(p.ultima.inicio)}` : 'nunca'],
            ...(r.usa.length ? [['usa lo de', r.usa.join(', ') + (p.despues_falta?.length ? ` (no existe: ${p.despues_falta.join(', ')})` : '')] as [string, string]] : []),
            ...(r.loUsan.length ? [['lo usan', r.loUsan.join(', ')] as [string, string]] : []),
            ...(r.juntas.length ? [['se junta con', r.juntas.slice(0, 6).map(j => `${j.con} (${fechaCorta(j.en.slice(0, 10), false)} ${j.en.slice(11, 16)}, ${Math.abs(j.antes)} min ${j.antes > 0 ? 'antes' : 'después'})`).join(' · ')
                + (r.juntas.length > 6 ? ` y ${r.juntas.length - 6} más` : '')] as [string, string]] : []),
        ];
        const deAfuera = p.disparador ? `[disparadores.${p.nombre}] en la configuración` : p.modulo ? `el modulo.toml de ${p.modulo}` : '';
        const args = (a: string[]) => esc(JSON.stringify(a));
        const botones = [
            `<a class="atajo" data-accion="per-orden" data-valor="${args(['ahora', p.nombre])}">${I.correr}<span>correr ahora</span></a>`,
            ...(deAfuera ? [] : [
                `<a class="atajo" data-accion="per-orden" data-valor="${args([p.activo ? 'pausar' : 'activar', p.nombre])}">${p.activo ? I.pausa : I.correr}<span>${p.activo ? 'pausar' : 'activar'}</span></a>`,
                `<a class="atajo" data-accion="per-editar" data-valor="${esc(p.nombre)}">${I.editar}<span>editar</span></a>`,
            ]),
            `<a class="atajo" data-accion="per-ver" data-valor="${esc(p.nombre)}">${I.ficha}<span>ficha y log</span></a>`,
        ];
        return `<div class="cr-det">`
            + `<div class="subcab"><b>${S.enLinea(S.periodico(p, dicePeriodico(p)))} ${esc(p.nombre)}</b>${p.activo ? '' : '<span class="dim">pausado</span>'}</div>`
            + (p.descripcion ? `<div class="sub-ficha dim">${esc(p.descripcion)}</div>` : '')
            + `<div class="cr-acciones">${botones.join('')}</div>`
            + (deAfuera ? `<div class="dim">se cambia en ${esc(deAfuera)}</div>` : '')
            + filas.map(([k, v]) => `<div class="fila"><span class="dim cr-k">${esc(k)}</span><span class="que">${esc(v)}</span></div>`).join('')
            + '</div>';
    };

    const pintarCalendario = (c: Calendario) => {
        const m: Modo = modo === 'semana' ? 'semana' : 'dia';
        ctx.pintar([banda(), error ? `<div class="vacio falla">${esc(error)}</div>` : '',
            !c.d.procesos.length ? `<div class="vacio">ninguno todavía · <a data-accion="per-nuevo">crear uno</a> · se guardan en ${esc(c.d.archivo)}</div>` : '',
            htmlLeyenda(), htmlCalendario(c, m, sel), htmlDetalle(c, sel)]);
    };

    const pintarLista = () => {
        const lista = datos?.procesos ?? [];
        const h = [banda()];
        if (error) h.push(`<div class="vacio falla">${esc(error)}</div>`);
        if (datos && !lista.length) h.push(`<div class="vacio">ninguno todavía · <a data-accion="per-nuevo">crear uno</a> · se guardan en ${esc(datos.archivo)}</div>`);
        for (const p of lista) {
            const que = p.tipo === 'mensaje' ? `${p.mensaje}${p.agente ? ` → ${agenteDe(p.agente)?.nombre ?? p.agente}` : ''}` : p.comando;
            const cuando = p.activo ? (p.proxima ? `en ${enCuanto(p.proxima)}` : '—') : 'pausado';
            const ultima = p.ultima.inicio ? `hace ${haceCorto(p.ultima.inicio)}` : 'nunca';
            h.push(`<div class="fila clic per${p.activo ? '' : ' dim'}" data-accion="per-ver" data-valor="${esc(p.nombre)}" title="${esc(`${p.descripcion ? p.descripcion + '\n' : ''}${dicePeriodico(p)}\nclic: su ficha y su log`)}">`
                + `${S.enLinea(S.periodico(p))}<b>${esc(p.nombre)}</b>`
                + `<code class="dim">${esc(p.cuando)}</code><span class="que">${esc(que)}</span>`
                + `<span class="der dim">${esc(cuando)} · ${esc(ultima)}</span></div>`);
        }
        if (datos) h.push(`<div class="vacio dim">${esc(datos.archivo)}</div>`);
        ctx.pintar(h);
    };

    const pintarFicha = () => {
        const p = datos?.procesos.find(x => x.nombre === abierto?.nombre);
        if (!abierto || !p) { abierto = undefined; seccion.pintar(); return; }
        const args = (a: string[]) => esc(JSON.stringify(a));
        // el de un módulo o de un [disparadores.x] se cambia allá: pausarlo, editarlo o borrarlo aquí era un 409
        const deAfuera = p.disparador ? `[disparadores.${p.nombre}] en la configuración` : p.modulo ? `el modulo.toml de ${p.modulo}` : '';
        const botones = [
            `<a class="atajo principal" data-accion="per-orden" data-valor="${args(['ahora', p.nombre])}"><kbd>⏎</kbd><span>correr ahora</span></a>`,
            ...(deAfuera ? [] : [
                `<a class="atajo" data-accion="per-orden" data-valor="${args([p.activo ? 'pausar' : 'activar', p.nombre])}"><kbd>1</kbd><span>${p.activo ? `${I.pausa} pausar` : `${I.correr} activar`}</span></a>`,
                `<a class="atajo" data-accion="per-editar" data-valor="${esc(p.nombre)}"><kbd>2</kbd><span>${I.editar} editar</span></a>`,
                `<a class="atajo" data-accion="per-orden" data-valor="${args(['borrar', p.nombre])}"><kbd>3</kbd><span>${I.descartar} borrar</span></a>`,
            ]),
            `<a class="atajo" data-accion="periodicos"><kbd>⎋</kbd><span>volver</span></a>`,
        ];
        ctx.teclas.set('⏎', () => orden(['ahora', p.nombre]));
        if (!deAfuera) {
            ctx.teclas.set('1', () => orden([p.activo ? 'pausar' : 'activar', p.nombre]));
            ctx.teclas.set('2', () => editar(p.nombre));
            ctx.teclas.set('3', () => orden(['borrar', p.nombre]));
        }
        const ag = p.agente ? agenteDe(p.agente)?.nombre ?? p.agente : '';
        const filas: [string, string][] = [
            ...(deAfuera ? [['se cambia en', deAfuera] as [string, string]] : []),
            ['cuándo', `${p.cuando}${p.proxima ? ` · la próxima ${diaHora(p.proxima)} (en ${enCuanto(p.proxima)})` : ''}`],
            p.tipo === 'mensaje' ? ['prompt', p.mensaje] : ['comando', p.comando],
            ...(p.tipo === 'mensaje' ? [['a quién', ag ? `${ag}, en su sesión de siempre` : `un hilo nuevo, «${p.hilo || p.nombre}»${p.padre ? `, hijo de ${p.padre}` : ''} · hasta ${p.max_abiertos} abierto(s)`] as [string, string]] : []),
            ...(p.despues?.length ? [['usa lo de', p.despues.join(', ')] as [string, string]] : []),
            ...(p.argumentos.length && !ag ? [['argumentos', p.argumentos.join(' ')] as [string, string]] : []),
            ...(p.carpeta && !ag ? [['carpeta', p.carpeta] as [string, string]] : []),
            ['última', p.ultima.inicio ? `${diaHora(p.ultima.inicio)} · ${p.ultima.resultado ?? 'corriendo'}${p.ultima.hilo ? ` · «${p.ultima.hilo}»` : ''}` : 'nunca'],
        ];
        ctx.pintar([`<div id="ficha-per">`,
            `<div class="subcab"><b>${S.enLinea(S.periodico(p))} ${esc(p.nombre)}</b><span class="der dim">${esc(dicePeriodico(p))}</span></div>`,
            p.descripcion ? `<div class="sub-ficha dim">${esc(p.descripcion)}</div>` : '',
            `<div class="acciones-t">${botones.join('')}</div>`,
            ...filas.map(([k, v]) => `<div class="fila"><span class="dim" style="min-width: 11ch">${esc(k)}</span><span class="que">${esc(v)}</span></div>`),
            `<h2 class="sec">log</h2><pre class="log">${esc(abierto.log)}</pre></div>`]);
    };

    const pintarForm = (f: Formulario) => {
        const p = f.p;
        const campo = (etiqueta: string, html: string, ayuda = '', clase = '') =>
            `<label class="campo${clase ? ` ${clase}` : ''}"><span class="etiqueta">${esc(etiqueta)}</span><span class="control">${html}`
            + `${ayuda ? `<span class="ayuda dim">${esc(ayuda)}</span>` : ''}</span></label>`;
        const opcion = (atr: string, valor: string, activa: boolean, html: string, titulo = '', extra = '') =>
            `<a class="opcion-t${activa ? ' activa' : ''}" ${atr}="${esc(valor)}"${extra}${titulo ? ` title="${esc(titulo)}"` : ''}>${html}</a>`;
        const destinos = [...agentes().map(a => opcion('data-per-destino', `agente:${a.clave}`, f.destino === `agente:${a.clave}`,
                `<span class="per-icono">${esc(a.icono || a.nombre.slice(0, 1).toUpperCase())}</span>${esc(a.nombre)}`, `se lo encarga a ${a.nombre}: su sesión de siempre, sus skills y sus permisos`, ` data-carpeta="${esc(a.carpeta)}"`)),
            opcion('data-per-destino', 'hilo', f.destino === 'hilo', `<span class="per-icono i">${I.terminal}</span>hilo nuevo`, 'abre un hilo nuevo cada vez, en la carpeta que digas')];
        const otros = (datos?.procesos ?? []).filter(x => x.nombre !== f.original);
        const tras = otros.map(x => opcion('data-per-tras', x.nombre, (p.despues ?? []).includes(x.nombre), esc(x.nombre), x.descripcion)).join('');
        const dice = f.skill ? `/${f.skill}${f.texto ? ` ${f.texto}` : ''}` : f.texto;
        // de quién es hijo cada hilo que abre: nadie, o el hilo de un agente (o el que diga el archivo, si es otro)
        const candidatos = [...new Set([...agentes().map(a => a.nombre), ...(p.padre ? [p.padre] : [])])];
        const padres = [opcion('data-per-padre', '', !p.padre, 'nadie', 'va suelto en la barra'),
            ...candidatos.map(n => opcion('data-per-padre', n, p.padre === n, esc(n), `cuelga de «${n}»`))].join('');
        ctx.pintar([`<div id="form-per" class="tipo-${p.tipo} destino-${f.destino === 'hilo' ? 'hilo' : 'agente'}" data-destino="${esc(f.destino)}">`,
            `<div class="subcab"><b>${f.original ? `editar «${esc(f.original)}»` : 'un proceso nuevo'}</b>${datos?.maquina ? `<span class="dim">${esc(datos.maquina)}</span>` : ''}</div>`,
            campo('nombre', `<input id="per-nombre" value="${esc(p.nombre)}" placeholder="resumen-diario" spellcheck="false"${f.original ? ' disabled' : ''}>`,
                f.original ? 'el nombre no se cambia' : 'minúsculas, números, - y _ (al elegir una skill, se propone el suyo)'),
            campo('para qué', `<input id="per-desc" value="${esc(p.descripcion)}" placeholder="en una línea, para acordarte">`),
            campo('qué hace', `<span class="opciones">${opcion('data-per-tipo', 'mensaje', p.tipo === 'mensaje', `${I.chispa} le pide algo a un agente`)}`
                + `${opcion('data-per-tipo', 'comando', p.tipo === 'comando', '$ corre un comando de shell')}</span>`),
            `<div class="solo-mensaje">`,
            campo('a quién', `<span class="opciones">${destinos.join('')}</span>`,
                'un agente residente (lo hace en su sesión de siempre; los de un mismo agente comparten su casilla) o un hilo nuevo cada vez'),
            campo('skill', `<input type="hidden" id="per-skill" value="${esc(f.skill)}">`
                + barraBuscar({ id: 'per-skill-filtro', placeholder: 'skills', ayuda: 'buscar por el nombre o lo que hace' })
                + `<div id="per-skills" class="skills">${htmlSkills()}</div>`, 'opcional: las de la carpeta de quien lo hace'),
            campo('y después', `<textarea id="per-mensaje" rows="3" placeholder="lo que va después de la skill; sin skill, todo lo que se le pide" spellcheck="false">${esc(f.texto)}</textarea>`
                + `<span class="per-dice">le llega: <code id="per-dice">${esc(dice) || '—'}</code></span>`, 'una skill, un texto, o las dos: al menos una'),
            `<div class="solo-hilo">`,
            campo('hilo', `<input id="per-hilo" value="${esc(p.hilo)}" placeholder="${esc(p.nombre || 'el nombre del proceso')}">`, 'su nombre; se le agrega la fecha y la hora'),
            campo('abiertos', `<input id="per-max" type="number" min="1" value="${p.max_abiertos}">`, 'con tantos sin cerrar, esa vez no abre otro'),
            campo('cuelga de', `<span class="opciones">${padres}</span>`,
                'opcional: en la barra, cada hilo que abre va debajo de ese (el de un agente), hereda sus etiquetas y le avisa al terminar cada turno'),
            campo('argumentos', `<textarea id="per-args" rows="3" spellcheck="false">${esc(p.argumentos.join('\n'))}</textarea>`, 'para el agente, uno por línea (permisos, herramientas)'),
            `</div></div><div class="solo-comando">`,
            campo('comando', `<input id="per-comando" value="${esc(p.comando)}" placeholder="~/bin/resumen --corto" spellcheck="false">`, 'una línea de bash; su salida queda en el log'),
            `</div>`,
            campo('carpeta', `<input id="per-carpeta" value="${esc(p.carpeta)}" placeholder="~ (el hogar)" spellcheck="false">`,
                'dónde corre: las skills de la lista son las de ahí', 'solo-carpeta'),
            campo('cuándo', `<input id="per-cuando" value="${esc(p.cuando)}" spellcheck="false">`
                + `<span class="presets">${PRESETS.map(([c, n]) => `<a data-per-horario="${esc(c)}" title="${esc(c)}">${esc(n)}</a>`).join('')}</span>`
                + `<div id="per-previa" class="dim">…</div>`, 'cron: minuto hora día-del-mes mes día-de-la-semana'),
            ...(otros.length ? [campo('usa lo de', `<span class="opciones tras">${tras}</span>`,
                'opcional: los procesos cuyo resultado usa este (el plan de la noche, la retro de la tarde). Se dibuja en el calendario; cron no espera a nadie')] : []),
            campo('activo', `<input id="per-activo" type="checkbox"${p.activo ? ' checked' : ''}>`),
            `<div id="per-error" class="falla"></div>`,
            `<div class="acciones-t fila-botones"><a class="atajo principal" data-accion="per-guardar"><kbd>⌘⏎</kbd><span>${f.original ? 'guardar' : 'crear'}</span></a>`
            + `<a class="atajo" data-accion="per-cancelar"><kbd>⎋</kbd><span>cancelar</span></a></div>`,
            '</div>']);
    };

    const seccion = {
        clave: 'periodicos',
        nombre: 'periódicos',
        ayuda: 'los procesos que corren solos, en un calendario: qué corrió, qué viene, a quién le llega y de qué depende',
        abrir: () => leer(),
        pintar(): void {
            ctx.teclas.clear();
            if (form) { pintarForm(form); return; }
            if (abierto) { pintarFicha(); return; }
            ctx.teclas.set('+', () => nuevo());
            if (modo !== 'lista') {
                ctx.teclas.set('[', () => mover('-1'));
                ctx.teclas.set(']', () => mover('1'));
            }
            if (modo === 'lista' || !cal) pintarLista();
            else pintarCalendario(cal);
        },
        async accion(accion: string, valor: string): Promise<boolean> {
            switch (accion) {
                // ⎋ desde la ficha: al calendario (o a la lista)
                case 'periodicos': abierto = undefined; form = undefined; await leer(); return true;
                case 'per-ver': if (valor) await ver(valor); return true;
                case 'per-sel': sel = sel === valor ? '' : valor; seccion.pintar(); return true;
                case 'per-mover': await mover(valor); return true;
                case 'per-modo': await cambiarModo(valor); return true;
                case 'per-ver-dia': if (valor) { fecha = valor; await cambiarModo('dia'); } return true;
                case 'per-nuevo': await nuevo(); return true;
                case 'per-editar': if (valor) await editar(valor); return true;
                case 'per-guardar': if (valor) await guardar(valor); return true;
                case 'per-cancelar': form = undefined; seccion.pintar(); return true;
                case 'per-orden': if (valor) await orden(JSON.parse(valor) as string[]); return true;
            }
            return false;
        },
        async mensaje(m: MensajeDia): Promise<boolean> {
            if (m.tipo === 'per-horario') { await previaHorario(m.valor ?? ''); return true; }
            if (m.tipo === 'per-skills') {
                if (form) form.destino = m.accion || form.destino;
                await cargarSkills(m.valor ?? '');
                return true;
            }
            return false;
        },
    };
    return seccion;
};
