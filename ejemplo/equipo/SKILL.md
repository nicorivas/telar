---
name: equipo-nico
description: Consultar las tareas que Nico comparte con el equipo y sugerirle subir una prioridad. Úsala cuando pregunten por lo que Nico está haciendo, su estado o prioridad, o cuando haya que pedirle que priorice algo.
---

# Tareas compartidas de Nico

Nico comparte algunas de sus tareas por una página de solo lectura. De cada una ves título, estado,
prioridad (P0 la más alta), fecha, proyecto y la línea de avance. **No** ves el detalle ni la historia:
si no está en la lista, Nico no la compartió; no insistas ni lo deduzcas.

Requisitos: Tailscale conectado, y tu llave en la variable `EQUIPO_NICO_LLAVE` (guárdala en tu perfil o
en un archivo tuyo; **nunca** en un repositorio).

## Consultar

```bash
curl -s -H "Authorization: Bearer $EQUIPO_NICO_LLAVE" http://100.66.75.117:8766/api/tareas
```

Devuelve `tareas` (id, titulo, estado, prioridad, vence, proyecto, avance, espera) y `sugerencias`
(las tuyas y cómo salieron: pendiente, aceptada o rechazada, con la nota de Nico si dejó una).

## Sugerir que suba una prioridad

Solo se puede sugerir, no cambiar: Nico decide. Hace falta un motivo concreto (5 a 500 caracteres), una
sugerencia pendiente por tarea, y no se puede pedir más arriba de P0.

```bash
curl -s -X POST -H "Authorization: Bearer $EQUIPO_NICO_LLAVE" -H "Content-Type: application/json" \
  -d '{"tarea":"T123","motivo":"bloquea la demo del jueves con el cliente"}' \
  http://100.66.75.117:8766/api/sugerir
```

Antes de enviar, muéstrale a tu persona la tarea y el motivo, y espera su visto bueno: a Nico le llega
como una notificación. Con un 429, espera unos segundos.

## Lo que no se puede
No hay forma de crear, editar ni cerrar tareas, ni de hablar con los agentes de Nico por aquí.
Para otra cosa, díselo a Nico directamente.
