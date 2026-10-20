"""LangGraph Agent 안전성 회귀 테스트 (모의 Tool, 실제 메일 발송 없음)."""
import unittest
from unittest.mock import patch
from uuid import uuid4

from agent.graph import ask, resume, permission_node


def thread():
    return "audit-" + uuid4().hex


def task(assignee):
    return {"id": 1, "assignee_name": assignee, "description": "정비 보고서 확인"}


class TestAgentSafety(unittest.TestCase):
    def test_member_cannot_complete_another_person_task(self):
        with patch("agent.graph.tools.sql_tool_get_task", return_value=task("박과장")), \
             patch("agent.graph.tools.sql_tool_update_task_status") as update:
            result = ask("1번 업무 완료 처리해줘", thread(), "김대리", "member")
            self.assertEqual(result["status"], "done")
            self.assertIn("접근 거부", result["answer"])
            update.assert_not_called()

    def test_rejected_approval_must_not_write(self):
        with patch("agent.graph.tools.sql_tool_get_task", return_value=task("김대리")), \
             patch("agent.graph.tools.sql_tool_update_task_status") as update:
            tid = thread()
            pending = ask("1번 업무 완료 처리해줘", tid, "김대리", "member")
            self.assertEqual(pending["status"], "needs_approval")
            self.assertIn("완료 처리", pending["preview"])
            declined = resume(tid, False)
            self.assertIn("승인 거부", declined["answer"])
            update.assert_not_called()

    def test_approved_own_task_updates_once(self):
        with patch("agent.graph.tools.sql_tool_get_task", return_value=task("김대리")), \
             patch("agent.graph.tools.sql_tool_update_task_status", return_value=True) as update:
            tid = thread()
            pending = ask("1번 업무 완료 처리해줘", tid, "김대리", "member")
            self.assertEqual(pending["status"], "needs_approval")
            completed = resume(tid, True)
            self.assertIn("성공", completed["answer"])
            update.assert_called_once_with(1, "done")

    def test_lead_can_request_other_task_but_still_needs_approval(self):
        with patch("agent.graph.tools.sql_tool_get_task", return_value=task("박과장")), \
             patch("agent.graph.tools.sql_tool_update_task_status") as update:
            tid = thread()
            pending = ask("1번 업무 완료 처리해줘", tid, "팀장", "lead")
            self.assertEqual(pending["status"], "needs_approval")
            resume(tid, False)
            update.assert_not_called()

    def test_member_due_range_is_limited_to_self(self):
        state = {"plan": {"type": "due_range", "start": "2026-10-01", "end": "2026-10-07"},
                 "requester_name": "김대리", "requester_role": "member"}
        result = permission_node(state)
        self.assertEqual(result["plan"]["person"], "김대리")
        self.assertNotIn("person", state["plan"])

    def test_mail_without_recipient_is_denied(self):
        result = permission_node({"plan": {"type": "mail_send", "person": None},
                                  "requester_name": "김대리", "requester_role": "member"})
        self.assertEqual(result["plan"]["type"], "denied")

    def test_mail_decline_never_sends(self):
        with patch("agent.graph.tools.sql_tool_get_tasks", return_value=[]), \
             patch("agent.graph.tools.mail_tool_send") as send:
            tid = thread()
            pending = ask("회의 결과 김대리에게 보내줘", tid, "김대리", "member")
            self.assertEqual(pending["status"], "needs_approval")
            self.assertIn("받는 사람", pending["preview"])
            refused = resume(tid, False)
            self.assertIn("승인 거부", refused["answer"])
            send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
