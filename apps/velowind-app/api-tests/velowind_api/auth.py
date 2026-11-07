from dataclasses import dataclass, field
from .checks import identifier, require


@dataclass(frozen=True)
class Identity:
    user_id: str
    token: str = field(repr=False)


def login(http, account):
    data = http.request("POST", "/api/v1/mobile/auth/login/phone/password", body={
        "phone": account["phone"], "password": account["password"],
    })
    token = data.get("accessToken")
    require(isinstance(token, str) and bool(token.strip()), "Login missing accessToken")
    user_id = identifier(data.get("userId"), "userId")
    if account.get("expected_user_id"):
        require(user_id == str(account["expected_user_id"]), "Login returned unexpected identity")
    return Identity(user_id, token)
