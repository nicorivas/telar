// Los módulos, en una página: arriba los disponibles que no tienes, abajo los instalados. Instalados: cada uno con lo que aporta, dónde está su carpeta, de dónde vino (su
// repositorio y versión, el catálogo, o «a mano»/«enlazado»), lo que pide, y encenderlo, apagarlo, actualizarlo o
// quitarlo. Disponibles: lo que hay en los catálogos (el oficial, el del equipo, otros), para buscar e instalar.
// Desde aquí se instala solo lo de un catálogo revisado o del equipo; uno sin revisar, desde la terminal.

import * as cli from '../../../cli';
import { esc } from '../../../estilo';
import * as ui from '../../../web/ui';
import type { FabricaSeccion } from './seccion';

const CONFIANZA: Record<string, [string, string]> = {
    oficial: ['revisado', 'del catálogo de telar: lo revisó quien mantiene telar'],
    equipo: ['del equipo', 'del catálogo de tu equipo (.telar/catalogo.toml de su repositorio)'],
    'sin revisar': ['sin revisar', 'de un catálogo sin revisar o suelto: se instala desde la terminal, viendo lo que corre'],
};

export const modulos: FabricaSeccion = ctx => {
    let instalados: cli.JsonModuloInstalado[] | undefined;
    let disponibles: cli.JsonModuloDisponible[] | undefined;
    let problemas: string[] = [];
    let buscar = '';
    let error = '';
    let trabajando = '';

    const leer = async (forzar = false) => {
        const [a, b] = await Promise.all([cli.modulosInstalados(), cli.modulosCatalogo(forzar)]);
        instalados = a.datos?.modulos ?? instalados;
        disponibles = b.datos?.disponibles ?? disponibles;
        problemas = b.datos?.problemas ?? [];
        error = a.datos ? '' : (a.error ?? 'no pude leer los módulos');
        if (ctx.seVe('modulos')) seccion.pintar();
    };

    const hacer = async (accion: 'instalar' | 'actualizar' | 'activar' | 'desactivar' | 'quitar', nombre: string) => {
        trabajando = nombre;
        seccion.pintar();
        const r = await cli.modulosAccion(accion, nombre);
        trabajando = '';
        if (!r.datos) void ui.falla(`telar: no se pudo: ${r.error ?? 'sin respuesta'}`);
        else void ui.estado(`telar: ${(r.datos.salida || `${accion} ${nombre}`).split('\n')[0]}`, 5000);
        await ctx.releerConfig();
        await leer();
    };

    const instalar = async (x: cli.JsonModuloDisponible) => {
        const pide = x.permisos ? Object.entries(x.permisos).filter(([k, v]) => k !== 'otros' && v && (!Array.isArray(v) || v.length))
            .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : String(v)}`).join(' · ') : 'no dice';
        const si = await ui.aviso(`¿Instalar ${x.nombre} ${x.version} (${CONFIANZA[x.confianza]?.[0] ?? x.confianza})? `
            + `Lo que pide: ${pide || 'nada fuera de su carpeta'}. telar todavía no lo hace cumplir: corre con tus permisos.`, 'Instalar');
        if (si === 'Instalar') await hacer('instalar', x.nombre);
    };

    const quitar = async (nombre: string) => {
        const si = await ui.aviso(`¿Quitar ${nombre}? Se desanota y se borra la carpeta que bajó telar. Para dejarlo instalado sin usarlo, apágalo.`, 'Quitar');
        if (si === 'Quitar') await hacer('quitar', nombre);
    };

    const origen = (m: cli.JsonModuloInstalado) => {
        if (m.a_mano) return 'a mano en la configuración';
        const de = m.catalogo ? `del catálogo ${m.catalogo}` : m.enlazado ? 'enlazado (una carpeta en desarrollo)' : 'suelto';
        const repo = m.fuente ? (/^https?:\/\//.test(m.fuente) ? `<a href="${esc(m.fuente)}" target="_blank" rel="noopener">${esc(m.fuente)}</a>` : esc(m.fuente)) : '';
        return `${esc(de)}${repo ? ` · ${repo}` : ''}${m.ref || m.version ? ` @ ${esc(m.ref || m.version)}` : ''}${m.instalado ? ` · desde ${esc(m.instalado)}` : ''}`;
    };

    const filaInstalado = (m: cli.JsonModuloInstalado) => {
        const ocupado = trabajando === m.nombre;
        const acciones = ocupado ? '<span class="dim">…</span>' : [
            m.a_mano ? '' : m.activo
                ? `<a data-accion="mod-desactivar" data-valor="${esc(m.nombre)}" title="apagarlo sin desinstalarlo: no aporta nada hasta encenderlo">apagar</a>`
                : `<a data-accion="mod-activar" data-valor="${esc(m.nombre)}" title="encenderlo de nuevo">encender</a>`,
            m.a_mano || !m.activo ? '' : `<a data-accion="mod-actualizar" data-valor="${esc(m.nombre)}" title="${m.nueva ? `a la ${esc(m.nueva)} del catálogo` : 'traer lo último y correr su [instalar]'}">${m.nueva ? `actualizar a ${esc(m.nueva)}` : 'actualizar'}</a>`,
            m.a_mano ? '' : `<a data-accion="mod-quitar" data-valor="${esc(m.nombre)}">quitar</a>`,
        ].filter(Boolean).join(' · ');
        const marca = m.confianza ? CONFIANZA[m.confianza] : undefined;
        return `<div class="item-pag${m.activo ? '' : ' dim'}">`
            + `<div class="fila"><b>${esc(m.nombre)}</b>${m.activo ? '' : '<span class="dim"> · apagado</span>'}`
            + (marca ? `<span class="dim" title="${esc(marca[1])}"> · ${esc(marca[0])}</span>` : '')
            + `<span class="der">${acciones}</span></div>`
            + (m.descripcion ? `<div class="fila">${esc(m.descripcion)}</div>` : '')
            + (m.aporta.length ? `<div class="fila dim">aporta: ${esc(m.aporta.join(', '))}</div>` : '')
            + `<div class="fila dim">carpeta: ${esc(m.carpeta)}</div>`
            + `<div class="fila dim">origen: ${origen(m)}</div>`
            + (m.pide.length ? `<div class="fila dim">pide: ${esc(m.pide.join('; '))}</div>` : '')
            + '</div>';
    };

    const filaDisponible = (x: cli.JsonModuloDisponible) => {
        const marca = CONFIANZA[x.confianza] ?? [x.confianza, ''];
        const accion = x.instalado ? '<span class="dim">instalado</span>'
            : !x.le_sirve ? `<span class="dim">pide telar ${esc(x.telar)}</span>`
            : x.confianza === 'sin revisar' ? `<span class="dim" title="${esc(marca[1])}">telar modulos instalar ${esc(x.nombre)}</span>`
            : trabajando === x.nombre ? '<span class="dim">instalando…</span>'
            : `<a data-accion="mod-instalar" data-valor="${esc(x.nombre)}">instalar</a>`;
        return '<div class="item-pag">'
            + `<div class="fila"><b>${esc(x.nombre)}</b><span class="dim" title="${esc(marca[1])}"> · ${esc(marca[0])} · ${esc(x.version)}${x.autor ? ` · ${esc(x.autor)}` : ''}</span>`
            + `<span class="der">${accion}</span></div>`
            + `<div class="fila">${esc(x.descripcion)}</div>`
            + (x.etiquetas.length ? `<div class="fila dim">${esc(x.etiquetas.join(', '))}</div>` : '')
            + `<div class="fila dim"><a href="${esc(x.fuente)}" target="_blank" rel="noopener">${esc(x.fuente)}</a> · de ${esc(x.catalogo)}</div>`
            + '</div>';
    };

    const seccion = {
        clave: 'modulos',
        nombre: 'módulos',
        ayuda: 'los instalados (encender, apagar, de dónde vienen) y los disponibles en los catálogos',
        abrir: () => { seccion.pintar(); return leer(); },
        pintar(): void {
            // una sola página, sin pestañas: primero lo que se puede instalar (es lo que no se ve si no se busca),
            // después lo instalado. Con pestañas, quien abría ⚙ módulos veía sus instalados y no sabía que había más
            const t = buscar.trim().toLowerCase();
            const porInstalar = (disponibles ?? []).filter(x => !x.instalado);
            const lista = porInstalar.filter(x => !t || [x.nombre, x.descripcion, x.autor, ...x.etiquetas].join(' ').toLowerCase().includes(t));
            const h = [`<div class="fila"><b>para instalar</b>${disponibles ? ` <span class="dim">${porInstalar.length}</span>` : ''}`
                + '<span class="der"><a data-accion="mod-leer" title="volver a leer, y bajar los catálogos ahora">↻ buscar ahora</a></span></div>'];
            if (error) h.push(`<div class="fila falla">${esc(error)}</div>`);
            if (porInstalar.length > 4 || buscar) {
                h.push(`<div class="fila"><input id="buscar-mod" type="text" placeholder="buscar por nombre, descripción o etiqueta" value="${esc(buscar)}" spellcheck="false" autocomplete="off"></div>`);
            }
            if (!disponibles) h.push('<div class="fila dim">leyendo los catálogos…</div>');
            else if (!lista.length) h.push(`<div class="fila dim">${t ? 'nada calza' : porInstalar.length < disponibles.length ? 'ya tienes todo lo de los catálogos' : 'los catálogos están vacíos'}</div>`);
            for (const x of lista) h.push(filaDisponible(x));
            for (const p of problemas) h.push(`<div class="fila dim">! ${esc(p)}</div>`);
            h.push('<div class="fila dim">para escribir y publicar uno: <code>telar modulos nuevo</code>, y la skill /modulos</div>');
            h.push('<div class="sep-pag"></div>');
            h.push(`<div class="fila"><b>instalados</b>${instalados ? ` <span class="dim">${instalados.length}</span>` : ''}</div>`);
            if (!instalados) h.push('<div class="fila dim">leyendo…</div>');
            else if (!instalados.length) h.push('<div class="fila dim">ninguno todavía</div>');
            for (const m of instalados ?? []) h.push(filaInstalado(m));
            ctx.pintar(h);
            const campo = document.getElementById('buscar-mod') as HTMLInputElement | null;
            campo?.addEventListener('input', () => {
                buscar = campo.value;
                const pos = campo.selectionStart;
                seccion.pintar();
                const nuevo = document.getElementById('buscar-mod') as HTMLInputElement | null;
                nuevo?.focus();
                if (nuevo && pos !== null) nuevo.setSelectionRange(pos, pos);
            });
        },
        async accion(accion: string, valor: string): Promise<boolean> {
            switch (accion) {
                case 'mod-leer': await leer(true); return true;
                case 'mod-activar': await hacer('activar', valor); return true;
                case 'mod-desactivar': await hacer('desactivar', valor); return true;
                case 'mod-actualizar': await hacer('actualizar', valor); return true;
                case 'mod-quitar': await quitar(valor); return true;
                case 'mod-instalar': {
                    const x = disponibles?.find(y => y.nombre === valor);
                    if (x) await instalar(x);
                    return true;
                }
            }
            return false;
        },
    };
    return seccion;
};
