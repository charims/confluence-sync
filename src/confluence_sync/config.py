from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class ConfluenceConfig(BaseModel):
    url: str = Field(..., description="Confluence instance URL")
    api_token: str = Field(..., description="API token for authentication")
    space_key: str = Field(..., description="Confluence space key")
    username: Optional[str] = Field(None, description="Username for legacy authentication")


class SyncConfig(BaseModel):
    confluence: ConfluenceConfig
    local_path: Path = Field(default=Path("docs"), description="Local directory for markdown files")
    ignore_patterns: list[str] = Field(default_factory=list, description="Patterns to ignore during sync")
    

class Config:
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path("confluence-sync.yml")
        self._config: Optional[SyncConfig] = None
    
    def load(self) -> SyncConfig:
        # Optional .env support for local development without requiring it at runtime.
        try:
            from dotenv import load_dotenv  # type: ignore

            load_dotenv()
        except ImportError:
            pass

        config_data: dict = {}

        if self.config_path.exists():
            with open(self.config_path) as f:
                loaded = yaml.safe_load(f)
            if loaded:
                if not isinstance(loaded, dict):
                    raise ValueError(f"Config file must contain a YAML mapping/object: {self.config_path}")
                config_data = loaded

        config_data = self._overlay_env(config_data)
        self._config = SyncConfig(**config_data)
        return self._config

    def _overlay_env(self, config_data: dict) -> dict:
        """Overlay environment variables onto YAML config (env wins when set)."""
        out = dict(config_data)

        # Confluence settings (into `confluence:` mapping)
        confluence = dict(out.get("confluence") or {})
        if confluence and not isinstance(confluence, dict):
            raise ValueError("Invalid config: 'confluence' must be a mapping/object")

        url = self._get_env("CONFLUENCE_URL")
        api_token = self._get_env("CONFLUENCE_API_TOKEN")
        space_key = self._get_env("CONFLUENCE_SPACE_KEY")
        username = self._get_env("CONFLUENCE_USERNAME")

        if url is not None:
            confluence["url"] = url
        if api_token is not None:
            confluence["api_token"] = api_token
        if space_key is not None:
            confluence["space_key"] = space_key
        if username is not None:
            confluence["username"] = username

        if confluence:
            out["confluence"] = confluence

        # Local settings (top-level keys)
        local_path = self._get_env("LOCAL_PATH")
        if local_path is not None:
            out["local_path"] = local_path

        ignore_patterns_raw = self._get_env("IGNORE_PATTERNS")
        if ignore_patterns_raw is not None:
            out["ignore_patterns"] = self._parse_ignore_patterns(ignore_patterns_raw)

        return out

    @staticmethod
    def _get_env(name: str) -> str | None:
        value = os.getenv(name)
        if value is None:
            return None
        value = value.strip()
        return value if value else None

    @staticmethod
    def _parse_ignore_patterns(value: str) -> list[str]:
        # Support JSON array or comma-separated list.
        raw = value.strip()
        if raw.startswith("["):
            parsed = json.loads(raw)
            if not isinstance(parsed, list) or not all(isinstance(x, str) for x in parsed):
                raise ValueError("IGNORE_PATTERNS must be a JSON array of strings or a comma-separated list")
            return [x.strip() for x in parsed if x.strip()]

        parts = [p.strip() for p in raw.split(",")]
        return [p for p in parts if p]
    
    def save_template(self) -> None:
        template = {
            "confluence": {
                "url": "https://your-domain.atlassian.net",
                "api_token": "your-api-token",
                "space_key": "YOUR_SPACE_KEY"
            },
            "local_path": "docs",
            "ignore_patterns": [
                "*.tmp",
                ".git/*"
            ]
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(template, f, default_flow_style=False, indent=2)
    
    def save_interactive_config(self, url: str, api_token: str, space_key: str, local_path: str = "docs", username: Optional[str] = None) -> None:
        """Save configuration from interactive setup"""
        confluence_config = {
            "url": url,
            "api_token": api_token,
            "space_key": space_key
        }
        
        if username:
            confluence_config["username"] = username
        
        config_data = {
            "confluence": confluence_config,
            "local_path": local_path,
            "ignore_patterns": [
                "*.tmp", 
                ".git/*",
                ".DS_Store"
            ]
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, indent=2)
    
    @property
    def config(self) -> SyncConfig:
        if self._config is None:
            self._config = self.load()
        return self._config