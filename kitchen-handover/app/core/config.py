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


settings = Settings()
