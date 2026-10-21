// Una sección de la configuración (⚙): una entrada del menú vertical y lo que se ve a su derecha. Cada una vive
// en su archivo de esta carpeta y se nombra en el registro de configuracion.ts: agregar una es escribir su archivo
// y sumarla ahí. Lo que necesita del resto (dibujar, la configuración leída, el día) le llega en el Contexto.

import type * as cli from '../../../cli';
import type { Dia } from '../dia';
import type { MensajeDia } from '../vista';

/** Lo que la configuración le da a cada sección. */
export interface Contexto {
    /** dibuja la sección: su cuerpo va a la derecha del menú, bajo su título */
    pintar(cuerpo: string[]): void;
    /** cambia un pedazo sin repintar: lo escrito en un formulario no se pierde */
    parcial(id: string, html: string): void;
    /** las teclas de la sección (⏎, 1, 2…): se vacían al entrar a otra */
    readonly teclas: Map<string, () => unknown>;
    /** si es la que se ve: una lectura que vuelve tarde no pinta encima de otra */
    seVe(clave: string): boolean;
    /** la configuración resuelta (`/config`), leída al entrar a ⚙; y releerla, después de cambiar algo */
    config(): cli.JsonConfig | undefined;
    releerConfig(): Promise<void>;
    /** lo del dashboard que la configuración mira o cambia */
    readonly dashboard: {
        /** el día leído: las fallas de los proveedores, si hay agenda */
        dia(): Dia | undefined;
        /** releerlo (con la red: después de cambiar de dónde sale la agenda) */
        actualizar(conRed: boolean): Promise<void>;
        /** todas sus pestañas, con su clave y su nombre, en el orden de siempre */
        pestanas(): { clave: string; nombre: string }[];
        /** el orden y las ocultas de `[dashboard]`, y ponerlos (lo que guardó `telar config --pestanas`) */
        orden(): { orden: string[]; ocultas: string[] };
        usarOrden(d: { orden: string[]; ocultas: string[] }): void;
    };
}

export interface Seccion {
    /** su llave: la del menú (`data-valor`) y la de `abrir` */
    readonly clave: string;
    readonly nombre: string;
    /** en una línea, qué se configura ahí: va junto al título y al pasar el mouse por el menú */
    readonly ayuda: string;
    /** si va en el menú (los mensajes entre hilos, solo con más de una máquina) */
    visible?(): boolean;
    /** al entrar: lee lo que le falte y se dibuja */
    abrir(): Promise<void>;
    /** se dibuja con lo que ya tiene (el refresco de cada minuto, al volver a ella) */
    pintar(): void;
    /** una acción de su página (`data-accion`): true si era suya */
    accion?(accion: string, valor: string, m: MensajeDia): Promise<boolean>;
    /** otro mensaje de su página (las previas de un formulario): true si era suyo */
    mensaje?(m: MensajeDia): Promise<boolean>;
}

export type FabricaSeccion = (ctx: Contexto) => Seccion;
