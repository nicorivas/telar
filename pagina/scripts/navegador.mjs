// Empaqueta la página (src/navegador/app.ts) en src/telar/web/app.js, el archivo que sirve
// `telar serve --web`. Y arma src/telar/web/marco.css: los estilos de toda la página (media/css), que carga
// antes que app.js.
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

// los estilos de la página (indice.html), en un archivo que carga antes que app.js: en la capa «base», los tokens;
// en «vistas», el marco y cada pantalla (cada una con su @scope)
const BASE = ['tokens', 'base'];
const VISTAS = ['marco', 'web', 'hilos', 'dia', 'plan', 'proyectos', 'ahora', 'configuracion', 'documento', 'compartir', 'lectura', 'conversacion', 'terminal'];
function marco() {
    const css = n => readFileSync(path.join(carpetaCss, `${n}.css`), 'utf8');
    writeFileSync(path.join(web, 'marco.css'),
        `/* Generado por pagina/scripts/navegador.mjs desde pagina/media/css (${[...BASE, ...VISTAS].join(', ')}): no editar aquí. */\n`
        + `@layer base, vistas;\n@layer base {\n${BASE.map(css).join('\n')}\n}\n@layer vistas {\n${VISTAS.map(css).join('\n')}\n}\n`);
}

const ctx = await context({
    entryPoints: [path.join(aqui, '..', 'src', 'navegador', 'app.ts')],
    outfile: path.join(web, 'app.js'),
    bundle: true, format: 'iife', platform: 'browser', target: 'es2022',
    minify: process.argv.includes('--min'), sourcemap: false, legalComments: 'none',
    // con --watch, cada vuelta dice cómo le fue (los errores ya los imprime esbuild)
    plugins: mirar ? [{ name: 'avisar', setup(b) { b.onEnd(r => console.log(`${hora()} app.js ${r.errors.length ? `con ${r.errors.length} error(es)` : 'listo'}`)); } }] : [],
    logLevel: 'warning',
});

if (!mirar) {
    await ctx.rebuild();
    await ctx.dispose();
    marco();
    console.log('src/telar/web/app.js');
    console.log('src/telar/web/marco.css');
} else {
    marco();
    await ctx.watch();
    // esbuild mira lo que importa app.ts (y los CSS de las vistas); marco.css no lo importa nadie: aparte
    let pendiente;
    watch(carpetaCss, (_, nombre) => {
        if (![...BASE, ...VISTAS].includes((nombre ?? '').replace(/\.css$/, ''))) return;
        clearTimeout(pendiente);
        pendiente = setTimeout(() => { try { marco(); console.log(`${hora()} marco.css listo`); } catch (e) { console.error(e.message); } }, 50);
    });
    console.log(`${hora()} mirando src/ y media/css (⌃C para salir)`);
}
