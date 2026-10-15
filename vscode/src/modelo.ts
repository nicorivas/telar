// El modelo: lo que hay ahora mismo, leído una vez y compartido por las cinco vistas.
//
// No guarda nada propio. Si la extensión muere, no se pierde un dato: el estado vive donde
// telar lo tenga, y aquí solo queda la última respuesta de `telar hilos --json`.
//
// Dos ritmos, porque leer los documentos es lo único caro de todo esto:
//   · el rápido (`telar.intervalo`) trae los hilos SIN ficha: quién está vivo, cuál tiene el
//     foco, qué dijo cada agente, cuánto lleva hoy;
//   · el lento (`telar.intervaloFicha`) los trae CON ficha, que es lo que pone la línea de
//     estado bajo cada hilo.
// Entre uno y otro, la ficha conocida se conserva: vale más una línea de hace un minuto que
// ninguna, y se nota si queda vieja porque el documento se relee al tocarlo.

import * as vscode from 'vscode';

import * as cli from './cli';

export class Modelo {
    sesion = '';
    multiplexor = '';
    raiz = '';
    viva = false;
    /** los pids de los clientes del multiplexor: qué terminales muestran la sesión */
    clientes: number[] = [];
    /** por qué no hay multiplexor, si no lo hay: lo dice telar, no lo adivinamos */
    aviso = '';
    /** el error de la última lectura, si la CLI no contestó */
    error = '';
    hilos: cli.JsonHilo[] = [];
    /** las secciones de la configuración; se releen con el ritmo lento */
    secciones: cli.JsonSeccion[] = [];
    /** las apps de la configuración (`[apps]`), en su orden */
    apps: cli.JsonApp[] = [];
    /** el correo entre agentes de cada máquina remota; se lee por ssh con el ritmo lento y
     *  aparte, para que un servidor lento no frene la lista */
    buzones: cli.JsonBuzon[] = [];
    private leyendoCorreo = false;
    /** lo que el equipo sugiere y Nico no ha decidido (`telar equipo`); vacío si la función está apagada */
    sugerencias: cli.JsonSugerencia[] = [];
    private sugerenciasVistas: Set<string> | undefined;
    hayRemotos = false;

    readonly cambio = new vscode.EventEmitter<void>();

    private fichas = new Map<string, cli.JsonFicha | null>();
    private firma = '';
    private enCurso = false;
    private ultimaFicha = 0;

    get activo(): cli.JsonHilo | undefined { return this.hilos.find(h => h.activo); }
    /** Los hilos con ventana (aquí, o la de otra máquina). Uno sin ventana que no se archivó a propósito
     *  no queda en un limbo gris bajo los activos: va al archivo con los demás, que es lo que es. */
    get enLista(): cli.JsonHilo[] { return this.hilos.filter(h => !h.archivado && (h.vivo || h.propio)); }
    get archivados(): cli.JsonHilo[] { return this.hilos.filter(h => h.archivado || (!h.vivo && !h.propio)); }
    get esperan(): number { return this.enLista.filter(h => h.atencion === 'espera').length; }

    /** Lee el correo de las máquinas remotas sin esperar: cuando llega, redibuja. */
    async leerCorreo(): Promise<void> {
        if (this.leyendoCorreo) return;
        this.leyendoCorreo = true;
        try {
            const r = await cli.correo();
            if (r.datos) { this.buzones = r.datos.remotos; this.firma = ''; this.cambio.fire(); }
        } finally { this.leyendoCorreo = false; }
    }

    get equipoRemoto(): string { return String(cli.ajuste('equipoRemoto', '')).trim(); }

    /** Lee las sugerencias del equipo y avisa de las nuevas con una notificación que no se va sola:
     *  la primera lectura avisa de lo que ya esperaba, para que nada pendiente pase sin verse. */
    async leerEquipo(): Promise<void> {
        const remoto = this.equipoRemoto;
        if (!remoto) { this.sugerencias = []; return; }
        const r = await cli.equipoPendientes(remoto);
        if (!r.datos) return;
        const nuevas = r.datos.sugerencias.filter(x => !this.sugerenciasVistas?.has(x.id));
        const primera = this.sugerenciasVistas === undefined;
        this.sugerenciasVistas = new Set([...(this.sugerenciasVistas ?? []), ...r.datos.sugerencias.map(x => x.id)]);
        this.sugerencias = r.datos.sugerencias;
        this.firma = ''; this.cambio.fire();
        if (!nuevas.length) return;
        const uno = nuevas.length === 1 ? nuevas[0] : undefined;
        const texto = uno
            ? (uno.tipo === 'tarea'
                ? `${uno.persona} te pide una tarea: «${uno.titulo.slice(0, 80)}»${uno.vence ? ` (para el ${uno.vence})` : ''}${uno.similares?.length ? ` · ¿ya existe ${uno.similares[0].id}?` : ''}`
                : `${uno.persona} sugiere subir ${uno.tarea} «${uno.titulo.slice(0, 60)}»: ${uno.motivo.slice(0, 120)}`)
            : `${nuevas.length} cosas del equipo ${primera ? 'esperan' : 'nuevas'}: ${nuevas.map(x => x.tipo === 'tarea' ? `pedido de ${x.persona}` : x.tarea).join(', ')}`;
        void vscode.window.showWarningMessage(`telar · ${texto}`, 'Ver', ...(uno ? [uno.tipo === 'tarea' ? 'Agregar' : 'Aceptar'] : [])).then(async eleccion => {
            if (eleccion === 'Ver') await vscode.commands.executeCommand('telar.equipoVer', uno?.id);
            else if ((eleccion === 'Aceptar' || eleccion === 'Agregar') && uno) {
                const a = await cli.equipoResolver(remoto, 'aceptar', uno.id);
                void vscode.window.showInformationMessage(!a.datos ? `telar: no se pudo: ${a.error ?? ''}`
                    : uno.tipo === 'tarea' ? `telar: agregada${a.datos.sugerencia.tarea ? ` como ${a.datos.sugerencia.tarea}` : ''}` : `telar: ${uno.tarea} sube de prioridad`);
                await this.leerEquipo();
            }
        });
    }

    /** El correo de un hilo remoto: su dirección y lo que le espera. */
    correoDe(hilo: string): cli.JsonCorreoHilo | undefined {
        for (const b of this.buzones) if (b.hilos[hilo]) return b.hilos[hilo];
        return undefined;
    }

    /** La sección a la que pertenece un hilo, si alguna lo reclama. */
    seccionDe(hilo: string): cli.JsonSeccion | undefined { return this.secciones.find(s => cli.enSeccion(s, hilo)); }

    porNombre(nombre: string): cli.JsonHilo | undefined { return this.hilos.find(h => h.nombre === nombre); }
    porId(id: string): cli.JsonHilo | undefined { return this.hilos.find(h => h.id === id); }

    /** El orden lo aplica telar (`--orden`), no esta vista: es una preferencia, y vive en la
     *  configuración para que sobreviva a cerrar la ventana. */
    get orden(): string { return String(cli.ajuste('orden', 'mux')); }

    async sondear(conFicha = false): Promise<void> {
        if (this.enCurso) return;
        this.enCurso = true;
        try {
            const cada = Number(cli.ajuste('intervaloFicha', 60000));
            const toca = conFicha || Date.now() - this.ultimaFicha > cada;
            const r = await cli.hilos(toca, this.orden);
            if (!r.datos) {
                this.error = r.error ?? '';
                this.anunciar(['error', this.error]);
                return;
            }
            this.error = '';
            const d = r.datos;
            this.sesion = d.sesion; this.multiplexor = d.multiplexor; this.raiz = d.raiz;
            this.viva = d.viva; this.aviso = d.aviso; this.clientes = d.clientes ?? [];
            if (toca) {
                const c = await cli.config();
                if (c.datos) {
                    this.secciones = c.datos.secciones ?? [];
                    this.apps = c.datos.apps ?? [];
                    this.hayRemotos = (c.datos.remotos ?? []).length > 0;
                }
                if (this.hayRemotos) void this.leerCorreo();
                void this.leerEquipo();
                this.ultimaFicha = Date.now();
                this.fichas = new Map(d.hilos.map(h => [h.nombre, h.ficha ?? null]));
            }
            this.hilos = d.hilos.map(h => cli.conRutasAbsolutas(
                { ...h, ficha: h.ficha ?? this.fichas.get(h.nombre) ?? null }, d.raiz));
            this.anunciar(['ok', d.sesion, d.viva, d.aviso, this.hilos, this.secciones]);
        } finally {
            this.enCurso = false;
        }
    }

    /** Redibujar solo si algo cambió: si no, la lista parpadea cada segundo. */
    private anunciar(estado: unknown[]): void {
        const firma = JSON.stringify(estado);
        if (firma === this.firma) return;
        this.firma = firma;
        this.cambio.fire();
    }

    /** Fuerza el próximo sondeo a releer los documentos (después de actuar sobre un hilo). */
    invalidar(): void { this.ultimaFicha = 0; }
}

export const modelo = new Modelo();
