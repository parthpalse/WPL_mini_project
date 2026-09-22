"""Money representation and Indian Rupee formatting helpers.

All monetary calculations must use Decimal with explicit rounding policies.
No float money representation.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Union

PAISE = Decimal('0.01')
RUPEE = Decimal('1')


def to_decimal(val: Union[int, float, str, Decimal, None], default: str = '0.00') -> Decimal:
    """Safely convert any numeric input or string to Decimal.
    
    Floats are converted via str to avoid binary floating-point representation artifacts.
    """
    if val is None:
        return Decimal(default)
    if isinstance(val, Decimal):
        return val
    if isinstance(val, float):
        # Convert through str representation
        return Decimal(str(val))
    return Decimal(str(val).strip() or default)


def round_inr(val: Union[int, float, str, Decimal], places: int = 2) -> Decimal:
    """Round a Decimal amount using standard HALF_UP policy."""
    d = to_decimal(val)
    if places == 0:
        return d.quantize(RUPEE, rounding=ROUND_HALF_UP)
    quant = Decimal('10') ** (-places)
    return d.quantize(quant, rounding=ROUND_HALF_UP)


def to_paise(val: Union[int, float, str, Decimal]) -> int:
    """Convert rupee amount to integer paise."""
    return int(round_inr(val, places=2) * 100)


def from_paise(paise: int) -> Decimal:
    """Convert integer paise back to Decimal rupees."""
    return (Decimal(paise) / Decimal(100)).quantize(PAISE)


def format_inr(
    amount: Union[int, float, str, Decimal],
    include_symbol: bool = True,
    decimals: int = 2
) -> str:
    """Format an amount using the Indian numbering grouping (e.g., 12,34,567.89).
    
    Rules for Indian numbering:
    - Rightmost 3 digits group together.
    - All preceding digits group in pairs of 2.
    """
    d = round_inr(amount, places=decimals)
    sign = "-" if d < 0 else ""
    abs_d = abs(d)

    parts = f"{abs_d:.{decimals}f}".split(".")
    integer_part = parts[0]
    decimal_part = ("." + parts[1]) if decimals > 0 else ""

    if len(integer_part) <= 3:
        formatted_int = integer_part
    else:
        last3 = integer_part[-3:]
        remaining = integer_part[:-3]
        groups = []
        while len(remaining) > 2:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            groups.insert(0, remaining)
        formatted_int = ",".join(groups) + "," + last3

    symbol = "₹" if include_symbol else ""
    return f"{sign}{symbol}{formatted_int}{decimal_part}"


def format_inr_compact(amount: Union[int, float, str, Decimal]) -> str:
    """Format an amount in compact Indian notation (e.g. ₹1.50 Lakh, ₹2.30 Crore)."""
    d = to_decimal(amount)
    sign = "-" if d < 0 else ""
    abs_d = abs(d)

    if abs_d >= Decimal('10000000'):  # 1 Crore
        val = abs_d / Decimal('10000000')
        return f"{sign}₹{val:.2f} Cr"
    elif abs_d >= Decimal('100000'):  # 1 Lakh
        val = abs_d / Decimal('100000')
        return f"{sign}₹{val:.2f} L"
    elif abs_d >= Decimal('1000'):  # 1 Thousand
        val = abs_d / Decimal('1000')
        return f"{sign}₹{val:.2f} K"
    else:
        return format_inr(amount, include_symbol=True, decimals=0)
