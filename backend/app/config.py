import os
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Browsers block cross-origin API calls unless the API echoes these in Access-Control-Allow-Origin.
# Cloud-first default; set CORS_ORIGINS on Cloud Run to add more hosts (e.g. Firebase Hosting).
_DEFAULT_CORS_ORIGINS = "https://wealthgraph-web-102631486332.us-central1.run.app"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    cors_origins: str = _DEFAULT_CORS_ORIGINS
    gcp_project_id: str = ""
    gcp_location: str = "us-central1"
    gemini_model: str = "gemini-2.5-flash"
    gemini_api_key: str = ""
    firebase_credentials_path: str = ""
    # When Firebase project ≠ default GCP project (e.g. web app is genaicohert1firebase)
    firebase_project_id: str = ""
    news_api_key: str = ""
    news_api_url: str = "https://newsapi.org/v2"

    @model_validator(mode="after")
    def default_gcp_project(self):
        if not self.gcp_project_id:
            self.gcp_project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "") or ""
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


def cors_list() -> list[str]:
    return [o.strip() for o in get_settings().cors_origins.split(",") if o.strip()]
