"""Configuration loading and validation."""

import json
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CalDavConfig:
    url: str
    username: str
    password: str
    calendars: list[str] = field(default_factory=list)


@dataclass
class TracksConfig:
    url: str
    username: str
    password: str


@dataclass
class RemarkableConfig:
    folder: str = "Daily Planner"


@dataclass
class PlannerConfig:
    day_start_hour: int = 7
    day_end_hour: int = 21
    timezone: str = "Europe/Helsinki"


@dataclass
class Config:
    caldav: CalDavConfig
    tracks: TracksConfig
    remarkable: RemarkableConfig
    planner: PlannerConfig


def load_config(path: Optional[str] = None) -> Config:
    """Load configuration from a JSON file.

    Searches for config.json in the following order:
    1. Explicit path argument
    2. ./config.json (current directory)
    3. Same directory as the script
    """
    if path:
        config_path = Path(path)
    else:
        config_path = Path("config.json")
        if not config_path.exists():
            config_path = Path(__file__).parent.parent / "config.json"

    if not config_path.exists():
        print(f"Error: Config file not found at {config_path}", file=sys.stderr)
        print("Copy config.example.json to config.json and fill in your credentials.", file=sys.stderr)
        sys.exit(1)

    # Load from file if it exists
    file_config = {}
    if config_path.exists():
        with open(config_path) as f:
            file_config = json.load(f)

    def get_val(section: str, key: str, env_var: str, default=None):
        import os
        # 1. Env var
        val = os.environ.get(env_var)
        if val is not None:
            return val
        # 2. Config file
        if section in file_config and key in file_config[section]:
            return file_config[section][key]
        # 3. Default
        if default is not None:
            return default
        # 4. Error (if required)
        # For optional fields handled by dataclass defaults, we might return None here 
        # but the logic below assumes required unless we handle it differently.
        # Actually, let's let the dataclass handle missing required fields if we pass nothing,
        # but here we need to return *something* or raise if it's strictly required by our logic.
        # Simplification: return None if not found, and let the caller/dataclass decide.
        return None

    # Helper to construct configs. 
    # We need to manually map env vars to keys.
    
    # CalDAV
    caldav_url = get_val("caldav", "url", "PLANNER_CALDAV_URL")
    caldav_user = get_val("caldav", "username", "PLANNER_CALDAV_USERNAME")
    caldav_pass = get_val("caldav", "password", "PLANNER_CALDAV_PASSWORD")
    # Calendars is a list. For env vars, maybe comma-separated?
    # Let's support a comma-separated string in env var.
    caldav_cals_env = get_val("caldav", "calendars", "PLANNER_CALDAV_CALENDARS")
    if caldav_cals_env and isinstance(caldav_cals_env, str):
        caldav_cals = [c.strip() for c in caldav_cals_env.split(",")]
    else:
        caldav_cals = file_config.get("caldav", {}).get("calendars", [])

    try:
        caldav_config = CalDavConfig(
            url=caldav_url,
            username=caldav_user,
            password=caldav_pass,
            calendars=caldav_cals
        )

        # Tracks
        tracks_url = get_val("tracks", "url", "PLANNER_TRACKS_URL")
        tracks_user = get_val("tracks", "username", "PLANNER_TRACKS_USERNAME")
        tracks_pass = get_val("tracks", "password", "PLANNER_TRACKS_PASSWORD")
        
        tracks_config = TracksConfig(
            url=tracks_url,
            username=tracks_user,
            password=tracks_pass
        )

        # Remarkable
        rem_folder = get_val("remarkable", "folder", "PLANNER_REMARKABLE_FOLDER", "Daily Planner")
        rem_config = RemarkableConfig(folder=rem_folder)

        # Planner
        day_start = int(get_val("planner", "day_start_hour", "PLANNER_DAY_START_HOUR", 7))
        day_end = int(get_val("planner", "day_end_hour", "PLANNER_DAY_END_HOUR", 21))
        timezone = get_val("planner", "timezone", "PLANNER_TIMEZONE", "Europe/Helsinki")
        
        planner_config = PlannerConfig(
            day_start_hour=day_start,
            day_end_hour=day_end,
            timezone=timezone
        )

        return Config(
            caldav=caldav_config,
            tracks=tracks_config,
            remarkable=rem_config,
            planner=planner_config,
        )
    except TypeError as e:
        print(f"Error: Invalid config file: {e}", file=sys.stderr)
        sys.exit(1)
