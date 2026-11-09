# LLM 연결 안내 (LLM_SETUP)

KS-Fix는 **LLM 없이도 모든 핵심 기능이 동작**합니다(기본값: 끔). LLM을 연결하면 규칙만으로는 판단할 수 없는 문장에 AI 판정·제안이 붙습니다.

## 1. LLM이 하는 일

| 작업 | 대상 | 결과 |
|---|---|---|
| T1 문장 말미 판정(KS A 0001 부속서 I) | ‘할 수 있다’(VRB-02)·‘반드시 ~하여야 한다’(VRB-01) 후보 문장 | 유형(요구사항·권고사항·허용·가능성/역량·외적 제약·설명) + 서술어만 고친 문장 제안 + 근거·신뢰도 |
| T2 구조 분류 보조 | 규칙으로 역할을 정하지 못한 문단(신뢰도 0.6 미만) | 역할 재판정 |

- 허용(‘~해도 된다’의 뜻)으로 판정된 ‘할 수 있다’ → “수행해도 된다.” 같은 **AI 제안**(변경추적본에서는 변경추적 + `AI 제안 · 모델 · 신뢰도` 메모, 반영본에서는 메모로만)
- 가능성·역량(‘견딜 수 있다’)으로 판정 → 지적하지 않음 / ‘반드시’가 외적 제약(법령 의무)이면 적합 처리
- LLM을 끄면 같은 문장이 ‘판단 필요’(참고)로 남아 사람이 확인합니다.

안전장치

- **가드레일**: 제안 문장은 원문과 앞부분이 70 % 이상 같아야 하고(서술어만 수정, ‘반드시’ 삭제는 예외) 숫자·단위·표준번호가 하나라도 바뀌면 버립니다. 제안을 버려도 유형 판정은 남깁니다.
- temperature 0, JSON 응답 강제(지원하지 않는 서버면 자동으로 빼고 재시도), 응답 형식 검사 후 1회 재시도, 묶음 응답에서 빠진 문장은 한 문장씩 다시 묻습니다.
- 서버에 닿지 못하면(연결 실패) 남은 문장은 묻지 않고 규칙 지적으로 계속하며, 리포트 경고에 “LLM 판정 실패”를 표시합니다. 응답이 늦어 묶음 질문이 시간 초과되면 한 문장씩 다시 묻고, 한 문장도 시간 안에 끝나지 않으면 멈춥니다.
- 응답 캐시(SQLite, `.ksfix_cache/llm.sqlite`): 같은 모델·프롬프트·문장이면 다시 묻지 않아 결과가 재현됩니다. 지우려면 폴더를 삭제합니다(위치: `KSFIX_CACHE_DIR`).
- 정형문(KS A 0001이 정한 문구)은 LLM에 보내지 않습니다.

## 2. 로컬 모델 준비(Ollama, 권장)

문서가 컴퓨터 밖으로 나가지 않는 방법입니다. 평가에 쓴 모델 2종:

| 모델 | Ollama 이름 | 내려받기 크기 | 라이선스 |
|---|---|---|---|
| EXAONE 3.5 7.8B(LG AI연구원) | `exaone3.5:7.8b` | 약 4.8 GB | EXAONE AI Model License 1.1 - NC(비상업) — 업무 활용 전 확인 필요 |
| Gemma 3 4B(Google) | `gemma3:4b` | 약 3.4 GB | Gemma Terms of Use |

1. https://ollama.com 에서 Ollama를 설치하고 실행합니다(기본 주소 http://localhost:11434).
2. 모델을 받습니다.
```bash
ollama pull exaone3.5:7.8b
```
```bash
ollama pull gemma3:4b
```
3. KS-Fix에서 프로필을 고릅니다.
```bash
ksfix fix samples/sample_01_violations.docx -o out --llm ollama-exaone
```

GPU가 없으면 CPU로 동작하지만 느립니다(아래 평가표의 문장당 시간 참고). 메모리는 모델 크기 + 2 GB 이상을 권장합니다.

Docker로 Ollama를 띄울 때(설치 없이):
```bash
docker run -d --name ollama -p 127.0.0.1:11434:11434 -v ollama:/root/.ollama ollama/ollama
```
```bash
docker exec ollama ollama pull exaone3.5:7.8b
```

## 3. 프로필 설정

기본 프로필(패키지에 포함): `none`(끔) · `ollama-exaone` · `ollama-gemma` · `vllm-gptoss` · `gov-common` · `upstage-solar`.
바꾸려면 예시 파일을 복사해 고칩니다.

```bash
cp config/llm_profiles.example.yaml config/llm_profiles.yaml
```

```yaml
profiles:
  my-model:
    provider: openai_compat          # OpenAI 호환 /v1/chat/completions
    base_url: "http://localhost:11434/v1"
    model: "exaone3.5:7.8b"
    timeout: 300                     # 초(선택, 기본 300)
    json_mode: true                  # response_format=json_object 사용(선택)
  agency-api:
    provider: openai_compat
    base_url: "${AGENCY_LLM_URL}"    # ${환경변수}는 읽을 때 치환
    model: "${AGENCY_LLM_MODEL}"
    api_key_env: "AGENCY_LLM_KEY"    # 키는 파일에 쓰지 않고 환경변수 이름만
    external: true                   # 외부 전송 경고 표시
```

- 파일 위치: `KSFIX_LLM_PROFILES`(경로) → 현재 폴더의 `config/llm_profiles.yaml` → 저장소의 `config/llm_profiles.yaml` → 패키지 기본값 순으로 찾습니다.
- `base_url`이 localhost·127.0.0.1·host.docker.internal이 아니면 자동으로 **외부**로 표시합니다.
- 비밀값(API 키)은 `.env`(커밋 금지) 또는 환경변수에 둡니다. `ksfix` 명령은 현재 폴더의 `.env`를 읽습니다(이미 지정된 환경변수는 덮어쓰지 않음). 항목은 `.env.example` 참고.

환경변수로 바로 지정(프로필 파일 없이)

| 변수 | 뜻 |
|---|---|
| `KSFIX_LLM_BASE_URL`, `KSFIX_LLM_MODEL` | 둘 다 있으면 `env` 프로필이 생기고 기본값이 됩니다 |
| `KSFIX_LLM_API_KEY` | API 키(필요한 서버만) |
| `KSFIX_LLM_PROFILE` | 기본 프로필 이름(웹 UI·CLI 기본값) |
| `KSFIX_CACHE_DIR` | 응답 캐시 위치 |

## 4. 실행 형태별 사용

- **CLI**: `ksfix check|fix 파일 --llm 프로필`. 외부 프로필이면 “⚠ 외부 API 프로필입니다” 경고를 표준 오류로 출력합니다.
- **웹 UI**: ‘AI(LLM)’ 목록에서 고릅니다. 외부 프로필을 고르면 전송 경고가 나옵니다. 목록은 서버가 읽은 프로필입니다.
- **Docker**: 호스트의 Ollama를 쓰려면 `docker-compose.yml`의 `environment`에 다음을 넣고 다시 시작합니다.
  ```yaml
  KSFIX_LLM_BASE_URL: "http://host.docker.internal:11434/v1"
  KSFIX_LLM_MODEL: "exaone3.5:7.8b"
  ```
- **Windows 실행파일**: 실행파일과 같은 폴더(작업 폴더)에 `config/llm_profiles.yaml`을 두거나 환경변수를 지정합니다.
- **브라우저 데모**: LLM 기능이 없습니다.

## 5. 모델 교체와 평가(`ksfix eval`)

직접 만든 합성 문장 60개(유형별 10개, `tests/llm_gold/modal_verbs.jsonl`)로 프로필별 판정 정확도를 잽니다. 실제 KS 문서는 쓰지 않습니다.

```bash
ksfix eval --profiles ollama-exaone,ollama-gemma
```

결과는 `docs/eval/modal_verbs_eval.md`(요약·혼동행렬·틀린 문장)와 `.json`으로 저장됩니다. 기본은 캐시 없이 응답 시간까지 재고, `--cache`를 주면 저장된 응답으로 다시 채점만 합니다.

| 지표 | 뜻 |
|---|---|
| 유형 정확도 | 6개 유형 일치 비율(판단보류는 오답) |
| 허용 판별 | ‘허용’인지 아닌지 — VRB-02가 실제로 쓰는 판정 |
| ‘반드시’ 판별 | ‘반드시’ 문장이 외적 제약인지 — VRB-01이 쓰는 판정 |
| 제안 채택/폐기 | 고친 문장 제안 중 가드레일을 통과한 수/버린 수 |

현재 결과: [docs/eval/modal_verbs_eval.md](eval/modal_verbs_eval.md)

새 모델을 시험하려면 프로필을 추가하고 같은 명령에 이름을 넣으면 됩니다. 골드셋 한 줄 형식:
```json
{"id": "p02", "category": "허용", "compliant": false, "text": "이 표준의 다른 시험들은 편리한 순서에 따라 수행할 수 있다."}
```

## 6. 문제 해결

| 증상 | 확인할 것 |
|---|---|
| 리포트 경고 “LLM 판정 실패 … 연결 실패” | Ollama가 실행 중인지(`ollama list`), 주소·포트, Docker면 `host.docker.internal` |
| “응답 시간 초과” | CPU 추론이 느린 경우 프로필에 `timeout: 600`, 더 작은 모델 사용 |
| “HTTP 400 … response_format” | 자동으로 JSON 모드를 빼고 다시 묻습니다. 계속되면 프로필에 `json_mode: false` |
| 판정이 모두 ‘판단보류’ | 모델이 JSON을 내지 못하는 경우 — 다른 모델로 바꾸거나 `ksfix eval`로 확인 |
| 프로필이 목록에 없음 | `config/llm_profiles.yaml` 위치와 YAML 들여쓰기, `KSFIX_LLM_PROFILES` |

## 7. 주의

- **실제 KS 문서나 미발간 초안을 외부 API로 보내지 마십시오.** 업무 문서는 로컬 모델이나 기관 내부 API(외부 표시 확인)만 씁니다.
- AI 제안은 참고용입니다. 변경추적본에서 사람이 수락·거절해야 반영됩니다.
