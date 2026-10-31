MAX_PASSWORD_BYTES = 72  # bcrypt limit
PHONE_PATTERN = r"^[0-9+()\-.\s]{7,30}$"


def normalize_email(value: object) -> object:
    return value.strip().lower() if isinstance(value, str) else value


def check_password_bytes(value: str) -> str:
    if len(value.encode()) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes")
    return value
