// Los procesos que corren solos (`telar periodicos`), de esta máquina o de la de `[periodicos] en`: la lista, la
// ficha de uno con su log (⏎ correrlo ahora, 1 pausarlo, 2 editarlo, 3 borrarlo) y el formulario para crear o
// editar uno, con la previa de su horario y las skills de su carpeta.

import * as cli from '../../../cli';
import { esc, haceCorto, normalizar } from '../../../estilo';
import * as ui from '../../../web/ui';
import { atajo } from '../dia';
import type { MensajeDia } from '../vista';
import type { FabricaSeccion } from './seccion';

/** La marca, el color y la frase del estado de un proceso: pausado, corriendo, falló, bien. */
function estadoPeriodico(p: cli.JsonPeriodico): [string, string, string] {
    if (p.ultima.corriendo) return ['◐', 'azul', 'corriendo ahora'];
    if (!p.activo) return ['⏸', 'dim', 'pausado: no corre hasta que lo actives'];
    if (p.ultima.codigo !== undefined && p.ultima.codigo !== 0) return ['✗', 'rojo', `la última vez: ${p.ultima.resultado ?? 'falló'}`];
    if (p.ultima.inicio) return ['●', 'verde', `la última vez: ${p.ultima.resultado ?? 'bien'}`];
    return ['○', 'dim', 'todavía no ha corrido'];
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
    const d = new Date(iso);
    return `${['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'][d.getDay()]} ${d.getDate()} ${iso.slice(11, 16)}`;
}

const PRESETS: [string, string][] = [['0 9 * * *', 'todos los días 9:00'], ['0 9 * * 1-5', 'lun–vie 9:00'],
    ['0 8-20/2 * * *', 'cada 2 h, 8–20'], ['0 * * * *', 'cada hora'], ['*/30 * * * *', 'cada 30 min'],
    ['30 18 * * 5', 'viernes 18:30'], ['0 9 1 * *', 'el 1 de cada mes']];

interface Formulario { original: string; p: cli.JsonPeriodico; skills?: cli.JsonSkill[]; skillsDe?: string }

export const periodicos: FabricaSeccion = ctx => {
    /** la lista leída, y por qué no llegó */
    let datos: cli.JsonPeriodicos | undefined;
    let error = '';
    /** el abierto (con su log), si hay uno; el formulario de crear o editar, si está abierto */
    let abierto: { nombre: string; log: string } | undefined;
    let form: Formulario | undefined;
    const seVe = () => ctx.seVe('periodicos');

    const leer = async () => {
        if (!datos) ctx.pintar(['<div class="vacio">leyendo los procesos periódicos…</div>']);
        const r = await cli.periodicos();
        datos = r.datos ?? datos;
        error = r.datos ? '' : (r.error ?? 'no contestó');
        if (seVe()) seccion.pintar();
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
            const si = await ui.aviso(`¿Borrar el proceso «${args[1]}»? Deja de correr; el archivo anterior queda en periodicos.toml.anterior.`, 'Borrar');
            if (si !== 'Borrar') return;
        }
        const r = await cli.periodicosOrden(args);
        if (!r.datos) { void ui.aviso(`telar: ${r.error ?? 'no se pudo'}`); return; }
        ui.estado(`telar: ${r.datos.hecho}`, 5000);
        if (args[0] === 'borrar') abierto = undefined;
        await leer();
        if (abierto) {
            // «ahora» corre suelto: el log se relee en unos segundos, cuando ya escribió algo
            const nombre = abierto.nombre;
            setTimeout(() => { if (abierto?.nombre === nombre) void leer().then(() => ver(nombre)); }, args[0] === 'ahora' ? 4000 : 0);
        }
    };

    const abrirForm = async (original: string, p: cli.JsonPeriodico) => {
        form = { original, p };
        seccion.pintar();
        await Promise.all([previaHorario(p.cuando), cargarSkills(p.carpeta)]);
    };

    /** Uno nuevo: el formulario, con lo que suelen llevar los que ya hay (carpeta, argumentos). */
    const nuevo = () => {
        const parecido = (datos?.procesos ?? []).find(x => x.tipo === 'mensaje');
        return abrirForm('', {
            nombre: '', cuando: '0 9 * * 1-5', tipo: 'mensaje', comando: '', mensaje: '', hilo: '', max_abiertos: 1,
            argumentos: parecido?.argumentos ?? ['--permission-mode', 'acceptEdits'], carpeta: parecido?.carpeta ?? '',
            descripcion: '', activo: true, proxima: '', ultima: {},
        });
    };

    const editar = async (nombre: string) => {
        const p = datos?.procesos.find(x => x.nombre === nombre);
        if (p) await abrirForm(nombre, { ...p, argumentos: [...p.argumentos] });
    };

    const htmlSkills = () => {
        if (!form?.skills) return '<div class="dim">leyendo las skills de allá…</div>';
        if (!form.skills.length) return '<div class="dim">no hay skills en esa carpeta</div>';
        return form.skills.map(x => `<a class="skill" data-skill="${esc(x.nombre)}" data-texto="${esc(normalizar(`${x.nombre} ${x.descripcion}`))}" title="${esc(x.descripcion)}">`
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
        const d = JSON.parse(valor) as { nombre: string; descripcion: string; tipo: string; mensaje: string; comando: string;
            hilo: string; max: string; args: string; cuando: string; carpeta: string; activo: boolean };
        const nombre = f.original || d.nombre.trim();
        const args = d.args.split('\n').map(x => x.trim()).filter(Boolean);
        const lista = [f.original ? 'editar' : 'nuevo', nombre, '--cuando', d.cuando.trim(), '--descripcion', d.descripcion.trim(),
            '--carpeta', d.carpeta.trim()];
        if (d.tipo === 'mensaje') {
            lista.push('--mensaje', d.mensaje.trim(), '--hilo', d.hilo.trim(), '--max', d.max.trim() || '1');
            if (args.length) lista.push(...args.map(a => `--arg=${a}`));
            else if (f.original) lista.push('--sin-args');
        } else {
            lista.push('--comando', d.comando.trim());
            if (f.original) lista.push('--sin-args');
        }
        if (f.original) lista.push('--activo', d.activo ? 'si' : 'no');
        else if (!d.activo) lista.push('--pausado');
        ctx.parcial('per-error', '<span class="dim">guardando…</span>');
        const r = await cli.periodicosOrden(lista);
        if (!r.datos) { ctx.parcial('per-error', esc(r.error ?? 'no se pudo')); return; }
        ui.estado(`telar: ${r.datos.hecho}`, 5000);
        form = undefined;
        abierto = { nombre, log: '' };
        await leer();
        await ver(nombre);
    };

    const pintarLista = () => {
        const lista = datos?.procesos ?? [];
        const activos = lista.filter(p => p.activo).length;
        ctx.teclas.set('+', () => nuevo());
        const h = [`<div class="fila">${datos?.maquina ? `<b>${esc(datos.maquina)}</b> · ` : ''}`
            + `<span class="dim">${lista.length ? `${activos} de ${lista.length} activos` : 'ninguno'}</span>`
            + `<span class="der">${atajo('+', 'nuevo', 'per-nuevo', '', 'un proceso nuevo: un comando de shell o un prompt para el agente')}</span></div>`];
        if (error) h.push(`<div class="vacio falla">${esc(error)}</div>`);
        if (datos && !lista.length) h.push(`<div class="vacio">ninguno todavía · <a data-accion="per-nuevo">crear uno</a> · se guardan en ${esc(datos.archivo)}</div>`);
        for (const p of lista) {
            const [marca, color, dice] = estadoPeriodico(p);
            const que = p.tipo === 'mensaje' ? `✦ ${p.mensaje}` : p.comando;
            const cuando = p.activo ? (p.proxima ? `en ${enCuanto(p.proxima)}` : '—') : 'pausado';
            const ultima = p.ultima.inicio ? `hace ${haceCorto(p.ultima.inicio)}` : 'nunca';
            h.push(`<div class="fila clic per${p.activo ? '' : ' dim'}" data-accion="per-ver" data-valor="${esc(p.nombre)}" title="${esc(`${p.descripcion ? p.descripcion + '\n' : ''}${dice}\nclic: su ficha y su log`)}">`
                + `<span style="color: var(--${color})">${marca}</span><b>${esc(p.nombre)}</b>`
                + `<code class="dim">${esc(p.cuando)}</code><span class="que">${esc(que)}</span>`
                + `<span class="der dim">${esc(cuando)} · ${esc(ultima)}</span></div>`);
        }
        if (datos) h.push(`<div class="vacio dim">${esc(datos.archivo)}${datos.zona ? ` · hora de ${esc(datos.zona)}` : ''}</div>`);
        ctx.pintar(h);
    };

    const pintarFicha = () => {
        const p = datos?.procesos.find(x => x.nombre === abierto?.nombre);
        if (!abierto || !p) { abierto = undefined; pintarLista(); return; }
        const [marca, color, dice] = estadoPeriodico(p);
        const args = (a: string[]) => esc(JSON.stringify(a));
        const botones = [
            `<a class="atajo principal" data-accion="per-orden" data-valor="${args(['ahora', p.nombre])}"><kbd>⏎</kbd><span>correr ahora</span></a>`,
            `<a class="atajo" data-accion="per-orden" data-valor="${args([p.activo ? 'pausar' : 'activar', p.nombre])}"><kbd>1</kbd><span>${p.activo ? '⏸ pausar' : '▶ activar'}</span></a>`,
            `<a class="atajo" data-accion="per-editar" data-valor="${esc(p.nombre)}"><kbd>2</kbd><span>✎ editar</span></a>`,
            `<a class="atajo" data-accion="per-orden" data-valor="${args(['borrar', p.nombre])}"><kbd>3</kbd><span>✕ borrar</span></a>`,
            `<a class="atajo" data-accion="periodicos"><kbd>⎋</kbd><span>volver</span></a>`,
        ];
        ctx.teclas.set('⏎', () => orden(['ahora', p.nombre]));
        ctx.teclas.set('1', () => orden([p.activo ? 'pausar' : 'activar', p.nombre]));
        ctx.teclas.set('2', () => editar(p.nombre));
        ctx.teclas.set('3', () => orden(['borrar', p.nombre]));
        const filas: [string, string][] = [
            ['cuándo', `${p.cuando}${p.proxima ? ` · la próxima ${p.proxima.slice(5, 16).replace('T', ' ')} (en ${enCuanto(p.proxima)})` : ''}`],
            p.tipo === 'mensaje' ? ['prompt', p.mensaje] : ['comando', p.comando],
            ...(p.tipo === 'mensaje' ? [['hilo', `${p.hilo || p.nombre} · hasta ${p.max_abiertos} abierto(s)`] as [string, string]] : []),
            ...(p.argumentos.length ? [['argumentos', p.argumentos.join(' ')] as [string, string]] : []),
            ...(p.carpeta ? [['carpeta', p.carpeta] as [string, string]] : []),
            ['última', p.ultima.inicio ? `${p.ultima.inicio.slice(5, 16).replace('T', ' ')} · ${p.ultima.resultado ?? 'corriendo'}${p.ultima.hilo ? ` · «${p.ultima.hilo}»` : ''}` : 'nunca'],
        ];
        ctx.pintar([`<div id="ficha-per" style="--c: var(--${color})">`,
            `<div class="subcab"><b>${marca} ${esc(p.nombre)}</b><span class="der dim">${esc(dice)}</span></div>`,
            p.descripcion ? `<div class="sub-ficha dim">${esc(p.descripcion)}</div>` : '',
            `<div class="acciones-t">${botones.join('')}</div>`,
            ...filas.map(([k, v]) => `<div class="fila"><span class="dim" style="min-width: 11ch">${esc(k)}</span><span class="que">${esc(v)}</span></div>`),
            `<h2 class="sec">log</h2><pre class="log">${esc(abierto.log)}</pre></div>`]);
    };

    const pintarForm = (f: Formulario) => {
        const p = f.p;
        const campo = (etiqueta: string, html: string, ayuda = '') =>
            `<label class="campo"><span class="etiqueta">${esc(etiqueta)}</span><span class="control">${html}`
            + `${ayuda ? `<span class="ayuda dim">${esc(ayuda)}</span>` : ''}</span></label>`;
        ctx.pintar([`<div id="form-per" class="tipo-${p.tipo}">`,
            `<div class="subcab"><b>${f.original ? `editar «${esc(f.original)}»` : 'un proceso nuevo'}</b>${datos?.maquina ? `<span class="dim">${esc(datos.maquina)}</span>` : ''}</div>`,
            campo('nombre', `<input id="per-nombre" value="${esc(p.nombre)}" placeholder="resumen-diario" spellcheck="false"${f.original ? ' disabled' : ''}>`,
                f.original ? 'el nombre no se cambia' : 'minúsculas, números, - y _'),
            campo('para qué', `<input id="per-desc" value="${esc(p.descripcion)}" placeholder="en una línea, para acordarte">`),
            campo('qué hace', `<span class="opciones"><a class="opcion-t${p.tipo === 'mensaje' ? ' activa' : ''}" data-per-tipo="mensaje">✦ prompt para el agente</a>`
                + `<a class="opcion-t${p.tipo === 'comando' ? ' activa' : ''}" data-per-tipo="comando">$ comando de shell</a></span>`),
            `<div class="solo-mensaje">`,
            campo('skill', `<input id="per-skill-filtro" placeholder="buscar una skill…" spellcheck="false" autocomplete="off">`
                + `<div id="per-skills" class="skills">${htmlSkills()}</div>`, 'elegir una la pone como prompt; después puedes agregarle texto'),
            campo('prompt', `<textarea id="per-mensaje" rows="4" placeholder="/correo, o lo que quieras pedirle" spellcheck="false">${esc(p.mensaje)}</textarea>`),
            campo('hilo', `<input id="per-hilo" value="${esc(p.hilo)}" placeholder="${esc(p.nombre || 'el nombre del proceso')}">`, 'su nombre; se le agrega la fecha y la hora'),
            campo('abiertos', `<input id="per-max" type="number" min="1" value="${p.max_abiertos}">`, 'con tantos sin cerrar, esa vez no abre otro'),
            campo('argumentos', `<textarea id="per-args" rows="3" spellcheck="false">${esc(p.argumentos.join('\n'))}</textarea>`, 'para el agente, uno por línea (permisos, herramientas)'),
            `</div><div class="solo-comando">`,
            campo('comando', `<input id="per-comando" value="${esc(p.comando)}" placeholder="~/bin/resumen --corto" spellcheck="false">`, 'una línea de bash; su salida queda en el log'),
            `</div>`,
            campo('cuándo', `<input id="per-cuando" value="${esc(p.cuando)}" spellcheck="false">`
                + `<span class="presets">${PRESETS.map(([c, n]) => `<a data-per-horario="${esc(c)}" title="${esc(c)}">${esc(n)}</a>`).join('')}</span>`
                + `<div id="per-previa" class="dim">…</div>`, 'cron: minuto hora día-del-mes mes día-de-la-semana'),
            campo('carpeta', `<input id="per-carpeta" value="${esc(p.carpeta)}" placeholder="~ (el hogar)" spellcheck="false">`, 'dónde corre; las skills de la lista son las de ahí'),
            campo('activo', `<input id="per-activo" type="checkbox"${p.activo ? ' checked' : ''}>`),
            `<div id="per-error" class="falla"></div>`,
            `<div class="acciones-t fila-botones"><a class="atajo principal" data-accion="per-guardar"><kbd>⌘⏎</kbd><span>${f.original ? 'guardar' : 'crear'}</span></a>`
            + `<a class="atajo" data-accion="per-cancelar"><kbd>⎋</kbd><span>cancelar</span></a></div>`,
            '</div>']);
    };

    const seccion = {
        clave: 'periodicos',
        nombre: 'periódicos',
        ayuda: 'los procesos que corren solos: un comando, o un prompt para un agente',
        abrir: () => leer(),
        pintar(): void {
            ctx.teclas.clear();
            if (form) pintarForm(form);
            else if (abierto) pintarFicha();
            else pintarLista();
        },
        async accion(accion: string, valor: string): Promise<boolean> {
            switch (accion) {
                // ⎋ desde la ficha: a la lista
                case 'periodicos': abierto = undefined; form = undefined; await leer(); return true;
                case 'per-ver': if (valor) await ver(valor); return true;
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
            if (m.tipo === 'per-skills') { await cargarSkills(m.valor ?? ''); return true; }
            return false;
        },
    };
    return seccion;
};
