# AI 업무비서 2.0 — 2026-10-19 로컬 검증 결과

검증 환경: Python 3.13, FastAPI TestClient, `pytest`; 비용이 발생하는 외부 서비스는 사용하지 않았습니다.

## 자동화 검증

`python -m pytest -q`: **28개 테스트 통과**

검증한 시나리오: 로컬 무료 모드, 사내 규정 키워드 조회, 업무·팀장 권한 분리, 회의록 미리보기·승인 후 저장, 미확인 담당자 저장 거부, 업무 변경 사전 승인 및 거절, 모의 발송함, 멱등 키 중복 방지·요청자 범위, 일시적 오류 재시도 후 성공, 영구 오류 3회 후 실패함(DLQ) 전환, 수동 재처리, 관리자 감사 로그, 접근 권한, 후속 질문 처리, 기존 DB 임포트 샘플 테스트, 모델 호출 분기 목 처리, 키 부재 시 유료 API 호출 차단.

## HTTP 서버 실동작 점검

`uvicorn officeops.web:app --host 127.0.0.1 --port 8542`로 로컬 실행 후 확인:

- GET / → HTTP 200 (업무비서 대시보드 페이지)
- GET /static/style.css → HTTP 200
- GET /static/app.js → HTTP 200 (JavaScript syntax: node --check 통과)
- GET /api/health → HTTP 200, offline 모드
- GET /api/people → HTTP 200
- POST /api/chat → '김대리님의 업무 2건을 찾았습니다.'
- POST /api/jobs → awaiting_approval
- POST /api/jobs/{id}/approve → queued
- POST /api/demo/worker-tick → retrying (가상 일시적 오류)
- GET /api/ops → HTTP 200 (관리자 역할)

## 아직 검증하지 않은 부분

- 실제 유료 OpenAI API 호출, 외부 음성 인식(STT)
- 운영환경의 AWS 배포 및 CloudWatch 연동
- 실제 SMTP 메일 발송 (이 버전은 모의 발송함만 구현)
- Redis 서버 기동·큐 시그널 연동, Docker Compose 통합 실행
- 실사용자 인증 및 엔터프라이즈 보안 감사
- 실제 기업 업무 데이터에서의 효과나 정량적 시간 절감

**자기소개서·포트폴리오에는 위의 구분을 유지하고, 미측정 성과를 측정한 것처럼 적지 마세요.**