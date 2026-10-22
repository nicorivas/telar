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
   **[mensajes-con-modos.md](mensajes-con-modos.md)** (aviso, pedido, encargo y consulta; el Encargo como
   objeto; cómo se funde `telar encargar`). Su primer paso está hecho.
   El paso 6, las vistas, también: **[vistas.md](vistas.md)** (`[vistas]`: qué se muestra y dónde aparece, qué
   tablas reemplaza y cómo conviven). Su primer paso está hecho.
   El paso 7, los disparadores y el estado deseado, también: **[disparadores.md](disparadores.md)**
   (`[disparadores]`: un reloj, una tecla o un cambio; qué reconciliaría el nodo y por qué por ahora solo avisa).
   Su primer paso está hecho.
3. **[un-dueno-por-hilo.md](un-dueno-por-hilo.md)**: que la máquina donde corre un hilo sea la única
   que guarda su registro; las demás lo leen del bus. Hecho, salvo quitar las sesiones propias de antes.
4. **[lo-que-hacen-los-otros.md](lo-que-hacen-los-otros.md)**: ideas tomadas de otros administradores
   de agentes, por decidir una a una (entregar mensajes sin teclear, permisos desde fuera, intentos por
   tarea…).

## Cómo se escribe una propuesta

- Arriba, una línea de estado: qué está decidido y qué no.
- El porqué en pocas líneas, la idea, y **los pasos que faltan**, cada uno de los cuales deja todo
  funcionando.
- Sin historia: lo que se hizo no se cuenta aquí. Al terminar un paso, su diseño se mueve a
  `arquitectura.md` y el paso se borra de la lista.
