"""Hand-off opcional para o robô rpa-pedidos.

Gera um CSV de uma linha no formato de entrada do robô (`pedido;fornecedor;email;valor`,
UTF-8, separador `;`, decimal com vírgula). O robô cria a própria fila persistente a partir
desse arquivo: `npm run demo -- --entrada <arquivo.csv>`.
"""

from __future__ import annotations

import csv
import io
import os
import tempfile
from pathlib import Path

from .models import Order

HEADER = ["pedido", "fornecedor", "email", "valor"]


def order_to_csv(order: Order) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", lineterminator="\n")
    writer.writerow(HEADER)
    writer.writerow(
        [order.order_id, order.supplier, order.supplier_email, f"{order.amount:.2f}".replace(".", ",")]
    )
    return buf.getvalue()


def write_job(directory: str, event_id: str, order: Order) -> str:
    """Grava de forma atômica (arquivo temporário + rename) e retorna o caminho."""
    target_dir = Path(directory)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{event_id}.csv"
    fd, tmp = tempfile.mkstemp(dir=target_dir, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(order_to_csv(order))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return str(target)
