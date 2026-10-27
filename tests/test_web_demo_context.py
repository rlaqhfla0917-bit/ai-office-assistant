import unittest
import json
import os
import subprocess
import sys
from pathlib import Path

from web_demo_context import MAX_HISTORY, is_read_only_question, safe_history


class TestWebDemoContext(unittest.TestCase):
    def test_read_only_question_filter(self):
        self.assertTrue(is_read_only_question("김대리 업무 알려줘"))
        self.assertTrue(is_read_only_question("그중 아직 안 끝난 거 있어?"))
        self.assertFalse(is_read_only_question("1번 업무 완료 처리해줘"))
        self.assertFalse(is_read_only_question("회의 결과 메일 보내줘"))
        self.assertFalse(is_read_only_question("a" * 401))

    def test_history_is_bounded_and_excludes_write_requests(self):
        history = [
            "오늘 연차자 누구야?", "김대리 업무 알려줘",
            "회의 결과 메일 보내줘", "그중 아직 안 끝난 거 있어?",
            "출장비 규정 알려줘",
        ]
        self.assertEqual(
            safe_history(history),
            ["김대리 업무 알려줘", "그중 아직 안 끝난 거 있어?", "출장비 규정 알려줘"],
        )
        self.assertEqual(len(safe_history(history)), MAX_HISTORY)
        self.assertEqual(safe_history("not a list"), [])

    def test_isolated_worker_replays_followup_context(self):
        root = Path(__file__).resolve().parents[1]
        payload = {
            "question": "그중 아직 안 끝난 거 있어?",
            "history": ["김대리가 맡은 업무 알려줘"],
            "requester_name": "김대리",
            "requester_role": "member",
        }
        result = subprocess.run(
            [sys.executable, str(root / "web_demo_worker.py")],
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True, text=True, timeout=20,
            cwd=root, env={**os.environ, "MOCK_MODE": "true"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        answer = json.loads(result.stdout)["answer"]
        self.assertIn("김대리의 업무", answer)
        self.assertIn("pending", answer)


if __name__ == "__main__":
    unittest.main()
