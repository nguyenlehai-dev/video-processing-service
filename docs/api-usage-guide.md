# Hướng dẫn sử dụng API - Video Processing Service

Tài liệu hướng dẫn chi tiết cách sử dụng tất cả API endpoints.

> 📖 **Swagger UI (Interactive docs):** `https://api.xyz.com/docs`
> 📖 **ReDoc:** `https://api.xyz.com/redoc`

---

## Mục lục

1. [Xác thực (Authentication)](#1-xác-thực-authentication)
2. [Quản lý API Key](#2-quản-lý-api-key)
3. [Xử lý Video](#3-xử-lý-video)
4. [Theo dõi Job](#4-theo-dõi-job)
5. [Quản lý User (Admin)](#5-quản-lý-user-admin)

---

## Tổng quan Authentication

Service sử dụng **2 loại xác thực**:

| Loại | Dùng cho | Header |
|------|----------|--------|
| **JWT Bearer Token** | Quản lý (auth, users, api-keys) | `Authorization: Bearer <token>` |
| **API Key** | Xử lý video | `X-API-Key: <api_key>` |

**Luồng sử dụng:**

```
1. Register → 2. Login (lấy JWT) → 3. Tạo API Key → 4. Dùng API Key gọi video API
```

---

## 1. Xác thực (Authentication)

### 1.1. Đăng ký tài khoản

```bash
curl -X POST https://api.xyz.com/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "username": "myuser",
    "password": "mypassword123",
    "full_name": "Nguyen Van A"
  }'
```

**Response (201):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "username": "myuser",
  "full_name": "Nguyen Van A",
  "is_active": true,
  "is_admin": true,
  "created_at": "2026-04-06T01:00:00"
}
```

> 💡 **User đầu tiên** đăng ký sẽ tự động trở thành **Admin**.

---

### 1.2. Đăng nhập

```bash
curl -X POST https://api.xyz.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "mypassword123"
  }'
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

> 🔑 **Lưu `access_token`** để dùng cho các request tiếp theo.
> Access token hết hạn sau **30 phút** (có thể thay đổi trong `.env`).

---

### 1.3. Refresh Token

Khi access token hết hạn, dùng refresh token để lấy token mới:

```bash
curl -X POST https://api.xyz.com/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
  }'
```

---

### 1.4. Xem thông tin tài khoản

```bash
curl https://api.xyz.com/api/v1/auth/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## 2. Quản lý API Key

### 2.1. Tạo API Key mới

```bash
curl -X POST https://api.xyz.com/api/v1/api-keys/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My App Key"
  }'
```

**Response (201):**
```json
{
  "id": "key-uuid-here",
  "name": "My App Key",
  "key": "vps_abc123def456ghi789...",
  "key_prefix": "vps_abc123de",
  "is_active": true,
  "created_at": "2026-04-06T01:00:00"
}
```

> ⚠️ **QUAN TRỌNG:** Trường `key` chỉ hiển thị **1 lần duy nhất** tại thời điểm tạo. Hãy lưu ngay!

---

### 2.2. Liệt kê API Keys

```bash
curl https://api.xyz.com/api/v1/api-keys/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

> Chỉ hiển thị `key_prefix` (8 ký tự đầu), không hiển thị full key.

---

### 2.3. Thu hồi API Key

```bash
curl -X DELETE https://api.xyz.com/api/v1/api-keys/KEY_ID \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## 3. Xử lý Video

> Tất cả endpoint video đều dùng **API Key** qua header `X-API-Key`.

### 3.1. Cắt video (Cut)

Cắt một đoạn video theo thời gian bắt đầu và kết thúc.

```bash
curl -X POST https://api.xyz.com/api/v1/video/cut \
  -H "X-API-Key: YOUR_API_KEY" \
  -F "video=@input.mp4" \
  -F "start_time=00:00:10" \
  -F "end_time=00:00:30"
```

| Parameter | Type | Bắt buộc | Mô tả |
|-----------|------|----------|-------|
| `video` | File | ✅ | File video cần cắt |
| `start_time` | String | ✅ | Thời gian bắt đầu (`HH:MM:SS` hoặc giây) |
| `end_time` | String | ✅ | Thời gian kết thúc |

**Response:**
```json
{
  "job_id": "job-uuid-here",
  "message": "Video cut processing",
  "status": "processing"
}
```

---

### 3.2. Ghép video (Merge)

Nối nhiều video lại thành 1 file.

```bash
curl -X POST https://api.xyz.com/api/v1/video/merge \
  -H "X-API-Key: YOUR_API_KEY" \
  -F "videos=@video1.mp4" \
  -F "videos=@video2.mp4" \
  -F "videos=@video3.mp4"
```

| Parameter | Type | Bắt buộc | Mô tả |
|-----------|------|----------|-------|
| `videos` | Files | ✅ | Tối thiểu 2 file video (theo thứ tự nối) |

---

### 3.3. Ghép âm thanh vào video (Add Audio)

Thêm hoặc thay thế audio track trong video.

```bash
# Thay thế audio hoàn toàn
curl -X POST https://api.xyz.com/api/v1/video/add-audio \
  -H "X-API-Key: YOUR_API_KEY" \
  -F "video=@input.mp4" \
  -F "audio=@music.mp3" \
  -F "replace=true"

# Mix audio (trộn với audio gốc)
curl -X POST https://api.xyz.com/api/v1/video/add-audio \
  -H "X-API-Key: YOUR_API_KEY" \
  -F "video=@input.mp4" \
  -F "audio=@background.mp3" \
  -F "replace=false"
```

| Parameter | Type | Bắt buộc | Mô tả |
|-----------|------|----------|-------|
| `video` | File | ✅ | File video |
| `audio` | File | ✅ | File audio cần ghép |
| `replace` | Boolean | ❌ | `true` = thay thế, `false` = trộn (mặc định: `false`) |

---

### 3.4. Tách âm thanh (Extract Audio)

Trích xuất audio từ video thành file riêng.

```bash
curl -X POST https://api.xyz.com/api/v1/video/extract-audio \
  -H "X-API-Key: YOUR_API_KEY" \
  -F "video=@input.mp4" \
  -F "format=mp3"
```

| Parameter | Type | Bắt buộc | Mô tả |
|-----------|------|----------|-------|
| `video` | File | ✅ | File video |
| `format` | String | ❌ | Format output: `mp3`, `wav`, `aac`, `flac` (mặc định: `mp3`) |

---

### 3.5. Tăng/giảm tốc độ (Speed)

Thay đổi tốc độ phát video.

```bash
# Tăng gấp đôi tốc độ
curl -X POST https://api.xyz.com/api/v1/video/speed \
  -H "X-API-Key: YOUR_API_KEY" \
  -F "video=@input.mp4" \
  -F "speed=2.0" \
  -F "adjust_audio=true"

# Giảm 1/2 tốc độ (slow motion)
curl -X POST https://api.xyz.com/api/v1/video/speed \
  -H "X-API-Key: YOUR_API_KEY" \
  -F "video=@input.mp4" \
  -F "speed=0.5"
```

| Parameter | Type | Bắt buộc | Mô tả |
|-----------|------|----------|-------|
| `video` | File | ✅ | File video |
| `speed` | Float | ❌ | Hệ số tốc độ: `0.25` - `4.0` (mặc định: `1.0`) |
| `adjust_audio` | Boolean | ❌ | Điều chỉnh audio theo tốc độ (mặc định: `true`) |

**Bảng tham khảo speed:**

| Giá trị | Hiệu ứng |
|---------|----------|
| `0.25` | Chậm 4x (slow motion cực) |
| `0.5` | Chậm 2x (slow motion) |
| `1.0` | Bình thường |
| `1.5` | Nhanh 1.5x |
| `2.0` | Nhanh 2x |
| `4.0` | Nhanh 4x (timelapse) |

---

### 3.6. Crop video

Cắt vùng hiển thị trong video (giữ lại chỉ 1 phần).

```bash
curl -X POST https://api.xyz.com/api/v1/video/crop \
  -H "X-API-Key: YOUR_API_KEY" \
  -F "video=@input.mp4" \
  -F "width=640" \
  -F "height=480" \
  -F "x=100" \
  -F "y=50"
```

| Parameter | Type | Bắt buộc | Mô tả |
|-----------|------|----------|-------|
| `video` | File | ✅ | File video |
| `width` | Integer | ✅ | Chiều rộng vùng crop (pixel) |
| `height` | Integer | ✅ | Chiều cao vùng crop (pixel) |
| `x` | Integer | ❌ | Offset ngang từ trái (mặc định: `0`) |
| `y` | Integer | ❌ | Offset dọc từ trên (mặc định: `0`) |

```
┌──────────────────────────────┐
│          Original Video       │
│    (x,y)                      │
│     ┌───────────┐             │
│     │  Cropped   │ height     │
│     │  Region    │             │
│     └───────────┘             │
│        width                  │
└──────────────────────────────┘
```

---

### 3.7. Resize video

Thay đổi kích thước video.

```bash
# Resize giữ tỷ lệ (pad nếu cần)
curl -X POST https://api.xyz.com/api/v1/video/resize \
  -H "X-API-Key: YOUR_API_KEY" \
  -F "video=@input.mp4" \
  -F "width=1280" \
  -F "height=720" \
  -F "maintain_aspect=true"

# Resize không giữ tỷ lệ (có thể bị méo)
curl -X POST https://api.xyz.com/api/v1/video/resize \
  -H "X-API-Key: YOUR_API_KEY" \
  -F "video=@input.mp4" \
  -F "width=1920" \
  -F "height=1080" \
  -F "maintain_aspect=false"
```

| Parameter | Type | Bắt buộc | Mô tả |
|-----------|------|----------|-------|
| `video` | File | ✅ | File video |
| `width` | Integer | ✅ | Chiều rộng mới (pixel) |
| `height` | Integer | ✅ | Chiều cao mới (pixel) |
| `maintain_aspect` | Boolean | ❌ | Giữ tỷ lệ khung hình (mặc định: `true`) |

**Kích thước phổ biến:**

| Tên | Kích thước | Tỷ lệ |
|-----|-----------|--------|
| 480p | 854×480 | 16:9 |
| 720p (HD) | 1280×720 | 16:9 |
| 1080p (Full HD) | 1920×1080 | 16:9 |
| 1440p (2K) | 2560×1440 | 16:9 |
| 2160p (4K) | 3840×2160 | 16:9 |
| Square | 1080×1080 | 1:1 |
| Portrait | 1080×1920 | 9:16 |

---

## 4. Theo dõi Job

Mỗi request xử lý video sẽ trả về `job_id`. Dùng ID này để kiểm tra trạng thái.

### 4.1. Kiểm tra trạng thái 1 job

```bash
curl https://api.xyz.com/api/v1/video/jobs/JOB_ID \
  -H "X-API-Key: YOUR_API_KEY"
```

**Response khi đang xử lý:**
```json
{
  "id": "job-uuid",
  "operation": "cut",
  "status": "processing",
  "progress": 50.0,
  "output_url": null,
  "created_at": "2026-04-06T01:00:00"
}
```

**Response khi hoàn tất:**
```json
{
  "id": "job-uuid",
  "operation": "cut",
  "status": "completed",
  "progress": 100.0,
  "output_url": "/api/v1/video/download/job-uuid.mp4",
  "output_filename": "cut_job-uuid.mp4",
  "file_size": 1548000,
  "duration": 3.45,
  "created_at": "2026-04-06T01:00:00",
  "completed_at": "2026-04-06T01:00:03"
}
```

> 💡 **Download file:** Dùng `output_url` để download kết quả:
> ```bash
> curl -O https://api.xyz.com/api/v1/video/download/job-uuid.mp4
> ```

**Response khi lỗi:**
```json
{
  "id": "job-uuid",
  "operation": "cut",
  "status": "failed",
  "progress": 0.0,
  "error_message": "FFmpeg error: Invalid input file",
  "created_at": "2026-04-06T01:00:00"
}
```

**Các trạng thái Job:**

| Status | Ý nghĩa |
|--------|---------|
| `pending` | Đang chờ xử lý |
| `processing` | Đang xử lý |
| `completed` | Hoàn tất, có `output_url` |
| `failed` | Lỗi, xem `error_message` |

---

### 4.2. Liệt kê tất cả jobs

```bash
curl "https://api.xyz.com/api/v1/video/jobs?skip=0&limit=20" \
  -H "X-API-Key: YOUR_API_KEY"
```

---

## 5. Quản lý User (Admin)

> Chỉ user có quyền **Admin** mới truy cập được.

### 5.1. Liệt kê users

```bash
curl https://api.xyz.com/api/v1/users/ \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

### 5.2. Xem chi tiết user

```bash
curl https://api.xyz.com/api/v1/users/USER_ID \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

### 5.3. Cập nhật user

```bash
curl -X PUT https://api.xyz.com/api/v1/users/USER_ID \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "is_active": false,
    "is_admin": true
  }'
```

### 5.4. Xoá user

```bash
curl -X DELETE https://api.xyz.com/api/v1/users/USER_ID \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

> ⚠️ Không thể xoá chính tài khoản đang đăng nhập.

---

## HTTP Status Codes

| Code | Ý nghĩa |
|------|---------|
| `200` | Thành công |
| `201` | Tạo mới thành công |
| `204` | Xoá thành công (không có body) |
| `400` | Request không hợp lệ |
| `401` | Chưa xác thực (token/key sai hoặc hết hạn) |
| `403` | Không có quyền |
| `404` | Không tìm thấy resource |
| `413` | File quá lớn (vượt giới hạn upload) |
| `500` | Lỗi server |

---

## Giới hạn

| Giới hạn | Giá trị | Cấu hình |
|----------|---------|----------|
| Max upload size | 500 MB | `MAX_UPLOAD_SIZE_MB` trong `.env` |
| Max API keys/user | 10 | Hardcode trong code |
| Access token TTL | 30 phút | `ACCESS_TOKEN_EXPIRE_MINUTES` |
| Refresh token TTL | 7 ngày | `REFRESH_TOKEN_EXPIRE_DAYS` |
| FFmpeg timeout | 10 phút | Hardcode trong `video_service.py` |
