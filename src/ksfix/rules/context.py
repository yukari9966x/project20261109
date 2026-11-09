"""규칙 실행 문맥: 매개변수·활성 규칙·정형문·LLM 클라이언트."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ksfix.assets import boilerplate


@dataclass
class RuleContext:
    params: dict[str, dict] = field(default_factory=dict)  # rule_id → params
    active: set[str] = field(default_factory=set)
    boilerplate: dict = field(default_factory=boilerplate)
    llm: Any = None  # LLMClient(없으면 None → 규칙만)
    diagnostics: list[dict] = field(default_factory=list)
    meta: dict[str, dict] = field(default_factory=dict)  # rule_id → 카탈로그 항목
    memo: dict[str, Any] = field(
        default_factory=dict
    )  # 규칙 사이에서 한 번만 계산할 값(LLM 판정 등)

    def p(self, rule_id: str, key: str, default: Any = None) -> Any:
        return self.params.get(rule_id, {}).get(key, default)

    def whitelist(self) -> list[str]:
        """판정 대상에서 뺄 정형문(머리말 저작권 문구의 '될 수 있다' 등)."""
        bp = self.boilerplate
        out = [bp["foreword"]["issue"]["enact"], *bp["foreword"]["copyright"]]
        out += list(bp["foreword"]["patent"])
        out += [bp["normref"]["intro"], bp["terms"]["intro1"], bp["commentary"]["intro"]]
        return out
