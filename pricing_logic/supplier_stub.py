
# Supplier API stub (demo). In prod, adapters pull city/postcode SKUs.
from dataclasses import dataclass

@dataclass
class SupplierQuote:
    sku: str
    description: str
    unit_price_eur: float
    city: str | None = None

def get_tile_price(city: str | None) -> SupplierQuote:
    # demo: Marseille slightly cheaper, Paris higher
    base = 27.0
    if not city: 
        return SupplierQuote("TILE-STD-01", "Standard ceramic tile 30x30", base)
    c = city.lower()
    if "paris" in c:
        return SupplierQuote("TILE-STD-01", "Standard ceramic tile 30x30", base * 1.12, city=city)
    if "marseille" in c:
        return SupplierQuote("TILE-STD-01", "Standard ceramic tile 30x30", base * 0.96, city=city)
    return SupplierQuote("TILE-STD-01", "Standard ceramic tile 30x30", base, city=city)
