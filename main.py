"""
전체 파이프라인 데모 (LangGraph Agent 버전).

실행: python main.py

흐름:
  1) 음성(mock) -> STT -> 회의 텍스트
  2) LLM 추출 -> 요약/담당자/업무/마감일
  3) 엔티티 정규화 (담당자 이름 -> 사번 매핑)
  4) Human-in-the-loop 검증 (자동 승인 모드)
  5) 저장 (SQL DB + Vector DB) + 연차/규정 데모 데이터 적재
  6) LangGraph Agent에게 질문을 던져서 응답 확인
     - 읽기 전용 질문: 바로 응답
     - 메일 발송 / 업무 완료처리: interrupt로 멈췄다가 승인 후 재개
     - 권한 없는 조회: 거부
     - 후속 질문("그중 ~"): 직전 맥락 재사용
"""
from datetime import date, timedelta

import db
import stt
import extract
import entity_resolution
import vector_store
from agent import graph as agent_graph


def setup_demo_people():
    db.seed_people([
        {"emp_no": "E001", "name": "김대리", "role": "member"},
        {"emp_no": "E002", "name": "박과장", "role": "lead"},
    ])


def setup_demo_leaves():
    today = date.today().isoformat()
    db.seed_leaves([
        {"name": "박과장", "leave_date": today, "leave_type": "annual"},
    ])


def setup_demo_due_range_tasks():
    """'이번 주 마감 업무' 데모를 위해 오늘 기준 가까운 마감일의 업무를 추가로 심어둔다."""
    meeting_id = db.save_meeting("추가 업무 등록", "", "날짜 범위 조회 데모용")
    soon = (date.today() + timedelta(days=2)).isoformat()
    db.save_task(meeting_id, "박과장", "분기 보고서 초안", soon, assignee_id=2)


def ingest_policy_documents():
    for path, label in [
        ("sample_data/policy_travel_expense.txt", "출장비 규정"),
        ("sample_data/policy_annual_leave.txt", "연차 규정"),
    ]:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        vector_store.add_document(doc_id=label, text=text, metadata={"type": "policy"})


def ingest_meeting(audio_path: str = "sample_data/meeting.wav"):
    print("=" * 60)
    print("STEP 1-2. STT + 회의 내용 추출")
    print("=" * 60)
    raw_text = stt.transcribe(audio_path)
    extracted = extract.extract_structured(raw_text)

    print("\nSTEP 3. 엔티티 정규화")
    for task in extracted["tasks"]:
        resolution = entity_resolution.resolve_assignee(task["assignee"])
        if resolution["status"] == "matched":
            task["_assignee_id"] = resolution["person"]["id"]
            print(f"  '{task['assignee']}' -> 사번 {resolution['person']['emp_no']} 매핑 완료")
        else:
            task["_assignee_id"] = None
            print(f"  '{task['assignee']}' -> 매칭 실패/모호, 담당자 미지정 상태로 저장")

    print("\nSTEP 4. 추출 결과 검증 (Human-in-the-loop)")
    confirmed = entity_resolution.review_and_confirm_extraction(extracted, auto_approve=True)

    print("STEP 5. 저장 (SQL DB + Vector DB)")
    meeting_id = db.save_meeting(confirmed["title"], raw_text, confirmed["summary"])
    for task in confirmed["tasks"]:
        db.save_task(
            meeting_id=meeting_id,
            raw_assignee_name=task["assignee"],
            description=task["description"],
            due_date=task["due_date"],
            assignee_id=task.get("_assignee_id"),
        )
    vector_store.add_document(
        doc_id=f"meeting_{meeting_id}",
        text=f"{confirmed['title']}\n{confirmed['summary']}\n{raw_text}",
        metadata={"meeting_id": meeting_id},
    )
    print(f"  회의 #{meeting_id} 저장 완료 (업무 {len(confirmed['tasks'])}건)\n")


def ask_and_print(question: str, thread_id: str, requester_name: str, requester_role: str,
                   auto_approve: bool = True):
    """LangGraph Agent에게 질문하고, 승인이 필요하면 미리보기를 보여준 뒤 자동 승인/거부로 재개."""
    print(f"\n>>> [{requester_name}/{requester_role}] 질문: {question}")
    result = agent_graph.ask(question, thread_id=thread_id,
                              requester_name=requester_name, requester_role=requester_role)

    if result["status"] == "needs_approval":
        print(f"[승인 대기] {result['preview']}")
        decision = auto_approve
        print(f"[사용자 응답] {'승인' if decision else '거부'} (데모 자동 처리)")
        result = agent_graph.resume(thread_id, approved=decision)

    print(result["answer"])


def demo_questions():
    print("=" * 60)
    print("STEP 6. 사용자 질문 -> LangGraph Agent 응답")
    print("=" * 60)

    # 김대리 본인 스레드 (멀티턴 맥락 유지는 같은 thread_id 안에서만 적용)
    t1 = "thread-kim"
    ask_and_print("오늘 연차자 누구야?", t1, requester_name="김대리", requester_role="member")
    ask_and_print("이번 주 마감 업무 뭐 있어?", t1, requester_name="김대리", requester_role="member")
    ask_and_print("출장비 규정 알려줘", t1, requester_name="김대리", requester_role="member")
    ask_and_print("김대리가 맡은 업무 알려줘", t1, requester_name="김대리", requester_role="member")
    ask_and_print("그중 아직 안 끝난 거 있어?", t1, requester_name="김대리", requester_role="member")  # 멀티턴: '그중' -> 직전 담당자(김대리) 재사용
    ask_and_print("1번 업무 완료 처리해줘", t1, requester_name="김대리", requester_role="member")       # 승인 필요 -> interrupt
    ask_and_print("회의 결과 김대리에게 보내줘", t1, requester_name="김대리", requester_role="member")  # 승인 필요 -> interrupt

    print("\n" + "-" * 60)
    print("권한 체크 데모: 일반 사원이 타인 업무 조회 시도")
    print("-" * 60)
    t2 = "thread-kim-2"
    ask_and_print("박과장 업무 알려줘", t2, requester_name="김대리", requester_role="member")  # 거부

    t3 = "thread-lead"
    ask_and_print("박과장 업무 알려줘", t3, requester_name="팀장", requester_role="lead")      # 팀장은 허용


if __name__ == "__main__":
    db.init_db()
    setup_demo_people()
    setup_demo_leaves()
    ingest_policy_documents()
    ingest_meeting()
    setup_demo_due_range_tasks()
    demo_questions()
