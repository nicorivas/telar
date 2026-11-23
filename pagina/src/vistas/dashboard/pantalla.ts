// Las pantallas del dashboard y lo que el núcleo (panel.ts) les da. Cada pantalla vive en su archivo de esta
// carpeta, con su estado, su HTML y sus acciones: el núcleo junta las acciones de todas en una tabla (cada nombre
// es de una sola), le pide a la que se ve que se repinte, y les da el Tablero, lo común. Una pantalla nueva es
// un archivo más, que se suma a la lista de panel.ts.

import type * as cli from '../../cli';
import type { AccionDePantalla, VistaDePantalla } from '../../componentes/pantalla';
import { I } from '../../web/iconos';
import * as ui from '../../web/ui';
import type { Dia } from './dia';
import type { Paginas } from './pagina';
import type { PantallaCalendario } from './plan';
import type { PantallaProyectos } from './proyectos';
import type { PantallaTareas } from './tareas';
import type { MensajeDia, VistaDia } from './vista';

/** Qué se ve en el dashboard. */
export type NombrePantalla = 'ahora' | 'bloque' | 'config' | 'proyectos' | 'seccion' | 'conversacion' | 'equipo' | 'agentes' | 'tarea' | 'esperas'
    | 'revisar' | 'pestana' | 'calendario' | 'foco' | 'tactica' | 'todo';

/** De qué pestaña fija (`dentro` de un bloque, config.DENTRO_DE) es cada pantalla, y con qué acción se vuelve a ella. */
export const SECCION_DE_PANTALLA: Partial<Record<NombrePantalla, string>> = {
    ahora: 'ahora', revisar: 'tareas', foco: 'tareas', proyectos: 'proyectos', calendario: 'calendario',
};
/** Las subpestañas de fábrica de una sección, antes de las de los bloques (`dentro`): [acción que la abre, nombre,
 *  pantalla]. «tareas» abre en foco (decidir de a una), y «lista» es la lista entera. */
export const SUBPESTANAS: Record<string, [string, string, NombrePantalla][]> = {
    tareas: [['foco', 'foco', 'foco'], ['revisar', 'lista', 'revisar']],
};
/** El ícono de cada vista de fábrica en la barra de su pantalla (por su nombre), y lo que dice su globo. La de un
 *  módulo (`dentro`) no trae ícono: va con su nombre. */
export const ICONO_VISTA: Record<string, [string, string]> = {
    foco: [I.foco, 'de a cinco, para decidir cada una'],
    lista: [I.lista, 'todas, con sus filtros'],
    proyectos: [I.tabla, 'la lista de los proyectos, con su estado y su plazo'],
};

/** La barra de cada pantalla (componentes/pantalla.ts): su nombre y su tinta, cuando no los dice la pestaña que se ve
 *  (un bloque, la pestaña de un proveedor, una sección: esos los ponen ellos). */
export const BARRA_DE: Partial<Record<NombrePantalla, [string, string]>> = {
    ahora: ['ahora', 'amarillo'], foco: ['tareas', 'cian'], revisar: ['tareas', 'cian'], tarea: ['tareas', 'cian'],
    proyectos: ['proyectos', 'verde'], calendario: ['calendario', 'azul'],
    config: ['configuración', 'dim'], agentes: ['agentes', 'violeta'], equipo: ['equipo', 'cian'],
};

/** Lo que una pantalla pone en su barra. El núcleo pone el resto: el nombre y la tinta de la pestaña que se ve
 *  (BARRA_DE), sus vistas (las subpestañas) y ↻ (releer, r). */
export interface EnBarra {
    nombre?: string;
    color?: string;
    /** «‹»: volver a de donde se vino (la ficha de una tarea, a su lista), antes del nombre */
    volver?: AccionDePantalla;
    /** sus propias vistas (el calendario: el día y la semana), si no son subpestañas del núcleo */
    vistas?: VistaDePantalla[];
    /** lo que resume, tenue: una cuenta, la fecha */
    resumen?: string;
    /** lo mismo, ya armado (HTML de confianza): un número en su color (el de «táctica») */
    resumenHtml?: string;
    /** sus acciones, antes de ↻ */
    acciones?: AccionDePantalla[];
    /** sin ↻: lo que se ve no se relee (la configuración) */
    sinReleer?: boolean;
}
export const PESTANA_DE_SECCION: Record<string, string> = {
    ahora: 'ahora', tareas: 'revisar', proyectos: 'proyectos', calendario: 'calendario',
};
/** La clave de la pestaña fija de una sección (`dentro`): la barra marca esa fila mientras se ve una subpestaña. */
export const pestanaDeSeccion = (seccion: string): string => PESTANA_DE_SECCION[seccion] ?? seccion;

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
    /** dibujar la pantalla: su barra (con lo que ella pone en ella) y su cuerpo (con lo que va arriba de todas); y
     *  cambiar un pedazo sin repintar */
    pintar(h: string[], barra?: EnBarra): void;
    parcial(id: string, html: string): void;
    /** redibujar la que se ve con lo que hay (si cambia con el reloj o es del núcleo) */
    render(): void;
    /** los atajos de `[atajos]` que van en un bloque o una sección (`en = "<clave>"`), como acciones de la barra de su
     *  pantalla (su tecla en su celda; el nombre, en su ayuda) */
    atajosEnBarra(en: string): AccionDePantalla[];
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
    readonly planes: PantallaCalendario;
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
