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
    monkeypatch.setattr("app.main.chat_message",fail)
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


def test_history_survives_reload_and_is_separate(client):
    send(client,"I spent 700 on food")
    turns=client.get("/api/history",params={"session":"flow_test"}).json()["turns"]
    assert turns[0]["user_text"]=="I spent 700 on food"
    assert "700.00" in turns[0]["reply"]
    assert client.get("/api/history",params={"session":"other_session"}).json()=={"turns":[]}

def test_retry_does_not_double_charge(client):
    payload={"session":"flow_test","request_id":"retry_id","text":"I spent 500 on food"}
    first=client.post("/api/message",json=payload)
    assert client.post("/api/message",json=payload).json()==first.json()
    assert len(client.get("/api/history",params={"session":"flow_test"}).json()["turns"])==1
    assert "Expenses: ₦500.00" in send(client,"summary")["reply"]
    payload["text"]="I spent 100 on food"
    assert client.post("/api/message",json=payload).status_code==409

def test_failed_chat_insert_rolls_back_ledger(client,monkeypatch):
    from app import core
    original=core.handle_in_transaction
    def fail_after_write(db,session,text):
        original(db,session,text)
        raise RuntimeError("forced failure")
    monkeypatch.setattr(core,"handle_in_transaction",fail_after_write)
    with TestClient(app,raise_server_exceptions=False) as c:
        assert c.post("/api/message",json={"session":"flow_test","text":"I spent 500 on food"}).status_code==500
    monkeypatch.setattr(core,"handle_in_transaction",original)
    assert "Expenses: ₦0.00" in send(client,"summary")["reply"]

@pytest.mark.parametrize("language",["en-NG","ha"])
def test_recorded_language_routes_and_requires_review(client,monkeypatch,language):
    calls=[]
    def mock(data,suffix,lang):
        calls.append((suffix,lang))
        return "Na kashe naira 500 a abinci" if lang=="ha" else "I spent 500 on food"
    monkeypatch.setattr("app.main.transcribe",mock)
    response=client.post("/api/voice",data={"session":"flow_test","language":language},files={"audio":("recording.webm",b"audio","audio/webm")})
    assert response.status_code==200
    assert calls==[(".webm",language)]
    assert response.json()["requires_confirmation"]
    assert client.get("/api/history",params={"session":"flow_test"}).json()["turns"]==[]


def test_empty_message_rejected(client):
    assert client.post("/api/message",json={"text":"   "}).status_code==422


def test_basic_hausa_financial_commands(client):
    result=send(client,"Na kashe naira 500 a abinci")
    assert result["action"]=="expense" and "food" in result["reply"]
    assert send(client,"Na samu naira 2000")["action"]=="income"
    assert "Expenses: ₦500.00" in send(client,"takaitawa")["reply"]

@pytest.mark.parametrize('language,whisper_language',[('en-NG','en'),('ha','ha')])
def test_local_voice_cpu_and_conversion_paths(monkeypatch,language,whisper_language):
    import sys
    from types import SimpleNamespace
    from app import natlas
    calls={}
    def pipeline(*args,**kwargs):
        calls['pipeline']=kwargs
        def infer(path,**options):
            calls['options']=options
            return {'text':'test transcript'}
        return infer
    monkeypatch.setitem(sys.modules,'transformers',SimpleNamespace(pipeline=pipeline))
    monkeypatch.delenv('VERCEL',raising=False)
    monkeypatch.delenv('ASR_ENDPOINT_'+language.upper().replace('-','_'),raising=False)
    monkeypatch.setattr(natlas.shutil,'which',lambda program:'/usr/bin/ffmpeg')
    monkeypatch.setattr(natlas.subprocess,'run',lambda args,**kwargs:calls.update(ffmpeg=args))
    natlas.get_asr.cache_clear()
    try:
        assert natlas.transcribe(b'audio','.wav',language)=='test transcript'
        assert calls['pipeline']['device']==-1
        assert calls['options']['generate_kwargs']=={'language':whisper_language,'task':'transcribe'}
        assert calls['ffmpeg'][calls['ffmpeg'].index('-i')+1]!=calls['ffmpeg'][-1]
    finally:
        natlas.get_asr.cache_clear()
