"""불변성 검증(INV-01·03): 기술적 내용(수치·표준번호·단위·표 셀 값)이 바뀌지 않았는지.

허용된 정규화만 같은 것으로 본다: 공백(일반·줄바꿈 없는·얇은), '~'→'∼', 천 단위 쉼표/공백,
소수 쉼표→마침표, '.5'→'0.5', '°C'→'℃', 'x'→'×', 표준번호의 쌍점 앞뒤 공백.
"""

from __future__ import annotations

import io
import re
import zipfile
from collections import Counter

from lxml import etree

from ksfix.classify import patterns as pt
from ksfix.model.ir import OBJ, KSDoc, Role
from ksfix.model.ns import W_NS

SPACES_RE = re.compile(r"[\s     ]+")
NUM_RE = re.compile(r"\d{1,3}(?:[ ,]\d{3})+(?:\.\d+)?|\d+(?:[.,]\d+)?|(?<![\w.])\.\d+")
UNIT_TOKENS = [
    "mm", "cm", "km", "µm", "μm", "nm", "kg", "mg", "kN", "MPa", "kPa", "GPa", "kV", "mV", "mA",
    "kW", "MW", "kHz", "MHz", "GHz", "Hz", "dB", "mL", "℃", "%", "Ω", "lx", "rpm",
]  # fmt: skip
UNIT_RE = re.compile("|".join(re.escape(u) for u in sorted(UNIT_TOKENS, key=len, reverse=True)))
EXCLUDE_ROLES = {Role.EMPTY}


UNIT_ALT = "|".join(re.escape(u) for u in sorted(UNIT_TOKENS, key=len, reverse=True))
RANGE_BOTH_RE = re.compile(rf"(\d+(?:[.,]\d+)?) ?({UNIT_ALT}) ?∼ ?(\d+(?:[.,]\d+)?) ?\2")
RANGE_PAREN_RE = re.compile(rf"\( ?(\d+(?:[.,]\d+)?) ?∼ ?(\d+(?:[.,]\d+)?) ?\) ?({UNIT_ALT})")
LABEL_RE = re.compile(r"^ ?(?:비 ?고|보 ?기|참 ?고) ?\d{1,2}(?=\s)")


def normalize(text: str) -> str:
    t = text.replace(OBJ, " ")
    t = SPACES_RE.sub(" ", t)
    t = (
        t.replace("~", "∼")
        .replace("～", "∼")
        .replace("〜", "∼")
        .replace("－", "∼")
        .replace("–", "∼")
    )
    t = t.replace("°C", "℃").replace("° C", "℃")
    # 허용된 표기 변환: 범위의 단위 반복('10 ℃ ∼ 40 ℃' = '10 ∼ 40 ℃' = '(10 ∼ 40) ℃'), 비고·보기 라벨 번호
    t = RANGE_BOTH_RE.sub(r"\1 ∼ \3 \2", t)
    t = RANGE_PAREN_RE.sub(r"\1 ∼ \2 \3", t)
    t = LABEL_RE.sub("비고", t)
    return t


def _norm_number(tok: str) -> str:
    tok = tok.replace(" ", "")
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", tok):
        tok = tok.replace(",", "")
    tok = tok.replace(",", ".")
    if tok.startswith("."):
        tok = "0" + tok
    return tok


def text_tokens(text: str, in_table: bool = False) -> Counter:
    t = normalize(text)
    c: Counter = Counter()
    for m in pt.STD_NO_RE.finditer(t):
        std = re.sub(r"\s*[:：]\s*", ":", re.sub(r"\s+", " ", m.group()).strip())
        c[("STD", std)] += 1
    t2 = pt.STD_NO_RE.sub(" ", t)
    for m in NUM_RE.finditer(t2):
        c[("NUM", _norm_number(m.group()))] += 1
    for m in UNIT_RE.finditer(t2):
        c[("UNIT", m.group())] += 1
    if in_table:
        cell = re.sub(r"\s+", "", t).replace("x", "×")
        if cell:
            c[("CELL", cell)] += 1
    return c


def doc_tokens(doc: KSDoc) -> Counter:
    total: Counter = Counter()
    for p in doc.paras:
        if p.role in EXCLUDE_ROLES:
            continue
        total.update(text_tokens(p.text, p.in_table))
    return total


def diff(before: Counter, after: Counter, allowed_extra: Counter | None = None) -> dict:
    extra = allowed_extra or Counter()
    added = after - before - extra
    removed = before - after

    def fmt(c: Counter) -> dict[str, int]:
        return {f"{k[0]}:{k[1]}": v for k, v in c.items()}

    return {"added": fmt(added), "removed": fmt(removed)}


def is_clean(d: dict) -> bool:
    return not d["added"] and not d["removed"]


# ── INV-03: 출력 docx 무결성 ─────────────────────────────
REV_TAGS = ("ins", "del", "moveFrom", "moveTo", "pPrChange", "rPrChange")


def integrity_problems(data: bytes) -> list[str]:
    problems: list[str] = []
    try:
        import docx

        docx.Document(io.BytesIO(data))
    except Exception as exc:
        return [f"python-docx로 다시 열 수 없습니다: {exc}"]
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = z.namelist()
        parsed = {}
        for name in names:
            if name.endswith(".xml") or name.endswith(".rels"):
                try:
                    parsed[name] = etree.fromstring(z.read(name))
                except etree.XMLSyntaxError as exc:
                    problems.append(f"XML 오류: {name}: {exc}")
    doc_xml = parsed.get("word/document.xml")
    if doc_xml is None:
        return problems + ["word/document.xml이 없습니다."]
    ns = {"w": W_NS}
    rev_ids = [
        el.get(f"{{{W_NS}}}id") for tag in REV_TAGS for el in doc_xml.iter(f"{{{W_NS}}}{tag}")
    ]
    dup = [k for k, v in Counter(rev_ids).items() if v > 1]
    if dup:
        problems.append(f"변경추적 ID 중복: {dup[:5]}")
    comments = parsed.get("word/comments.xml")
    comment_ids = (
        [el.get(f"{{{W_NS}}}id") for el in comments.findall("w:comment", ns)]
        if comments is not None
        else []
    )
    dupc = [k for k, v in Counter(comment_ids).items() if v > 1]
    if dupc:
        problems.append(f"메모 ID 중복: {dupc[:5]}")
    clash = set(comment_ids) & set(rev_ids)
    if clash:
        problems.append(f"메모와 변경추적 ID 충돌: {sorted(clash)[:5]}")
    refs = {el.get(f"{{{W_NS}}}id") for el in doc_xml.iter(f"{{{W_NS}}}commentReference")}
    missing = refs - set(comment_ids)
    if missing:
        problems.append(f"본문이 없는 메모 참조: {sorted(missing)[:5]}")
    starts = Counter(el.get(f"{{{W_NS}}}id") for el in doc_xml.iter(f"{{{W_NS}}}commentRangeStart"))
    ends = Counter(el.get(f"{{{W_NS}}}id") for el in doc_xml.iter(f"{{{W_NS}}}commentRangeEnd"))
    if starts != ends:
        problems.append("메모 범위 시작·끝 짝이 맞지 않습니다.")
    return problems
