import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.agent.nodes import GeneratedPatch
from unittest.mock import patch


@pytest.mark.asyncio
async def test_api_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check both /health and /api/health
        resp1 = await client.get("/health")
        assert resp1.status_code == 200
        assert resp1.json() == {"status": "ok", "service": "autofix-agent"}

        resp2 = await client.get("/api/health")
        assert resp2.status_code == 200
        assert resp2.json() == {"status": "ok", "service": "autofix-agent"}


@pytest.mark.asyncio
async def test_api_analyze_clean_code():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "source_code": "print('Hello AutoFix')",
            "language": "python",
            "timeout": 3.0,
        }
        resp = await client.post("/api/analyze", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["language"] == "python"
        assert data["execution_result"]["success"] is True
        assert "Hello AutoFix" in data["execution_result"]["stdout"]
        assert data["error_observation"] is None


@pytest.mark.asyncio
async def test_api_analyze_error_code():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "source_code": "print(missing_var)",
            "language": "python",
            "timeout": 3.0,
        }
        resp = await client.post("/api/analyze", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["execution_result"]["success"] is False
        assert data["error_observation"] is not None
        assert data["error_observation"]["error_type"] == "NameError"
        assert "missing_var" in data["error_observation"]["error_message"]


@pytest.mark.asyncio
async def test_api_analyze_unsupported_language():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "source_code": "puts 'hi'",
            "language": "ruby",
        }
        resp = await client.post("/api/analyze", json=payload)
        # Pydantic field_validator now returns 422 for unsupported language
        assert resp.status_code in (400, 422)
        body = resp.json()
        detail_str = str(body.get("detail", ""))
        assert "Unsupported language" in detail_str or "unsupported" in detail_str.lower()


@pytest.mark.asyncio
async def test_api_repair_empty_code():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "source_code": "   ",
            "language": "python",
        }
        resp = await client.post("/api/repair", json=payload)
        # Pydantic field_validator now returns 422 for empty source_code
        assert resp.status_code in (400, 422)
        body = resp.json()
        detail_str = str(body.get("detail", ""))
        assert "empty" in detail_str or "source_code" in detail_str


@pytest.mark.asyncio
async def test_api_repair_clean_code_immediate_success():
    """Verify that submitting clean code terminates with success and concise events."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "source_code": "print('All good')",
            "language": "python",
            "max_attempts": 3,
            "timeout": 3.0,
        }
        resp = await client.post("/api/repair", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["attempts"] == 0
        assert "All good" in data["final_code"]
        assert len(data["events"]) >= 1
        assert any(e["type"] == "execution" for e in data["events"])
        assert any(e["type"] == "completion" for e in data["events"])
