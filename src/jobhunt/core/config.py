from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class UserProfile(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JH_USER_", extra="ignore")

    name: str = "User"
    email: str = "user@example.com"
    phone: str = ""
    location: str = "San Francisco, CA"
    linkedin_url: str = ""
    github_url: str = ""
    portfolio_url: str = ""
    target_roles: list[str] = Field(default_factory=lambda: ["Software Engineer", "Senior Software Engineer"])
    target_industries: list[str] = Field(default_factory=lambda: ["Technology", "FinTech", "AI/ML"])
    target_locations: list[str] = Field(default_factory=lambda: ["San Francisco", "Remote"])
    excluded_companies: list[str] = Field(default_factory=list)
    years_experience: int = 5
    visa_status: str = "US Citizen"
    salary_min: int = 150000
    salary_max: int = 300000
    preferred_work_type: Literal["remote", "hybrid", "onsite"] = "hybrid"
    notice_period_weeks: int = 2


class AIConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JH_AI_", extra="ignore")

    provider: Literal["openai", "anthropic", "openrouter"] = "openai"
    api_key: str = ""
    model: str = "gpt-4o"
    temperature: float = 0.3
    max_tokens: int = 4000
    timeout: int = 60
    max_retries: int = 3


class LinkedInConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JH_LI_", extra="ignore")

    enabled: bool = False
    li_at_cookie: str = ""
    session_file: str = "~/.jobhunt/linkedin_session.json"
    rate_limit_per_hour: int = 20
    headless: bool = True


class DatabaseConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JH_DB_", extra="ignore")

    type: Literal["sqlite", "postgresql"] = "sqlite"
    path: str = "~/.jobhunt/jobhunt.db"
    host: str = "localhost"
    port: int = 5432
    username: str = "jobhunt"
    password: str = ""
    name: str = "jobhunt"

    @property
    def url(self) -> str:
        if self.type == "sqlite":
            path = Path(self.path).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{path}"
        return f"postgresql+psycopg://{self.username}:{self.password}@{self.host}:{self.port}/{self.name}"


class GoogleConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JH_GOOGLE_", extra="ignore")

    enabled: bool = False
    credentials_file: str = "~/.jobhunt/google_credentials.json"
    token_file: str = "~/.jobhunt/google_token.json"
    sheets_id: str = ""


class SearchConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JH_SEARCH_", extra="ignore")

    sources: list[str] = Field(default_factory=lambda: ["linkedin", "indeed", "glassdoor", "google"])
    results_per_source: int = 50
    radius_km: int = 50
    remote_only: bool = False
    date_posted_days: int = 7
    job_types: list[str] = Field(default_factory=lambda: ["fulltime", "contract"])
    experience_levels: list[str] = Field(default_factory=lambda: ["mid", "senior", "lead"])


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    user: UserProfile = Field(default_factory=UserProfile)
    ai: AIConfig = Field(default_factory=AIConfig)
    linkedin: LinkedInConfig = Field(default_factory=LinkedInConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    google: GoogleConfig = Field(default_factory=GoogleConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)

    data_dir: Path = Field(default_factory=lambda: Path("~/.jobhunt").expanduser())
    log_level: str = "INFO"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "profiles").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "resumes").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "outreach").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "interviews").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "applications").mkdir(parents=True, exist_ok=True)


settings = Settings()


def load_profile(profile_name: str) -> UserProfile:
    import yaml
    profile_path = settings.data_dir / "profiles" / f"{profile_name}.yaml"
    if profile_path.exists():
        with open(profile_path) as f:
            data = yaml.safe_load(f)
        return UserProfile(**data)
    return settings.user


def save_profile(profile: UserProfile, profile_name: str) -> None:
    import yaml
    profile_path = settings.data_dir / "profiles" / f"{profile_name}.yaml"
    with open(profile_path, "w") as f:
        yaml.dump(profile.model_dump(), f, default_flow_style=False, sort_keys=False)
