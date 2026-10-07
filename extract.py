"""
회의 텍스트 -> 구조화 데이터 추출.
실제 서비스에서는 LLM에게 "JSON만 출력하라"고 강하게 지시한 뒤 파싱합니다.
MOCK_MODE 에서는 데모 트랜스크립트에 맞춘 규칙 기반 결과를 반환합니다.
"""
import json
from config import MOCK_MODE, OPENAI_API_KEY, LLM_MODEL

EXTRACTION_SYSTEM_PROMPT = """\
당신은 회의록에서 정보를 추출하는 어시스턴트입니다.
아래 회의 원문을 읽고 반드시 JSON 형식으로만 응답하세요. 다른 텍스트는 절대 포함하지 마세요.

출력 형식:
{
  "title": "회의 제목",
  "summary": "3~5문장 요약",
  "decisions": ["주요 결정사항1", "주요 결정사항2"],
  "tasks": [
    {"assignee": "담당자 원문 이름", "description": "업무 내용", "due_date": "YYYY-MM-DD 또는 null"}
  ]
}
"""


def extract_structured(meeting_text: str) -> dict:
    if MOCK_MODE:
        return _mock_extract(meeting_text)

    # --- 실제 연동 예시 (openai>=1.0, function calling 대신 JSON 강제 프롬프트 사용) ---
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=LLM_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": meeting_text},
        ],
    )
    return json.loads(response.choices[0].message.content)


def _mock_extract(meeting_text: str) -> dict:
    """데모용 더미 추출 결과 (sample_data/meeting_transcript.txt 내용에 맞춤)."""
    return {
        "title": "9월 3주차 정기 회의",
        "summary": (
            "이번 회의에서는 신규 기능 배포 일정과 QA 이슈 대응 방안을 논의했습니다. "
            "김대리가 프론트엔드 버그 수정을, 박과장이 API 문서화를 맡기로 했습니다. "
            "다음 배포는 10월 첫째 주로 결정되었습니다."
        ),
        "decisions": [
            "다음 배포는 10월 첫째 주로 확정",
            "QA 이슈는 우선순위 상으로 분류하여 이번 주 내 처리",
        ],
        "tasks": [
            {"assignee": "김대리", "description": "로그인 화면 버그 수정", "due_date": "2026-09-26"},
            {"assignee": "박과장", "description": "API 문서화 초안 작성", "due_date": "2026-09-30"},
            {"assignee": "김대리", "description": "QA 리포트 정리", "due_date": "2026-09-25"},
        ],
    }
