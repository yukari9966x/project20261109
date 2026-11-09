"""문서의 상대 링크가 실제 파일을 가리키는지 확인(README·docs·examples)."""

import re

from tests.conftest import ROOT

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def _md_files():
    files = [ROOT / "README.md", ROOT / "CHANGELOG.md", ROOT / "THIRD_PARTY_NOTICES.md"]
    for sub in ("docs", "examples"):
        files += sorted((ROOT / sub).rglob("*.md"))
    return [p for p in files if p.is_file()]


def _strip_code(text: str) -> str:
    return re.sub(r"```.*?```", "", text, flags=re.S)  # 코드 블록 안은 링크·제목이 아님


def _anchors(md) -> set[str]:
    """GitHub·GitLab 방식 제목 앵커: 소문자, 글자·숫자·공백·-·_ 외 제거, 공백 → -."""
    out = set()
    for line in _strip_code(md.read_text(encoding="utf-8")).splitlines():
        m = re.match(r"^#{1,6}\s+(.*?)\s*#*$", line)
        if m:
            out.add(re.sub(r"[^\w\- ]", "", m.group(1).strip().lower()).replace(" ", "-"))
    return out


def test_relative_links_resolve():
    broken = []
    for md in _md_files():
        for target in LINK_RE.findall(_strip_code(md.read_text(encoding="utf-8"))):
            if re.match(r"^(https?:|mailto:)", target):
                continue
            path, _, anchor = target.partition("#")
            dest = (md.parent / path) if path else md
            if not dest.exists():
                broken.append(f"{md.relative_to(ROOT)} → {target}")
            elif anchor and dest.suffix == ".md" and anchor not in _anchors(dest):
                broken.append(f"{md.relative_to(ROOT)} → {target}(제목 없음)")
    assert not broken, "깨진 링크: " + ", ".join(broken)


def test_readme_has_required_sections():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    for head in (
        "## 접속 주소",
        "## 주요 기능",
        "## 빠른 실행",
        "## 사용 방법",
        "## LLM 연결·교체",
        "## 모의데이터",
    ):
        assert head in text, head
