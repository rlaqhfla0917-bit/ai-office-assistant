import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from officeops.web import app

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('OFFICEOPS_DB',str(tmp_path/'officeops.sqlite3'))
    monkeypatch.setenv('AI_MODE','offline')
    monkeypatch.delenv('REDIS_URL',raising=False)
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    with TestClient(app) as c:
        yield c
