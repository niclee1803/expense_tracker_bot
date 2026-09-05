import calendar
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from settings import CURRENCY, TIMEZONE


def now_local() -> datetime:
    return datetime.now(TIMEZONE)


def month_key(value: datetime) -> str:
    return value.strftime("%Y-%m")


def month_title(key: str) -> str:
    year, month = map(int, key.split("-"))
    return f"{calendar.month_name[month]} {year}"


def previous_months(count: int = 12) -> list[str]:
    current = now_local()
    year, month = current.year, current.month
    result = []

    for _ in range(count):
        month -= 1

        if month == 0:
            month = 12
            year -= 1

        result.append(f"{year:04d}-{month:02d}")

    return result


def money(cents: int) -> str:
    return f"{CURRENCY} {cents / 100:,.2f}"


def parse_money_to_cents(text: str) -> int:
    cleaned = text.replace(",", "").strip()
    value = Decimal(cleaned).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    cents = int(value * 100)

    if cents <= 0:
        raise ValueError("Amount must be greater than zero")

    return cents


def parse_expense_input(text: str) -> tuple[int, str]:
    parts = text.strip().split(maxsplit=1)

    if not parts:
        raise ValueError("Expense amount is required")

    cents = parse_money_to_cents(parts[0])
    comment = parts[1].strip() if len(parts) > 1 else ""

    if len(comment) > 200:
        raise ValueError("Comment must be 200 characters or fewer")

    return cents, comment