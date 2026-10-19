// Service worker mínimo: existe para que el navegador deje instalar el panel como app (y recibir lo que
// el teléfono comparte). No guarda nada en caché: todo va a la red, como siempre.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', () => {});
