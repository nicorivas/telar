// Los estilos del dashboard, que todavía va en un marco, empaquetados como texto. Este módulo va primero en app.ts: las vistas arman su CSS al
// cargarse, y tienen que encontrarlos ya puestos. Los de lo que se dibuja directo en la página van en marco.css
// (scripts/navegador.mjs).
import { usarEstilos } from '../estilo';

import ahora from '../../media/css/ahora.css';
import base from '../../media/css/base.css';
import dia from '../../media/css/dia.css';
import plan from '../../media/css/plan.css';
import proyectos from '../../media/css/proyectos.css';
import tokens from '../../media/css/tokens.css';

usarEstilos({ ahora, base, dia, plan, proyectos, tokens });
