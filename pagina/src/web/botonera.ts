// Las teclas de los botones con texto (componentes/boton.ts) en una ventana o en una franja de la página: lo que dice cada
// celda es lo que hace. abrirVentana (web/ventana.ts) lo pone en cada ventana que abre; la instrucción, la mudanza y la
// franja de soltar en la terminal, que todavía no son ventanas, lo ponen ellas.
//
// · La tecla de un botón (⌘⌫, ⌘⏎, 1, 2…) lo aprieta tenga o no el foco; ⌫ y los números no, si se está escribiendo en un
//   campo (son del campo).
// · ⏎ aprieta el botón que tiene el foco, y solo ese: en lo que destruye el foco parte en cancelar, así que ahí ⏎ cancela.
// · Una tecla sostenida (`repeat`: el ⏎ que abrió la ventana desde una fila, apretado todavía) no aprieta nada.
// · ⎋ es de la ventana (el `cancel` del <dialog>); en una franja, que no es ventana, aprieta su botón de ⎋.
// · Lo que se atiende aquí no sigue a la página (el dashboard tiene atajos de una letra) ni a otros oyentes de la ventana.

/** La tecla de un evento, como la dice un botón: ⌘ (o ⌃) ⌥ ⇧ y la tecla (⏎, ⎋, ⌫, una letra o un número). */
export function teclaDelEvento(e: KeyboardEvent): string {
    const nombres: Record<string, string> = { Enter: '⏎', Escape: '⎋', Backspace: '⌫', Delete: '⌫', Tab: '⇥' };
    const tecla = nombres[e.key] ?? (e.key.length === 1 ? e.key.toLowerCase() : e.key);
    // ⇧ solo cuenta en lo que no escribe (⇧⏎): en una letra o un signo ya está en lo que dio
    return `${e.metaKey || e.ctrlKey ? '⌘' : ''}${e.altKey ? '⌥' : ''}${e.shiftKey && e.key.length > 1 ? '⇧' : ''}${tecla}`;
}

const enCampo = (t: EventTarget | null) => !!(t as HTMLElement | null)?.closest?.('input, textarea, select, [contenteditable]');

/** Atiende las teclas de los botones de `raiz`. Devuelve cómo dejar de hacerlo. */
export function teclasDeBotones(raiz: HTMLElement): () => void {
    const alTeclear = (e: KeyboardEvent) => {
        if (e.isComposing || e.defaultPrevented) return;
        const tecla = teclaDelEvento(e);
        const parar = () => { e.preventDefault(); e.stopImmediatePropagation(); };
        const objetivo = e.target as HTMLElement;
        // ⏎ solo: el botón con el foco
        if (tecla === '⏎') {
            const b = objetivo.closest?.<HTMLButtonElement>('button.boton');
            if (!b || !raiz.contains(b)) return;
            parar();
            if (!e.repeat && !b.disabled) b.click();
            return;
        }
        if (tecla === '⎋' && raiz.closest('dialog')) return;
        const b = [...raiz.querySelectorAll<HTMLButtonElement>('button.boton[data-tecla]')].find(x => x.dataset.tecla === tecla);
        if (!b) return;
        // en un campo, ⌫ y lo que se escribe son del campo; un acorde con ⌘ que no borra (⌘⏎), del botón
        if (enCampo(objetivo) && (/⌫$/.test(tecla) || !tecla.startsWith('⌘'))) return;
        parar();
        if (!e.repeat && !b.disabled) b.click();
    };
    raiz.addEventListener('keydown', alTeclear);
    return () => raiz.removeEventListener('keydown', alTeclear);
}
