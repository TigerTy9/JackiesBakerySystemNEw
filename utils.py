# utils.py

def convert_to_base(quantity: float, from_unit: str, multiplier: float) -> float:
    """
    Converts any incoming purchase quantity to the base_unit (usually grams).
    Example: 1 Bag (from_unit) * 22679.6 (multiplier) = 22679.6g
    """
    return quantity * multiplier

def get_margin_status(fifo_margin: float, newest_margin: float) -> str:
    """
    Business logic to flag if the baker needs to raise prices.
    """
    if newest_margin < (fifo_margin * 0.9): # 10% drop in margin
        return "CRITICAL: Price Hike Detected"
    return "Healthy"

def get_conversion_multiplier(db, tenant_id: int, from_unit: str, to_unit: str):
    """Looks up the multiplier in the unit_conversions table."""
    conversion = db.query(models.UnitConversion).filter(
        models.UnitConversion.tenant_id == tenant_id,
        models.UnitConversion.from_unit == from_unit,
        models.UnitConversion.to_unit == to_unit
    ).first()
    return conversion.multiplier if conversion else 1.0