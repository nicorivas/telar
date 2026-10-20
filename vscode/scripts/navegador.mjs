// Empaqueta el dashboard para el navegador (src/navegador/app.ts) en src/telar/web/app.js, el archivo que
// sirve `telar serve --web`. Los módulos de Node que importan las vistas se reemplazan por los de
// src/navegador/nodo (en el navegador no hay archivos ni procesos), y los estilos se cargan como texto.
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { readFileSync, writeFileSync } from 'node:fs';

const aqui = path.dirname(fileURLToPath(import.meta.url));
const nodo = path.join(aqui, '..', 'src', 'navegador', 'nodo');
const reemplazos = { fs: 'fs.ts', path: 'path.ts', child_process: 'child_process.ts', os: 'os.ts', http: 'vacio.ts', crypto: 'vacio.ts' };

await build({
    entryPoints: [path.join(aqui, '..', 'src', 'navegador', 'app.ts')],
    outfile: path.join(aqui, '..', '..', 'src', 'telar', 'web', 'app.js'),
    bundle: true, format: 'iife', platform: 'browser', target: 'es2022',
    minify: process.argv.includes('--min'), sourcemap: false, legalComments: 'none',
    loader: { '.css': 'text' },
    // `process` lo leen los módulos de Node al cargarse (cli.ts): en el navegador, uno vacío
    banner: { js: 'var __dirname = "/", __filename = "/app.js"; var process = globalThis.process || { env: {}, platform: "navegador", cwd: function () { return "/"; } };' },
    plugins: [{
        name: 'node-en-el-navegador',
        setup(b) {
            b.onResolve({ filter: /^(node:)?(fs|path|child_process|os|http|crypto)$/ }, a => ({ path: path.join(nodo, reemplazos[a.path.replace(/^node:/, '')]) }));
        },
    }],
    logLevel: 'warning',
});
console.log('src/telar/web/app.js');

// el marco de la página (indice.html): sus estilos sobre los tokens, en un archivo que carga antes que app.js
const css = n => readFileSync(path.join(aqui, '..', 'media', 'css', `${n}.css`), 'utf8');
writeFileSync(path.join(aqui, '..', '..', 'src', 'telar', 'web', 'marco.css'),
    `/* Generado por vscode/scripts/navegador.mjs desde vscode/media/css (tokens, base y marco): no editar aquí. */\n`
    + `@layer base, vistas;\n@layer base {\n${css('tokens')}\n${css('base')}\n}\n@layer vistas {\n${css('marco')}\n}\n`);
console.log('src/telar/web/marco.css');
