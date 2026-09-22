// Las acciones que comparten las vistas: ir a un hilo, y devolver el teclado al terminal.

import { execFile } from 'child_process';
import * as vscode from 'vscode';

import * as cli from './cli';
import { modelo } from './modelo';

/** El terminal donde corre la sesión, al frente y con el teclado.
 *
 *  Primero por parentesco: telar dice qué procesos son los clientes del multiplexor, y el
 *  terminal de VS Code que buscamos es aquel cuya shell es antepasado de uno de ellos. Así
 *  se encuentra aunque se llame «tmux», «zsh» o como la persona lo haya renombrado, que
 *  fue justo lo que falló buscando por nombre. Si eso no da, por nombre; y si tampoco, el
 *  activo. Esto no abre nada: mover el foco a un terminal no pedido es peor que no moverlo. */
let anotar: (linea: string) => void = () => {};
/** Dónde contar lo que se decidió; lo pone la extensión al activarse. */
export function conBitacora(f: (linea: string) => void): void { anotar = f; }
/** Para que otras vistas cuenten lo suyo en la misma bitácora. */
export function anotarDesdeFuera(linea: string): void { anotar(linea); }

export async function mostrarTerminal(opciones: { soloSuyo?: boolean } = {}): Promise<void> {
    const porClientes = await terminalDeLosClientes();
    if (porClientes) { anotar(`foco: «${porClientes.name}», por parentesco`); porClientes.show(false); return; }
    // por nombre: el de la sesión, «telar», o el del multiplexor, que es como VS Code
    // bautiza un terminal donde se corrió `tmux attach`
    const sesion = modelo.sesion || 'telar';
    const mux = modelo.multiplexor || 'tmux';
    const suyo = vscode.window.terminals.find(t => t.name === sesion || /telar/i.test(t.name))
        ?? vscode.window.terminals.find(t => t.name.toLowerCase() === mux);
    if (!suyo && opciones.soloSuyo) { anotar('foco: ningún terminal muestra la sesión; no se toca'); return; }
    const elegido = suyo ?? vscode.window.activeTerminal;
    anotar(`foco: «${elegido?.name ?? 'ninguno'}», ${suyo ? 'por nombre' : 'el activo, a falta de otro'}`);
    elegido?.show(false);
}

async function terminalDeLosClientes(): Promise<vscode.Terminal | undefined> {
    if (!modelo.clientes.length || process.platform === 'win32') {
        anotar(`foco: telar no informó clientes (${JSON.stringify(modelo.clientes)})`);
        return undefined;
    }
    const padres = await arbolDeProcesos();
    if (!padres.size) { anotar('foco: ps no devolvió el árbol de procesos'); return undefined; }
    const antepasados = new Set<number>();
    for (const cliente of modelo.clientes) {
        let p: number | undefined = cliente;
        for (let i = 0; p && p > 1 && i < 64; i++) { antepasados.add(p); p = padres.get(p); }
    }
    const vistos: string[] = [];
    for (const t of vscode.window.terminals) {
        const pid = await t.processId;
        vistos.push(`${t.name}=${pid ?? '?'}`);
        if (pid && antepasados.has(pid)) return t;
    }
    anotar(`foco: clientes ${modelo.clientes.join(',')} con antepasados ${[...antepasados].join(',')}; `
        + `ningún terminal calza: ${vistos.join(' ') || 'no hay terminales'}`);
    return undefined;
}

/** pid → pid del padre, de todos los procesos de la máquina. Una sola llamada a `ps`. */
function arbolDeProcesos(): Promise<Map<number, number>> {
    return new Promise(resolve => {
        execFile('ps', ['-A', '-o', 'pid=,ppid='], { timeout: 3000 }, (err, salida) => {
            const padres = new Map<number, number>();
            if (!err) {
                for (const linea of salida.split('\n')) {
                    const [pid, ppid] = linea.trim().split(/\s+/).map(Number);
                    if (pid && ppid) padres.set(pid, ppid);
                }
            }
            resolve(padres);
        });
    });
}

/** `telar ir`. Con `crear`, lo abre si no está vivo. */
export async function irAHilo(hilo: string, crear = false): Promise<void> {
    anotar(`ir: «${hilo}»${crear ? ' (crear)' : ''}`);
    const r = await cli.ir(hilo, crear);
    anotar(`ir: telar ir → ${r.ok ? 'ok' : `error ${r.codigo}: ${r.err.trim()}`}`);
    if (!r.ok) {
        void vscode.window.showWarningMessage(`telar: ${r.err.trim().split('\n').pop() ?? `no pude ir a «${hilo}»`}`);
        return;
    }
    await modelo.sondear();
    await mostrarTerminal();
}
