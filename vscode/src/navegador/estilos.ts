// Los estilos del dashboard, empaquetados (en el navegador no hay archivos que leer). Este módulo va
// primero en app.ts: las vistas arman su CSS al cargarse, y tienen que encontrarlos ya puestos.
import { usarEstilos } from '../estilo';

import ahora from '../../media/css/ahora.css';
import base from '../../media/css/base.css';
import compartir from '../../media/css/compartir.css';
import conversacion from '../../media/css/conversacion.css';
import dia from '../../media/css/dia.css';
import documento from '../../media/css/documento.css';
import hilos from '../../media/css/hilos.css';
import lectura from '../../media/css/lectura.css';
import plan from '../../media/css/plan.css';
import proyectos from '../../media/css/proyectos.css';
import terminal from '../../media/css/terminal.css';
import tokens from '../../media/css/tokens.css';
import webCss from '../../media/css/web.css';

usarEstilos({ ahora, base, compartir, conversacion, dia, documento, hilos, lectura, plan, proyectos, terminal, tokens, web: webCss });

export const web = webCss;
