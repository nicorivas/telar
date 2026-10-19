// los estilos se empaquetan como texto (scripts/navegador.mjs, loader «text»)
declare module '*.css' { const texto: string; export default texto; }
