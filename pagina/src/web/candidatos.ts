// Los archivos que se llaman como uno que nombró el agente de un hilo y no está donde lo dijo: los deja
// web/rutas-agente.ts (`abrirRuta`, con lo que encontró el backend, telar.servicios.resolver), y el visor de esa ruta
// (web/carpeta.ts) los ofrece para elegir en vez de decir que no existe. Aparte, sin nada de la página: así
// rutas-agente.ts no carga el visor (y sus pruebas, tampoco).

const ofrecidos = new Map<string, { candidatos: string[]; mas: boolean }>();

/** Que el visor de `ruta` (como va en `arch:`) ofrezca `candidatos` (con «máquina:» delante si son de otra), los más
 *  cercanos primero; `mas`, si había más que esos. Sirve hasta que se ofrezcan otros para la misma ruta. */
export function ofrecer(ruta: string, candidatos: string[], mas = false): void {
    ofrecidos.set(ruta, { candidatos, mas });
}

/** Los candidatos que se ofrecieron para `ruta`, si hay. */
export const ofrecidosPara = (ruta: string): { candidatos: string[]; mas: boolean } | undefined => ofrecidos.get(ruta);
