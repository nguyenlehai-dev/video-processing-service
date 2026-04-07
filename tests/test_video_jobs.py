from pathlib import Path
from types import SimpleNamespace


def _create_user_and_api_key(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "video@example.com",
            "username": "videouser",
            "password": "testpass123",
        },
    )
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "video@example.com",
            "password": "testpass123",
        },
    )
    access_token = login_response.json()["access_token"]
    api_key_response = client.post(
        "/api/v1/api-keys/",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"name": "Video Test Key"},
    )
    return api_key_response.json()["key"]


def test_resize_job_runs_in_background_and_persists_result(client, monkeypatch):
    api_key = _create_user_and_api_key(client)

    def fake_run(cmd, capture_output, text, timeout):
        output_path = Path(cmd[-1])
        output_path.write_bytes(b"processed-video")
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr("app.services.video_service.subprocess.run", fake_run)

    response = client.post(
        "/api/v1/video/resize",
        headers={"X-API-Key": api_key},
        files={"video": ("input.mp4", b"fake-video-content", "video/mp4")},
        data={"width": "320", "height": "240", "maintain_aspect": "true"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pending"

    job_response = client.get(
        f"/api/v1/video/jobs/{payload['job_id']}",
        headers={"X-API-Key": api_key},
    )
    assert job_response.status_code == 200
    job = job_response.json()
    assert job["status"] == "completed"
    assert job["output_url"].startswith("/api/v1/video/download/")
    assert job["file_size"] == len(b"processed-video")


def test_large_upload_is_rejected(client, monkeypatch):
    api_key = _create_user_and_api_key(client)
    monkeypatch.setattr("app.api.v1.video.settings.MAX_UPLOAD_SIZE_MB", 1)
    oversized = b"x" * (2 * 1024 * 1024)

    response = client.post(
        "/api/v1/video/cut",
        headers={"X-API-Key": api_key},
        files={"video": ("big.mp4", oversized, "video/mp4")},
        data={"start_time": "00:00:00", "end_time": "00:00:01"},
    )

    assert response.status_code == 413
