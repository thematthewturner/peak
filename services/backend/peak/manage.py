import argparse
import getpass

from sqlalchemy import select

from .auth import passwords
from .db import Login, SessionLocal, User


def main(argv=None):
    parser = argparse.ArgumentParser(description="Peak invite-only account provisioning")
    parser.add_argument("username")
    parser.add_argument("--role", required=True, choices=["parent", "student"])
    parser.add_argument("--household", default="family")
    args = parser.parse_args(argv)
    password = getpass.getpass("New password (at least 12 characters): ")
    if len(password) < 12 or password != getpass.getpass("Confirm password: "):
        raise SystemExit("Password must match and contain at least 12 characters")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == args.username))
        if user:
            user.password_hash = passwords.hash(password)
            for login in db.scalars(select(Login).where(Login.user_id == user.id)):
                db.delete(login)
        else:
            db.add(
                User(
                    username=args.username,
                    role=args.role,
                    household=args.household,
                    password_hash=passwords.hash(password),
                )
            )
        db.commit()
    print("Account provisioned. Existing role is preserved when resetting a password.")


if __name__ == "__main__":
    main()
