import secrets
import string

def make_key(prefix: str) -> str:
    chars = string.ascii_uppercase + string.digits
    body = "-".join(
        "".join(secrets.choice(chars) for _ in range(4))
        for _ in range(3)
    )
    return f"{prefix}-{body}"

if __name__ == "__main__":
    print("STANDARD:", make_key("SSB-STD"))
    print("PRO:     ", make_key("SSB-PRO"))
    print("ELITE:   ", make_key("SSB-ELITE"))
