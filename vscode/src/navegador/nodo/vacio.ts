// `http`, `crypto` y lo que no hace falta en el navegador: el transporte de la API es `fetch`.
export const request = (): never => { throw new Error('en el navegador, la API va por fetch'); };
export default { request };
