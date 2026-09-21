// La vista «carpeta»: los archivos del hilo que mira la ficha, y nada más.
//
// El explorador de VS Code no sirve para esto: muestra siempre la raíz del workspace y no
// se puede acotar a una carpeta. Aquí la raíz es la del hilo, la dice telar (`ruta`), y
// cambia sola cuando cambia el hilo con el foco.

import * as path from 'path';
import * as vscode from 'vscode';

import { modelo } from '../modelo';

export class Entrada extends vscode.TreeItem {
    constructor(public uri: vscode.Uri, public esCarpeta: boolean) {
        super(uri, esCarpeta ? vscode.TreeItemCollapsibleState.Collapsed : vscode.TreeItemCollapsibleState.None);
        this.contextValue = esCarpeta ? 'carpeta' : 'archivo';
        this.id = uri.fsPath;
        if (!esCarpeta) this.command = { command: 'vscode.open', title: 'abrir', arguments: [uri, { preview: true }] };
    }
}

export class VistaCarpeta implements vscode.TreeDataProvider<Entrada> {
    private emisor = new vscode.EventEmitter<Entrada | undefined>();
    readonly onDidChangeTreeData = this.emisor.event;
    vista?: vscode.TreeView<Entrada>;
    ocultos = false;
    /** de quién es la carpeta que se está mirando; lo pone la ficha */
    objetivo: () => string | undefined = () => undefined;
    private raiz?: string;
    private vigia?: vscode.FileSystemWatcher;
    private rebote?: NodeJS.Timeout;

    refrescar(): void { this.emisor.fire(undefined); }

    seguir(): void {
        const hilo = this.objetivo();
        const h = hilo ? modelo.porNombre(hilo) : undefined;
        const nueva = h?.ruta || undefined;
        if (nueva === this.raiz) return;
        this.raiz = nueva;
        if (this.vista) this.vista.description = h?.relativa ?? '';
        this.vigilar(nueva);
        this.refrescar();
    }

    private vigilar(dir?: string): void {
        this.vigia?.dispose(); this.vigia = undefined;
        if (!dir) return;
        this.vigia = vscode.workspace.createFileSystemWatcher(
            new vscode.RelativePattern(vscode.Uri.file(dir), '**/*'), false, true, false);
        const cambio = () => {
            if (this.rebote) clearTimeout(this.rebote);
            this.rebote = setTimeout(() => this.refrescar(), 400);
        };
        this.vigia.onDidCreate(cambio); this.vigia.onDidDelete(cambio);
    }

    getTreeItem(e: Entrada): vscode.TreeItem { return e; }

    async getChildren(e?: Entrada): Promise<Entrada[]> {
        const dir = e ? e.uri.fsPath : this.raiz;
        if (!dir) return [];
        let entradas: [string, vscode.FileType][];
        try { entradas = await vscode.workspace.fs.readDirectory(vscode.Uri.file(dir)); } catch { return []; }
        const documento = modelo.porNombre(this.objetivo() ?? '')?.ficha?.documento;
        const principal = documento ? path.basename(documento) : '';
        return entradas
            .filter(([n]) => this.ocultos || (!n.startsWith('.') && n !== 'node_modules'))
            // carpetas arriba, el documento del hilo primero, el resto alfabético
            .sort(([na, ta], [nb, tb]) =>
                (tb === vscode.FileType.Directory ? 1 : 0) - (ta === vscode.FileType.Directory ? 1 : 0)
                || (na === principal ? -1 : nb === principal ? 1 : 0)
                || na.localeCompare(nb))
            .map(([n, t]) => new Entrada(vscode.Uri.file(path.join(dir, n)), t === vscode.FileType.Directory));
    }
}
