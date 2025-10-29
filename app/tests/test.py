from datetime import datetime, timedelta

from jose import jwt

from app.models.user_management_models import *
from app.schemas.inventory_schemas import Medicine
from app.services.auth_service import AuthService

jti = "something"
payload = {
    "sub": "1",
    "scopes": [],
    "exp": datetime.utcnow() + timedelta(minutes=20),
    "jti": jti,
}
print(jwt.encode(payload, "nayeem", "HS256"))
print(jwt.encode(payload, "nayeem", "HS256"))
print(jwt.encode(payload, "nayeem", "HS256"))
print(jwt.encode(payload, "nayeem", "HS256"))
