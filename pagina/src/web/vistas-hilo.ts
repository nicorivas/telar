// Las vistas de un hilo en el navegador: distintas formas de mirar lo mismo, una a la vez, que se cambian
// con la barra de arriba del hilo o con su atajo (⌥ y una letra, también desde adentro de la terminal).
// Cada vista es una entrada de VISTAS: su nombre, su tecla y cómo se dibuja (en un elemento de la página). Una
// forma nueva de mirar un hilo es una entrada más.
import { montar as montarConversacion } from './conversacion';
import { I } from './iconos';
import { montar as montarLectura } from './lectura';
import { montar as montarTerminal } from './terminal';

export interface RutasVista { hilo: string; maquina: string }

/** Una vista dibujada en la página: se le avisa cuando vuelve a verse, y se cierra cuando ya no hace falta
 *  (sus lecturas periódicas, sus conexiones, sus teclas). */
export interface Vista {
    mostrada?(): void;
    cerrar(): void;
}

export interface VistaDeHilo {
    clave: string;
    nombre: string;
    /** su ícono en la barra de arriba del hilo (web/iconos.ts) */
    icono: string;
    /** la tecla del atajo, con ⌥: el `KeyboardEvent.code` (en macOS ⌥ cambia la letra, el código no) */
    tecla: string;
    atajo: string;
    ayuda: string;
    /** dibujarla en `el`; `volver`: a la terminal del hilo (⎋ desde la lectura) */
    montar(el: HTMLElement, rutas: RutasVista, volver: () => void): Vista;
}

export const VISTAS: VistaDeHilo[] = [
    { clave: 'term', nombre: 'terminal', icono: I.terminal, tecla: 'KeyT', atajo: '⌥T', ayuda: 'la terminal del hilo, tal cual',
        montar: (el, r) => montarTerminal(el, r) },
    { clave: 'lectura', nombre: 'lectura', icono: I.lectura, tecla: 'KeyL', atajo: '⌥L', ayuda: 'la respuesta del agente, para leerla con calma (← → recorren, ⎋ vuelve)',
        montar: (el, r, volver) => montarLectura(el, r, volver) },
    { clave: 'conv', nombre: 'conversación', icono: I.conversacion, tecla: 'KeyC', atajo: '⌥C', ayuda: 'la conversación entera, con una caja para escribirle (la del celular)',
        montar: (el, r) => montarConversacion(el, r) },
];

export const vista = (clave: string): VistaDeHilo | undefined => VISTAS.find(v => v.clave === clave);

/** Si una tecla es para la vista de `raiz`: se ve, no se está escribiendo en un campo (el buscador de la barra,
 *  la caja de la conversación), no hay un diálogo abierto, y no lleva modificadores (esos son de la página). */
export function teclaParaLaVista(e: KeyboardEvent, raiz: HTMLElement): boolean {
    if (e.altKey || e.metaKey || e.ctrlKey || raiz.hidden || !raiz.isConnected) return false;
    const t = e.target as HTMLElement | null;
    if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return false;
    return !document.querySelector('dialog[open]');
}
