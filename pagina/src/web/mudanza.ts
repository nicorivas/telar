// La mudanza de un hilo a otra máquina, a la vista: un panel con el nombre de la máquina en letras grandes, una barra
// de carga y los pasos (revisar, esperar su turno, copiar, abrir, cerrar, listo), que sigue lo que la mudanza va
// escribiendo (telar.mudanza.progreso, GET /mudanza; la de otra máquina, si se pidió traerlo de ella). Aquí no se
// cierra nada hasta que allá lo abrió: cerrar es el penúltimo.
// Mientras dura, la fila del hilo en la barra dice que está viajando (`modelo.mudando`). Si el hilo tiene algo sin subir
// (telar.sin_subir) o allá llegaría a medias (su carpeta sin clonar, sus hijos con rama), el panel lo muestra entero,
// repositorio por repositorio (lo que se sube y lo que se queda), y se elige ahí mismo: «subir y llevar», «llevar igual»
// o no llevarlo. Si no hay nada, ni se ve. Si falla, el panel dice por qué (y el hilo sigue aquí como estaba). Al llegar,
// va a su terminal allá.
//
// El mismo panel sirve para **seguir aquí** un hilo cuya máquina está apagada, desde la copia de aquí (telar.seguir, la
// etapa 4): primero dice de cuándo es la copia y cuánto falta, y se elige seguirlo o no (`seguirAqui`).

import * as cli from '../cli';
import { modelo } from '../modelo';
import { C, I } from './iconos';
import { grande } from './letras';
import { boton as botonHtml, cancelar, type Boton } from '../componentes/boton';
import { teclasDeBotones } from './botonera';
import { antes, detalle, fraccion, type Antes } from './mudanza-texto';

function el<K extends keyof HTMLElementTagNameMap>(tag: K, clase = '', texto?: string): HTMLElementTagNameMap[K] {
    const e = document.createElement(tag);
    if (clase) e.className = clase;
    if (texto !== undefined) e.textContent = texto;
    return e;
}

const PASOS: [string, string][] = [
    ['revisar', 'revisar allá'], ['esperar', 'esperar su turno'], ['subir', 'subir lo suyo'], ['detener', 'detenerlo aquí'],
    ['copiar', 'copiar lo que falta'], ['abrir', 'abrir allá'], ['cerrar', 'cerrar aquí'], ['listo', 'listo'],
];
/** los pasos que solo se ven si pasaron: esperar su turno (si estaba en medio de uno) y subir lo suyo (si se eligió) */
const OPCIONALES = new Set(['esperar', 'subir', 'detener']);
/** dónde empieza cada paso en la barra (el resto lo va llenando de a poco mientras dura) */
const DESDE: Record<string, number> = { revisar: 0.02, esperar: 0.05, subir: 0.08, detener: 0.1, copiar: 0.12, abrir: 0.8, cerrar: 0.93, listo: 1 };
/** el ícono y el color de cada tono de lo que se muestra antes de llevarlo: lo que se sube, lo que se queda, lo de allá */
const TONO: Record<'sube' | 'queda' | 'info' | 'aviso', [string, string]> = {
    sube: [I.subir, 'verde'], queda: [I.alerta, 'amarillo'], info: [I.traer, 'cian'], aviso: [I.alerta, 'amarillo'],
};
const GIRA = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏';
const ANCHO = 42;

/** El panel: lo que se ve, y cómo cambiarlo. `desde`: la máquina de donde viene (un hilo que se trae de otra). `o`: otro
 *  título arriba, y otros pasos (seguir aquí no copia ni cierra nada). */
function panel(hilo: string, maquina: string, desde = '', o: { arriba?: string; pasos?: [string, string][] } = {}) {
    const lista = o.pasos ?? PASOS;
    const c = el('dialog', 'mudanza');
    const arriba = el('div', 'arriba', o.arriba ?? (desde ? `trayendo «${hilo}» de ${desde} a` : `llevando «${hilo}» a`));
    const letras = el('pre', 'letras', grande(maquina).join('\n'));
    const barra = el('pre', 'barra');
    const pasos = el('div', 'pasos');
    const linea = el('div', 'linea');
    // lo que tiene sin subir, antes de llevarlo: solo si hay algo
    const pendiente = el('div', 'pendiente');
    pendiente.hidden = true;
    // sus botones: la banda de componentes/boton.ts, vacía mientras viaja
    const botones = el('div', 'ventana-pie botonera');
    botones.hidden = true;
    c.append(arriba, letras, barra, pasos, pendiente, linea, botones);
    document.body.appendChild(c);
    // las teclas de sus botones; ⎋ aprieta el de ⎋ (no llevarlo, cerrar), y mientras viaja no hace nada
    teclasDeBotones(c);
    c.addEventListener('cancel', e => { e.preventDefault(); botones.querySelector<HTMLElement>('[data-tecla="⎋"]')?.click(); });
    c.showModal();

    let valor = 0, meta = 0.02, paso = 'revisar', estado: 'va' | 'listo' | 'falla' | 'pregunta' = 'va', vuelta = 0;
    const vistos = new Set<string>();
    const pintar = () => {
        const llenas = Math.round(valor * ANCHO);
        barra.textContent = `[${'█'.repeat(llenas)}${'░'.repeat(ANCHO - llenas)}] ${String(Math.round(valor * 100)).padStart(3)}%`;
        barra.dataset.estado = estado;
        pasos.replaceChildren(...lista.filter(([k]) => !OPCIONALES.has(k) || vistos.has(k)).map(([clave, nombre]) => {
            const i = lista.findIndex(([k]) => k === clave), j = lista.findIndex(([k]) => k === paso);
            const hecho = estado === 'listo' || i < j, ahora = i === j && estado !== 'listo';
            const s = el('span', `paso${hecho ? ' hecho' : ahora ? ` ahora ${estado}` : ''}`);
            s.append(el('span', `i ico`, hecho ? I.hecha : ahora ? (estado === 'falla' ? I.cerrar : GIRA[vuelta % GIRA.length]) : I.vacio),
                el('span', '', nombre));
            return s;
        }));
    };
    // la barra avanza sola hacia donde va: dentro de un paso largo (copiar) se sigue moviendo, cada vez más lento,
    // sin llegar al paso siguiente; así nunca se queda quieta mientras algo pasa
    const reloj = setInterval(() => {
        vuelta++;
        if (estado === 'va') {
            const sig = lista[lista.findIndex(([k]) => k === paso) + 1]?.[0];
            const techo = sig ? DESDE[sig] - 0.01 : 1;
            meta = Math.max(meta, Math.min(techo, meta + (techo - meta) * 0.03));
        }
        valor += (meta - valor) * 0.25;
        pintar();
    }, 80);
    pintar();
    return {
        dialogo: c,
        paso(p: string, texto = '', parte?: number) {
            if (estado !== 'va' || !(p in DESDE)) return;
            paso = p; meta = Math.max(meta, DESDE[p]);
            vistos.add(p);
            // copiando: la barra avanza con lo que de verdad viajó
            const sig = lista[lista.findIndex(([k]) => k === p) + 1]?.[0];
            if (parte !== undefined && sig) meta = Math.max(meta, DESDE[p] + (DESDE[sig] - 0.01 - DESDE[p]) * parte);
            linea.textContent = texto;
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
            poner([{ ...cancelar('cerrar', null) }], [() => cerrar()]);
        },
        /** lo que allá llegaría a medias: llevar igual, o no */
        preguntar(texto: string): Promise<boolean> {
            estado = 'pregunta';
            linea.textContent = texto;
            // llevarlo igual no destruye nada (lo que falta sigue aquí): el foco parte en él, con ⏎; no llevarlo es cancelar
            return new Promise(si => {
                poner([{ texto: 'llevar igual', color: C.hecho, tecla: '⏎', ayuda: 'lo que falta allá sigue aquí' }, cancelar('no llevarlo', null)],
                    [() => { botones.replaceChildren(); botones.hidden = true; estado = 'va'; si(true); }, () => { cerrar(); si(false); }]);
            });
        },
        /** Una pregunta con lo que hay que saber antes (seguir aquí: de cuándo es la copia y cuánto falta), en una
         *  sección: `si` (⏎) o `no` (⎋). */
        confirmar(titulo: string, texto: string, si: string, no: string, ayuda = ''): Promise<boolean> {
            estado = 'pregunta';
            linea.textContent = '';
            pendiente.replaceChildren(seccion('aviso', titulo, [texto], 0));
            pendiente.hidden = false;
            return new Promise(r => {
                poner([{ texto: si, color: C.hecho, tecla: '⏎', ayuda }, cancelar(no, null)],
                    [() => { botones.replaceChildren(); botones.hidden = true; pendiente.hidden = true; estado = 'va'; r(true); },
                        () => { cerrar(); r(false); }]);
            });
        },
        /** Lo que tiene sin subir y lo que llegaría a medias (web/mudanza-texto.ts, `antes`), repositorio por repositorio:
         *  «subir y llevar» (si hay algo suyo que se pueda subir), «llevar igual» o no llevarlo. */
        elegir(a: Antes): Promise<'subir' | 'igual' | null> {
            estado = 'pregunta';
            linea.textContent = a.puedeSubir ? 'subir y llevar commitea solo lo de este hilo y lo sube; lo demás se queda aquí'
                : 'la conversación viaja; esto no: allá no va a estar';
            pendiente.replaceChildren(...a.grupos.map(g => {
                const d = el('div', 'repo');
                d.append(el('div', 'nombre', g.repo), ...g.secciones.map(s => seccion(s.tono, s.titulo, s.items, s.mas)));
                return d;
            }), ...a.avisos.map(x => seccion('aviso', x, [], 0)));
            pendiente.hidden = false;
            const seguir = (que: 'subir' | 'igual' | null, si: (x: 'subir' | 'igual' | null) => void) => () => {
                botones.replaceChildren(); botones.hidden = true; pendiente.hidden = true; estado = 'va'; si(que);
            };
            // subir es lo que se pidió tantas veces que no fuera necesario: va primero, con ⏎. Llevarlo igual no
            // destruye nada (lo que falta sigue aquí); no llevarlo es cancelar
            return new Promise(si => {
                const bs: Boton[] = [], hacer: (() => void)[] = [];
                if (a.puedeSubir) {
                    bs.push({ texto: 'subir y llevar', color: C.hecho, tecla: '⏎', ayuda: 'commitea y sube solo lo de este hilo' });
                    hacer.push(seguir('subir', si));
                }
                bs.push({ texto: 'llevar igual', color: a.puedeSubir ? C.cambiar : C.hecho, tecla: a.puedeSubir ? '⇧⏎' : '⏎',
                    ayuda: 'lo que falta allá sigue aquí' });
                hacer.push(seguir('igual', si));
                bs.push(cancelar('no llevarlo', null));
                hacer.push(() => { cerrar(); si(null); });
                poner(bs, hacer);
            });
        },
        cerrar,
    };
    /** Una sección de lo que se muestra antes de llevarlo: su ícono y su color, su título y su lista. */
    function seccion(tono: keyof typeof TONO, titulo: string, items: string[], mas: number): HTMLElement {
        const [icono, color] = TONO[tono];
        const s = el('div', 'seccion');
        s.dataset.tono = tono;
        s.style.setProperty('--tono', `var(--${color})`);
        const cabeza = el('div', 'titulo');
        cabeza.append(el('span', 'i ico', icono), el('span', '', titulo));
        s.append(cabeza);
        if (items.length) {
            const ul = el('ul');
            ul.append(...items.map(x => el('li', '', x)), ...(mas ? [el('li', 'mas', `y ${mas} más`)] : []));
            s.append(ul);
        }
        return s;
    }
    /** Los botones de la banda, cada uno con lo que hace; el foco, en el primero. */
    function poner(bs: Boton[], hacer: (() => void)[]): void {
        botones.innerHTML = bs.map(botonHtml).join('');
        botones.hidden = false;
        [...botones.querySelectorAll<HTMLButtonElement>('button')].forEach((b, i) => b.addEventListener('click', hacer[i]));
        botones.querySelector<HTMLButtonElement>('button')?.focus();
    }
    function cerrar(): void { clearInterval(reloj); if (c.open) c.close(); c.remove(); }
}

/** Llevar `hilo` a `maquina`, con su transición a la vista. `alLlegar` va a su terminal allá. Con `trae`, el hilo vive
 *  en esa otra máquina y se le pide que lo lleve a `maquina` (traerlo, aquí o a una tercera: `a`, vacío si es aquí): la
 *  mudanza corre allá, y su progreso se lee de allá. */
export async function llevar(hilo: string, maquina: string, alLlegar: () => Promise<void> | void,
    trae?: { desde: string; a: string }): Promise<void> {
    const p = panel(hilo, maquina, trae?.desde ?? '');
    const desde = Date.now() / 1000 - 1;
    const progreso = () => cli.mudanza(hilo, trae?.desde ?? '');
    const pedir = (si: boolean, subir: boolean) => trae ? cli.traer(hilo, trae.desde, si, trae.a, subir)
        : cli.llevar(hilo, maquina, si, subir);
    modelo.mudando.set(hilo, maquina);
    modelo.cambio.fire();
    let siguiendo = true;
    // lo que la mudanza va escribiendo (solo lo de esta vez: uno viejo se descarta por la hora)
    const seguir = (async () => {
        while (siguiendo) {
            const m = (await progreso()).datos;
            if (m?.paso && (m.hora ?? 0) >= desde) p.paso(m.paso, detalle(m, hilo, maquina), fraccion(m));
            await new Promise(r => setTimeout(r, 300));
        }
    })();
    try {
        let si = false, subir = false;
        for (;;) {
            let r = await pedir(si, subir);
            // lo que pide elegir (algo sin subir, o allá llegaría a medias): el detalle quedó en el progreso de la
            // mudanza, y se muestra entero en el panel; de un telar de antes, solo sus líneas
            if (r.error && /llevarla igual|sin subir/.test(r.error)) {
                const a = antes((await progreso()).datos ?? {}, maquina);
                if (a.hay) {
                    const que = await p.elegir(a);
                    if (!que) return;
                    [si, subir] = [que === 'igual', que === 'subir'];
                    continue;
                }
                const salida = String(r.cuerpo?.salida ?? r.error);
                const lista = salida.split('\n').filter(l => l.trim().startsWith('·')).map(l => l.trim()).join('\n');
                if (!(await p.preguntar(lista || r.error))) return;
                si = true;
                continue;
            }
            if (r.error) { p.falla(r.error); return; }
            // una conversación grande sigue viajando, o su agente termina su turno: se espera a que diga listo o falla
            if (r.datos?.en_curso) {
                const limite = Date.now() + 25 * 60_000;
                for (;;) {
                    const m = (await progreso()).datos;
                    if (m?.paso === 'falla' && (m.hora ?? 0) >= desde) { p.falla(m.error ?? 'no se llevó'); return; }
                    if (m?.paso === 'listo' && (m.hora ?? 0) >= desde) break;
                    if (Date.now() > limite) { p.falla('sigue viajando: aparece allá al terminar'); return; }
                    await new Promise(x => setTimeout(x, 700));
                }
                r = { datos: { ...r.datos, en_curso: false } };
            }
            const m = (await progreso()).datos;
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

/** Los pasos de seguir aquí: no se copia nada (la copia ya está aquí) ni se cierra nada allá (está apagada). */
const PASOS_SEGUIR: [string, string][] = [['revisar', 'mirar la copia de aquí'], ['abrir', 'tomarlo y abrirlo aquí'], ['listo', 'listo']];

/** Seguir aquí `hilo`, cuya máquina (`desde`) está apagada, desde la copia de su conversación que quedó aquí
 *  (telar.seguir): el panel dice de cuándo es la copia y cuánto falta (`GET /hilo/seguir`), y se elige seguirlo o no.
 *  Seguirlo lo toma y lo abre aquí (`POST /hilo/seguir`); `alLlegar` va a su terminal. Cuando `desde` vuelva, cede
 *  sola. Con `revision`, lo que ya se preguntó (el menú lo preguntó para ofrecerlo). */
export async function seguirAqui(hilo: string, desde: string, aqui: string, alLlegar: () => Promise<void> | void,
    revision?: cli.JsonSeguir): Promise<void> {
    const p = panel(hilo, aqui || 'aquí', '', { arriba: `siguiendo «${hilo}», con ${desde} apagada, en`, pasos: PASOS_SEGUIR });
    p.paso('revisar', `mirando la copia de aquí y lo último que se vio de ${desde}`);
    const r = revision ?? (await cli.seguirRevisar(hilo)).datos;
    if (!r) { p.falla('telar no contestó'); return; }
    if (!r.puede) { p.falla(r.por_que_no || 'no se puede seguir aquí'); return; }
    const si = await p.confirmar(`de cuándo es la copia de aquí, y lo que falta`, r.aviso, 'seguir aquí', 'no seguirlo',
        `lo toma y lo abre aquí; cuando ${desde} vuelva, cede sola`);
    if (!si) return;
    p.paso('abrir', `tomándolo y abriéndolo aquí, con la copia de aquí`);
    modelo.mudando.set(hilo, aqui);
    modelo.cambio.fire();
    try {
        const s = await cli.seguir(hilo);
        if (s.error || !s.datos?.ok) { p.falla(s.error ?? s.datos?.error ?? 'no se pudo'); return; }
        p.listo(s.datos.hecho ?? `«${hilo}» sigue aquí`);
        modelo.invalidar();
        await modelo.sondear();
        await new Promise(x => setTimeout(x, 1600));
        p.cerrar();
        await alLlegar();
    } finally {
        modelo.mudando.delete(hilo);
        modelo.cambio.fire();
    }
}

/** Lo que el ensayo de seguir aquí muestra: una copia de la mañana, y el laptop que pesaba más la última vez. */
const EJEMPLO_SEGUIR: cli.JsonSeguir = {
    puede: true, por_que_no: '', dueno: 'laptop', epoca: 6, conversacion: 'e3e3e3e3',
    aviso: 'Aquí está como quedó hoy 09:12 (61,2 MB). En laptop, la última vez que se lo vio (11:47), pesaba 63,8 MB, y '
        + 'creció por última vez 11:40: faltan unos 2,6 MB, y el agente no va a recordar lo de después. Cuando laptop '
        + 'vuelva, cede sola: lo que haya escrito allá después queda aparte, y se avisa.',
    aqui: { bytes: 61.2e6, fecha: '2026-11-24T09:12:00-03:00' },
    alla: { visto: '2026-11-24T11:47:00-03:00', en_linea: false, bytes: 63.8e6, crecio: '2026-11-24T11:40:00-03:00', en_la_foto: true },
};

/** Seguir aquí, sin tocar nada: el panel con su aviso (`window.telar.ensayoSeguir()`). Con `falla`, termina diciendo
 *  por qué no se abrió. */
export async function ensayoSeguir(aqui = 'telar', falla = false): Promise<void> {
    const p = panel('prueba', aqui, '', { arriba: '«prueba», con laptop apagada, se sigue en', pasos: PASOS_SEGUIR });
    const espera = (ms: number) => new Promise(r => setTimeout(r, ms));
    p.paso('revisar', 'mirando la copia de aquí y lo último que se vio de laptop'); await espera(900);
    const si = await p.confirmar('de cuándo es la copia de aquí, y lo que falta', EJEMPLO_SEGUIR.aviso, 'seguir aquí',
        'no seguirlo', 'lo toma y lo abre aquí; cuando laptop vuelva, cede sola');
    if (!si) return;
    p.paso('abrir', 'tomándolo y abriéndolo aquí, con la copia de aquí'); await espera(1400);
    if (falla) { p.falla('no lo tomé: el registro cambió (¿volvió laptop, o otra lo tomó antes?). Aquí no se abrió nada'); return; }
    p.listo('«prueba» sigue aquí desde la copia de hoy 09:12 (61,2 MB); cuando laptop vuelva, cede sola');
    await espera(2500);
    p.cerrar();
}

/** Lo que el ensayo muestra antes de llevarlo: dos archivos suyos sin commitear, uno de su carpeta que no se sabe de quién
 *  es, un commit sin subir, y la máquina de allá atrás. */
const EJEMPLO = {
    pendiente: { repos: [{ nombre: 'proyectos/faro', relativa: 'proyectos/faro', rama: 'main', commit: 'a1b2c3d4e5',
        del_hilo: ['docs/plan.md', 'src/mapa.ts'], n_del_hilo: 2, en_su_carpeta: ['salida/mapa.png'], n_en_su_carpeta: 1,
        commits: ['9f8e7d6 el mapa, con sus capas'], n_commits: 1, puede_subir: true, por_que_no: '', pendiente: true }] },
    destino: [{ relativa: 'proyectos/faro', existe: true, tiene: false }],
    avisos: ['sus hijos con rama (Calendario) se quedan aquí, con su rama y su worktree: se lleva solo a «Faro», y fusionarlos se hace desde aquí'],
};

/** La transición sin mudar nada, con tiempos inventados: para mirarla y afinarla (`window.telar.ensayoMudanza()`). Con
 *  `falla`, termina en una falla; con `'pregunta'`, se queda en lo que allá llegaría a medias (llevar igual, o no); con
 *  `'subir'`, en lo que tiene sin subir (`EJEMPLO`), y si se elige subir, pasa por ese paso. */
export async function ensayo(maquina = 'telar', falla: boolean | 'pregunta' | 'subir' = false): Promise<void> {
    const p = panel('prueba', maquina);
    const espera = (ms: number) => new Promise(r => setTimeout(r, ms));
    const paso = (m: Parameters<typeof detalle>[0]) => p.paso(m.paso ?? '', detalle(m, 'prueba', maquina), fraccion(m));
    paso({ paso: 'revisar' }); await espera(900);
    if (falla === 'pregunta') {
        const si = await p.preguntar('· personal/proyectos/telar: 3 commits sin subir\n· personal/proyectos/telar: 2 archivos sin commitear');
        if (!si) return;
    }
    let subio = false;
    if (falla === 'subir') {
        const que = await p.elegir(antes(EJEMPLO, maquina));
        if (!que) return;
        subio = que === 'subir';
    }
    paso({ paso: 'esperar' }); await espera(1600);
    if (subio) { paso({ paso: 'subir' }); await espera(1400); paso({ paso: 'subir', subido: 'proyectos/faro: 2 archivos commiteados (a1b2c3d) y subido' }); await espera(900); }
    paso({ paso: 'detener' }); await espera(700);
    // de vuelta a donde ya estuvo: allá había casi todo, y viaja solo lo que falta
    for (let i = 0; i <= 10; i++) { paso({ paso: 'copiar', total: 65e6, por_mandar: 1.2e6, mandados: i * 1.2e5 }); await espera(280); }
    paso({ paso: 'abrir' }); await espera(1400);
    if (falla) { p.falla(`${maquina} recibió la conversación pero no abrió el hilo: no pude abrir el hilo: claude no está en el PATH. Aquí sigue como estaba.`); return; }
    paso({ paso: 'cerrar' }); await espera(700);
    p.listo(`llegó a ${maquina}: sigue ahí, con su conversación`);
    await espera(2500);
    p.cerrar();
}
