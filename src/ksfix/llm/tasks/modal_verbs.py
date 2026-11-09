"""T1 문장 말미 판정(부속서 I): 정규식이 고른 후보 문장을 LLM이 유형 판정·말미 교정.

가드레일: temperature 0, JSON만, 스키마 검증(1회 재시도), 제안 문장은 원문과 앞부분 일치(공통 접두 비율 ≥ 0.7,
'반드시' 삭제는 예외 허용), 숫자·단위·표준번호가 바뀌면 폐기 → '판단보류'.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from functools import cache
from importlib import resources

from ksfix.fix.invariants import text_tokens
from ksfix.llm.base import LLMError

PROMPT_VERSION = (
    "modal_verbs.v2"  # v1 = 계획서 부록 F 원본(예시가 단건 출력이라 일부 모델이 첫 문장만 답함)
)
CATEGORIES = ("요구사항", "권고사항", "허용", "가능성/역량", "외적 제약", "설명", "판단보류")
SCHEMA = {"required": ["items"], "list": "items", "item_required": ["id", "category"]}
SCHEMA_LOOSE: dict = {}  # 모양은 normalize_items에서 정규화한다
PREFIX_MIN = 0.7
# 문장 경계: '다.'·'요.' 등 뒤의 마침표, 물음표·느낌표(소수점 '1.5'는 경계가 아님)
BOUNDARY_RE = re.compile(r"(?<=[가-힣)\]”\"])[.。](?=\s|$)|[?!](?=\s|$)")


@dataclass
class Judgment:
    id: str
    text: str
    category: str
    compliant: bool | None
    suggestion: str | None
    reason: str
    confidence: float
    model: str
    rejected: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@cache
def load_prompt() -> tuple[str, str]:
    name = f"{PROMPT_VERSION}.md"
    text = resources.files("ksfix.llm.prompts").joinpath(name).read_text(encoding="utf-8")
    sys_part, user_part = text.split("[사용자]", 1)
    return sys_part.replace("[시스템]", "", 1).strip(), user_part.strip()


def split_sentences(text: str) -> list[tuple[int, int, str]]:
    """(시작, 끝, 문장) — 끝 마침표 포함, 앞뒤 공백 제외."""
    out = []
    start = 0
    for m in BOUNDARY_RE.finditer(text):
        end = m.end()
        out.append((start, end))
        start = end
    if start < len(text):
        out.append((start, len(text)))
    res = []
    for a, b in out:
        seg = text[a:b]
        lead = len(seg) - len(seg.lstrip())
        trail = len(seg) - len(seg.rstrip())
        if seg.strip():
            res.append((a + lead, b - trail, seg.strip()))
    return res


def prefix_ratio(a: str, b: str) -> float:
    n = 0
    for x, y in zip(a, b, strict=False):
        if x != y:
            break
        n += 1
    return n / len(a) if a else 0.0


def guard(original: str, suggestion: str | None) -> tuple[bool, str | None]:
    if not suggestion or suggestion.strip() == original.strip():
        return False, None
    if text_tokens(original) != text_tokens(suggestion):
        return False, "숫자·단위·표준번호가 바뀌는 제안이라 폐기"
    if prefix_ratio(original, suggestion) >= PREFIX_MIN:
        return True, None
    if suggestion == re.sub(r"반드시\s+", "", original, count=1):
        return True, None
    return False, "문장 앞부분이 바뀌는 제안이라 폐기(서술어만 고칠 수 있음)"


def _conf(x: object) -> float:
    try:
        return max(0.0, min(1.0, float(x)))
    except (TypeError, ValueError):
        return 0.0


def _ask(llm, system: str, tmpl: str, batch: list[dict]) -> dict[str, dict]:
    payload = [
        {
            "id": it["id"],
            "text": it["text"],
            "위치": it.get("where", ""),
            "역할": it.get("role", ""),
        }
        for it in batch
    ]
    user = (
        tmpl.replace("{clause_no}", "항목별 '위치' 참조")
        .replace(" {clause_title}", "")
        .replace("{role}", "항목별 '역할' 참조")
        .replace("{count}", str(len(batch)))
        .replace("{items_json}", json.dumps(payload, ensure_ascii=False))
    )
    resp = llm.complete_json(
        system, user, SCHEMA_LOOSE, temperature=0.0, prompt_version=PROMPT_VERSION
    )
    return {str(x.get("id")): x for x in normalize_items(resp)}


def normalize_items(resp: object) -> list[dict]:
    """{"items":[…]} 외에 단일 객체·배열·다른 키 이름으로 온 응답도 받아들인다."""
    if isinstance(resp, list):
        return [x for x in resp if isinstance(x, dict)]
    if not isinstance(resp, dict):
        return []
    if isinstance(resp.get("items"), list):
        return [x for x in resp["items"] if isinstance(x, dict)]
    if "id" in resp and "category" in resp:
        return [resp]
    for v in resp.values():
        if isinstance(v, list) and v and isinstance(v[0], dict) and "category" in v[0]:
            return [x for x in v if isinstance(x, dict)]
    return []


def judge(llm, items: list[dict], batch_size: int = 8) -> dict[str, Judgment]:
    """items: [{id, text, where, role}] → {id: Judgment}. LLM 오류는 '판단보류'로.

    묶음 응답에서 빠진 문장은 한 문장씩 다시 묻는다(일부 모델은 첫 문장만 답한다).
    """
    system, tmpl = load_prompt()
    out: dict[str, Judgment] = {}
    model = getattr(llm, "model", "") or getattr(llm, "name", "")
    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        try:
            by_id = _ask(llm, system, tmpl, batch)
        except LLMError:
            by_id = {}
        errors: dict[str, str] = {}
        for it in batch:
            if str(it["id"]) in by_id:
                continue
            try:
                by_id.update(_ask(llm, system, tmpl, [it]))
            except LLMError as exc:
                errors[str(it["id"])] = f"LLM 오류: {exc}"
        for it in batch:
            x = by_id.get(str(it["id"]))
            if x is None:
                why = errors.get(str(it["id"]), "응답 누락")
                out[it["id"]] = Judgment(
                    it["id"], it["text"], "판단보류", None, None, "", 0.0, model, why
                )
                continue
            cat = x.get("category") if x.get("category") in CATEGORIES else "판단보류"
            sugg = x.get("suggestion") or None
            ok, why = guard(it["text"], sugg) if sugg else (False, None)
            compliant = x.get("compliant") if isinstance(x.get("compliant"), bool) else None
            j = Judgment(
                id=it["id"],
                text=it["text"],
                category=cat,
                compliant=compliant,
                suggestion=sugg if ok else None,
                reason=str(x.get("reason") or "")[:200],
                confidence=_conf(x.get("confidence")),
                model=model,
                rejected=why,
            )
            if sugg and not ok:
                j.category = "판단보류"
            out[it["id"]] = j
    return out
