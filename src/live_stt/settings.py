from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict  # type: ignore

try:
    from dotenv import load_dotenv

    _DOTENV_AVAILABLE = True
except Exception:
    _DOTENV_AVAILABLE = False

if _DOTENV_AVAILABLE:
    load_dotenv()


class Settings(BaseSettings):  # type: ignore[misc]
    """
    Settings for the application.
    Reads settings from environment variables.
    You can create a .env file in the root of the project to store
    sensitive information.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    app_name: str = "live-stt"
    debug: bool = False
    # The Optional[X] syntax has been replaced with X | None
    secret_key: SecretStr | None = None
    redis_dsn: str | None = None


# Instantiate the settings
settings = Settings()
