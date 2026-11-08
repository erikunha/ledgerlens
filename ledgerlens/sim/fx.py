"""Reference exchange rates for the simulator, read from the recorded ECB series.

`data/fixtures/fx/frankfurter_eur.json` holds the ECB daily rates (business days only, EUR base).
A weekend or holiday uses the previous business day, like the API. A pair that does not involve
the euro is a cross rate through the euro, rounded half-even to four decimals, which is what the
API returns for the same pair.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "fx" / "frankfurter_eur.json"
MAX_CARRY_DAYS = 5
FOUR_DECIMALS = Decimal("0.0001")


class FxUnavailable(LookupError):
    """No rate can be given for the request. The message says why."""


@dataclass(frozen=True)
class FxRate:
    rate: Decimal
    rate_date: date
    requested_date: date
    from_currency: str
    to_currency: str


class FxTable:
    def __init__(self, rates: dict[date, dict[str, Decimal]], base: str = "EUR") -> None:
        if not rates:
            raise ValueError("an empty rate table")
        self.base = base
        self._rates = dict(sorted(rates.items()))
        self._days = list(self._rates)
        self.first_day = self._days[0]
        self.last_day = self._days[-1]

    @classmethod
    def from_file(cls, path: Path = DEFAULT_PATH) -> FxTable:
        data = json.loads(Path(path).read_text(encoding="utf-8"), parse_float=Decimal)
        rates = {date.fromisoformat(day): dict(values) for day, values in data["rates"].items()}
        return cls(rates, base=data.get("base", "EUR"))

    def _day_on_or_before(self, day: date) -> date:
        if day < self.first_day:
            raise FxUnavailable(f"{day} is before the first recorded rate {self.first_day}")
        if day > self.last_day + timedelta(days=MAX_CARRY_DAYS):
            raise FxUnavailable(f"{day} is after the last recorded rate {self.last_day}")
        low, high = 0, len(self._days) - 1
        while low < high:
            mid = (low + high + 1) // 2
            if self._days[mid] <= day:
                low = mid
            else:
                high = mid - 1
        return self._days[low]

    def _per_base(self, day: date, currency: str) -> Decimal:
        if currency == self.base:
            return Decimal(1)
        try:
            return self._rates[day][currency]
        except KeyError:
            raise FxUnavailable(f"no {self.base}/{currency} rate recorded (unsupported currency {currency})") from None

    def rate(self, day: date, from_currency: str, to_currency: str) -> FxRate:
        """Units of `to_currency` per one unit of `from_currency` on `day` (or the business day before)."""
        used = self._day_on_or_before(day)
        if from_currency == to_currency:
            value = Decimal(1)
        elif from_currency == self.base:
            value = self._per_base(used, to_currency)
        else:
            value = (self._per_base(used, to_currency) / self._per_base(used, from_currency)).quantize(
                FOUR_DECIMALS, ROUND_HALF_EVEN
            )
        return FxRate(value, used, day, from_currency, to_currency)
