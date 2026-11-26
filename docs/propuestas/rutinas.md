# Rutinas: lo que se repite, con la prueba de que se hizo

Estado: **prototipo** en el catálogo (`/componentes#rutinas`, 26-nov-2026), con rutinas inventadas. No hay modelo de
datos todavía. Esto es lo que se propone, para que la persona lo mire antes de construir; nada está decidido.

## Por qué

Una gerencia, y una vida, tienen cosas que se repiten: el plan del día, la revisión del tablero los lunes, los 1:1
cada dos semanas, el diagnóstico de cada mes. Lo difícil no es acordarse de que existen: es saber, una mañana
cualquiera, cuáles se hicieron y cuáles se están cayendo. Seguir eso a mano es otra tarea más, y se abandona.

La idea: **cada rutina dice con qué prueba se sabe que se hizo**, y la vista lo calcula. El plan del día deja un
archivo; la reunión de líderes, su minuta; el resumen comercial, una tarea cerrada. Si la prueba está, la rutina está
al día sin que nadie marque nada. Lo que no deja prueba se marca a mano, y es la excepción, no la regla.

No es una lista de tareas: una tarea se hace una vez y se cierra; una rutina vuelve. Tampoco es el calendario: el
calendario dice cuándo hay reunión, no si quedó la minuta.

## Qué es una rutina

| campo | qué dice | ejemplo |
| --- | --- | --- |
| `nombre` | cómo se llama | Plan del día |
| `cada` | cada cuánto | `día hábil`, `lunes`, `14 días`, `mes`, `trimestre`, `calendario "Daily del área"` |
| `quien` | quién la hace | `yo`, una persona (`Leo`), un agente (`agente:Analista`) |
| `prepara` | lo que la deja lista, si hay | `periodico:planear`, `skill:preparar-reunion` |
| `prueba` | con qué se sabe que se hizo; sin esto, se marca a mano | `archivo planes/{fecha}*.md` |
| `area` | de qué parte de la vida es (el mundo, como las tareas) | `trabajo` |
| `desde` | desde cuándo rige: antes no se le pide prueba | 2026-11-01 |

Más abajo, qué es, en prosa, y una `## Historia` que solo crece por el final: las marcas a mano y los cambios.

## El archivo

Un archivo por rutina, como las tareas del tipo `tarea` (`docs/arquitectura.md`, «Los tipos»): arriba una clave por
línea, sin YAML; un campo vacío no se escribe; lo que el formato no reconoce se conserva.

```markdown
---
nombre: 1:1 con Leo
cada: 14 días
quien: yo
prepara: skill:preparar-reunion
prueba: cita "1:1 Leo" y nota personas/leo.md
area: trabajo
desde: 2026-11-17
---
Cada dos semanas. La nota de la ficha dice lo conversado y lo que quedó.

## Historia
- 2026-11-17 [creada] desde el método de gerencia
```

Una sin prueba, con sus marcas:

```markdown
---
nombre: Revisión semanal
cada: viernes
quien: yo
---
Mirar la semana entera: qué se cumplió, qué se mueve.

## Historia
- 2026-11-13 [hecha] a mano
- 2026-11-20 [hecha] a mano
```

## Dónde vive

Cada repositorio declara su carpeta de rutinas en `.telar/rutinas.yaml` (como `.telar/registro.yaml` o
`.telar/tablero.yaml`), y telar junta las de todos:

```yaml
carpeta: operacion/rutinas     # un <slug>.md por rutina
```

Lo abierto de un equipo (la daily, la revisión del tablero, el resumen comercial) va en el repositorio del equipo,
que todos ven. Lo de una persona (su plan del día, sus 1:1, su retro) va en el suyo. Un 1:1 es de quien lo lleva: la
rutina vive en el repositorio de esa persona, aunque la cita sea de dos.

## Las pruebas

Cada clase de prueba es un comprobador: dado el texto de `prueba`, la cadencia y un rango de fechas, dice en qué días
hay prueba. La vista se queda con la última. Lo de la máquina se lee donde viven los archivos (como las tareas,
`en`), sin salir de ella; lo de afuera (el calendario) pasa por su proveedor.

| clase | se escribe | cuenta como hecha el día que… |
| --- | --- | --- |
| `archivo` | `archivo planes/{fecha}*.md` | existe un archivo que calza; `{fecha}` es AAAA-MM-DD, `{semana}` AAAA-Wnn, `{mes}` AAAA-MM |
| `minuta` | `minuta reuniones/` | hay una minuta de la reunión de ese día en esa carpeta (por su fecha) |
| `cita` | `cita "1:1 Leo"` | el calendario tiene un evento pasado que calza, al que la persona fue; con `y nota <archivo>`, además el archivo tiene una línea de ese día |
| `resultado` | `resultado planear-semana` | `telar resultado <clave>` tiene el de ese día |
| `tarea` | `tarea #resumen-comercial` | se cerró como hecha una tarea con esa etiqueta |
| `linea` | `linea bitacora.md` | el archivo tiene una línea con esa fecha |
| `comando` | `comando ["horas", "--sello"]` | el programa dice esa fecha (para lo que vive en otro sistema: un sello en una planilla) |

Una prueba puede ser débil, y se dice: que exista el archivo de la semana del tablero no prueba que alguien lo leyó.
La rutina lo anota en su prosa; la vista no lo oculta.

## El estado

De la última prueba y la cadencia sale **cuándo vuelve a tocar**: el día hábil siguiente, el próximo día de la semana
que le toca, N días o meses después; con `calendario`, la próxima reunión de su serie que todavía no tiene su prueba.
Contra hoy:

- **atrasada**: le tocaba antes de hoy;
- **toca hoy**;
- **esta semana**: le toca antes del domingo (lo de cada día, hecho hoy, está al día: mañana no es «esta semana»);
- **al día**: le toca después;
- **sin prueba definida**: no dice su prueba, y la vista no calcula; es la única que se marca a mano.

Antes de `desde` no se pide nada: una rutina nueva no nace atrasada.

## Marcar a mano

Solo donde no hay prueba. El ✓ deja `- AAAA-MM-DD [hecha] a mano` en su historia, y esa línea hace de prueba. Una
rutina con prueba no ofrece el ✓: si la prueba no aparece, lo que falta es la prueba (la minuta, el archivo), no la
marca. Si la prueba elegida no sirve, se cambia la prueba.

## La vista y la orden

- **`tareas › rutinas`**: una subpestaña de tareas, tras foco, lista y esperando, con la barra, el buscador y los
  filtros estándar (quién: tuyas, de otros, de agentes). Una sección por estado; al día, plegada. Cada fila: el estado
  en su círculo, quién la hace, el nombre y cada cuánto, cuándo vuelve a tocar y cuándo se hizo; debajo, tenue, su
  prueba y qué la prepara. Al pasar el mouse: ver la prueba, correr lo que la prepara y, si no tiene prueba, marcarla.
  El prototipo, en `/componentes#rutinas` (`pagina/src/componentes/catalogo-rutinas.ts`).
- **`telar rutinas [--json]`**: las mismas, con su estado; `telar rutina marcar <slug>` y su dirección
  (`rutina:<repo>/<slug>`), para que un agente las lea y Táctica cuente las atrasadas.

## Cómo encaja

Un **tipo** `rutina` (`telar.tipos`, como `tarea`): el modelo, sus acciones (marcar, editar) y su formato, con las dos
promesas de todo formato (leer y escribir sin cambios da los mismos bytes; un cambio toca solo sus líneas). Los
comprobadores, uno por clase, en el núcleo los que leen archivos y en sus proveedores los de afuera. No hace falta una
base aparte: las pruebas ya existen (las minutas, los planes, las tareas); la rutina solo dice dónde mirarlas.

## Lo que falta decidir

1. **Dónde vive cada rutina de la instancia**: el catálogo inicial (el inventario de la gerencia) mezcla lo del
   equipo y lo de la persona; hay que repartirlo.
2. **Las que no tienen prueba todavía** (la retro del día, la revisión semanal, la de decisiones, la trimestral): cuál
   se define, cuál se marca a mano y cuál se deja.
3. **La cita como prueba**: si basta con que el evento haya pasado, o hace falta la nota.
4. **Las de otros**: si las rutinas que hace otra persona (sus 1:1, su revisión) se ven aquí, o solo las que la
   persona lleva.
5. **Si «toca hoy» cuenta la hora**: una reunión a las 15:00 toca hoy en la mañana; a las 16:00 sin minuta, ¿ya está
   atrasada o se espera al día siguiente?

## Pasos

1. El tipo `rutina` y su formato, con las pruebas de bytes.
2. Los comprobadores locales (`archivo`, `linea`, `resultado`, `tarea`) y la marca a mano.
3. `telar rutinas` y la vista de verdad (el prototipo, con datos).
4. Los de afuera: `cita` y `minuta` con el calendario, `comando`.
5. El catálogo de la instancia, en sus repositorios.
