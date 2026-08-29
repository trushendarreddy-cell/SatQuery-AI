from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_agent_chat_returns_response():
    """Test POST /api/v1/agent/chat returns a response."""
    res = client.post(
        "/api/v1/agent/chat",
        json={
            "session_id": "test_agent_session",
            "query": "What can you do?",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "response" in data
    assert "tool_calls" in data
    assert "provider" in data


def test_agent_chat_with_tool_selection():
    """Test POST /api/v1/agent/chat selects appropriate tools."""
    res = client.post(
        "/api/v1/agent/chat",
        json={
            "session_id": "test_agent_session",
            "query": "Detect changes between two images",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["provider"] == "MockLLMProvider"


def test_agent_chat_missing_session():
    """Test POST /api/v1/agent/chat handles missing session gracefully."""
    res = client.post(
        "/api/v1/agent/chat",
        json={
            "session_id": "nonexistent_session",
            "query": "Hello",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "response" in data
