import hmac
import hashlib
import json
from urllib.parse import parse_qs

def validate_init_data(token: str, init_data: str) -> bool:
    try:
        parsed_data = {k: v[0] for k, v in parse_qs(init_data).items()}
        if "hash" not in parsed_data:
            return False

        check_hash = parsed_data.pop("hash")
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))

        secret_key = hmac.new("WebAppData".encode(), token.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        return calculated_hash == check_hash
    except Exception:
        return False

def get_user_id_from_init_data(init_data: str) -> int:
    try:
        parsed_data = {k: v[0] for k, v in parse_qs(init_data).items()}
        user_data = json.loads(parsed_data.get("user", "{}"))
        return user_data.get("id")
    except Exception:
        return None
