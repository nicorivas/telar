// La página de una sección, un agente o una app (`telar seccion`, `telar app`): la abre su fila en la barra, y se
// dibuja como cualquier página de bloques (pagina.ts). Un ítem con conversación la abre entera, aquí mismo.

import * as ui from '../../web/ui';
import * as cli from '../../cli';
import { esc } from '../../estilo';
import { modelo } from '../../modelo';
import { mdSimple } from './pagina';
import type { Accion, Pantalla, Tablero } from './pantalla';

/** Una hora ISO en la hora local, HH:MM. */
function horaLocal(iso: string): string {
    const t = Date.parse(iso);
    return Number.isNaN(t) ? '' : new Date(t).toTimeString().slice(0, 5);
}

export class PantallaSecciones implements Pantalla {
    readonly pantallas = ['seccion', 'conversacion'] as const;
    /** no dependen del reloj: el refresco del día no las pisa */
    readonly conReloj = [] as const;
    /** la sección abierta y su página; la conversación que se está leyendo */
    private clave = '';
    private pagina?: cli.JsonPagina;
    private charla?: cli.JsonConversacion;

    readonly acciones: Record<string, Accion> = {
        'seccion': v => v && this.abrir(v),
        'recargar-seccion': () => { this.pagina = undefined; if (this.clave) return this.abrir(this.clave); },
        'volver-seccion': () => {
            if (!this.clave || !this.pagina) return this.t.accion('ahora');
            this.t.ir('seccion');
            this.pintarSeccion();
        },
        'conversacion': v => v && this.abrirConversacion(v),
        'retomar-charla': () => {
            if (!this.charla?.hilo) return;
            const vivo = modelo.porNombre(this.charla.hilo)?.vivo;
            return ui.orden(vivo ? 'telar.ir' : 'telar.retomar', { hilo: this.charla.hilo });
        },
    };

    constructor(private readonly t: Tablero) {}

    /** La app que se ve («app:<clave>»), o "": la barra marca su fila. */
    get app(): string {
        return this.t.pantalla === 'seccion' && this.clave.startsWith('app:') ? this.clave.slice(4) : '';
    }

    /** Una conversación es de su sección: se marca la de ella. */
    pestanaMarcada(): string { return `seccion:${this.clave}`; }

    /** La página, con lo que ya se leyó (un panel recién montado pierde lo que se le mandó antes de estar listo). */
    pintar(): void { if (this.t.pantalla === 'seccion') this.pintarSeccion(); }

    /** La página de una sección: la pide a `telar seccion`, que corre su `home`. Abre el
     *  panel si hace falta; el refresco del día no la pisa (ver `render`). */
    async abrir(clave: string): Promise<void> {
        this.t.abrir();
        const antes = this.app;
        this.t.ir('seccion');
        if (this.clave !== clave) { this.clave = clave; this.pagina = undefined; }
        if (antes !== this.app) this.t.alCambiarFoco?.(true);
        // «app:<clave>» es una app (`telar app`); lo demás, una sección o un agente (`telar seccion`)
        const app = clave.startsWith('app:') ? clave.slice(4) : '';
        const nombre = (app ? modelo.apps.find(a => a.clave === app)?.nombre : modelo.secciones.find(s => s.clave === clave)?.nombre) ?? clave;
        if (!this.pagina) this.t.pintar([`<div class="subcab"><b>${esc(nombre)}</b></div>`, '<div class="fila dim">leyendo…</div>']);
        const r = app ? await cli.app(app) : await cli.seccion(clave);
        await this.t.paginas.precargar(r.datos?.bloques);
        if (this.t.pantalla !== 'seccion' || this.clave !== clave) return;
        if (!r.datos) {
            this.t.pintar([`<div class="subcab"><b>${esc(nombre)}</b></div>`,
                `<div class="fila falla">${esc(r.error ?? 'el home no contestó')}</div>`]);
            return;
        }
        this.pagina = r.datos;
        this.pintarSeccion();
    }

    private pintarSeccion(): void {
        const p = this.pagina;
        if (!p) return;
        const h: string[] = [`<div class="subcab"><b>${esc(p.titulo)}</b>${p.subtitulo ? `<span class="dim">${esc(p.subtitulo)}</span>` : ''}`
            + '<span class="der">' + this.t.atajosEn(`seccion:${this.clave}`)
            // los enlaces de la página (una app servida: abrirla en el navegador) van junto al ↻
            + (p.acciones ?? []).filter(a => a.tipo === 'abrir' && a.enlace)
                .map(a => `<a class="atajo" data-accion="abrir-enlace" data-valor="${esc(a.enlace!)}" title="${esc(a.enlace!)}"><span>↗</span> ${esc(a.nombre)}</a>`).join('')
            + '<a class="atajo" data-accion="recargar-seccion" title="volver a pedir la página"><span>↻</span></a>'
            + '</span></div>'];
        h.push(...this.t.paginas.html(p.bloques, this.clave.startsWith('app:') ? this.clave : ''));
        this.t.pintar(h);
    }

    /** Una conversación entera: lo que se dijo, y una línea por herramienta. */
    private async abrirConversacion(id: string): Promise<void> {
        this.t.ir('conversacion');
        this.t.pintar(['<div class="fila dim">leyendo la conversación…</div>']);
        const r = await cli.conversacion(id);
        if (this.t.pantalla !== 'conversacion') return;
        if (!r.datos) {
            this.t.pintar([`<div class="fila falla">${esc(r.error ?? 'no pude leerla')}</div>`,
                '<div class="fila"><a data-accion="volver-seccion">← volver</a></div>']);
            return;
        }
        this.charla = r.datos;
        const c = r.datos;
        const hilo = c.hilo && modelo.porNombre(c.hilo);
        const h: string[] = [`<div class="subcab"><b>Conversación</b><span class="dim">${esc(c.conversacion.slice(0, 8))}`
            + `${c.hilo ? ` · ${esc(c.hilo)}` : ''} · ${c.mensajes.length} mensajes</span>`
            + '<span class="der dim">'
            + (hilo ? `<a data-accion="retomar-charla" title="volver a esta conversación en su hilo">▶ retomar</a> · ` : '')
            + (this.clave ? '<a data-accion="volver-seccion">← ' + esc(modelo.secciones.find(x => x.clave === this.clave)?.nombre ?? 'volver') + '</a>' : '')
            + '</span></div>'];
        for (const m of c.mensajes) {
            const hora = m.hora ? horaLocal(m.hora) : '';
            if (m.quien === 'herramienta') {
                h.push(`<div class="herr dim">› ${esc(m.texto)}</div>`);
            } else {
                h.push(`<div class="msg ${m.quien}"><div class="quien">${m.quien === 'usuario' ? 'tú' : 'agente'}`
                    + `<span class="dim"> ${esc(hora)}</span></div><div class="md-pag">${mdSimple(m.texto)}</div></div>`);
            }
        }
        this.t.pintar(h);
    }
}
