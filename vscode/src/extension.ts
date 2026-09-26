// telar para VS Code — los hilos de trabajo en la barra lateral.
//
// La sesión, los hilos y los procesos siguen siendo del multiplexor, y quién es cada hilo lo
// declara el perfil del repositorio. Esto es la VISTA: pregunta por `telar … --json`, dibuja,
// y cada acción vuelve a ser una orden de la CLI. No guarda estado propio; si la extensión
// muere, no se pierde nada.
//
// Aquí solo vive la activación: las órdenes, el sondeo y el reparto a las cinco vistas.

import * as path from 'path';
import * as vscode from 'vscode';

import * as acciones from './acciones';
import { irAHilo, mostrarTerminal } from './acciones';
import * as cli from './cli';
import { modelo } from './modelo';
import { Entrada, VistaCarpeta } from './vistas/carpeta';
import { VistaFicha } from './vistas/ficha';
import { VistaHilos } from './vistas/hilos';
import { PanelHoy } from './vistas/hoy';
import { VistaTareas } from './vistas/tareas';

let bitacora: vscode.LogOutputChannel;
let vistaHilos: VistaHilos;
let vistaFicha: VistaFicha;
let vistaCarpeta: VistaCarpeta;
let vistaTareas: VistaTareas;
let hoy: PanelHoy;

function anotar(linea: string): void {
    bitacora.appendLine(`${new Date().toLocaleTimeString()}  ${linea}`);
}

// ───────────────────────── a qué hilo se le hace ─────────────────────────

/** Lo que recibe una orden: nada (el hilo con el foco), `{hilo}` desde el código, o el
 *  contexto de la fila del webview (`{webviewSection, hilo}`) desde el menú contextual. */
type Arg = { hilo?: string; accion?: string } | undefined;

function hiloDe(a: Arg): string | undefined {
    return a?.hilo ?? modelo.activo?.nombre;
}

/** Una orden de `telar hilo …`, con la queja a la vista si falla. */
/** Pasar la conversación de un hilo a otra máquina: se cierra aquí y sigue allá. Si el
 *  repositorio tiene trabajo sin subir, telar lo dice y aquí se pregunta antes de seguir. */
async function llevar(a: Arg): Promise<void> {
    const hilo = hiloDe(a);
    if (!hilo) return;
    if (modelo.porNombre(hilo)?.remoto) {
        void vscode.window.showInformationMessage(`telar: «${hilo}» ya vive en otra máquina.`);
        return;
    }
    const remotos = (await cli.config()).datos?.remotos ?? [];
    if (!remotos.length) { void vscode.window.showWarningMessage('telar: no hay máquinas en [remotos].'); return; }
    let remoto = remotos[0].nombre;
    if (remotos.length > 1) {
        const r = await vscode.window.showQuickPick(remotos.map(x => ({ label: x.nombre, description: x.destino, x })),
            { placeHolder: `¿A qué máquina llevo «${hilo}»?` });
        if (!r) return;
        remoto = r.x.nombre;
    }
    const intento = await cli.hilo('llevar', hilo, remoto);
    let r = intento;
    if (!intento.ok && /sin subir/.test(intento.err)) {
        const avisos = intento.out.split('\n').filter(l => l.trim().startsWith('·')).map(l => l.trim()).join('\n');
        const si = await vscode.window.showWarningMessage(
            `La conversación de «${hilo}» viaja, los archivos no. Aquí hay trabajo que allá no va a estar:`,
            { modal: true, detail: `${avisos}\n\nSincroniza primero, o llévala sabiendo que el agente de allá no lo verá.` },
            'Llevar igual');
        if (si !== 'Llevar igual') return;
        r = await cli.hilo('llevar', hilo, remoto, ['--si']);
    }
    anotar(`hilo llevar ${remoto} --hilo ${hilo} → ${r.ok ? 'ok' : `error ${r.codigo}`} ${r.out.trim()}`);
    if (!r.ok) { void vscode.window.showErrorMessage(`telar: ${r.err.trim().split('\n').pop() ?? 'no se llevó'}`); return; }
    modelo.invalidar();
    await modelo.sondear();
    await mostrarTerminal();
}

async function sobreHilo(a: Arg, verbo: string, valor?: string, extra: string[] = []): Promise<boolean> {
    const hilo = hiloDe(a);
    if (!hilo) { void vscode.window.showWarningMessage('telar: no sé sobre qué hilo; abre uno o elígelo en la lista.'); return false; }
    const r = await cli.hilo(verbo, hilo, valor, extra);
    anotar(`hilo ${verbo} ${valor ?? ''} --hilo ${hilo} → ${r.ok ? 'ok' : `error ${r.codigo}`} ${r.out.trim()}`);
    if (!r.ok) {
        void vscode.window.showErrorMessage(`telar: ${r.err.trim().split('\n').pop() ?? `«telar hilo ${verbo}» falló`}`);
        return false;
    }
    modelo.invalidar();
    await modelo.sondear();
    return true;
}

// ───────────────────────── órdenes que piden algo a la persona ─────────────────────────

async function nuevo(): Promise<void> {
    const nombre = await vscode.window.showInputBox({
        prompt: 'Nombre del hilo nuevo', placeHolder: 'faro',
    });
    if (!nombre) return;
    // dónde vive su agente: solo se pregunta si la configuración declara otras máquinas
    const remotos = (await cli.config()).datos?.remotos ?? [];
    let remoto = '';
    if (remotos.length) {
        const elegido = await vscode.window.showQuickPick([
            { label: '$(device-desktop) Local', description: 'en esta máquina', remoto: '' },
            ...remotos.map(r => ({ label: `$(remote) Remoto: ${r.nombre}`, description: `${r.destino} (${r.transporte})`, remoto: r.nombre })),
        ], { placeHolder: `¿Dónde vive el agente de «${nombre.trim()}»?` });
        if (!elegido) { anotar('nuevo: se cerró el menú local/remoto, no se crea nada'); return; }
        remoto = elegido.remoto;
    }
    anotar(`nuevo: ${remotos.length} remoto(s) declarado(s); elegido ${remoto || 'local'}`);
    await irAHilo(nombre.trim(), true, remoto);
}

async function renombrar(a: Arg): Promise<void> {
    const hilo = hiloDe(a);
    if (!hilo) return;
    const nombre = await vscode.window.showInputBox({
        prompt: 'Nombre nuevo (se mueve con él lo que telar sabía: carpeta, prioridad, atención)',
        value: hilo,
    });
    if (!nombre || nombre === hilo) return;
    if (await sobreHilo(a, 'renombrar', nombre) && vistaFicha.fijado === hilo) vistaFicha.fijado = nombre;
}

async function vincular(a: Arg): Promise<void> {
    const hilo = hiloDe(a);
    if (!hilo) return;
    if (!modelo.raiz) { void vscode.window.showWarningMessage('telar: todavía no sé cuál es la raíz del repositorio.'); return; }
    const actual = modelo.porNombre(hilo)?.ruta;
    const elegido = await vscode.window.showOpenDialog({
        canSelectFiles: false, canSelectFolders: true, canSelectMany: false,
        defaultUri: vscode.Uri.file(actual || modelo.raiz),
        openLabel: `Vincular «${hilo}» a esta carpeta`,
    });
    const dir = elegido?.[0]?.fsPath;
    if (!dir) return;
    // fuera de la raíz se vincula por su ruta absoluta; su ficha es solo el README
    const relativa = path.relative(modelo.raiz, dir);
    const valor = relativa.startsWith('..') || path.isAbsolute(relativa) ? dir : (relativa || '.');
    if (await sobreHilo(a, 'vincular', valor)) vistaCarpeta.seguir();
}

/** Cierra el tab y lo que corra adentro, y telar lo olvida: sale de la lista. No pregunta,
 *  porque lo que se quiere guardar se archiva (⏸) y la conversación sigue en disco. */
async function cerrar(a: Arg): Promise<void> {
    if (!hiloDe(a)) return;
    await sobreHilo(a, 'cerrar');
}

async function olvidar(a: Arg): Promise<void> {
    const hilo = hiloDe(a);
    if (!hilo) return;
    const ok = await vscode.window.showWarningMessage(
        `¿Que telar olvide «${hilo}»? Pierde su carpeta, su prioridad y su atención; el registro de foco queda.`,
        { modal: true }, 'Olvidar');
    if (ok !== 'Olvidar') return;
    await sobreHilo(a, 'olvidar');
}

async function lanzador(): Promise<void> {
    type Fila = vscode.QuickPickItem & { hilo?: string };
    const filas: Fila[] = [];
    const fila = (h: (typeof modelo.hilos)[number], extra = ''): Fila => ({
        hilo: h.nombre,
        label: `${h.id !== h.nombre ? `${h.id}  ` : ''}${h.nombre}`,
        description: [h.prioridad ? `P${h.prioridad}` : '', h.relativa, extra].filter(Boolean).join('  '),
        detail: h.ficha?.estado || undefined,
    });
    for (const h of modelo.enLista) filas.push(fila(h));
    if (modelo.archivados.length) {
        filas.push({ label: 'archivo', kind: vscode.QuickPickItemKind.Separator });
        for (const h of modelo.archivados) filas.push(fila(h, '$(archive)'));
    }
    const elegido = await vscode.window.showQuickPick(filas, {
        placeHolder: 'Ir a un hilo', matchOnDescription: true, matchOnDetail: true,
    });
    if (elegido?.hilo) await irAHilo(elegido.hilo);
}

async function ordenar(): Promise<void> {
    const actual = modelo.orden;
    const opciones = [
        { k: 'mux', label: 'como los da el multiplexor' },
        { k: 'alfa', label: 'alfabético' },
        { k: 'reciente', label: 'último foco, lo más reciente arriba' },
        { k: 'prioridad', label: 'prioridad: ● alta, ◐ media, ○ baja; sin prioridad al final' },
    ].map(o => ({ ...o, description: o.k === actual ? '● actual' : '' }));
    const e = await vscode.window.showQuickPick(opciones, { placeHolder: 'Ordenar los hilos por' });
    if (!e) return;
    await vscode.workspace.getConfiguration('telar').update('orden', e.k, vscode.ConfigurationTarget.Global);
    await modelo.sondear();
}

/** Las acciones son del perfil del repositorio, no de esta extensión: se preguntan cada vez. */
async function accion(a: Arg): Promise<void> {
    const hilo = hiloDe(a);
    if (!hilo) return;
    const r = await cli.ficha(hilo);
    const acciones = r.datos?.acciones ?? [];
    if (!acciones.length) {
        void vscode.window.showInformationMessage(
            r.error ?? 'telar: el perfil de este repositorio no declara ninguna acción (docs/perfil.md).');
        return;
    }
    let elegida = acciones.find(x => x.nombre === a?.accion);
    if (!elegida) {
        const pick = await vscode.window.showQuickPick(
            acciones.map(x => ({ label: x.nombre, description: x.tecla ? `[${x.tecla}]` : '', detail: x.descripcion, x })),
            { placeHolder: `Acción sobre «${hilo}»` });
        elegida = pick?.x;
    }
    if (!elegida) return;
    if (elegida.confirmar) {
        const ok = await vscode.window.showWarningMessage(
            `¿Correr «${elegida.nombre}» sobre «${hilo}»?\n${elegida.descripcion}`, { modal: true }, 'Correr');
        if (ok !== 'Correr') return;
    }
    const salida = await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Window, title: `telar accion ${elegida.nombre}` },
        () => cli.accion(elegida!.nombre, hilo));
    anotar(`accion ${elegida.nombre} --hilo ${hilo} → ${salida.ok ? 'ok' : `error ${salida.codigo}`}\n${salida.out.trim()}`);
    if (!salida.ok) void vscode.window.showErrorMessage(`telar: ${salida.err.trim().split('\n').pop() ?? 'la acción falló'}`);
    modelo.invalidar();
    await modelo.sondear();
}

/** Abre un terminal y teje la sesión ahí: el multiplexor quiere un terminal de verdad. */
function tejer(): void {
    const nombre = modelo.sesion || 'telar';
    const existente = vscode.window.terminals.find(t => t.name === nombre);
    if (existente) { existente.show(); return; }
    const t = vscode.window.createTerminal({
        name: nombre, location: vscode.TerminalLocation.Editor,
        cwd: path.isAbsolute(modelo.raiz) ? modelo.raiz : undefined,
    });
    t.show();
    t.sendText(`${cli.programa()} tejer`, true);
}

async function documento(a: Arg): Promise<void> {
    const hilo = hiloDe(a);
    const h = hilo ? modelo.porNombre(hilo) : undefined;
    const archivo = h?.ficha?.documento;
    if (!archivo) {
        void vscode.window.showInformationMessage(
            `telar: «${hilo ?? '?'}» no tiene documento. Vincúlalo a una carpeta que el perfil declare.`);
        return;
    }
    const doc = await vscode.workspace.openTextDocument(archivo);
    await vscode.window.showTextDocument(doc, { viewColumn: vscode.ViewColumn.Beside, preview: true });
}

/** Pide la dirección iCal privada y se la pasa a `telar config --calendario`, que valida y
 *  escribe. La dirección no pasa por ningún otro lado: es un secreto, porque quien la
 *  tiene ve la agenda, y telar deja el archivo legible solo por su dueño. */
async function conectarCalendario(): Promise<void> {
    const valor = await vscode.window.showInputBox({
        title: 'Conectar calendario',
        prompt: 'La dirección privada de tu calendario en formato iCal. En Google Calendar: '
            + 'Configuración › tu calendario › «Dirección secreta en formato iCal».',
        placeHolder: 'https://calendar.google.com/calendar/ical/…/basic.ics',
        ignoreFocusOut: true,
    });
    if (!valor?.trim()) return;
    const r = await cli.telar(['config', '--calendario', valor.trim()], 20000);
    if (!r.ok) {
        void vscode.window.showWarningMessage(`telar: ${r.err.trim().split('\n').pop() || 'no pude conectar el calendario'}`);
        return;
    }
    anotar('calendario conectado');
    void vscode.window.showInformationMessage('Calendario conectado.');
}

// ───────────────────────── activación ─────────────────────────

export async function activate(ctx: vscode.ExtensionContext): Promise<void> {
    bitacora = vscode.window.createOutputChannel('telar', { log: true });
    acciones.conBitacora(anotar);
    ctx.subscriptions.push(bitacora);
    cli.conBitacora(anotar);

    vistaHilos = new VistaHilos();
    ctx.subscriptions.push(vscode.window.registerWebviewViewProvider('telar.hilos', vistaHilos,
        { webviewOptions: { retainContextWhenHidden: true } }));
    vistaTareas = new VistaTareas();
    ctx.subscriptions.push(vscode.window.registerWebviewViewProvider('telar.tareas', vistaTareas,
        { webviewOptions: { retainContextWhenHidden: true } }));
    vistaFicha = new VistaFicha();
    ctx.subscriptions.push(vscode.window.registerWebviewViewProvider('telar.ficha', vistaFicha,
        { webviewOptions: { retainContextWhenHidden: true } }));
    vistaCarpeta = new VistaCarpeta();
    vistaCarpeta.objetivo = () => vistaFicha.objetivo();
    vistaCarpeta.vista = vscode.window.createTreeView('telar.carpeta',
        { treeDataProvider: vistaCarpeta, showCollapseAll: true });
    ctx.subscriptions.push(vistaCarpeta.vista);
    hoy = new PanelHoy();

    await cli.resolverPath();
    anotar(`PATH: ${cli.pathResuelto()}`);

    // cada cambio del modelo redibuja la lista; la ficha y la carpeta siguen al hilo con foco
    ctx.subscriptions.push(modelo.cambio.event(() => {
        vistaHilos.refrescar();
        vistaFicha.seguir();
        vistaCarpeta.seguir();
    }));

    // si cambia la letra del terminal, las vistas la siguen
    ctx.subscriptions.push(vscode.workspace.onDidChangeConfiguration(e => {
        if (e.affectsConfiguration('terminal.integrated') || e.affectsConfiguration('editor.fontFamily')
            || e.affectsConfiguration('editor.fontSize') || e.affectsConfiguration('workbench.colorCustomizations')) {
            vistaHilos.pintarMarco(); void vistaFicha.render(); hoy.pintarMarco(); vistaTareas.pintarMarco();
        }
        if (e.affectsConfiguration('telar')) void modelo.sondear(true);
    }));

    // el sondeo: `telar.intervalo` con la sesión viva, cinco segundos cuando no hay a quién preguntar
    let temporizador: NodeJS.Timeout | undefined;
    const programar = () => {
        const espera = modelo.error || !modelo.viva ? 5000 : Math.max(Number(cli.ajuste('intervalo', 2000)), 250);
        temporizador = setTimeout(async () => {
            await modelo.sondear().catch(e => anotar(`sondeo: ${e}`));
            programar();
        }, espera);
    };
    // el `catch` no es adorno: si el primer sondeo revienta, sin él no se programa el
    // siguiente y la barra se queda muda para siempre
    void modelo.sondear(true).catch(e => anotar(`sondeo: ${e}`)).then(programar);
    ctx.subscriptions.push({ dispose: () => { if (temporizador) clearTimeout(temporizador); } });

    // los hilos que nacen en una máquina remota (un reloj allá, el celular) se traen
    // solos; cada tres minutos es lo que tarda en aparecer, y un ssh cada tanto es barato
    let vuelta = 0;
    const traer = async () => {
        if (!modelo.hayRemotos) return;
        const r = await cli.traerRemotos();
        if (r.datos?.traidos.length) await modelo.sondear();
    };
    // el día se relee solo mientras se esté mirando
    const cadaMinuto = setInterval(() => {
        if (vuelta++ % 3 === 0) void traer().catch(e => anotar(`traer remotos: ${e}`));
        if (hoy.panel?.visible) void hoy.actualizar();
        if (vistaTareas.vista?.visible) void vistaTareas.actualizar();
    }, 60 * 1000);
    ctx.subscriptions.push({ dispose: () => clearInterval(cadaMinuto) });

    const orden = (id: string, f: (...a: any[]) => unknown) =>
        ctx.subscriptions.push(vscode.commands.registerCommand(id,
            (...a) => Promise.resolve(f(...a)).catch(e => anotar(`${id}: ${e}`))));

    orden('telar.ir', (a?: Arg) => { const h = hiloDe(a); if (h) return irAHilo(h); });
    orden('telar.irNumero', (n: number) => {
        const h = modelo.enLista[Number(n) - 1];
        if (h) return irAHilo(h.nombre);
    });
    orden('telar.tejer', tejer);
    orden('telar.tarea', (valor: string) => hoy.abrirTarea(valor));
    orden('telar.nuevo', nuevo);
    orden('telar.lanzador', lanzador);
    orden('telar.orden', ordenar);
    orden('telar.actualizar', () => modelo.sondear(true));
    orden('telar.archivo', async () => {
        vistaHilos.alternarArchivo();
        if (vistaHilos.archivoAbierto) await vscode.commands.executeCommand('telar.hilos.focus');
    });

    orden('telar.ficha', async (a?: Arg) => {
        if (a?.hilo) vistaFicha.fijado = a.hilo;
        await vscode.commands.executeCommand('telar.ficha.focus');
        await vistaFicha.actualizar();
    });
    orden('telar.fichaActualizar', () => vistaFicha.actualizar());
    orden('telar.documento', documento);
    orden('telar.carpeta', (a?: Arg) => {
        const h = hiloDe(a);
        const ruta = h ? modelo.porNombre(h)?.ruta : undefined;
        if (ruta) return vscode.commands.executeCommand('revealInExplorer', vscode.Uri.file(ruta));
    });

    orden('telar.renombrar', renombrar);
    orden('telar.vincular', vincular);
    orden('telar.desvincular', (a?: Arg) => sobreHilo(a, 'desvincular'));
    orden('telar.prioridadAlta', (a?: Arg) => sobreHilo(a, 'prioridad', '1'));
    orden('telar.prioridadMedia', (a?: Arg) => sobreHilo(a, 'prioridad', '2'));
    orden('telar.prioridadBaja', (a?: Arg) => sobreHilo(a, 'prioridad', '3'));
    orden('telar.prioridadNinguna', (a?: Arg) => sobreHilo(a, 'prioridad', 'ninguna'));
    // Archivar cierra el tab y deja la conversación guardada junto al hilo (telar la abrió
    // con un id conocido); retomar la reabre con `--resume`. Por eso archivar ya no pide
    // confirmación: no se pierde nada.
    orden('telar.archivar', (a?: Arg) => vscode.window.withProgress(
        { location: { viewId: 'telar.hilos' }, title: `archivando ${hiloDe(a) ?? ''}` },
        () => sobreHilo(a, 'archivar', undefined, ['--cerrar'])));
    orden('telar.retomar', (a?: Arg) => vscode.window.withProgress(
        { location: { viewId: 'telar.hilos' }, title: `retomando ${hiloDe(a) ?? ''}` },
        async () => { if (await sobreHilo(a, 'retomar')) await mostrarTerminal(); }));
    orden('telar.desarchivar', (a?: Arg) => sobreHilo(a, 'desarchivar'));
    orden('telar.olvidar', olvidar);
    orden('telar.cerrar', cerrar);
    orden('telar.llevar', llevar);
    orden('telar.accion', accion);

    orden('telar.hoy', () => hoy.alternar());
    orden('telar.seccion', (clave?: string) => { if (typeof clave === 'string' && clave) void hoy.abrirSeccion(clave); });
    orden('telar.conectarCalendario', conectarCalendario);
    orden('telar.tareas', async () => {
        await vscode.commands.executeCommand('telar.tareas.focus');
        await vistaTareas.actualizar();
    });
    orden('telar.tareasActualizar', () => vistaTareas.actualizar(true));
    orden('telar.terminal', () => mostrarTerminal());

    orden('telar.carpetaActualizar', () => vistaCarpeta.refrescar());
    orden('telar.carpetaOcultos', () => { vistaCarpeta.ocultos = !vistaCarpeta.ocultos; vistaCarpeta.refrescar(); });
    orden('telar.carpetaAlLado', (e?: Entrada) =>
        e && vscode.commands.executeCommand('vscode.open', e.uri, { viewColumn: vscode.ViewColumn.Beside }));
    orden('telar.carpetaSistema', (e?: Entrada) => vscode.commands.executeCommand('revealFileInOS', e?.uri));
    orden('telar.carpetaExplorador', (e?: Entrada) => vscode.commands.executeCommand('revealInExplorer', e?.uri));
    orden('telar.carpetaRuta', async (e?: Entrada) => {
        if (!e) return;
        await vscode.env.clipboard.writeText(e.uri.fsPath);
        void vscode.window.setStatusBarMessage(`telar: ${e.uri.fsPath}`, 4000);
    });
}

export function deactivate(): void { /* nada que guardar: el estado es de telar */ }
