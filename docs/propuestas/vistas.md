# Vistas

Estado: **primer paso hecho** (22-oct-2026): la configuración lee `[vistas.<clave>]` y lo traduce, al leerla, a
lo de hoy (`[bloques]`, `[apps]`, `[secciones]`, `[resultados]`), que se sigue leyendo; un nombre en las dos
formas es un error, y `telar doctor` sugiere la forma nueva. **Por decidir**: las preguntas de abajo, las vistas
de un objeto y cómo la declara un módulo. Es el paso 6 de [primitivas.md](primitivas.md).

## Por qué

Hoy hay cuatro tablas para una misma idea, «mostrar algo en el dashboard»:

| tabla | qué muestra | dónde aparece |
|---|---|---|
| `[bloques.x]` | la página que imprime un comando | una pestaña del dashboard, o arriba del plan (`en = "plan"`) |
| `[apps.x]` | la página de un comando, un HTML autocontenido o una url | bajo **APPS**, en la barra |
| `[secciones.x]` | un grupo de hilos y, si quiere, la página de un comando (`home`) | un grupo en la lista de hilos |
| `[resultados.x]` | lo que una skill deja por día en una carpeta | donde la página lo pide por su clave (el plan pide `plan`) |

Cada una nombra la fuente a su manera (`comando`, `pagina`, `home`) y una usa `en` para decir el lugar
mientras las demás tablas de telar lo usan para decir la máquina. Quien quiere mover una página de una pestaña
a la barra tiene que cambiar de tabla y de clave. primitivas.md lo junta en una pieza, la **vista**: qué se
muestra y dónde aparece.

## Qué es y cómo se declara

Una vista es **una fuente** (de dónde sale lo que se muestra) y **un lugar** (`aparece`). La clave de la tabla
es su nombre, el mismo que hoy usan los atajos (`[atajos.x] en = "correo"`, `en = "seccion:diario"`) y la API
(`telar bloque correo`, `telar app vivero`, `telar resultado plan`).

```toml
[vistas.correo]                      # una pestaña del dashboard
aparece = "pestana"
comando = ["mi-correo", "--json"]
color = "rojo"
tecla = "e"

[vistas.retro]                       # arriba del plan del día, solo cuando trae algo
aparece = "plan"
comando = ["mi-retro"]

[vistas.vivero]                      # una app: un HTML autocontenido
archivo = "~/proyectos/vivero/vivero.html"
memoria = "~/.local/state/vivero.json"

[vistas.atlas]                       # una app: una página servida
url = "http://servidor:8790"

[vistas.juego]                       # una app que arma un comando
aparece = "apps"
comando = ["~/juego/casa"]

[vistas.diario]                      # un grupo en la lista de hilos, con su página
hilos = ["notas", "rato*"]
comando = ["mi-diario", "--json"]

[vistas.plan]                        # lo que una skill deja por día
carpeta = "~/notas/planes"
en = "servidor"
comentar = ["~/bin/plan-comentario"]
```

**Las fuentes.** Una sola de `comando` (imprime el JSON de una página, el contrato de `telar seccion`),
`archivo` (un `.html` autocontenido, con `memoria` si guarda), `url` (una página servida), o `carpeta`/`en`
(un `AAAA-MM-DD.json` por día; `en` es la máquina donde vive). `hilos` no es una fuente: dice qué hilos agrupa.

**Los lugares** (`aparece`):

| `aparece` | qué es hoy | claves que acepta, además de `nombre` |
|---|---|---|
| `pestana` | un `[bloques.x]` | `comando` (obligatorio), `color`, `tecla` |
| `plan` | un `[bloques.x]` con `en = "plan"` | las mismas |
| `apps` | un `[apps.x]` | una de `comando`, `archivo` o `url`; `descripcion`; `memoria` con `archivo` |
| `hilos` | un `[secciones.x]` | `hilos`; `comando` si tiene página (su `home`) |
| `dia` | un `[resultados.x]` | `carpeta` y/o `en`, `comentar` |

`aparece` se puede callar cuando las claves dejan un solo lugar: `archivo` o `url` son una app, `hilos` es un
grupo de hilos, `carpeta` o `en` es un resultado por día. Con `comando` solo, que sirve en cuatro lugares, se
dice siempre.

**Qué reemplaza.** Cada clave de antes tiene su par:

| antes | ahora |
|---|---|
| `[bloques.x] comando`, `en = "plan"` | `[vistas.x] comando`, `aparece = "plan"` (sin `en`: `aparece = "pestana"`) |
| `[apps.x] pagina` | `[vistas.x] aparece = "apps"`, `comando` |
| `[apps.x] archivo`, `url`, `memoria`, `descripcion` | las mismas |
| `[secciones.x] hilos`, `home` | `[vistas.x] hilos`, `comando` |
| `[resultados.x] carpeta`, `en`, `comentar` | las mismas, con `aparece = "dia"` si se quiere decir |

`en` queda con un solo sentido, el de las demás tablas: la máquina donde vive la fuente.

## Cómo convive con lo de hoy

- **Se traduce al leer.** `telar.config` arma, con cada `[vistas.x]`, la entrada de la tabla de antes y la pasa
  por la misma validación. Lo que sale es la misma `Config` que daría la forma de antes: `cfg.bloques`,
  `cfg.apps`, `cfg.secciones` y `cfg.resultados` no cambian, así que el resto de telar (las órdenes, la API, la
  página, `telar config --json`) no se entera. Las pruebas comparan cada forma de antes con su equivalente.
- **Las tablas de antes se siguen leyendo**, sin aviso al cargar. `telar doctor` dice cuáles quedan y escribe
  la `[vistas.x]` que las reemplaza.
- **Un nombre en las dos formas es un error**: `[vistas.correo]` y `[bloques.correo]` no se juntan ni se
  adivina cuál gana. Lo mismo un módulo que aporta algo con el nombre de una vista.
- **El orden.** En cada lugar van primero las de antes, después las vistas, en el orden del archivo, y al final
  lo de los módulos. Quien pasa todo a `[vistas]` tiene el orden de sus vistas.
- **Los errores nombran la vista** (`vistas.correo.color: …`), no la tabla a la que se tradujo.
- **Los módulos siguen igual** por ahora: `modulo.toml` declara `[pestana]`, `[app]` y `[resultado]`.
- **Las órdenes siguen igual**: `telar bloque`, `telar app`, `telar seccion` y `telar resultado`.

## Las decisiones abiertas

Cada una con la opción que tomé por ahora y por qué.

1. **Cómo se llama el lugar.** Elegí `aparece`. `en` ya dice «en qué máquina» en `[tipos]`, `[notas]`,
   `[agentes]` y `[resultados]`, y `[bloques]` lo usaba para el lugar: dos sentidos para una clave. Otra opción
   era `lugar`, pero esa palabra ya es una pieza del plan (el nodo, la carpeta y la rama de un hilo).
2. **`aparece` con `comando`: ¿obligatorio o por defecto `pestana`?** Obligatorio. Un mismo comando sirve de
   pestaña, de bloque del plan, de app o de página de un grupo; adivinar lo pondría en un lugar que nadie
   pidió, sin error. Con las otras fuentes no hay que decirlo porque no hay dónde equivocarse.
3. **¿Los resultados por día son vistas?** Por ahora sí (`aparece = "dia"`), porque el plan lo pide y así
   `[resultados]` también se retira. Pero un resultado es más un dato que un lugar: no aparece en ningún sitio
   por sí solo, la página lo pide por su clave. La otra opción es volverlo un tipo de objeto (`resultado:plan`,
   con `ver` por día y `comentar` como acción) y que la vista del plan lo muestre. Si se elige eso, `dia`
   se queda como alias.
4. **¿Un grupo de hilos es una vista?** Sí (`aparece = "hilos"`): es una colección (los hilos que calzan)
   mostrada en un lugar, con su página opcional. Es la única con algo que no es fuente (`hilos`), que más
   adelante podría ser un filtro sobre objetos `hilo:`.
5. **El nombre «vista».** En telar ya se llaman «vistas» las sesiones agrupadas de tmux (`ver-…`) y las
   pestañas de un hilo en la página (`vistas-hilo.ts`). Lo dejé así porque es la palabra del plan y en la
   configuración no hay confusión, pero los documentos tendrán que decir cuál de las tres.
6. **El orden cuando se mezclan.** Primero las de antes y después las vistas. La otra opción era el orden en
   que aparecen en el archivo, mezclando tablas, pero `tomllib` no guarda el orden entre tablas distintas.
7. **Cuánto se leen las tablas de antes.** Sin fecha: hasta una versión que lo anuncie en el CHANGELOG, después
   de que `telar doctor` lleve un tiempo avisando. Retirarlas antes rompería configuraciones de gente que
   instaló desde PyPI.
8. **`en` (la máquina) con un `comando`, un `archivo` o una `url`.** Por ahora no vale: hoy ninguna de esas
   fuentes corre en otra máquina. Cuando una lo haga, la clave ya tiene nombre.
9. **Escribirlo solo.** `telar doctor` muestra la vista nueva, pero no reescribe el archivo. Un `telar doctor
   --arreglar` (o `telar config --migrar-vistas`) que cambie las tablas por sus vistas, conservando los
   comentarios, es fácil con lo que ya hace `escribir_clave`, pero toca la configuración de alguien y prefiero
   que lo pida.

## Lo que queda

- **Las vistas de un objeto**: cómo se muestra un `tarea:`, un `encargo:` o un objeto de un módulo (una página
  declarativa o una app aislada, según primitivas.md), con `muestra = "<tipo>"` en vez de una fuente.
- **Los módulos**: que `modulo.toml` declare `[vistas.x]` (una o varias) y que `[pestana]`, `[app]` y
  `[resultado]` se traduzcan igual.
- **Una sola orden**, `telar vista [clave]`, con `bloque`, `app`, `seccion` y `resultado` como alias.
- **La configuración en la forma nueva** en `telar config --json` y `GET /config` (un campo `vistas`), para que
  la página deje de leer cuatro listas. Hoy salen las cuatro de antes.
- **Escribir la migración** (decisión 9) y retirar las tablas de antes (decisión 7).
