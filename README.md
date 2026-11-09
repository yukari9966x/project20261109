# KS-Fix — KS A 0001 표준안 서식 자동교정 AI

> 한국산업표준(KS) 표준안(docx)을 KS A 0001:2023(표준의 서식과 작성방법)에 맞춰 점검하고,
> 근거 조항이 달린 Word 변경추적으로 교정하는 도구입니다. (개발 중 — 진행 상황: [docs/PROGRESS.md](docs/PROGRESS.md))

## 접속 주소
- 온라인 데모(브라우저, 규칙 기능): 준비 중
- 로컬 실행 후: http://127.0.0.1:8765

## 주요 기능
준비 중

## 빠른 실행 (pip / Docker)
pip(Python 3.11 이상):
```bash
pip install -e ".[web]"
```
```bash
ksfix serve --open
```
Docker:
```bash
docker compose up --build
```
브라우저에서 http://127.0.0.1:8765 를 연다. 명령줄만 쓸 때는 아래 "사용 방법"을 본다.

## 사용 방법 (웹 3단계 · CLI 예시)
웹: ① docx 올리기 → ② 출력(변경추적본·반영본·점검만) 선택 → ③ 결과 확인 후 변경추적본·리포트 내려받기

CLI:
```bash
ksfix fix samples/sample_01_violations.docx -o out --mode tracked
```
```bash
ksfix check samples/sample_02_clean.docx -o out
```
```bash
ksfix inspect samples/sample_03_messy_styles.docx
```
```bash
ksfix rules
```

## LLM 연결·교체 방법
준비 중 — 기본값은 LLM 끔(규칙만으로 동작)

## 모의데이터
준비 중 — `samples/`에 합성 표준안을 둡니다.

## 구조
상세 설계: [docs/PLAN.md](docs/PLAN.md)

## 신뢰성·보안 설계
준비 중

## 알려진 제약
준비 중

## 라이선스 · 오픈소스 고지 · 참고한 자료
MIT(가칭, 소속기관 확인 후 확정) — [LICENSE](LICENSE)

## 개발 경위
준비 중
