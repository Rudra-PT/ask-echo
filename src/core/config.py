from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    GOOGLE_API_KEY: str = ""
    PINECONE_API_KEY: str = ""
    GOOGLE_CLIENT_ID: str = ""

    @property
    def GEMINI_API_KEY(self) -> str:
        return self.GOOGLE_API_KEY


settings = Settings()
