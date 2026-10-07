"""
전역 설정.
MOCK_MODE=True 이면 실제 LLM/STT API를 호출하지 않고 규칙 기반 더미 응답으로 동작합니다.
(포트폴리오 데모를 API 키 없이 바로 돌려볼 수 있게 하기 위함)

실제 서비스로 전환하려면:
  - .env 에 OPENAI_API_KEY 또는 ANTHROPIC_API_KEY 설정
  - MOCK_MODE = False
"""
import os

MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
STT_MODEL = os.getenv("STT_MODEL", "whisper-1")

DB_PATH = os.getenv("DB_PATH", "meeting_agent.db")
VECTOR_DB_DIR = os.getenv("VECTOR_DB_DIR", "chroma_store")
