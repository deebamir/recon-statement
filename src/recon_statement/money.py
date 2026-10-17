from decimal import Decimal

def to_pence(amount: str) -> int:
    """'12.34' -> 1234. Takes text, never a float."""
    return int((Decimal(amount) * 100).to_integral_value())

def fmt(pence: int) -> str:
    """1234 -> '12.34'"""
    return f"{Decimal(pence) / 100:,.2f}"
