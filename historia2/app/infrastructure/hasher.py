from __future__ import annotations

import bcrypt


class BcryptHasher:
    def hash_password(self, raw_password: str) -> str:
        return bcrypt.hashpw(raw_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def verify(self, raw_password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(raw_password.encode("utf-8"), hashed_password.encode("utf-8"))
