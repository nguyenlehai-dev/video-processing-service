from pathlib import Path

import pytest

from app.services import storage_service


def test_upload_file_to_storage_uses_r2_when_configured(monkeypatch, tmp_path):
    source_file = tmp_path / "video.mp4"
    source_file.write_bytes(b"video-bytes")

    uploaded = {}

    class FakeClient:
        def upload_file(self, file_path, bucket_name, object_name, ExtraArgs=None):
            uploaded["file_path"] = file_path
            uploaded["bucket_name"] = bucket_name
            uploaded["object_name"] = object_name
            uploaded["content_type"] = ExtraArgs["ContentType"]

    monkeypatch.setattr(storage_service.settings, "STORAGE_BACKEND", "r2")
    monkeypatch.setattr(storage_service.settings, "R2_ACCOUNT_ID", "account-id")
    monkeypatch.setattr(storage_service.settings, "R2_ACCESS_KEY_ID", "access-key")
    monkeypatch.setattr(storage_service.settings, "R2_SECRET_ACCESS_KEY", "secret-key")
    monkeypatch.setattr(storage_service.settings, "R2_BUCKET_NAME", "video-output")
    monkeypatch.setattr(storage_service.settings, "R2_PUBLIC_URL", "https://pub.example.com")
    monkeypatch.setattr(storage_service.settings, "R2_REGION", "auto")
    monkeypatch.setattr(storage_service, "_get_r2_client", lambda: FakeClient())

    output_url = storage_service.upload_file_to_storage(str(source_file), "output/test-job.mp4")

    assert output_url == "https://pub.example.com/output/test-job.mp4"
    assert uploaded["file_path"] == str(source_file)
    assert uploaded["bucket_name"] == "video-output"
    assert uploaded["object_name"] == "output/test-job.mp4"
    assert uploaded["content_type"] == "video/mp4"


def test_validate_storage_configuration_falls_back_to_local(monkeypatch):
    monkeypatch.setattr(storage_service.settings, "STORAGE_BACKEND", "auto")
    monkeypatch.setattr(storage_service.settings, "R2_ACCOUNT_ID", "")
    monkeypatch.setattr(storage_service.settings, "R2_ACCESS_KEY_ID", "")
    monkeypatch.setattr(storage_service.settings, "R2_SECRET_ACCESS_KEY", "")
    monkeypatch.setattr(storage_service.settings, "R2_BUCKET_NAME", "")
    monkeypatch.setattr(storage_service.settings, "R2_PUBLIC_URL", "")

    assert storage_service.validate_storage_configuration() == "local"


def test_upload_file_to_storage_returns_full_public_url_for_local_fallback(monkeypatch, tmp_path):
    source_file = tmp_path / "video.mp4"
    source_file.write_bytes(b"video-bytes")

    monkeypatch.setattr(storage_service.settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(storage_service.settings, "PUBLIC_BASE_URL", "https://plxeditor.com")

    output_url = storage_service.upload_file_to_storage(str(source_file), "output/test-job.mp4")

    assert output_url == "https://plxeditor.com/api/v1/video/download/test-job.mp4"


def test_upload_file_to_storage_raises_when_r2_upload_fails(monkeypatch, tmp_path):
    source_file = tmp_path / "video.mp4"
    source_file.write_bytes(b"video-bytes")

    monkeypatch.setattr(storage_service.settings, "STORAGE_BACKEND", "r2")
    monkeypatch.setattr(storage_service.settings, "R2_ACCOUNT_ID", "account-id")
    monkeypatch.setattr(storage_service.settings, "R2_ACCESS_KEY_ID", "access-key")
    monkeypatch.setattr(storage_service.settings, "R2_SECRET_ACCESS_KEY", "secret-key")
    monkeypatch.setattr(storage_service.settings, "R2_BUCKET_NAME", "video-output")
    monkeypatch.setattr(storage_service.settings, "R2_PUBLIC_URL", "https://pub.example.com")

    def fake_upload(*_args, **_kwargs):
        raise RuntimeError("Access Denied")

    monkeypatch.setattr(storage_service, "_upload_file_to_r2", fake_upload)

    with pytest.raises(RuntimeError, match="Access Denied"):
        storage_service.upload_file_to_storage(str(source_file), "output/test-job.mp4")


def test_probe_storage_health_reports_success_for_r2(monkeypatch):
    created = {}

    class FakeClient:
        def put_object(self, Bucket, Key, Body, ContentType):
            created["bucket"] = Bucket
            created["key"] = Key
            created["body"] = Body
            created["content_type"] = ContentType

        def delete_object(self, Bucket, Key):
            created["deleted_bucket"] = Bucket
            created["deleted_key"] = Key

    monkeypatch.setattr(storage_service.settings, "STORAGE_BACKEND", "r2")
    monkeypatch.setattr(storage_service.settings, "R2_ACCOUNT_ID", "account-id")
    monkeypatch.setattr(storage_service.settings, "R2_ACCESS_KEY_ID", "access-key")
    monkeypatch.setattr(storage_service.settings, "R2_SECRET_ACCESS_KEY", "secret-key")
    monkeypatch.setattr(storage_service.settings, "R2_BUCKET_NAME", "video-output")
    monkeypatch.setattr(storage_service.settings, "R2_PUBLIC_URL", "https://pub.example.com")
    monkeypatch.setattr(storage_service, "_get_r2_client", lambda: FakeClient())

    result = storage_service.probe_storage_health()

    assert result["backend"] == "r2"
    assert result["ok"] is True
    assert created["bucket"] == "video-output"
    assert created["deleted_bucket"] == "video-output"
    assert created["deleted_key"] == created["key"]


def test_probe_storage_health_reports_failure_for_r2(monkeypatch):
    class FakeClient:
        def put_object(self, **_kwargs):
            raise RuntimeError("Access Denied")

    monkeypatch.setattr(storage_service.settings, "STORAGE_BACKEND", "r2")
    monkeypatch.setattr(storage_service.settings, "R2_ACCOUNT_ID", "account-id")
    monkeypatch.setattr(storage_service.settings, "R2_ACCESS_KEY_ID", "access-key")
    monkeypatch.setattr(storage_service.settings, "R2_SECRET_ACCESS_KEY", "secret-key")
    monkeypatch.setattr(storage_service.settings, "R2_BUCKET_NAME", "video-output")
    monkeypatch.setattr(storage_service.settings, "R2_PUBLIC_URL", "https://pub.example.com")
    monkeypatch.setattr(storage_service, "_get_r2_client", lambda: FakeClient())

    result = storage_service.probe_storage_health()

    assert result["backend"] == "r2"
    assert result["ok"] is False
    assert "Access Denied" in result["message"]
