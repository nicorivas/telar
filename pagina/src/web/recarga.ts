// Ponerse al día después de un despliegue. Desplegar telar es `git pull` y reiniciar el servicio en cada máquina, y una
// página que ya estaba abierta (la del teléfono queda abierta días) seguía corriendo el app.js que cargó.
//
// La página trae escrita la firma de lo que se le sirvió (`<meta name="telar-pagina">`, que llena telar.api_web) y le
// pregunta al servicio por la suya (`/pagina.json`): al volver a mirarla, cuando el servicio vuelve de reiniciarse (lo
// avisa navegador/app.ts) y cada medio minuto. Es la de esta máquina, la que sirve la página, aunque se mire un hilo de
// otra. Si es otra:
//
//   - sin mirarla (oculta: otra pestaña, otra app, el teléfono bloqueado), recarga sola, ahí mismo o al volver a
//     mirarla, antes de que se alcance a usar la vieja;
//   - mirándola, no recarga debajo de las manos: lo dice la franja de avisos, arriba de la barra (web/version.ts), y
//     «recargar» recarga.
//
// Nada se pierde: lo escrito se guarda mientras se escribe (web/guardado.ts) y lo que se miraba se retoma al cargar
// (`lugarAlRecargar`). Lo que no se podría retomar cuenta como «en uso» y entonces no recarga sola, avisa: una ventana
// abierta, un campo con algo escrito que nadie guarda, y lo que cada vista diga (`enUso`: algo enviándose).
// Mientras el servicio se reinicia no contesta: lo que se sabía sigue, y solo se recarga con una respuesta en la mano.

/** cada cuánto se pregunta, además de al volver a mirarla y al volver el servicio */
const CADA = 30 * 1000;
/** cuánto después de volver a mirarla (o de cargar), sin tocarla, recargar todavía no le quita nada a nadie */
const GRACIA = 5000;
/** adónde iba la última recarga (sessionStorage): si la página nueva no es esa, no se insiste sola */
const HACIA = 'telar.recarga.hacia';
/** lo que se miraba (sessionStorage), para retomarlo al recargar */
const LUGAR = 'telar.recarga.lugar';

const propia = document.querySelector<HTMLMetaElement>('meta[name="telar-pagina"]')?.content ?? '';
/** la firma que dice el servicio, si es otra que la propia ('' al día) */
let nueva = '';
/** una recarga hacia esta firma no la trajo (un intermediario que guardó la vieja): solo el aviso */
let noInsistir = '';
let volvio = Date.now();
let toco = false;
const enUsoPor = new Set<() => boolean>();
const oyentes = new Set<() => void>();

try {
    const hacia = sessionStorage.getItem(HACIA);
    sessionStorage.removeItem(HACIA);
    if (hacia && hacia !== propia) noInsistir = hacia;
} catch { /* sin almacén */ }

/** Si hay una página nueva que esta todavía no es. */
export const hayNueva = (): boolean => !!nueva;

/** Avisar cuando cambia si hay una nueva (para el aviso de arriba). */
export function alCambiar(f: () => void): void { oyentes.add(f); }

/** Algo de una vista que recargar perdería (un envío en camino): mientras diga que sí, no se recarga sola. Devuelve cómo
 *  dejar de preguntarle. */
export function enUso(f: () => boolean): () => void {
    enUsoPor.add(f);
    return () => { enUsoPor.delete(f); };
}

const escribible = (e: Element | null): e is HTMLInputElement | HTMLTextAreaElement =>
    !!e && /^(INPUT|TEXTAREA)$/.test(e.tagName) && !(e as HTMLInputElement).readOnly && !['checkbox', 'radio', 'button', 'submit'].includes((e as HTMLInputElement).type);

function ocupada(): boolean {
    if (document.querySelector('dialog[open]')) return true;
    const a = document.activeElement;
    if (escribible(a) && a.dataset.guarda === undefined && a.value.trim()) return true;
    if (a instanceof HTMLElement && a.isContentEditable && a.textContent?.trim()) return true;
    for (const f of enUsoPor) {
        try { if (f()) return true; } catch { return true; }
    }
    return false;
}

/** Recargar ahora: lo escrito y lo que se mira quedan guardados (al irse la página: `pagehide`). */
export function recargar(): void {
    try { if (nueva) sessionStorage.setItem(HACIA, nueva); } catch { /* sin almacén */ }
    location.reload();
}

/** Si ya se sabe de una nueva: recargar si no se mira (o si recién se volvió a mirar y no se ha tocado) y nada se
 *  perdería. Si no, queda el aviso. */
function intentar(): void {
    if (!nueva || nueva === noInsistir || ocupada()) return;
    const recien = !toco && Date.now() - volvio < GRACIA;
    if (document.hidden || recien) recargar();
}

let pidiendo: Promise<void> | null = null;
/** Preguntarle al servicio por su página. Sin respuesta (se reinicia, sin red), lo que se sabía sigue. */
export function revisar(): Promise<void> {
    if (!propia) return Promise.resolve();
    pidiendo ??= (async () => {
        try {
            const r = await fetch('/pagina.json', { cache: 'no-store' });
            if (!r.ok) return;
            const firma = (await r.json() as { firma?: string }).firma;
            if (!firma) return;
            const antes = nueva;
            nueva = firma === propia ? '' : firma;
            if (nueva !== antes) for (const f of oyentes) f();
            intentar();
        } catch { /* reiniciándose: se sabe lo de antes */ } finally { pidiendo = null; }
    })();
    return pidiendo;
}

/** Volvió a mirarse (o salió de estar congelada): hasta que se toque, recargar no le quita nada. */
function alVolver(): void {
    volvio = Date.now();
    toco = false;
    void revisar();
}

document.addEventListener('visibilitychange', () => {
    if (document.hidden) intentar();   // ya se sabía: ahora que no se mira
    else alVolver();
});
window.addEventListener('pageshow', e => { if (e.persisted) alVolver(); });
// (Chrome congela una página oculta y la descongela al volver; el teléfono, al desbloquearlo)
document.addEventListener('resume', alVolver);
window.addEventListener('online', () => void revisar());
for (const ev of ['pointerdown', 'keydown', 'wheel', 'touchstart']) window.addEventListener(ev, () => { toco = true; }, { capture: true, passive: true });
setInterval(() => void revisar(), CADA);
setTimeout(() => void revisar(), 1500);

// ── lo que se miraba ──────────────────────────────────────────────────────────

/** Lo que se miraba: `que` (lo de la derecha: `dashboard`, un hilo, `rem:<máquina>:<hilo>`, `arch:<ruta>`…), con qué
 *  vista si es un hilo, en qué pestaña si es el dashboard, y si en el celular se estaba en la lista. */
export interface Lugar { que: string; como?: string; pestana?: string; lista?: boolean }

let lugarDe: (() => Lugar) | undefined;
/** De dónde sale lo que se mira (navegador/app.ts): se guarda al irse la página y al dejar de mirarla. */
export function lugar(f: () => Lugar): void { lugarDe = f; }
function anotarLugar(): void {
    if (!lugarDe) return;
    try { sessionStorage.setItem(LUGAR, JSON.stringify(lugarDe())); } catch { /* sin almacén */ }
}
window.addEventListener('pagehide', anotarLugar);
document.addEventListener('visibilitychange', () => { if (document.hidden) anotarLugar(); });

/** Lo que se miraba antes de recargar (una recarga: la de aquí, F5, o el navegador que la había descartado); abrirla
 *  de nuevo empieza como siempre. */
export function lugarAlRecargar(): Lugar | undefined {
    const nav = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined;
    const descartada = (document as Document & { wasDiscarded?: boolean }).wasDiscarded;
    if (nav?.type !== 'reload' && !descartada) return undefined;
    try {
        const l = JSON.parse(sessionStorage.getItem(LUGAR) ?? 'null') as Lugar | null;
        return l && typeof l.que === 'string' && l.que ? l : undefined;
    } catch { return undefined; }
}
