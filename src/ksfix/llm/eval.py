"""ksfix eval: 합성 골드셋으로 LLM 프로필별 문장 말미 판정 정확도를 잰다(모델 비종속 입증)."""

from __future__ import annotations

import datetime as dt
import json
import time
from collections import Counter
from pathlib import Path

from ksfix.llm.config import make_client
from ksfix.llm.tasks.modal_verbs import CATEGORIES, judge

GOLD_CATS = [c for c in CATEGORIES if c != "판단보류"]


def load_gold(path: str | Path) -> list[dict]:
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            rows.append(json.loads(line))
    return rows


def evaluate_profile(name: str, gold: list[dict], batch_size: int = 6, client=None) -> dict:
    client = client or make_client(name)
    if client is None:
        raise ValueError(f"'{name}'은(는) LLM 끔 프로필이라 평가할 수 없습니다.")
    items = [{"id": g["id"], "text": g["text"], "where": "", "role": "body"} for g in gold]
    t0 = time.perf_counter()
    js = judge(client, items, batch_size=batch_size)
    elapsed = time.perf_counter() - t0
    confusion: dict[str, Counter] = {c: Counter() for c in GOLD_CATS}
    correct = comp_total = comp_correct = held = 0
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
    return {
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


def to_markdown(results: list[dict], gold_path: str) -> str:
    today = dt.date.today().isoformat()
    lines = [
        "# LLM 문장 말미 판정 평가 (T1, KS A 0001 부속서 I)",
        "",
        f"- 일자: {today} · 골드셋: `{gold_path}`(합성 {results[0]['n'] if results else 0}문장, 유형별 10) · "
        "프롬프트: `modal_verbs.v1` · temperature 0",
        "- 정확도 = 조항 유형(요구사항·권고사항·허용·가능성/역량·외적 제약·설명) 일치 비율. "
        "판단보류는 오답으로 센다. 적합성 정확도 = 모델이 낸 '적합 여부'가 정답과 같은 비율",
        "",
        "## 요약",
        "",
        "| 프로필 | 모델 | 정확도 | 적합성 정확도 | 판단보류 | 문장당 시간(초) |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        comp = (
            "-" if r["compliance_accuracy"] is None else f"{100 * r['compliance_accuracy']:.0f} %"
        )
        lines.append(
            f"| {r['profile']} | {r['model']} | {100 * r['accuracy']:.0f} % | {comp} | {r['held']} | "
            f"{r['sec_per_sentence']} |"
        )
    for r in results:
        lines += ["", f"## {r['profile']} ({r['model']}) — 유형별 정확도·혼동행렬", ""]
        head = "| 정답 \\ 예측 | " + " | ".join(CATEGORIES) + " | 정확도 |"
        lines += [head, "|" + "---|" * (len(CATEGORIES) + 2)]
        for c in GOLD_CATS:
            cells = " | ".join(str(r["confusion"][c].get(p, 0)) for p in CATEGORIES)
            acc = r["per_category"][c]
            lines.append(f"| {c} | {cells} | {'-' if acc is None else f'{100 * acc:.0f} %'} |")
    lines.append("")
    return "\n".join(lines)


def run_eval(profiles: list[str], gold_path: str, out_dir: str) -> list[dict]:
    gold = load_gold(gold_path)
    results = [evaluate_profile(p, gold) for p in profiles]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "modal_verbs_eval.md").write_text(to_markdown(results, gold_path), encoding="utf-8")
    (out / "modal_verbs_eval.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return results
