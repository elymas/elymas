#!/usr/bin/env python3
"""Generate the light and dark SVG cards used by the profile README."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 local environments
    tomllib = None  # type: ignore[assignment]


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "profile.toml"
GITHUB_API = "https://api.github.com"
USER_AGENT = "elymas-profile-readme"
PLACEHOLDER_PATTERN = re.compile(r"\{\{[A-Z0-9_]+\}\}")

THEMES = {
    "dark": {
        "BACKGROUND": "#07100d",
        "SURFACE": "#0d1814",
        "PANEL": "#12231c",
        "TEXT": "#edf5f0",
        "MUTED": "#839a90",
        "ACCENT": "#f0b957",
        "ACCENT_TWO": "#55c9a5",
        "PORTRAIT": "#75d6b8",
        "BORDER": "#25463a",
        "GRID": "#173127",
        "SHADOW": "#020604",
    },
    "light": {
        "BACKGROUND": "#eee7da",
        "SURFACE": "#fbf7ed",
        "PANEL": "#f0e8da",
        "TEXT": "#17231f",
        "MUTED": "#687872",
        "ACCENT": "#b65b16",
        "ACCENT_TWO": "#087d68",
        "PORTRAIT": "#176e5d",
        "BORDER": "#cdbfa8",
        "GRID": "#ddd2bf",
        "SHADOW": "#aa9d87",
    },
}


class ProfileGenerationError(RuntimeError):
    """Raised when profile input or generated output is invalid."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use the committed statistics cache without contacting GitHub.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail instead of falling back to cached statistics after an API error.",
    )
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    try:
        config = load_toml(path)
    except (OSError, ValueError) as error:
        raise ProfileGenerationError(f"Cannot read config {path}: {error}") from error

    required = {
        "profile": ("username", "name", "headline", "email", "blog_url", "blog_label"),
        "signal": ("focus", "core_stack", "web_stack", "building", "projects"),
        "display": (
            "timezone",
            "portrait_path",
            "template_path",
            "dark_output",
            "light_output",
            "cache_path",
        ),
    }
    for section, keys in required.items():
        if section not in config:
            raise ProfileGenerationError(f"Missing config section: {section}")
        for key in keys:
            if key not in config[section]:
                raise ProfileGenerationError(f"Missing config value: {section}.{key}")

    username = str(config["profile"]["username"])
    if re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", username) is None:
        raise ProfileGenerationError(f"Invalid GitHub username: {username!r}")
    return config


def load_toml(path: Path) -> dict[str, Any]:
    """Load TOML with the standard parser, plus a Python 3.10 fallback.

    The fallback intentionally supports only the section, string, number,
    boolean, and array values used by this repository's small config file.
    """
    if tomllib is not None:
        with path.open("rb") as handle:
            return tomllib.load(handle)

    document: dict[str, Any] = {}
    section: dict[str, Any] | None = None
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section_name = line[1:-1].strip()
            if not section_name:
                raise ValueError(f"empty section name on line {line_number}")
            section = document.setdefault(section_name, {})
            continue
        if section is None or "=" not in line:
            raise ValueError(f"unsupported TOML syntax on line {line_number}")
        key, raw_value = (part.strip() for part in line.split("=", 1))
        try:
            section[key] = json.loads(raw_value)
        except json.JSONDecodeError as error:
            raise ValueError(f"unsupported value on line {line_number}: {error}") from error
    return document


def project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def api_headers(token: str | None) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": USER_AGENT,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def get_json(url: str, token: str | None) -> Any:
    request = urllib.request.Request(url, headers=api_headers(token))
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise ProfileGenerationError(f"GitHub request failed for {url}: {error}") from error


def fetch_repositories(username: str, token: str | None) -> list[dict[str, Any]]:
    repositories: list[dict[str, Any]] = []
    page = 1
    while True:
        query = urllib.parse.urlencode(
            {"type": "owner", "sort": "updated", "per_page": 100, "page": page}
        )
        payload = get_json(f"{GITHUB_API}/users/{username}/repos?{query}", token)
        if not isinstance(payload, list):
            raise ProfileGenerationError("GitHub repositories response was not a list")
        repositories.extend(payload)
        if len(payload) < 100:
            return repositories
        page += 1


def github_years(created_at: str, today: date) -> int:
    created = datetime.fromisoformat(created_at.replace("Z", "+00:00")).date()
    years = today.year - created.year
    if (today.month, today.day) < (created.month, created.day):
        years -= 1
    return max(0, years)


def pick_top_repository(repositories: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [repo for repo in repositories if not repo.get("fork") and not repo.get("archived")]
    if not candidates:
        candidates = repositories
    if not candidates:
        return {"name": "building-in-public", "stargazers_count": 0}
    return max(
        candidates,
        key=lambda repo: (
            int(repo.get("stargazers_count", 0)),
            str(repo.get("updated_at", "")),
            str(repo.get("name", "")),
        ),
    )


def fetch_statistics(username: str, timezone_name: str) -> dict[str, Any]:
    token = os.getenv("PROFILE_TOKEN") or os.getenv("GITHUB_TOKEN")
    encoded_username = urllib.parse.quote(username, safe="")
    user = get_json(f"{GITHUB_API}/users/{encoded_username}", token)
    if not isinstance(user, dict):
        raise ProfileGenerationError("GitHub user response was not an object")
    repositories = fetch_repositories(encoded_username, token)
    top_repository = pick_top_repository(repositories)
    local_now = datetime.now(timezone.utc).astimezone(ZoneInfo(timezone_name))

    return {
        "username": username,
        "repositories": int(user.get("public_repos", len(repositories))),
        "stars": sum(int(repo.get("stargazers_count", 0)) for repo in repositories),
        "followers": int(user.get("followers", 0)),
        "github_years": github_years(str(user["created_at"]), local_now.date()),
        "top_repository": str(top_repository.get("name", "building-in-public")),
        "top_repository_stars": int(top_repository.get("stargazers_count", 0)),
        "refreshed_on": local_now.strftime("%Y-%m-%d KST"),
        "source": "GitHub public REST API",
    }


def load_cache(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProfileGenerationError(f"Cannot read statistics cache {path}: {error}") from error
    if not isinstance(payload, dict):
        raise ProfileGenerationError(f"Statistics cache {path} is not an object")
    return payload


def write_if_changed(path: Path, content: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary_path = Path(handle.name)
    temporary_path.replace(path)
    return True


def save_cache(path: Path, stats: dict[str, Any]) -> bool:
    return write_if_changed(path, json.dumps(stats, indent=2, sort_keys=True) + "\n")


def ascii_tspans(portrait: str, x: int = 48, first_y: int = 95, leading: int = 18) -> str:
    lines = portrait.rstrip("\n").splitlines()
    if not lines:
        raise ProfileGenerationError("ASCII portrait is empty")
    return "\n".join(
        f'<tspan x="{x}" y="{first_y + index * leading}">{escape(line.rstrip())}</tspan>'
        for index, line in enumerate(lines)
    )


def joined(values: list[Any]) -> str:
    return " · ".join(str(value) for value in values)


def format_number(value: Any) -> str:
    return f"{int(value):,}"


def render_svg(
    template: str,
    theme: dict[str, str],
    config: dict[str, Any],
    stats: dict[str, Any],
    portrait: str,
) -> str:
    profile = config["profile"]
    signal = config["signal"]
    tokens = {
        **theme,
        "TITLE": f"{profile['name']} — GitHub profile",
        "DESCRIPTION": (
            f"{profile['headline']}. {stats['repositories']} public repositories, "
            f"{stats['stars']} stars, and {stats['followers']} followers."
        ),
        "ASCII_ART": ascii_tspans(portrait),
        "USERNAME": profile["username"],
        "NAME": profile["name"],
        "HEADLINE": profile["headline"],
        "FOCUS": joined(signal["focus"]),
        "CORE_STACK": joined(signal["core_stack"]),
        "WEB_STACK": joined(signal["web_stack"]),
        "BUILDING": signal["building"],
        "PROJECTS": joined(signal["projects"]),
        "TOP_REPOSITORY": stats["top_repository"],
        "TOP_REPOSITORY_STARS": format_number(stats["top_repository_stars"]),
        "BLOG": profile["blog_label"],
        "EMAIL": profile["email"],
        "REPOSITORIES": format_number(stats["repositories"]),
        "STARS": format_number(stats["stars"]),
        "FOLLOWERS": format_number(stats["followers"]),
        "GITHUB_YEARS": format_number(stats["github_years"]),
        "REFRESHED_ON": stats["refreshed_on"],
    }

    output = template
    for key, value in tokens.items():
        replacement = str(value) if key == "ASCII_ART" else escape(str(value))
        output = output.replace(f"{{{{{key}}}}}", replacement)

    missing = sorted(set(PLACEHOLDER_PATTERN.findall(output)))
    if missing:
        raise ProfileGenerationError(f"Unresolved SVG placeholders: {', '.join(missing)}")
    return output


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    display = config["display"]
    cache_path = project_path(display["cache_path"])

    if args.offline:
        stats = load_cache(cache_path)
        source = "cache"
    else:
        try:
            stats = fetch_statistics(config["profile"]["username"], display["timezone"])
            save_cache(cache_path, stats)
            source = "GitHub"
        except ProfileGenerationError as error:
            if args.strict or not cache_path.exists():
                raise
            print(f"warning: {error}; using cached statistics", file=sys.stderr)
            stats = load_cache(cache_path)
            source = "cache fallback"

    template_path = project_path(display["template_path"])
    portrait_path = project_path(display["portrait_path"])
    template = template_path.read_text(encoding="utf-8")
    portrait = portrait_path.read_text(encoding="utf-8")

    outputs = {
        "dark": project_path(display["dark_output"]),
        "light": project_path(display["light_output"]),
    }
    changed: list[str] = []
    for theme_name, output_path in outputs.items():
        svg = render_svg(template, THEMES[theme_name], config, stats, portrait)
        if write_if_changed(output_path, svg):
            changed.append(str(output_path.relative_to(ROOT)))

    summary = ", ".join(changed) if changed else "no SVG changes"
    print(f"Generated from {source}: {summary}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProfileGenerationError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
