from datetime import time

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, loaded from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite:///./kitchen_handover.db"

    # --- auth / sessions ---
    # INSECURE DEFAULT, dev-only: a real deployment MUST set SESSION_SECRET_KEY
    # in the environment to a long random value (e.g. `python -c "import
    # secrets; print(secrets.token_urlsafe(48))"`). Anyone who knows this key
    # can forge login sessions.
    session_secret_key: str = "dev-only-insecure-secret-change-me"
    session_max_age_seconds: int = 60 * 60 * 24 * 14  # 14 days — "don't ask for the password every few minutes"

    # Cookies must be Secure (HTTPS-only) in production, but this MVP has
    # been tested over plain HTTP on a local kitchen WiFi network — forcing
    # Secure=True there would silently break login. Set COOKIE_SECURE=true
    # in the environment once the app is served over HTTPS.
    cookie_secure: bool = False

    # --- worker PIN login brute-force protection ---
    # A 4-digit PIN has only 10,000 possibilities, far fewer than a password
    # — acceptable for a fast internal kitchen login ONLY because repeated
    # wrong guesses get temporarily locked out (see auth_service.authenticate_pin).
    pin_max_failed_attempts: int = 5
    pin_lockout_seconds: int = 15 * 60

    # --- operational (business) day ---
    # NOT confirmed restaurant truth — a development placeholder until the
    # actual overnight kitchen workflow is confirmed. Before this cutoff,
    # the calendar has technically already rolled over to a new date but
    # the kitchen's working day hasn't (see app/core/operational_day.py).
    # Override via env var, e.g. OPERATIONAL_DAY_CUTOFF=03:30
    operational_day_cutoff: time = time(4, 0)


settings = Settings()
