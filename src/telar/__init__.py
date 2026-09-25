"""telar — un telar para hilos de trabajo.

Cada hilo es una unidad de trabajo viva: un tab del multiplexor de terminal, una
carpeta del repositorio donde se trabaja, y lo que esa carpeta dice de sí misma.

telar NO decide qué es un proyecto. Eso lo declara el repositorio de trabajo en su
`telar-perfil.yaml` (ver `telar.perfil`); telar solo sabe tejer lo declarado.

Los módulos, y qué le toca a cada uno:

  `telar.config`       la configuración del usuario (`~/.config/telar/config.toml`).
  `telar.perfil`       el perfil que publica el repositorio de trabajo.
  `telar.modelo`       los datos puros que los demás módulos se pasan. Sin E/S.
  `telar.estado`       lo que telar recuerda entre corridas. Derivado y desechable.
  `telar.lectura`      leer un documento como lo declara el perfil, y dar una ficha.
  `telar.mux`          hablarle al multiplexor de terminal (tmux, zellij).
  `telar.proveedores`  fuentes externas opcionales, cada una declarada.
  `telar.agente`       reconocer y dirigirse al agente que corre en un hilo.
  `telar.salida`       que la codificación de la terminal no tumbe una orden.
  `telar.cli`          el despachador; cada orden vive en `telar.ordenes.<nombre>`.
"""

__version__ = "0.1.4"
__all__ = ["__version__"]
