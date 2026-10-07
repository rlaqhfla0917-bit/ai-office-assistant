"""
LangGraph 기반 Agent.

핵심 흐름
- 자연어 질문의 의도를 분류하고 필요한 Tool을 선택
- 읽기 전용 조회는 권한 확인 후 즉시 실행
- 메일 발송 / 업무 상태 변경처럼 실제 상태를 바꾸는 작업은
  LangGraph의 interrupt()로 실행을 멈추고 사용자 승인 후 resume
- 체크포인터(MemorySaver)로 thread_id 단위 대화 상태를 유지
- requester_role 기반 접근 제어
  * 일반 사용자(member): 본인 업무만 조회/변경
  * 팀장(lead): 팀 범위 업무 조회/변경 가능
"""
import os
import re
import sys
from datetime import date, timedelta
from typing import Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent import tools


class AgentState(TypedDict, total=False):
    question: str
    requester_name: str
    requester_role: str       # "member" | "lead"
    history: list[str]
    last_person: Optional[str]
    plan: dict
    context_chunks: list[str]
    approved: Optional[bool]
    mail_draft: dict
    answer: str


NAME_RE = re.compile(r"([가-힣]{1,3}(?:대리|과장|팀장|사원|부장))")
FOLLOWUP_HINTS = ["그중", "그 중", "방금", "아까", "위에서", "그거"]


def _extract_name(question: str) -> Optional[str]:
    m = NAME_RE.search(question)
    return m.group(1) if m else None


def _this_week_range() -> tuple[str, str]:
    today = date.today()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start.isoformat(), end.isoformat()


# ---------------------------------------------------------------------------
# 노드 1: 의도 분석 (+ 멀티턴 맥락 반영)
# ---------------------------------------------------------------------------
def classify_node(state: AgentState) -> AgentState:
    q = state["question"].strip()
    history = state.get("history", [])

    person = _extract_name(q)
    if not person and any(h in q for h in FOLLOWUP_HINTS):
        person = state.get("last_person")

    if any(k in q for k in ["연차", "휴가"]) and ("누구" in q or "누가" in q):
        plan = {"type": "leave_query", "date": date.today().isoformat()}

    elif "이번 주" in q and ("마감" in q or "업무" in q):
        start, end = _this_week_range()
        plan = {"type": "due_range", "start": start, "end": end}

    elif ("완료" in q or "처리" in q) and re.search(r"(\d+)번", q):
        task_id = int(re.search(r"(\d+)번", q).group(1))
        plan = {"type": "task_complete", "task_id": task_id}

    elif "보내" in q or "메일" in q:
        plan = {"type": "mail_send", "person": person}

    elif person and any(k in q for k in ["지연", "안 끝난", "미완료", "아직"]):
        plan = {"type": "person_pending", "person": person}

    elif person:
        plan = {"type": "person_tasks", "person": person}

    else:
        plan = {"type": "policy_rag", "query": q}

    return {
        "plan": plan,
        "last_person": person or state.get("last_person"),
        "history": history + [q],
        "context_chunks": [],
        "answer": "",
        "approved": None,
        "mail_draft": {},
    }


def route_after_classify(state: AgentState) -> str:
    return "check_permission"


# ---------------------------------------------------------------------------
# 노드 2: 권한 체크
# ---------------------------------------------------------------------------
def permission_node(state: AgentState) -> AgentState:
    """
    업무 데이터 접근 규칙.
    - member: 본인 업무만 조회/변경
    - lead: 팀 범위 조회/변경 가능

    연차자 목록은 조직 내 공유 가능한 일정 정보라는 데모 가정으로 별도 제한하지 않는다.
    """
    plan = dict(state["plan"])
    requester_name = state.get("requester_name", "익명")
    requester_role = state.get("requester_role", "member")

    # "이번 주 마감 업무"처럼 담당자를 명시하지 않은 범위 조회는
    # 일반 사용자에게는 본인 업무로 자동 제한하고, lead만 팀 전체를 조회한다.
    if plan["type"] == "due_range" and requester_role != "lead":
        plan["person"] = requester_name
        return {"plan": plan}

    # 업무 상태 변경은 task_id만 들어오므로 DB에서 실제 담당자를 확인한다.
    if plan["type"] == "task_complete":
        task = tools.sql_tool_get_task(plan["task_id"])
        if not task:
            return {
                "answer": f"[업무 없음] #{plan['task_id']} 업무를 찾을 수 없습니다.",
                "plan": {**plan, "type": "denied"},
            }

        target_person = task.get("assignee_name") or task.get("raw_assignee_name")
        plan["person"] = target_person
        plan["task_description"] = task.get("description")

        if requester_role != "lead" and target_person != requester_name:
            return {
                "answer": (
                    f"[접근 거부] #{plan['task_id']} 업무는 {target_person}님의 업무입니다. "
                    "본인 또는 팀장만 상태를 변경할 수 있습니다."
                ),
                "plan": {**plan, "type": "denied"},
            }
        return {"plan": plan}

    # 특정 사람의 업무를 조회하거나 그 사람의 업무 목록을 메일로 보내는 경우
    target_person = plan.get("person")
    if plan["type"] == "mail_send" and not target_person:
        return {
            "answer": "[확인 필요] 메일로 보낼 대상자를 질문에서 확인할 수 없습니다.",
            "plan": {**plan, "type": "denied"},
        }

    if target_person and target_person != requester_name and requester_role != "lead":
        return {
            "answer": f"[접근 거부] {target_person}님의 업무는 본인 또는 팀장만 조회할 수 있습니다.",
            "plan": {**plan, "type": "denied"},
        }

    return {"plan": plan}


def route_after_permission(state: AgentState) -> str:
    if state["plan"]["type"] == "denied":
        return END
    if state["plan"]["type"] in ("mail_send", "task_complete"):
        return "approval"
    return "execute_read"


# ---------------------------------------------------------------------------
# 노드 3-a: 읽기 전용 실행
# ---------------------------------------------------------------------------
def execute_read_node(state: AgentState) -> AgentState:
    plan = state["plan"]
    chunks = []

    if plan["type"] == "leave_query":
        rows = tools.sql_tool_get_leaves(plan["date"])
        if not rows:
            chunks.append(f"[연차 DB 조회] {plan['date']} 연차자가 없습니다.")
        else:
            lines = [f"  - {r['name']} ({r['leave_type']})" for r in rows]
            chunks.append(f"[연차 DB 조회] {plan['date']} 연차자:\n" + "\n".join(lines))

    elif plan["type"] == "due_range":
        rows = tools.sql_tool_get_tasks_due_between(
            plan["start"], plan["end"], person_name=plan.get("person")
        )
        scope = f"{plan['person']}의 " if plan.get("person") else "팀 "
        if not rows:
            chunks.append(
                f"[업무 DB 조회] {plan['start']}~{plan['end']} {scope}마감 업무가 없습니다."
            )
        else:
            lines = [
                f"  #{r['id']} {r['description']} "
                f"(담당 {r['assignee_name']}, 마감 {r['due_date']}, 상태 {r['status']})"
                for r in rows
            ]
            chunks.append(
                f"[업무 DB 조회] {plan['start']}~{plan['end']} {scope}마감 업무:\n"
                + "\n".join(lines)
            )

    elif plan["type"] == "person_tasks":
        rows = tools.sql_tool_get_tasks(plan["person"], only_pending=False)
        chunks.append(_format_tasks(plan["person"], rows))

    elif plan["type"] == "person_pending":
        # 회의 문맥(RAG)과 현재 업무 상태(SQL)를 각각 조회해 한 답변에서 함께 사용한다.
        rag_result = tools.rag_tool(plan["person"])
        chunks.append(f"[회의록/문서 검색 결과]\n{rag_result}")
        rows = tools.sql_tool_get_tasks(plan["person"], only_pending=True)
        chunks.append(_format_tasks(plan["person"], rows))

    elif plan["type"] == "policy_rag":
        rag_result = tools.rag_tool(plan["query"])
        chunks.append(f"[사내 문서 검색 결과]\n{rag_result}")

    return {"context_chunks": state.get("context_chunks", []) + chunks}


def _format_tasks(person: str, rows: list[dict]) -> str:
    if not rows:
        return f"[업무 DB 조회] {person}의 업무를 찾지 못했습니다."
    lines = [
        f"  #{r['id']} {r['description']} (마감 {r['due_date']}, 상태 {r['status']})"
        for r in rows
    ]
    return f"[업무 DB 조회] {person}의 업무 목록:\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# 노드 3-b: 승인 게이트
# ---------------------------------------------------------------------------
def approval_node(state: AgentState) -> AgentState:
    """
    되돌리기 어려운 작업은 실제 실행 전에 interrupt()로 멈춘다.

    메일은 '초안을 먼저 생성 -> 초안 내용을 사용자에게 제시 -> 승인 후 발송' 순서다.
    """
    plan = state["plan"]

    if plan["type"] == "mail_send":
        rows = tools.sql_tool_get_tasks(plan["person"], only_pending=False)
        body_lines = "\n".join(
            f"- {r['description']} (마감 {r['due_date']}, 상태 {r['status']})" for r in rows
        ) or "관련 업무 없음"
        draft = tools.mail_tool_draft(
            to_name=plan["person"],
            subject=f"[회의 결과 공유] {plan['person']}님 업무 안내",
            body=f"{plan['person']}님, 정리된 업무 목록입니다.\n\n{body_lines}",
        )
        preview = (
            f"받는 사람: {draft['to']}\n"
            f"제목: {draft['subject']}\n"
            f"본문:\n{draft['body']}"
        )
        decision = interrupt({"action": "mail_send", "preview": preview})
        return {"approved": bool(decision), "mail_draft": draft}

    task = tools.sql_tool_get_task(plan["task_id"])
    description = task.get("description") if task else plan.get("task_description", "")
    target = task.get("assignee_name") if task else plan.get("person", "")
    preview = f"업무 #{plan['task_id']} '{description}' (담당 {target})를 완료 처리"
    decision = interrupt({"action": "task_complete", "preview": preview})
    return {"approved": bool(decision)}


def route_after_approval(state: AgentState) -> str:
    return "execute_action" if state.get("approved") else "synthesize"


# ---------------------------------------------------------------------------
# 노드 3-c: 승인된 쓰기 작업 실행
# ---------------------------------------------------------------------------
def execute_action_node(state: AgentState) -> AgentState:
    plan = state["plan"]
    chunks = []

    if plan["type"] == "task_complete":
        ok = tools.sql_tool_update_task_status(plan["task_id"], "done")
        chunks.append(
            f"[업무 상태 변경] #{plan['task_id']} -> done {'성공' if ok else '실패'}"
        )

    elif plan["type"] == "mail_send":
        draft = state.get("mail_draft")
        if not draft:
            # 체크포인터/실행환경 차이에 대비한 안전한 재구성 폴백
            rows = tools.sql_tool_get_tasks(plan["person"], only_pending=False)
            body_lines = "\n".join(
                f"- {r['description']} (마감 {r['due_date']}, 상태 {r['status']})" for r in rows
            ) or "관련 업무 없음"
            draft = tools.mail_tool_draft(
                to_name=plan["person"],
                subject=f"[회의 결과 공유] {plan['person']}님 업무 안내",
                body=f"{plan['person']}님, 정리된 업무 목록입니다.\n\n{body_lines}",
            )
        sent = tools.mail_tool_send(draft)
        chunks.append(f"[메일 발송 완료] {sent['to']}에게 '{sent['subject']}' 발송됨")

    return {"context_chunks": state.get("context_chunks", []) + chunks}


# ---------------------------------------------------------------------------
# 노드 4: 결과 통합
# ---------------------------------------------------------------------------
def synthesize_node(state: AgentState) -> AgentState:
    if state.get("answer"):
        return {}
    if state.get("approved") is False:
        return {"answer": "[승인 거부됨] 요청한 작업을 취소하였습니다."}
    joined = "\n\n".join(state.get("context_chunks", []))
    return {"answer": f"[답변]\n질문: {state['question']}\n\n{joined}"}


# ---------------------------------------------------------------------------
# 그래프 조립
# ---------------------------------------------------------------------------
def build_graph():
    g = StateGraph(AgentState)
    g.add_node("classify", classify_node)
    g.add_node("check_permission", permission_node)
    g.add_node("execute_read", execute_read_node)
    g.add_node("approval", approval_node)
    g.add_node("execute_action", execute_action_node)
    g.add_node("synthesize", synthesize_node)

    g.set_entry_point("classify")
    g.add_conditional_edges(
        "classify", route_after_classify, {"check_permission": "check_permission"}
    )
    g.add_conditional_edges(
        "check_permission",
        route_after_permission,
        {"execute_read": "execute_read", "approval": "approval", END: END},
    )
    g.add_edge("execute_read", "synthesize")
    g.add_conditional_edges(
        "approval",
        route_after_approval,
        {"execute_action": "execute_action", "synthesize": "synthesize"},
    )
    g.add_edge("execute_action", "synthesize")
    g.add_edge("synthesize", END)

    return g.compile(checkpointer=MemorySaver())


GRAPH = build_graph()


def ask(
    question: str,
    thread_id: str,
    requester_name: str = "익명",
    requester_role: str = "member",
) -> dict:
    """
    질문을 그래프에 넣고 실행.
    반환:
      {"status": "done", "answer": ...}
      {"status": "needs_approval", "preview": ...}
    """
    config = {"configurable": {"thread_id": thread_id}}
    result = GRAPH.invoke(
        {
            "question": question,
            "requester_name": requester_name,
            "requester_role": requester_role,
        },
        config=config,
    )
    if "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        return {"status": "needs_approval", "preview": payload["preview"]}
    return {"status": "done", "answer": result["answer"]}


def resume(thread_id: str, approved: bool) -> dict:
    """interrupt에서 멈춘 그래프를 사용자 승인 여부와 함께 재개."""
    config = {"configurable": {"thread_id": thread_id}}
    result = GRAPH.invoke(Command(resume=approved), config=config)
    return {"status": "done", "answer": result["answer"]}
