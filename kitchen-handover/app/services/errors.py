class NotFoundError(Exception):
    """Base class: a referenced entity does not exist."""


class ProductNotFoundError(NotFoundError):
    def __init__(self, product_id: int):
        super().__init__(f"Prepared product {product_id} not found.")


class StationNotFoundError(NotFoundError):
    def __init__(self, station_id: int):
        super().__init__(f"Station {station_id} not found.")


class SectionNotFoundError(NotFoundError):
    def __init__(self, section_id: int):
        super().__init__(f"Section {section_id} not found.")


class WorkerNotFoundError(NotFoundError):
    def __init__(self, worker_id: int):
        super().__init__(f"Worker {worker_id} not found.")


class TaskNotFoundError(NotFoundError):
    def __init__(self, task_id: int):
        super().__init__(f"Preparation task {task_id} not found.")


class InactiveProductError(Exception):
    """A preparation task cannot be created for a product that is no longer active."""

    def __init__(self, product_id: int):
        super().__init__(f"Prepared product {product_id} is inactive and cannot be scheduled for preparation.")


# --- auth / authorization ---


class InvalidCredentialsError(Exception):
    """Wrong email or wrong password. Deliberately the same message/error
    for both cases (never reveal which one was wrong — don't let login help
    an attacker enumerate valid emails)."""


class InactiveAccountError(Exception):
    """Credentials were correct but the account is deactivated."""


class LoginRequiredError(Exception):
    """Raised by the `require_user` dependency; the exception handler turns
    this into a redirect to /login?next=..., not a raw 401, since almost
    every route that can raise this is a browser page."""

    def __init__(self, next_path: str = "/"):
        self.next_path = next_path
        super().__init__("Login required.")


class ForbiddenError(Exception):
    """Authenticated, but not permitted (e.g. a WORKER hitting /admin)."""


class CSRFError(Exception):
    def __init__(self):
        super().__init__("CSRF validation failed. Please reload the page and try again.")


# --- admin / catalog management ---


class DuplicateEmailError(Exception):
    def __init__(self, email: str):
        super().__init__(f"A user with email {email!r} already exists.")


class DuplicateNameError(Exception):
    def __init__(self, kind: str, name: str):
        super().__init__(f"A {kind} named {name!r} already exists.")


class SectionStationMismatchError(Exception):
    """A product/section pairing where the section doesn't belong to the
    selected station (spec: "a section assigned to a product must belong to
    the selected station")."""

    def __init__(self, section_id: int, station_id: int):
        super().__init__(f"Section {section_id} does not belong to station {station_id}.")


class LastAdminError(Exception):
    """Refuses to deactivate/demote the only remaining active admin, so
    nobody can accidentally lock everyone out of /admin."""

    def __init__(self):
        super().__init__("Cannot deactivate or demote the only remaining active admin.")


class PasswordRequiredForAdminError(Exception):
    """A WORKER account created through the PIN-based flow has no password
    at all. Promoting it to ADMIN (or creating a new account directly as
    ADMIN through the worker-creation form) would leave an admin account
    that can never log in, since ADMIN only ever authenticates with
    email+password. Set a password first (the existing password-reset
    form works on any account, regardless of its current role)."""

    def __init__(self):
        super().__init__(
            "ADMIN accounts require a password. Set a password for this account first "
            "(or use scripts/create_admin.py), then change its role to ADMIN."
        )


# --- worker PIN login ---


class InvalidPinFormatError(Exception):
    def __init__(self):
        super().__init__("PIN must be exactly 4 numeric digits.")


class PinMismatchError(Exception):
    def __init__(self):
        super().__init__("PIN and confirmation do not match.")


class InvalidPinError(Exception):
    """Wrong worker name or wrong PIN. Deliberately the same error for both
    (and never reveals which digit was wrong) — same reasoning as
    InvalidCredentialsError for email+password."""


class PinLockedError(Exception):
    """Too many wrong PINs in a row; further attempts are refused for a
    while, regardless of whether this one would have been correct."""
