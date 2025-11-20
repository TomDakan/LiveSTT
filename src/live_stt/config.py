"""
Application Configuration.
This module defines the settings for the application.
"""


import logging
from pathlib import Path
import typed_settings as ts

# Find the project root directory (which contains the .env file)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
@ts.settings(
appname="live_stt",  # Env var prefix (e.g., LIVE_STT_LOG_LEVEL)
config_files=[PROJECT_ROOT / ".env"],  # Load .env file from project root
merge_Dashes=True,  # Allow MYAPP_LOG_LEVEL to match log_level
)


@ts.dataclass
class Settings:
"""
Application settings, loaded from .env files and environment variables.
"""
    # Example setting:
    log_level: str = ts.option(
    default="INFO",
    help="The minimum log level (e.g., DEBUG, INFO, WARNING)."
    )
    # Add more settings here as needed:
    # api_key: str = ts.secret(default="", help="An example API key.")
    # Load the settings instance
    try:
        settings = ts.load_settings(Settings)
    except (ts.ConfigError, FileNotFoundError) as e:
        logging.error(f"Error loading configuration: {e}")
        # Fallback to default settings on error
        settings = Settings()

