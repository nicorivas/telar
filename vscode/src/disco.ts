// El disco, para el dashboard: leer un archivo (el README de un proyecto, la preparación de una reunión, la
// página y la memoria de un lienzo), buscar los .md de una carpeta y guardar la memoria de un lienzo. En VS
// Code, el disco de la máquina (fs); en el navegador (src/navegador), la API de
// telar, que pone los límites (telar.servicios.archivos). Todo asíncrono: en el navegador no se espera.

import * as fs from 'fs';
import * as path from 'path';

export interface Disco {
    /** el texto de un archivo, o undefined si no está (o no se puede leer) */
    leer(ruta: string): Promise<string | undefined>;
    /** los .md de una carpeta, hasta `hondo` niveles (sin ocultos, node_modules ni assets), con su fecha */
    buscarMd(carpeta: string, hondo: number): Promise<{ ruta: string; mtime: number }[]>;
    /** guarda un archivo entero; false si no se pudo */
    escribir(ruta: string, texto: string): Promise<boolean>;
}

const local: Disco = {
    leer: async ruta => { try { return fs.readFileSync(ruta, 'utf8'); } catch { return undefined; } },
    buscarMd: async (carpeta, hondo) => {
        const hallados: { ruta: string; mtime: number }[] = [];
        const recorrer = (dir: string, nivel: number) => {
            let entradas: fs.Dirent[] = [];
            try { entradas = fs.readdirSync(dir, { withFileTypes: true }); } catch { return; }
            for (const x of entradas) {
                if (x.name.startsWith('.') || x.name === 'node_modules' || x.name === 'assets') continue;
                const r = path.join(dir, x.name);
                if (x.isDirectory() && nivel < hondo) recorrer(r, nivel + 1);
                else if (x.isFile() && x.name.endsWith('.md')) {
                    try { hallados.push({ ruta: r, mtime: fs.statSync(r).mtimeMs }); } catch { /* se fue */ }
                }
            }
        };
        recorrer(carpeta, 0);
        return hallados;
    },
    escribir: async (ruta, texto) => {
        try {
            fs.mkdirSync(path.dirname(ruta), { recursive: true });
            const tmp = `${ruta}.${process.pid}.tmp`;
            fs.writeFileSync(tmp, texto);
            fs.renameSync(tmp, ruta);
            return true;
        } catch { return false; }
    },
};

let actual: Disco = local;
export function usarDisco(d: Disco): void { actual = d; }
export const disco = (): Disco => actual;
