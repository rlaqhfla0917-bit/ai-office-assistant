"""
음성 -> 텍스트 변환.
MOCK_MODE 에서는 파일을 읽지 않고 미리 준비된 스크립트를 돌려줍니다.
실제 연동 시 OpenAI Whisper API 예시를 사용합니다.
"""
from config import MOCK_MODE, OPENAI_API_KEY, STT_MODEL


def transcribe(audio_path: str) -> str:
    if MOCK_MODE:
        # 데모용 더미 트랜스크립트 (sample_data/meeting_transcript.txt 참고)
        with open("sample_data/meeting_transcript.txt", "r", encoding="utf-8") as f:
            return f.read()

    # --- 실제 연동 예시 (openai>=1.0) ---
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    with open(audio_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model=STT_MODEL, file=audio_file
        )
    return transcript.text
