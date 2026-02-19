from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    openai_api_key: str = ""
    github_token: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    frontend_url: str = "http://localhost:5173"
    data_dir: str = "/tmp/ci-heal-runs"
    allowed_origins: str = "*"
    max_iterations: int = 5


settings = Settings()
