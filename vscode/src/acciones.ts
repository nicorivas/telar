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
export async function mostrarTerminal(): Promise<void> {
    const porClientes = await terminalDeLosClientes();
    if (porClientes) { porClientes.show(false); return; }
    const sesion = modelo.sesion || 'telar';
    const suyo = vscode.window.terminals.find(t => t.name === sesion || /telar/i.test(t.name));
    (suyo ?? vscode.window.activeTerminal)?.show(false);
}

async function terminalDeLosClientes(): Promise<vscode.Terminal | undefined> {
    if (!modelo.clientes.length || process.platform === 'win32') return undefined;
    const padres = await arbolDeProcesos();
    if (!padres.size) return undefined;
    const antepasados = new Set<number>();
    for (const cliente of modelo.clientes) {
        let p: number | undefined = cliente;
        for (let i = 0; p && p > 1 && i < 64; i++) { antepasados.add(p); p = padres.get(p); }
    }
    for (const t of vscode.window.terminals) {
        const pid = await t.processId;
        if (pid && antepasados.has(pid)) return t;
    }
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
    const r = await cli.ir(hilo, crear);
    if (!r.ok) {
        void vscode.window.showWarningMessage(`telar: ${r.err.trim().split('\n').pop() ?? `no pude ir a «${hilo}»`}`);
        return;
    }
    await modelo.sondear();
    await mostrarTerminal();
}
