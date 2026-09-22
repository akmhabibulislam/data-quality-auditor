import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_api_root():
    response = client.get("/")
    assert response.status_code == 200

def test_audit_upload_csv():
    csv_content = b"col_a,col_b\n1,100\n2,200\n,300"
    files = {"file": ("test.csv", csv_content, "text/csv")}
    response = client.post("/api/audit", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["row_count"] == 3
    assert data["summary"]["column_count"] == 2
    assert "health_score" in data

def test_sample_benchmark_api():
    response = client.post("/api/audit/sample/messy_ecommerce")
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["row_count"] > 0
    assert len(data["columns"]) > 0

def test_export_endpoints():
    # Ingest sample first
    client.post("/api/audit/sample/messy_ecommerce")
    
    # Export JSON
    res_json = client.post("/api/export/json")
    assert res_json.status_code == 200
    assert res_json.headers["content-type"] == "application/json"

    # Export HTML
    res_html = client.post("/api/export/html")
    assert res_html.status_code == 200
    assert "text/html" in res_html.headers["content-type"]

    # Export PDF
    res_pdf = client.post("/api/export/pdf")
    assert res_pdf.status_code == 200
    assert res_pdf.headers["content-type"] == "application/pdf"
    assert len(res_pdf.content) > 1000
