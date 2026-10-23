// Las pantallas del dashboard y lo que el núcleo (panel.ts) les da. Cada pantalla vive en su archivo de esta
// carpeta, con su estado, su HTML y sus acciones: el núcleo junta las acciones de todas en una tabla (cada nombre
// es de una sola), le pide a la que se ve que se repinte, y les da el Tablero, lo común. Una pantalla nueva es
// un archivo más, que se suma a la lista de panel.ts.

import type * as cli from '../../cli';
import * as ui from '../../web/ui';
import type { Dia } from './dia';
import type { Paginas } from './pagina';
import type { PantallaPlan } from './plan';
import type { PantallaProyectos } from './proyectos';
import type { PantallaTareas } from './tareas';
import type { MensajeDia, VistaDia } from './vista';

/** Qué se ve en el dashboard. */
export type NombrePantalla = 'ahora' | 'bloque' | 'config' | 'proyectos' | 'seccion' | 'conversacion' | 'equipo' | 'agentes' | 'tarea'
    | 'revisar' | 'pestana' | 'plan' | 'calendario';

/** Una acción de una página (`data-accion`): su valor (`data-valor`) y el mensaje entero (⌘, lo escrito). */
export type Accion = (valor: string, m: MensajeDia) => unknown;

export interface Pantalla {
    /** las pantallas que dibuja: cuando una de ellas se ve, el núcleo le pide repintarse */
    readonly pantallas: readonly NombrePantalla[];
    /** las que cambian con el reloj (la marca de «ahora», los «hace»): se repintan cada minuto y con cada lectura
     *  del día. Las demás solo cuando ella lo pide (una lista que movería el scroll, una ficha con algo escrito) */
    readonly conReloj: readonly NombrePantalla[];
    /** repintar con lo que ya tiene */
    pintar(): void;
    /** sus acciones, por nombre */
    readonly acciones: Record<string, Accion>;
    /** la pestaña que se marca en la barra mientras se ve (sin esto, la de su nombre): la ficha, la de donde se abrió */
    pestanaMarcada?(): string;
}

/** Lo que el núcleo les da a todas. */
export interface Tablero {
    /** abrir el dashboard: montarlo en la página, o si ya está traerlo al frente y releer el día; y solo
     *  montarlo si todavía no está */
    abrir(): void;
    montar(): void;
    /** se le avisa a la página cuando el dashboard gana el foco o cambia la app que muestra (la barra marca su fila) */
    readonly alCambiarFoco?: (activo: boolean) => void;
    /** traerlo al frente si otra pestaña del navegador lo tapa, sin releer */
    alFrente(): void;
    /** la vista montada (vista.ts), para lo que es de una sola pantalla: las cuentas de los proyectos */
    readonly panel?: VistaDia;
    /** la pantalla que se ve, y cambiarla (pintarla es de quien la abre) */
    readonly pantalla: NombrePantalla;
    ir(p: NombrePantalla): void;
    /** dibujar la pantalla (con lo que va arriba de todas), y cambiar un pedazo sin repintar */
    pintar(h: string[]): void;
    parcial(id: string, html: string): void;
    /** redibujar la que se ve con lo que hay (si cambia con el reloj o es del núcleo) */
    render(): void;
    /** los bloques que van arriba de otra pestaña (`en = "plan"`), ya dibujados, si traen algo */
    bloquesEn(en: string): string[];
    /** los botones de los atajos de `[atajos]` que van en un bloque o una sección (`en = "<clave>"`) */
    atajosEn(en: string): string;
    /** cómo se llama una pestaña («revisar» es «tareas»; la de un feed, sin su cuenta) */
    nombrePestana(clave: string): string;
    /** las teclas de la pantalla que se ve: cada una las pone al pintarse */
    readonly teclas: Map<string, () => unknown>;
    /** el día leído (`telar hoy`), leerlo si todavía no está, y releerlo (`conRed`: consultando a los proveedores ya) */
    dia(): Dia | undefined;
    diaLeido(): Promise<Dia>;
    actualizar(conRed?: boolean): Promise<void>;
    /** correr una acción del dashboard como si viniera de la página: ir a una pantalla de otro archivo */
    accion(accion: string, valor?: string): Promise<void>;
    /** el bloque y el ítem que se ven en la pestaña de un bloque («<clave>:<ítem>»): la ficha vuelve ahí */
    bloqueAbierto(): string;
    /** las pantallas a las que otras les preguntan: de qué proyecto es algo, qué tareas siguen vivas y cómo se
     *  dibuja su fila, el plan del día; cómo se dibuja una página */
    readonly proyectos: PantallaProyectos;
    readonly tareas: PantallaTareas;
    readonly planes: PantallaPlan;
    readonly paginas: Paginas;
    /** el agente que recibe lo que no tiene proyecto (`[agentes] sin_proyecto`), si hay */
    general(): { clave: string; nombre: string } | undefined;
    /** la configuración resuelta, leída al abrir el dashboard */
    config(): cli.JsonConfig | undefined;
}

/** Abre un enlace de una página: una URL en una pestaña nueva, una ruta de la máquina en la vista de
 *  carpeta de la página. */
export async function abrirEnlace(enlace: string): Promise<void> {
    if (/^https?:\/\//.test(enlace)) {
        await ui.abrirExterno(enlace);
        return;
    }
    if (enlace.startsWith('/')) {
        await ui.abrirArchivo(enlace);
        return;
    }
    void ui.aviso(`telar: no sé abrir ${enlace}`);
}
