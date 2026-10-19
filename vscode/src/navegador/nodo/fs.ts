// `fs` en el navegador: no hay archivos. Lo que el dashboard lee del disco, en el navegador lo pide a la
// API (o no lo muestra todavía); estas funciones dicen «no está», que es lo que ya sabe manejar.
const noHay = (ruta: unknown) => Object.assign(new Error(`en el navegador no hay archivos: ${String(ruta)}`), { code: 'ENOENT' });
export const existsSync = (): boolean => false;
export function readFileSync(ruta: unknown): never { throw noHay(ruta); }
export function readdirSync(ruta: unknown): never { throw noHay(ruta); }
export function statSync(ruta: unknown): never { throw noHay(ruta); }
export function writeFileSync(ruta: unknown): never { throw noHay(ruta); }
export function mkdirSync(): void { /* nada */ }
export function renameSync(ruta: unknown): never { throw noHay(ruta); }
export type Dirent = { name: string; isDirectory(): boolean; isFile(): boolean };
export default { existsSync, readFileSync, readdirSync, statSync, writeFileSync, mkdirSync, renameSync };
