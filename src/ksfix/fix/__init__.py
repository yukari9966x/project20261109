"""수정 엔진: 편집 계획 → 변경추적/반영본 → 메모 → 불변성 검증."""

from ksfix.fix.engine import ApplyResult, apply_decisions
from ksfix.fix.planner import Decision, plan

__all__ = ["ApplyResult", "Decision", "apply_decisions", "plan"]
