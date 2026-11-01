// Los glifos de risografía (web/glifos), todo lo que se puede cambiar, en dos partes:
//
//   - lo del modo puesto: si hay glifos, qué estilo usa, si la barra lleva glifos y dónde va el campo en cada pantalla,
//     con su intensidad. Son ajustes del modo (web/modos.ts): un cambio vale hasta cambiar de modo, y «guardar en este
//     modo» lo escribe en `[modos.<n>]`.
//   - el estilo: las tintas, la forma y el movimiento del campo, su vida, el gesto de cada pieza, el glifo de cada hilo
//     y sus estados (`[glifos.<estilo>]`, telar.glifos). Se afina con los controles y se ve al tiro, en la vista previa
//     y en la página; «guardar el estilo» lo escribe.

import { esc } from '../../../estilo';
import * as glifos from '../../../web/glifos';
import * as modos from '../../../web/modos';
import * as ui from '../../../web/ui';
import type { FabricaSeccion } from './seccion';

const { estilo } = glifos;

/** Las claves de los ajustes del modo que son de los glifos. */
const DEL_MODO = ['glifos', 'estilo', 'iconos', 'campo'];
const ESTADOS: [glifos.Estado, string, string][] = [['trabajando', 'trabajando', 'azul'], ['espera', 'te espera', 'amarillo'],
    ['termino', 'terminó', 'verde'], ['visto', 'ya visto', 'dim'], ['ninguna', 'sin atención', 'dim']];
const LUGARES: glifos.Lugar[] = ['nada', 'banda', 'fondo'];

/** `campo` partido por pantalla: «ahora=banda, *=fondo 0.15» → {ahora: {banda, 1}, '*': {fondo, .15}}. */
function partir(texto: string): Map<string, glifos.Ubicacion> {
    const m = new Map<string, glifos.Ubicacion>();
    for (const parte of texto.split(',')) {
        const x = /^\s*([^=\s]+)\s*=\s*(banda|fondo|nada)(?:\s+([\d.]+))?\s*$/.exec(parte);
        if (x) m.set(x[1], { lugar: x[2] as glifos.Lugar, intensidad: Number(x[3] ?? (x[2] === 'fondo' ? .15 : 1)) });
    }
    return m;
}
function juntar(m: Map<string, glifos.Ubicacion>): string {
    const conComodin = m.has('*') && m.get('*')!.lugar !== 'nada';
    return [...m].filter(([k, u]) => u.lugar !== 'nada' || (k !== '*' && conComodin))
        .map(([k, u]) => `${k}=${u.lugar}${u.lugar !== 'nada' && u.intensidad !== (u.lugar === 'fondo' ? .15 : 1) ? ` ${u.intensidad}` : ''}`).join(', ');
}

/** Cuántos decimales muestra un rango con ese paso. */
const decimales = (paso: number) => (paso >= 1 ? 0 : paso >= .1 ? 1 : 2);

export const glifosSeccion: FabricaSeccion = ctx => {
    const pintarSiSeVe = () => { if (ctx.seVe('glifos')) seccion.pintar(); };
    modos.alCambiar(pintarSiSeVe);
    /** el nombre de muestra de la vista previa: el de un hilo cualquiera da su glifo */
    let muestra = 'telar';
    /** el estilo que se afina: el del modo puesto, salvo que se elija otro */
    let afinando = '';
    const cual = () => (afinando && estilo.lista().includes(afinando) ? afinando : estilo.puesto());

    const opcion = (accion: string, valor: string, texto: string, activa: boolean, ayuda = '') =>
        `<a class="${activa ? 'si' : ''}" data-accion="${accion}" data-valor="${esc(valor)}"${ayuda ? ` title="${esc(ayuda)}"` : ''}>${esc(texto)}</a>`;

    /** Lo de los glifos que se cambió a mano en el modo puesto (el resto de sus cambios, ⚙ modos). */
    const cambiados = () => Object.keys(modos.cambiosAMano()).filter(k => DEL_MODO.includes(k));

    const delModo = (h: string[]) => {
        const m = modos.puesto();
        const prendidos = glifos.prendidos();
        h.push(`<h2>en el modo «${esc(m.nombre)}»<small>cada modo dice lo suyo; el modo se elige con su ícono, arriba</small></h2>`);
        h.push(`<div class="fila">glifos<span class="der">${opcion('gl-modo', 'glifos=no', 'apagados', !prendidos, 'la página como siempre')} · `
            + `${opcion('gl-modo', 'glifos=si', 'prendidos', prendidos)}</span></div>`);
        if (!prendidos) {
            h.push('<div class="fila dim">apagados: ni campo ni glifos en la barra. Lo de abajo se puede afinar igual, y se ve en la vista previa</div>');
        } else {
            const iconos = modos.valor('iconos') === 'glifos';
            h.push(`<div class="fila">íconos de los hilos<span class="der">${opcion('gl-modo', 'iconos=simbolos', 'símbolos', !iconos, 'los de siempre')} · `
                + `${opcion('gl-modo', 'iconos=glifos', 'glifos', iconos, 'el glifo de cada hilo, con su estado; y su sello en la ficha')}</span></div>`);
            h.push(`<div class="fila">estilo<span class="der">${estilo.lista().map(e => opcion('gl-modo', `estilo=${e}`, e, estilo.puesto() === e)).join(' · ')}</span></div>`);
            // el campo, pantalla por pantalla: dónde va y con qué intensidad
            const m2 = partir(String(modos.valor('campo') ?? ''));
            const comodin = m2.get('*');
            const pantallas: [string, string][] = [...ctx.dashboard.pestanas().map(p => [p.clave, p.nombre] as [string, string]),
                ['config', 'configuración'], ['conversacion', 'conversación de un hilo'], ['lectura', 'lectura de un hilo'], ['*', 'las demás']];
            h.push('<div class="fila dim">el campo, por pantalla: una banda arriba, detrás de todo, o nada; y su intensidad</div>');
            h.push('<div class="gl-pantallas">');
            for (const [clave, nombre] of pantallas) {
                const propio = m2.get(clave);
                const u = propio ?? (clave === '*' ? undefined : comodin) ?? { lugar: 'nada' as glifos.Lugar, intensidad: 1 };
                const heredado = !propio && clave !== '*' && !!comodin;
                h.push(`<span class="${heredado ? 'dim' : ''}">${esc(nombre)}${heredado ? ' · como las demás' : ''}</span>`
                    + `<span>${LUGARES.map(l => opcion('gl-campo', `${clave}=${l}`, l, u.lugar === l)).join(' · ')}</span>`
                    + (u.lugar !== 'nada'
                        ? `<input type="range" min="0.05" max="1" step="0.01" value="${u.intensidad}" data-pantalla="${esc(clave)}" title="intensidad">`
                            + `<output>${u.intensidad.toFixed(2)}</output>`
                        : '<span></span><span></span>'));
            }
            h.push('</div>');
        }
        const n = cambiados().length;
        if (n) {
            h.push(`<div class="fila gl-afinado">${n === 1 ? 'un cambio' : `${n} cambios`} en «${esc(m.nombre)}», hasta cambiar de modo<span class="der">`
                + '<a data-accion="gl-modo-guardar" title="dejarlos escritos en este modo">guardar en este modo</a> · '
                + '<a data-accion="gl-modo-descartar" title="volver a lo que dice el modo">descartar</a></span></div>');
        }
    };

    const delEstilo = (h: string[]) => {
        const e = cual();
        const vs = estilo.valores(e);
        const borrador = estilo.enBorrador() === e;
        h.push(`<h2>estilo «${esc(e)}»<small>${e === estilo.puesto() ? 'el del modo puesto' : 'no es el del modo puesto'}; lo que mueves se ve al tiro</small></h2>`);
        if (estilo.lista().length > 1) {
            h.push(`<div class="fila">afinar<span class="der">${estilo.lista().map(x => opcion('gl-afinar', x, x, x === e)).join(' · ')}</span></div>`);
        }
        // la vista previa: un trozo del campo y el glifo de un nombre en cada estado
        h.push('<div class="gl-previa"><canvas id="gl-campo" aria-hidden="true"></canvas><div class="gl-estados">'
            + ESTADOS.map(([est, nombre, color]) => `<div>${glifos.htmlHilo(muestra, est, 38, e)}<span class="${color}">${esc(nombre)}</span></div>`).join('')
            + `</div><div class="fila dim">el glifo de <input id="gl-muestra" type="text" value="${esc(muestra)}" spellcheck="false" autocomplete="off" title="el nombre de un hilo: su glifo">`
            + '</div></div>');
        h.push(`<div class="fila" id="gl-estado">${filaEstado(e, borrador)}</div>`);
        // los parámetros, por grupo
        let grupo = '';
        for (const p of estilo.parametros()) {
            if (p.grupo !== grupo) {
                if (grupo) h.push('</div>');
                grupo = p.grupo;
                h.push(`<div class="fila dim gl-grupo">${esc(grupo)}</div><div class="gl-params">`);
            }
            const v = vs[p.clave] ?? p.base;
            const fuera = v !== p.base ? ' cambiado' : '';
            if (p.opciones) {
                h.push(`<label for="gl-${p.clave}" class="${fuera}" title="${esc(p.ayuda)}">${esc(p.nombre)}</label>`
                    + `<select id="gl-${p.clave}" data-param="${p.clave}">${p.opciones.map(o => `<option${o === v ? ' selected' : ''}>${esc(o)}</option>`).join('')}</select><span></span>`);
            } else {
                const d = decimales(p.paso ?? .01);
                h.push(`<label for="gl-${p.clave}" class="${fuera}" title="${esc(p.ayuda)}">${esc(p.nombre)}</label>`
                    + `<input id="gl-${p.clave}" type="range" min="${p.minimo}" max="${p.maximo}" step="${p.paso}" value="${v}" data-param="${p.clave}">`
                    + `<output>${Number(v).toFixed(d)}</output>`);
            }
        }
        if (grupo) h.push('</div>');
        if (!estilo.parametros().length) h.push('<div class="fila dim">leyendo los parámetros…</div>');
    };

    /** Si el estilo está afinado sin guardar, y lo que se puede hacer con él. */
    const filaEstado = (e: string, borrador: boolean) =>
        `${borrador ? '<span class="gl-afinado">afinado, sin guardar</span>' : '<span class="dim">guardado</span>'}<span class="der">`
        + `${borrador ? '<a data-accion="gl-guardar" title="escribirlo en la configuración">guardar el estilo</a> · <a data-accion="gl-descartar">descartar</a> · ' : ''}`
        + '<a data-accion="gl-fabrica" title="sus valores, los de fábrica (se ve al tiro; guardar lo deja)">de fábrica</a> · '
        + '<a data-accion="gl-nuevo" title="otro estilo, con estos valores">estilo nuevo…</a>'
        + `${e !== 'base' ? ` · <a data-accion="gl-borrar" title="quitar [glifos.${esc(e)}]">borrar</a>` : ''}</span>`;

    /** Lo que no son clics: los rangos, las listas y el nombre de muestra. */
    const atar = () => {
        const raiz = document.getElementById('gl-raiz');
        if (!raiz) return;
        const cv = raiz.querySelector<HTMLCanvasElement>('#gl-campo');
        if (cv) glifos.muestra(cv, cual());
        glifos.pintarEn(raiz);
        for (const inp of raiz.querySelectorAll<HTMLInputElement | HTMLSelectElement>('[data-param]')) {
            const p = estilo.parametros().find(x => x.clave === inp.dataset.param);
            if (!p) continue;
            const salida = inp.nextElementSibling;
            inp.addEventListener('input', () => {
                const v = p.opciones ? inp.value : Number(inp.value);
                if (salida?.tagName === 'OUTPUT') salida.textContent = Number(v).toFixed(decimales(p.paso ?? .01));
                estilo.probar(cual(), p.clave, v);
                // sin repintar la sección (se perdería el control que se arrastra): solo la fila de su estado y la marca
                const fila = raiz.querySelector('#gl-estado');
                if (fila) fila.innerHTML = filaEstado(cual(), true);
                inp.previousElementSibling?.classList.toggle('cambiado', v !== p.base);
            });
        }
        // la intensidad del campo de una pantalla: se cambia al soltar (repinta la sección)
        for (const inp of raiz.querySelectorAll<HTMLInputElement>('input[data-pantalla]')) {
            inp.addEventListener('input', () => { const o = inp.nextElementSibling; if (o) o.textContent = Number(inp.value).toFixed(2); });
            inp.addEventListener('change', () => {
                const m = partir(String(modos.valor('campo') ?? ''));
                const clave = inp.dataset.pantalla ?? '';
                const u = m.get(clave) ?? m.get('*');
                if (!u) return;
                m.set(clave, { lugar: u.lugar, intensidad: Number(inp.value) });
                modos.poner('campo', juntar(m));
            });
        }
        const nombre = raiz.querySelector<HTMLInputElement>('#gl-muestra');
        nombre?.addEventListener('change', () => {
            muestra = nombre.value.trim() || 'telar';
            for (const c of raiz.querySelectorAll<HTMLCanvasElement>('.gl-estados canvas')) c.dataset.nombre = muestra;
            glifos.pintarEn(raiz);
        });
    };

    const seccion = {
        clave: 'glifos',
        nombre: 'glifos',
        ayuda: 'los glifos de risografía: si hay, dónde va el campo, y su estilo (tintas, vida, gestos, el glifo de cada hilo)',
        abrir: async () => { seccion.pintar(); await estilo.leer(true); pintarSiSeVe(); },
        pintar(): void {
            const h: string[] = ['<div id="gl-raiz">'];
            delModo(h);
            delEstilo(h);
            h.push('</div>');
            ctx.pintar(h);
            atar();
        },
        async accion(accion: string, valor: string): Promise<boolean> {
            switch (accion) {
                case 'gl-modo': {
                    const [k, v] = valor.split('=');
                    if (k && v !== undefined) modos.poner(k, v);
                    return true;
                }
                case 'gl-campo': {
                    const [clave, lugar] = valor.split('=');
                    const m = partir(String(modos.valor('campo') ?? ''));
                    const antes = m.get(clave);
                    m.set(clave, { lugar: lugar as glifos.Lugar, intensidad: antes && antes.lugar === lugar ? antes.intensidad : lugar === 'fondo' ? .15 : 1 });
                    modos.poner('campo', juntar(m));
                    return true;
                }
                case 'gl-modo-guardar': {
                    const error = await modos.guardarCambios();
                    if (error) void ui.falla(`telar: no se pudo: ${error}`);
                    else void ui.estado(`telar: guardado en «${modos.puesto().nombre}»`, 4000);
                    return true;
                }
                case 'gl-modo-descartar': modos.cambiar(modos.puesto().clave); return true;
                case 'gl-afinar': afinando = valor; pintarSiSeVe(); return true;
                case 'gl-guardar': {
                    const error = await estilo.guardar(cual());
                    if (error) void ui.falla(`telar: no se pudo: ${error}`);
                    else void ui.estado(`telar: estilo «${cual()}» guardado`, 4000);
                    pintarSiSeVe();
                    return true;
                }
                case 'gl-descartar': estilo.descartar(); pintarSiSeVe(); return true;
                case 'gl-fabrica': {
                    estilo.probarTodos(cual(), Object.fromEntries(estilo.parametros().map(p => [p.clave, p.base])));
                    pintarSiSeVe();
                    return true;
                }
                case 'gl-nuevo': {
                    const nombre = (await ui.campo({
                        titulo: 'Estilo nuevo', placeholder: 'tenue',
                        ayuda: `con los valores de «${cual()}». En minúsculas: letras, números y guiones. Un modo lo usa con «estilo».`,
                        validar: t => /^[a-z][a-z0-9-]{0,23}$/.test(t.trim()) ? undefined : 'en minúsculas: letras, números y guiones',
                    }))?.trim();
                    if (!nombre) return true;
                    const error = await estilo.guardar(cual(), nombre);
                    if (error) void ui.falla(`telar: no se pudo: ${error}`);
                    else { afinando = nombre; void ui.estado(`telar: estilo «${nombre}» guardado`, 4000); }
                    pintarSiSeVe();
                    return true;
                }
                case 'gl-borrar': {
                    const e = cual();
                    if (await ui.aviso(`¿Borrar el estilo «${e}»? Los modos que lo usen vuelven a «base».`, 'Borrar') !== 'Borrar') return true;
                    const error = await estilo.borrar(e);
                    if (error) void ui.falla(`telar: no se pudo: ${error}`);
                    afinando = '';
                    pintarSiSeVe();
                    return true;
                }
            }
            return false;
        },
    };
    return seccion;
};
