# El estado

El multiplexor sabe qué hilos hay ahora mismo, cómo se llaman y cuál tiene el foco.
El repositorio de trabajo sabe qué dice cada documento. Ninguno de los dos recuerda
lo que decidiste **sobre** un hilo: a qué carpeta lo vinculaste, qué conversación
vive ahí, qué prioridad le pusiste, cuánto tiempo llevas mirándolo.

Eso es el estado, y vive fuera de los dos.

```
~/.local/state/telar/        (o lo que diga `estado` en el config.toml)
├── vinculos.json            hilo → carpeta
├── prioridades.json         hilo → 1, 2 o 3
├── archivados.json          [hilo, …]
├── atencion.json            hilo → {atencion, desde}
├── sesiones.json            hilo → [conversación, …]
├── paneles.json             panel → conversación
├── orden                    una palabra
└── foco.log                 ISO<TAB>hilo, una línea por cambio
```

Más los candados (`.candado` y un `.lock` por archivo), que están siempre vacíos:
lo que importa de ellos no es lo que contienen sino quién los tiene tomados.

**Es derivado y desechable.** Borrar la carpeta entera pierde los vínculos y el
tiempo medido; no pierde nada de trabajo. telar arranca igual, con menos memoria.
Por eso no se versiona, no va dentro de `raiz` y no hay migraciones: si un archivo
se rompe, telar dice cuál es y se borra.

## La llave es el nombre, no el id

Todos estos archivos están indexados por el **nombre** del hilo. `paneles.json` es
la excepción: lo está por el panel del multiplexor.

Podría estarlo por el `id`, que es estable mientras la sesión viva (`@3` en tmux, el
id del tab en zellij; ninguno es posicional). No lo está porque el id **no sobrevive a
cerrar la sesión**: al volver a levantarla, los mismos proyectos traen ids nuevos y el
estado quedaría huérfano entero. El nombre sí sobrevive, es lo que pusiste tú y lo que
reconoces.

El precio es que renombrar hay que acompañarlo, y renombrar es fácil: dos teclas en
tmux. Por eso `ids.json` recuerda qué nombre tenía cada id la última vez que se lo vio,
y `Estado.reconciliar()` —que corre al armar la lista de hilos— detecta el renombre y
mueve el estado detrás, avisando. Lo que mueve es `Estado.renombrar()`: mueve
las llaves de los cinco archivos de una sola vez, bajo el candado de la carpeta. Lo
que **no** reescribe es `foco.log`, y es a propósito: es historia, y reescribirla
para que cuadre un total es peor que un total repartido en dos nombres.

## Archivo por archivo

### `vinculos.json` — hilo → carpeta

```json
{ "faro": "proyectos/faro", "molino": "proyectos/molino" }
```

La ruta se guarda **relativa a `raiz`**, para que el estado siga sirviendo si mueves
el repositorio de trabajo. Una ruta que apunte fuera de la raíz se guarda absoluta.

Es lo único que conecta un hilo con lo que el perfil sabe leer: de aquí sale la
carpeta, de la carpeta sale el documento, del documento sale la ficha.

Al vestir un hilo, este vínculo **gana** sobre el directorio de trabajo que reporta
el multiplexor. El cwd es dónde quedó una shell; el vínculo es lo que decidiste.

### `prioridades.json` — hilo → 1, 2 o 3

```json
{ "faro": 1, "molino": 3 }
```

`1` alta, `2` media, `3` baja (`telar.modelo.Prioridad`). Un hilo sin prioridad no
es de prioridad baja: es un hilo sin prioridad, y al ordenar va **después** de los
tres niveles. Un número que no sea 1, 2 o 3 se ignora al leer.

### `archivados.json` — la lista de los guardados

```json
["molino", "arboleda"]
```

Archivar no cierra nada ni borra nada: saca al hilo de la lista viva y lo deja en un
cajón aparte. Lo contrario lo hace `desarchivar`, y también —solo— volver a levantar
el agente del hilo: ver `sesiones.json`.

### `atencion.json` — el semáforo del agente

```json
{ "faro": { "atencion": "espera", "desde": "2026-09-18T22:58:50" } }
```

Los cuatro colores son los de `telar.modelo.Atencion`: `ninguna`, `trabajando`,
`espera`, `termino`. Lo escribe quien vea al agente arrancar, pedir algo y terminar
—en Claude Code, los ganchos `UserPromptSubmit`, `Notification` y `Stop`—, que
normalmente conoce el id de la sesión y no el hilo: `Estado.hilo_de()` traduce.

`anotar_atencion` con `ninguna` borra la anotación en vez de escribir un color
apagado. Y conviene escribir solo cuando el color **cambia**: quien dibuja vigila el
archivo, y un `mtime` nuevo lo hace redibujar de balde.

### `sesiones.json` — las conversaciones de cada hilo

```json
{ "faro": ["3fca812d-…", "9b076f61-…"] }
```

En orden: la principal primero. Existe porque un multiplexor que resucita una sesión
guardada serializa el comando (`claude` a secas) y pierde con qué conversación
estaba: sin este mapa, cada hilo amanece con una conversación nueva y en blanco.

Se anota cuando el agente **arranca**, no cuando se necesita.

Tres reglas la mantienen honesta, y las tres están en `anotar_sesion`:

1. **una conversación vive en un hilo.** Entra en este y sale de donde estuviera.
2. **un panel corre una conversación.** La que corría antes en este panel, si no
   quedó abierta en otro, sale de su hilo. Para eso está `paneles.json`.
3. **revivir el agente desarchiva el hilo.** Si volviste a él, está vivo
   (`revivir=False` si no quieres esto).

Se acepta al leer el formato de una sola cadena (`"faro": "3fca812d-…"`); se escribe
siempre lista.

### `paneles.json` — panel → conversación

```json
{ "276": "e8727a5d-…", "15": "d054daae-…" }
```

Un panel corre una conversación a la vez. Este mapa es lo único que permite darse
cuenta de que la anterior se fue —un `/clear`, o salir y abrir otra— en vez de
acumularla: sin él, un hilo junta conversaciones muertas y al retomar se abre la
equivocada.

Es el único archivo que no está indexado por hilo, y el más volátil de todos: los
ids de panel no sobreviven a que se caiga el multiplexor. No importa; se reconstruye
solo la próxima vez que cada agente arranque.

### `orden` — cómo se ordena la lista

Una palabra suelta, sin JSON, para que se pueda cambiar con `echo alfa > orden` y
quien dibuja lo relea al instante:

| palabra | qué hace |
|---|---|
| `mux` | el orden que reporta el multiplexor (creación). Es el de por defecto |
| `alfa` | alfabético, sin distinguir mayúsculas |
| `reciente` | último foco primero; lo que nunca lo tuvo, al final |
| `prioridad` | 1 → 3, y sin prioridad al final |

Una palabra que telar no entienda se lee como `mux`: un archivo raro no es motivo
para no dibujar la lista. Escribirla sí se rechaza.

### `foco.log` — el reloj

```
2026-09-18T22:58:22	molino
2026-09-18T22:58:42	faro
```

Una línea por cambio de foco, y solo crece. Cada línea **abre** un intervalo que
cierra la siguiente; el último cierra ahora.

Dos decisiones que hay que conocer para leer cualquier total:

- **El intervalo se recorta a `intervalos.foco_maximo`** (una hora por defecto).
  Nadie avisa «me fui del computador»: sin el recorte, salir a almorzar le regala
  dos horas al hilo que quedó arriba. Tres horas seguidas en un hilo sin tocar nada
  cuentan una.
- **Un intervalo cuenta entero en el día en que empezó.** Cruzar la medianoche es
  raro y partirlo costaría más de lo que aclara.

Marcar dos veces seguidas el mismo hilo no escribe nada: el intervalo es el mismo, y
cortarlo en dos le quitaría el recorte de encima.

Las horas son **locales e ingenuas** (sin zona). Es el registro de uso de una
máquina, no un dato que viaje.

## Cómo se escribe

Varias sesiones del agente escriben estos archivos a la vez. Sin candado, la última
pisaba a las demás y se perdían prioridades.

- Toda escritura es **leer-modificar-escribir bajo `flock`**, sobre un `.lock` al
  lado del archivo.
- El archivo se escribe entero a un temporal y se mueve con `os.replace`, que es
  atómico: nadie lee nunca un JSON a medio escribir.
- Lo que toca varios archivos —`anotar_sesion`, `renombrar`, `olvidar`— toma además
  el candado de la carpeta (`.candado`), que se pide **siempre antes** que el de un
  archivo y nunca después. Con ese orden, anidarlos no se traba.
- Sin `fcntl` (Windows) se escribe igual, sin candado: el riesgo es perder una
  escritura simultánea, no corromper un archivo.

Una llave que empiece con `_` se ignora al leer: queda libre para una nota al pie
escrita a mano en el propio JSON.

## Lo puro y lo que toca el disco

`telar.estado` tiene dos mitades, y la frontera es explícita.

**`Estado`** es la que toca el disco: un objeto sobre una carpeta, construido con
`estado.abrir(config)`. Sus métodos son cortos porque no calculan nada.

**Las funciones del módulo** no tocan el disco: reciben lo ya leído y devuelven
datos nuevos. Son las que se prueban con datos inventados y las que usa quien dibuja
sin volver a leer.

| función | de qué a qué |
|---|---|
| `marcas_desde(lineas)` | líneas de `foco.log` → `Marca` ordenadas |
| `intervalos_de(marcas, tope)` | marcas → `(inicio, hilo, segundos)`, ya recortado |
| `tiempo_por_hilo(marcas, tope, …)` | marcas → segundos por hilo |
| `tiempo_por_dia(marcas, tope, …)` | lo mismo, abierto por día |
| `ultimo_foco(marcas)` | marcas → cuándo tuvo el foco cada hilo |
| `agrupar(tiempos, vinculos)` | dos hilos de la misma carpeta son un proyecto |
| `vestir(hilos, …)` | `Hilo` del multiplexor + estado → `Hilo` completo |
| `ordenar(hilos, criterio)` | por `Orden` |
| `partir(hilos)` | `(vivos, archivados)` |

`Estado.foto(tope=…)` es el puente: lee todo de una vez y bajo candado, y devuelve
justo los argumentos de `vestir`, para que nadie dibuje media lista de antes y media
de después.

```python
from telar import config, estado, mux

cfg = config.cargar()
est = estado.abrir(cfg)

crudos = mux.obtener(cfg).hilos()                      # lo que sabe el multiplexor
hilos = estado.vestir(crudos, raiz=cfg.raiz, **est.foto(tope=cfg.intervalos.foco_maximo))
vivos, archivados = estado.partir(estado.ordenar(hilos, est.orden()))
```

## Lo que el estado no guarda

- **La ficha.** Se lee del documento, que es la fuente. Guardarla sería tener dos
  verdades y una desactualizada.
- **Nada del repositorio de trabajo.** telar no escribe en `raiz`.
- **Nada de red, ni nada de un proveedor.** Lo que traiga un proveedor se consulta y
  se muestra; no se acumula aquí.
