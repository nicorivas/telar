// La vista «hilos»: lo que hay abierto, con semáforo, prioridad y tiempo del día.
//
// Es la lista de proyectos de la barra, pero se llama como la llama telar: un hilo es una
// unidad de trabajo viva, y qué cuenta como proyecto lo declara el perfil del repositorio,
// no esta página.
//
//   ● ●   faro                 49m   ← inicio: prioridad · atención · dónde vive; el nombre; fin: hace cuánto
//   ◐     molino                7m
//       ▸ archivo 6                  ← un submenú de HILOS, plegado: los archivados también son hilos
//
// Un solo buscador y una sola fila de herramientas, los de HILOS: lo escrito filtra los vivos y también los archivados. Si
// algún archivado calza, ARCHIVO se muestra abierto con solo esos (y su número); al borrarlo, vuelve a como lo dejó la
// persona.
//
// Cada fila es un ítem (componentes/item.ts): las ranuras de íconos al inicio, el texto y, al final, la meta, los
// avisos y las acciones. Los botones de la fila (⋯, archivar, descartar) flotan sobre el borde derecho al pasar el
// mouse y no ocupan lugar, porque si lo ocuparan correrían la columna del tiempo según cuántos hay. El id del
// multiplexor no se muestra: para elegir un hilo basta la prioridad y el nombre.
//
// Se dibuja directo en la columna izquierda de la página (`#barra`), y solo cambia la lista, no lo que la
// rodea: así no se pierde el scroll ni lo escrito en un buscador cada vez que cambia el tiempo de hoy. Lo propio de
// la barra (el buscador, los separadores, plegarla), en media/css/hilos.css; las filas, en item.css. /componentes la
// muestra con hilos de mentira, en cada tema.

import { I } from '../web/iconos';
import * as S from '../componentes/senales';
import * as A from '../componentes/acciones';
import { item, type Accion, type Pieza, type Tono } from '../componentes/item';
import { type OpcionOrden } from '../componentes/orden';
import { herramientas as herramientasLista, separador } from '../componentes/seccion';
import * as entidades from '../web/entidades';
import * as ui from '../web/ui';
import * as cli from '../cli';
import { GLIFO, NOMBRE_ATENCION, PRIORIDAD, duracion, esc, hace, haceCorto, normalizar } from '../estilo';
import * as modos from '../web/modos';
import * as mundo from '../web/mundo';
import * as glifos from '../web/glifos';
import { modelo } from '../modelo';
import { HIJO, anidar, repartir } from './hilos-familia';
import { ayudaInalcanzable, fueraDe, type MaquinaAlcance } from '../web/alcance';

/** Una pestaña del dashboard (su lista y su orden los decide el dashboard, vistas/dashboard/panel.ts): una fila del grupo
 *  DASHBOARD. */
export interface PestanaDashboard { clave: string; accion: string; valor: string; nombre: string; tecla: string;
    /** algo nuevo en ella («3 chats sin leer», el `aviso` de un bloque): un punto al final de su fila */
    aviso?: string;
    /** cuántas cosas suyas te esperan («te esperan»: lo que pregunta): un número tras su nombre, si no es cero */
    cuenta?: number; cuentaAyuda?: string }

/** Un hilo de otra máquina, como viene en su foto (`telar.espejo`). */
export interface HiloDeFoto {
    nombre: string; atencion?: string; vivo?: boolean; relativa?: string; prioridad?: number | null; resumen?: string; etiquetas?: string[]; padre?: string;
    /** si duerme allá (telar.dormir): su agente se cerró por estar quieto; abrirlo lo despierta */
    dormido?: boolean;
    /** si terminó y la persona no lo ha visto, y desde cuándo está así: lo dice su máquina (un telar viejo no lo manda) */
    sin_ver?: boolean; atencion_desde?: string | null;
    /** su mundo, derivado aquí con los `[mundos]` de esta máquina (`GET /espejos`); sin `[mundos]`, no viene */
    mundo?: string;
    /** el agente residente del que es, si lo dice su foto (un telar de antes no lo manda) */
    agente?: string;
}

type Seccion = 'hilo' | 'archivado';
/** Cómo se ordena un grupo: "" como lo da telar (el orden de ⌘⇧P «ordenar»), o uno de estos. */
type Orden = '' | 'urgencia' | 'nombre' | 'reciente';
// en el grupo de ordenar (la gramática visual: un grupo dentro de la banda de herramientas), tras su ícono padre: cada
// una un ícono en su celda cuadrada (ninguna palabra, que ocuparía otro ancho; ningún círculo, que dice un estado)
const ORDENES: (OpcionOrden & { clave: Orden })[] = [
    { clave: 'urgencia', icono: I.urgencia, ayuda: 'urgencia: prioridad alta primero; a igual prioridad, el que te espera y después el más reciente' },
    { clave: 'nombre', icono: I.alfabetico, ayuda: 'nombre, alfabético' },
    { clave: 'reciente', icono: I.reloj, ayuda: 'última modificación: el último prompt a su agente, lo más reciente arriba' },
];

function leerBuscado(): Record<string, string> {
    try {
        const g = JSON.parse(localStorage.getItem('telar.barra.buscado') ?? '{}') ?? {};
        // el archivo tuvo su propio buscador: lo que quedó escrito ahí ya no filtra nada
        delete g.archivo;
        return g;
    } catch { return {}; }
}

/** Si una fila tiene lo buscado (`q`, ya normalizado), sin tildes ni mayúsculas. */
const calza = (q: string, busca: string): boolean => !q || normalizar(busca).includes(q);

/** El estado que dibuja el glifo de un hilo: su atención, con «terminó» partido en sin ver y ya visto. */
const estadoDe = (atencion: string, visto: boolean): glifos.Estado =>
    atencion === 'termino' ? (visto ? 'visto' : 'termino') : atencion === 'trabajando' || atencion === 'espera' ? atencion : 'ninguna';
/** Lo que dice la ayuda de un hilo dormido: desde cuándo (la hora de `desde`, ISO local) y dónde, y que abrirlo lo
 *  despierta. */
export function ayudaDormido(sinVer: boolean, desde = '', maquina = ''): string {
    const hora = /T(\d\d:\d\d)/.exec(desde)?.[1];
    return `${sinVer ? 'terminó y no lo has visto · ' : ''}duerme${maquina ? ` en ${maquina}` : ''}${hora ? ` desde las ${hora}` : ''}: `
        + 'su agente se cerró por estar quieto; abrirlo o escribirle lo despierta';
}

/** La última modificación de un hilo: cuándo se le pidió algo a su agente. Si telar todavía no lo
 *  anotó (un hilo de antes), lo último que hizo su agente. Mirarlo (`visto`) nunca cuenta: un clic
 *  no es trabajo. */
const ultimaDe = (h: cli.JsonHilo): string => h.actividad || h.atencion_desde || '';

/** Lo que el orden mira de un hilo, sea de la lista de esta máquina o de la foto de otra. */
interface Ordenable { prioridad?: number | null; atencion?: string; nombre: string; ultima: string }

/** Ordenar `l` según `orden`, mirando cada uno por `ver`. Con «urgencia», la prioridad manda sobre todo lo demás
 *  (esté vivo o no, sea de esta máquina o de otra); a igual prioridad, el que te espera y después el más reciente. */
function ordenarPor<T>(l: T[], orden: Orden, ver: (x: T) => Ordenable): T[] {
    if (!orden) return l;
    const reciente = (a: Ordenable, b: Ordenable) => b.ultima.localeCompare(a.ultima);
    const cmp: Record<Exclude<Orden, ''>, (a: Ordenable, b: Ordenable) => number> = {
        urgencia: (a, b) => ((a.prioridad || 9) - (b.prioridad || 9))
            || (Number(b.atencion === 'espera') - Number(a.atencion === 'espera')) || reciente(a, b),
        nombre: (a, b) => a.nombre.localeCompare(b.nombre, 'es', { sensitivity: 'base' }),
        reciente,
    };
    return l.map(x => [x, ver(x)] as const).sort((a, b) => cmp[orden](a[1], b[1])).map(([x]) => x);
}

const deLista = (h: cli.JsonHilo): Ordenable =>
    ({ prioridad: h.prioridad, atencion: h.atencion, nombre: cli.nombreVisible(h), ultima: ultimaDe(h) });

function ordenar(l: cli.JsonHilo[], orden: Orden): cli.JsonHilo[] {
    return ordenarPor(l, orden, deLista);
}

/** Donde se guarda lo que se recuerda entre sesiones (la página: el localStorage del navegador). */
export interface Guardado {
    get<T>(clave: string): T | undefined;
    update(clave: string, valor: unknown): PromiseLike<void>;
}

/** La barra de hilos: arma la lista y responde a sus clics. */
export class BarraHilos {
    /** donde se dibuja la lista (dentro de `#barra`); hasta `montar`, nada */
    private lista?: HTMLElement;
    /** lo escrito en cada buscador: sobrevive a los redibujos (llegan varios por minuto) y a recargar */
    private buscado: Record<string, string> = leerBuscado();
    /** plegada: una franja angosta con «›» y «hilos» en vertical; un clic la abre (en el celular no se pliega). Lo
     *  dice el modo puesto (web/modos.ts); plegarla a mano es un cambio en él */
    private get plegada(): boolean { return modos.valor('barra') === 'plegada'; }
    private ultimoHtml = '';
    private ultimoActivo?: string;
    /** el dashboard tiene el foco: su fila va marcada, y no la del último hilo (que no es lo que se mira) */
    dashboardActivo = false;
    /** la app que el dashboard muestra (si está al frente): ninguna fila del dashboard se marca (la app está en el menú
     *  de la cabecera, no en la barra) */
    appActiva = '';
    /** las pestañas del dashboard, que pone la página (del dashboard), y la que se ve: su fila se marca */
    pestanasDashboard: () => PestanaDashboard[] = () => [];
    pestanaActiva = '';
    /** el hilo cuya terminal se muestra a la derecha. Si se da, manda sobre el foco de tmux para marcar
     *  la fila; si no, la marca el hilo con foco */
    mostrado?: string;
    /** los hilos de otras máquinas que esta no ve en su multiplexor, de la foto que publica cada una
     *  (`telar espejo ver`): van en HILOS, con su máquina en la columna de dónde vive. Lo pone la página web */
    otras: (MaquinaAlcance & { hilos: HiloDeFoto[] })[] = [];
    /** el nombre de esta máquina (la que sirve la página): con la columna ancha, lo muestran sus hilos */
    aqui = '';
    /** la columna de dónde vive cada hilo: ⇄ (o nada, si vive aquí), o el nombre de la máquina */
    private conMaquina(): boolean { return !!this.estado?.get<boolean>('telar.hilos.maquina'); }
    /** el ancho de esa columna con los nombres: el del nombre más largo, hasta 12 */
    private anchoMaquina = 1;
    /** los hilos vivos en otra máquina, por nombre → la máquina (una fila [remotos] o de su foto): lo que se llevó
     *  allá no se repite aquí en el ARCHIVO (uno abierto en las dos lo dice la franja de avisos: web/vigia.ts) */
    private enOtra = new Map<string, string>();
    private irAlArchivo = false;
    /** ARCHIVO mientras se busca: abierto (lo que calza) salvo que la persona lo pliegue ahí mismo. No se recuerda: al
     *  borrar lo escrito, vuelve a como lo dejó (`archivoAbierto`) */
    private archivoBuscando?: boolean;
    /** cuántos archivados calzan con lo escrito en el último dibujo (sin nada escrito, -1) */
    private archivoCalza = -1;
    /** lo escrito en el buscador de HILOS, listo para comparar */
    private buscando(): string { return normalizar((this.buscado.hilos ?? '').trim()); }
    /** dónde guardar el orden elegido de cada grupo */
    estado?: Guardado;
    private ordenDe(grupo: string): Orden { return (this.estado?.get<string>(`telar.orden.${grupo}`) ?? '') as Orden; }
    /** las cabeceras que la persona dejó al revés de como empiezan: clave → abierta. Se guardan en `estado` (en la página,
     *  este navegador, también el del teléfono): al recargar, cada una sigue como la dejó */
    private cabeceras?: Record<string, boolean>;
    /** cómo empieza cada cabecera que ya se dibujó: para dar vuelta una que la persona no ha tocado */
    private porDefecto = new Map<string, boolean>();
    private recordadas(): Record<string, boolean> {
        if (!this.cabeceras) {
            const g = this.estado?.get<Record<string, boolean>>('telar.cabeceras');
            this.cabeceras = g && typeof g === 'object' ? { ...g } : {};
        }
        return this.cabeceras;
    }

    /** El archivo es un submenú de HILOS (`__archivo`); `archivoAbierto` lo deja ver y cambiar desde afuera. */
    get archivoAbierto(): boolean { return this.abierta('__archivo', false); }
    set archivoAbierto(v: boolean) { if (v !== this.archivoAbierto) this.alternar('__archivo'); }

    private abierta(clave: string, porDefecto: boolean): boolean {
        this.porDefecto.set(clave, porDefecto);
        const r = this.recordadas()[clave];
        return typeof r === 'boolean' ? r : porDefecto;
    }
    /** Abrirla o plegarla, y recordarlo. Si vuelve a como empieza, se olvida: si cambia cómo empieza, la sigue. */
    private alternar(clave: string): void {
        const porDefecto = this.porDefecto.get(clave) ?? true;
        const r = this.recordadas(), abierta = !this.abierta(clave, porDefecto);
        if (abierta === porDefecto) delete r[clave]; else r[clave] = abierta;
        void this.estado?.update('telar.cabeceras', r);
    }

    /** La barra ya tiene dónde dibujarse: `raiz` es la columna izquierda de la página. Los clics y lo que
     *  se escribe en los buscadores se atienden ahí, sobre la lista que se redibuja. */
    montar(raiz: HTMLElement): void {
        const lista = document.createElement('div');
        lista.id = 'lista';
        raiz.replaceChildren(lista);
        this.lista = lista;
        this.ultimoHtml = '';
        lista.addEventListener('input', e => {
            const inp = e.target as HTMLInputElement;
            if (!inp.classList.contains('buscar')) return;
            this.buscar(inp.dataset.grupo ?? '', inp.value);
        });
        lista.addEventListener('keydown', e => {
            const inp = e.target as HTMLInputElement;
            if (!inp.classList?.contains('buscar')) return;
            if (e.key === 'Escape') { inp.value = ''; this.buscar(inp.dataset.grupo ?? '', ''); }
            // ⏎: al primero que se ve
            if (e.key === 'Enter') {
                const f = lista.querySelector<HTMLElement>(`.item[data-grupo="${inp.dataset.grupo}"]:not([hidden])`);
                if (f?.dataset.hilo) this.mensaje({ tipo: 'ir', hilo: f.dataset.hilo });
                else if (f?.dataset.accion) this.mensaje({ tipo: f.dataset.accion, id: f.dataset.id });
            }
        });
        lista.addEventListener('click', e => {
            const f = (e.target as HTMLElement).closest<HTMLElement>('[data-hilo],[data-accion]');
            if (!f) return;
            if (f.dataset.accion) this.mensaje({ tipo: f.dataset.accion, id: f.dataset.id, donde: entidades.dondeDe(e, f) });
            else this.mensaje({ tipo: 'ir', hilo: f.dataset.hilo });
        });
        // el clic derecho abre el menú del hilo (⋯)
        // arrastrar un hilo sobre otro lo cuelga de él (`telar hilo padre`); sobre la cabecera de HILOS, lo suelta.
        // Se arrastran los de esta máquina; el destino puede ser de cualquiera
        let arrastrado = '';
        const destinoDe = (t: EventTarget | null): { el: HTMLElement; padre: string } | null => {
            const el = (t as HTMLElement | null)?.closest<HTMLElement>('.item[data-hilo], .item.remota, .item.cabecera[data-id="__hilos"]');
            if (!el) return null;
            const padre = el.dataset.hilo ?? (el.classList.contains('cabecera') ? '' : (el.dataset.id ?? '').split('|').slice(1).join('|'));
            return padre === arrastrado ? null : { el, padre };
        };
        lista.addEventListener('dragstart', e => {
            const f = (e.target as HTMLElement).closest<HTMLElement>('.item[data-hilo]');
            if (!f?.dataset.hilo || !e.dataTransfer) return;
            arrastrado = f.dataset.hilo;
            e.dataTransfer.setData('text/plain', arrastrado);
            e.dataTransfer.effectAllowed = 'move';
            f.classList.add('arrastrando');
        });
        lista.addEventListener('dragend', () => {
            arrastrado = '';
            for (const x of lista.querySelectorAll('.arrastrando, .destino')) x.classList.remove('arrastrando', 'destino');
        });
        lista.addEventListener('dragover', e => {
            if (!arrastrado) return;
            const d = destinoDe(e.target);
            for (const x of lista.querySelectorAll('.destino')) if (x !== d?.el) x.classList.remove('destino');
            if (!d) return;
            e.preventDefault();
            if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';
            d.el.classList.add('destino');
        });
        lista.addEventListener('drop', e => {
            const d = destinoDe(e.target);
            const hijo = arrastrado;
            if (!d || !hijo) return;
            e.preventDefault();
            void ui.orden('telar.colgar', hijo, d.padre);
        });
        lista.addEventListener('contextmenu', e => {
            const f = (e.target as HTMLElement).closest<HTMLElement>('[data-hilo]');
            if (!f) return;
            e.preventDefault();
            this.mensaje({ tipo: 'menu', id: f.dataset.hilo, donde: entidades.dondeDe(e) });
        });
        modos.alCambiar(() => this.refrescar(true));
        this.refrescar(true);
    }

    /** Lo escrito en un buscador. En el de HILOS también decide qué archivados se ven: si eso cambia, la lista se
     *  redibuja (sin mover el scroll ni perder el cursor); si no, basta esconder filas. */
    buscar(grupo: string, texto: string): void {
        this.buscado[grupo] = texto;
        if (!this.buscando()) this.archivoBuscando = undefined;
        try { localStorage.setItem('telar.barra.buscado', JSON.stringify(this.buscado)); } catch { /* sin almacén */ }
        const antes = this.ultimoHtml;
        this.refrescar();
        if (this.ultimoHtml === antes) this.filtrar();
    }

    /** Esconde las filas de cada grupo que no tienen lo buscado (sin tildes ni mayúsculas). */
    private filtrar(): void {
        const lista = this.lista;
        if (!lista) return;
        for (const inp of lista.querySelectorAll<HTMLInputElement>('input.buscar')) {
            const g = inp.dataset.grupo ?? '', q = normalizar(inp.value.trim());
            let n = 0;
            for (const f of lista.querySelectorAll<HTMLElement>(`.item[data-grupo="${g}"]`)) {
                const ok = calza(q, f.dataset.busca ?? '');
                f.hidden = !ok;
                if (ok) n++;
            }
            const v = lista.querySelector<HTMLElement>(`.vacia[data-grupo="${g}"]`);
            if (v) v.hidden = !(q && !n);
        }
    }

    /** La lista nueva, sin perder lo escrito en un buscador (ni dónde estaba el cursor). `mostrar`: la fila
     *  que tiene que quedar a la vista (la marcada, o el archivo recién abierto). */
    private pintarLista(html: string, mostrar?: string): void {
        const lista = this.lista;
        if (!lista) return;
        const a = document.activeElement as HTMLInputElement | null;
        const foco = a && lista.contains(a) && a.classList.contains('buscar')
            ? { g: a.dataset.grupo, i: a.selectionStart, j: a.selectionEnd } : undefined;
        lista.innerHTML = html;
        // los glifos de los hilos, si el modo los pone (web/glifos): se pintan sobre sus lienzos ya puestos
        glifos.pintarEn(lista);
        for (const inp of lista.querySelectorAll<HTMLInputElement>('input.buscar')) inp.value = this.buscado[inp.dataset.grupo ?? ''] ?? '';
        if (foco) {
            const inp = lista.querySelector<HTMLInputElement>(`input.buscar[data-grupo="${foco.g}"]`);
            if (inp) { inp.focus(); inp.setSelectionRange(foco.i, foco.j); }
        }
        this.filtrar();
        if (mostrar) { const el = lista.querySelector<HTMLElement>(mostrar); if (el && !el.hidden) el.scrollIntoView({ block: 'nearest' }); }
    }

    mensaje(m: { tipo: string; hilo?: string; id?: string; donde?: { x: number; y: number } }): void {
        switch (m.tipo) {
            case 'ir': {
                if (!m.hilo) break;
                // uno archivado o cerrado no tiene tab: pincharlo lo muestra (su conversación, con «retomar»), sin
                // abrir el agente todavía
                const sinTab = modelo.hilos.some(x => x.nombre === m.hilo && (!x.vivo || x.archivado));
                void ui.orden(sinTab ? 'telar.ver' : 'telar.ir', { hilo: m.hilo });
                break;
            }
            case 'archivar': if (m.id) void ui.orden('telar.archivar', { hilo: m.id }); break;
            case 'retomar': if (m.id) void ui.orden('telar.retomar', { hilo: m.id }); break;
            case 'cerrar': if (m.id) void ui.orden('telar.cerrar', { hilo: m.id }); break;
            case 'descartar': if (m.id) void ui.orden('telar.descartar', { hilo: m.id }); break;
            case 'archivo': void ui.orden('telar.archivo'); break;
            case 'menu': if (m.id) void entidades.menuDe(`hilo:${m.id}`, m.donde); break;
            // la clave de la sección de un agente ya es su dirección (`agente:secretaria`)
            case 'menu-agente': if (m.id) void entidades.menuDe(m.id.startsWith('agente:') ? m.id : `agente:${m.id}`, m.donde); break;
            case 'ir-remoto': if (m.id) void ui.orden('telar.irRemoto', m.id); break;
            case 'menu-remoto': if (m.id) void ui.orden('telar.menuRemoto', m.id); break;
            case 'abrir-barra': this.plegar(false); break;
            case 'seccion':
                if (m.id === '__archivo') { void ui.orden('telar.archivo'); break; }
                if (m.id) { this.alternar(m.id); this.refrescar(true); }
                break;
            case 'equipo': void ui.orden('telar.equipoVer', m.id); break;
            case 'colega': if (m.id) void ui.orden('telar.escribirColega', m.id); break;
            case 'home': if (m.id) void ui.orden('telar.seccion', m.id); break;
            case 'abrir-agente': if (m.id) {
                // uno de otra máquina (su carpeta todavía no llega a esta), allá
                const s = modelo.secciones.find(x => x.clave === m.id);
                void ui.orden('telar.agenteAbrir', { clave: m.id, nombre: s?.nombre ?? m.id, ...(s?.maquina ? { maquina: s.maquina } : {}) });
            } break;
            case 'app': if (m.id) void ui.orden('telar.app', m.id); break;
            case 'ver-maquina':
                void this.estado?.update('telar.hilos.maquina', !this.conMaquina()).then(() => this.refrescar(true));
                break;
            case 'orden-grupo': if (m.id) {
                const [grupo, orden] = m.id.split(':');
                void this.estado?.update(`telar.orden.${grupo}`, orden === this.ordenDe(grupo) ? '' : orden).then(() => this.refrescar(true));
            } break;
            case 'cmd': if (m.id?.startsWith('telar.')) void ui.orden(m.id); break;
            // una fila del grupo DASHBOARD: ir a esa pestaña
            case 'dash': if (m.id) { const [accion, valor] = JSON.parse(m.id) as string[]; void ui.orden('telar.pestana', accion, valor); } break;
        }
    }

    alternarArchivo(): void {
        // buscando, con archivados que calzan: se pliega o se abre solo mientras dure lo escrito
        if (this.buscando() && this.archivoCalza > 0) {
            this.archivoBuscando = !(this.archivoBuscando ?? true);
            this.irAlArchivo = this.archivoBuscando;
            this.refrescar(true);
            return;
        }
        this.archivoAbierto = !this.archivoAbierto;
        // está dentro de HILOS: para verlo, HILOS abierta
        if (this.archivoAbierto && !this.abierta('__hilos', true)) this.alternar('__hilos');
        this.irAlArchivo = this.archivoAbierto;
        this.refrescar(true);
    }

    /** Plegarla o abrirla, y recordarlo. La terminal que se ve se mide de nuevo sola (su ResizeObserver). */
    private plegar(si: boolean): void {
        modos.poner('barra', si ? 'plegada' : 'abierta');   // avisa, y alCambiar la redibuja
    }

    refrescar(forzar = false): void {
        if (!this.lista) return;
        const html = this.plegada
            ? '<div class="plegada" data-accion="abrir-barra" title="mostrar la barra de hilos">'
                + '<span class="pliegue-barra">›</span><span class="vertical">hilos</span></div>'
            : this.html();
        const activo = this.dashboardActivo ? '\u0000dashboard' : this.mostrado ?? modelo.activo?.nombre;
        const seMovio = activo !== this.ultimoActivo;
        if (!forzar && !seMovio && html === this.ultimoHtml) return;
        this.ultimoActivo = activo; this.ultimoHtml = html;
        const mostrar = this.irAlArchivo ? '#archivo' : seMovio || forzar ? '.activa' : undefined;
        this.irAlArchivo = false;
        this.pintarLista(html, mostrar);
    }

    /** La ranura de la prioridad (componentes/senales.ts): chica, alta llena, media a medias, baja un aro; sin ella, un punto. */
    private ranuraPrioridad(p: number | null | undefined, archivado = false): Pieza {
        return S.prioridad(p, archivado);
    }

    /** La ranura de la atención de uno dormido (telar.dormir): un aro tenue, o su diana tenue si terminó y no lo has
     *  visto. O su glifo, tenue, si el modo los pone en la barra. */
    private ranuraDormido(nombre: string, at: string, sinVer: boolean, ayuda: string): Pieza {
        if (!glifos.enLaBarra()) return S.dormido(sinVer, ayuda);
        return { html: glifos.htmlHilo(nombre, estadoDe(at, !sinVer)), tono: 'tenue', ayuda };
    }

    /** La ranura de la atención mientras el hilo se va (se cierra, se archiva): un círculo que se vacía. */
    private ranuraSale(texto: string): Pieza {
        return S.sale(`${texto}…`);
    }

    /** La ranura de la atención (componentes/senales.ts): trabajando lleno, te espera un aro, terminó con algo adentro (ya
     *  visto, tenue); sin atención, vacía. O el glifo del hilo, si el modo los pone en la barra. */
    private ranuraAtencion(nombre: string, at: string, visto: boolean, ayuda: string): Pieza | null {
        if (!glifos.enLaBarra()) return S.atencion(at, visto, ayuda);
        const tono = visto ? 'tenue' : ({ trabajando: 'trabajando', espera: 'espera', termino: 'termino' } as Record<string, Tono>)[at];
        return { html: glifos.htmlHilo(nombre, estadoDe(at, visto)), tono, ayuda };
    }

    /** La fila de un hilo de otra máquina, de su foto: un clic va a su terminal allá. `hondo`: cuántos niveles cuelga
     *  (bajo su agente o su padre), con «↳»; `visible`, el nombre que se muestra si no es el suyo. */
    private filaRemota(m: (typeof this.otras)[number], x: HiloDeFoto, hondo = 0, visible = ''): string {
        const at = x.atencion ?? 'ninguna';
        // terminó y ya se vio: lo dice su máquina; o se vio aquí recién (lo local), o es el que la página muestra
        const visto = at === 'termino' && (x.sin_ver === false || x.nombre === this.mostrado || modelo.vistoAqui(x.nombre, x.atencion_desde));
        const saliendo = modelo.saliendo.get(x.nombre);
        // fuera de línea (telar.alcance): inalcanzable, ni vivo ni dormido; lo que dijo antes de irse va en la ayuda
        const estadoM = m.fuera ? `\n${ayudaInalcanzable(m, x)}`
            : m.en_linea ? '' : `\n${m.nombre} está apagado${m.edad !== null ? ` hace ${haceCorto(new Date(Date.now() - m.edad * 1000).toISOString())}` : ''}`;
        const id = `${m.nombre}|${x.nombre}`;
        return item({
            clases: ['remota'], apagada: !m.en_linea, saliendo: !!saliendo, hondo,
            accion: 'ir-remoto', id,
            datos: { grupo: 'hilos', busca: `${x.nombre} ${x.relativa ?? ''} ${m.nombre}` },
            ayuda: `${m.nombre}:${x.nombre}${x.relativa ? `\n${x.relativa}` : ''}${x.resumen ? `\n${x.resumen}` : ''}${estadoM}`,
            // un hijo no dice su prioridad: hereda la de su padre (la ranura queda, vacía)
            inicio: [hondo ? null : this.ranuraPrioridad(x.prioridad),
                saliendo ? this.ranuraSale(saliendo.texto)
                    : m.fuera ? S.inalcanzable(ayudaInalcanzable(m, x))
                    : x.dormido && x.vivo ? this.ranuraDormido(x.nombre, at, at === 'termino' && !visto, ayudaDormido(at === 'termino' && !visto, '', m.nombre))
                    : this.ranuraAtencion(x.nombre, at, visto, NOMBRE_ATENCION[at] ?? ''),
                this.columnaMaquina(m.nombre, `vive en ${m.nombre}`)],
            prefijo: hondo ? [{ icono: I.hijo }] : [],
            titulo: visible || x.nombre,
            meta: saliendo ? { texto: saliendo.texto } : undefined,
            // ⋯: lo que se hace con un hilo de otra máquina desde aquí (traerlo a esta)
            menu: { accion: 'menu-remoto', id, icono: I.menu, ayuda: 'más: traerlo a esta máquina' },
        });
    }

    /** La fila de un hilo de esta máquina (o de un [remotos] que la lista ya trae). `grupo`: el buscador que la filtra
     *  («hilos», «archivo»), si alguno; `hondo` y `visible`, como en filaRemota; `acciones`, las suyas al pasar el mouse,
     *  antes de las de todo hilo (la casa de un agente); `agente`: es el hilo de siempre de un agente residente (su
     *  nombre en otro color). */
    private fila(h: cli.JsonHilo, o: { seccion?: Seccion; grupo?: string; hondo?: number; visible?: string; acciones?: Accion[]; agente?: boolean } = {}): string {
        const seccion = o.seccion ?? 'hilo', hondo = o.hondo ?? 0;
        // el que la página muestra ahora está a la vista: lo que terminó ahí ya se ve
        const visto = h.atencion === 'termino' && (!h.sin_ver || h.nombre === this.mostrado);
        const marcada = this.mostrado !== undefined ? h.nombre === this.mostrado : h.activo;
        const archivado = !h.vivo || seccion === 'archivado';
        // lo que está en curso lo dice un círculo que se mueve en su ranura (componentes/circulo.ts), y la meta, quieta:
        // cerrándose o archivándose, se vacía donde va la atención; viajando a otra máquina, gira donde va el lugar
        const saliendo = modelo.saliendo.get(h.nombre);
        const sale = saliendo?.texto ?? modelo.ocupados.get(h.nombre)?.replace(/…$/, '');
        const viaja = modelo.mudando.get(h.nombre);
        // dónde vive: el satélite si es en otra máquina y esta ventana solo lo mira (con la columna ancha, su nombre)
        const lugar: Pieza | null = viaja !== undefined ? S.viaja(`viajando a ${viaja}…`)
            : this.columnaMaquina(h.remoto === '?' ? '?' : h.remoto ?? '',
                h.remoto ? (h.remoto === '?' ? 'conectado a otra máquina' : `vive en ${h.remoto}`) : '');
        // antes del nombre: de qué agente es, o quién lo abrió (salvo que ya cuelgue de él con su «↳»: no se repite)
        const prefijo: Pieza[] = [];
        if (h.icono) prefijo.push({ texto: h.icono, tono: 'agente', ayuda: `de agente:${h.agente}` });
        else if (h.abierto_por && !(hondo && !h.abierto_por.icono)) {
            const quien = h.abierto_por.agente ? `agente:${h.abierto_por.agente} (desde «${h.abierto_por.por}»)` : `«${h.abierto_por.por}»`;
            prefijo.push({ ...(h.abierto_por.icono ? { texto: h.abierto_por.icono } : { icono: I.hijo }), tono: 'tenue', ayuda: `lo abrió ${quien}` });
        }
        // un hijo en su propia rama: la rama en vez del «↳» (también dice que cuelga), y aunque su padre no esté a la vista
        if (h.rama) prefijo.push({ icono: I.rama, tono: 'tenue', ayuda: `en su rama ${h.rama.rama}, que sale de ${h.rama.base}: la fusiona su padre` });
        else if (hondo) prefijo.push({ icono: I.hijo });
        // al pasar el mouse, dos maneras de sacarlo de la lista: archivar lo guarda (en ARCHIVO, con su conversación, para
        // retomarlo después); descartar lo termina y lo saca (la conversación queda en disco, sin botón para volver). Sin
        // tab que cerrar, lo único que cabe es volver a abrirlo. Antes, las de quien la pone (la casa de un agente), que no
        // dependen de cómo está el hilo
        const acciones: Accion[] = [...o.acciones ?? [], ...modelo.ocupados.has(h.nombre) || saliendo ? [] : archivado
            ? [{ accion: 'retomar', id: h.nombre, icono: I.retomar, ayuda: 'retomar: abre el agente con su conversación' },
                { accion: 'descartar', id: h.nombre, icono: I.descartar, peligro: true, ayuda: 'descartar: sale del archivo (pregunta antes; su conversación queda en disco)' }]
            : [{ accion: 'archivar', id: h.nombre, icono: I.archivar, ayuda: 'archivar: lo cierra y lo guarda en ARCHIVO, con su conversación, para retomarlo después' },
                { accion: 'cerrar', id: h.nombre, icono: I.descartar, peligro: true, ayuda: 'descartar: lo termina y lo saca de la lista, sin guardarlo en ARCHIVO (pregunta antes; para guardarlo, archivar)' }]];
        return item({
            variante: o.agente ? 'agente' : 'normal',
            activa: marcada && !this.dashboardActivo, apagada: archivado, saliendo: !!saliendo, hondo,
            datos: { hilo: h.nombre, ...(o.grupo ? { grupo: o.grupo, busca: this.buscaDe(h) } : {}) },
            arrastrable: true,
            ayuda: this.tooltip(h),
            // al principio, todos los íconos, cada uno en su ranura aunque esté vacía: así los nombres empiezan siempre
            // en el mismo lugar. Prioridad · semáforo · dónde vive. Un hijo no dice su prioridad: hereda la de su padre
            inicio: [hondo ? null : this.ranuraPrioridad(h.prioridad, seccion === 'archivado'),
                sale !== undefined ? this.ranuraSale(sale)
                    : h.alcanzable === false && h.vivo ? S.inalcanzable(this.ayudaFuera(h))
                    : h.dormido && h.vivo ? this.ranuraDormido(h.nombre, h.atencion, !!h.sin_ver && !visto,
                        ayudaDormido(!!h.sin_ver && !visto, h.dormido.desde, h.remoto && h.remoto !== '?' ? h.remoto : ''))
                    : this.ranuraAtencion(h.nombre, h.atencion, visto, visto ? 'terminó (ya lo viste)' : h.sin_ver ? 'terminó y no lo has visto: ⌥S' : NOMBRE_ATENCION[h.atencion] ?? ''),
                lugar],
            prefijo,
            titulo: o.visible || cli.nombreVisible(h),
            sufijo: h.publico ? [S.publico('público: lo ven las otras personas del bus (EQUIPO); ⋯ para hacerlo privado')] : [],
            // al final, solo su última modificación: el último prompt a su agente (un clic no cuenta)
            meta: sale !== undefined ? { texto: sale } : viaja !== undefined ? { texto: `→ ${viaja}`, ayuda: `viajando a ${viaja}…` } : { texto: haceCorto(ultimaDe(h)) },
            // ⋯ el menú del hilo (ordenes.ts): renombrar, vincular, prioridad, llevar…
            menu: { accion: 'menu', id: h.nombre, icono: I.menu, ayuda: 'más: renombrar, vincular, prioridad, llevar…' },
            acciones,
        });
    }

    /** En qué busca el buscador de un hilo de esta máquina: su nombre, su carpeta y dónde vive. */
    private buscaDe(h: cli.JsonHilo): string {
        return `${cli.nombreVisible(h)} ${h.nombre} ${h.relativa ?? ''} ${h.remoto || this.aqui}`;
    }

    /** La ranura de dónde vive un hilo: `maquina` vacía es esta. Angosta, el satélite para los de otra máquina (vacía si
     *  es de aquí); ancha (el botón de las máquinas junto a buscar), el nombre de la máquina de cada uno, también el de esta. */
    private columnaMaquina(maquina: string, titulo: string): Pieza | null {
        if (!this.conMaquina()) return maquina ? S.remoto(titulo) : null;
        const nombre = maquina === '?' ? '?' : maquina || this.aqui || '·';
        return { texto: nombre, ancho: this.anchoMaquina, tono: maquina ? 'atencion' : 'tenue',
            ayuda: titulo || `vive aquí${this.aqui ? ` (${this.aqui})` : ''}` };
    }

    /** Bajo la cabecera de HILOS: el buscador (filtra los vivos y los archivados) y los órdenes (valen para los dos).
     *  Un clic en el orden que ya rige vuelve al de telar. Además, ⇄: ver la máquina de cada uno. ARCHIVO no tiene los
     *  suyos: dos buscadores en la misma sección confundían. */
    private herramientas(orden_: Orden): string {
        const maquina = `<span class="ord i${this.conMaquina() ? ' si' : ''}" data-accion="ver-maquina" title="${this.conMaquina() ? 'ver solo una marca en los hilos de otra máquina' : 'ver en qué máquina vive cada hilo'}">${I.maquinas}</span>`;
        // la banda de herramientas: la barra del buscador (con su línea abajo, de borde a borde) y a su derecha el grupo de
        // ordenar (su ícono padre y las opciones, entre dos cortes en su púrpura: orden.ts) y las máquinas
        return herramientasLista({ grupo: 'hilos', placeholder: 'hilos',
            ayuda: 'buscar por nombre, carpeta o máquina, también en el archivo · ⏎ abre el primero · ⎋ borra',
            orden: { opciones: ORDENES, activa: orden_ }, extra: maquina });
    }

    /** La ayuda de la ventana de aquí de un hilo cuya máquina está fuera de línea (telar.alcance): con su foto si la
     *  hay; si no, con lo que dice la lista. */
    private ayudaFuera(h: cli.JsonHilo): string {
        const desde = h.fuera_de_linea_desde ? Date.parse(h.fuera_de_linea_desde) : NaN;
        const m: MaquinaAlcance = fueraDe(h.remoto ?? '', this.otras)
            ?? { nombre: h.remoto ?? '', en_linea: false, fuera: true, edad: Number.isNaN(desde) ? null : (Date.now() - desde) / 1000 };
        return ayudaInalcanzable(m, { vivo: h.vivo, dormido: h.dormido, atencion: h.atencion });
    }

    private tooltip(h: cli.JsonHilo): string {
        const visible = cli.nombreVisible(h);
        const l: string[] = [...(visible !== h.nombre ? [visible] : []),
            `${h.nombre}${h.id !== h.nombre ? ` · ${h.id}` : ''} · ${h.relativa || 'sin carpeta'}`];
        const datos: string[] = [];
        if (h.arquetipo) datos.push(h.arquetipo);
        if (h.remoto) datos.push(h.remoto === '?' ? 'en otra máquina' : `vive en ${h.remoto}`);
        if (!h.vivo) datos.push('no vivo');
        else if (h.alcanzable === false) datos.push(this.ayudaFuera(h).replace(/\n/g, ' '));
        else if (h.dormido) datos.push(ayudaDormido(false, h.dormido.desde, h.remoto && h.remoto !== '?' ? h.remoto : ''));
        if (h.publico) datos.push('público');
        if (h.abierto_por) datos.push(`lo abrió ${h.abierto_por.agente ? `agente:${h.abierto_por.agente}` : `«${h.abierto_por.por}»`}`);
        if (h.rama) datos.push(`rama ${h.rama.rama} (desde ${h.rama.base})`);
        if (GLIFO[h.atencion] && h.alcanzable !== false) datos.push(`${GLIFO[h.atencion]} ${NOMBRE_ATENCION[h.atencion] ?? h.atencion}`);
        if (h.prioridad) datos.push(`prioridad ${PRIORIDAD[h.prioridad]} ${['', 'alta', 'media', 'baja'][h.prioridad]}`);
        if (h.tiempo >= 60) datos.push(`hoy ${duracion(h.tiempo)}`);
        if (h.actividad) datos.push(`último prompt hace ${hace(h.actividad)}`);
        if (h.visto) datos.push(`último foco hace ${hace(h.visto)}`);
        if (datos.length) l.push(datos.join(' · '));
        const f = h.ficha;
        if (f?.estado) l.push('', `› ${f.estado}`);
        else if (f?.nota) l.push('', f.nota);
        for (const p of (f?.pendientes ?? []).slice(0, 6)) l.push(`${p.en_curso ? '▣' : p.hecho ? '✓' : '☐'} ${p.texto}`);
        return l.join('\n');
    }

    private html(): string {
        // sin API, la lista sigue (es lo último que se supo); la caída, la sesión y el multiplexor los dice la franja de
        // avisos, arriba (web/vigia.ts). Sin ninguna lista leída todavía, nada que mostrar
        if (!modelo.leido && !modelo.hilos.length) return `<div class="nota">${modelo.caido() ? 'todavía sin la lista de hilos' : 'leyendo los hilos…'}</div>`;
        const h: string[] = [];
        // «cerrando…» dura hasta que el hilo ya no se ve (aquí ni en la foto de su máquina), o se vence
        for (const [n, x] of modelo.saliendo) {
            const sigue = modelo.enLista.some(y => y.nombre === n) || this.otras.some(m => m.hilos.some(y => y.vivo && y.nombre === n));
            if (!sigue || Date.now() > x.hasta) modelo.saliendo.delete(n);
        }
        this.enOtra = new Map([
            ...this.otras.flatMap(m => m.hilos.filter(x => x.vivo).map(x => [x.nombre, m.nombre] as [string, string])),
            ...modelo.hilos.filter(x => x.remoto && x.remoto !== '?' && x.vivo).map(x => [x.nombre, x.remoto!] as [string, string]),
        ]);
        if (!modelo.viva && !modelo.hilos.length) return '<div class="nota">sin hilos</div>';
        if (!modelo.hilos.length) {
            return h.join('') + '<div class="aviso">ningún hilo todavía.<br><br>'
                + '<a data-accion="cmd" data-id="telar.nuevo">abrir uno</a></div>';
        }
        // grupos con cabecera plegable, en este orden: DASHBOARD, AGENTES, HILOS (con ARCHIVO adentro, al final: un
        // submenú), las secciones propias y EQUIPO. Los tres primeros empiezan abiertos (es donde se trabaja); los
        // demás y ARCHIVO, cerrados (se miran de vez en cuando). Dentro de cada grupo, los que tienen tab primero
        const vivosPrimero = (l: cli.JsonHilo[]) => [...l.filter(x => x.vivo), ...l.filter(x => !x.vivo)];
        // `extra`: lo que va al final de la cabecera, con su propia acción (el + de HILOS)
        let primera = true;
        // las acciones de una sección, en su cabecera y en este orden: las suyas, y el «+» de crear uno, al final (en la
        // misma columna en todas las cabeceras: componentes/acciones.ts). El ‹ que pliega la barra entera es de la barra
        // y no de una sección: va en su primera fila, la franja de avisos (web/franja.ts)
        const cabecera = (clave: string, titulo: string, cuenta: number, porDefecto: boolean, ayuda: string, fijas: Accion[] = [], nuevo?: Accion): boolean => {
            const abierta = this.abierta(clave, porDefecto);
            if (!primera) h.push(separador());
            fijas = [...fijas, ...(nuevo ? [nuevo] : [])];
            primera = false;
            // el título va como se escribe («hilos», el nombre de una sección): las mayúsculas las pone el tema
            h.push(item({ variante: 'cabecera', ancla: clave === '__archivo' ? 'archivo' : undefined, accion: 'seccion', id: clave,
                ayuda: `${ayuda}: abrir o cerrar`, inicio: [{ icono: abierta ? I.abierto : I.plegado }],
                titulo, sufijo: cuenta ? [{ texto: String(cuenta), tono: 'tenue' }] : [], fijas }));
            return abierta;
        };
        // un submenú: una sección dentro de otra (ARCHIVO dentro de HILOS), con su cabecera plegable. Es una fila más de
        // la lista (componentes/item.ts, variante «submenu»): la flecha en la ranura de dónde vive, justo antes de los
        // nombres (con la columna de las máquinas, tan ancha como ella), y su nombre en la columna de los nombres
        // `forzada`: abierto o plegado por otra cosa que lo recordado (ARCHIVO mientras se busca)
        const submenu = (clave: string, titulo: string, cuenta: number, porDefecto: boolean, ayuda: string, forzada?: boolean): boolean => {
            const abierta = forzada ?? this.abierta(clave, porDefecto);
            const flecha: Pieza = { icono: abierta ? I.abierto : I.plegado, ...this.conMaquina() ? { ancho: this.anchoMaquina } : {} };
            h.push(item({ variante: 'submenu', ancla: clave === '__archivo' ? 'archivo' : undefined, accion: 'seccion', id: clave,
                ayuda: `${ayuda}: abrir o cerrar`, inicio: [null, null, flecha],
                titulo, sufijo: cuenta ? [{ texto: String(cuenta), tono: 'tenue' }] : [] }));
            return abierta;
        };

        // el dashboard: una fila por pestaña (ahora, tareas, el correo…), en el orden de `[dashboard]`. Es el lugar
        // al que se vuelve varias veces al día: encabeza la lista. Algo nuevo en una (el `aviso` de un bloque: chats sin
        // leer) es un punto al final; la tecla que la abre, a la derecha
        if (cabecera('__dashboard', 'dashboard', 0, true, 'el día: agenda, tareas, correo y lo que traigan los proveedores')) {
            for (const p of this.pestanasDashboard()) {
                h.push(item({ variante: 'enlace', activa: this.dashboardActivo && !this.appActiva && p.clave === this.pestanaActiva,
                    accion: 'dash', id: JSON.stringify([p.accion, p.valor]),
                    ayuda: p.tecla ? `${p.nombre} · con el dashboard a la vista, la tecla ${p.tecla}` : p.nombre,
                    inicio: [null], titulo: p.nombre,
                    sufijo: p.cuenta ? [{ texto: String(p.cuenta), tono: 'atencion', ayuda: p.cuentaAyuda }] : [],
                    aviso: p.aviso ? S.nuevo(p.aviso) : undefined,
                    meta: p.tecla ? { texto: p.tecla } : undefined }));
            }
        }

        // los agentes residentes: uno por línea (su hilo de siempre, el de su nombre). Su casa (bitácora, memoria,
        // archivos) es una acción de las que aparecen al pasar el mouse, y en el teléfono está en su ⋯. Un agente sin hilo
        // abierto sale igual, tenue, y su línea abre su hilo. Sus otros hilos van en HILOS, con su ícono
        const agentes = modelo.secciones.filter(s => s.grupo === 'agentes');
        const verTodos: Accion = { accion: 'cmd', id: 'telar.agentesVer', icono: I.lista, ayuda: 'todos los agentes: su estado, sus encargos, encargar y rotar' };
        const crear = A.nuevo({ accion: 'cmd', id: 'telar.agenteNuevo' }, 'agente nuevo: un agente residente, su carpeta con CLAUDE.md y agente.toml');
        // los que el modo puesto no muestra (`agentes`, ⚙ modos) no se esconden sin decirlo: la cabecera dice cuántos se
        // ven, y si no se ve ninguno, una fila lo dice y lleva a elegirlos
        const delModo = agentes.filter(a => modos.seVeAgente(a.clave)).length;
        // quién se ve y dónde (vistas/hilos-familia.ts): el modo puesto puede filtrar por etiquetas (web/modos.ts; un hijo
        // sin etiquetas propias lleva las de su padre, y así hacia arriba) y el mundo puesto (web/mundo.ts) deja ver lo
        // suyo y lo sin clasificar. El hilo que se está mirando no se esconde, ni su familia: sus padres, para que quede
        // anidado, y sus descendientes, que suben con él (y salen de «de personal»). En todos los modos, también en todo
        // (`mundo.enElPuesto`): la barra está siempre a la vista, y una pantalla compartida en el trabajo no muestra
        // lo personal; en todo, lo de otro mundo va al final, plegado (ahí el mundo ordena)
        const padreDeNombre = new Map<string, string>([
            ...modelo.hilos.map(y => [y.nombre, y.padre || ''] as [string, string]),
            ...this.otras.flatMap(m => m.hilos.map(y => [y.nombre, y.padre || ''] as [string, string]))]);
        const etiquetasDe = new Map<string, string[]>([...modelo.hilos.map(y => [y.nombre, y.etiquetas ?? []] as [string, string[]]),
            ...this.otras.flatMap(m => m.hilos.map(y => [y.nombre, y.etiquetas ?? []] as [string, string[]]))]);
        const reparto = repartir({ mostrado: this.mostrado, padres: padreDeNombre, etiquetas: etiquetasDe,
            agentes: agentes.map(a => a.nombre), modo: modos.seVe, mundo: mundo.enElPuesto });
        const familia = reparto.familia;
        const elModo = delModo < agentes.length ? ` · «${modos.puesto().nombre}» muestra ${delModo} de ${agentes.length} (⚙ modos)` : '';
        // la sección sale aunque no haya ninguno: es donde se aprende que existen y se arma el primero
        if (cabecera('__agentes', 'agentes', 0, true, `los agentes residentes${elModo}`, [verTodos], crear)) {
            if (!agentes.length) {
                h.push(item({ variante: 'agente', apagada: true, accion: 'cmd', id: 'telar.agenteNuevo', inicio: [null],
                    ayuda: 'un agente vive en su carpeta, con su memoria y su bitácora, y le encargas cosas',
                    tituloHtml: 'no tienes agentes residentes · <a>crear uno</a>' }));
            }
            let mostrados = 0;
            for (const a of agentes) {
                // uno de otra máquina cuya carpeta todavía no llega a esta (`maquina`, por la foto de allá): sin casa aquí
                const casas: Accion[] = a.maquina ? [] : [{ accion: 'home', id: a.clave, icono: I.casa, ayuda: `la casa de ${a.nombre}: bitácora, memoria, archivos` }];
                const suyos = vivosPrimero(modelo.enLista.filter(x => x.nombre === a.nombre));
                // y su hilo, si no viene en la lista de aquí, de la foto de su máquina
                const suyoAlla = a.maquina && !suyos.length
                    ? this.otras.find(m => m.nombre === a.maquina)?.hilos.find(y => y.vivo && y.nombre === a.nombre) : undefined;
                // un agente cuyo hilo es de otro mundo no se ve; uno sin hilo, tampoco si es de otro mundo por su
                // agente.toml, su carpeta o la etiqueta de su hilo (`mundo.seVeAgente`, lo que dicen las grillas de
                // ⚙ modos y ⚙ mundos; sin saberlo, se ve). Salvo que se esté mirando su hilo o el de un hijo suyo: el mostrado no se esconde, y sus
                // hijos se dibujan colgados de él
                const deOtroMundo = !mundo.seVeAgente(a, suyoAlla ? [suyoAlla.mundo ?? a.mundo] : suyos.map(x => x.mundo), mundo.enElPuesto);
                if (deOtroMundo && !familia.has(a.nombre)) continue;
                // ni uno que el modo puesto no muestra (`agentes`, la grilla de ⚙ modos), salvo lo mismo (en el dashboard,
                // donde está la grilla, no: lo que se marca se ve al tiro)
                const mirado = !this.dashboardActivo && familia.has(a.nombre);
                if (!mirado && !modos.seVeAgente(a.clave)) continue;
                mostrados++;
                if (suyoAlla) h.push(this.filaRemota(this.otras.find(m => m.nombre === a.maquina)!, suyoAlla, 0));
                else if (!suyos.length) {
                    // sin hilo vivo: si telar recuerda uno (cerrado o archivado), la línea lo retoma; si nunca existió, lo
                    // abre (con su motor; si falta, se ofrece elegirlo)
                    const previo = modelo.hilos.find(x => cli.enSeccion(a, x.nombre));
                    const abrir: Accion = previo
                        ? { accion: 'retomar', id: previo.nombre, icono: I.retomar, ayuda: 'retomar: reabre el hilo con su conversación' }
                        : { accion: 'abrir-agente', id: a.clave, icono: I.correr, ayuda: 'abrir su hilo' };
                    // quieta, el ▷ que lo abre; al pasar el mouse, su casa y el ▷ otra vez (las de a mano flotan sobre el
                    // final y lo tapan); su ⋯, el menú del agente (web/ordenes.ts): su casa, abrir su hilo, encargarle, eliminarlo
                    const alla = a.maquina ? ` en ${a.maquina} (su carpeta todavía no llega a esta máquina: telar doctor)` : '';
                    h.push(item({ variante: 'agente', apagada: true, accion: abrir.accion, id: abrir.id,
                        ayuda: `${a.nombre}: sin hilo abierto; pincha para ${previo ? 'retomarlo' : 'abrirlo'}${alla}`,
                        inicio: [null, null, null], titulo: a.nombre, fijas: [abrir], acciones: [...casas, abrir],
                        menu: { accion: 'menu-agente', id: a.clave, icono: I.menu, ayuda: 'más: su casa, abrir su hilo, encargarle, eliminarlo' } }));
                } else suyos.forEach((x, i) => h.push(this.fila(x, { agente: true, acciones: i === 0 ? casas : [] })));
                // sus hijos: un hilo por tarea que se le llevó («Secretaría › T454 …», telar.hijos), de esta máquina o de
                // la suya, colgados de él y con el nombre sin el suyo adelante
                const prefijo = `${a.nombre}${HIJO}`;
                for (const x of vivosPrimero(modelo.enLista.filter(y => y.nombre.startsWith(prefijo)))) {
                    h.push(this.fila(x, { grupo: 'hilos', hondo: 1, visible: x.nombre.slice(prefijo.length) }));
                }
                const vistos = new Set(modelo.enLista.map(y => y.nombre));
                for (const m of this.otras) {
                    for (const x of m.hilos.filter(y => y.vivo && y.nombre.startsWith(prefijo) && !vistos.has(y.nombre))) {
                        h.push(this.filaRemota(m, x, 1, x.nombre.slice(prefijo.length)));
                    }
                }
            }
            if (agentes.length && !delModo && !mostrados) {
                h.push(item({ variante: 'agente', apagada: true, accion: 'dash', id: JSON.stringify(['config', 'modos']), inicio: [null],
                    ayuda: 'qué agentes se ven en cada modo: ⚙ modos',
                    tituloHtml: `ninguno en «${esc(modos.puesto().nombre)}» · <a>elegir</a>` }));
            }
        }

        // los hilos abiertos que no reclama nadie: los de esta máquina y, después, los de las otras (de su foto,
        // solo los vivos; un hilo que la lista ya trae, uno de [remotos], no se repite). Cada uno dice dónde vive
        const ordenH = this.ordenDe('hilos');
        // (los de un agente que no son su hilo de siempre también van aquí, con su ícono: son trabajo como cualquiera)
        const deAgente = (y: cli.JsonHilo) => { const s = modelo.seccionDe(y.nombre); return !s || (s.grupo === 'agentes' && s.nombre !== y.nombre); };
        // los hijos de un agente van colgados de él, arriba: aquí no se repiten
        // (y el hilo de un agente de otra máquina sin carpeta aquí, que va en AGENTES desde la foto de allá)
        const esHijo = (n: string) => agentes.some(a => n.startsWith(`${a.nombre}${HIJO}`) || (a.maquina && n === a.nombre));
        // lo que el modo y el mundo puestos dejan ver (`reparto`, arriba). Lo que el mundo deja afuera no se esconde sin
        // decirlo: va contado en una fila plegada al final de HILOS («de personal 7»), que lo abre ahí mismo
        const seVe = (n: string, et?: string[], mu?: string) => reparto.donde(n, et, mu) === 'lista';
        const fuera = (n: string, et?: string[], mu?: string) => reparto.donde(n, et, mu) === 'fuera';
        const sueltos = vivosPrimero(modelo.enLista.filter(deAgente).filter(y => !esHijo(y.nombre) && seVe(y.nombre, y.etiquetas, y.mundo)));
        const yaEstan = new Set(modelo.hilos.filter(x => x.remoto).map(x => `${x.remoto}|${x.nombre}`));
        const deOtras = this.otras.flatMap(m => m.hilos.filter(x => x.vivo && !esHijo(x.nombre) && !yaEstan.has(`${m.nombre}|${x.nombre}`)
            && seVe(x.nombre, x.etiquetas, x.mundo)).map(x => ({ m, x })));
        // los de esta máquina y los de las otras, en una sola lista: el orden elegido vale para todos (en la página
        // del servidor, los del laptop vienen de su foto, y antes quedaban al final sin ordenar)
        type FilaH = { aqui: cli.JsonHilo } | { m: (typeof deOtras)[number]['m']; x: HiloDeFoto };
        const ordenarH = (l: FilaH[]) => ordenarPor<FilaH>(l, ordenH, f => 'aqui' in f ? deLista(f.aqui)
            : { prioridad: f.x.prioridad, atencion: f.x.atencion, nombre: f.x.nombre, ultima: '' });
        const todos = ordenarH([...sueltos.map(aqui => ({ aqui })), ...deOtras]);
        const fueraDelMundo = ordenarH([
            ...vivosPrimero(modelo.enLista.filter(deAgente).filter(y => !esHijo(y.nombre) && fuera(y.nombre, y.etiquetas, y.mundo)))
                .map(aqui => ({ aqui })),
            ...this.otras.flatMap(m => m.hilos.filter(x => x.vivo && !esHijo(x.nombre) && !yaEstan.has(`${m.nombre}|${x.nombre}`)
                && fuera(x.nombre, x.etiquetas, x.mundo)).map(x => ({ m, x }))),
        ]);
        const nombres = [this.aqui, ...this.otras.map(m => m.nombre), ...sueltos.map(x => x.remoto ?? '')];
        this.anchoMaquina = Math.min(12, Math.max(1, ...nombres.map(n => n.length)));
        // + abre un hilo nuevo (ordenes.ts: pide el nombre y la máquina)
        const nuevo = A.nuevo({ accion: 'cmd', id: 'telar.nuevo' }, 'hilo nuevo: un tab con su agente');
        const filtrando = modos.filtro().length ? ` · el modo «${modos.puesto().nombre}» muestra solo los de ${modos.filtro().join(', ')}` : '';
        this.archivoCalza = -1;
        if (cabecera('__hilos', 'hilos', sueltos.length + deOtras.length, true, `los hilos abiertos, de esta máquina y de las otras${filtrando}`, [], nuevo)) {
            h.push(this.herramientas(ordenH));
            // los hijos (los que abrió otro hilo de la lista: `abierto_por`) van justo bajo su padre, sangrados, en el
            // orden elegido entre ellos; el orden manda solo entre los de arriba (vistas/hilos-familia.ts, `anidar`). Del
            // que cuelga: el que se le puso (`telar hilo padre`, o arrastrándolo) o el que lo abrió; de aquí o de otra
            // máquina. Igual en HILOS que en «de personal», abajo
            const nombreDe = (f: FilaH) => 'aqui' in f ? f.aqui.nombre : f.x.nombre;
            const visibleDe = (f: FilaH) => 'aqui' in f ? cli.nombreVisible(f.aqui) : f.x.nombre;
            const poner = (filas: FilaH[]) => {
                for (const { fila: f, hondo, padre } of anidar(filas, nombreDe, f => 'aqui' in f ? f.aqui.padre : f.x.padre)) {
                    // un hijo lleva «↳» delante, como los hijos de un agente. Uno que trabaja en la carpeta de su padre se
                    // llamaría igual que él (el título de esa carpeta: «telar» bajo «telar»): va con su propio nombre
                    const propio = padre && visibleDe(f) === visibleDe(padre) ? nombreDe(f) : '';
                    h.push('aqui' in f ? this.fila(f.aqui, { grupo: 'hilos', hondo, visible: propio || undefined })
                        : this.filaRemota(f.m, f.x, hondo, propio));
                }
            };
            poner(todos);

            // ARCHIVO, al final de HILOS: un submenú, porque los archivados también son hilos. Empieza plegado; sus filas
            // van en la grilla de las de arriba, con el orden de HILOS. No tiene buscador propio: lo escrito arriba lo
            // filtra también, y mientras haya algo escrito se ve abierto con solo lo que calza (y esa cuenta); si nada
            // calza, no sale. Lo que se llevó a otra máquina y vive allá no se repite aquí: su fila es la de allá
            const q = this.buscando();
            const archivados = ordenar(modelo.archivados.filter(x => (x.remoto || !this.enOtra.has(x.nombre)) && seVe(x.nombre, x.etiquetas, x.mundo)
                && calza(q, this.buscaDe(x))), ordenH);
            this.archivoCalza = q ? archivados.length : -1;
            const ayudaA = q ? 'los hilos archivados que calzan con lo buscado' : 'los hilos archivados';
            if (archivados.length && submenu('__archivo', 'archivo', archivados.length, false, ayudaA, q ? this.archivoBuscando ?? true : undefined)) {
                for (const x of archivados) h.push(this.fila(x, { seccion: 'archivado', grupo: 'hilos' }));
            }

            // lo que el mundo puesto deja afuera, al final: «de personal 7» (con un solo mundo más, su nombre en su color),
            // plegado; abierto, sus hilos aquí mismo, sin cambiar el mundo, y cada hijo bajo su padre, como arriba
            if (fueraDelMundo.length) {
                const otros = mundo.declarados().filter(m => m.clave !== mundo.puesto().mundo);
                const nombre = otros.length === 1 ? `de ${otros[0].nombre}` : 'de otros mundos';
                if (submenu('__otros_mundos', nombre, fueraDelMundo.length, false, 'los hilos que el mundo puesto deja afuera')) poner(fueraDelMundo);
            }
        }

        // las secciones propias (`[secciones]`): un grupo de hilos cada una, como HILOS
        for (const s of modelo.secciones.filter(x => x.grupo !== 'agentes')) {
            const suyos = vivosPrimero(modelo.enLista.filter(x => cli.enSeccion(s, x.nombre) && seVe(x.nombre, x.etiquetas)));
            if (!cabecera(s.clave, s.nombre, suyos.length, true, `la sección ${s.nombre}`)) continue;
            if (s.home) h.push(item({ variante: 'enlace', accion: 'home', id: s.clave, ayuda: `la página de ${s.nombre}`, inicio: [null], titulo: 'home' }));
            for (const x of suyos) h.push(this.fila(x));
        }

        // lo que el equipo le pide a la persona; pinchar una fila abre sus acciones
        if (modelo.equipoRemoto) {
            const pend = modelo.sugerencias;
            if (cabecera('__equipo', 'pedidos', pend.length, false, 'lo que el equipo te pide en su página')) {
                if (!pend.length) h.push(item({ apagada: true, inicio: [null], titulo: 'nada esperando' }));
                for (const x of pend) {
                    const pedido = x.tipo === 'tarea';
                    const meta = x.revisando ? 'Gestión' : (x.similares?.length ? '¿ya existe?' : '');
                    h.push(item({ accion: 'equipo', id: x.id, ayuda: `${x.persona}: ${x.titulo}${x.motivo ? `\n«${x.motivo}»` : ''}\nclic: acciones`,
                        inicio: [{ icono: I.pedido }], titulo: `${x.persona} · ${pedido ? x.titulo : `${x.tarea}: subir`}`,
                        meta: meta ? { texto: meta } : undefined }));
                }
            }
        }

        // las otras personas del bus, todas las que se conectan (aunque no tengan hilos públicos), con los hilos que
        // publican: de solo lectura; pinchar uno es escribirle
        const colegas = modelo.colegas;
        if (colegas.length && cabecera('__colegas', 'equipo', colegas.length, false,
            'las otras personas del bus y sus hilos públicos (no su conversación); clic en uno para escribirle')) {
            for (const p of colegas) {
                for (const m of p.maquinas) {
                    h.push(item({ apagada: !m.al_dia,
                        ayuda: `${p.persona} en ${m.maquina} · publicado ${m.publicado.slice(0, 16).replace('T', ' ')}${m.al_dia ? '' : ' · hace rato: puede estar desconectado'}`,
                        inicio: [S.presente(m.al_dia)],
                        titulo: p.persona, sufijo: [{ texto: `· ${m.maquina}${m.al_dia ? '' : ' · sin noticias'}`, tono: 'tenue' }] }));
                    if (!m.hilos.length) h.push(item({ apagada: true, hondo: 1, inicio: [null], titulo: 'sin hilos públicos' }));
                    for (const x of m.hilos) {
                        h.push(item({ accion: 'colega', id: JSON.stringify([p.persona, x.ext, x.nombre]), apagada: !x.vivo,
                            ayuda: [x.resumen, x.carpeta, `${p.persona}+${x.ext}`, 'clic: escribirle'].filter(Boolean).join('\n'),
                            inicio: [S.presente(x.vivo)], titulo: x.nombre }));
                    }
                }
            }
        }

        // las apps (`[apps]`: juegos, visores) no van aquí, que es la barra del trabajo: están en el menú de su ícono, en
        // la cabecera (navegador/app.ts)
        return h.join('');
    }
}
