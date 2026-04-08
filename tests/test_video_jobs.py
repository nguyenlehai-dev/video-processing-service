from pathlib import Path
from types import SimpleNamespace

from app.api.v1.video import _build_local_upload_token
from app.db.session import SessionLocal
from app.models.job import Job
from app.models.user import User
from app.services.video_service import process_cut_job, process_speed_job


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


def test_legacy_status_endpoint_returns_same_job_payload(client, monkeypatch):
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
    job_id = response.json()["job_id"]

    job_response = client.get(
        f"/api/v1/video/status/{job_id}",
        headers={"X-API-Key": api_key},
    )

    assert job_response.status_code == 200
    assert job_response.json()["id"] == job_id
    assert job_response.json()["status"] == "completed"


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


def test_jobs_init_returns_local_upload_url_when_r2_is_disabled(client, monkeypatch):
    api_key = _create_user_and_api_key(client)
    monkeypatch.setattr("app.api.v1.video.generate_presigned_put_url", lambda object_name: None)
    monkeypatch.setattr("app.api.v1.video.get_storage_backend", lambda: "local")

    response = client.post(
        "/api/v1/video/jobs/init",
        headers={"X-API-Key": api_key},
        json={"tool_name": "cut", "filenames": ["input.mp4"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["upload_urls"][0].startswith(f"/api/v1/video/jobs/{payload['job_id']}/upload/0?token=")


def test_local_upload_endpoint_accepts_file_for_initialized_job(client):
    api_key = _create_user_and_api_key(client)
    init_response = client.post(
        "/api/v1/video/jobs/init",
        headers={"X-API-Key": api_key},
        json={"tool_name": "cut", "filenames": ["input.mp4"]},
    )
    payload = init_response.json()

    db = SessionLocal()
    job = db.query(Job).filter(Job.id == payload["job_id"]).first()
    object_key = job.input_files[0]["object_key"]
    db.close()

    token = _build_local_upload_token(job.id, object_key)
    upload_response = client.put(
        f"/api/v1/video/jobs/{job.id}/upload/0?token={token}",
        content=b"fake-video-content",
        headers={"Content-Type": "video/mp4"},
    )

    assert upload_response.status_code == 200
    stored_path = Path("data/output") / Path(object_key).name
    assert stored_path.exists()


def test_url_whitelist_matches_hostname_not_substring(client, monkeypatch):
    api_key = _create_user_and_api_key(client)
    monkeypatch.setattr(
        "app.api.v1.video.settings.ALLOWED_DOMAIN_WHITELIST",
        "cdn.plxeditor.com,plenxai.com,r2.dev",
    )

    response = client.post(
        "/api/v1/video/jobs/init",
        headers={"X-API-Key": api_key},
        json={
            "tool_name": "cut",
            "filenames": ["https://evil.example.com/file.mp4?mirror=cdn.plxeditor.com"],
        },
    )

    assert response.status_code == 400
    assert "Domain not in whitelist" in response.json()["detail"]


def test_retry_job_does_not_precheck_external_url_inputs(client):
    api_key = _create_user_and_api_key(client)

    db = SessionLocal()
    user = db.query(User).filter(User.email == "video@example.com").first()
    job = Job(
        operation="cut",
        status="failed",
        progress=0.0,
        user_id=user.id,
        params={"start_time": "00:00:00", "end_time": "00:00:01"},
        input_files=[
            {
                "filename": "remote.mp4",
                "object_key": "https://cdn.pixabay.com/video/2015/09/24/859-140683075_small.mp4",
                "managed": False,
            }
        ],
    )
    db.add(job)
    db.commit()
    job_id = job.id
    db.close()

    response = client.post(
        f"/api/v1/video/jobs/{job_id}/retry",
        headers={"X-API-Key": api_key},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"


def test_extract_frames_requires_at_least_one_selector(client):
    api_key = _create_user_and_api_key(client)

    response = client.post(
        "/api/v1/video/extract-frames",
        headers={"X-API-Key": api_key},
        files={"video": ("input.mp4", b"fake-video-content", "video/mp4")},
        data={},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "At least one of first_frame, last_frame, or timestamp is required"


def test_extract_audio_returns_clear_error_for_video_without_audio(client, monkeypatch):
    api_key = _create_user_and_api_key(client)
    monkeypatch.setattr("app.services.video_service._has_audio", lambda _path: False)

    response = client.post(
        "/api/v1/video/extract-audio",
        headers={"X-API-Key": api_key},
        files={"video": ("input.mp4", b"fake-video-content", "video/mp4")},
        data={"format": "mp3"},
    )

    assert response.status_code == 200
    job_id = response.json()["job_id"]

    job_response = client.get(
        f"/api/v1/video/jobs/{job_id}",
        headers={"X-API-Key": api_key},
    )
    assert job_response.status_code == 200
    assert job_response.json()["status"] == "failed"
    assert job_response.json()["error_message"] == "Input video does not contain an audio stream to extract."


def test_speed_job_without_audio_falls_back_to_video_only(client, monkeypatch):
    _create_user_and_api_key(client)

    def fake_run(cmd, capture_output, text, timeout):
        output_path = Path(cmd[-1])
        output_path.write_bytes(b"processed-video")
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr("app.services.video_service._has_audio", lambda _path: False)
    monkeypatch.setattr("app.services.video_service.subprocess.run", fake_run)

    db = SessionLocal()
    user = db.query(User).filter(User.email == "video@example.com").first()
    source_output = Path("data/output/silent-input.mp4")
    source_output.parent.mkdir(parents=True, exist_ok=True)
    source_output.write_bytes(b"source-video")

    job = Job(
        operation="speed",
        status="pending",
        progress=0.0,
        user_id=user.id,
        params={"speed": 1.5, "adjust_audio": True},
        input_files=[
            {
                "filename": "silent-input.mp4",
                "object_key": "output/silent-input.mp4",
                "managed": False,
            }
        ],
    )
    db.add(job)
    db.commit()
    job_id = job.id
    db.close()

    process_speed_job(job_id, "output/silent-input.mp4", 1.5, True)

    db = SessionLocal()
    stored_job = db.query(Job).filter(Job.id == job_id).first()
    assert stored_job.status == "completed"
    assert stored_job.output_url is not None
    db.close()


def test_output_reference_input_is_not_deleted_after_processing(client, monkeypatch):
    _create_user_and_api_key(client)
    source_output = Path("data/output/existing-output.mp4")
    source_output.parent.mkdir(parents=True, exist_ok=True)
    source_output.write_bytes(b"source-video")

    def fake_run(cmd, capture_output, text, timeout):
        output_path = Path(cmd[-1])
        output_path.write_bytes(b"processed-video")
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr("app.services.video_service.subprocess.run", fake_run)

    db = SessionLocal()
    user = db.query(User).filter(User.email == "video@example.com").first()
    job = Job(
        operation="cut",
        status="pending",
        progress=0.0,
        user_id=user.id,
        params={"start_time": "00:00:00", "end_time": "00:00:01"},
        input_files=[
            {
                "filename": "existing-output.mp4",
                "object_key": "output/existing-output.mp4",
                "managed": False,
            }
        ],
    )
    db.add(job)
    db.commit()
    job_id = job.id
    db.close()

    process_cut_job(job_id, "output/existing-output.mp4", "00:00:00", "00:00:01")

    db = SessionLocal()
    stored_job = db.query(Job).filter(Job.id == job_id).first()
    assert stored_job.status == "completed"
    assert source_output.exists()
    db.close()


def test_missing_storage_input_returns_clear_error_message(client):
    _create_user_and_api_key(client)

    db = SessionLocal()
    user = db.query(User).filter(User.email == "video@example.com").first()
    job = Job(
        operation="cut",
        status="pending",
        progress=0.0,
        user_id=user.id,
        params={"start_time": "00:00:00", "end_time": "00:00:01"},
        input_files=[
            {
                "filename": "missing.mp4",
                "object_key": "output/missing.mp4",
                "managed": False,
            }
        ],
    )
    db.add(job)
    db.commit()
    job_id = job.id
    db.close()

    process_cut_job(job_id, "output/missing.mp4", "00:00:00", "00:00:01")

    db = SessionLocal()
    stored_job = db.query(Job).filter(Job.id == job_id).first()
    assert stored_job.status == "failed"
    assert stored_job.error_message == "Input object not found in local storage: output/missing.mp4"
    db.close()
