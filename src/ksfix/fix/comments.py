"""Word 메모: python-docx 1.2.0 Comments로 본문을 만들고, 범위 표시는 직접 넣는다.

범위 표시(commentRangeStart/End)와 참조 런은 w:ins 같은 변경추적 요소 바깥에 둔다
(삽입을 거절해도 메모가 고아가 되지 않게). 기존 메모는 건드리지 않는다.
"""

from __future__ import annotations

from typing import Any

from lxml import etree

from ksfix.fix.revisions import AUTHOR, INITIALS, Revisions
from ksfix.model.ns import w


class Commenter:
    def __init__(self, document: Any, rev: Revisions):
        self.document = document
        self.rev = rev
        self.count = 0
        self._comments = None

    @property
    def comments(self) -> Any:
        if self._comments is None:
            self._comments = self.document.comments
        return self._comments

    def _new(self, text: str) -> int:
        c = self.comments.add_comment(text=text, author=AUTHOR, initials=INITIALS)
        cid = self.rev.new_id()
        c._comment_elm.id = cid
        self.count += 1
        return cid

    def add_range(self, first: Any, last: Any, text: str) -> int:
        """first~last 요소(같은 부모 또는 같은 문단 안)를 메모 범위로."""
        cid = self._new(text)
        start = etree.Element(w("commentRangeStart"))
        start.set(w("id"), str(cid))
        end = etree.Element(w("commentRangeEnd"))
        end.set(w("id"), str(cid))
        first.addprevious(start)
        last.addnext(end)
        end.addnext(_reference_run(cid))
        return cid

    def add_paragraph(self, p: Any, text: str) -> int:
        """문단 전체를 범위로(필드 등 런을 나눌 수 없는 경우)."""
        children = [c for c in p if c.tag != w("pPr")]
        if not children:
            run = etree.SubElement(p, w("r"))
            children = [run]
        return self.add_range(children[0], children[-1], text)


def _reference_run(cid: int) -> Any:
    run = etree.Element(w("r"))
    ref = etree.SubElement(run, w("commentReference"))
    ref.set(w("id"), str(cid))
    return run


def comment_text(finding: Any, status_label: str) -> str:
    head = f"[{finding.rule_id} · {finding.clause_ref}]"
    tail = f"({status_label})"
    body = finding.message
    if finding.suggestion and finding.suggestion not in body and status_label != "자동수정":
        body += f" 제안: {finding.suggestion}"
    return f"{head} {body} {tail}"
