// El disco, para el dashboard: leer un archivo (el README de un proyecto, la preparación de una reunión, la
// página y la memoria de un lienzo), buscar los .md de una carpeta y guardar la memoria de un lienzo. Por la
// API de telar, que pone los límites (telar.servicios.archivos).

export interface Disco {
    /** el texto de un archivo, o undefined si no está (o no se puede leer) */
    leer(ruta: string): Promise<string | undefined>;
    /** lo mismo, para lo que puede no estar todavía (la memoria de un lienzo): que no esté no es un error (un 204, no un
     *  404 que el navegador anota en rojo al cargar la página) */
    leerSiHay(ruta: string): Promise<string | undefined>;
    /** los .md de una carpeta, hasta `hondo` niveles (sin ocultos, node_modules ni assets), con su fecha */
    buscarMd(carpeta: string, hondo: number): Promise<{ ruta: string; mtime: number }[]>;
    /** guarda un archivo entero; false si no se pudo */
    escribir(ruta: string, texto: string): Promise<boolean>;
}

async function leer(ruta: string, siHay = false): Promise<string | undefined> {
    try {
        const r = await fetch(`/api/archivos?ruta=${encodeURIComponent(ruta)}${siHay ? '&si_hay=true' : ''}`, { cache: 'no-store' });
        return r.ok && r.status !== 204 ? ((await r.json()) as { texto: string }).texto : undefined;
    } catch { return undefined; }
}

const porLaApi: Disco = {
    leer: ruta => leer(ruta),
    leerSiHay: ruta => leer(ruta, true),
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
