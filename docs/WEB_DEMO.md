# Streamlit 웹 데모

실행: `streamlit run streamlit_app.py`

가상 데이터를 사용하는 읽기 전용 데모입니다. 질문마다 임시 SQLite 데이터베이스를 새로 만들며 외부 메일 발송, 영구 DB 변경, OpenAI API 호출은 비활성화되어 있습니다. 최근 3개의 읽기 전용 질문을 같은 임시 Agent 세션에서 재실행해 후속 질문의 맥락을 연결합니다. 가상 사용자를 변경하면 대화가 초기화되며, 서버에 이전 대화를 영구 저장하지 않습니다.

대화 상태와 사용자 승인 흐름은 로컬 CLI 예제 [`main.py`](../main.py)에서 확인할 수 있습니다.

## 배포

Streamlit Community Cloud에서 이 저장소를 선택하고 실행 파일을 `streamlit_app.py`로 지정합니다. 필요한 패키지는 루트의 `requirements.txt`에 정의되어 있으며, 모의 데이터 데모에는 API 키가 필요하지 않습니다.
