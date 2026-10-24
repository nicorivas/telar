// Todos los agentes residentes en una página (≡ en AGENTES, en la barra): cada uno con su ícono, su presencia (siempre,
// a pedido, no), si está vivo y qué hace, el peso de su conversación contra el tope de rotación, si está rotando, y sus
// encargos (los abiertos, con cancelar; los últimos cerrados, con su resultado). Desde aquí se le encarga algo, se
// rota su conversación con relevo o se va a su hilo. Los de otra máquina se le piden a esa (GET /agentes).

import * as ui from '../../web/ui';
import * as cli from '../../cli';
import { esc, fechaCorta } from '../../estilo';
import type { Accion, Pantalla, Tablero } from './pantalla';

const PRESENCIA: Record<string, string> = {
    siempre: 'siempre abierto', 'a-pedido': 'se abre cuando le llega algo', no: 'lo abres tú',
};
const ATENCION: Record<string, string> = { trabajando: '● trabajando', espera: '○ te espera', termino: '✓ terminó', ninguna: 'quieto' };
const mb = (b: number) => `${(b / (1024 * 1024)).toFixed(b < 10 * 1024 * 1024 ? 1 : 0).replace('.', ',')} MB`;

export class PantallaAgentes implements Pantalla {
    readonly pantallas = ['agentes'] as const;
    readonly conReloj = [] as const;
    private lista?: cli.JsonEstadoAgente[];
    private problemas: string[] = [];
    private error = '';

    readonly acciones: Record<string, Accion> = {
        'agentes-leer': () => this.leer(),
        'agente-encargar': v => v && this.encargar(v),
        'agente-rotar': v => v && this.rotar(v),
        'agente-ir': v => v && this.ir(v),
        'encargo-cancelar': v => v && this.cancelar(v),
        'encargo-ver': v => v && ui.abrirDireccion(v),
        'agente-archivar-abiertos': v => v && this.archivarAbiertos(v),
    };

    constructor(private readonly t: Tablero) {}

    async abrir(): Promise<void> {
        this.t.abrir();
        this.t.ir('agentes');
        this.pintar();
        await this.leer();
    }

    private async leer(): Promise<void> {
        const r = await cli.agentes();
        this.lista = r.datos?.agentes ?? this.lista;
        this.problemas = r.datos?.problemas ?? [];
        this.error = r.datos ? '' : (r.error ?? 'no pude leer los agentes');
        if (this.t.pantalla === 'agentes') this.pintar();
    }

    private de(clave: string) { return this.lista?.find(x => x.agente.clave === clave); }

    private async encargar(clave: string): Promise<void> {
        const x = this.de(clave);
        if (!x) return;
        const escrito = await ui.escribir({ titulo: `encargarle a ${x.agente.nombre}`,
            ayuda: `${x.agente.para || 'un encargo'} · queda como encargo:e-…, con su estado; el resultado te llega. ⌘⏎ envía.`,
            placeholder: '¿qué le encargas?' });
        if (!escrito?.texto.trim()) return;
        const r = await cli.encargar(x.agente.clave, escrito.texto);
        if (!r.datos) { void ui.falla(`telar: no se pudo: ${r.error ?? 'sin respuesta'}`); return; }
        void ui.estado(`telar: encargado a ${x.agente.nombre}`, 4000);
        await this.leer();
    }

    private async rotar(clave: string): Promise<void> {
        const x = this.de(clave);
        if (!x) return;
        const si = await ui.aviso(`¿Rotar la conversación de ${x.agente.nombre} ahora? Escribe su relevo, y la siguiente `
            + 'conversación empieza leyéndolo.', 'Rotar');
        if (si !== 'Rotar') return;
        const r = await cli.rotarAgente(x.agente.nombre, x.aqui ? '' : x.maquina);
        if (!r.datos) { void ui.falla(`telar: no se pudo: ${r.error ?? 'sin respuesta'}`); return; }
        void ui.estado(`telar: ${r.datos.hecho ?? 'pedido'}`, 5000);
        await this.leer();
    }

    private async ir(clave: string): Promise<void> {
        const x = this.de(clave);
        if (!x) return;
        await ui.irAHilo(x.agente.nombre, false, x.aqui ? '' : x.maquina);
    }

    /** Archivar (cerrando su tab) los hilos vivos que abrió un agente: su conversación queda, y se retoman cuando
     *  haga falta. */
    private async archivarAbiertos(clave: string): Promise<void> {
        const x = this.de(clave);
        const vivos = (x?.abrio ?? []).filter(h => h.vivo && !h.archivado);
        if (!x || !vivos.length) return;
        const si = await ui.aviso(`¿Archivar los ${vivos.length} hilos que abrió ${x.agente.nombre}? ${vivos.map(h => `«${h.hilo}»`).join(', ')}. `
            + 'Se cierra su tab y queda su conversación, para retomarlos.', 'Archivar');
        if (si !== 'Archivar') return;
        let mal = 0;
        for (const h of vivos) {
            const r = await cli.hilo('archivar', h.hilo, undefined, ['--cerrar']);
            if (!r.ok) mal++;
        }
        void (mal ? ui.falla(`telar: ${mal} no se pudieron archivar`) : ui.estado(`telar: archivados ${vivos.length}`, 4000));
        await this.leer();
    }

    private async cancelar(valor: string): Promise<void> {
        const [direccion, texto] = valor.split('|');
        const si = await ui.aviso(`¿Cancelar ${direccion}? «${(texto ?? '').slice(0, 120)}»`, 'Cancelar el encargo');
        if (si !== 'Cancelar el encargo') return;
        const r = await cli.accionObjeto(direccion, 'cancelar', { motivo: 'lo canceló su persona desde la página' });
        if (!r.datos) { void ui.falla(`telar: no se pudo: ${r.error ?? 'sin respuesta'}`); return; }
        void ui.estado(`telar: ${direccion} cancelado`, 4000);
        await this.leer();
    }

    private encargo(x: cli.JsonEstadoAgente, e: cli.JsonEncargoCorto): string {
        const direccion = `encargo:${e.id}${x.aqui ? '' : `@${x.maquina}`}`;
        const abierto = !['hecho', 'falló', 'cancelado'].includes(e.estado);
        const texto = (e.texto ?? '').split(/\s+/).join(' ');
        return `<div class="fila${abierto ? '' : ' dim'}"><a data-accion="encargo-ver" data-valor="${esc(direccion)}" title="abrir ${esc(direccion)}">${esc(e.estado)}</a>`
            + ` <span title="${esc(texto)}">${esc(texto.slice(0, 90))}</span>`
            + `<span class="der dim">${esc(e.de || '')}${e.creado ? ` · ${esc(fechaCorta(e.creado))}` : ''}`
            + (abierto ? ` · <a data-accion="encargo-cancelar" data-valor="${esc(`${direccion}|${texto}`)}" title="ya no hace falta">cancelar</a>` : '')
            + '</span></div>'
            + (!abierto && e.resultado ? `<div class="fila dim" style="padding-left:2ch">→ ${esc(e.resultado.slice(0, 160))}</div>` : '');
    }

    private abiertos(x: cli.JsonEstadoAgente): string {
        const abrio = x.abrio ?? [];
        if (!abrio.length) return '';
        const vivos = abrio.filter(h => h.vivo && !h.archivado);
        return `<div class="fila dim">abrió ${abrio.length}: ${abrio.map(h => `${h.vivo && !h.archivado ? '●' : '·'} ${esc(h.hilo)}`).join(', ')}`
            + (vivos.length ? ` · <a data-accion="agente-archivar-abiertos" data-valor="${esc(x.agente.clave)}" title="cerrar sus tabs y guardar su conversación">archivar los ${vivos.length} vivos</a>` : '')
            + '</div>';
    }

    pintar(): void {
        const h: string[] = ['<div class="subcab"><b>Agentes</b><span class="der"><a data-accion="agentes-leer" title="volver a leer">↻</a></span></div>'];
        if (this.error) h.push(`<div class="fila falla">${esc(this.error)}</div>`);
        for (const p of this.problemas) h.push(`<div class="fila dim">${esc(p)}</div>`);
        if (!this.lista) h.push('<div class="fila dim">leyendo…</div>');
        for (const x of this.lista ?? []) {
            const a = x.agente;
            const estado = x.sin_noticias ? 'sin noticias de su máquina' : x.vivo ? (ATENCION[x.atencion] ?? x.atencion) : 'sin sesión';
            const c = x.conversacion;
            const pct = c?.tope ? Math.min(100, Math.round((c.peso / c.tope) * 100)) : 0;
            h.push('<div class="item-pag">'
                + `<div class="fila"><b>${esc(a.icono ?? '')} ${esc(a.nombre)}</b><span class="dim"> · ${esc(PRESENCIA[a.presencia ?? 'a-pedido'] ?? '')}`
                + `${x.maquina ? ` · en ${esc(x.maquina)}` : ''}${a.publico ? ' · ◇ público' : ''}</span>`
                + `<span class="der">${esc(estado)}</span></div>`
                + (a.para ? `<div class="fila dim">${esc(a.para)}</div>` : '')
                + (c && c.peso ? `<div class="fila dim">conversación ${esc(mb(c.peso))}${c.tope ? ` de ${esc(mb(c.tope))} (${pct} %)` : ''}`
                    + `${x.rotacion ? ` · <span style="color: var(--amarillo)">↻ rotando (${esc(x.rotacion)})</span>` : ''}`
                    + `${x.relevo ? ` · último relevo ${esc(fechaCorta(x.relevo.cuando))}` : ''}</div>` : '')
                + `<div class="fila"><a data-accion="agente-encargar" data-valor="${esc(a.clave)}">encargar</a>`
                + ` · <a data-accion="agente-ir" data-valor="${esc(a.clave)}">ir a su hilo</a>`
                + (x.vivo ? ` · <a data-accion="agente-rotar" data-valor="${esc(a.clave)}" title="que escriba su relevo y empiece otra conversación">rotar con relevo</a>` : '')
                + '</div>'
                + this.abiertos(x)
                + x.encargos.map(e => this.encargo(x, e)).join('')
                + '</div>');
        }
        if (this.lista && !this.lista.length) h.push('<div class="fila dim">no hay agentes: [agentes] carpeta en la configuración</div>');
        this.t.pintar(h);
    }
}
