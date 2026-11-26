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
# buscador = true                       # opcional, con listar: también se buscan en ⌘K, en su grupo

[ventanas]                              # ventanas que pide abrir en la página cuando ocurre algo (abajo, «Sus ventanas»)
consulta = "pendientes"                 # una consulta suya: da las que quiere abrir ahora, con el mundo puesto
acciones = ["hola"]                     # las consultas que pueden correr sus botones (y nada más por este camino)

[permisos]                              # lo que pide fuera de su carpeta (obligatorio para un catálogo)
leer = ["~/datos"]                      # rutas que lee (o una frase: "los repositorios de [repos]")
escribir = ["~/.local/state/saludo"]    # rutas que escribe
red = ["example.org"]                   # los sitios a los que se conecta; true: cualquiera; false: ninguno
ordenes = ["mensaje"]                   # las órdenes de telar que corre
```

Todo es opcional salvo `descripcion`. Las rutas relativas son de su carpeta. Las órdenes reciben en el entorno
`TELAR_RAIZ`, `TELAR_REPOS` (los repos de `[repos]`, en JSON), `TELAR_MAQUINA`, `TELAR_MODULO` (su carpeta),
`TELAR_PERSONA` (la del entorno, `[bus] persona` o el usuario) y `TELAR_MUNDOS` (los de `[mundos]`, en JSON: `[{nombre,
etiquetas}]`, para que clasifique lo suyo por mundo), y también los comandos de su `[pestana]`, su `[app]`, su
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
sin pedir permiso; el menú de la página con sus opciones (`opciones`), también; lo que cambia tus documentos (`fecha`,
`idea`), con el permiso de la persona.

Un lienzo de pestaña puede abrirse en un ítem suyo cuando la página lo pide (la ventana de un chat de foco: «abrir el
chat»): lo recibe en `window.lienzo.item` si se pinta entonces, o como el evento `lienzo-item` (con el ítem en
`detail`) si ya estaba pintado. La dirección `pestana:<nombre>` abre la pestaña; el ítem lo pasa la página.

**Las pestañas y los filtros de telar.** Para que su página se vea y se maneje como las de telar sin copiar nada, un
lienzo pide los componentes de la página con `"componentes": true` ([contratos.md](contratos.md), «telar seccion»), y
arma con ellos sus filas: en la primera, sus vistas como pestañas; en la segunda, el buscador con sus filtros a la
derecha. Cada una del alto de una barra de telar, con su línea abajo de borde a borde:

```js
const C = window.lienzo.componentes;                 // undefined en un telar que no los tiene: dibujar lo de antes
if (C) cabecera.innerHTML =
    C.pestanas({ nombre: 'vistas', accion: 'vista', activa: vista,
        pestanas: [{ valor: 'lista', nombre: 'lista', icono: C.iconos.lista, cuenta: 12 },
                   { valor: 'tablero', nombre: 'tablero', icono: C.iconos.tabla }],
        fin: '<a class="pestana" data-accion="nueva">+ nueva</a>' })
  + C.barraBuscar({ placeholder: 'ideas', valor: texto, cuenta: { texto: '4 de 12' },
        herramientas: C.filtros({ accion: 'filtro', grupos: [
            { clave: 'area', nombre: 'área', plegado: true, activa: area || 'todas', siempre: 'todas',
              opciones: [{ clave: 'todas', nombre: 'todas' }, { clave: 'norte', nombre: 'norte', cuenta: 3 }] }] }) });
cabecera.addEventListener('click', e => {
    const t = e.target.closest('[data-accion]');
    if (t?.dataset.accion === 'vista') { vista = t.dataset.valor; pintar(); }
    if (t?.dataset.accion === 'filtro') { const [grupo, clave] = t.dataset.id.split(':'); /* filtrar */ }
});
```

Las props son las de la página (`pagina/src/componentes/pestanas.ts`, `buscador.ts` y `filtros.ts`, y su página en
/componentes). Lo que hacen solos, sin que el lienzo lo repita: las pestañas que no caben van a un «⋯» al dibujarse y al
cambiar el ancho (repintar la cabecera entera está bien: la fila nueva se acomoda sola), con su teclado (← → Inicio Fin
⏎); el ✕ del buscador lo borra y avisa con un `input`; el «⋯» y un grupo de filtros plegado abren el menú de la página
(`window.lienzo.pedir("opciones")`, que el lienzo también puede usar con `C.elegir(opciones, ancla, titulo)`), y lo elegido
le llega como el clic en esa pestaña o esa opción. Los íconos de los componentes van en la letra de la página
(`telar-iconos`); si el lienzo tiene su propia letra con su `.i`, que ponga `telar-iconos` de respaldo para usar
`C.iconos`. La hoja de los componentes entra antes que la del lienzo y sin capa: un estilo suyo para `input` o `a` le
gana a uno de los componentes si pesa igual, así que conviene acotarlo (`#cuerpo input`).

**La prosa de telar.** Un documento (el README de lo que muestra el lienzo) se lee en la misma prosa que el visor en
modo lectura y la lectura de un hilo (`media/css/prosa.css`): `await C.prosa(markdown, { ruta })` da su HTML, dentro de
un `.prosa.prosa-md`. El markdown lo dibuja la página como el visor (`window.lienzo.pedir("prosa", {markdown})`, sin
permiso: no cambia nada), así que markdown-it no va en cada lienzo; sin el frontmatter y sin HTML propio. `ruta` es la
del archivo, relativa a la raíz: sus enlaces relativos abren ese archivo en el visor de la página (uno a una carpeta, su
README), uno a un título (`#…`) baja hasta él, y uno de afuera no se sigue (el lienzo no tiene red). Con `version` 2 o
más; un telar que no lo dibuja da el texto tal cual, en la misma prosa.

Desplegar en este orden: primero telar, después el módulo. Un telar sin componentes ignora el campo, y el lienzo que
mira `window.lienzo.componentes` antes de usarlos dibuja lo de antes; un módulo viejo no los pide y queda igual.

**Sus ventanas.** Un módulo puede pedir que salga una ventana en la página cuando ocurre algo, esté donde esté la persona:
la de WhatsApp sale cuando llega un mensaje a un chat de foco, para responder o aplazar sin ir a su pestaña. `[ventanas]
consulta` es una consulta suya que dice qué ventanas quiere abrir **ahora**; la página le pregunta cada 10 s mientras está
a la vista (cada 3 s con una abierta, al volver a ella, al cambiar de mundo, y al tiro cuando otra pestaña de la misma
máquina hace algo), por `GET /ventanas` ([contratos.md](contratos.md)). Recibe `{"mundo": "trabajo"}` (el mundo puesto en
la página; `""` con ambos) y, en silencio, `{"solo_cuantas": true}`, y da:

```json
{ "cuantas": 1,
  "ventanas": [ {
    "id": "56911111111@s.whatsapp.net", "version": "3EB0A1:2", "mundo": "trabajo", "desde": "2026-11-23T10:42:00-03:00",
    "titulo": "Ana Rojas", "ayuda": "", "icono": "persona", "nuevos": 2,
    "lineas": [ { "de": "Ana Rojas", "ts": "2026-11-23T10:42:00-03:00", "texto": "¿Llegaste?", "marca": "", "nueva": true, "mia": false } ],
    "responder": { "verbo": "salida", "params": { "accion": "enviar", "chat": "…" }, "campo": "texto",
                   "placeholder": "responder a Ana…", "largo": 4000, "despues": { "verbo": "hola", "params": { "…": "…" } } },
    "acciones": [ { "texto": "aplazar 15 min", "icono": "aplazar", "corto": "15m", "tecla": "", "verbo": "hola", "params": { "por": "15m" } },
                  { "texto": "aplazar 1 h", "icono": "aplazar", "corto": "1h", "tecla": "1", "verbo": "hola", "params": { "por": "1h" } },
                  { "texto": "abrir el chat", "icono": "externo", "en": "cabecera", "abrir": "pestana:whatsapp", "item": "…" },
                  { "texto": "mandar a…", "icono": "instruccion", "en": "cabecera", "instruccion": { "verbo": "contexto", "params": { "…": "…" } } } ],
    "escape": 0 } ] }
```

- **Lo que muestra**: el título (con su ícono: `persona`, `grupo` o `aviso`), `nuevos` (cuántos llegaron, que pueden ser
  más que las líneas: junto al título, con el punto de no leídos y el número), una `ayuda` tenue si hace falta algo más
  (mejor nada: lo que se dice con un ícono no se escribe) y sus líneas: quién, cuándo y qué (`marca`, lo que va delante
  en otro color: «nota de voz 0:42»), las de antes tenues y las `nueva` bajo una raya con el punto de no leídos. Todo se
  escapa: lo que dicen las líneas lo dijeron otras personas.
- **`borradores`** (opcional): lo que alguien dejó para responder y espera que la persona lo apruebe (el borrador de un
  agente para ese chat): `{id, de, texto, motivo, sale, editable, aprobar: {verbo, params, campo, despues}, descartar:
  {verbo, params}}`. Se ve sobre la caja, con quién lo pidió y por qué; «enviar» (o «aprobar · sale a las 08:30», con
  `sale`) corre `aprobar` con lo editado en `campo` y después `despues` (aprobarlo es responder: la ventana se cierra), y
  «descartar», `descartar` (la ventana queda). ⌘⏎ escribiendo en uno lo aprueba a él. Aprobar es lo que el módulo diga:
  en WhatsApp, la aprobación de siempre de la pestaña, que sale firmada, en su horario y con su tope.
- **`responder`**: una caja de texto; ⌘⏎ (o «enviar») corre esa consulta con lo escrito en `campo`, después `despues`
  (si salió), y, si la respuesta trae `seguir` (`{verbo, params}`), la consulta cada 1,5 s hasta que su `seguimiento.estado`
  sea `hecho` o `falla` (con `error`): la ventana dice «enviando…», «enviado» o por qué no salió, y lo escrito vuelve a
  la caja.
- **`acciones`**: los botones, en el pie con su `tecla` (o en la `cabecera`, junto al título: lo que lleva a otra parte).
  Lo que se entiende por su ícono va como ícono: `icono` es un nombre de los de la página (`pagina/src/web/iconos.ts`:
  `aplazar`, la campana dormida; `externo`, abrir afuera; `instruccion`, mandarlo a un hilo o un agente; `sinFoco`, la
  mira tachada; `enviar`; `descartar`, el basurero), y entonces `texto` pasa a ser su nombre (se lee al pasar el mouse y
  lo lee un lector de pantalla) y se ve el ícono, tras su tecla en el pie; `corto`, lo poco que el ícono no dice, a su
  lado (el plazo: «15m»; hasta 12 letras). Un nombre que la página no conoce deja la palabra, como sin `icono`. Enviar y
  descartar un borrador, y enviar lo escrito, ya van con su ícono.
  Cada uno corre una consulta (`verbo`, `params`), abre una dirección (`abrir`, con `item` para su pestaña) o la ventana de
  la instrucción con lo que da una consulta (`instruccion`: `{texto, titulo}`); `despues`, si salió. Después, la ventana se
  cierra. `escape`: el botón que hacen ⎋ y un clic fuera (aplazar lo más corto: nunca «visto»); la celda lo dice con ⎋.
- **Solo lo declarado**: cada `verbo` tiene que ser `consulta` o uno de `acciones` de `[ventanas]`; si no, la ventana no
  sale (va a `fallas`). Lo que corre un botón llega por `POST /ventanas/accion`, que revisa lo mismo.
- **El estado es del módulo**: qué espera, lo respondido, lo aplazado. Lo que se hace en una página cierra la ventana en
  las demás cuando vuelven a preguntar; lo que llegó con la página cerrada sale al abrirla, una vez.
- **Los mundos**: el módulo da solo lo del mundo que se le dice (lo de `mundo` "" sale en todos) y telar descarta lo que
  diga ser de otro: lo de otro mundo no llega a la página, ni su nombre ni cuántas.
- **El silencio**: «no molestar» (el ícono de la campana en la banda, o ⌘K), por máquina, y solo durante una reunión del
  calendario en curso (una cita con otras personas que no se rechazó). Mientras, no sale ninguna y se pide solo cuántas
  esperan; al terminar, salen.
- **No roba teclas**: si se está escribiendo (una tecla hace menos de 1,5 s) o el foco está en un campo (una caja, la
  terminal, un lienzo), la ventana sale quieta, sin fondo y sin tomar el teclado; lo toma con un clic en ella, o sola
  cuando el foco sale de los campos y pasa un rato sin teclear.

Las abre `pagina/src/web/ventanas.ts` (sobre `abrirVentana`, con los botones de la casa) y las sirve
`telar.servicios.ventanas`.

Un tipo de objeto con `listar` y `buscador = true` se busca también en ⌘K, en su grupo (con su `plural`), con el mundo
puesto primero y lo de otro mundo fuera, como lo demás de ⌘K; abrirlo es su vista, con sus acciones. Un objeto que no
vive en un archivo dice su mundo en `campos.mundo`.

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
