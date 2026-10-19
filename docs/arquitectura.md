# Cómo está hecho telar

telar junta en un solo lugar los hilos de trabajo de una persona: cada hilo es una terminal con
un agente (Claude Code, por ejemplo) trabajando en una carpeta. Alrededor de los hilos, telar
muestra lo que hay que hacer (tareas, agenda, correo) y deja que los agentes se hablen entre sí,
en una máquina o en varias.

Este documento explica las piezas, cómo se conectan y por dónde se enchufa lo propio. El ejemplo
de punta a punta es **conectar un sistema de tareas**, al final.

## El dibujo

```
 lo que ves                el núcleo                         lo que hay debajo
 ─────────                 ─────────                         ─────────────────

 ┌──────────────┐        ┌──────────────────────┐          ┌──────────────────────┐
 │ barra de     │        │                      │  tmux    │ una sesión de tmux   │
 │ hilos        │──┐     │   la CLI `telar`     │─────────▶│ por máquina; cada    │
 └──────────────┘  │     │   (Python)           │          │ hilo es una ventana  │
 ┌──────────────┐  │     │                      │          │ con su agente        │
 │ dashboard    │──┼────▶│  · hilos             │          └──────────┬───────────┘
 │ (tareas,     │  │JSON │  · mensajes          │                     │ ganchos del agente
 │  agenda,     │  │     │  · proveedores       │◀────────────────────┘ («trabajando»,
 │  correo…)    │  │     │  · módulos           │                        «te espera»,
 └──────────────┘  │     │  · periódicos        │                        «terminó»)
 ┌──────────────┐  │     │                      │          ┌──────────────────────┐
 │ terminal del │──┘     │                      │  bus     │ las otras máquinas,  │
 │ hilo (web)   │        │                      │◀────────▶│ cada una con su      │
 └──────────────┘        └───┬─────────┬────────┘  (NATS)  │ `telar nodo`         │
   VS Code o navegador       │         │                   └──────────────────────┘
                             │         │
                ┌────────────┘         └─────────────┐
                ▼                                    ▼
 ┌────────────────────────────┐       ┌──────────────────────────────┐
 │ tu repositorio de trabajo  │       │ lo tuyo, enchufado           │
 │ + telar-perfil.yaml        │       │ · proveedores (tareas,       │
 │ (qué es un proyecto, qué   │       │   calendario, lo que sea)    │
 │ se lee de cada uno)        │       │ · módulos (modulo.toml)      │
 └────────────────────────────┘       └──────────────────────────────┘
```

Tres reglas sostienen el dibujo:

1. **Todo pasa por la CLI.** La barra, el dashboard y la página web no tienen lógica propia:
   llaman a `telar … --json` y dibujan lo que vuelve. Cada salida `--json` es un contrato escrito
   en [contratos.md](contratos.md). Cualquier cosa que telar muestra, un script o un agente la puede
   pedir igual.
2. **telar no sabe qué es un proyecto, ni cómo son tus tareas.** Lo dice tu repositorio
   (`telar-perfil.yaml`) y lo traen tus proveedores. telar sabe de hilos, de mensajes y de máquinas.
3. **Nada se hace a escondidas.** Los comandos son listas de palabras (sin shell), los proveedores
   no salen a la red salvo que se les pida, y una acción solo corre si el proveedor la ofreció.

## Las piezas

| pieza | qué es | dónde vive |
|---|---|---|
| **hilo** | una ventana de tmux con un agente, vinculada a una carpeta. telar recuerda su conversación, su atención y su prioridad | la sesión de tmux; el estado en `~/.local/state/telar/` |
| **perfil** | lo que tu repositorio dice de sí mismo: qué carpetas son unidades de trabajo, qué archivo es su cara, qué secciones se leen | `telar-perfil.yaml`, en la raíz del repo ([perfil.md](perfil.md)) |
| **configuración** | lo de esta máquina: dónde está el repo, qué proveedores hay, qué se muestra | `~/.config/telar/config.toml` ([configuracion.md](configuracion.md)) |
| **proveedor** | un programa que le trae a telar datos de afuera, en un JSON conocido: tareas, agenda, cualquier lista | lo declaras en la configuración |
| **módulo** | una carpeta con un `modulo.toml` que aporta de una vez una pestaña, una app, un proceso periódico o un resultado | donde quieras; lo declaras en `[modulos]` |
| **mensaje** | texto para un hilo o un agente, en cualquier máquina; llega aunque el hilo esté cerrado | `telar mensaje`; viaja por el bus |
| **periódico** | algo que corre solo cada cierto tiempo, a veces abriendo un hilo con un agente | `telar periodicos` |
| **nodo** | el proceso de telar de cada máquina en el bus: recibe los mensajes, avisa a los hilos, publica qué hay vivo | `telar nodo`, como servicio |
| **superficie** | lo que dibuja: la extensión de VS Code, el panel web (`npm run panel`) o la página para el celular (`telar web`) | `vscode/` |

## Cómo se mueve una cosa

**Un hilo pide atención.** El agente de un hilo termina y espera respuesta. Su gancho
(`telar agente aviso`) anota «te espera» en el estado. La barra relee `telar hilos --json` y pinta
el hilo. Si el hilo vive en otra máquina, su nodo publica el cambio en el bus y la barra de aquí lo
ve igual.

**Un agente le pide algo a otro.** El hilo A corre `telar mensaje B "…"`. El mensaje va al bus. El
nodo de la máquina de B lo deja en su casilla, y el gancho de B se lo entrega al terminar su turno
(o se lo teclea si está ocioso).

**Una tarea se trabaja.** El dashboard pide las tareas (`telar hoy --json`, que consulta al
proveedor). Con ▶, telar busca el hilo de la tarea: el que lleva su id en el nombre, el que tiene su
carpeta en el texto o el que calza con una etiqueta. Si no hay ninguno, abre uno nuevo con el
agente y le da la tarea como primer mensaje (`pendiente_nuevo`). Con ✓, corre la acción «hecha»
que el proveedor ofreció.

## Por dónde se enchufa lo propio

| quiero… | se hace con | sin escribir código |
|---|---|---|
| que telar entienda mis proyectos | el perfil (`telar-perfil.yaml`) | sí |
| ver mis tareas | `[proveedores.tareas]`: `markdown` o `comando` | sí, con `markdown` |
| ver mi agenda | `[proveedores.calendario]`: iCal o `gws` | sí |
| una pestaña propia en el dashboard | `[bloques]`: un comando que imprime una página | no: un script |
| una app (un juego, un visor) | `[apps]`: una página, un archivo o una URL | depende |
| algo que corra solo | `telar periodicos crear …` | sí |
| empaquetar todo lo anterior | un módulo con `modulo.toml` | — |
| que otro agente o script use telar | la CLI con `--json` ([contratos.md](contratos.md)) | — |

## Conectar un sistema de tareas

Hay tres niveles. Cada uno agrega algo al anterior, y se puede parar en cualquiera.

### Nivel 1: casillas en tus documentos (sin código)

Si tus tareas ya son casillas de markdown en los README de tus proyectos, basta con decirle a telar
dónde mirar:

```toml
# ~/.config/telar/config.toml
[proveedores.tareas]
tipo  = "markdown"
rutas = ["proyectos/*/README.md"]
encabezado = '^##\s+Pendientes'     # opcional: solo esa sección
```

Cada casilla es una tarea, y entiende unas pocas marcas:

```markdown
## Pendientes
- [ ] Medir el alcance real  vence:2026-06-30  !alta  #faro
- [>] Ajustar el giro  espera:@electricista
- [x] Montar la lámpara
```

`[>]` es «en curso», `espera:` saca la tarea de lo urgente (depende de otro), y como la tarea vive en
la carpeta de un proyecto, telar ya sabe a qué hilo va.

### Nivel 2: tu propio gestor, por un puente (un script)

Si tus tareas viven en otra parte (un `todo.txt`, Todoist, una base de datos, una CLI propia),
escribes un **puente**: un programa que las imprime en el JSON que telar espera.

```toml
[proveedores.tareas]
tipo    = "comando"
comando = ["/ruta/a/mis-tareas"]
```

El programa imprime una lista. Solo `texto` es obligatorio:

```json
[{"id": "T84", "texto": "Medir el alcance", "prioridad": "alta", "vence": "2026-06-30",
  "etiquetas": ["faro"], "espera": "", "en_curso": false, "area": "trabajo"}]
```

Un puente completo para un `todo.txt` (el formato de [todotxt.org](http://todotxt.org)):

```python
#!/usr/bin/env python3
"""Las tareas de ~/todo.txt, en el JSON de telar."""
import json, re
from pathlib import Path

PRIORIDAD = {"A": "alta", "B": "media", "C": "baja"}
tareas = []
for n, linea in enumerate(Path("~/todo.txt").expanduser().read_text().splitlines(), 1):
    if not linea.strip() or linea.startswith("x "):          # vacía o hecha
        continue
    pri = re.match(r"\(([A-Z])\) ", linea)
    vence = re.search(r"\bdue:(\d{4}-\d{2}-\d{2})", linea)
    texto = re.sub(r"^\([A-Z]\) |\s*\bdue:\S+|\s*[+@]\S+", "", linea).strip()
    tareas.append({"id": str(n), "texto": texto,
                   "prioridad": PRIORIDAD.get(pri.group(1)) if pri else None,
                   "vence": vence.group(1) if vence else None,
                   "etiquetas": re.findall(r"\+(\S+)", linea)})   # +faro → el hilo «faro»
print(json.dumps(tareas, ensure_ascii=False))
```

Con eso, tus tareas aparecen en el dashboard ordenadas por urgencia (prioridad y fecha), cada una al
lado del hilo donde se trabaja, y ▶ la lleva a un agente.

### Nivel 3: la ficha y las acciones

Para poder **hacer cosas** sobre una tarea desde telar (marcarla hecha, cambiarle la fecha,
contestarle algo), el puente ofrece además su **ficha**:

```toml
[proveedores.tareas]
tipo    = "comando"
comando = ["/ruta/a/mis-tareas"]
detalle = ["/ruta/a/mis-tareas", "--ver", "{id}"]
```

`--ver T84` imprime una página con la tarea y sus botones:

```json
{ "titulo": "T84 · Medir el alcance", "subtitulo": "alta · vence 2026-06-30",
  "bloques": [{"titulo": "notas", "texto": "falta la cota del lado norte"}],
  "acciones": [
    {"nombre": "✓ hecha", "rol": "hecha", "principal": true, "comando": ["mis-tareas", "hecha", "T84"]},
    {"nombre": "cambiar fecha", "rol": "fecha", "comando": ["mis-tareas", "fecha", "T84", "{texto}"]},
    {"nombre": "anotar", "pide": "qué", "comando": ["mis-tareas", "nota", "T84", "{texto}"]},
    {"nombre": "trabajar en un hilo", "tipo": "hilo"} ] }
```

- El **rol** dice qué es cada acción para quien la corre sin abrir la ficha. `hecha` es la que
  corre el ✓ de la lista, y `fecha` la que corre el selector de fecha al hacer clic en un atraso.
- Una acción solo corre si el proveedor la ofreció: telar vuelve a pedir la ficha y toma el
  comando de ahí, nunca de quien hace clic.
- Un agente usa lo mismo: `telar tarea T84 --json` lee la ficha, y
  `telar tarea T84 --accion 0` corre la primera acción.

### Si tus tareas viven en otra máquina

Si el gestor corre en un servidor (para que el laptop y el servidor vean lo mismo, sin esperar a que
se sincronice una copia), se dice dónde:

```toml
[proveedores.tareas]
tipo = "comando"
en   = "servidor"          # la máquina, por el bus: se leen allá y sus acciones corren allá
comando = ["/ruta/allá/mis-tareas"]
```

## Hacia dónde va

Lo de arriba es lo que corre hoy: cada superficie llama a la CLI abriendo un proceso por pedido. El
plan cambia una flecha y agrega una caja:

```
 hoy:        superficie ──(un proceso por pedido)──▶ CLI telar ──▶ tmux, bus, proveedores

 después:    superficie ──(HTTP / WebSocket)──▶ telar serve ──▶ el mismo núcleo
             (el panel web primero;               (siempre corriendo: objetos, acciones,
              VS Code, el celular, otra app)       y los cambios avisados, no preguntados)
```

Para quien conecta un sistema de tareas, el puente no cambia: sigue siendo un programa que imprime
el JSON. El estado y el orden de esa migración están en
[dashboard-fuera-de-vscode.md](propuestas/dashboard-fuera-de-vscode.md), «Estado y plan».

## Lo que viene

La propuesta [primitivas.md](propuestas/primitivas.md) ordena todo esto en pocas piezas. Para quien
conecta sus tareas, cambian dos cosas:

- **Un módulo podrá traer su proveedor.** Hoy el proveedor se declara a mano en la configuración. Un
  módulo `mis-tareas/` con su `modulo.toml` declarará el proveedor, sus acciones y su pestaña, y
  instalarlo será una línea.
- **Las tareas serán un tipo de objeto más.** Con una dirección (`tarea:T84`), acciones con esquema
  y cambios que se piden «desde el último». Lo mismo valdrá para el correo, los eventos o lo que
  traiga un módulo, y un agente los usará igual que el dashboard.
