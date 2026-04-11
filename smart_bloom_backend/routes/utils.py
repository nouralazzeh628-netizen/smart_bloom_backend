import re

EMAIL_PATTERN = r'^[\w\.-]+@[\w\.-]+\.\w{2,}$'

def validate_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number"
    if not re.search(r'[!@#$%^&*(),.?\":{}|<>]', password):
        return False, "Password must contain at least one special character"
    return True, None

def is_valid_email(email: str) -> bool:
    return bool(re.match(EMAIL_PATTERN, email))