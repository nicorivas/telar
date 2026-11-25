// Lo que dice el panel de una mudanza en cada paso (web/mudanza.ts), sacado de lo que la mudanza va escribiendo
// (telar.mudanza.progreso, GET /mudanza): cuánto pesa, cuánto va copiado y cuánto ya estaba allá; y, antes de llevarlo,
// lo que el hilo tiene sin subir (telar.sin_subir), en secciones, para elegir «subir y llevar» o «llevar igual». Sin
// DOM, para probarlo en Node (`npm run prueba:llevar`).

/** Lo que llega de GET /mudanza: el mismo objeto que cli.JsonMudanza, con lo que se lee aquí. */
export interface Paso {
    paso?: string; bytes?: number;
    /** al copiar de a pedazos (telar.replica): lo que pesa todo (la conversación y su carpeta), lo que falta allá y lo
     *  que ya se mandó */
    total?: number; por_mandar?: number; mandados?: number;
    /** lo que se subió antes de llevarlo («subir y llevar») */
    subido?: string;
}

export const pesa = (b?: number) => !b ? '' : b > 1e6 ? `${(b / 1e6).toFixed(1).replace('.', ',')} MB` : `${Math.max(1, Math.round(b / 1e3))} KB`;

/** La línea de abajo del panel en el paso de `m`. `adonde`: la máquina adonde va. */
export function detalle(m: Paso, hilo: string, adonde: string): string {
    switch (m.paso) {
        case 'revisar': return `preguntándole a ${adonde} si lo puede recibir…`;
        case 'esperar': return `esperando que «${hilo}» termine su turno: lo que diga al final viaja con él…`;
        case 'subir': return m.subido ? `subido: ${m.subido}` : `subiendo lo suyo: commiteando solo lo que escribió «${hilo}»…`;
        case 'detener': return `deteniendo a su agente aquí: desde ahora su conversación no cambia, y viaja entera…`;
        case 'copiar': return copiando(m, adonde);
        case 'abrir': return `abriéndolo en ${adonde}, retomando su conversación…`;
        case 'cerrar': return `${adonde} ya lo tomó: cerrando su ventana de aquí, que esperaba…`;
        default: return '';
    }
}

function copiando(m: Paso, adonde: string): string {
    // de un telar de antes (entera), o antes de saber qué hay allá
    if (m.por_mandar === undefined) return `copiando ${pesa(m.bytes) || 'la conversación'}…`;
    const total = m.total ?? m.bytes ?? 0;
    const ya = Math.max(0, total - m.por_mandar);
    if (m.por_mandar === 0) return `${adonde} ya tenía su conversación entera (${pesa(total) || '0 KB'})…`;
    return `copiando ${pesa(m.mandados) || '0 KB'} de ${pesa(m.por_mandar)}`
        + (ya > 0 ? ` · ${pesa(ya)} ya estaban en ${adonde}` : '') + '…';
}

/** Qué parte de la copia va (0 a 1), si se sabe: para que la barra avance con lo que de verdad viaja. */
export function fraccion(m: Paso): number | undefined {
    if (m.paso !== 'copiar' || !m.por_mandar) return undefined;
    return Math.max(0, Math.min(1, (m.mandados ?? 0) / m.por_mandar));
}

/** Un repositorio del hilo, como lo ve la mudanza antes de llevarlo (telar.sin_subir.revisar). */
export interface RepoPendiente {
    nombre: string; relativa?: string; rama?: string; commit?: string;
    del_hilo?: string[]; n_del_hilo?: number; en_su_carpeta?: string[]; n_en_su_carpeta?: number;
    commits?: string[]; n_commits?: number; puede_subir?: boolean; por_que_no?: string; pendiente?: boolean;
}
/** Lo que la otra máquina tiene de cada repositorio (telar.sin_subir.en_destino). */
export interface RepoAlla { relativa: string; existe: boolean; tiene: boolean }
/** Una sección del panel: qué es, si se sube o se queda, y su lista (cortada, con cuántos más). */
export interface Seccion { tono: 'sube' | 'queda' | 'info'; titulo: string; items: string[]; mas: number }
export interface Antes { grupos: { repo: string; secciones: Seccion[] }[]; avisos: string[]; puedeSubir: boolean; hay: boolean }

/** cuántos de cada lista se muestran; el resto, «y N más» */
export const MOSTRAR = 8;

const lista = (xs: string[] | undefined, n: number | undefined): Pick<Seccion, 'items' | 'mas'> => {
    const items = (xs ?? []).slice(0, MOSTRAR);
    return { items, mas: Math.max(0, (n ?? xs?.length ?? 0) - items.length) };
};
const plural = (n: number, uno: string, varios: string) => `${n} ${n === 1 ? uno : varios}`;

/** Lo que el panel muestra antes de llevar un hilo, de lo que dejó la mudanza en su progreso: por repositorio, lo que se
 *  sube con «subir y llevar» (lo suyo sin commitear, los commits sin subir), lo que se queda (lo de su carpeta que no
 *  se sabe si es suyo, lo que no se puede subir) y si `adonde` va atrás (al llegar se trae de arriba); y lo que llegaría
 *  a medias (`avisos`). `hay`: si hay algo que elegir; si no, el panel ni pregunta. */
export function antes(m: { pendiente?: { repos?: RepoPendiente[] }; destino?: RepoAlla[]; avisos?: string[] },
    adonde: string): Antes {
    const alla = new Map((m.destino ?? []).map(d => [d.relativa, d]));
    const grupos: Antes['grupos'] = [];
    let puedeSubir = false, hayRepo = false;
    for (const r of m.pendiente?.repos ?? []) {
        const s: Seccion[] = [];
        const nh = r.n_del_hilo ?? r.del_hilo?.length ?? 0, nc = r.n_commits ?? r.commits?.length ?? 0;
        const nq = r.n_en_su_carpeta ?? r.en_su_carpeta?.length ?? 0;
        const sube = !!r.puede_subir;
        if (nh) s.push({ tono: sube ? 'sube' : 'queda', ...lista(r.del_hilo, nh),
            titulo: `${plural(nh, 'archivo', 'archivos')} de este hilo sin commitear${sube ? (nh === 1 ? ': se commitea y se sube' : ': se commitean y se suben') : ''}` });
        if (nc) s.push({ tono: sube ? 'sube' : 'queda', ...lista(r.commits, nc),
            titulo: `${plural(nc, 'commit', 'commits')} sin subir${sube ? (nc === 1 ? ': se sube' : ': se suben') : ''}` });
        if (nq) s.push({ tono: 'queda', ...lista(r.en_su_carpeta, nq),
            titulo: `${plural(nq, 'archivo', 'archivos')}${nh ? ' más' : ''} sin commitear en su carpeta: ${nq === 1 ? 'no sé si es suyo, no se sube' : 'no sé si son suyos, no se suben'}` });
        if (r.pendiente && r.por_que_no) s.push({ tono: 'queda', titulo: `no se puede subir: ${r.por_que_no}`, items: [], mas: 0 });
        const d = r.relativa ? alla.get(r.relativa) : undefined;
        if (d?.existe && !d.tiene)
            s.push({ tono: 'info', titulo: `${adonde} va atrás${r.commit ? ` (no tiene ${r.commit.slice(0, 7)})` : ''}: al llegar se trae de arriba`, items: [], mas: 0 });
        if (r.pendiente) hayRepo = true;
        if (r.pendiente && sube) puedeSubir = true;
        if (s.length) grupos.push({ repo: r.rama ? `${r.nombre} · ${r.rama}` : r.nombre, secciones: s });
    }
    const avisos = m.avisos ?? [];
    return { grupos, avisos, puedeSubir, hay: hayRepo || avisos.length > 0 };
}
