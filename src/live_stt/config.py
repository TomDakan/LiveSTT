"""
Application Configuration.
This module defines the settings for the application.
"""

import logging
from pathlib import Path

import typed_settings as ts
from dotenv import load_dotenv

load_dotenv()

# Find the project root directory (which contains the .env file)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@ts.settings
class Settings:
    """
    Application settings, loaded from .env files and environment variables.
    """

    # Example setting:
    log_level: str = ts.option(
        default="INFO", help="The minimum log level (e.g., DEBUG, INFO, WARNING)."
    )
    # Add more settings here as needed:
    # api_key: str = ts.secret(default="", help="An example API key.")


# Load the settings instance
try:
    _loaders = ts.default_loaders(appname="live_stt", config_files=[])
    settings = ts.load_settings(Settings, loaders=_loaders)
except Exception as e:
    logging.error(f"Error loading configuration: {e}")
    # Fallback to default settings on error
    settings = Settings()
