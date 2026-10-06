"""Bootstrap the very first ADMIN account.

Run with: python scripts/create_admin.py
(from the kitchen-handover/ directory, venv active, migrations applied)

Prompts interactively for display name, email, and password — the password
is read via getpass (not echoed to the terminal, never appears in shell
history). Never hardcode real credentials into source code, and never
commit them to Git.

Refuses to run if an ADMIN account already exists, to avoid this becoming a
general "create any admin from the command line" backdoor — once the first
admin exists, every other account (including additional admins) should be
created through /admin/users by a logged-in admin. Pass --force to bypass
this (e.g. you're resetting a dev database).
"""

import getpass
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.enums import Role  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.repositories import worker_repository  # noqa: E402
from app.services import user_admin_service  # noqa: E402
from app.services.errors import DuplicateEmailError  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        existing_admins = [w for w in worker_repository.list_all_workers(db) if w.role == Role.ADMIN]
        if existing_admins and "--force" not in sys.argv:
            print("An ADMIN account already exists:")
            for w in existing_admins:
                print(f"  - {w.display_name} <{w.email}>")
            print("Refusing to create another via this script.")
            print("Log in and use /admin/users to create more accounts,")
            print("or re-run with --force if you really need another bootstrap admin.")
            sys.exit(1)

        print("Create the first administrator account.")
        display_name = input("Display name: ").strip()
        email = input("Email: ").strip().lower()
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm password: ")

        if not display_name or not email or not password:
            print("All fields are required.")
            sys.exit(1)
        if password != confirm:
            print("Passwords do not match.")
            sys.exit(1)
        if len(password) < 8:
            print("Password must be at least 8 characters.")
            sys.exit(1)

        try:
            admin = user_admin_service.create_user(
                db, display_name=display_name, email=email, password=password, role=Role.ADMIN
            )
        except DuplicateEmailError as exc:
            print(str(exc))
            sys.exit(1)

        print(f"Created ADMIN account: {admin.display_name} <{admin.email}> (id={admin.id})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
