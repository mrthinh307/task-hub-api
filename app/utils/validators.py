import re


def validate_bcrypt_password_length(password: str) -> str:
    """Validate that a password fits bcrypt's 72-byte input limit."""
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password must not exceed 72 bytes")
    return password


def validate_sku_format(sku: str) -> bool:
    """Validate that SKU follows alphanumeric and hyphen format."""
    pattern = r"^[A-Z0-9\-]{3,20}$"
    return bool(re.match(pattern, sku))
