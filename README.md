# AI 업무비서 — 사내 정보 조회부터 후속 업무 실행까지

직원이 자연어로 질문하면 질문의 성격에 따라 **SQL DB(정형 데이터)** 또는 **Vector DB(RAG, 비정형 문서)** 를 선택해 조회하고,
메일 발송·업무 상태 변경처럼 실제 업무에 영향을 주는 작업은 **LangGraph `interrupt()`** 로 실행을 멈춘 뒤
**사용자 승인 후 재개**하는 생성형 AI 업무비서 프로젝트입니다.

> KT AIVLE School 프로젝트를 포트폴리오용으로 재구성했습니다. Mock 모드를 기본 제공해 LLM API 키 없이 흐름을 확인할 수 있습니다.

## 데모로 확인할 수 있는 기능

| 질문 예시 | 처리 방식 |
|---|---|
| "오늘 연차자 누구야?" | SQL DB(연차 테이블) 조건 조회 |
| "이번 주 마감 업무 뭐 있어?" | SQL DB 날짜 범위 조회. `member`는 본인 업무만, `lead`는 팀 범위 조회 |
| "출장비 규정 알려줘" | Vector DB에서 RAG 검색 (사내 규정 문서) |
| "김대리가 맡은 업무 알려줘" | SQL DB 담당자 조건 조회 |
| "그중 아직 안 끝난 거 있어?" | **멀티턴**: 직전 담당자 맥락 재사용 + 회의 문맥(RAG)·현재 업무 상태(SQL) 조합 조회 |
| "1번 업무 완료 처리해줘" | 업무 담당자 권한 확인 → `interrupt()` → 승인 후 SQL 상태 업데이트 |
| "회의 결과 김대리에게 보내줘" | 업무 조회 → **메일 초안 생성·미리보기** → `interrupt()` → 승인 후 발송 |
| (타인) "박과장 업무 알려줘" — 일반 사원이 질문 | **권한 체크**로 거부, 팀장(`lead`)은 허용 |

회의 음성(STT) → LLM 추출(요약/담당자/업무/마감일) → 엔티티 정규화(담당자 이름→사번 매핑) → 사람 검증 →
SQL/Vector DB 저장까지 전체 파이프라인이 `main.py` 한 번 실행으로 이어집니다.

## 빠른 실행

```bash
git clone https://github.com/rlaqhfla0917-bit/ai-office-assistant.git
cd meeting_agent
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

기본값은 `MOCK_MODE=true`입니다. STT/LLM 추출과 메일 발송은 데모 방식으로 동작하며,
LangGraph의 그래프·체크포인터·권한 검사·`interrupt()` 승인/재개 흐름은 실제 코드로 실행됩니다.

## 아키텍처

자연어 질문은 **LangGraph Agent**에서 의도·대화 맥락·권한을 확인한 뒤 읽기 Tool과 실행 Tool로 분기됩니다.
읽기 작업은 바로 결과를 반환하고, 메일 발송이나 업무 상태 변경 같은 쓰기 작업만 사용자 승인 게이트를 거칩니다.

자세한 구조와 설계 의도는 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) 참고.

## 프로젝트 구조

```text
meeting_agent/
├── config.py              # MOCK_MODE 등 전역 설정
├── db.py                  # SQL DB (담당자/업무/회의/연차) - SQLite
├── vector_store.py        # Vector DB (회의록/규정) - Chroma 또는 폴백
├── stt.py                 # 음성 -> 텍스트 (Whisper 연동 지점)
├── extract.py             # 텍스트 -> 요약/담당자/업무/마감일 (LLM 연동 지점)
├── entity_resolution.py   # 담당자 이름 -> 사번 매핑 + 검증(Human-in-the-loop)
├── agent/
│   ├── tools.py           # RAG / SQL 조회·쓰기 / Mail Tool
│   └── graph.py           # LangGraph Agent (의도분석·권한·멀티턴·interrupt 승인)
├── sample_data/
│   ├── meeting_transcript.txt
│   ├── policy_travel_expense.txt
│   └── policy_annual_leave.txt
├── docs/
│   └── ARCHITECTURE.md
└── main.py                # 전체 파이프라인 + Agent 데모
```

## 설계 포인트

1. **비정형/정형 데이터 분리**  
   회의 원문·요약·사내 규정은 Vector DB(RAG), 담당자·업무·마감일·상태·연차는 SQL DB로 분리했습니다. 질문과 데이터 특성에 따라 조회 방식을 선택합니다.

2. **엔티티 정규화**  
   STT/LLM 추출 결과의 "김대리" 같은 텍스트를 실제 인물 레코드와 사번으로 매핑합니다. 매칭이 모호하면 후보를 제시하고 보류합니다.

3. **Human-in-the-loop 데이터 검증**  
   회의에서 추출된 업무 정보를 저장하기 전에 사람이 확인하는 단계를 두어 잘못된 담당자·마감일이 바로 DB에 반영되지 않도록 설계했습니다.

4. **LangGraph 기반 Tool orchestration**  
   질문 의도에 따라 RAG·SQL·Mail Tool을 선택합니다. 필요한 경우 회의 문맥(RAG)과 현재 업무 상태(SQL)를 각각 조회해 하나의 응답에서 함께 사용합니다. `MemorySaver`로 `thread_id` 단위 대화 상태를 유지해 후속 질문도 처리합니다.

5. **권한 검증을 LLM 밖에서 수행**  
   권한 판단을 프롬프트에만 맡기지 않고 Tool 실행 전에 코드로 검증합니다. `member`는 본인 업무만 조회·변경할 수 있고, `lead`는 팀 범위를 확인할 수 있습니다. 담당자가 명시되지 않은 "이번 주 마감 업무"도 일반 사용자는 본인 범위로 제한됩니다.

6. **실행 전 승인 게이트**  
   읽기 작업은 승인 없이 처리하지만 메일 발송·업무 상태 변경은 `interrupt()`로 그래프를 멈춥니다. 메일은 **초안을 먼저 생성해 사용자에게 보여준 뒤**, `Command(resume=...)`로 승인된 경우에만 발송합니다.

## 실제 서비스로 전환하는 법

| 항목 | 현재(Mock 모드) | 실제 전환 |
|---|---|---|
| STT | 샘플 텍스트 기반 데모 | `stt.py`의 OpenAI Whisper 호출부 사용 |
| 구조화 추출 | 규칙 기반 더미 JSON | `extract.py`의 LLM JSON 출력 사용 |
| Vector DB | 키워드 겹침 폴백 | `MOCK_MODE=false` + Chroma 사용 |
| Agent 의도 분석 | 정규식 규칙 (`classify_node`) | 동일 그래프 구조에서 LLM tool/function calling으로 교체 |
| 메일 발송 | 콘솔 출력 | `mail_tool_send`를 SMTP/메일 API로 교체 |
| 사용자 승인 | CLI 데모에서 승인 여부 입력/자동 처리 | 웹 UI·Slack/Teams 버튼과 `resume(thread_id, approved=...)` 연결 |

`.env.example`을 `.env`로 복사하고 `OPENAI_API_KEY`를 설정한 뒤 `MOCK_MODE=false python main.py`로 실행하면
실제 LLM/STT 호출 경로를 사용할 수 있습니다.

## 로드맵

- 승인 UI를 웹/Slack/Teams와 연결해 비동기 Human-in-the-loop 구현
- 연차 조회에서 신청/승인 업무까지 확장
- LLM 기반 의도 분류 및 structured tool calling 적용
- 마감 임박 업무 자동 탐지·알림 배치 추가

## 라이선스

MIT License — 자세한 내용은 [LICENSE](LICENSE) 참고.
