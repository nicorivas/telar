// El eco de la terminal en el navegador, como mosh: lo que se teclea aparece al tiro, tenue, sin esperar el
// viaje al servidor (220 ms del laptop al servidor, el doble con un hilo reenviado).
//
// Hecho para Claude Code, que con cada tecla vuelve a dibujar la pantalla entera (el eco de VS Code espera
// que la letra vuelva sola, como en una shell, y con Claude Code nunca acierta). Aquí no se adivina qué va a
// mandar el servidor: después de cada cuadro que llega se mira la línea del cursor, se dan por confirmadas
// las letras pendientes que ya están antes del cursor, y las que faltan se vuelven a dibujar, tenues. Como el
// cuadro siguiente redibuja todo, lo que sobre se corrige solo.
//
// Lo empaqueta scripts/navegador.mjs en src/telar/web/eco.js; lo usa la página de la terminal
// (web/pagina.ts, paginaTerminal):
//
//   var eco = telarEco.conEco(term);
//   ws.onmessage = e => eco.escribir(e.data);    // en vez de term.write
//   term.onData(d => { eco.tecleado(d); enviar(d); });
import type { Terminal } from '@xterm/xterm';

/** Desde qué latencia (la mediana de las últimas confirmaciones, en ms) se muestra el eco. */
const DESDE_MS = 40;
/** Una letra que el servidor no confirma en este tiempo se da por perdida (y se deja de predecir). */
const PERDIDA_MS = 3000;

const ESC = '\x1b';
const GUARDAR = `${ESC}7`;      // DECSC: la posición y los atributos del cursor
const VOLVER = `${ESC}8`;       // DECRC
const TENUE = `${ESC}[2m`;
// salida sincronizada (DEC 2026): xterm no dibuja entre el comienzo y el fin, así un cuadro y su eco se ven
// juntos (si no, el cursor salta al lugar del servidor y de vuelta al del eco con cada cuadro)
const SINCRO = `${ESC}[?2026h`, FIN_SINCRO = `${ESC}[?2026l`;

export interface EstadoEco { mostrando: boolean; pendientes: string; latencia: number; muestras: number }

export function conEco(term: Terminal): {
    escribir(datos: string): void; tecleado(datos: string): void; reiniciar(): void; estado(): EstadoEco;
} {
    /** lo tecleado que el servidor todavía no muestra, con cuándo se tecleó */
    let pendientes: { c: string; t: number }[] = [];
    /** cuántas celdas del eco hay dibujadas ahora, a partir de la posición guardada (GUARDAR) */
    let dibujadas = 0;
    /** lo que tarda una letra en aparecer: las últimas confirmaciones, en ms */
    const latencias: number[] = [];
    /** el cursor del servidor: el último cuadro lo dejó visible o escondido */
    let cursorVisible = true;
    /** los cuadros se escriben de a uno: el eco de uno se dibuja antes de escribir el siguiente */
    let cola = Promise.resolve();

    const mediana = () => {
        if (!latencias.length) return 0;
        const o = [...latencias].sort((a, b) => a - b);
        return o[Math.floor(o.length / 2)];
    };
    const mostrando = () => mediana() >= DESDE_MS;

    /** Borra el eco dibujado: vuelve a la posición guardada, pone espacios donde estaba y vuelve otra vez. */
    const borrar = () => {
        if (!dibujadas) return '';
        const s = VOLVER + ' '.repeat(dibujadas) + VOLVER;
        dibujadas = 0;
        return s;
    };

    /** Si en la línea del cursor no hay nada después de él (solo espacios: Claude Code rellena su caja con
     *  espacios duros): solo ahí se predice, para no pisar texto. */
    const alFinal = () => {
        const b = term.buffer.active;
        const linea = b.getLine(b.baseY + b.cursorY);
        return !!linea && /^[\s\u00a0]*$/.test(linea.translateToString(false).slice(b.cursorX));
    };

    /** Lo pendiente, tenue, a partir del cursor (el cursor queda después, como si ya hubiera llegado); "" si
     *  no corresponde dibujarlo. Lo escribe quien llama, junto con lo demás. */
    const eco = () => {
        if (!pendientes.length || !mostrando() || !cursorVisible || !alFinal()) return '';
        const texto = pendientes.map(p => p.c).join('');
        if (term.buffer.active.cursorX + texto.length >= term.cols) return '';
        dibujadas = texto.length;
        return GUARDAR + TENUE + texto;
    };

    /** Después de un cuadro: cuántas de las pendientes ya están antes del cursor (la confirmación es por el
     *  contenido, no por adivinar qué manda el servidor). */
    const confirmar = () => {
        if (!pendientes.length) return;
        const b = term.buffer.active;
        const antes = (b.getLine(b.baseY + b.cursorY)?.translateToString(false) ?? '').slice(0, b.cursorX);
        let m = 0;
        for (let k = pendientes.length; k > 0; k--) {
            if (antes.endsWith(pendientes.slice(0, k).map(p => p.c).join(''))) { m = k; break; }
        }
        const ahora = performance.now();
        for (const p of pendientes.slice(0, m)) {
            latencias.push(ahora - p.t);
            if (latencias.length > 15) latencias.shift();
        }
        pendientes = pendientes.slice(m).filter(p => ahora - p.t < PERDIDA_MS);
    };

    return {
        escribir(datos) {
            cola = cola.then(() => new Promise<void>(listo => {
                // el estado del cursor que deja este cuadro: el último ?25h / ?25l que trae
                const v = datos.lastIndexOf(`${ESC}[?25h`), e = datos.lastIndexOf(`${ESC}[?25l`);
                if (v >= 0 || e >= 0) cursorVisible = v > e;
                // el cuadro y su eco, en una sola salida sincronizada
                term.write(SINCRO + borrar() + datos, () => { confirmar(); term.write(eco() + FIN_SINCRO, listo); });
            }));
        },
        tecleado(datos) {
            // una letra imprimible (una sola: un pegado no se predice)
            if (datos.length === 1 && datos >= ' ' && datos !== '\x7f') {
                pendientes.push({ c: datos, t: performance.now() });
                if (!mostrando() || !cursorVisible) return;
                if (dibujadas) {
                    term.write(datos);
                    dibujadas++;
                } else {
                    const e = eco();
                    if (e) term.write(e);
                }
                return;
            }
            // ⌫ deshace la última letra pendiente (la que todavía no confirma el servidor)
            if (datos === '\x7f' && pendientes.length) {
                pendientes.pop();
                if (dibujadas) { term.write('\b \b'); dibujadas--; }
                return;
            }
            // cualquier otra cosa (⏎, ⎋, flechas, ctrl): ya no se sabe qué va a dibujar el servidor
            pendientes = [];
            if (dibujadas) term.write(borrar());
        },
        reiniciar() { pendientes = []; dibujadas = 0; cursorVisible = true; },
        estado() {
            return { mostrando: mostrando(), pendientes: pendientes.map(p => p.c).join(''), latencia: Math.round(mediana()), muestras: latencias.length };
        },
    };
}

(globalThis as { telarEco?: unknown }).telarEco = { conEco };
