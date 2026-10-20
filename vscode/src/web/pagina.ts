// Lo que el marco del dashboard necesita en el navegador: `acquireVsCodeApi` (mandar
// mensajes y guardar su estado; el nombre viene del webview de la extensión de VS Code, deprecada) y los
// mensajes que llegan. El script del dashboard (dia.ts) habla con `vscode`, y ese `vscode` es la página que
// lo contiene (src/navegador), por postMessage. Los avisos y diálogos los pone esa página (web/interfaz.ts).

/** El script que va antes del del dashboard: define `acquireVsCodeApi`. El canal: la página que contiene al
 *  dashboard (src/navegador), por postMessage. */
const CANAL_PADRE = String.raw`
  // la página que contiene al dashboard (src/navegador) le habla por postMessage
  var abierto = false, cola = [];
  function conectar() {
    window.addEventListener('message', function (e) {
      if (e.source !== window.parent || !e.data || !e.data.__telarPadre) return;
      llega(e.data.__telarPadre);
    });
    abierto = true;
  }
  function enviar(s) { window.parent.postMessage({ __telarHijo: s }, location.origin === 'null' ? '*' : location.origin); }`;

function script(canal: string): string {
    return String.raw`
(function () {` + canal + String.raw`
  function llega(m) { window.dispatchEvent(new MessageEvent('message', { data: m })); }
  function mandar(m) { var s = JSON.stringify(m); if (abierto) enviar(s); else cola.push(s); }
  window.acquireVsCodeApi = function () {
    return {
      postMessage: mandar,
      getState: function () { try { return JSON.parse(localStorage.getItem('telar.' + location.pathname) || 'null'); } catch (x) { return null; } },
      setState: function (s) { try { localStorage.setItem('telar.' + location.pathname, JSON.stringify(s)); } catch (x) {} },
    };
  };
  conectar();
})();
`;
}

/** El script del dashboard que corre en el navegador (src/navegador): le habla a la página que lo contiene. */
export const SCRIPT_NAVEGADOR = script(CANAL_PADRE);
