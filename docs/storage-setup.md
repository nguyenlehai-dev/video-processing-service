# Hướng dẫn cấu hình Storage (Cloudflare R2)

Video output được upload lên **Cloudflare R2** sau khi FFmpeg xử lý xong. Đây là backend storage mặc định cho môi trường production.

---

## Cách hoạt động

```
Upload video -> Job pending -> FFmpeg xử lý nền -> Upload output lên R2 -> Trả public URL
```

### Luồng chi tiết

```
1. Client upload video lên API             -> POST /api/v1/video/*
2. API lưu file tạm vào /tmp/video-processing/
3. API tạo job trạng thái pending
4. Background task chạy FFmpeg
5. Output được upload lên bucket R2
6. Job completed + trả output_url public
```

---

## Biến môi trường bắt buộc

```env
R2_ACCOUNT_ID=your-account-id
R2_ACCESS_KEY_ID=your-access-key-id
R2_SECRET_ACCESS_KEY=your-secret-access-key
R2_BUCKET_NAME=video-output
R2_PUBLIC_URL=https://pub-xxx.r2.dev
R2_REGION=auto
STORAGE_BACKEND=r2
```

> Nếu để `STORAGE_BACKEND=auto`, service sẽ tự dùng R2 khi đủ credentials, nếu thiếu sẽ fallback sang local storage để tiện phát triển.

---

## Tạo bucket và public URL

1. Vào Cloudflare Dashboard
2. Mở **R2 Object Storage**
3. Tạo bucket, ví dụ `video-output`
4. Bật public access hoặc custom domain cho bucket
5. Copy public base URL vào `R2_PUBLIC_URL`

Ví dụ output URL sau khi xử lý:

```json
{
  "id": "abc-123",
  "status": "completed",
  "output_url": "https://pub-xxx.r2.dev/output/abc-123.mp4"
}
```

---

## Kiểm tra nhanh

```bash
curl https://api.xyz.com/api/v1/video/jobs/JOB_ID \
  -H "X-API-Key: YOUR_API_KEY"
```

Kết quả mong đợi:

```json
{
  "id": "job-id",
  "status": "completed",
  "output_url": "https://pub-xxx.r2.dev/output/job-id.mp4"
}
```

---

## Ghi chú

- Download endpoint nội bộ `/api/v1/video/download/{filename}` vẫn được giữ lại để hỗ trợ local fallback.
- Bucket R2 nên cấu hình lifecycle policy nếu muốn tự dọn file cũ.
- Với production, nên dùng custom domain thay vì URL mặc định `r2.dev`.
