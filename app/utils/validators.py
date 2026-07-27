import re


def validate_sku_format(sku: str) -> bool:
    """Validate that SKU follows alphanumeric and hyphen format."""
    pattern = r"^[A-Z0-9\-]{3,20}$"
    return bool(re.match(pattern, sku))
