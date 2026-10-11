"""Operator-only local CLI: python -m app.admin email@example.com."""

import argparse
from sqlalchemy import select
from .db import SessionLocal
from .models import User

parser = argparse.ArgumentParser(
    description="Grant or revoke an existing account administrator access"
)
parser.add_argument("email")
parser.add_argument("--revoke", action="store_true")
if __name__ == "__main__":
    args = parser.parse_args()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == args.email.lower()))
        if not user:
            parser.error("Account not found; register first")
        user.is_admin = not args.revoke
        db.commit()
        print("Administrator access updated.")
