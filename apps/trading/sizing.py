from decimal import ROUND_HALF_UP, Decimal


def contracts_for(capital_usdt, leverage, price, quanto_multiplier, size_min=1):
    """Nombre de contrats = capital x levier / (prix x taille du contrat)."""
    per_contract = price * float(quanto_multiplier)
    n = int((capital_usdt * leverage) // per_contract)
    if n < int(size_min):
        need = per_contract * int(size_min) / leverage
        raise ValueError(f"Capital insuffisant : minimum ~{need:.2f} USDT de marge pour {size_min} contrat(s) a x{leverage}")
    return n


def round_price(p, tick):
    t = Decimal(str(tick))
    return str((Decimal(str(p)) / t).to_integral_value(rounding=ROUND_HALF_UP) * t)
