// La mudanza de un hilo a otra máquina, a la vista (docs/propuestas/mudanza.md): un panel con el nombre de la máquina
// en letras grandes, una barra de carga y los pasos (revisar, cerrar, copiar, abrir, listo), que sigue lo que la
// mudanza va escribiendo (telar.mudanza.progreso, GET /mudanza). Mientras dura, la fila del hilo en la barra dice
// que está viajando (`modelo.mudando`). Si allá falta algo para recibirlo bien (su carpeta sin clonar, trabajo sin
// subir), se pregunta aquí mismo; si falla, el panel dice por qué (y el hilo ya volvió a abrirse aquí). Al llegar,
// va a su terminal allá.

import * as cli from '../cli';
import { modelo } from '../modelo';
import { C, I } from './iconos';
import { grande } from './letras';

function el<K extends keyof HTMLElementTagNameMap>(tag: K, clase = '', texto?: string): HTMLElementTagNameMap[K] {
    const e = document.createElement(tag);
    if (clase) e.className = clase;
    if (texto !== undefined) e.textContent = texto;
    return e;
}

const PASOS: [string, string][] = [
    ['revisar', 'revisar allá'], ['cerrar', 'cerrar aquí'], ['copiar', 'copiar la conversación'], ['abrir', 'abrir allá'],
    ['listo', 'listo'],
];
/** dónde empieza cada paso en la barra (el resto lo va llenando de a poco mientras dura) */
const DESDE: Record<string, number> = { revisar: 0.02, cerrar: 0.12, copiar: 0.2, abrir: 0.82, listo: 1 };
const GIRA = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏';
const ANCHO = 42;

const pesa = (b?: number) => !b ? '' : b > 1e6 ? `${(b / 1e6).toFixed(1).replace('.', ',')} MB` : `${Math.max(1, Math.round(b / 1e3))} KB`;

/** El panel: lo que se ve, y cómo cambiarlo. */
function panel(hilo: string, maquina: string) {
    const c = el('dialog', 'mudanza');
    const arriba = el('div', 'arriba', `llevando «${hilo}» a`);
    const letras = el('pre', 'letras', grande(maquina).join('\n'));
    const barra = el('pre', 'barra');
    const pasos = el('div', 'pasos');
    const linea = el('div', 'linea');
    const botones = el('div', 'botones');
    c.append(arriba, letras, barra, pasos, linea, botones);
    document.body.appendChild(c);
    c.showModal();

    let valor = 0, meta = 0.02, paso = 'revisar', estado: 'va' | 'listo' | 'falla' | 'pregunta' = 'va', vuelta = 0;
    const pintar = () => {
        const llenas = Math.round(valor * ANCHO);
        barra.textContent = `[${'█'.repeat(llenas)}${'░'.repeat(ANCHO - llenas)}] ${String(Math.round(valor * 100)).padStart(3)}%`;
        barra.dataset.estado = estado;
        pasos.replaceChildren(...PASOS.map(([clave, nombre]) => {
            const i = PASOS.findIndex(([k]) => k === clave), j = PASOS.findIndex(([k]) => k === paso);
            const hecho = estado === 'listo' || i < j, ahora = i === j && estado !== 'listo';
            const s = el('span', `paso${hecho ? ' hecho' : ahora ? ` ahora ${estado}` : ''}`);
            s.append(el('span', `i ico`, hecho ? I.hecha : ahora ? (estado === 'falla' ? I.cerrar : GIRA[vuelta % GIRA.length]) : '○'),
                el('span', '', nombre));
            return s;
        }));
    };
    // la barra avanza sola hacia donde va: dentro de un paso largo (copiar) se sigue moviendo, cada vez más lento,
    // sin llegar al paso siguiente; así nunca se queda quieta mientras algo pasa
    const reloj = setInterval(() => {
        vuelta++;
        if (estado === 'va') {
            const sig = PASOS[PASOS.findIndex(([k]) => k === paso) + 1]?.[0];
            const techo = sig ? DESDE[sig] - 0.01 : 1;
            meta = Math.max(meta, Math.min(techo, meta + (techo - meta) * 0.03));
        }
        valor += (meta - valor) * 0.25;
        pintar();
    }, 80);
    pintar();
    return {
        dialogo: c,
        paso(p: string, detalle = '') {
            if (estado !== 'va' || !(p in DESDE)) return;
            paso = p; meta = Math.max(meta, DESDE[p]);
            linea.textContent = detalle;
        },
        listo(texto: string) {
            estado = 'listo'; paso = 'listo'; meta = 1;
            letras.textContent = grande('listo').join('\n');
            letras.dataset.estado = 'listo';
            linea.textContent = texto;
        },
        falla(texto: string) {
            estado = 'falla'; meta = valor;
            letras.dataset.estado = 'falla';
            linea.textContent = texto;
            boton('cerrar', C.quitar, () => cerrar());
        },
        /** lo que allá llegaría a medias: llevar igual, o no */
        preguntar(texto: string): Promise<boolean> {
            estado = 'pregunta';
            linea.textContent = texto;
            return new Promise(si => {
                boton('llevar igual', C.hecho, () => { botones.replaceChildren(); estado = 'va'; si(true); });
                boton('no llevarlo', C.quitar, () => { cerrar(); si(false); });
            });
        },
        cerrar,
    };
    function boton(nombre: string, color: string, hacer: () => void): void {
        const a = el('a', '', nombre);
        a.style.color = `var(--${color})`;
        a.addEventListener('click', hacer);
        botones.appendChild(a);
    }
    function cerrar(): void { clearInterval(reloj); if (c.open) c.close(); c.remove(); }
}

/** Llevar `hilo` a `maquina`, con su transición a la vista. `alLlegar` va a su terminal allá. */
export async function llevar(hilo: string, maquina: string, alLlegar: () => Promise<void> | void): Promise<void> {
    const p = panel(hilo, maquina);
    const desde = Date.now() / 1000 - 1;
    modelo.mudando.set(hilo, maquina);
    modelo.cambio.fire();
    let siguiendo = true;
    // lo que la mudanza va escribiendo (solo lo de esta vez: uno viejo se descarta por la hora)
    const seguir = (async () => {
        while (siguiendo) {
            const r = await cli.mudanza(hilo);
            const m = r.datos;
            if (m?.paso && (m.hora ?? 0) >= desde) {
                const detalle = m.paso === 'copiar' ? `copiando ${pesa(m.bytes) || 'la conversación'}…`
                    : m.paso === 'abrir' ? `abriéndolo en ${maquina}, retomando su conversación…`
                    : m.paso === 'cerrar' ? 'cerrándolo aquí, para que no siga en dos máquinas a la vez…'
                    : m.paso === 'revisar' ? `preguntándole a ${maquina} si lo puede recibir…` : '';
                p.paso(m.paso, detalle);
            }
            await new Promise(r => setTimeout(r, 300));
        }
    })();
    try {
        let si = false;
        for (;;) {
            let r = await cli.llevar(hilo, maquina, si);
            // lo que pide confirmar (allá llegaría a medias, o aquí hay trabajo sin subir): se pregunta en el panel
            if (r.error && /llevarla igual|sin subir/.test(r.error)) {
                const salida = String(r.cuerpo?.salida ?? r.error);
                const lista = salida.split('\n').filter(l => l.trim().startsWith('·')).map(l => l.trim()).join('\n');
                if (!(await p.preguntar(lista || r.error))) return;
                si = true;
                continue;
            }
            if (r.error) { p.falla(r.error); return; }
            // una conversación grande sigue viajando: se espera a que el progreso diga listo o falla
            if (r.datos?.en_curso) {
                const limite = Date.now() + 15 * 60_000;
                for (;;) {
                    const m = (await cli.mudanza(hilo)).datos;
                    if (m?.paso === 'falla' && (m.hora ?? 0) >= desde) { p.falla(m.error ?? 'no se llevó'); return; }
                    if (m?.paso === 'listo' && (m.hora ?? 0) >= desde) break;
                    if (Date.now() > limite) { p.falla('sigue viajando: aparece allá al terminar'); return; }
                    await new Promise(x => setTimeout(x, 700));
                }
                r = { datos: { ...r.datos, en_curso: false } };
            }
            const m = (await cli.mudanza(hilo)).datos;
            p.listo(m?.aviso ? `llegó a ${maquina} · ${m.aviso}` : `llegó a ${maquina}: sigue ahí, con su conversación`);
            modelo.invalidar();
            await modelo.sondear();
            await new Promise(x => setTimeout(x, 1600));
            p.cerrar();
            await alLlegar();
            return;
        }
    } finally {
        siguiendo = false;
        await seguir;
        modelo.mudando.delete(hilo);
        modelo.cambio.fire();
    }
}

/** La transición sin mudar nada, con tiempos inventados: para mirarla y afinarla (`window.telar.ensayoMudanza()`). */
export async function ensayo(maquina = 'telar', falla = false): Promise<void> {
    const p = panel('prueba', maquina);
    const espera = (ms: number) => new Promise(r => setTimeout(r, ms));
    p.paso('revisar', `preguntándole a ${maquina} si lo puede recibir…`); await espera(900);
    p.paso('cerrar', 'cerrándolo aquí, para que no siga en dos máquinas a la vez…'); await espera(700);
    p.paso('copiar', 'copiando 2,3 MB…'); await espera(3200);
    if (falla) { p.falla(`${maquina} recibió la conversación pero no abrió el hilo: no pude abrir el hilo: claude no está en el PATH. Se volvió a abrir aquí, con su conversación.`); return; }
    p.paso('abrir', `abriéndolo en ${maquina}, retomando su conversación…`); await espera(1400);
    p.listo(`llegó a ${maquina}: sigue ahí, con su conversación`);
    await espera(2500);
    p.cerrar();
}
