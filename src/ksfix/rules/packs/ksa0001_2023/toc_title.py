"""목차·제목·표준번호 규칙: TOC-01(자동 목차), TOC-02(목차 = 실제 제목), TTL-01(제목 구분자), TTL-04(표준번호 꼴)."""

from __future__ import annotations

import re

from ksfix.classify import patterns as pt
from ksfix.model.ir import KSDoc, Role
from ksfix.rules.base import FixSpec
from ksfix.rules.context import RuleContext
from ksfix.rules.packs.ksa0001_2023.common import finding
from ksfix.rules.registry import rule


@rule("TOC-01")
def toc_is_field(doc: KSDoc, ctx: RuleContext):
    title = next((p for p in doc.paras if p.role == Role.TOC_TITLE), None)
    entries = [p for p in doc.paras if p.role == Role.TOC_ENTRY]
    if title is None or not entries:
        return
    typed = [p for p in entries if not p.attrs.get("in_toc")]
    if typed and len(typed) == len(entries):
        yield finding(
            ctx,
            "TOC-01",
            title,
            None,
            None,
            "목차를 손으로 썼습니다. Word의 자동 목차(TOC 필드)로 만들어 제목과 쪽 번호가 갱신되게 합니다.",
        )


ENTRY_RE = re.compile(
    r"^(?P<num>\d+(?:\.\d+)*)[\t ]+(?P<title>.+?)(?:\t+|[.·…]{2,}\s*|\s{2,})(?P<page>\d+|[ivxlc]+)\s*$",
    re.I,
)


@rule("TOC-02")
def toc_matches_headings(doc: KSDoc, ctx: RuleContext):
    heads = {
        p.attrs["number"]: pt.squash(p.attrs.get("title") or p.text)
        for p in doc.paras
        if p.role == Role.HEADING and p.attrs.get("number") and p.attrs.get("zone") == "body"
    }
    if not heads:
        return
    field_toc = any(p.attrs.get("in_toc") for p in doc.paras if p.role == Role.TOC_ENTRY)
    fix_given = False
    for p in doc.by_role(Role.TOC_ENTRY):
        m = ENTRY_RE.match(p.text.strip())
        if not m:
            continue
        num, title = m.group("num"), m.group("title").strip()
        actual = heads.get(num)
        if actual is not None and actual == pt.squash(title):
            continue
        if actual is None:
            msg = f"목차 항목 '{num} {title}'에 해당하는 절이 본문에 없습니다."
        else:
            msg = f"목차 항목 '{num} {title}'이(가) 본문 제목과 다릅니다. 목차를 갱신해야 합니다."
        fix = None
        if field_toc and not fix_given and not doc.meta.get("update_fields"):
            fix = FixSpec("set_doc_setting", p.idx, props={"updateFields": True})
            fix_given = True
            msg += " (Word가 문서를 열 때 목차를 갱신하도록 설정)"
        yield finding(ctx, "TOC-02", p, None, None, msg, fix=fix, toc_title=title, number=num)


SEP_RE = re.compile(r"(?<=\S)(?:[ \t]+[-–ㅡ―—][ \t]*|[ \t]*[-–ㅡ―—][ \t]+|—)(?=\S)")


@rule("TTL-01")
def title_separator(doc: KSDoc, ctx: RuleContext):
    for p in doc.paras:
        if p.role not in (Role.TITLE_KO, Role.TITLE_EN):
            continue
        for m in SEP_RE.finditer(p.text):
            if m.group() == " — ":
                continue
            yield finding(
                ctx,
                "TTL-01",
                p,
                m.start(),
                m.end(),
                f"제목 요소 사이는 줄표(—) 앞뒤를 한 칸씩 띄워 구분합니다('{m.group().strip() or m.group()}' → ' — ').",
                fix=FixSpec("replace_text", p.idx, m.start(), m.end(), text=" — "),
                suggestion=" — ",
            )


STD_LINE_RE = re.compile(
    r"^(?P<pre>KS)\s*(?P<cls>[A-Z])\s*(?P<org>(?:ISO/IEC|ISO|IEC)\s*)?(?P<no>[0-9A-Z][\d\-\s]*?)\s*(?:[:：]\s*(?P<year>\d{4}))?$"
)


@rule("TTL-04")
def std_number_line(doc: KSDoc, ctx: RuleContext):
    for p in doc.paras:
        if p.role != Role.STD_NUMBER:
            continue
        text = p.text.strip()
        m = STD_LINE_RE.match(text)
        if not m:
            continue
        org = f"{m.group('org').strip()} " if m.group("org") else ""
        no = re.sub(r"\s*-\s*", "-", m.group("no").strip())
        want = f"KS {m.group('cls')} {org}{no}" + (f":{m.group('year')}" if m.group("year") else "")
        if want == text:
            continue
        lead = len(p.text) - len(p.text.lstrip())
        yield finding(
            ctx,
            "TTL-04",
            p,
            lead,
            lead + len(text),
            f"표준번호는 'KS C IEC 60974-11:2021'처럼 씁니다('{text}' → '{want}').",
            fix=FixSpec("replace_text", p.idx, lead, lead + len(text), text=want),
            suggestion=want,
        )
