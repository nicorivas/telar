# El arte de los mundos

La ventana de mundos (⌘M, un clic en el mundo de la banda, «cambiar de mundo» en ⌘K) muestra una tarjeta por mundo, y
arriba de cada una un dibujo de letras animado: su **arte**. Con el mouse o el foco encima, una ola de letras lo cruza: su
**efecto de hover**. Cada arte y cada efecto es un módulo aparte, y agregar uno no toca la ventana. Este documento dice cómo
se hace uno y cómo se elige.

## Qué arte lleva cada mundo

`[mundos.<n>] arte = "<clave>"` en la configuración de la máquina (o ⚙ mundos › arte, que escribe esa línea), como el
color y el tema. Sin la línea, el que le toca, en este orden:

1. el que se llama como el mundo (un `<raiz>/.telar/arte/huerta.txt` es el de `huerta` sin decir nada);
2. uno de fábrica que lo sugiere (`para`): el telar para `trabajo`, el cielo para `personal`;
3. la órbita.

«Ambos» lleva la binaria. Una clave que no hay no es un error: la tarjeta lleva el que le toca.

Los de fábrica:

| clave | qué es |
|---|---|
| `telar` | un telar tejiendo: la lanzadera cruza y la tela de rombos crece hacia abajo, una pasada a la vez |
| `cielo` | el cielo de noche: la luna, estrellas que titilan cada una a su ritmo, una fugaz de vez en cuando y una casa con la luz prendida |
| `orbita` | un planeta con anillo, sus bandas que giran y una luna que le da la vuelta (el de un mundo sin arte) |
| `binaria` | dos mundos que giran uno alrededor del otro (el de ambos) |

Se ven todos, animados, en `/componentes#mundos/artes`.

## Uno nuevo, sin código: un archivo en la raíz

`<raiz>/.telar/arte/<clave>.txt`. telar lo entrega solo (`GET /arte`) y la página lo registra al abrir la ventana: no hay
que compilar nada, y como vive en la raíz viaja por git a las otras máquinas. La clave es el nombre del archivo, en
minúsculas, números y guiones (`faro`, `mar-de-noche`).

```
nombre: faro
que: un faro que barre la noche
fps: 3
hover: 9
efecto: ninguno
---
      *
     /|\
    |▒|  ·      ·
   _|_|_ ~~~ ~~
---
   ·  *
     /|\ ─ ─ ─
    |▒|  ·
   _|_|_  ~~~ ~~
--- hover
      *
 ═══ /|\ ═══
    |▒|
   _|_|_ ~~ ~~~
```

- **Los cuadros** van separados por una línea que dice solo `---`, y se repiten en orden.
- **La cabecera**, si se quiere: la primera parte, si todas sus líneas son `clave: valor`. `fps` (cuadros por segundo;
  de fábrica 6), `hover` (los fps con el mouse encima; de fábrica, el triple), `nombre` y `que` (cómo se ve en el
  catálogo y en ⚙ mundos), `para` (los mundos que lo llevan sin decir `arte`, separados por coma) y `efecto` (el efecto
  de hover: `ola`, `ninguno` u otro registrado; sin decirlo, la ola).
- **La escena de hover**: desde una línea `--- hover`, los cuadros que siguen son los de cuando el mouse (o el foco) está
  encima, en vez de acelerar los de siempre. Un arte con escena propia no lleva la ola, salvo que diga `efecto: ola`.
- **El lienzo** mide 30 × 9 letras. Los cuadros más chicos se centran todos juntos (la caja que los contiene a todos va al
  medio: no saltan de uno a otro); lo que no cabe se recorta. Las líneas en blanco de arriba y de abajo de un cuadro no
  cuentan.
- **El color** es el del mundo: el dibujo es solo letras. Las que se ven bien en todas partes son las de la caja (`─│┼╱╲`),
  los bloques (`█▀▄░▒▓▁▂…▇`) y lo de siempre (`. · + * ~ ' "`); otras pueden salir de otro ancho en el teléfono.
- Hasta 64 KB por archivo, en UTF-8. Uno que no se lee lo dice `GET /arte` (`errores`), y la página sigue sin él.

`/componentes#mundos/probar` es el lugar para escribirlo: se ve al lado, animado, mientras se escribe.

## Uno con código: un módulo de fábrica

Para lo que no se dibuja cuadro a cuadro (un cielo que nunca se repite, un planeta que gira), una función del tiempo. Un
archivo en `pagina/src/componentes/arte/` y una línea en su `index.ts`:

```ts
// pagina/src/componentes/arte/faro.ts
import { registrarArte } from '../arte';
import { lienzo } from './comun';

registrarArte('faro', {
    nombre: 'faro',
    que: 'un faro que barre la noche',
    // el cuadro en el instante t (segundos de su reloj), del tamaño del lienzo
    cuadros: (t, ancho, alto, { hover }) => {
        const l = lienzo(ancho, alto);
        const x = Math.round((Math.sin(t) + 1) / 2 * (ancho - 1));
        for (let c = 0; c < ancho; c++) l.poner(c, alto - 1, '~');
        l.poner(x, 2, hover ? '+' : '*');
        return l.texto();
    },
    fps: 10,                 // a qué ritmo se dibuja (la función se llama cuando cambia el cuadro, no a 60 por segundo)
    alHover: { fps: 30 },    // con el mouse encima: más rápido (o `cuadros`: otra escena; `efecto`: otro que la ola)
    para: ['faro'],          // los mundos que lo llevan sin decir `arte`
});
```

El contrato (`pagina/src/componentes/arte.ts`):

- `cuadros`: una lista de textos, o `(t, ancho, alto, { hover }) => string`. Una función tiene que ser **pura**: el mismo
  instante da siempre el mismo cuadro (para algo al azar, `azar(semilla)` de `arte/comun.ts`). Así «reducir movimiento»
  muestra siempre el mismo cuadro quieto, el de `t = 0`, y la prueba puede revisarla.
- `t` es el reloj del arte, no el de la pared: corre más rápido mientras se acelera (con el mouse encima), y frena de a
  poco al salir. Una escena de hover aparte (`alHover.cuadros`) corre a su ritmo, sin acelerar.
- Lo que devuelve se ajusta al lienzo (cada línea a `ancho`, `alto` líneas): no hace falta rellenar.
- `lienzo(ancho, alto)` (`arte/comun.ts`) da un lienzo en blanco donde `poner(x, y, letra)` y `leer(x, y)`.

La prueba (`npm run prueba:mundos-ventana`) revisa cada arte registrado: que cada cuadro mida el lienzo exacto, que el
mismo instante dé el mismo cuadro, que se mueva y que encima vaya más rápido.

## El efecto de hover: la ola

Cuando el mouse o el foco entra en una tarjeta, una ola de letras cruza su arte una vez, de izquierda a derecha, en menos
de un segundo: la cresta va adelante arriba y ondula, cambia las letras del dibujo por las suyas (`▓ ▒ ░` y la espuma
`~`) y se las devuelve. Se dibuja en la misma grilla de letras que el arte, encima del cuadro que toca, así que sirve
sobre cualquier arte (de fábrica, registrado o de un archivo) sin que el arte la programe. Si el mouse sale antes,
termina su pasada igual. Es `componentes/arte/ola.ts`.

Cuál lleva cada arte (`efectoDe`, en `componentes/arte.ts`):

1. el que dice su `alHover.efecto` (en un archivo, `efecto:`): la clave de uno registrado, uno propio (un objeto con
   `dura` y `aplicar`), o `ninguno`;
2. si no dice y tiene escena de hover propia (`alHover.cuadros`, `--- hover`), ninguno: manda su escena;
3. si no, la ola. Una clave que no hay, también la ola.

Un efecto nuevo, como un arte de fábrica: un archivo en `componentes/arte/` y una línea en su `index.ts`.

```ts
import { registrarEfecto } from '../arte';

registrarEfecto('lluvia', {
    nombre: 'lluvia',
    que: 'gotas que caen sobre el dibujo',
    dura: .8,     // segundos que dura una pasada
    fps: 30,      // a qué ritmo se redibuja mientras pasa
    // el cuadro del arte (ya del lienzo) y los segundos desde que entró el mouse (los de la pared, no el reloj del arte)
    aplicar: (cuadro, t, ancho, alto) => cuadro,
});
```

Como un arte, `aplicar` tiene que ser **pura**: el mismo cuadro y el mismo instante dan lo mismo. Lo que devuelve se ajusta
al lienzo, y si falla, el cuadro queda sin efecto. La prueba (`npm run prueba:mundos-ventana`) pasa la ola sobre cada arte
registrado: que mida el lienzo, que se vea mientras pasa, que avance y que al terminar deje el cuadro como estaba.

## Cómo se anima

`web/arte-vivo.ts`: un solo `requestAnimationFrame` para todas las tarjetas, solo mientras la ventana está abierta y la
pestaña se ve (cerrada, ningún cuadro más), y el DOM se toca solo cuando cambia el cuadro (a los fps del arte, o del efecto
mientras pasa). Solo anima lo que se ve: un `IntersectionObserver` dice qué artes están a la vista (con muchos mundos, la
ventana se desplaza), y los demás ni avanzan ni se dibujan; si no se ve ninguno, ningún `requestAnimationFrame`. Lo que se
mueve es todo de letras; el CSS (`media/css/mundos.css`) solo cambia colores: el fondo de su color y el arte entero, sin
inclinarlo, agrandarlo ni darle halo, para que la grilla quede nítida. Con «reducir movimiento», el primer cuadro, quieto,
sin ola, y ningún `requestAnimationFrame`.
