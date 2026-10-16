"""Public, read-only portfolio interface for the existing LangGraph demo.

Each question runs the original mock-mode agent in a fresh temporary folder.
No SMTP calls, external LLM requests or shared employee records are used.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="AI Office Assistant · Portfolio Demo", page_icon="🤖", layout="wide")
st.title("AI Office Assistant")
st.caption("LangGraph 기반 업무비서 · 포트폴리오 체험용")
st.info("가상 직원/사내 규정으로 실행하는 MOCK 데모입니다. 실제 사내 시스템, 메일, OpenAI API와 연결되지 않습니다.")
with st.sidebar:
    st.subheader("데모 안내")
    st.markdown("**체험 가능:** SQL 기반 연차·업무 조회, 규정 검색, 권한 제한")
    st.markdown("**제한:** 실제 메일 전송, 업무 변경, 실시간 데이터 연동")
    requester = st.selectbox("가상 사용자", ["김대리 (일반 직원)", "박과장 (팀장)"])
    st.markdown("[GitHub 소스 보기](https://github.com/rlaqhfla0917-bit/ai-office-assistant)")
examples = ["오늘 연차자 누구야?", "이번 주 마감 업무 뭐 있어?", "출장비 규정 알려줘", "김대리가 맡은 업무 알려줘", "박과장 업무 알려줘"]
st.markdown("**예시 질문:** " + " · ".join(examples))
if "messages" not in st.session_state:
    st.session_state.messages = []
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
question = st.chat_input("업무 관련 질문을 입력하세요")
if question:
    st.session_state.messages.append({"role":"user","content":question})
    with st.chat_message("user"):
        st.markdown(question)
    if len(question) > 400:
        answer = "질문은 400자 이내로 입력해주세요."
    elif any(x in question for x in ["보내", "메일", "완료 처리", "완료처리", "변경", "삭제"]):
        answer = "공개 포트폴리오에서는 데이터 변경 및 메일 발송을 비활성화했습니다. 승인 흐름은 GitHub의 LangGraph 코드에서 확인할 수 있습니다."
    else:
        actor = "박과장" if requester.startswith("박") else "김대리"
        role = "lead" if actor == "박과장" else "member"
        try:
            run = subprocess.run(
                [sys.executable, str(ROOT / "web_demo_worker.py")],
                input=json.dumps({"question": question, "requester_name": actor, "requester_role": role}),
                text=True, capture_output=True, timeout=25,
                cwd=str(ROOT), env={**os.environ, "MOCK_MODE": "true"}
            )
            if run.returncode:
                answer = "데모 실행 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."
            else:
                result = json.loads(run.stdout)
                answer = result.get("answer", "조회된 내용이 없습니다.")
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
            answer = "데모 실행 시간이 초과되었거나 응답을 처리하지 못했습니다."
    st.session_state.messages.append({"role":"assistant","content":answer})
    with st.chat_message("assistant"):
        st.markdown(answer)
