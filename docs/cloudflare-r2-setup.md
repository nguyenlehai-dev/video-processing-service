# Hướng dẫn cấu hình Cloudflare R2 Storage

Cloudflare R2 dùng để lưu trữ video output sau khi xử lý. R2 tương thích S3 API nên dùng `boto3` để tương tác.

---

## Bước 1: Tạo R2 Bucket

1. Đăng nhập vào [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. Vào menu **R2 Object Storage** → **Overview**
3. Click **Create bucket**
4. Đặt tên bucket: `video-output` (hoặc tên tùy chọn)
5. Chọn region: **Automatic** (mặc định)
6. Click **Create bucket**

---

## Bước 2: Tạo API Token cho R2

1. Trong R2 Overview, click **Manage R2 API Tokens**
2. Click **Create API token**
3. Cấu hình:

| Field | Giá trị |
|-------|---------|
| **Token name** | `video-processing-service` |
| **Permissions** | **Object Read & Write** |
| **Bucket scope** | Chọn bucket `video-output` |
| **TTL** | Không giới hạn (hoặc set theo nhu cầu) |

4. Click **Create API Token**
5. Copy 3 giá trị:
   - **Access Key ID** (VD: `a1b2c3d4e5f6...`)
   - **Secret Access Key** (VD: `xyz789...`)
   - **Account ID** — tìm ở URL Dashboard: `https://dash.cloudflare.com/<ACCOUNT_ID>/r2`

> ⚠️ **Secret Access Key chỉ hiển thị 1 lần!** Lưu ngay.

---

## Bước 3: Cấu hình Public Access cho Bucket

Để video output có thể truy cập qua URL public:

1. Vào bucket `video-output` → tab **Settings**
2. Mục **Public access** → Click **Allow Access**
3. Sẽ nhận được Public URL dạng: `https://pub-xxxxxxxxxxxx.r2.dev`

Hoặc sử dụng **Custom Domain**:

1. Mục **Custom Domains** → Click **Connect Domain**
2. Nhập subdomain (VD: `cdn.xyz.com`)
3. Cloudflare sẽ tự tạo DNS record

---

## Bước 4: Cập nhật .env trên VPS

```bash
ssh vpsroot@ssh.vpspanel.io.vn
cd ~/video-processing-service
nano .env
```

Cập nhật các dòng:

```env
R2_ACCOUNT_ID=a1b2c3d4e5f6g7h8i9j0
R2_ACCESS_KEY_ID=your-access-key-id
R2_SECRET_ACCESS_KEY=your-secret-access-key
R2_BUCKET_NAME=video-output
R2_PUBLIC_URL=https://pub-xxxxxxxxxxxx.r2.dev
```

---

## Bước 5: Restart API container

```bash
sudo docker compose restart api

# Kiểm tra logs
sudo docker compose logs -f api
```

---

## Bước 6: Test upload

```bash
# Trên VPS, test upload thử
sudo docker compose exec api python3 -c "
from app.services.storage_service import upload_file_to_r2
# Tạo file test
with open('/tmp/test.txt', 'w') as f:
    f.write('hello r2')
result = upload_file_to_r2('/tmp/test.txt', 'test/hello.txt')
print(f'Upload result: {result}')
"
```

Nếu thấy URL → **R2 đã kết nối thành công!**

---

## Cấu trúc lưu trữ trên R2

```
video-output/               ← Bucket
├── output/                  ← Video output sau xử lý
│   ├── <job_id>.mp4
│   ├── <job_id>.mp3         ← Extract audio output
│   └── ...
└── test/                    ← Test files
```

---

## Pricing (Tham khảo)

| Resource | Free Tier | Giá |
|----------|-----------|-----|
| **Storage** | 10 GB/tháng | $0.015/GB/tháng |
| **Class A ops** (PUT, POST) | 1M/tháng | $4.50/1M ops |
| **Class B ops** (GET) | 10M/tháng | $0.36/1M ops |
| **Egress** (data ra) | **Miễn phí** | $0 (luôn luôn) |

> 💡 **Lợi thế R2 so với S3:** Egress (download bandwidth) hoàn toàn miễn phí!

---

## Xử lý lỗi thường gặp

| Lỗi | Nguyên nhân | Cách sửa |
|-----|------------|----------|
| `ClientError: Access Denied` | Token không có quyền Object Write | Tạo lại token với đúng quyền |
| `ClientError: NoSuchBucket` | Tên bucket sai | Kiểm tra `R2_BUCKET_NAME` trong `.env` |
| `EndpointConnectionError` | Account ID sai | Kiểm tra `R2_ACCOUNT_ID` |
| Upload thành công nhưng URL 403 | Bucket chưa bật public access | Bật Public Access trong Settings |
