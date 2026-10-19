"""Lo que telar sabe hacer, como funciones: reciben parámetros con tipo y devuelven un modelo.

Cada orden de la CLI (`telar.ordenes`) y cada ruta de la API (`telar.api`) es una cáscara alrededor de
una de estas funciones: la CLI traduce `argv` a parámetros y el modelo a texto o a JSON; la API
traduce la consulta HTTP a parámetros y devuelve el modelo, que FastAPI valida y documenta. La lógica
vive aquí una sola vez.

Los modelos (Pydantic) son el contrato: lo que `telar <orden> --json` imprime y lo que la API devuelve
es el mismo objeto, serializado igual. Se migran orden por orden; las que todavía no están aquí siguen
con su `main` de siempre (ver docs/propuestas/dashboard-fuera-de-vscode.md).
"""

from pydantic import BaseModel, ConfigDict


class ErrorDeServicio(Exception):
    """Lo pedido no se puede hacer, con un mensaje para la persona. La CLI lo dice como queja y sale con
    error; la API responde con `codigo` (404 si no existe, 400 si el pedido no sirve, 502 si un
    programa de afuera falló)."""

    def __init__(self, mensaje: str, codigo: int = 400, datos: dict | None = None) -> None:
        super().__init__(mensaje)
        self.codigo = codigo
        #: lo que acompaña al error en la respuesta (la `version` de ahora, si la tarea cambió)
        self.datos = dict(datos or {})


class Pagina(BaseModel):
    """Una página: la de una sección, la de un bloque del día o la ficha de una tarea (docs/contratos.md,
    «telar seccion»). La arma un programa de afuera; telar la valida y la entrega como viene."""

    model_config = ConfigDict(extra="allow")

    titulo: str = ""
    bloques: list[dict] = []
