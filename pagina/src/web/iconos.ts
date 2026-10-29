// Los íconos de la página (Codicons, de Nerd Fonts: la letra `iconos`, en media/css/iconos.css). Un nombre por cosa que
// se hace o se muestra, el mismo en todas partes: el menú de un hilo y el de un proyecto usan el mismo «abrir». Para
// agregar uno: su código (https://www.nerdfonts.com/cheat-sheet) aquí, y `python3 scripts/iconos.py` rehace la letra
// con solo los que se usan.

export const I = {
    ver: '\u{ea70}', retomar: '\u{ead2}', abrir: '\u{eb2c}', renombrar: '\u{ea73}', carpeta: '\u{eaf7}',
    vincular: '\u{eb15}', desvincular: '\u{ead0}', publico: '\u{eb01}', privado: '\u{ea75}', prioridad: '\u{ea71}',
    archivar: '\u{ea98}', desarchivar: '\u{eb09}', cerrar: '\u{ea76}', llevar: '\u{eac3}', traer: '\u{eac2}',
    olvidar: '\u{ea81}', agente: '\u{ea85}', consolidar: '\u{eab3}', escribir: '\u{ea6b}', documento: '\u{eaa4}',
    copiar: '\u{ebcc}', hecha: '\u{eab2}', fecha: '\u{eab0}', persona: '\u{ea67}', enlace: '\u{eb14}', nuevo: '\u{ea60}',
    accion: '\u{ebcf}', direccion: '\u{eb15}', viaja: '\u{ea77}', alerta: '\u{ea6c}',
} as const;

/** Los colores con que se distingue una acción en un menú, por lo que hace: ir y mirar, cambiar, el agente, hecho,
 *  y lo que borra o cierra. */
export const C = { ir: 'azul', cambiar: 'amarillo', agente: 'violeta', hecho: 'verde', quitar: 'rojo', otro: 'cian' } as const;
