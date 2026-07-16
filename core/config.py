import os
from pydantic_settings import BaseSettings, SettingsConfigDict

# 1. Dynamically calculate the root directory (Hackathon_Scraper/)
# __file__ is 'core/config.py'. dirname(__file__) is 'core/'. dirname(dirname(__file__)) is root.
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE_PATH = os.path.join(ROOT_DIR, ".env")

class Settings(BaseSettings):
    database_url: str
    proxy_api_key: str
    gemini_api_key: str
    scrapy_concurrency: int = 16

    # Force Pydantic to look at the true root folder path for .env
    model_config = SettingsConfigDict(env_file=ENV_FILE_PATH, extra="ignore")

settings = Settings()