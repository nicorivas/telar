// Empaqueta la página (src/navegador/app.ts) en src/telar/web/app.js, el archivo que sirve
// `telar serve --web`, y el catálogo de componentes (src/componentes/catalogo.ts, /componentes) en componentes.js. Y
// arma src/telar/web/marco.css: los estilos de toda la página (media/css), que carga antes que app.js. Y los componentes
// para el lienzo de un módulo (src/lienzo/componentes.ts): lienzo-componentes.js y su hoja, lienzo-componentes.css, que la
// página mete en línea en el lienzo que los pide (vistas/dashboard/pagina.ts; docs/contratos.md).
//
//   node scripts/navegador.mjs --min      una vez (npm run navegador, que antes revisa los tipos)
//   node scripts/navegador.mjs --watch    y de nuevo con cada cambio (npm run navegador:watch, con --min: el mismo
//                                         app.js que se commitea; scripts/dev.py)
import { context } from 'esbuild';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { readFileSync, watch, writeFileSync } from 'node:fs';

const aqui = path.dirname(fileURLToPath(import.meta.url));
const carpetaCss = path.join(aqui, '..', 'media', 'css');
const web = path.join(aqui, '..', '..', 'src', 'telar', 'web');
const mirar = process.argv.includes('--watch');
const hora = () => new Date().toTimeString().slice(0, 8);

// los estilos de la página (indice.html), en un archivo que carga antes que app.js: en la capa «base», los tokens (y
// los temas y las densidades, después: lo suyo gana) y los componentes; en «vistas», el marco y cada pantalla (cada una con su @scope)
const BASE = ['tokens', 'temas', 'densidades', 'iconos', 'base', 'componentes', 'prosa', 'circulo', 'item', 'tarjeta', 'casillas', 'orden', 'buscador', 'seccion', 'filtros', 'ventana', 'boton', 'mundos', 'contestar', 'ventanas', 'pantalla', 'pestanas', 'mensaje', 'franja', 'pulso', 'partes', 'jornada', 'tactica', 'equipo'];
const VISTAS = ['marco', 'web', 'hilos', 'dia', 'plan', 'proyectos', 'ahora', 'configuracion', 'periodicos', 'documento', 'objeto', 'compartir', 'lectura', 'leer', 'conversacion', 'terminal', 'catalogo', 'modos'];
// los del lienzo de un módulo (src/lienzo/componentes.ts): sus hojas, sin capa (entran antes que el estilo del lienzo), y
// la letra de íconos de la página con otro nombre, `telar-iconos`, para no tapar la del lienzo (lienzo.css); y la prosa
// (`C.prosa`: el markdown lo dibuja la página, aquí solo va su hoja)
const KIT = ['circulo', 'pestanas', 'buscador', 'filtros', 'prosa', 'lienzo'];
const css = n => readFileSync(path.join(carpetaCss, `${n}.css`), 'utf8');
function marco() {
    writeFileSync(path.join(web, 'marco.css'),
        `/* Generado por pagina/scripts/navegador.mjs desde pagina/media/css (${[...BASE, ...VISTAS].join(', ')}): no editar aquí. */\n`
        + `@layer base, vistas;\n@layer base {\n${BASE.map(css).join('\n')}\n}\n@layer vistas {\n${VISTAS.map(css).join('\n')}\n}\n`);
    const letra = css('iconos').match(/@font-face\s*\{[^}]*\}/)?.[0];
    if (!letra) throw new Error('media/css/iconos.css: no encuentro su @font-face');
    writeFileSync(path.join(web, 'lienzo-componentes.css'),
        `/* Generado por pagina/scripts/navegador.mjs desde pagina/media/css (la letra de iconos, ${KIT.join(', ')}): no editar aquí. */\n`
        + `${letra.replace(/font-family:\s*iconos\s*;/, 'font-family: telar-iconos;')}\n${KIT.map(css).join('\n')}\n`);
}

const ctx = await context({
    entryPoints: { app: path.join(aqui, '..', 'src', 'navegador', 'app.ts'), componentes: path.join(aqui, '..', 'src', 'componentes', 'catalogo.ts'),
        'lienzo-componentes': path.join(aqui, '..', 'src', 'lienzo', 'componentes.ts') },
    outdir: web,
    bundle: true, format: 'iife', platform: 'browser', target: 'es2022',
    minify: process.argv.includes('--min'), sourcemap: false, legalComments: 'none',
    // con --watch, cada vuelta dice cómo le fue (los errores ya los imprime esbuild)
    plugins: mirar ? [{ name: 'avisar', setup(b) { b.onEnd(r => console.log(`${hora()} app.js y componentes.js ${r.errors.length ? `con ${r.errors.length} error(es)` : 'listo'}`)); } }] : [],
    logLevel: 'warning',
});

if (!mirar) {
    await ctx.rebuild();
    await ctx.dispose();
    marco();
    console.log('src/telar/web/app.js');
    console.log('src/telar/web/componentes.js');
    console.log('src/telar/web/marco.css');
    console.log('src/telar/web/lienzo-componentes.js');
    console.log('src/telar/web/lienzo-componentes.css');
} else {
    marco();
    await ctx.watch();
    // esbuild mira lo que importa app.ts (y los CSS de las vistas); marco.css no lo importa nadie: aparte
    let pendiente;
    watch(carpetaCss, (_, nombre) => {
        if (![...BASE, ...VISTAS, ...KIT].includes((nombre ?? '').replace(/\.css$/, ''))) return;
        clearTimeout(pendiente);
        pendiente = setTimeout(() => { try { marco(); console.log(`${hora()} marco.css y lienzo-componentes.css listos`); } catch (e) { console.error(e.message); } }, 50);
    });
    console.log(`${hora()} mirando src/ y media/css (⌃C para salir)`);
}
