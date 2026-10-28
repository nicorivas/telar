// Una página de bloques —la que trae una sección o una app (`telar seccion`, `telar app`), o la ficha de una tarea
// (`telar tarea`)— en HTML: texto, ítems, lienzos y marcos. La dibujan las pantallas que la muestran; los lienzos
// guardan su memoria por aquí.

import * as cli from '../../cli';
import * as ui from '../../web/ui';
import { disco } from '../../disco';
import { esc, llaveAlAzar } from '../../estilo';

/** El markdown que cabe en una página de sección: párrafos, **negrita**, `código` y listas
 *  con «- ». Nada más: la página la escribe un comando ajeno, y lo que no se entiende se
 *  muestra como texto, nunca como HTML. */
export function mdSimple(texto: string): string {
    const linea = (t: string) => esc(t)
        .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
        .replace(/(^|[\s(])\*([^*\s][^*]*?)\*(?=[\s.,;:)!?]|$)/g, '$1<i>$2</i>')
        .replace(/`([^`]+)`/g, '<code>$1</code>');
    const esItem = (l: string) => /^\s*[-*] /.test(l);
    return texto.trim().split(/\n\s*\n/).map(parrafo => {
        // un párrafo puede abrir con una frase y seguir con una lista: cada tramo es lo suyo
        const salida: string[] = [];
        let texto: string[] = [], items: string[] = [];
        const cerrar = () => {
            if (texto.length) salida.push(`<p>${texto.map(linea).join(' ')}</p>`);
            if (items.length) salida.push('<ul>' + items.map(l => `<li>${linea(l.replace(/^\s*[-*] /, ''))}</li>`).join('') + '</ul>');
            texto = []; items = [];
        };
        for (const l of parrafo.split('\n')) {
            if (esItem(l)) { if (texto.length) cerrar(); items.push(l); }
            else if (items.length && /^\s+\S/.test(l)) items[items.length - 1] += ' ' + l.trim();
            else { if (items.length) cerrar(); texto.push(l); }
        }
        cerrar();
        return salida.join('');
    }).join('');
}

/** Lo que puede un lienzo: sus scripts y estilos en línea, imágenes y letras en línea (`data:`, una letra de íconos);
 *  ni red, ni `<script src>`, ni `eval`. */
const POLITICA_LIENZO = "default-src 'none'; img-src https: data: blob:; font-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'";

/** El alto de un lienzo o un marco: píxeles, o «lleno» (lo que queda del panel, por la clase). */
function estiloAlto(alto: number | 'lleno' | undefined): string {
    return alto === 'lleno' ? '' : ` style="height:${Math.round(alto ?? 240)}px"`;
}

/** Una página servida dentro del panel. Su sandbox le deja su propio origen (necesita sus
 *  cookies y su almacenamiento), pero no alcanzar el panel: es otro origen. */
function htmlMarco(m: cli.JsonMarco): string {
    return `<iframe class="lienzo${m.alto === 'lleno' ? ' lleno' : ''}" src="${esc(m.url)}"`
        + ` sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-downloads"${estiloAlto(m.alto)}></iframe>`;
}

export class Paginas {
    /** la página y la memoria de cada lienzo, por ruta (ver `precargar`) */
    private readonly lienzos = new Map<string, string>();
    /** las memorias de los lienzos pintados: una llave al azar por lienzo → el archivo que declaró
     *  su página. El lienzo solo escribe ese archivo, y lo nombra con la llave, nunca con una ruta. */
    private readonly memorias = new Map<string, string>();
    /** de dónde es cada lienzo pintado («bloque:gantt», «app:x»), por su llave: lo que pide lo pide en nombre de eso */
    private readonly origenes = new Map<string, string>();

    /** La página y la memoria de los lienzos de una página, leídas del disco (o de la API, en el navegador)
     *  antes de dibujarla: el HTML se arma sin esperar. */
    async precargar(bloques: cli.JsonPagina['bloques'] | undefined): Promise<void> {
        const rutas = (bloques ?? []).flatMap(b => b.lienzo ? [b.lienzo.archivo, ...(b.lienzo.memoria ? [b.lienzo.memoria] : [])] : []);
        await Promise.all(rutas.map(async r => {
            const t = await disco().leer(r);
            if (t !== undefined) this.lienzos.set(r, t); else this.lienzos.delete(r);
        }));
    }

    /** Los bloques de una página, en HTML. */
    html(bloques: cli.JsonPagina['bloques'], origen = ''): string[] {
        const h: string[] = [];
        this.memorias.clear();   // los iframes de antes se reemplazan: sus llaves ya no valen
        bloques.forEach((b, i) => {
            if (b.lienzo) h.push(this.lienzo(b.lienzo, origen));
            if (b.marco) h.push(htmlMarco(b.marco));
            if (b.destacado) h.push(`<div class="prop" style="--c: var(--${esc(b.color ?? 'azul')})">`);
            if (b.titulo) h.push(`<h2>${esc(b.titulo)}</h2>`);
            else if (i > 0 && !b.destacado) h.push('<div class="sep-pag"></div>');
            if (b.texto) h.push(`<div class="md-pag">${mdSimple(b.texto)}</div>`);
            for (const x of b.items ?? []) {
                const clic = x.conversacion ? ` data-accion="conversacion" data-valor="${esc(x.conversacion)}"`
                    : x.hilo ? ` data-accion="ir" data-valor="${esc(x.hilo)}"`
                    : x.enlace ? ` data-accion="abrir-enlace" data-valor="${esc(x.enlace)}"` : '';
                const fecha = x.fecha ? x.fecha.slice(0, 16).replace('T', ' ').replace(' 00:00', '') : '';
                h.push(`<div class="item-pag${clic ? ' clic' : ''}"${clic}`
                    + ` title="${esc(x.conversacion ? 'clic: leer la conversación entera' : x.hilo ? `clic: ir a «${x.hilo}»` : x.enlace ? `clic: abrir ${x.enlace}` : '')}">`
                    + `<div class="fila"><b>${esc(x.titulo)}</b><span class="der dim">${esc(fecha)}</span></div>`
                    + (x.texto ? `<div class="texto-pag">${mdSimple(x.texto)}</div>` : '') + '</div>');
            }
            if (b.destacado) h.push('</div>');
        });
        return h;
    }

    /** Un lienzo va como `srcdoc`: su página la lee la API (es un archivo del repositorio), no se sirve. Como
     *  srcdoc no tiene query string, un script previo deja los params en la URL (`about:srcdoc?…`) y en
     *  `window.lienzo`. El sandbox sin allow-same-origin deja correr sus scripts sin alcanzar la página, y su
     *  política de contenido (POLITICA_LIENZO), sin red: lo que promete docs/contratos.md. */
    lienzo(l: cli.JsonLienzo, origen = ''): string {
        // lo que necesita (su página y su memoria) se leyó antes, al llegar la página (precargar)
        let doc = this.lienzos.get(l.archivo);
        if (doc === undefined) return `<div class="fila falla">no pude leer ${esc(l.archivo)}</div>`;
        const params: Record<string, string> = {};
        for (const [k, v] of Object.entries(l.params ?? {})) params[k] = String(v);
        const datos = JSON.stringify(params).replace(/</g, '\\u003c');
        // con `memoria`, el lienzo recibe lo que guardó la vez anterior y una función para guardar:
        // el iframe no tiene almacenamiento propio (sandbox sin allow-same-origin)
        let memoria = '';
        // la llave nombra a este lienzo en lo que manda: su memoria, y lo que pide (`pedir`)
        const llave = llaveAlAzar();
        if (origen) this.origenes.set(llave, origen);
        // `pedir(orden, datos)`: que telar haga algo por él (cambiar una fecha). Devuelve una promesa con lo que quedó, o
        // falla con el porqué; la página pregunta a la persona la primera vez (telar.servicios.lienzos)
        const pedir = !origen ? '' : `var n=0,esperan={};window.addEventListener('message',function(e){var d=e.data;`
            + `if(!d||d.lienzo!=='respuesta'||!esperan[d.id])return;var p=esperan[d.id];delete esperan[d.id];`
            + `if(d.ok)p[0](d.datos);else p[1](new Error(d.error||'no se pudo'))});`
            + `window.lienzo.pedir=function(orden,datos){return new Promise(function(si,no){var id=String(++n);esperan[id]=[si,no];`
            + `parent.postMessage({lienzo:'pedir',llave:${JSON.stringify(llave)},id:id,orden:orden,datos:datos},'*')})};`;
        if (l.memoria) {
            this.memorias.set(llave, l.memoria);
            let leida = 'null';
            try { const t = this.lienzos.get(l.memoria); if (t !== undefined) { JSON.parse(t); leida = t; } } catch { /* todavía no guardó nada */ }
            memoria = `window.lienzo.memoria=${leida.replace(/</g, '\\u003c')};window.lienzo.guardar=function(d){`
                + `parent.postMessage({lienzo:'guardar',llave:${JSON.stringify(llave)},datos:JSON.stringify(d)},'*')};`;
        }
        const previo = `<meta http-equiv="Content-Security-Policy" content="${POLITICA_LIENZO}"><script>(function(){var p=${datos};window.lienzo={params:p};${memoria}${pedir}`
            + `var q=new URLSearchParams(p).toString();`
            + `if(q){try{history.replaceState(null,'','about:srcdoc?'+q)}catch(e){}}})()</script>`;
        doc = previo + doc;
        return `<iframe class="lienzo${l.alto === 'lleno' ? ' lleno' : ''}" sandbox="allow-scripts" srcdoc="${esc(doc)}"${estiloAlto(l.alto)}></iframe>`;
    }

    /** Lo que un lienzo pide guardar (`window.lienzo.guardar`), en el archivo que declaró su página: solo el de su
     *  llave, y si es JSON. Se escribe entero (temporal y rename): un corte a medias no deja un JSON roto que el
     *  lienzo no pueda leer. */
    /** Lo que pide un lienzo (`window.lienzo.pedir`), en nombre de su origen: se lo pide a telar y, si telar dice que
     *  falta el permiso, le pregunta a la persona (siempre, esta vez, no) y vuelve a pedir. Devuelve la respuesta para
     *  el lienzo. */
    async pedir(llave: string, orden: string, datos: unknown): Promise<{ ok: boolean; datos?: unknown; error?: string }> {
        const origen = this.origenes.get(llave);
        if (!origen) return { ok: false, error: 'este lienzo no puede pedir órdenes' };
        let r = await cli.lienzoPedir(origen, orden, datos);
        const permiso = r.cuerpo?.permiso as { modulo: string; orden: string; descripcion: string; decision: string } | undefined;
        if (!r.datos && permiso && permiso.decision !== 'negado') {
            const eleccion = await ui.aviso(`El módulo «${permiso.modulo}» pide ${permiso.descripcion}.`, 'Permitir siempre', 'Solo esta vez', 'No',
                { detalle: `Lo que telar le concede queda anotado; se revoca con: telar modulos permisos ${permiso.modulo} --quitar ${permiso.orden}` });
            if (eleccion === 'Permitir siempre' || eleccion === 'Solo esta vez') {
                await cli.conceder(permiso.modulo, permiso.orden, 'concedido');
                r = await cli.lienzoPedir(origen, orden, datos);
                if (eleccion === 'Solo esta vez') void cli.conceder(permiso.modulo, permiso.orden, 'olvidar');
            } else if (eleccion === 'No') {
                await cli.conceder(permiso.modulo, permiso.orden, 'negado');
            }
        }
        return r.datos ? { ok: true, datos: r.datos.datos } : { ok: false, error: r.error ?? 'no se pudo' };
    }

    guardar(llave: string, datos: string): void {
        const ruta = this.memorias.get(llave);
        if (!ruta || datos.length > 4_000_000) return;
        try { JSON.parse(datos); } catch { return; }
        // sin permiso o sin disco: el lienzo sigue, sin memoria
        void disco().escribir(ruta, datos).then(ok => { if (ok) this.lienzos.set(ruta, datos); });
    }
}
