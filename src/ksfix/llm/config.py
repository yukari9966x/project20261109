"""LLM 프로필 로딩: config/llm_profiles.yaml + 환경변수(${VAR} 치환, KSFIX_LLM_* 직접 지정)."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from ksfix.llm.cache import LLMCache

VAR_RE = re.compile(r"\$\{([A-Z0-9_]+)\}")
ROOT = Path(__file__).resolve().parents[3]


def _subst(value: Any) -> Any:
    if isinstance(value, str):
        return VAR_RE.sub(lambda m: os.environ.get(m.group(1), ""), value)
    return value


def profiles_path() -> Path | None:
    env = os.environ.get("KSFIX_LLM_PROFILES")
    cands = [Path(env)] if env else []
    cands += [Path.cwd() / "config" / "llm_profiles.yaml", ROOT / "config" / "llm_profiles.yaml"]
    for c in cands:
        if c.is_file():
            return c
    return None


def load_profiles() -> dict[str, dict]:
    path = profiles_path()
    if path is not None:
        text = path.read_text(encoding="utf-8")
    else:
        from ksfix.assets import read_text

        text = read_text("llm_profiles.default.yaml")
    data = yaml.safe_load(text) or {}
    profiles = {}
    for name, prof in (data.get("profiles") or {}).items():
        profiles[name] = {k: _subst(v) for k, v in (prof or {}).items()}
    profiles.setdefault("none", {"provider": "none"})
    if os.environ.get("KSFIX_LLM_BASE_URL") and os.environ.get("KSFIX_LLM_MODEL"):
        profiles["env"] = {
            "provider": "openai_compat",
            "base_url": os.environ["KSFIX_LLM_BASE_URL"],
            "model": os.environ["KSFIX_LLM_MODEL"],
            "api_key_env": "KSFIX_LLM_API_KEY",
            "external": not _is_local(os.environ["KSFIX_LLM_BASE_URL"]),
        }
    return profiles


def _is_local(url: str) -> bool:
    return bool(
        re.match(
            r"https?://(localhost|127\.0\.0\.1|\[::1\]|host\.docker\.internal)([:/]|$)", url or ""
        )
    )


def list_profiles() -> list[dict]:
    out = []
    for name, p in load_profiles().items():
        external = bool(p.get("external")) or (
            p.get("provider") == "openai_compat" and not _is_local(p.get("base_url", ""))
        )
        out.append(
            {
                "name": name,
                "provider": p.get("provider", "none"),
                "model": p.get("model") or None,
                "external": external,
            }
        )
    return out


def default_profile_name() -> str:
    return os.environ.get("KSFIX_LLM_PROFILE") or (
        "env" if os.environ.get("KSFIX_LLM_BASE_URL") else "none"
    )


def make_client(name: str | None = None, *, cache_dir: str | Path | None = None):
    """프로필 이름 → LLM 클라이언트(끔이면 None)."""
    name = name or default_profile_name()
    profiles = load_profiles()
    if name not in profiles:
        raise KeyError(f"LLM 프로필 '{name}'이(가) 없습니다. 가능한 값: {', '.join(profiles)}")
    p = profiles[name]
    provider = p.get("provider", "none")
    if provider == "none":
        return None
    if provider != "openai_compat":
        raise ValueError(f"지원하지 않는 공급자: {provider}")
    from ksfix.llm.openai_compat import OpenAICompatClient

    key_env = p.get("api_key_env")
    api_key = os.environ.get(key_env) if key_env else None
    api_key = api_key or os.environ.get("KSFIX_LLM_API_KEY") or None
    base_url = p.get("base_url", "")
    external = bool(p.get("external")) or not _is_local(base_url)
    cache_root = cache_dir or os.environ.get("KSFIX_CACHE_DIR") or (Path.cwd() / ".ksfix_cache")
    cache = LLMCache(Path(cache_root) / "llm.sqlite") if cache_root != "memory" else LLMCache(None)
    return OpenAICompatClient(
        f"{name}/{p.get('model')}",
        base_url,
        p.get("model", ""),
        api_key=api_key,
        external=external,
        timeout=float(p.get("timeout", 300)),
        cache=cache,
        json_mode=bool(p.get("json_mode", True)),
    )
