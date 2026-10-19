"""Lo que telar sabe hacer, como funciones: reciben parámetros con tipo y devuelven un modelo.

Cada orden de la CLI (`telar.ordenes`) y cada ruta de la API (`telar.api`) es una cáscara alrededor de
una de estas funciones: la CLI traduce `argv` a parámetros y el modelo a texto o a JSON; la API
traduce la consulta HTTP a parámetros y devuelve el modelo, que FastAPI valida y documenta. La lógica
vive aquí una sola vez.

Los modelos (Pydantic) son el contrato: lo que `telar <orden> --json` imprime y lo que la API devuelve
es el mismo objeto, serializado igual. Se migran orden por orden; las que todavía no están aquí siguen
con su `main` de siempre (ver docs/propuestas/dashboard-fuera-de-vscode.md).
"""
