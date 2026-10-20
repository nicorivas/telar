// Empaqueta la página (src/navegador/app.ts) en src/telar/web/app.js, el archivo que sirve
// `telar serve --web`. Los estilos se cargan como texto.
// Y arma src/telar/web/marco.css (el marco de la página: tokens, base y marco) y src/telar/web/eco.js (el eco
// de la terminal, src/navegador/eco).
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

// el marco de la página (indice.html): sus estilos sobre los tokens, en un archivo que carga antes que app.js
function marco() {
    const css = n => readFileSync(path.join(carpetaCss, `${n}.css`), 'utf8');
    writeFileSync(path.join(web, 'marco.css'),
        `/* Generado por vscode/scripts/navegador.mjs desde vscode/media/css (tokens, base y marco): no editar aquí. */\n`
        + `@layer base, vistas;\n@layer base {\n${css('tokens')}\n${css('base')}\n}\n@layer vistas {\n${css('marco')}\n}\n`);
}

const ctx = await context({
    entryPoints: [path.join(aqui, '..', 'src', 'navegador', 'app.ts')],
    outfile: path.join(web, 'app.js'),
    bundle: true, format: 'iife', platform: 'browser', target: 'es2022',
    minify: process.argv.includes('--min'), sourcemap: false, legalComments: 'none',
    loader: { '.css': 'text' },
    // con --watch, cada vuelta dice cómo le fue (los errores ya los imprime esbuild)
    plugins: mirar ? [{ name: 'avisar', setup(b) { b.onEnd(r => console.log(`${hora()} app.js ${r.errors.length ? `con ${r.errors.length} error(es)` : 'listo'}`)); } }] : [],
    logLevel: 'warning',
});

// el eco de la terminal: aparte, porque lo carga la página de la terminal (no app.js)
const ctxEco = await context({
    entryPoints: [path.join(aqui, '..', 'src', 'navegador', 'eco', 'entrada.ts')],
    outfile: path.join(web, 'eco.js'),
    bundle: true, format: 'iife', platform: 'browser', target: 'es2022',
    minify: process.argv.includes('--min'), sourcemap: false, legalComments: 'none',
    plugins: mirar ? [{ name: 'avisar', setup(b) { b.onEnd(r => console.log(`${hora()} eco.js ${r.errors.length ? 'con errores' : 'listo'}`)); } }] : [],
    logLevel: 'warning',
});

// el modo lectura de un hilo (src/navegador/vistas/lectura.ts): aparte, porque lo carga su página
const ctxLectura = await context({
    entryPoints: [path.join(aqui, '..', 'src', 'navegador', 'vistas', 'lectura.ts')],
    outfile: path.join(web, 'lectura.js'),
    bundle: true, format: 'iife', platform: 'browser', target: 'es2022',
    minify: process.argv.includes('--min'), sourcemap: false, legalComments: 'none',
    plugins: mirar ? [{ name: 'avisar', setup(b) { b.onEnd(r => console.log(`${hora()} lectura.js ${r.errors.length ? 'con errores' : 'listo'}`)); } }] : [],
    logLevel: 'warning',
});

if (!mirar) {
    await ctx.rebuild();
    await ctx.dispose();
    await ctxEco.rebuild();
    await ctxEco.dispose();
    console.log('src/telar/web/eco.js');
    await ctxLectura.rebuild();
    await ctxLectura.dispose();
    console.log('src/telar/web/lectura.js');
    marco();
    console.log('src/telar/web/app.js');
    console.log('src/telar/web/marco.css');
} else {
    marco();
    await ctx.watch();
    await ctxEco.watch();
    await ctxLectura.watch();
    // esbuild mira lo que importa app.ts (y los CSS de las vistas); marco.css no lo importa nadie: aparte
    let pendiente;
    watch(carpetaCss, (_, nombre) => {
        if (!/^(tokens|base|marco)\.css$/.test(nombre ?? '')) return;
        clearTimeout(pendiente);
        pendiente = setTimeout(() => { try { marco(); console.log(`${hora()} marco.css listo`); } catch (e) { console.error(e.message); } }, 50);
    });
    console.log(`${hora()} mirando src/ y media/css (⌃C para salir)`);
}
