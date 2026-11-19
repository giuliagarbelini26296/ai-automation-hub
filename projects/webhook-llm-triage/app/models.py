"""Contratos de entrada (webhook) e saída (triagem) validados com Pydantic."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EMAIL_PATTERN = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
SINGLE_LINE = r"^[^\r\n;\"]+$"  # sem quebra de linha, ';' ou aspas: compatível com o CSV do rpa-pedidos


class Customer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(max_length=150, pattern=EMAIL_PATTERN)


class Order(BaseModel):
    """Pedido de compra no mesmo formato de negócio do rpa-pedidos (pedido;fornecedor;email;valor)."""

    model_config = ConfigDict(extra="forbid")
    order_id: str = Field(pattern=r"^PED-\d{4}$", description="Formato PED-0001")
    supplier: str = Field(min_length=2, max_length=100, pattern=SINGLE_LINE)
    supplier_email: str = Field(max_length=150, pattern=EMAIL_PATTERN)
    amount: Decimal = Field(gt=0, le=1_000_000, decimal_places=2, description="Valor em reais")


class WebhookEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{8,64}$")
    type: Literal["order.created", "order.updated", "support.message"]
    occurred_at: datetime
    channel: Literal["site", "email", "whatsapp", "marketplace"] = "site"
    customer: Customer
    order: Order | None = None
    message: str | None = Field(default=None, min_length=1, max_length=4000)

    @model_validator(mode="after")
    def _required_by_type(self) -> WebhookEvent:
        if self.type.startswith("order.") and self.order is None:
            raise ValueError(f"'order' é obrigatório para eventos {self.type}")
        if self.type == "support.message" and not self.message:
            raise ValueError("'message' é obrigatório para eventos support.message")
        return self


Category = Literal[
    "new_order", "order_change", "delivery_issue", "cancellation", "refund", "question", "other"
]
Priority = Literal["low", "medium", "high"]
Action = Literal["send_to_rpa", "reply_customer", "escalate_human", "no_action"]


class Triage(BaseModel):
    """Saída obrigatória do passo de LLM. Qualquer campo extra ou valor fora do enum é rejeitado."""

    model_config = ConfigDict(extra="forbid")
    category: Category
    priority: Priority
    summary: str = Field(min_length=1, max_length=280)
    suggested_action: Action


def _enum(values: object) -> list[str]:
    return list(values.__args__)  # type: ignore[attr-defined]


# Schema usado em response_format (modo strict da API compatível com OpenAI).
# Limites de tamanho são conferidos depois pelo Pydantic.
TRIAGE_JSON_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["category", "priority", "summary", "suggested_action"],
    "properties": {
        "category": {"type": "string", "enum": _enum(Category)},
        "priority": {"type": "string", "enum": _enum(Priority)},
        "summary": {"type": "string"},
        "suggested_action": {"type": "string", "enum": _enum(Action)},
    },
}
