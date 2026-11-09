"""문서의 상대 링크가 실제 파일을 가리키는지 확인(README·docs·examples)."""

import re

from tests.conftest import ROOT

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def _md_files():
    files = [ROOT / "README.md", ROOT / "CHANGELOG.md", ROOT / "THIRD_PARTY_NOTICES.md"]
    for sub in ("docs", "examples"):
        files += sorted((ROOT / sub).rglob("*.md"))
    return [p for p in files if p.is_file()]


def test_relative_links_resolve():
    broken = []
    for md in _md_files():
        text = md.read_text(encoding="utf-8")
        text = re.sub(r"```.*?```", "", text, flags=re.S)  # 코드 블록 안은 링크가 아님
        for target in LINK_RE.findall(text):
            if re.match(r"^(https?:|mailto:|#)", target):
                continue
            path = target.split("#", 1)[0]
            if path and not (md.parent / path).exists():
                broken.append(f"{md.relative_to(ROOT)} → {target}")
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
