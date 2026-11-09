"""규칙 등록(@rule)·카탈로그 검증·실행."""

from __future__ import annotations

import importlib.util
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from typing import Any

import yaml

from ksfix._paths import read_pkg_text
from ksfix.model.ir import KSDoc
from ksfix.rules.base import SEVERITY_ORDER, Finding
from ksfix.rules.context import RuleContext

DEFAULT_PACK = "ksa0001_2023"
SYSTEM_RULES = {"INV-01", "INV-02", "INV-03"}  # 수정 파이프라인(fix/invariants)이 담당

_REGISTRY: dict[str, Callable[..., Any]] = {}


def rule(rule_id: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """@rule("QTY-01") — 규칙 함수 등록."""

    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        if rule_id in _REGISTRY and _REGISTRY[rule_id] is not fn:
            raise ValueError(f"규칙 ID 중복 등록: {rule_id}")
        _REGISTRY[rule_id] = fn
        fn.rule_id = rule_id  # type: ignore[attr-defined]
        return fn

    return deco


@dataclass
class Catalog:
    pack: str
    title: str
    version: str
    categories: dict[str, str]
    rules: list[dict]

    def by_id(self) -> dict[str, dict]:
        return {r["id"]: r for r in self.rules}


@cache
def load_catalog(pack: str = DEFAULT_PACK) -> Catalog:
    text = read_pkg_text("rules", "packs", pack, "catalog.yaml")
    data = yaml.safe_load(text)
    ids = [r["id"] for r in data["rules"]]
    if len(ids) != len(set(ids)):
        raise ValueError("catalog.yaml에 중복된 규칙 ID가 있습니다.")
    for r in data["rules"]:
        r.setdefault("category", data["categories"].get(r["id"].split("-")[0], "기타"))
        r.setdefault("default", True)
    return Catalog(
        data["pack"], data["title"], str(data["version"]), data["categories"], data["rules"]
    )


def ensure_loaded(pack: str = DEFAULT_PACK) -> dict[str, Callable[..., Any]]:
    """규칙팩 모듈을 불러와 @rule 등록을 마친다. 규칙팩은 이름 문자열로 동적 import하지 않고 명시한다."""
    if pack != DEFAULT_PACK:
        raise ValueError(f"알 수 없는 규칙팩입니다: {pack}")
    from ksfix.rules.packs import ksa0001_2023  # noqa: F401  (import 시 규칙이 등록됨)

    return _REGISTRY


def validate(pack: str = DEFAULT_PACK) -> None:
    """구현된 규칙 ID가 모두 카탈로그에 있는지(1:1) 확인."""
    reg = ensure_loaded(pack)
    cat = load_catalog(pack).by_id()
    unknown = sorted(set(reg) - set(cat))
    if unknown:
        raise ValueError(f"카탈로그에 없는 규칙이 구현되어 있습니다: {unknown}")


def implemented_ids(pack: str = DEFAULT_PACK, include_system: bool = True) -> set[str]:
    ids = set(ensure_loaded(pack))
    if include_system and importlib.util.find_spec("ksfix.fix") is not None:
        ids |= SYSTEM_RULES
    return ids


def select_rules(spec: str | None, pack: str = DEFAULT_PACK) -> set[str]:
    """--rules 값: None(기본 켜진 규칙 전부) / 'P0,P0b'(우선순위) / 'QTY-01,PUN-02'(ID)."""
    validate(pack)
    cat = load_catalog(pack).by_id()
    reg = ensure_loaded(pack)
    if not spec:
        return {rid for rid in reg if cat[rid].get("default", True)}
    tokens = [t.strip() for t in spec.split(",") if t.strip()]
    out: set[str] = set()
    for tok in tokens:
        up = tok.upper()
        if up in ("P0", "P0B", "P1", "P2"):
            want = {"P0": "P0", "P0B": "P0b", "P1": "P1", "P2": "P2"}[up]
            out |= {
                rid for rid in reg if cat[rid]["priority"] == want and cat[rid].get("default", True)
            }
        elif up in reg:
            out.add(up)
        elif up.endswith("-*") or len(up) == 3:
            prefix = up.split("-")[0]
            out |= {rid for rid in reg if rid.startswith(prefix + "-")}
        else:
            raise ValueError(f"알 수 없는 규칙 또는 우선순위: {tok}")
    return out


def make_context(
    rules: set[str] | None = None, llm: Any = None, pack: str = DEFAULT_PACK
) -> RuleContext:
    cat = load_catalog(pack).by_id()
    active = rules if rules is not None else select_rules(None, pack)
    return RuleContext(
        params={rid: dict(cat[rid].get("params", {})) for rid in cat},
        active=set(active),
        llm=llm,
        meta=cat,
    )


def run_rules(doc: KSDoc, ctx: RuleContext, pack: str = DEFAULT_PACK) -> list[Finding]:
    reg = ensure_loaded(pack)
    cat = load_catalog(pack).by_id()
    findings: list[Finding] = []
    timings: dict[str, float] = {}
    for rid in sorted(ctx.active):
        fn = reg.get(rid)
        if fn is None:
            continue
        t0 = time.perf_counter()
        try:
            for f in fn(doc, ctx) or ():
                meta = cat.get(f.rule_id, {})
                f.category = f.category or meta.get("category")
                f.priority = f.priority or meta.get("priority")
                f.title = f.title or meta.get("title")
                if not f.clause_ref:
                    f.clause_ref = f"KS A 0001:2023 {meta.get('clause', '')}".strip()
                findings.append(f)
        except Exception as exc:
            ctx.diagnostics.append(
                {
                    "rule_id": "ksfix.internal",
                    "failed_rule": rid,
                    "error": f"{type(exc).__name__}: {exc}",
                    "trace": traceback.format_exc(limit=3),
                }
            )
        timings[rid] = round(time.perf_counter() - t0, 4)
    doc.meta["rule_timings"] = timings
    findings.sort(key=lambda f: (f.block, f.start or 0, SEVERITY_ORDER[f.severity], f.rule_id))
    return findings
