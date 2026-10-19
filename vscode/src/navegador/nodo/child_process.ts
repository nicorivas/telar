// `child_process` en el navegador: no se abren procesos. Quien los pide recibe un error, como si el
// programa no existiera, y el dashboard ya sabe decirlo.
type Cb = (e: Error | null, out: string, err: string) => void;
export function execFile(_cmd: string, ...resto: unknown[]): void {
    const cb = resto.reverse().find((x): x is Cb => typeof x === 'function');
    setTimeout(() => cb?.(new Error('en el navegador no se corren programas: falta su ruta en la API'), '', ''), 0);
}
export function spawn(): never { throw new Error('en el navegador no se corren programas'); }
export default { execFile, spawn };
