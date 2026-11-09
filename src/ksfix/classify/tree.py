"""문서 트리: 절·항 계층과 앞부분·본체·부속서·참고문헌·해설 경계."""

from __future__ import annotations

from dataclasses import dataclass, field

from ksfix.model.ir import KSDoc, Para, Role

PART_OF_ZONE = {
    "cover": "cover",
    "cover_info": "cover",
    "toc": "front",
    "foreword": "front",
    "intro": "front",
    "title": "body",
    "body": "body",
    "annex": "annex",
    "biblio": "biblio",
    "commentary": "commentary",
    "back_cover": "back_cover",
}


@dataclass
class Node:
    kind: str  # root | clause | annex | biblio | commentary
    number: str | None
    title: str | None
    level: int
    para_idx: int | None
    children: list[Node] = field(default_factory=list)
    status: str | None = None  # 부속서 (규정)/(참고)
    end_idx: int | None = None

    def walk(self):
        yield self
        for ch in self.children:
            yield from ch.walk()

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "number": self.number,
            "title": self.title,
            "level": self.level,
            "para": self.para_idx,
            "status": self.status,
            "children": [c.to_dict() for c in self.children],
        }


def build_tree(doc: KSDoc) -> Node:
    root = Node("root", None, None, 0, None)
    stack: list[Node] = [root]
    for p in doc.paras:
        if p.role == Role.ANNEX_HEADING:
            del stack[1:]
            node = Node(
                "annex",
                p.attrs.get("letter"),
                p.attrs.get("annex_title"),
                1,
                p.idx,
                status=p.attrs.get("status"),
            )
            root.children.append(node)
            stack.append(node)
        elif p.role in (Role.BIBLIO_TITLE, Role.COMMENTARY_TITLE):
            del stack[1:]
            kind = "biblio" if p.role == Role.BIBLIO_TITLE else "commentary"
            node = Node(kind, None, p.text.strip(), 1, p.idx)
            root.children.append(node)
            stack.append(node)
        elif p.role == Role.HEADING and p.attrs.get("number"):
            number = p.attrs["number"]
            level = number.count(".") + 1
            in_annex = len(stack) > 1 and stack[1].kind == "annex" and number[:1].isalpha()
            if in_annex:
                level = number.count(".") + 1  # A.1 → 2 (부속서 자체가 1)
            else:
                if len(stack) > 1 and stack[1].kind in ("annex", "biblio", "commentary"):
                    del stack[1:]
            while len(stack) > 1 and stack[-1].level >= level:
                stack.pop()
            node = Node("clause", number, p.attrs.get("title"), level, p.idx)
            stack[-1].children.append(node)
            stack.append(node)
        cur = stack[-1]
        p.clause_no = cur.number if cur.kind in ("clause", "annex") else None
    return root


def compute_parts(doc: KSDoc) -> dict[str, list[int]]:
    """부분별 [첫 문단, 마지막 문단] (빈 문단 제외)."""
    parts: dict[str, list[int]] = {}
    for p in doc.paras:
        if p.role == Role.EMPTY:
            continue
        part = PART_OF_ZONE.get(p.attrs.get("zone", ""), None)
        if part is None:
            continue
        if part not in parts:
            parts[part] = [p.idx, p.idx]
        else:
            parts[part][1] = p.idx
    return parts


def headings(doc: KSDoc, *, annex: bool | None = None) -> list[Para]:
    out = []
    for p in doc.paras:
        if p.role != Role.HEADING or not p.attrs.get("number"):
            continue
        is_annex = p.attrs.get("zone") == "annex"
        if annex is None or annex == is_annex:
            out.append(p)
    return out
