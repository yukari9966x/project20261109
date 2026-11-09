"""수정 적용: 편집 계획 → 문서 XML 변경(변경추적/반영본) → 메모 → 저장."""

from __future__ import annotations

import datetime as dt
import io
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from ksfix.fix import paragraphs as para_ops
from ksfix.fix import styles as style_ops
from ksfix.fix.comments import Commenter, comment_text
from ksfix.fix.invariants import text_tokens
from ksfix.fix.planner import Decision
from ksfix.fix.revisions import Revisions
from ksfix.fix.settings import set_update_fields
from ksfix.fix.textedit import EditError, apply_text_edit, isolate, refresh
from ksfix.model.ir import KSDoc, Para

STYLE_KEYS = {
    "body": ["Normal"],
    "heading1": ["heading 1"],
    "table_caption": ["[KSDT] 표제목"],
    "figure_caption": ["[KSDT] 그림제목"],
}


@dataclass
class ApplyResult:
    data: bytes | None
    audit: list[dict] = field(default_factory=list)
    comments: int = 0
    applied: int = 0
    suggested: int = 0
    allowed_extra: Counter = field(default_factory=Counter)


def _label(d: Decision) -> str:
    f = d.finding
    if d.action == "apply":
        return "자동수정"
    if f.source == "llm":
        return f"AI 제안 · {f.llm_model or '모델'} · 신뢰도 {f.confidence:.2f}"
    if f.extra.get("needs_judgement"):
        return "판단 필요"
    if f.fix is not None:
        return "제안"
    return "검토 필요"


def _style_id(doc: KSDoc, key: str | None) -> str | None:
    if not key:
        return None
    for name in STYLE_KEYS.get(key, [key]):
        sid = doc.styles.find_by_name(name)
        if sid:
            return sid
    return None


def _audit(d: Decision, mode: str, before: str | None, after: str | None) -> dict:
    f = d.finding
    return {
        "time": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "rule_id": f.rule_id,
        "block": f.block,
        "action": d.action,
        "kind": f.fix.kind if f.fix else None,
        "before": before,
        "after": after,
        "reason": d.reason,
        "mode": mode,
        "source": f.source,
        "model": f.llm_model,
    }


def _anchor_suggestion(commenter: Commenter, p: Para, f, text: str) -> None:
    if (
        f.start is not None
        and f.end is not None
        and f.end > f.start
        and p.is_editable(f.start, f.end)
    ):
        try:
            runs = isolate(p, f.start, f.end)
            refresh(p)
            commenter.add_range(runs[0], runs[-1], text)
            return
        except EditError:
            refresh(p)
    commenter.add_paragraph(p.xml, text)


def apply_decisions(
    doc: KSDoc,
    decisions: list[Decision],
    mode: str,
    *,
    date: str | None = None,
    comment_applied: bool = True,
) -> ApplyResult:
    """doc.docx(python-docx Document)를 제자리에서 바꾸고 저장한 bytes를 돌려준다."""
    document = doc.docx
    rev = Revisions(document, date=date)
    commenter = Commenter(document, rev)
    res = ApplyResult(data=None)
    want_comments = mode == "tracked" or not comment_applied

    # 1) 제안·보고 메모(편집 전에 범위를 잡는다. 이후 런 분할에도 범위가 유지된다)
    for d in decisions:
        f = d.finding
        if d.action == "apply":
            continue
        res.suggested += 1
        res.audit.append(_audit(d, mode, f.snippet, f.suggestion))
        f.status = "suggested" if f.fix is not None else "reported"
        if mode == "report":
            continue
        _anchor_suggestion(commenter, doc.paras[f.block], f, comment_text(f, _label(d)))

    # 2) 텍스트 편집: 문단별로 뒤에서부터
    by_para: dict[int, list[Decision]] = {}
    for d in decisions:
        if d.action == "apply" and d.finding.fix and d.finding.fix.kind == "replace_text":
            if d.covered_by:
                d.finding.status = "fixed"
                res.audit.append(_audit(d, mode, d.finding.snippet, d.finding.suggestion))
                continue
            by_para.setdefault(d.finding.fix.target, []).append(d)
    for idx, ds in by_para.items():
        p = doc.paras[idx]
        for d in sorted(ds, key=lambda x: x.finding.fix.start or 0, reverse=True):
            fx = d.finding.fix
            start = fx.start or 0
            end = fx.end if fx.end is not None else len(p.text)
            before = p.text[start:end]
            try:
                d.anchors = apply_text_edit(p, start, end, fx.text or "", mode, rev)
            except EditError as exc:
                d.action, d.reason = "suggest", f"편집 실패: {exc}"
                d.finding.status = "suggested"
                _anchor_suggestion(commenter, p, d.finding, comment_text(d.finding, "제안"))
                res.audit.append(_audit(d, mode, before, fx.text))
                continue
            d.finding.status = "fixed"
            res.applied += 1
            res.audit.append(_audit(d, mode, before, fx.text))
            if want_comments and comment_applied and mode == "tracked" and d.anchors:
                commenter.add_range(
                    d.anchors[0], d.anchors[-1], comment_text(d.finding, "자동수정")
                )

    # 3) 문단 서식·이동·삽입·설정
    for d in decisions:
        f = d.finding
        fx = f.fix
        if d.action != "apply" or fx is None or fx.kind == "replace_text":
            continue
        p = doc.paras[fx.target]
        created: list[Any] = []
        if fx.kind == "set_style":
            sid = _style_id(doc, fx.style)
            if sid is None:
                d.action, d.reason = "suggest", f"스타일 없음: {fx.style}"
            else:
                style_ops.set_style(p.xml, sid, mode, rev)
        elif fx.kind == "set_alignment":
            style_ops.set_alignment(p.xml, (fx.props or {}).get("jc", "center"), mode, rev)
        elif fx.kind in ("insert_paragraph_after", "insert_paragraph_before"):
            texts = (fx.text or "").split("\n")
            where = "after" if fx.kind.endswith("after") else "before"
            created = para_ops.insert_paragraphs(
                p.xml, texts, where, _style_id(doc, fx.style), mode, rev
            )
            for t in texts:
                res.allowed_extra.update(text_tokens(t))
        elif fx.kind == "move_paragraph":
            target = doc.paras[(fx.props or {})["to"]]
            where = (fx.props or {}).get("where", "before")
            created = [para_ops.move_paragraph(p.xml, target.xml, where, mode, rev)]
        elif fx.kind == "delete_paragraph":
            para_ops.delete_paragraph(p.xml, mode, rev)
        elif fx.kind == "set_doc_setting":
            set_update_fields(document)
        if d.action != "apply":
            f.status = "suggested"
            _anchor_suggestion(commenter, p, f, comment_text(f, "제안"))
            res.audit.append(_audit(d, mode, f.snippet, f.suggestion))
            continue
        f.status = "fixed"
        res.applied += 1
        res.audit.append(_audit(d, mode, f.snippet, f.suggestion or fx.text))
        if mode == "tracked" and comment_applied:
            if created:
                commenter.add_paragraph(created[0], comment_text(f, "자동수정"))
            elif fx.kind != "set_doc_setting":
                commenter.add_paragraph(p.xml, comment_text(f, "자동수정"))

    if res.applied and doc.meta.get("has_toc_field"):
        set_update_fields(document)
    res.comments = commenter.count
    if mode != "report":
        buf = io.BytesIO()
        document.save(buf)
        res.data = buf.getvalue()
    return res
