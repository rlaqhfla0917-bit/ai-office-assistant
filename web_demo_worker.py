"""Isolated, mock-only read-query worker for the portfolio Streamlit UI."""
import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

payload = json.loads(sys.stdin.read())
question = str(payload["question"])[:400]
requester_name = payload["requester_name"]
requester_role = payload["requester_role"]
if requester_name not in {"김대리", "박과장"} or requester_role not in {"member", "lead"}:
    raise ValueError("Unsupported demo identity")
os.environ["MOCK_MODE"] = "true"
with tempfile.TemporaryDirectory(prefix="office_portfolio_") as tmp:
    os.environ["DB_PATH"] = str(Path(tmp) / "sample.db")
    os.environ["VECTOR_DB_DIR"] = str(Path(tmp) / "vector")
    with contextlib.redirect_stdout(io.StringIO()):
        import db
        import main
        from agent import graph
        db.init_db()
        main.setup_demo_people()
        main.setup_demo_leaves()
        main.ingest_policy_documents()
        main.ingest_meeting()
        main.setup_demo_due_range_tasks()
        response = graph.ask(question, thread_id="isolated", requester_name=requester_name, requester_role=requester_role)
    if response.get("status") == "needs_approval":
        answer = "데모에서는 변경 요청의 실행을 허용하지 않습니다."
    else:
        answer = str(response.get("answer", "조회된 내용이 없습니다."))
    print(json.dumps({"answer": answer}, ensure_ascii=False))
