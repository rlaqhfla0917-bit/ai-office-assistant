"""
Agent가 호출하는 개별 Tool들.
각 Tool은 "입력 -> 출력" 이 명확한 독립 함수로, Planner가 조합해서 사용합니다.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
import vector_store


def rag_tool(query: str) -> str:
    """비정형 검색: 회의록/규정 문서에서 관련 내용을 찾아 텍스트로 반환."""
    hits = vector_store.search(query, top_k=3)
    if not hits:
        return "관련 문서를 찾지 못했습니다."
    return "\n".join(f"- {h['text'][:200]}" for h in hits)


def sql_tool_get_tasks(person_name: str, only_pending: bool = False) -> list[dict]:
    """정형 조회: 특정 인물의 업무 목록을 조회."""
    rows = db.get_tasks_by_person_name(person_name, only_pending=only_pending)
    return [dict(r) for r in rows]


def sql_tool_get_leaves(date: str) -> list[dict]:
    """정형 조회: 특정 날짜에 연차/휴가인 사람 목록."""
    rows = db.get_people_on_leave(date)
    return [dict(r) for r in rows]


def sql_tool_get_tasks_due_between(
    start_date: str, end_date: str, person_name: str | None = None
) -> list[dict]:
    """정형 조회: 특정 기간의 마감 업무. person_name 지정 시 해당 담당자로 제한."""
    rows = db.get_tasks_due_between(start_date, end_date, person_name=person_name)
    return [dict(r) for r in rows]


def sql_tool_get_task(task_id: int) -> dict | None:
    """정형 조회: task_id로 업무와 담당자 정보를 확인 (권한 검사/승인 미리보기용)."""
    row = db.get_task_by_id(task_id)
    return dict(row) if row else None


def sql_tool_update_task_status(task_id: int, status: str) -> bool:
    """정형 쓰기: 업무 상태값 갱신 (예: 완료 처리)."""
    return db.update_task_status(task_id, status)


def mail_tool_draft(to_name: str, subject: str, body: str) -> dict:
    """
    메일 초안 생성. 실제 발송은 하지 않고 초안만 반환한다.
    (되돌리기 어려운 행동이므로 Planner가 사용자 승인을 받은 뒤 별도로 send를 호출해야 함)
    """
    return {"to": to_name, "subject": subject, "body": body, "status": "draft"}


def mail_tool_send(draft: dict) -> dict:
    """
    실제 발송 단계. 데모에서는 실제 SMTP 연동 대신 콘솔 출력으로 대체.
    실제 구현 시 smtplib 또는 이메일 서비스 API(SendGrid 등)로 교체.
    """
    print(f"\n[메일 발송] To: {draft['to']} | Subject: {draft['subject']}")
    print(f"  Body: {draft['body']}\n")
    return {**draft, "status": "sent"}
