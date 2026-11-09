"""번호 규칙: NUM-01(절 번호 연속), NUM-02(항 하나뿐), NUM-03(5단계), NUM-06(부속서), NUM-07(그림·표 번호)."""

from __future__ import annotations

import re

from ksfix.classify import patterns as pt
from ksfix.classify.tree import Node
from ksfix.model.ir import KSDoc, Role
from ksfix.rules.context import RuleContext
from ksfix.rules.packs.ksa0001_2023.common import finding
from ksfix.rules.registry import rule


def _walk(node: Node):
    for ch in node.children:
        yield ch
        yield from _walk(ch)


@rule("NUM-01")
def clause_numbers_continuous(doc: KSDoc, ctx: RuleContext):
    if doc.tree is None:
        return
    tops = [n for n in doc.tree.children if n.kind == "clause" and n.number and n.number.isdigit()]
    if not tops:
        return
    first = doc.paras[tops[0].para_idx]
    if tops[0].number != "1" or first.attrs.get("clause_kind") != "scope":
        yield finding(
            ctx,
            "NUM-01",
            first,
            None,
            None,
            f"절 번호는 적용범위를 1로 시작합니다(첫 절: {tops[0].number} {tops[0].title or ''}).",
        )
    for prev, cur in zip(tops, tops[1:], strict=False):
        if int(cur.number) != int(prev.number) + 1:
            yield finding(
                ctx,
                "NUM-01",
                doc.paras[cur.para_idx],
                None,
                None,
                f"절 번호가 이어지지 않습니다({prev.number} 다음 {cur.number}).",
            )


@rule("NUM-02")
def single_subclause(doc: KSDoc, ctx: RuleContext):
    if doc.tree is None:
        return
    for node in _walk(doc.tree):
        if node.kind not in ("clause", "annex"):
            continue
        kids = [c for c in node.children if c.kind == "clause"]
        if len(kids) == 1 and kids[0].para_idx is not None:
            label = node.number if node.kind == "clause" else f"부속서 {node.number}"
            yield finding(
                ctx,
                "NUM-02",
                doc.paras[kids[0].para_idx],
                None,
                None,
                f"같은 단계에 항이 하나뿐입니다({label} 아래 {kids[0].number}만 있음). 항은 둘 이상이어야 합니다.",
            )


@rule("NUM-03")
def max_depth(doc: KSDoc, ctx: RuleContext):
    for p in doc.paras:
        num = p.attrs.get("number") if p.role == Role.HEADING else None
        if not num:
            continue
        depth = num.count(".") + 1
        if not num[:1].isalpha() and depth > 5:
            yield finding(
                ctx, "NUM-03", p, None, None, f"세분은 5단계까지입니다({num}은 {depth}단계)."
            )


@rule("NUM-06")
def annex_numbering(doc: KSDoc, ctx: RuleContext):
    letters: list[str] = []
    current: str | None = None
    for p in doc.paras:
        if p.role == Role.ANNEX_HEADING:
            letter = p.attrs.get("letter")
            current = letter
            if not letter:
                continue
            if letter in letters:
                yield finding(ctx, "NUM-06", p, None, None, f"부속서 {letter}가 두 번 나옵니다.")
            elif letters and letter < letters[-1]:
                yield finding(
                    ctx,
                    "NUM-06",
                    p,
                    None,
                    None,
                    f"부속서는 A부터 순서대로 둡니다(부속서 {letters[-1]} 다음에 부속서 {letter}).",
                )
            elif not letters and letter != "A":
                yield finding(
                    ctx, "NUM-06", p, None, None, f"첫 부속서는 부속서 A입니다(부속서 {letter})."
                )
            letters.append(letter)
            if not p.attrs.get("status"):
                yield finding(
                    ctx,
                    "NUM-06",
                    p,
                    None,
                    None,
                    f"부속서 {letter} 다음 행에 (규정) 또는 (참고)를 표시합니다.",
                )
            if not p.attrs.get("annex_title"):
                yield finding(ctx, "NUM-06", p, None, None, f"부속서 {letter}에 제목이 없습니다.")
            continue
        if current is None or p.attrs.get("zone") != "annex":
            continue
        if p.role == Role.HEADING and p.attrs.get("number"):
            num = p.attrs["number"]
            if num[:1].isalpha() and num[:1] != current:
                yield finding(
                    ctx,
                    "NUM-06",
                    p,
                    None,
                    None,
                    f"부속서 {current} 안의 항 번호는 {current}.1처럼 씁니다({num}).",
                )
        elif p.role in (Role.TABLE_CAPTION, Role.FIGURE_CAPTION):
            m = pt.CAPTION_RE.match(p.text.strip())
            if m and not m.group("num")[:1].isalpha():
                kind = m.group("kind")
                yield finding(
                    ctx,
                    "NUM-06",
                    p,
                    None,
                    None,
                    f"부속서 {current}의 {kind} 번호는 '{kind} {current}.1'처럼 씁니다({kind} {m.group('num')}).",
                )


def _seq_findings(ctx: RuleContext, doc: KSDoc, role: Role, word: str):
    groups: dict[str, list[tuple[int, int]]] = {}
    for p in doc.paras:
        if p.role != role:
            continue
        m = pt.CAPTION_RE.match(p.text.strip())
        if not m or "(계속)" in p.text:
            continue
        num = m.group("num")
        mm = re.fullmatch(r"(?:([A-Z])\.)?(\d+)", num)
        if not mm:
            continue
        groups.setdefault(mm.group(1) or "", []).append((int(mm.group(2)), p.idx))
    for prefix, items in groups.items():
        expect = 1
        seen: set[int] = set()
        for n, idx in items:
            label = f"{prefix}.{n}" if prefix else str(n)
            if n in seen:
                yield finding(
                    ctx,
                    "NUM-07",
                    doc.paras[idx],
                    None,
                    None,
                    f"{word} {label} 번호가 두 번 쓰였습니다.",
                )
            elif n != expect:
                want = f"{prefix}.{expect}" if prefix else str(expect)
                yield finding(
                    ctx,
                    "NUM-07",
                    doc.paras[idx],
                    None,
                    None,
                    f"{word} 번호는 1부터 이어서 붙입니다({word} {want} 자리에 {word} {label}).",
                )
            seen.add(n)
            expect = max(expect, n) + 1


FORMULA_SUB_RE = re.compile(r"\(\s*(?:[A-Z]\.)?\d+[a-z]\s*\)\s*$")


@rule("NUM-07")
def figure_table_numbers(doc: KSDoc, ctx: RuleContext):
    yield from _seq_findings(ctx, doc, Role.TABLE_CAPTION, "표")
    yield from _seq_findings(ctx, doc, Role.FIGURE_CAPTION, "그림")
    for p in doc.by_role(Role.FORMULA):
        if FORMULA_SUB_RE.search(p.text.replace("￼", " ")):
            yield finding(ctx, "NUM-07", p, None, None, "식 번호를 (2a)처럼 세분하지 않습니다.")
