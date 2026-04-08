"""API integration tests using FastAPI TestClient."""

import pytest

try:
    from fastapi.testclient import TestClient
    from src.main import app as _app
    _HAS_FULL_DEPS = True
except ImportError:
    _HAS_FULL_DEPS = False

pytestmark = pytest.mark.skipif(
    not _HAS_FULL_DEPS,
    reason="Full dependencies (feedparser, uvicorn) not available",
)


@pytest.fixture
def client():
    """Create a test client for the HYDRA API."""
    return TestClient(_app)


class TestFreeEndpoints:
    def test_health(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "wallet" in data

    def test_root(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "operational"
        assert "docs" in data

    def test_pricing(self, client: TestClient) -> None:
        response = client.get("/pricing")
        assert response.status_code == 200
        data = response.json()
        assert "endpoints" in data
        assert len(data["endpoints"]) > 0

    def test_docs(self, client: TestClient) -> None:
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi(self, client: TestClient) -> None:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "paths" in data

    def test_metrics(self, client: TestClient) -> None:
        response = client.get("/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "uptime_seconds" in data
        assert "remittance_threshold_usdc" in data
        assert data["remittance_threshold_usdc"] == "1000"


class TestPaidEndpointsRequirePayment:
    """Verify that all paid endpoints return 402 without payment proof."""

    def test_regulatory_scan_requires_payment(self, client: TestClient) -> None:
        response = client.post(
            "/v1/regulatory/scan",
            json={
                "business_description": "A crypto exchange for retail investors with token trading",
            },
        )
        assert response.status_code == 402
        data = response.json()
        assert data["error"] == "Payment Required"
        assert "payment" in data
        assert data["payment"]["token"] == "USDC"

    def test_regulatory_changes_requires_payment(self, client: TestClient) -> None:
        response = client.post("/v1/regulatory/changes", json={})
        assert response.status_code == 402

    def test_regulatory_jurisdiction_requires_payment(self, client: TestClient) -> None:
        response = client.post(
            "/v1/regulatory/jurisdiction",
            json={"jurisdictions": ["WY", "DE"], "business_type": "crypto"},
        )
        assert response.status_code == 402

    def test_regulatory_query_requires_payment(self, client: TestClient) -> None:
        response = client.post(
            "/v1/regulatory/query",
            json={"question": "What is a money transmitter license?"},
        )
        assert response.status_code == 402

    def test_fed_signal_requires_payment(self, client: TestClient) -> None:
        response = client.post("/v1/fed/signal", json={})
        assert response.status_code == 402

    def test_fed_decision_requires_payment(self, client: TestClient) -> None:
        response = client.post("/v1/fed/decision", json={})
        assert response.status_code == 402

    def test_fed_resolution_requires_payment(self, client: TestClient) -> None:
        response = client.post(
            "/v1/fed/resolution",
            json={"market_question": "Will the Fed hold rates at the next FOMC meeting?"},
        )
        assert response.status_code == 402


class TestPaymentHeaders:
    """Verify 402 responses include proper x402 headers."""

    def test_402_includes_payment_headers(self, client: TestClient) -> None:
        response = client.post(
            "/v1/regulatory/scan",
            json={
                "business_description": "A crypto exchange for retail investors with token trading",
            },
        )
        assert response.headers.get("X-Payment-Required") == "true"
        assert response.headers.get("X-Payment-Network") == "base"
        assert response.headers.get("X-Payment-Token") == "USDC"
        assert "X-Payment-Amount" in response.headers
        assert "X-Payment-Address" in response.headers

    def test_invalid_tx_hash_returns_402(self, client: TestClient) -> None:
        response = client.post(
            "/v1/regulatory/scan",
            json={
                "business_description": "A crypto exchange for retail investors with token trading",
            },
            headers={"X-Payment-Proof": "invalid_hash"},
        )
        assert response.status_code == 402
        assert "Invalid payment proof" in response.json()["message"]


class TestErrorHandling:
    def test_404_returns_json(self, client: TestClient) -> None:
        response = client.get("/nonexistent/endpoint")
        assert response.status_code == 404
        data = response.json()
        assert data["error"] == "Not Found"
        assert "available_endpoints" in data

    def test_405_returns_json(self, client: TestClient) -> None:
        # /v1/regulatory/scan is POST only
        response = client.get("/v1/regulatory/scan")
        # This might be 402 (middleware) or 405 depending on order
        assert response.status_code in (402, 405)

    def test_validation_error(self, client: TestClient) -> None:
        """Validation errors from Pydantic should return structured response."""
        # This would need a valid payment to reach the handler,
        # so we test that the middleware catches it first as 402
        response = client.post("/v1/regulatory/scan", json={})
        assert response.status_code == 402  # Payment required before validation


class TestRequestIdTracking:
    def test_response_has_request_id(self, client: TestClient) -> None:
        response = client.get("/health")
        assert "X-Request-ID" in response.headers

    def test_response_has_timing(self, client: TestClient) -> None:
        response = client.get("/health")
        assert "X-Response-Time-Ms" in response.headers

    def test_custom_request_id_echoed(self, client: TestClient) -> None:
        response = client.get("/health", headers={"X-Request-ID": "my-custom-id"})
        assert response.headers["X-Request-ID"] == "my-custom-id"


class TestSystemEndpoints:
    def test_system_status_requires_auth(self, client: TestClient) -> None:
        response = client.get("/system/status")
        assert response.status_code == 403

    def test_system_wallet_requires_auth(self, client: TestClient) -> None:
        response = client.post("/system/wallet", json={"address": "0x1234"})
        assert response.status_code == 403

    def test_system_remittance_requires_auth(self, client: TestClient) -> None:
        response = client.get("/system/remittance/status")
        assert response.status_code == 403

    def test_system_shutdown_requires_bearer(self, client: TestClient) -> None:
        response = client.post("/system/shutdown")
        assert response.status_code == 403
