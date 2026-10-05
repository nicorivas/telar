# Agentes residentes

*Estado: construido en lo principal (octubre de 2026). Lo que falta, al final.*

## El problema

Cada proceso recurrente (pasar por los pendientes, procesar el correo, armar las lecturas) abría una
sesión nueva del agente que quedaba viva esperando. En un servidor de 8 GB, eso se come la memoria:
decenas de procesos de Claude, cada uno con su contexto, casi todos ociosos. Además cada sesión empezaba
de cero y no sabía lo que hizo la anterior.

## La idea: una sola clase de hilo, con dos modos

No hay «hilos de agente» e «hilos de proyecto». Un hilo es siempre una conversación con una casa
(una carpeta). La diferencia es de comportamiento:

- **De paso**: se abre para algo, se archiva. Los hilos de proyecto, casi siempre.
- **Residente**: siempre existe, recibe encargos, rota su conversación cuando pesa. Vive en una carpeta
  bajo `[agentes] carpeta` con una estructura fija (`CLAUDE.md`, `README.md`, `memoria/`, `bitacora.md`).

Dos clases habrían dado una sola ventaja (dejar claro quién coordina) a cambio de dudar siempre a quién
escribirle. El nombre y la casa ya dicen quién coordina.

## Cómo carga cada uno lo suyo

Claude lee los `CLAUDE.md` desde la carpeta donde arranca hasta la raíz del repositorio (no más arriba),
y los de subcarpetas recién cuando trabaja en ellas. Un `@import` fuera de la carpeta de arranque se
ignora sin aviso cuando no hay nadie para aprobarlo, y un enlace simbólico se resuelve a la ruta real.
De ahí:

- la raíz del repositorio tiene lo de **la casa** (mapa, reglas) y la leen todos;
- `agentes/CLAUDE.md` tiene lo **común a los agentes** y lo carga cada uno solo por vivir debajo;
- cada agente **arranca en su carpeta** (telar lo hace aunque `[agente] carpeta` diga otra cosa), para
  cargar su `CLAUDE.md` desde el comienzo; su memoria propia entra con `@memoria/MEMORY.md`, que está
  dentro de su carpeta y sí se importa.

Los ganchos que usan `$CLAUDE_PROJECT_DIR` se rompen al arrancar en una subcarpeta: esa variable es la
carpeta de arranque, no la raíz. Hay que escribirlos con una ruta fija.

## Encargos

`telar encargar <agente> "…"` (o un periódico con `agente = "…"`):

- sesión viva y libre → se le escribe el encargo;
- viva y trabajando → cola; el gancho `Stop` le entrega el siguiente al terminar su turno;
- sin sesión → se abre retomando su última conversación, o una nueva si pasó de `[agentes] rotar_mb`.

El resultado se deja **en el registro** (la tarea, el estado del proyecto, la bitácora), no en la
conversación: así nadie depende de que la conversación siga ahí, y no hay ida y vuelta entre agentes.
Un agente que coordina (Gestión) no hace el trabajo de un proyecto: se lo encarga al hilo del proyecto.

## El tope

`[agente] max_vivos` limita las sesiones propias vivas de una máquina. Antes de abrir otra, telar cierra
las ociosas que nadie mira, la más quieta primero y los residentes al final. Cerrar no pierde nada: la
conversación queda en disco y se retoma.

## Lo que falta

- Encargarle a un **hilo de proyecto** (no solo a un residente): hoy se le escribe con `SendMessage` o
  correo; falta que `telar encargar` lo acepte, con la misma cola.
- El tope no cuenta los **tabs** de la sesión del telar en el servidor, solo las sesiones propias.
- Un agente que vive en **otra máquina** que la que encarga: hoy `telar encargar` es local.
