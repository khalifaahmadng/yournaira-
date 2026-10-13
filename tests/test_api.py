from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)

def test_health():
    response=client.get("/api/health")
    assert response.status_code==200
    assert response.json()["ok"] is True
    assert "not verified" in response.json()["note"].lower()

def test_home():
    response=client.get("/")
    assert response.status_code==200
    assert "YourNaira" in response.text

def test_validation_template_blank():
    response=client.get("/api/validation-template")
    assert response.status_code==200
    assert response.text.count("\n") <= 2
