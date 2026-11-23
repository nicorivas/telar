# Módulos y catálogos

Un **módulo** es un repositorio con un `modulo.toml` que dice lo que le aporta a telar: órdenes, una pestaña, una
app, procesos periódicos, contexto para los agentes, tipos de objeto. Un **catálogo** es un archivo,
`.telar/catalogo.toml`, que lista módulos para encontrarlos e instalarlos por su nombre. Este documento es el
formato de los dos; el criterio para escribir uno (qué pedir, cómo nombrarlo, cuándo subir la versión) está en la
skill `/modulos`, que `telar agente instalar` le pone al agente.

## El ciclo, en órdenes

```sh
telar modulos nuevo saludo                  # arma ./telar-saludo: modulo.toml, una orden de ejemplo, README, git
telar modulos instalar --enlazar ./telar-saludo   # probarlo desde donde está, sin copiarlo
telar modulos revisar ./telar-saludo        # lo que le falta para publicarlo
telar modulos publicar ./telar-saludo --version v0.1.0 [--catalogo oficial|<repo>] [--seco]
telar modulos catalogo [--buscar X]         # lo que hay en los catálogos
telar modulos instalar saludo               # del catálogo, en la versión que dice el catálogo
telar modulos activar|desactivar saludo     # encenderlo o apagarlo sin desinstalarlo
telar modulos actualizar saludo             # a la versión nueva del catálogo
```

Lo mismo, en la página: ⚙ → módulos (instalados y disponibles).

## `modulo.toml`

```toml
nombre = "saludo"                       # el de su orden: `telar saludo …` (si no, el del repositorio sin telar-)
descripcion = "Saluda, para probar."    # una frase: es lo que se lee en el catálogo
icono = "icono.png"                     # opcional: PNG cuadrado (512 px), el de su pestaña instalada como app

[ordenes.hola]                          # `telar saludo hola [args…]`, con la terminal
descripcion = "un saludo"
comando = ["python3", "bin/hola.py"]    # relativo a su carpeta
consulta = true                         # también sin terminal: un objeto JSON entra y otro sale (la página, el bus)

[pestana]                               # una pestaña del dashboard: un comando que imprime una página
nombre = "saludo"
comando = ["bin/saludo", "pagina"]
# dentro = "proyectos"                  # o una subpestaña de una fija: ahora, tareas, proyectos, calendario

[configurar]                            # su pantalla de configuración, en ⚙ módulos y en el ⚙ del título de su pestaña:
comando = ["bin/saludo", "configurar"]  # imprime una página, como [pestana]; su lienzo cambia lo suyo con sus consultas

[fechas]                                # una fuente de fechas (telar fechas): imprime fechas en JSON, corre aquí
comando = ["bin/saludo", "fechas"]
# escribir = ["bin/saludo", "mover"]    # opcional: cómo cambia una (recibe el cambio en JSON; telar fecha)

[app]                                   # algo que se abre en el panel: pagina, archivo o url
archivo = "dist/app.html"

[periodicos.bajar]                      # corre donde viven los periódicos, como cron
cuando = "30 7 * * *"
comando = "bin/saludo bajar"

[resultado]                             # lo que el periódico deja por día
carpeta = "~/.local/state/saludo"

[instalar]                              # lo que corre al instalarlo y al actualizarlo, en su carpeta
comando = ["python3", "-m", "venv", ".venv"]

[fondo]                                 # un fondo para la terminal de los hilos (⚙ terminal, [terminal] fondo)
archivo = "web/fondo.html"              # una página de su carpeta: se dibuja detrás de la terminal, aislada (un iframe
nombre = "estrellas"                    # sin el origen de la página: no la ve, ni a la API) y sin clics

[contexto]                              # lo que el agente de cada hilo sabe de él al arrancar: una o dos líneas
texto = "El módulo saludo: `telar saludo hola`."

[requiere]                              # lo que tiene que haber en la máquina
programas = ["uv"]

[objetos.saludo]                        # un tipo de objeto: saludo:<id>, con sus consultas
ver = "hola"
# esperando = "pendientes"              # opcional: una consulta suya que da los suyos que esperan a la persona
                                        # (telar esperas; la forma, en configuracion.md, «tipos de objeto»)
# listar = "todos"                      # opcional: una consulta suya que da todos los suyos
                                        # (telar objeto saludo --listar, GET /objetos/saludo; y son
                                        # una fuente de telar buscar y de Todo)
# plural = "saludos"                    # opcional: cómo se llaman juntos en una lista

[permisos]                              # lo que pide fuera de su carpeta (obligatorio para un catálogo)
leer = ["~/datos"]                      # rutas que lee (o una frase: "los repositorios de [repos]")
escribir = ["~/.local/state/saludo"]    # rutas que escribe
red = ["example.org"]                   # los sitios a los que se conecta; true: cualquiera; false: ninguno
ordenes = ["mensaje"]                   # las órdenes de telar que corre
```

Todo es opcional salvo `descripcion`. Las rutas relativas son de su carpeta. Las órdenes reciben en el entorno
`TELAR_RAIZ`, `TELAR_REPOS` (los repos de `[repos]`, en JSON), `TELAR_MAQUINA`, `TELAR_MODULO` (su carpeta) y
`TELAR_PERSONA` (la del entorno, `[bus] persona` o el usuario), y también los comandos de su `[pestana]`, su `[app]`, su
`[configurar]` y sus periódicos: la página sabe dónde está la raíz y los repositorios sin preguntárselo a `telar
config`. Una consulta que no se puede hacer sale con 1 e imprime `{"error", "codigo"}`: un 4xx (409: cambió desde que
se leyó) le llega así a quien la pidió; otra cosa es una falla del módulo (502).
`[permisos]` es una promesa: telar todavía no la hace cumplir, la muestra antes de instalarlo y dice si cambió al
actualizar. Sin la tabla, el módulo «no dice qué pide», que no es lo mismo que la tabla vacía («nada fuera de su
carpeta»).

**Su página.** La de su pestaña, su app o su configuración es casi siempre un lienzo: un HTML aislado y sin red
([contratos.md](contratos.md), «telar seccion»). Desde ahí le pide a telar con `window.lienzo.pedir(orden, datos)`:
sus propias consultas (`consulta`), el menú de una entidad (`menu`), abrirla en la página (`abrir`, con
`{direccion: "tarea:T84"}`: lo mismo que un clic en un enlace a esa dirección) o la ventana de la instrucción con lo
que muestra como contexto (`instruccion`, con `{contexto, destino?, texto?}`: un chat, para que un agente lo procese),
sin pedir permiso; lo que cambia tus documentos (`fecha`, `idea`), con el permiso de la persona.

**Su pestaña, como app.** `/pestana/<nombre>/` (en la página de telar) es la página con solo esa pestaña, sin la
cabecera ni la lista de hilos, y con un manifiesto propio: en el teléfono, Chrome la instala aparte de telar
(⋮ › «Instalar app»), con el nombre de la pestaña y el `icono` del módulo. El ícono se usa entero y recortado
(maskable): el dibujo, en el 80% del centro, sobre un fondo que llene el cuadrado. Sin `icono`, el de telar.

## `.telar/catalogo.toml`

El mismo nombre y la misma forma en cualquier repositorio: el oficial
([`nicorivas/telar-modulos`](https://github.com/nicorivas/telar-modulos)), el de un equipo (en el repositorio del
equipo) o cualquier otro.

```toml
version = 1                                       # la del formato

[modulos.saludo]
descripcion = "Saluda, para probar."
fuente = "https://github.com/ana/telar-saludo"    # su repositorio git
version = "v0.1.0"                                # una etiqueta o un commit, nunca una rama
autor = "ana"
etiquetas = ["prueba"]
telar = ">=0.6"                                   # la versión mínima de telar (opcional)

[modulos.saludo.permisos]                         # lo que pide, igual que en su modulo.toml (opcional)
red = ["example.org"]
```

`version` apunta a una etiqueta o a un commit: lo que se instala es lo que se revisó, no lo último de la rama.
`permisos`, si va, tiene que decir lo mismo que el `modulo.toml` de esa versión (`telar modulos revisar --catalogo
… --resolver` lo comprueba).

## De dónde se leen, y cuánto se confía en cada uno

| catálogo | dónde | en la página |
|---|---|---|
| el oficial | `nicorivas/telar-modulos`, con caché de una hora (`↻ buscar ahora` lo baja ya) | «revisado»: se instala con un clic |
| el de un equipo | el `.telar/catalogo.toml` de cada repo de `[repos]` (y de la raíz) | «del equipo»: se instala con un clic |
| otros | `[catalogos] fuentes` (una URL o una ruta) | «sin revisar»: solo desde la terminal |

```toml
[catalogos]
oficial = true                                    # false: no leer el oficial
fuentes = ["https://example.org/.telar/catalogo.toml"]
```

Un nombre que aparece en dos catálogos queda con el primero (el oficial, después los de los repos, después los
otros), y se dice. Un módulo suelto (`telar modulos instalar <url>`) también es «sin revisar».

## Publicar en un catálogo

`telar modulos publicar` revisa el módulo, etiqueta la versión (si no lo está) y la sube, arma su entrada y abre un
PR al repositorio del catálogo con `gh`: el oficial, o el de un repo de `[repos]` (`--catalogo faro`). Si el
módulo ya estaba, la entrada se reemplaza y el PR muestra la de antes. En el oficial, la revisión del PR baja el
módulo en esa versión y comprueba su manifiesto (`telar modulos revisar --catalogo .telar/catalogo.toml
--resolver`); después lo lee quien mantiene telar y lo mergea, o no.

Una versión nueva es otra etiqueta y otro `publicar`. Quien lo tenga instalado ve «actualizar a vX.Y.Z» en ⚙
módulos, y al actualizar, si lo que pide cambió, se lo dice.
