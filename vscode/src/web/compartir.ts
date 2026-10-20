// Lo que el teléfono le comparte a la página instalada como app (`share_target` del manifiesto, que la abre en
// /compartir): un enlace o un texto, para llevarlo a un hilo, a un agente o a un proveedor que lo recibe (un
// feed de lecturas). Lo lleva `POST /api/compartir`. Se dibuja en un elemento de la página; sus estilos, en
// media/css/compartir.css (con @scope, en `.v-compartir`).

function el<K extends keyof HTMLElementTagNameMap>(tag: K, clase = '', texto?: string): HTMLElementTagNameMap[K] {
    const e = document.createElement(tag);
    if (clase) e.className = clase;
    if (texto !== undefined) e.textContent = texto;
    return e;
}

interface Destino { destino: string; nombre: string; tipo: string }

/** `consulta`: lo que llegó en la dirección (`?title=…&text=…&url=…`). */
export function montar(raiz: HTMLElement, consulta: string): void {
    raiz.classList.add('v-compartir');
    raiz.innerHTML = '<header><a href="/">◀ telar</a><b>compartir</b></header><main>'
        + '<section class="que"></section>'
        + '<textarea class="nota" rows="3" placeholder="una nota, si quieres (va con lo compartido)"></textarea>'
        + '<input class="filtro" placeholder="filtrar destinos" autocomplete="off">'
        + '<div class="destinos"><p class="dim">leyendo destinos…</p></div><p class="dicho dim"></p></main>';
    const $ = <T extends HTMLElement>(s: string) => raiz.querySelector<T>(s)!;
    const q = new URLSearchParams(consulta);
    const titulo = (q.get('title') ?? '').trim();
    let texto = (q.get('text') ?? '').trim(), url = (q.get('url') ?? '').trim();
    // muchas apps mandan el enlace dentro del texto, no en url
    if (!url) { const m = texto.match(/https?:\/\/\S+/); if (m) { url = m[0]; texto = texto.replace(m[0], '').trim(); } }
    const que = $('.que');
    if (titulo) que.appendChild(el('div', 'titulo', titulo));
    if (url) que.appendChild(el('div', 'url', url));
    if (texto) que.appendChild(el('div', 'texto', texto));
    if (!titulo && !url && !texto) que.appendChild(el('div', 'dim', 'nada compartido: escribe una nota y elige a dónde'));
    const dicho = $('.dicho'), filtro = $<HTMLInputElement>('.filtro'), nota = $<HTMLTextAreaElement>('.nota'), cont = $('.destinos');
    let lista: Destino[] = [];

    const llevar = async (d: Destino, b: HTMLButtonElement) => {
        const escrita = nota.value.trim();
        if (!url && !texto && !escrita) { dicho.textContent = 'no hay nada que llevar'; return; }
        b.disabled = true; dicho.className = 'dicho dim'; dicho.textContent = `llevando a ${d.nombre}…`;
        try {
            const r = await (await fetch('/api/compartir', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ a: d.destino, url, titulo, texto: [escrita, texto].filter(Boolean).join('\n') }),
            })).json() as { ok?: boolean; dicho?: string; error?: string };
            dicho.className = `dicho ${r.ok ? 'bien' : 'mal'}`;
            dicho.textContent = r.ok ? (r.dicho || 'listo') : (r.error || 'no salió');
        } catch {
            dicho.className = 'dicho mal'; dicho.textContent = 'sin conexión con telar';
        }
        b.disabled = false;
    };
    const pintar = () => {
        const f = filtro.value.toLowerCase();
        cont.textContent = '';
        for (const [tipo, nombre] of [['proveedor', 'guardar en'], ['hilo', 'mandar a un hilo']]) {
            const de = lista.filter(d => d.tipo === tipo && (!f || d.nombre.toLowerCase().includes(f)));
            if (!de.length) continue;
            cont.appendChild(el('div', 'grupo', nombre));
            for (const d of de) {
                const b = el('button', 'destino', d.nombre);
                b.addEventListener('click', () => void llevar(d, b));
                cont.appendChild(b);
            }
        }
    };
    filtro.addEventListener('input', pintar);

    // los proveedores que reciben, y los hilos (de esta máquina y de las otras)
    const hilos = fetch('/api/hilos?ficha=false&red=true').then(r => r.json())
        .then((d: { hilos?: { nombre: string; archivado?: boolean }[] }) => (d.hilos ?? []).filter(h => !h.archivado)
            .map(h => ({ destino: `hilo:${h.nombre}`, nombre: h.nombre, tipo: 'hilo' })))
        .catch(() => [] as Destino[]);
    fetch('/api/compartir/destinos').then(r => r.json())
        .then(async (d: { destinos?: Destino[] }) => { lista = [...(d.destinos ?? []), ...await hilos]; pintar(); })
        .catch(() => { cont.textContent = 'no pude leer los destinos'; });
}
