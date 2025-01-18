from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MIRRORFACE_",
    )

    # URL of the upstream HF Hub instance to fall back to.
    upstream_url: str = "https://huggingface.co"

    # Path to local directory where mirrored repositories are stored.
    local_directory: str

    # Chunk size for transparent proxying.
    chunk_size: int = 8 * 1024 * 1024


settings = Settings()  # pyright: ignore[reportCallIssue], pydantic-settings will initialize or throw
