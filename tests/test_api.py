import io


def test_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_upload_process_search_and_correct_csv(client):
    body = b"Invoice No,Invoice Date,Supplier,Subtotal,Tax,Grand Total,Currency\nAPI-10,2025-01-05,Acme Ltd,100,15,115,USD\n"
    response = client.post(
        "/api/v1/documents/upload", files=[("files", ("invoice.csv", io.BytesIO(body), "text/csv"))]
    )
    assert response.status_code == 202
    document_id = response.json()["accepted"][0]["id"]

    detail = client.get(f"/api/v1/documents/{document_id}")
    assert detail.status_code == 200
    assert detail.json()["status"] in {"completed", "needs_review"}

    search = client.get("/api/v1/documents", params={"q": "Acme"})
    assert search.status_code == 200
    assert search.json()["total"] == 1

    corrected = client.patch(
        f"/api/v1/documents/{document_id}",
        json={"updates": {"invoice_number": "API-10-FIXED"}, "corrected_by": "tester"},
    )
    assert corrected.status_code == 200
    assert corrected.json()["structured_data"]["invoice_number"] == "API-10-FIXED"


def test_rejects_unsupported_upload(client):
    response = client.post(
        "/api/v1/documents/upload",
        files=[("files", ("malware.exe", io.BytesIO(b"MZ"), "application/octet-stream"))],
    )
    assert response.status_code == 202
    assert response.json()["accepted"] == []
    assert len(response.json()["rejected"]) == 1


def test_404_and_compare_missing_documents(client):
    assert client.get("/api/v1/documents/not-found").status_code == 404
    response = client.post(
        "/api/v1/documents/compare", json={"left_document_id": "a", "right_document_id": "b"}
    )
    assert response.status_code == 404
