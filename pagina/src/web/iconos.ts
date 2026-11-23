// Los íconos de la página (Codicons, de Nerd Fonts: la letra `iconos`, en media/css/iconos.css). Un nombre por cosa que
// se hace o se muestra, el mismo en todas partes: el menú de un hilo y el de un proyecto usan el mismo «abrir». Para
// agregar uno: su código (https://www.nerdfonts.com/cheat-sheet) aquí, y `python3 scripts/iconos.py` rehace la letra
// con solo los que se usan.

export const I = {
    ver: '\u{ea70}', retomar: '\u{eacf}', abrir: '\u{eb2c}', renombrar: '\u{ea73}', carpeta: '\u{eaf7}',
    vincular: '\u{eb15}', desvincular: '\u{ead0}', publico: '\u{eb01}', privado: '\u{ea75}', prioridad: '\u{ea71}',
    archivar: '\u{ea98}', desarchivar: '\u{eb09}', cerrar: '\u{ea76}', llevar: '\u{eac3}', traer: '\u{eac2}',
    descartar: '\u{ea81}', releer: '\u{eb37}', agente: '\u{ea85}', consolidar: '\u{eab3}', escribir: '\u{ea6b}', documento: '\u{eaa4}',
    copiar: '\u{ebcc}', hecha: '\u{eab2}', fecha: '\u{eab0}', persona: '\u{ea67}', enlace: '\u{eb14}', nuevo: '\u{ea60}',
    accion: '\u{ebcf}', direccion: '\u{eb15}', viaja: '\u{ea77}', alerta: '\u{ea6c}',
    // sin conexión (con telar, con una terminal): el enchufe suelto, el mismo glifo de desvincular
    desconectado: '\u{ead0}',
    remoto: '\u{ebcb}', abierto: '\u{eab4}', plegado: '\u{eab6}', persona_dot: '\u{ea71}', pedido: '\u{eb9a}',
    maquinas: '\u{eb50}', config: '\u{eb51}', actualizar: '\u{ebff}', etiqueta: '\u{ea66}', modo: '\u{ebeb}', enviar: '\u{ec0f}', reloj: '\u{ea82}',
    alfabetico: '\u{eab1}', urgencia: '\u{eaf2}',
    menu: '\u{ea7c}', pausa: '\u{ead1}', correr: '\u{ead3}', editar: '\u{ea73}', estrella: '\u{eb59}', sinEstrella: '\u{ea6a}',
    externo: '\u{eb14}', ordenar: '\u{eb73}', asc: '\u{eb71}', desc: '\u{eb6e}', atras: '\u{eab5}', siguiente: '\u{eab6}', subir: '\u{eab7}',
    deshacer: '\u{eae2}', lista: '\u{eb84}', lleno: '\u{ea71}', vacio: '\u{ebb5}', medio: '\u{eac6}', punto: '\u{eb8a}',
    chispa: '\u{ec10}', filtro: '\u{eaf1}', ninguno: '\u{eabd}', casa: '\u{eb06}', ventana: '\u{eb7f}', compartir: '\u{eb18}',
    adelante: '\u{ea9c}', marca: '\u{eb2b}', hijo: '\u{f060d}', rama: '\u{f062c}',
    terminal: '\u{ea85}', lectura: '\u{eb2f}', conversacion: '\u{eac7}',
    codigos: '\u{ea90}', buscar: '\u{ea6d}', irArchivo: '\u{ea94}', ficha: '\u{ea74}',
    etapa: '\u{eb20}', ancho: '\u{ea99}',
    // las apps (juegos, visores): el de las extensiones, cuatro cuadrados, el mismo de una skill
    apps: '\u{eae6}',
    // la instrucción: mandarle a un hilo (el suyo, uno nuevo, otro) o a un agente lo que se pide, con su contexto
    instruccion: '\u{ead2}',
    // es la misma que otra tarea: se le une (foco, el ⋯ de una tarea)
    unir: '\u{ebab}',
    foco: '\u{ebf8}', tabla: '\u{ebb7}', dia: '\u{eab0}', semana: '\u{eb56}', plan: '\u{ebaf}', libro: '\u{eaa4}', anterior: '\u{ea9b}',
    // cuánto toma una tarea (rápida o larga): un reloj de pulsera, que no se confunde con las flechas de reloj e instrucción
    tamano: '\u{eb7c}',
    // lo que carga el contexto de un hilo (web/carga.ts): la hoja (una torta), cada grupo y cada clase de cosa
    carga: '\u{ebe4}', claude: '\u{eb08}', capas: '\u{ebd2}', repite: '\u{ebc0}', correo: '\u{eb1c}',
    markdown: '\u{eb1d}', memoria: '\u{eb9c}', gancho: '\u{ea86}', listado: '\u{eb17}', skill: '\u{eae6}', mcp: '\u{eb2d}',
    herramientas: '\u{eb6d}', subagentes: '\u{ea7e}', git: '\u{ea68}', campana: '\u{eaa2}', archivo: '\u{ea7b}',
    imagen: '\u{eaea}', sesion: '\u{eaad}', salida: '\u{eb9d}', llamada: '\u{ea8c}', resumen: '\u{eac5}', razonamiento: '\u{ea61}',
    // una pasada de pulso (lo que un agente revisó en las fuentes y avanzó en las tareas, cada hora): el pulso
    pulso: '\u{eb31}',
    // un mundo (`[mundos]`: trabajo, personal, ambos): el planeta con anillo, delante de su nombre en la banda y en la
    // ventana de mundos (de Font Awesome Extension, en Nerd Fonts: Codicons no tiene planeta)
    planeta: '\u{e22e}',
} as const;

/** La etapa de un plazo (la fase que dice su fuente) como la clase de trabajo que hay en ella: preparar (la lista),
 *  partir (el cohete), desarrollar (las herramientas), cerrar (el paquete: se entrega) y cerrado (el doble visto).
 *  Cuánto avanzó no lo dice el ícono: lo dice el círculo de su fase. Una etapa que no está aquí, `I.etapa`. */
export const ETAPA_I: Record<string, string> = {
    preparacion: '\u{eb67}', inicio: '\u{eb44}', desarrollo: '\u{eb6d}', cierre: '\u{eb29}', cerrado: '\u{ebb1}',
};

/** Las columnas de una fila de la barra de hilos, en la letra de íconos (un ícono ocupa 2ch: la columna es de 2ch
 *  y así todo calza en la grilla del monoespaciado): la prioridad (alta llena, media a medias, baja vacía, sin ella
 *  un punto) y la atención (trabajando, te espera, terminó). */
export const PRIO_I: Record<number, string> = { 0: '\u{eb8a}', 1: '\u{ebb4}', 2: '\u{eac6}', 3: '\u{ebb5}' };
export const ATENCION_I: Record<string, string> = { trabajando: '\u{ea71}', espera: '\u{eaa2}', termino: '\u{eab2}' };

/** Los colores con que se distingue una acción en un menú, por lo que hace: ir y mirar, cambiar, el agente, hecho,
 *  y lo que borra o cierra. */
export const C = { ir: 'azul', cambiar: 'amarillo', agente: 'violeta', hecho: 'verde', quitar: 'rojo', otro: 'cian' } as const;
