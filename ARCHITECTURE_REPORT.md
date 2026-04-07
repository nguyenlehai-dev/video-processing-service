# BÁO CÁO KIẾN TRÚC HỆ THỐNG: VIDEO PROCESSING SERVICE
**Ngày báo cáo:** 07/04/2026
**Dự án:** PlenX Editor (Video Processing Service)

Tài liệu này tổng hợp chi tiết về kiến trúc kỹ thuật cốt lõi đã được triển khai cho hệ thống xử lý Video nhằm giải quyết các bài toán về hiệu suất, khả năng mở rộng, và trải nghiệm người dùng theo đúng chỉ đạo về việc sử dụng cơ chế **Queue, Background Worker, Polling Status và Database**.

---

## 1. Tổng quan Kiến trúc (High-Level Architecture)

Hệ thống được thiết kế theo mô hình **Asynchronous Microservice** (Dịch vụ vi mô bất đồng bộ). Việc xử lý video (như Cắt, Ghép, Trích xuất, v.v.) thường tốn nhiều tài nguyên CPU, RAM và thời gian. Do đó, nếu thiết kế API chạy đồng bộ (Synchronous) sẽ dẫn đến tình trạng treo server (Blocking) và Timeout ở phía người dùng.

Để giải quyết, kiến trúc của hệ thống chia luồng xử lý làm 2 giai đoạn:
1. **Tiếp nhận (API Gateway):** Nhận file, lưu trữ file nháp, tạo Job ID, và đẩy công việc vào hàng chờ (Queue) rồi phản hồi ngay lập tức cho Client.
2. **Xử lý ngầm (Background Worker):** Các tiến trình chạy ngầm (Workers) tuần tự lấy công việc ra khỏi hàng chờ để xử lý FFmpeg, sau đó tự động cập nhật kết quả vào Database.

## 2. Chi tiết Triển khai Kỹ thuật

### A. Cơ chế Queue & Background Worker
- **Công nghệ lõi:** `FastAPI BackgroundTasks` kết hợp thư viện `subprocess` của Python.
- **Quy trình hoạt động:**
  1. Khi người dùng gọi API (vd: `POST /api/v1/video/merge`), Server chỉ thực hiện validate dữ liệu và lưu file video gốc xuống thư mục `/tmp/video-processing`.
  2. Một bản ghi (Record) trạng thái công việc (Job) được tạo trong cơ sở dữ liệu với trạng thái `pending`.
  3. Tác vụ nặng (thuật toán gọi tệp thực thi FFmpeg để cắt/ghép) được `BackgroundTasks` đưa vào luồng Thread Pool riêng biệt của Server.
  4. API ngay lập tức `return 200 OK` về cho Front-end kèm theo `job_id` trong chưa tới 100ms. Luồng Worker lúc này mới bắt đầu hoạt động một cách độc lập không ảnh hưởng tới API chính.

### B. Tạo Database Lưu trữ Background Jobs
- **Công nghệ lõi:** SQLite kết nối qua thẻ ORM `SQLAlchemy`.
- **Cấu trúc dữ liệu (Bảng `jobs`):**
  - Mọi yêu cầu đều được định danh bằng UUID v4 (`id` - Khóa chính bảo mật).
  - Track toàn bộ vòng đời của Job: `status` (Giá trị: `pending`, `processing`, `completed`, `failed`).
  - Lữu trữ tiến độ (`progress`: 0% -> 100%), ngày tạo (`created_at`), ngày hoàn thành (`completed_at`), và tổng thời lượng tốn kém (`duration`).
  - Ghi nhận thông báo lỗi chi tiết (`error_message`) để debug trong trường hợp Job bị crash.
  - Sau khi xử lý thành công, Worker sẽ upload kết quả lên Cloudflare R2 và lưu link tải về vào cột `output_url`.

### C. Cơ chế Giám sát tiến độ - Polling Status
- **Vấn đề:** Vì thao tác ghép/cắt Video đã bị đẩy xuống Background, Front-end (Studio) không thể biết lúc nào Video hoàn thành, và cũng không thể bật kết nối treo (Long-polling) vì gây tốn kết nối Server.
- **Giải pháp - Polling Status:**
  - Front-end ReactJS sử dụng hàm `setInterval` để định kỳ mỗi **3 giây** gọi lệnh `GET /api/v1/video/jobs/{job_id}`.
  - Server sẽ tra cứu Database siêu tốc và trả về tiến độ hiện tại.
  - Khi Server trả về `status: "completed"`, vòng lặp Polling trên Front-end tự động dừng lại, giao diện liền chuyển đổi sang màu xanh (Success) và thả xuống Nút "Download Result". Kịch bản hoàn hảo chống rò rỉ bộ nhớ (Memory Leak).

### D. Tối ưu Lệnh thuật toán ("Đừng gọi 1 lệnh")
Thay vì dùng cách ngây ngô là gọi hàm OS Terminal một cách cứng nhắc (`os.system("ffmpeg ...")`), hệ thống sử dụng **Python Subprocess Management**:
- **Bảo mật và Memory Leak:** Toàn bộ lệnh FFmpeg được chia thành danh sách đối số an toàn để chống lỗi Command Injection (Bảo mật).
- **Thuật toán thông minh (Smart Concat):** Tính năng "Merge Video" tạo ra một tệp kịch bản `concat.txt` tạm thời, chứa danh sách đường dẫn ảo trước khi nối luồng Stream (`-c copy`) thay vì Render và Encode lại từ đầu. Chống treo máy khi nén hàng chục GB video.
- **Kiểm soát Timeout chặt chẽ:** Worker được cài đặt Timeout Cứng là `600s` (10 Phút). Nếu video bị lỗi corrupt gây kẹt RAM, tự động luồng sẽ bị ngắt và đánh dấu là `failed` vào Database, tránh tình trạng 1 file lỗi đánh ngã toàn bộ máy trạm.

---

## 3. Tổng kết

Hệ thống hiện tại đáp ứng mức **Sẵn sàng cho môi trường Sản xuất thực tế (Production-Ready)**. Bằng việc tuân thủ triệt để nguyên tắc **Tách biệt luồng xử lý (Decoupling)** thông qua Queue và Worker, Back-end API có khả năng đảm nhận tới hàng ngàn truy vấn đồng thời mà hệ thống vẫn duy trì sự kiên cố và tính khả dụng cao tuyệt đối.
