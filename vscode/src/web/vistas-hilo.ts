// Las vistas de un hilo en el navegador: distintas formas de mirar lo mismo, una a la vez, que se cambian
// con la barra de arriba del hilo o con su atajo (⌥ y una letra, también desde adentro de la terminal).
// Cada vista es una entrada de VISTAS: su nombre, su tecla y la página que la dibuja (en un iframe). Una
// forma nueva de mirar un hilo es una entrada más.
import { paginaConversacion, paginaLectura, paginaTerminal } from './pagina';

export interface RutasVista { hilo: string; maquina: string }

export interface VistaDeHilo {
    clave: string;
    nombre: string;
    /** la tecla del atajo, con ⌥: el `KeyboardEvent.code` (en macOS ⌥ cambia la letra, el código no) */
    tecla: string;
    atajo: string;
    ayuda: string;
    pagina(nonce: string, rutas: RutasVista & { atajos: string }): string;
}

export const VISTAS: VistaDeHilo[] = [
    { clave: 'term', nombre: 'terminal', tecla: 'KeyT', atajo: '⌥T', ayuda: 'la terminal del hilo, tal cual',
        pagina: (n, r) => paginaTerminal(n, r) },
    { clave: 'lectura', nombre: 'lectura', tecla: 'KeyL', atajo: '⌥L', ayuda: 'la respuesta del agente, para leerla con calma (← → recorren, ⎋ vuelve)',
        pagina: (n, r) => paginaLectura(n, r) },
    { clave: 'conv', nombre: 'conversación', tecla: 'KeyC', atajo: '⌥C', ayuda: 'la conversación entera, con una caja para escribirle (la del celular)',
        pagina: (n, r) => paginaConversacion(n, r) },
];

export const vista = (clave: string): VistaDeHilo | undefined => VISTAS.find(v => v.clave === clave);

/** El script que va en cada página de una vista: los atajos (⌥ y la letra) se atrapan antes que nadie (la
 *  terminal se los comería) y se le avisan a la página de arriba, que cambia la vista. */
export function scriptAtajos(): string {
    const teclas = Object.fromEntries(VISTAS.map(v => [v.tecla, v.clave]));
    return `(function () {
  var V = ${JSON.stringify(teclas)};
  window.addEventListener('keydown', function (e) {
    if (!e.altKey || e.metaKey || e.ctrlKey || !V[e.code]) return;
    e.preventDefault(); e.stopPropagation();
    parent.postMessage({ __telarVista: V[e.code] }, '*');
  }, true);
})();`;
}
