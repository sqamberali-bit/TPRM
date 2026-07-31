from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    upguard_api_key: str = ""
    upguard_base_url: str = "https://cyber-risk.upguard.com/api/public"

    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""
    sharepoint_site_url: str = ""
    sharepoint_site_id: str = ""

    reports_dir: Path = Path("./input/reports")

    dry_run: bool = True
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
