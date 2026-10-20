// El disco, para el dashboard: leer un archivo (el README de un proyecto, la preparación de una reunión, la
// página y la memoria de un lienzo), buscar los .md de una carpeta y guardar la memoria de un lienzo. Por la
// API de telar, que pone los límites (telar.servicios.archivos).

export interface Disco {
    /** el texto de un archivo, o undefined si no está (o no se puede leer) */
    leer(ruta: string): Promise<string | undefined>;
    /** los .md de una carpeta, hasta `hondo` niveles (sin ocultos, node_modules ni assets), con su fecha */
    buscarMd(carpeta: string, hondo: number): Promise<{ ruta: string; mtime: number }[]>;
    /** guarda un archivo entero; false si no se pudo */
    escribir(ruta: string, texto: string): Promise<boolean>;
}

const porLaApi: Disco = {
    leer: async ruta => {
        try {
            const r = await fetch(`/api/archivos?ruta=${encodeURIComponent(ruta)}`, { cache: 'no-store' });
            return r.ok ? ((await r.json()) as { texto: string }).texto : undefined;
        } catch { return undefined; }
    },
    buscarMd: async (carpeta, hondo) => {
        try {
            const r = await fetch(`/api/archivos/md?carpeta=${encodeURIComponent(carpeta)}&hondo=${hondo}`, { cache: 'no-store' });
            return r.ok ? ((await r.json()) as { archivos: { ruta: string; mtime: number }[] }).archivos : [];
        } catch { return []; }
    },
    escribir: async (ruta, texto) => {
        try {
            const r = await fetch('/api/archivos', {
                method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ruta, texto }),
            });
            return r.ok;
        } catch { return false; }
    },
};

export const disco = (): Disco => porLaApi;
