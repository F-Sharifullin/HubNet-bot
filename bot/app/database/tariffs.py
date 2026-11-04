from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Tariff:
    name: str
    title: str
    monthly_price: Decimal
    max_keys: int

    @property
    def daily_price(self) -> Decimal:
        return self.monthly_price / 30

TARIFFS: dict[str, Tariff] = {
    "START":    Tariff("START",    "START",    Decimal("150"), 2),
    "STANDARD": Tariff("STANDARD", "STANDARD", Decimal("250"), 4),
    "PREMIUM":  Tariff("PREMIUM",  "PREMIUM",  Decimal("350"), 6),
}