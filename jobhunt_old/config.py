"""Runtime configuration for JobHunt OS (env-driven, defaults for local)."""

from __future__ import annotations

import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


class Settings:
    def __init__(self) -> None:
        self.api_key: str = os.getenv("OPENAI_API_KEY", "")
        self.base_url: str = os.getenv("OPENAI_BASE_URL", "") or "https://api.openai.com/v1"
        self.model: str = os.getenv("JOBHUNT_MODEL", "gpt-4o-mini")
        self.data_dir: Path = Path(os.getenv("JOBHUNT_DATA", BASE / "data"))
        self.assert_profile: str = str(BASE / "samples" / "profile.json")

    @property
    def profile_path(self) -> Path:
        """Your real profile (private) wins when it exists in the data dir;
        otherwise fall back to the public demo persona in samples/."""
        override = os.getenv("JOBHUNT_PROFILE")
        if override:
            return Path(override).resolve()
        local = self.data_dir / "profile.json"
        if local.exists():
            return local.resolve()
        return Path(self.assert_profile).resolve()

    @property
    def jobs_csv_path(self) -> Path:
        """Real scout output in data/ wins over the neutral sample."""
        local = self.data_dir / "jobs.csv"
        if local.exists():
            return local.resolve()
        path = Path(os.getenv("JOBHUNT_JOBS_CSV", str(BASE / "samples" / "jobs.csv")))
        return path.resolve()

    @property
    def llm_enabled(self) -> bool:
        return bool(self.api_key)


SETTINGS = Settings()