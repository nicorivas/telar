// Un WKWebView con el bloqueo de ventanas emergentes de Safari (javaScriptCanOpenWindowsAutomatically = false, el de
// fábrica): el motor de Safari de esta Mac, que decide igual que Safari si una pestaña se abre. Lo usa
// pruebas/abrir-safari.mjs. Carga la dirección de argv[1] y escribe por la salida estándar:
//   ABRE <url>      la página pidió una ventana y WebKit la dejó (si la bloquea, no llega aquí)
//   VA <url>        adónde fue esa ventana nueva
//   <texto>         lo que la página manda con webkit.messageHandlers.log.postMessage(texto)
// La página pide clics de verdad (NSEvent, como el mouse) con postMessage({ clic: [x, y] }), y termina con «FIN».
import Cocoa
import WebKit

final class Prueba: NSObject, NSApplicationDelegate, WKUIDelegate, WKScriptMessageHandler, WKNavigationDelegate {
    var ventana: NSWindow!
    var web: WKWebView!
    var nuevas: [WKWebView] = []
    var otrasVentanas: [NSWindow] = []

    func applicationDidFinishLaunching(_ n: Notification) {
        let conf = WKWebViewConfiguration()
        conf.preferences.javaScriptCanOpenWindowsAutomatically = false
        conf.userContentController.add(self, name: "log")
        web = WKWebView(frame: NSRect(x: 0, y: 0, width: 900, height: 500), configuration: conf)
        web.uiDelegate = self
        // fuera de la pantalla y sin activar la aplicación (.accessory): no se ve ni le quita el foco a nadie
        ventana = NSWindow(contentRect: NSRect(x: -20000, y: -20000, width: 900, height: 500), styleMask: [.titled], backing: .buffered, defer: false)
        ventana.title = "telar: prueba de abrir enlaces (se cierra sola)"
        ventana.contentView = web
        ventana.orderFrontRegardless()
        web.load(URLRequest(url: URL(string: CommandLine.arguments[1])!))
        DispatchQueue.main.asyncAfter(deadline: .now() + 20) { print("TOPE"); exit(2) }
    }

    func webView(_ w: WKWebView, createWebViewWith c: WKWebViewConfiguration, for a: WKNavigationAction, windowFeatures f: WKWindowFeatures) -> WKWebView? {
        print("ABRE \(a.request.url?.absoluteString ?? "")"); fflush(stdout)
        let nueva = WKWebView(frame: NSRect(x: 0, y: 0, width: 300, height: 200), configuration: c)
        nueva.navigationDelegate = self
        nuevas.append(nueva)
        // en una ventana propia, detrás de la de la prueba (sin una, la de la prueba deja de recibir los clics)
        let v = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 300, height: 200), styleMask: [.titled], backing: .buffered, defer: false)
        v.contentView = nueva
        v.orderBack(nil)
        otrasVentanas.append(v)
        return nueva
    }

    func webView(_ w: WKWebView, decidePolicyFor a: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if w !== web, let u = a.request.url?.absoluteString, u != "about:blank" { print("VA \(u)"); fflush(stdout); decisionHandler(.cancel); return }
        decisionHandler(.allow)
    }

    func evento(_ t: NSEvent.EventType, _ p: NSPoint) -> NSEvent {
        NSEvent.mouseEvent(with: t, location: p, modifierFlags: [], timestamp: ProcessInfo.processInfo.systemUptime,
                           windowNumber: ventana.windowNumber, context: nil, eventNumber: 0, clickCount: 1, pressure: t == .leftMouseUp ? 0 : 1)!
    }

    func userContentController(_ u: WKUserContentController, didReceive m: WKScriptMessage) {
        if let d = m.body as? [String: Any], let c = d["clic"] as? [Double] {
            ventana.makeFirstResponder(web)
            // de la página (desde arriba) a la ventana (desde abajo)
            let p = NSPoint(x: c[0], y: web.frame.height - c[1])
            // directo al WKWebView, no por la ventana: así no hace falta activar la aplicación ni quitarle el foco a nadie
            web.mouseDown(with: evento(.leftMouseDown, p))
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.08) { self.web.mouseUp(with: self.evento(.leftMouseUp, p)) }
            return
        }
        if let s = m.body as? String {
            print(s); fflush(stdout)
            if s == "FIN" { exit(0) }
        }
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let prueba = Prueba()
app.delegate = prueba
app.run()
