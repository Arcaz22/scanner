from pathlib import Path
from typing import Optional
from functools import lru_cache
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Konfigurasi Pydantic: otomatis membaca file .env
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # DB_URL dan db_url dianggap sama
        extra="ignore",        # Mengabaikan variabel di .env yang tidak didefinisikan di sini
    )

    # ── Environment ───────────────────────────────────────────────────────────
    env: str = Field("development", alias="APP_ENV")

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"

    # ── API Keys ──────────────────────────────────────────────────────────────
    tavily_api_key: Optional[str] = Field(None, alias="TAVILY_API_KEY")
    discord_token: Optional[str] = Field(None, alias="DISCORD_TOKEN")
    guild_id: Optional[str] = Field(None, alias="GUILD_ID")
    ch_bot: Optional[str] = Field(None, alias="CH_BOT")

    # ── Database Lokal (Docker Postgres) ──────────────────────────────────────
    database_url: str = Field(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/scanner",
        alias="DATABASE_URL"
    )

    @property
    def async_database_url(self) -> str:
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self.database_url

    # ── Paths ─────────────────────────────────────────────────────────────────
    # Menyelesaikan path secara dinamis relatif terhadap file config ini
    # Asumsi: file ini ada di src/core/config.py, maka parent.parent.parent adalah root project
    base_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent)

    @property
    def watchlist_path(self) -> Path:
        config_path = self.base_dir / "config" / "watchlist.json"
        root_path = self.base_dir / "watchlist.json"
        return config_path if config_path.exists() else root_path

    @property
    def log_dir(self) -> Path:
        return self.base_dir / "logs"

    # ── Thresholds (Flagging Logic) ───────────────────────────────────────────
    volume_spike_multiplier: float = Field(1.5, alias="VOLUME_SPIKE_MULTIPLIER")
    price_change_threshold: float = Field(2.0, alias="PRICE_CHANGE_THRESHOLD")
    volume_avg_days: int = Field(20, alias="VOLUME_AVG_DAYS")
    support_resistance_days: int = Field(30, alias="SUPPORT_RESISTANCE_DAYS")

    # ── Fundamental Red Flag Thresholds ───────────────────────────────────────
    der_caution: float = Field(1.5, alias="DER_CAUTION")
    der_danger: float = Field(2.0, alias="DER_DANGER")
    per_high: float = Field(30.0, alias="PER_HIGH")
    per_very_high: float = Field(50.0, alias="PER_VERY_HIGH")
    cf_neg_quarters: int = Field(2, alias="CF_NEG_QUARTERS")

    # ── Tavily Search Settings ────────────────────────────────────────────────
    tavily_max_results: int = Field(3, alias="TAVILY_MAX_RESULTS")
    tavily_search_days: int = Field(1, alias="TAVILY_SEARCH_DAYS")
    tavily_include_domains: str = Field(
        "investasi.kontan.co.id,bisnis.com,market.bisnis.com,cnbcindonesia.com,"
        "emitennews.com,stockwatch.id",
        alias="TAVILY_INCLUDE_DOMAINS",
    )
    tavily_exclude_domains: str = Field(
        "blogspot.com,wordpress.com,medium.com,facebook.com,twitter.com,x.com,"
        "tiktok.com,instagram.com,youtube.com",
        alias="TAVILY_EXCLUDE_DOMAINS",
    )
    tavily_validate_urls: bool = Field(True, alias="TAVILY_VALIDATE_URLS")
    tavily_url_check_timeout: int = Field(8, alias="TAVILY_URL_CHECK_TIMEOUT")
    tavily_debug_results: bool = Field(False, alias="TAVILY_DEBUG_RESULTS")
    tavily_allow_broad_retry: bool = Field(False, alias="TAVILY_ALLOW_BROAD_RETRY")

    # ── Ollama Local LLM ─────────────────────────────────────────────────────
    ollama_base_url: str = Field("http://172.20.160.1:11434", alias="OLLAMA_BASE_URL")
    ollama_text_model: str = Field("llama3.1:8b", alias="OLLAMA_TEXT_MODEL")
    ollama_timeout_seconds: int = Field(60, alias="OLLAMA_TIMEOUT_SECONDS")

    # ── Schedule Settings ─────────────────────────────────────────────────────
    daily_scan_hour: int = Field(6, alias="DAILY_SCAN_HOUR")
    daily_scan_minute: int = Field(30, alias="DAILY_SCAN_MINUTE")
    weekly_update_day: int = Field(5, alias="WEEKLY_UPDATE_DAY")  # 5 = Sabtu (0=Senin)

    # ── Validators (Opsional: untuk memastikan data masuk akal) ───────────────
    @field_validator("tavily_api_key", "discord_token", "ch_bot")
    @classmethod
    def warn_if_missing_api_keys(cls, v: Optional[str], info) -> Optional[str]:
        if not v and info.data.get("env") == "production":
            raise ValueError(f"{info.field_name} wajib diisi di environment production!")
        return v


# Singleton pattern dengan cache agar tidak membaca ulang file .env setiap kali dipanggil
@lru_cache
def get_settings() -> Settings:
    """
    Mengembalikan instance Settings yang di-cache.
    Gunakan ini di seluruh aplikasi Anda, bukan meng-inisialisasi Settings() secara langsung.
    """
    return Settings()


# Ekspor instance global untuk kemudahan akses (opsional, tapi umum di FastAPI)
settings = get_settings()
