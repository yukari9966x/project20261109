# 오픈소스 고지 (THIRD_PARTY_NOTICES)

`python scripts/gen_notices.py`로 생성 · KS-Fix가 실행할 때 쓰는 패키지(`pip install ".[web,llm]"` 기준)와 라이선스.
모두 허용형(permissive) 라이선스이며, LLM 호출은 표준 라이브러리(urllib)만 써서 추가 의존성이 없다.

## 실행 의존성

| 패키지 | 버전 | 라이선스 | 용도 |
|---|---|---|---|
| annotated-doc | 0.0.5 | MIT | 웹(FastAPI·uvicorn) |
| annotated-types | 0.8.0 | MIT | 웹(FastAPI·uvicorn) |
| anyio | 4.16.0 | MIT | 웹(FastAPI·uvicorn) |
| click | 8.5.1 | BSD-3-Clause | 웹(FastAPI·uvicorn) |
| fastapi | 0.162.2 | MIT | 웹(FastAPI·uvicorn) |
| h11 | 0.16.0 | MIT License | 웹(FastAPI·uvicorn) |
| idna | 3.20 | BSD-3-Clause | 웹(FastAPI·uvicorn) |
| Jinja2 | 3.1.6 | BSD License | 코어 |
| lxml | 6.1.3 | BSD-3-Clause | 코어 |
| MarkupSafe | 3.0.4 | BSD-3-Clause | 코어 |
| opentelemetry-api | 1.45.2 | Apache-2.0 | 웹(FastAPI·uvicorn) |
| pydantic | 2.14.3 | MIT | 웹(FastAPI·uvicorn) |
| pydantic_core | 2.50.4 | MIT | 웹(FastAPI·uvicorn) |
| python-docx | 1.2.0 | MIT License | 코어 |
| python-multipart | 0.0.33 | Apache-2.0 | 웹(FastAPI·uvicorn) |
| PyYAML | 6.0.3 | MIT License | 코어 |
| starlette | 1.10.0 | BSD-3-Clause | 웹(FastAPI·uvicorn) |
| typing_extensions | 4.16.0 | PSF-2.0 | 코어 |
| typing-inspection | 0.4.5 | MIT | 웹(FastAPI·uvicorn) |
| uvicorn | 0.54.0 | BSD-3-Clause | 웹(FastAPI·uvicorn) |

## 함께 쓰지만 이 저장소에 포함하지 않는 구성요소

| 구성요소 | 라이선스 | 비고 |
|---|---|---|
| PyInstaller(Windows 실행파일 빌드) | GPL-2.0-or-later + 부트로더 예외 | 부트로더 예외에 따라 만든 실행파일은 자유롭게 배포할 수 있다. 실행파일 zip에는 PyInstaller 부트로더가 들어 있다 |
| Pyodide 0.27.2(브라우저 데모) | MPL-2.0 | 브라우저 데모가 CDN(cdn.jsdelivr.net)에서 내려받아 실행한다. 데모 페이지에는 포함하지 않는다 |
| python:3.12-slim(Docker 기반 이미지) | PSF-2.0 및 Debian 패키지 라이선스 | Docker 이미지를 만들 때 내려받는다 |
| Ollama | MIT | LLM 기능(선택)을 쓸 때 사용자가 따로 설치한다 |
| EXAONE 3.5 7.8B(LG AI연구원) | EXAONE AI Model License Agreement 1.1 - NC(비상업) | 평가·시연용. 모델 파일은 이 도구에 포함하지 않으며 사용자가 직접 받는다. 업무 활용 시 라이선스 확인 필요 |
| Gemma 3 4B(Google) | Gemma Terms of Use | 평가·시연용. 모델 파일은 포함하지 않는다 |

KS 표준 문서(KS A 0001:2023 등)는 저작권 보호 대상이므로 저장소에 넣지 않는다. 규칙 설명은 조항 번호와 요약만 쓰고,
도구 기능에 꼭 필요한 정형문(KS A 0001:2023 6.1.3·6.4.1·6.4.2·부속서 E·N)만 `src/ksfix/assets/boilerplate.yaml`에 담았다.
