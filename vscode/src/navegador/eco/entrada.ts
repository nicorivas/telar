// El eco predictivo de la terminal en el navegador, como mosh: lo que se teclea aparece al tiro, tenue, sin
// esperar el viaje al servidor, y se corrige cuando llega lo que el servidor dibujó. Es el «local echo» de
// VS Code (prediccion.ts), que se enciende solo cuando la latencia pasa de 30 ms y sus predicciones
// aciertan, y se apaga si empiezan a fallar.
//
// Lo empaqueta scripts/navegador.mjs en src/telar/web/eco.js, que carga la página de la terminal
// (web/pagina.ts, paginaTerminal):
//
//   var eco = telarEco.conEco(term);
//   ws.onmessage = e => eco.escribir(e.data);   // en vez de term.write: el eco ve lo que llega primero
import type { Terminal } from '@xterm/xterm';
import { TypeAheadAddon } from './prediccion';
import { DEFAULT_LOCAL_ECHO_EXCLUDE, Emitter, type IBeforeProcessDataEvent } from './vs';

export function conEco(term: Terminal): { escribir(datos: string): void; reiniciar(): void } {
    const llegada = new Emitter<IBeforeProcessDataEvent>();
    const eco = new TypeAheadAddon({ onBeforeProcessData: llegada.event }, {
        localEchoLatencyThreshold: 30, localEchoExcludePrograms: DEFAULT_LOCAL_ECHO_EXCLUDE,
        localEchoEnabled: 'auto', localEchoStyle: 'dim',
    });
    term.loadAddon(eco);
    return {
        escribir(datos) {
            const e = { data: datos };
            llegada.fire(e);
            term.write(e.data);
        },
        reiniciar() { eco.reset(); },
    };
}

(globalThis as { telarEco?: unknown }).telarEco = { conEco };
