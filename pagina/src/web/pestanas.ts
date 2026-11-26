// Las pestañas en la página (componentes/pestanas.ts): lo que hacen está en web/pestanas-fila.ts, que no conoce la
// página; aquí se le pone el menú del «⋯», el de la casa (ui.menu).

import * as ui from './ui';
import { usarMenu } from './pestanas-fila';

export * from './pestanas-fila';

usarMenu((opciones, ancla, titulo) => ui.menu(opciones, ancla, titulo));
