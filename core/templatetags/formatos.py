from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def moneda(valor):
    """Formatea como pesos colombianos: $1.234.567"""
    try:
        valor = Decimal(valor)
    except Exception:
        return valor
    return "$" + f"{valor:,.0f}".replace(",", ".")
