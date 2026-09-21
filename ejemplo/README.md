# El taller

Un repositorio de trabajo inventado, para probar telar sin datos de nadie. Tres
proyectos, una nota y un `telar-perfil.yaml` que los declara.

Sirve para dos cosas: que las pruebas de humo tengan contra qué correr, y que
alguien que llega vea en un minuto qué forma tiene un repositorio tejible.

```sh
telar --raiz ejemplo perfil    # qué declara este taller y qué documentos alcanza
telar --raiz ejemplo hilos     # los hilos, cuando haya sesión
```

| Carpeta | Qué hay |
|---|---|
| `proyectos/` | Un encargo por carpeta, con `README.md`. Arquetipo `proyecto`. |
| `notas/` | Notas sueltas; el archivo es la unidad. Arquetipo `nota`. |
| `telar-perfil.yaml` | Lo que este repositorio declara de sí mismo. |

Los tres proyectos están escritos a propósito de formas distintas: `faro` usa
todas las secciones, `molino` solo las obligatorias, y `arboleda` no tiene sección
`Estado`, para que se vea qué hace telar cuando falta algo que el perfil pedía.
