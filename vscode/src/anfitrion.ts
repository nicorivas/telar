// El anfitrión: lo que el dashboard y la barra le piden a quien los muestra.
//
// El dashboard y la barra no dependen de VS Code: arman HTML con lo que da la CLI y responden a
// los clics. Lo que sí depende de dónde corren —un aviso, un menú para elegir, un campo para
// escribir, abrir un enlace o un archivo, la barra de estado— pasa por aquí. VS Code lo hace con
// su API (`anfitrion-vscode.ts`); el navegador, con mensajes a la página (`web/`). Ver
// docs/propuestas/dashboard-fuera-de-vscode.md.
//
// Las firmas siguen a las de VS Code que se usaban, para que el cambio fuera mecánico: un aviso
// con botones devuelve el botón elegido (o undefined), un menú devuelve el ítem.

/** Un ítem de un menú para elegir. `separador`: un título de grupo, no se elige. */
export interface Opcion {
    label: string;
    description?: string;
    detail?: string;
    separador?: boolean;
}

export interface OpcionesMenu {
    title?: string;
    placeHolder?: string;
    matchOnDescription?: boolean;
    matchOnDetail?: boolean;
    ignoreFocusOut?: boolean;
}

export interface OpcionesCampo {
    title?: string;
    prompt?: string;
    placeHolder?: string;
    value?: string;
    ignoreFocusOut?: boolean;
    password?: boolean;
    /** Un texto con el problema si lo escrito no sirve; undefined si sirve. */
    validateInput?: (texto: string) => string | undefined;
}

/** Un aviso con botones: `modal` lo pone delante de todo y espera la respuesta. */
export interface OpcionesAviso {
    modal?: boolean;
    detail?: string;
}

export interface Anfitrion {
    /** Avisos: el texto, y si se dan botones, el que se eligió (undefined si se cerró). */
    aviso(texto: string, ...botones: (string | OpcionesAviso)[]): Promise<string | undefined>;
    falla(texto: string, ...botones: (string | OpcionesAviso)[]): Promise<string | undefined>;
    info(texto: string, ...botones: (string | OpcionesAviso)[]): Promise<string | undefined>;
    /** Una línea que se va sola (la barra de estado). */
    estado(texto: string, ms?: number): void;
    /** Mientras corre `trabajo`, se ve que algo pasa. `ventana`: discreto (la barra), no un aviso. */
    progreso<T>(opciones: { title: string; ventana?: boolean }, trabajo: () => Promise<T>): Promise<T>;
    /** Un campo para escribir. undefined si se canceló. */
    campo(opciones: OpcionesCampo): Promise<string | undefined>;
    /** Un menú para elegir uno. */
    elegir<T extends Opcion>(opciones: T[], menu?: OpcionesMenu): Promise<T | undefined>;
    /** Una URL en el navegador. */
    abrirExterno(url: string): Promise<void>;
    /** Un archivo en el editor (en su línea, si se da). */
    abrirArchivo(ruta: string, linea?: number): Promise<void>;
    /** Mostrar una carpeta en el explorador de archivos. */
    mostrarCarpeta(ruta: string): Promise<void>;
    copiar(texto: string): Promise<void>;
    /** Markdown a HTML. */
    markdown(texto: string): Promise<string>;
    /** Llevar a un hilo (en VS Code, su terminal al frente; en la web, se muestra en la página). */
    irAHilo(hilo: string, crear?: boolean, remoto?: string): Promise<void>;
    /** Volver a la terminal de la sesión (en la web, mostrar el hilo que quedó al frente en tmux). */
    mostrarTerminal(): Promise<void>;
    /** Una orden de telar que vive en el anfitrión (`telar.ir`, `telar.tareas`…): en VS Code, un
     *  comando; en la web, lo que corresponda o nada. */
    orden(id: string, ...args: unknown[]): Promise<unknown>;
}

let actual: Anfitrion | undefined;

/** Quien muestra el dashboard lo dice una vez, al arrancar. */
export function usar(a: Anfitrion): void { actual = a; }

/** El anfitrión de ahora. Sin uno, fallar fuerte: es un error de quien arranca, no de quien pide. */
export function ui(): Anfitrion {
    if (!actual) throw new Error('telar: nadie dijo quién muestra el dashboard (anfitrion.usar)');
    return actual;
}
