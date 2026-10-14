---
name: equipo-nico
description: Consultar las tareas que Nico comparte con el equipo, sugerirle subir una prioridad y pedirle una tarea nueva. Úsala cuando pregunten por lo que Nico está haciendo, su estado o prioridad, o cuando haya que pedirle que priorice algo.
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

## Pedirle algo a Nico (una tarea nueva)

Si necesitas que Nico haga algo («hacer la sesión 5 de GOA»), no lo dejes para un chat: déjalo como pedido. Le llega
como notificación y él decide si lo agrega como tarea suya (P2, con la etiqueta de equipo, y tú la ves en la lista).
Hace falta un título concreto (5 a 150 caracteres); el contexto (por qué, para quién, qué depende de esto) y la fecha
(`AAAA-MM-DD`) son opcionales pero ayudan. Máximo 10 cosas tuyas esperando a Nico a la vez.

```bash
curl -s -X POST -H "Authorization: Bearer $EQUIPO_NICO_LLAVE" -H "Content-Type: application/json" \
  -d '{"titulo":"Hacer la sesión 5 de GOA","contexto":"la pide el cliente para el jueves","vence":"2026-10-22"}' \
  http://100.66.75.117:8766/api/pedir
```

Antes de molestar a Nico, el servidor revisa si ya hay una tarea parecida **que el equipo ve**. Si la hay, no crea el pedido:
responde `409` con `existe` (título, estado, prioridad, fecha, avance y un `resumen`). Cuéntale a tu persona ese estado: puede
que no necesite pedir nada. Solo si es de verdad otra cosa, repite el envío con `"aunque_exista": true` en el JSON. Y si Nico
dice que ya existía una tarea que el equipo no ve, tu pedido queda como `ya existía` con su estado en `nota`: léelo y
transmítelo, no lo pidas de nuevo.

Antes de enviar, muéstrale a tu persona el pedido tal como saldrá y espera su visto bueno. En `GET /api/tareas`, tus
pedidos salen en `sugerencias` con `tipo: "tarea"`, su estado (pendiente, aceptada, rechazada) y, si Nico la aceptó,
el número de la tarea que quedó.

## Lo que no se puede
No hay forma de crear, editar ni cerrar las tareas de Nico directamente (solo pedirlas, arriba), ni de hablar con sus
agentes por aquí. Para otra cosa, díselo a Nico directamente.
