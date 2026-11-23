# Propuestas

Aquí está solo lo que falta hacer. Cómo es telar hoy está en [../arquitectura.md](../arquitectura.md);
lo que ya cambió, en el CHANGELOG y en git. Cuando algo de una propuesta se construye, su diseño pasa a
`arquitectura.md` (o a `configuracion.md`) y sale de aquí.

Para retomar el trabajo después de empezar de cero: lee `arquitectura.md`, después esta lista, y toma
el primer paso sin hacer de la primera propuesta.

## El plan, en orden

1. **[telar-para-otros.md](telar-para-otros.md)**: el plan maestro. Qué falta para que lo use un
   equipo y después cualquiera: credenciales por persona en el bus, `telar instalar` y la 0.2.0, el mod
   de Claude Code, retirar la extensión de VS Code y los vestigios.
2. **[primitivas.md](primitivas.md)**: pocas piezas de las que se arma todo (objetos con dirección,
   mensajes con modos, el encargo, el lugar y los worktrees, vistas, disparadores, permisos), y
   `telar commit` en todas partes.
   El paso 3, el agente como definición, tiene su diseño aparte:
   **[agente-como-definicion.md](agente-como-definicion.md)** (`agente.toml`: qué es, cómo convive con lo de
   hoy y las decisiones que faltan). Su primer paso está hecho.
   El paso 4, los mensajes con modos y el Encargo, también:
   **[mensajes-con-modos.md](mensajes-con-modos.md)** (aviso, pedido y encargo; el Encargo como
   objeto; cómo se funde `telar encargar`). Su primer paso está hecho.
   El paso 6, las vistas, también: **[vistas.md](vistas.md)** (`[vistas]`: qué se muestra y dónde aparece, qué
   tablas reemplaza y cómo conviven). Su primer paso está hecho.
   El paso 7, los disparadores y el estado deseado, también: **[disparadores.md](disparadores.md)**
   (`[disparadores]`: un reloj, una tecla o un cambio; qué reconciliaría el nodo y por qué por ahora solo avisa).
   Su primer paso está hecho.
   El paso 8, los permisos, también: **[permisos.md](permisos.md)** (sujetos, la solicitud de permiso como objeto,
   `[permisos]` en el manifiesto de un módulo; quién contesta y qué se hace cumplir, por decidir). Su primer paso
   está hecho.
3. **[un-dueno-por-hilo.md](un-dueno-por-hilo.md)**: que la máquina donde corre un hilo sea la única
   que guarda su registro; las demás lo leen del bus. Hecho, salvo quitar las sesiones propias de antes.
4. **[servidor-mainframe.md](servidor-mainframe.md)**: que una persona del bus pida un lugar en el servidor y tenga ahí sus
   hilos, como una máquina más suya. En uso desde el 26-oct-2026, con la puerta (una dirección para todos); falta
   que el alojado la pruebe desde su laptop, el aviso de pedido nuevo y `telar doctor`.
5. **[modos.md](modos.md)**: modos de la página (estándar, foco…), un nombre con valores para la disposición, la
   terminal y los avisos, que se cambian de una vez. El primer paso, en construcción; el resto, en su hoja de ruta.
6. **[fechas.md](fechas.md)**: un formato único para lo que tiene día (actividades, hitos, sesiones) y fuentes
   intercambiables (secciones de cronograma en los documentos, comandos, las tareas), juntadas en `telar fechas`;
   un Gantt o el calendario las dibujan sin saber de qué equipo son. Casi todo hecho: `telar fechas`, mapas, editar donde viven, el Gantt general; falta publicarlo y los eventos.
7. **[acciones.md](acciones.md)**: un solo menú para toda entidad (clic derecho, donde está), hecho. Su «instrucción…»
   tiene su propuesta, **[instruccion.md](instruccion.md)**: una sola ventana para mandarle algo a un hilo o a un agente
   desde donde sea (foco, la ficha, el menú, un agente), con el contexto de donde se pidió. Hecha en lo principal;
   falta llevar a ella los atajos de las tareas, los bloques, los eventos y el formulario de un periódico.
8. **[lo-que-hacen-los-otros.md](lo-que-hacen-los-otros.md)**: ideas tomadas de otros administradores
   de agentes, por decidir una a una (entregar mensajes sin teclear, permisos desde fuera, intentos por
   tarea…).
9. **[productos.md](productos.md)**: un módulo de productos (lo que se vende) con su backlog de ideas y un tablero
   kanban, sobre README y frontmatter declarados por cada repositorio; para que las ideas de mejora salgan de la
   lista de tareas. Hecho (lista, backlog, tablero, ideas y tareas); queda declararlo como tipo general.
10. **[codigos.md](codigos.md)**: los códigos que un hilo nombra (`H3`, `PEN-07`, `T84`) en una hoja al lado de su
   conversación, con lo que son, para buscarlos y ver su detalle, sin que nadie los declare. Hecho (el escáner, la
   hoja y los enlaces); quedan ideas para después.
11. **[componentes.md](componentes.md)**: la librería de componentes de la página (buscador, orden, nuevo, sección,
   ventana), con su jerarquía y el catálogo navegable por ella; se trabaja de noche, en una rama que se revisa de
   día. Hechos el ítem, el círculo, los temas, las densidades y el catálogo.
12. **[lo-que-espera-a-la-persona.md](lo-que-espera-a-la-persona.md)**: una sola bandeja para lo que un agente le
   pide decidir a la persona (permisos, preguntas en vivo, propuestas en tareas, retenidos) y la pregunta que vive
   como archivo en el repositorio; qué está duplicado entre los avisos de hoy. Hecho el paso 1 (la bandeja de solo
   lectura: `telar esperas` y la pestaña «te esperan»); lo demás, por decidir.
13. **[orden-por-modos.md](orden-por-modos.md)**: la página ordenada por lo que hace la persona, en dos ejes. Uno es
   el modo: Táctica (decidir y hacer), Estrategia (mirar con calma), Foco y Todo (ver y buscar todo). El otro es el
   mundo (trabajo, personal). Decidido en lo grande; se construye por pasos.
14. **[seguir-sin-su-maquina.md](seguir-sin-su-maquina.md)**: seguir un hilo en el servidor cuando su máquina está
   apagada, desde un respaldo de su conversación que cada nodo manda por turno; y qué hace el laptop al volver. Sin
   construir: falta que la persona decida qué conversaciones se copian al servidor.

## Cómo se escribe una propuesta

- Arriba, una línea de estado: qué está decidido y qué no.
- El porqué en pocas líneas, la idea, y **los pasos que faltan**, cada uno de los cuales deja todo
  funcionando.
- Cada mecanismo nuevo dice **qué reemplaza**, o por qué no reemplaza nada. Lo reemplazado se retira con un alias
  que avisa, no se deja al lado.
- Sin historia: lo que se hizo no se cuenta aquí. Al terminar un paso, su diseño se mueve a
  `arquitectura.md` y el paso se borra de la lista.
