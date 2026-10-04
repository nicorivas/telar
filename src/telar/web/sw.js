// Service worker mínimo: existe para que Chrome deje instalar telar como app. No guarda nada en caché
// —la página se edita y se recarga sola, y un caché la dejaría vieja—: todo va a la red como siempre.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', () => {});
