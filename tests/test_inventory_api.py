
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_inventory_prediction_success():
    response = client.post(
        "/api/v1/predict/inventory_optimization",
        json={
            "use_case": "inventory_optimization",
            "request_id": "pytest-valid-001",
            "input": {
                "product_id": "85123A",
                "current_stock": 100,
                "lead_time_days": 5,
                "review_period_days": 7,
                "safety_stock_days": 3
            },
            "options": {}
        }
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["prediction"]["product_id"] == "85123A"
    assert body["prediction"]["recommended_order_quantity"] >= 0
    assert body["errors"] == []

def test_negative_stock_rejected():
    response = client.post(
        "/api/v1/predict/inventory_optimization",
        json={
            "use_case": "inventory_optimization",
            "request_id": "pytest-invalid-001",
            "input": {
                "product_id": "85123A",
                "current_stock": -10,
                "lead_time_days": 5,
                "review_period_days": 7,
                "safety_stock_days": 3
            },
            "options": {}
        }
    )
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["errors"][0]["code"] == "INVALID_INPUT"
