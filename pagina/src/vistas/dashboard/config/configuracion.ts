// La configuración (⚙, arriba a la derecha de la página): un menú vertical a la izquierda, como la barra de hilos,
// y a la derecha la sección elegida. Las secciones son las del registro (SECCIONES), cada una en su archivo de
// esta carpeta (ver seccion.ts). La configuración se lee una vez al entrar (`/config`) y se le pasa a todas.

import * as cli from '../../../cli';
import { esc } from '../../../estilo';
import type { MensajeDia } from '../vista';
import { agente } from './agente';
import { agentes } from './agentes';
import { calendario } from './calendario';
import { carpetas } from './carpetas';
import { modulos } from './modulos';
import { periodicos } from './periodicos';
import { personas } from './personas';
import { versionSeccion } from './version';
import { pestanas } from './pestanas';
import type { Contexto, FabricaSeccion, Seccion } from './seccion';

/** Las secciones, en el orden del menú. */
const SECCIONES: FabricaSeccion[] = [pestanas, calendario, carpetas, agente, periodicos, agentes, modulos, personas, versionSeccion];

/** Lo que la configuración necesita del dashboard: dónde dibujar y lo que sus secciones miran. */
export type Base = Pick<Contexto, 'parcial' | 'teclas' | 'dashboard'> & { pintar(h: string[]): void };

export class Configuracion {
    private readonly secciones: Seccion[];
    private actual = '';
    private leida?: cli.JsonConfig;
    private error = '';

    constructor(private readonly base: Base) {
        const ctx: Contexto = {
            pintar: cuerpo => this.dibujar(cuerpo),
            parcial: (id, html) => base.parcial(id, html),
            teclas: base.teclas,
            seVe: clave => this.actual === clave,
            config: () => this.leida,
            releerConfig: () => this.releer(),
            dashboard: base.dashboard,
        };
        this.secciones = SECCIONES.map(f => f(ctx));
    }

    private visibles(): Seccion[] { return this.secciones.filter(s => s.visible?.() ?? true); }
    private seccion(): Seccion | undefined { return this.visibles().find(s => s.clave === this.actual); }

    /** Entrar a ⚙: a `clave`, si se da (y existe); si no, a la última que se miró, o a la primera. */
    async abrir(clave = ''): Promise<void> {
        const visibles = this.visibles();
        const nueva = visibles.find(s => s.clave === clave)?.clave
            ?? (visibles.some(s => s.clave === this.actual) ? this.actual : visibles[0]?.clave ?? '');
        if (nueva !== this.actual) this.base.teclas.clear();
        this.actual = nueva;
        if (!this.leida) await this.releer();
        await this.seccion()?.abrir();
    }

    /** Redibujar lo que se ve (el refresco de cada minuto). */
    pintar(): void { this.seccion()?.pintar(); }

    /** Un mensaje de la página mientras se ve ⚙: el menú, o lo de la sección. true si era de aquí. */
    async atender(m: MensajeDia): Promise<boolean> {
        if (m.tipo === 'accion' && m.accion === 'config') { await this.abrir(m.valor ?? ''); return true; }
        const s = this.seccion();
        if (!s) return false;
        if (m.tipo === 'accion' && m.accion) return (await s.accion?.(m.accion, m.valor ?? '', m)) ?? false;
        return (await s.mensaje?.(m)) ?? false;
    }

    private async releer(): Promise<void> {
        const r = await cli.config();
        this.leida = r.datos ?? this.leida;
        this.error = r.datos ? '' : (r.error ?? 'telar config no contestó');
    }

    /** El marco de toda sección: el menú, y a la derecha su título y su cuerpo. */
    private dibujar(cuerpo: string[]): void {
        const s = this.seccion();
        if (!s) return;
        const menu = this.visibles().map(x => `<a class="config-op${x.clave === s.clave ? ' activa' : ''}" data-accion="config" data-valor="${esc(x.clave)}"`
            + ` title="${esc(x.ayuda)}">${esc(x.nombre)}</a>`).join('');
        this.base.pintar([`<div class="config"><nav class="config-menu"><div class="config-titulo">configuración</div>${menu}</nav>`,
            `<div class="config-cuerpo"><div class="config-cab"><b>${esc(s.nombre)}</b><span class="dim">${esc(s.ayuda)}</span></div>`,
            ...(this.error ? [`<div class="fila falla">${esc(this.error)}</div>`] : []),
            ...cuerpo, '</div></div>']);
    }
}
