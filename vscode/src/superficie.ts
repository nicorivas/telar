// La superficie: donde se dibuja el dashboard, la página del navegador (`web/`). El dashboard le manda HTML
// y mensajes, y recibe los de la página. Una capa de cuando el dashboard también vivía en un webview de la
// extensión de VS Code (deprecada, 20-oct-2026): queda hasta que la página se escriba sin ella.

export interface Superficie {
    /** El origen de sus recursos, para la política de contenido de la página (CSP). */
    readonly cspSource: string;
    /** A dónde puede conectarse la página (la web: su WebSocket). VS Code no lo necesita. */
    readonly cspConectar?: string;
    /** Se ve (no está tapada por otra pestaña). */
    readonly visible: boolean;
    /** Tiene el foco. */
    readonly activa: boolean;
    /** La página entera: estilo, cuerpo y script (ver `estilo.marco`). */
    html(pagina: string): void;
    /** Un mensaje a la página (lo recibe su script). */
    enviar(mensaje: unknown): void;
    /** Traerla al frente. */
    revelar(): void;
}

/** Lo que la superficie le avisa al dashboard. */
export interface AvisosSuperficie {
    mensaje(m: any): void;
    cerrada(): void;
    cambio(visible: boolean, activa: boolean): void;
}

/** Quien muestra el dashboard sabe crear su superficie. */
export type CrearSuperficie = (avisos: AvisosSuperficie) => Superficie;
