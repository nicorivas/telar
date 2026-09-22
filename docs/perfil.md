# El perfil del repositorio

**telar no sabe qué es un proyecto.** Es a propósito: en un repositorio un proyecto
es una carpeta con README, en otro es un archivo, en otro es una fila de una tabla.
Un programa que lo decida por todos sirve para uno solo.

Lo decide el repositorio de trabajo, en un `telar-perfil.yaml` en su raíz. El perfil
viaja con el repositorio, se versiona con él, y cualquier telar que lo abra teje lo
mismo. Sin perfil, rige la [convención mínima](#sin-perfil-la-convención-mínima).

Un perfil declara tres cosas:

1. **arquetipos** — qué carpetas o archivos son unidades de trabajo, y qué se lee de
   cada una;
2. **secciones** — qué partes del documento son legibles, y cómo;
3. **acciones** — qué ofrece el repositorio hacer sobre un hilo.

## El archivo entero

```yaml
version: 1              # el esquema; hoy solo existe la 1
nombre: taller          # para decirlo en la interfaz; opcional

arquetipos:

  proyecto:                          # el nombre del arquetipo es la llave
    descripcion: Un encargo con carpeta propia.
    ruta: "proyectos/*/"             # glob relativo a la raíz; la barra final importa
    documento: README.md             # el archivo que se parsea, dentro de la carpeta
    secciones:
      titulo:
        tipo: linea
        encabezado: '^#\s+(.+)$'     # el grupo 1 es el valor
      estado:
        tipo: parrafo
        encabezado: '^##\s+Estado'
        requerida: true
      pendientes:
        tipo: casillas
        encabezado: '^##\s+Pendientes'
        maximo: 6

  nota:
    ruta: "notas/*.md"               # sin barra final: cada coincidencia ES el documento
    documento: "."
    secciones:
      titulo: { tipo: linea, encabezado: '^#\s+(.+)$' }

acciones:
  - nombre: revisar
    descripcion: Repasa el proyecto del hilo.
    comando: ["make", "revisar"]     # lista de palabras, nunca una línea de shell
    tecla: r                         # sugerencia para la interfaz; opcional
    donde: hilo                      # hilo (la carpeta del hilo) | raiz
    confirmar: false                 # si es true, la interfaz pregunta antes
```

Hay uno completo y comentado en [`ejemplo/telar-perfil.yaml`](../ejemplo/telar-perfil.yaml).

## Arquetipos

Un arquetipo es una **forma** de unidad de trabajo. Un repositorio puede tener
varias: proyectos, notas, clientes.

| Clave | Obligatoria | Qué es |
|---|---|---|
| `ruta` | sí | glob relativo a la raíz. **Si termina en `/`**, cada coincidencia es una carpeta y el documento es `documento` adentro. Si no, cada coincidencia es el documento mismo. |
| `documento` | no (`README.md`) | el archivo que se parsea, dentro de la carpeta |
| `descripcion` | no | una línea, para que la interfaz pueda decir qué es esto |
| `etiqueta` | no (el título) | cómo se llama una unidad en pantalla: `{titulo}` y `{campo:Clave}`, una fila de la tabla de campos. Ver abajo. |
| `secciones` | no | qué se lee del documento |

La ruta tiene que ser relativa y no salir de la raíz: un `..` o un `/` inicial es
un error. telar solo lee dentro del repositorio que lo invitó.

**El orden en que se declaran importa dos veces.** Cuando dos rutas calzan con dos
arquetipos, gana el primero que se declaró —por eso «proyecto cerrado» va antes que
«área de conocimiento» si `conocimiento/proyectos/` calza con los dos—. Y cuando
`telar tejer` tiene que elegir cuáles ocho unidades abre de las que haya, abre las del
primer arquetipo antes que las del segundo. Un repositorio con ciento setenta y nueve
unidades declara así qué es lo que trabaja: el arquetipo de arriba es el que se ve al
entrar.

### El nombre en pantalla

El nombre de un hilo es la llave con que telar lo recuerda —su carpeta, su conversación,
si está archivado— y por eso es el de la carpeta: estable y sin espacios. Lo que se
*lee* en la lista puede ser otra cosa, y lo declara el arquetipo:

```yaml
proyecto:
  ruta: "operacion/proyectos/*/"
  etiqueta: "{campo:Cliente} · {titulo}"    # «Grupo Anasac · Adopción IA»
```

De un campo queda solo el nombre: sin lo que va entre paréntesis y cortado en la
primera raya, coma o punto y coma. Si un valor ya está dentro de otro no se repite (con
el título «AquaChile — Campaña de Ideas», el cliente «AquaChile» sobra), y un marcador
vacío se lleva su separador. Sin `etiqueta`, se muestra el título del documento.

## Secciones

Una sección dice **dónde** está algo (`encabezado`) y **qué forma** tiene (`tipo`).

| `tipo` | Devuelve |
|---|---|
| `linea` | una línea. Si el `encabezado` tiene un grupo de captura, el valor es ese grupo: así el título sale del propio encabezado. Si no, la primera línea del cuerpo. |
| `parrafo` | el primer párrafo de texto del cuerpo, con los saltos unidos |
| `texto` | el cuerpo entero, tal cual |
| `lista` | las viñetas del cuerpo, en orden |
| `casillas` | las viñetas con casilla: `[ ]` pendiente, `[x]` hecha, `[>]` en curso |
| `tabla` | las filas `\| clave \| valor \|` del cuerpo, como diccionario |

| Clave | Por defecto | Qué es |
|---|---|---|
| `tipo` | `texto` | de la tabla de arriba |
| `encabezado` | — | expresión regular contra la línea del encabezado. **Sin ella la sección no está anclada**: se busca lo primero del documento que calce con el tipo |
| `maximo` | `0` (sin tope) | tope de elementos, para los tipos que devuelven varios |
| `requerida` | `false` | si falta, el documento no cumple lo que su repositorio prometió, y telar lo dice |

### Los tres nombres que telar entiende

El nombre de una sección es libre, pero tres significan algo:

| Nombre | telar lo usa para |
|---|---|
| `titulo` | cómo se llama el hilo cuando no tiene nombre propio |
| `estado` | la línea que se muestra bajo cada hilo |
| `pendientes` | lo que queda por hacer, con su marca de hecho / en curso |

Todo lo demás se lee y se guarda igual, y lo dibuja quien sepa qué significa. Un
`esperando` o un `ficha` valen lo mismo para telar: datos con nombre.

### La regex es contra el encabezado, no contra el cuerpo

`encabezado` calza la **línea del título de la sección**; el cuerpo es lo que va
desde ahí hasta el próximo encabezado del mismo nivel o mayor. Por eso
`'^##\s+Estado'` toma la sección entera y no solo esa línea, y por eso
`'^##\s+Estado(?! anterior)'` sirve para saltarse una sección vecina que empieza
igual.

## Acciones

Lo que el repositorio ofrece hacer sobre un hilo. telar no adivina órdenes: corre
las declaradas, y ninguna otra.

| Clave | Obligatoria | Qué es |
|---|---|---|
| `nombre` | sí | cómo se la llama (`telar accion revisar`) |
| `comando` | sí | **lista de palabras**, no una línea de shell |
| `descripcion` | no | una línea |
| `tecla` | no | una letra, sugerencia para la interfaz |
| `donde` | no (`hilo`) | el `cwd`: `hilo` (la carpeta del hilo) o `raiz` |
| `confirmar` | no (`false`) | si la interfaz pregunta antes de correrla |

El comando es una lista porque así no hay shell en el medio, y sin shell en el
medio no hay una carpeta con comillas en el nombre convertida en dos argumentos, ni
un `;` de alguien convertido en otra orden. Si de verdad hace falta una shell, se
pide explícita: `["sh", "-c", "…"]`, a la vista.

Marcadores que telar reemplaza en cada palabra: `{ruta}` (la carpeta del hilo),
`{hilo}` (su nombre), `{documento}` (el archivo parseado).

## Sin perfil: la convención mínima

Un repositorio sin `telar-perfil.yaml` no queda fuera: rige el **perfil de casa**, que
cubre las tres formas en que la gente guarda su trabajo, sin pedirle que declare nada.

```yaml
arquetipos:
  proyecto:           { ruta: "*/",        documento: README.md }   # carpetas de la raíz
  proyecto anidado:   { ruta: "*/*/",      documento: README.md }   # proyectos/…, projects/…
  repositorio:        { ruta: "README.md" }                         # un repo, un proyecto
```

Los tres leen lo mismo, y sin anclar, porque sin perfil no se sabe cómo titula este
repositorio sus secciones:

```yaml
    secciones:
      titulo:     { tipo: linea, encabezado: '^#\s+(.+)$' }
      estado:     { tipo: parrafo }                # el primer párrafo
      pendientes: { tipo: casillas, maximo: 6 }    # la primera lista de casillas
```

Es el `telar.perfil.PERFIL_MINIMO`. Sirve para el primer día en cualquier carpeta; el
perfil propio se escribe cuando eso ya no alcanza —y `telar init --perfil` lo propone
mirando el repositorio: qué rutas tienen README y con qué encabezados titula sus
secciones.

## Errores

Igual que la configuración: telar prefiere quejarse a adivinar. Una clave que no
existe en este documento, un `tipo` desconocido, una regex inválida, un `comando`
que es una cadena en vez de una lista, o una `ruta` que se sale de la raíz son
`ErrorDePerfil`, con la ruta de la clave en el mensaje (`arquetipos.proyecto.ruta:
…`). Un perfil a medias rompe todos los hilos a la vez, así que no se tolera a
medias.
