#!/usr/bin/env bash
# 공공 GitLab으로 전체 이력·태그를 그대로 올린다(계획서 §8.3). 사용자 확인 후에만 실행한다.
#   export GITLAB_URL="https://gitlab.aigov.go.kr/<네임스페이스>/ksfix.git"
#   bash scripts/push_gitlab.sh
# 사용자 이름 = GitLab 아이디, 비밀번호 = 개인 액세스 토큰(Git 자격 증명 입력 창에만 입력).
# 현재 브랜치를 GitLab의 main으로 올린다(GITLAB_BRANCH로 바꿀 수 있음).
set -euo pipefail
: "${GITLAB_URL:?GITLAB_URL을 지정하세요. 예: https://gitlab.aigov.go.kr/<네임스페이스>/ksfix.git}"
TARGET_BRANCH="${GITLAB_BRANCH:-main}"
FREEZE_TAG="${FREEZE_TAG:-v1.0.0}"

case "$GITLAB_URL" in
  *@*) echo "GITLAB_URL에 아이디·토큰을 넣지 마세요(자격 증명 창으로만 입력)."; exit 1 ;;
  https://*) ;;
  *) echo "GITLAB_URL은 https:// 주소여야 합니다."; exit 1 ;;
esac
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "커밋되지 않은 변경이 있습니다."; exit 1
fi
if git log --all --name-only --pretty=format: | grep -qi "local_samples/"; then
  echo "이력에 local_samples/ 파일이 있습니다. 푸시를 중단합니다."; exit 1
fi
if command -v gitleaks >/dev/null 2>&1; then
  gitleaks detect --no-banner
elif git log -p --all | grep -nEi "(api[_-]?key|token|secret|password)[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9_\-]{16,}" >/dev/null; then
  echo "이력에 비밀값으로 보이는 줄이 있습니다. 확인 후 다시 실행하세요:"
  echo "  git log -p --all | grep -nEi '(api[_-]?key|token|secret|password)'"
  exit 1
fi
python scripts/check.py

git remote get-url gitlab >/dev/null 2>&1 || git remote add gitlab "$GITLAB_URL"
if [ "$(git remote get-url gitlab)" != "$GITLAB_URL" ]; then
  echo "gitlab 원격 주소가 GITLAB_URL과 다릅니다: $(git remote get-url gitlab)"; exit 1
fi
if git ls-remote --tags gitlab "refs/tags/$FREEZE_TAG" | grep -q "$FREEZE_TAG"; then
  echo "GitLab에 이미 동결 태그 $FREEZE_TAG가 있습니다. 동결 이후에는 푸시하지 않습니다(계획서 §8.6)."; exit 1
fi
git push gitlab "HEAD:refs/heads/$TARGET_BRANCH"
git push gitlab --tags
echo "GitLab 푸시 완료: $(git rev-parse HEAD) → $TARGET_BRANCH ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
echo "다음: GitLab 설정(보호 브랜치·보호 태그·Topics) 후 'git remote remove gitlab'으로 원격을 지웁니다."
