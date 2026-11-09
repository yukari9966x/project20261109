"""ksfix eval: 합성 골드셋으로 LLM 프로필별 문장 말미 판정 정확도를 잰다(모델 비종속 입증)."""

from __future__ import annotations

import datetime as dt
import json
import time
from collections import Counter
from pathlib import Path

from ksfix.llm.config import make_client
from ksfix.llm.tasks.modal_verbs import CATEGORIES, PROMPT_VERSION, judge

GOLD_CATS = [c for c in CATEGORIES if c != "판단보류"]


def load_gold(path: str | Path) -> list[dict]:
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            rows.append(json.loads(line))
    return rows


def evaluate_profile(
    name: str, gold: list[dict], batch_size: int = 6, client=None, use_cache: bool = False
) -> dict:
    client = client or make_client(name, cache_dir=None if use_cache else "memory")
    if client is None:
        raise ValueError(f"'{name}'은(는) LLM 끔 프로필이라 평가할 수 없습니다.")
    items = [{"id": g["id"], "text": g["text"], "where": "", "role": "body"} for g in gold]
    t0 = time.perf_counter()
    js = judge(client, items, batch_size=batch_size)
    elapsed = time.perf_counter() - t0
    confusion: dict[str, Counter] = {c: Counter() for c in GOLD_CATS}
    correct = comp_total = comp_correct = held = 0
    perm = Counter()  # 허용 판별(VRB-02가 쓰는 이진 판정)
    must = Counter()  # '반드시' 문장의 외적 제약 판별(VRB-01)
    sugg_ok = sugg_rejected = 0
    rows = []
    for g in gold:
        j = js[g["id"]]
        confusion[g["category"]][j.category] += 1
        ok = j.category == g["category"]
        correct += ok
        held += j.category == "판단보류"
        if j.compliant is not None:
            comp_total += 1
            comp_correct += j.compliant == g["compliant"]
        g_perm, p_perm = g["category"] == "허용", j.category == "허용"
        perm["tp" if g_perm and p_perm else "fn" if g_perm else "fp" if p_perm else "tn"] += 1
        if "반드시" in g["text"]:
            must["total"] += 1
            must["ok"] += (j.category == "외적 제약") == (g["category"] == "외적 제약")
        sugg_ok += j.suggestion is not None
        sugg_rejected += j.rejected is not None
        rows.append(
            {
                "id": g["id"],
                "gold": g["category"],
                "pred": j.category,
                "ok": ok,
                "compliant_gold": g["compliant"],
                "compliant_pred": j.compliant,
                "suggestion": j.suggestion,
                "rejected": j.rejected,
            }
        )
    n = len(gold)
    perm_acc = (perm["tp"] + perm["tn"]) / n if n else 0.0
    return {
        "permission_accuracy": round(perm_acc, 3),
        "permission_recall": round(perm["tp"] / (perm["tp"] + perm["fn"]), 3)
        if perm["tp"] + perm["fn"]
        else None,
        "permission_false_positive": perm["fp"],
        "must_accuracy": round(must["ok"] / must["total"], 3) if must["total"] else None,
        "suggestions_used": sugg_ok,
        "suggestions_rejected": sugg_rejected,
        "cached": bool(use_cache),
        "profile": name,
        "model": getattr(client, "model", name),
        "n": n,
        "accuracy": round(correct / n, 3) if n else 0.0,
        "compliance_accuracy": round(comp_correct / comp_total, 3) if comp_total else None,
        "held": held,
        "seconds": round(elapsed, 1),
        "sec_per_sentence": round(elapsed / n, 2) if n else 0.0,
        "per_category": {
            c: round(confusion[c][c] / sum(confusion[c].values()), 2)
            if sum(confusion[c].values())
            else None
            for c in GOLD_CATS
        },
        "confusion": {c: dict(confusion[c]) for c in GOLD_CATS},
        "rows": rows,
    }


def _shown(path: str) -> str:
    try:
        return Path(path).resolve().relative_to(Path.cwd()).as_posix()
    except ValueError:
        return Path(path).name


def to_markdown(results: list[dict], gold_path: str) -> str:
    today = dt.date.today().isoformat()
    gold_path = _shown(gold_path)
    cached = any(r.get("cached") for r in results)
    lines = [
        "# LLM 문장 말미 판정 평가 (T1, KS A 0001 부속서 I)",
        "",
        f"- 일자: {today} · 골드셋: `{gold_path}`(합성 {results[0]['n'] if results else 0}문장, 유형별 10) · "
        f"프롬프트: `{PROMPT_VERSION}` · temperature 0 · 한 번에 6문장씩 묻기",
        "- 유형 정확도 = 조항 유형(요구사항·권고사항·허용·가능성/역량·외적 제약·설명) 일치 비율(판단보류는 오답). "
        "적합성 정확도 = 모델이 낸 '적합 여부'가 정답과 같은 비율",
        "- 허용 판별 = '허용'인지 아닌지(VRB-02가 실제로 쓰는 판정)의 정확도. 허용 재현율 = 허용 문장을 허용으로 본 비율, "
        "허용 오판 = 허용이 아닌데 허용으로 본 문장 수. '반드시' 판별 = '반드시'가 든 문장이 외적 제약인지(VRB-01) 맞힌 비율",
        "- 제안 채택/폐기 = 고친 문장 제안 중 가드레일(숫자·단위·표준번호 보존, 서술어만 수정)을 통과한 수/버린 수. "
        "버린 경우에도 유형 판정은 유지한다",
        "- 응답 시간: "
        + (
            "캐시된 응답으로 다시 채점해 의미 없음"
            if cached
            else "응답 캐시 없이 측정(이 컴퓨터 CPU 추론 기준)"
        ),
        "",
        "## 요약",
        "",
        "| 프로필 | 모델 | 유형 정확도 | 허용 판별 | 허용 재현율 | 허용 오판 | '반드시' 판별 "
        "| 적합성 정확도 | 판단보류 | 제안 채택/폐기 | 문장당 시간(초) |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]

    def pct(v: float | None) -> str:
        return "-" if v is None else f"{100 * v:.0f} %"

    for r in results:
        sec = "-" if r.get("cached") else r["sec_per_sentence"]
        lines.append(
            f"| {r['profile']} | {r['model']} | {pct(r['accuracy'])} | {pct(r['permission_accuracy'])} "
            f"| {pct(r['permission_recall'])} | {r['permission_false_positive']} | {pct(r['must_accuracy'])} "
            f"| {pct(r['compliance_accuracy'])} | {r['held']} "
            f"| {r['suggestions_used']}/{r['suggestions_rejected']} | {sec} |"
        )
    for r in results:
        lines += ["", f"## {r['profile']} ({r['model']}) — 유형별 정확도·혼동행렬", ""]
        head = "| 정답 \\ 예측 | " + " | ".join(CATEGORIES) + " | 정확도 |"
        lines += [head, "|" + "---|" * (len(CATEGORIES) + 2)]
        for c in GOLD_CATS:
            cells = " | ".join(str(r["confusion"][c].get(p, 0)) for p in CATEGORIES)
            acc = r["per_category"][c]
            lines.append(f"| {c} | {cells} | {pct(acc)} |")
        wrong = [x for x in r["rows"] if not x["ok"]]
        if wrong:
            lines += ["", "틀린 문장(정답 → 예측): " + ", ".join(
                f"{x['id']}({x['gold']}→{x['pred']})" for x in wrong
            )]  # fmt: skip
    lines.append("")
    return "\n".join(lines)


def run_eval(
    profiles: list[str], gold_path: str, out_dir: str, use_cache: bool = False
) -> list[dict]:
    gold = load_gold(gold_path)
    results = [evaluate_profile(p, gold, use_cache=use_cache) for p in profiles]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "modal_verbs_eval.md").write_text(to_markdown(results, gold_path), encoding="utf-8")
    (out / "modal_verbs_eval.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return results
