// Los íconos de la página (Codicons, de Nerd Fonts: la letra `iconos`, en media/css/iconos.css). Un nombre por cosa que
// se hace o se muestra, el mismo en todas partes: el menú de un hilo y el de un proyecto usan el mismo «abrir». Para
// agregar uno: su código (https://www.nerdfonts.com/cheat-sheet) aquí, y `python3 scripts/iconos.py` rehace la letra
// con solo los que se usan.

export const I = {
    ver: '\u{ea70}', retomar: '\u{ead2}', abrir: '\u{eb2c}', renombrar: '\u{ea73}', carpeta: '\u{eaf7}',
    vincular: '\u{eb15}', desvincular: '\u{ead0}', publico: '\u{eb01}', privado: '\u{ea75}', prioridad: '\u{ea71}',
    archivar: '\u{ea98}', desarchivar: '\u{eb09}', cerrar: '\u{ea76}', llevar: '\u{eac3}', traer: '\u{eac2}',
    descartar: '\u{ea81}', releer: '\u{eb37}', agente: '\u{ea85}', consolidar: '\u{eab3}', escribir: '\u{ea6b}', documento: '\u{eaa4}',
    copiar: '\u{ebcc}', hecha: '\u{eab2}', fecha: '\u{eab0}', persona: '\u{ea67}', enlace: '\u{eb14}', nuevo: '\u{ea60}',
    accion: '\u{ebcf}', direccion: '\u{eb15}', viaja: '\u{ea77}', alerta: '\u{ea6c}',
    remoto: '\u{ebcb}', abierto: '\u{eab4}', plegado: '\u{eab6}', persona_dot: '\u{ea71}', pedido: '\u{eb9a}',
    maquinas: '\u{eb50}', config: '\u{eb51}', actualizar: '\u{ebff}', etiqueta: '\u{ea66}', modo: '\u{ebeb}',
    terminal: '\u{ea85}', lectura: '\u{eb2f}', conversacion: '\u{eac7}',
} as const;

/** Las columnas de una fila de la barra de hilos, en la letra de íconos (un ícono ocupa 2ch: la columna es de 2ch
 *  y así todo calza en la grilla del monoespaciado): la prioridad (alta llena, media a medias, baja vacía, sin ella
 *  un punto) y la atención (trabajando, te espera, terminó). */
export const PRIO_I: Record<number, string> = { 0: '\u{eb8a}', 1: '\u{ebb4}', 2: '\u{eac6}', 3: '\u{ebb5}' };
export const ATENCION_I: Record<string, string> = { trabajando: '\u{ea71}', espera: '\u{eaa2}', termino: '\u{eab2}' };

/** Los colores con que se distingue una acción en un menú, por lo que hace: ir y mirar, cambiar, el agente, hecho,
 *  y lo que borra o cierra. */
export const C = { ir: 'azul', cambiar: 'amarillo', agente: 'violeta', hecho: 'verde', quitar: 'rojo', otro: 'cian' } as const;
