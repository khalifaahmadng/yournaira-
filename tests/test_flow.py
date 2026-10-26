import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "ledger.db"))
    return TestClient(app)

def send(client, text, session="flow_test"):
    response=client.post("/api/message",json={"session":session,"text":text})
    assert response.status_code==200, response.text
    return response.json()

def test_money_flow_and_isolation(client):
    assert send(client,"I received 25000 salary")["action"]=="income"
    send(client,"Set budget 30000")
    send(client,"I spent 1500 on food")
    reply=send(client,"summary")["reply"]
    assert "25,000.00" in reply and "1,500.00" in reply and "28,500.00" in reply
    assert "1,500.00" not in send(client,"summary","another_session")["reply"]

def test_upload_reviews_before_saving(client,monkeypatch):
    monkeypatch.setattr("app.main.transcribe",lambda *args: "I spent 1500 on food")
    response=client.post("/api/voice",data={"session":"flow_test","language":"en-NG"},files={"audio":("clip.wav",b"test","audio/wav")})
    assert response.status_code==200
    assert response.json()["requires_confirmation"] is True
    assert "1,500.00" not in send(client,"summary")["reply"]
    send(client,response.json()["transcript"])
    assert "1,500.00" in send(client,"summary")["reply"]

def test_voice_error_is_json(client,monkeypatch):
    def fail(*args): raise RuntimeError("Speech endpoint unavailable")
    monkeypatch.setattr("app.main.transcribe",fail)
    response=client.post("/api/voice",data={"session":"flow_test"},files={"audio":("clip.wav",b"test")})
    assert response.status_code==503
    assert response.json()["detail"]=="Speech endpoint unavailable"

def test_validation(client):
    assert client.post("/api/message",json={"text":""}).status_code==422
    assert client.post("/api/voice",data={"session":"flow_test","language":"xx"},files={"audio":("x.wav",b"x")}).status_code==400

def test_server_error_json(client,monkeypatch):
    def fail(*args): raise RuntimeError("private diagnostic")
    monkeypatch.setattr("app.main.handle",fail)
    with TestClient(app,raise_server_exceptions=False) as c:
        response=c.post("/api/message",json={"text":"summary"})
    assert response.status_code==500
    assert "private diagnostic" not in response.text
    assert "detail" in response.json()

def test_vercel_voice_configuration(monkeypatch):
    from app.natlas import transcribe
    monkeypatch.setenv("VERCEL","1")
    monkeypatch.delenv("ASR_ENDPOINT_HA",raising=False)
    with pytest.raises(RuntimeError,match="not configured"):
        transcribe(b"audio",".wav","ha")


def test_dictated_amount(client):
    assert "1,500.00" in send(client,"I spent one thousand five hundred naira on food")["reply"]
    assert "Please include" in send(client,"I spent -1500 on food")["reply"]
