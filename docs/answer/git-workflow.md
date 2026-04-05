# Git Workflow - Video Processing Service

## Tổng quan

Dự án sử dụng **Gitflow Workflow** để quản lý mã nguồn, đảm bảo quy trình phát triển rõ ràng và kiểm soát chất lượng code trước khi triển khai.

> **Quy tắc chung:** Mọi commit đều phải đi kèm Issue ID.

---

## Cấu trúc nhánh

### Nhánh chính

| Nhánh | Mục đích | Quy tắc |
|-------|----------|---------|
| `prod` | Code chạy trên môi trường **production** | Chỉ merge qua PR sau khi kiểm tra kỹ. **Không push trực tiếp.** |
| `staging` | Kiểm tra **QA** và **demo** | Chỉ merge qua PR. **Không push trực tiếp.** |
| `dev` | Nhánh phát triển chính, nơi tất cả feature được hợp nhất | Merge từ các nhánh feature qua PR. |

### Nhánh phụ

| Loại nhánh | Format | Ví dụ | Tạo từ |
|------------|--------|-------|--------|
| Feature | `feat/<feature_name>` | `feat/login_page` | `dev` |
| Hotfix | `hotfix/<hotfix_name>` | `hotfix/fix_login_error` | `prod` |

---

## Luồng làm việc

### 1. Phát triển Feature

```
dev ──► feat/xxx ──► PR vào dev ──► merge dev → staging ──► merge staging → prod
```

**Các bước chi tiết:**

1. **Tạo nhánh feature** từ `dev`:
   ```bash
   git checkout dev
   git pull origin dev
   git checkout -b feat/<feature_name>
   ```

2. **Làm việc trên nhánh feature**, commit và push lên remote:
   ```bash
   git add .
   git commit -m "feat: mô tả ngắn gọn #issue_id"
   git push origin feat/<feature_name>
   ```

3. **Tạo Pull Request** từ `feat/<feature_name>` → `dev` trên GitHub.

4. **Review code** → Approve → **Merge PR** vào `dev`.

5. Khi các feature đủ ổn định, **merge `dev` → `staging`** để kiểm thử/demo.

6. Sau khi kiểm tra xong, **merge `staging` → `prod`** để triển khai production.

---

### 2. Xử lý Hotfix

Hotfix là các bản sửa lỗi **khẩn cấp** áp dụng trực tiếp cho production.

```
prod ──► hotfix/xxx ──► PR vào prod ──► đồng bộ prod → staging & dev
```

**Các bước chi tiết:**

1. **Tạo nhánh hotfix** từ `prod`:
   ```bash
   git checkout prod
   git pull origin prod
   git checkout -b hotfix/<hotfix_name>
   ```

2. **Sửa lỗi**, commit và push lên remote:
   ```bash
   git add .
   git commit -m "fix: mô tả lỗi đã sửa #issue_id"
   git push origin hotfix/<hotfix_name>
   ```

3. **Tạo PR** từ `hotfix/<hotfix_name>` → `prod`. Approve → Merge.

4. **Đồng bộ** `prod` vào `staging` và `dev`:
   ```bash
   # Đồng bộ staging
   git checkout staging
   git pull origin staging
   git merge prod
   git push origin staging

   # Đồng bộ dev
   git checkout dev
   git pull origin dev
   git merge prod
   git push origin dev
   ```

---

## Quy ước Commit Message

Sử dụng format [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <mô tả ngắn gọn> #<issue_id>
```

### Các type thường dùng

| Type | Mô tả | Ví dụ |
|------|--------|-------|
| `feat` | Thêm tính năng mới | `feat: add homepage #12` |
| `fix` | Sửa lỗi | `fix: resolve login bug #34` |
| `docs` | Thay đổi tài liệu | `docs: update README #5` |
| `style` | Format code, không thay đổi logic | `style: fix indentation #8` |
| `refactor` | Tái cấu trúc code | `refactor: simplify auth flow #15` |
| `test` | Thêm hoặc sửa test | `test: add unit tests for auth #20` |
| `chore` | Công việc bảo trì, config | `chore: update dependencies #25` |

---

## Sơ đồ luồng

```
                    ┌─────────────────────────────────────────┐
                    │              PRODUCTION (prod)           │
                    └──────▲──────────────┬───────────▲────────┘
                           │              │           │
                     merge staging    đồng bộ     merge hotfix
                       → prod        prod →        → prod
                           │        staging &         │
                           │          dev             │
                    ┌──────┴──────────────┴────────────┴───────┐
                    │              STAGING (staging)            │
                    └──────▲───────────────────────────────────┘
                           │
                      merge dev
                       → staging
                           │
                    ┌──────┴───────────────────────────────────┐
                    │              DEVELOPMENT (dev)            │
                    └──▲───────▲───────▲───────▲───────▲───────┘
                       │       │       │       │       │
                     merge   merge   merge   merge   merge
                       │       │       │       │       │
                    ┌──┴──┐ ┌──┴──┐ ┌──┴──┐ ┌──┴──┐ ┌──┴──┐
                    │feat/│ │feat/│ │feat/│ │feat/│ │feat/│
                    │  A  │ │  B  │ │  C  │ │  D  │ │  E  │
                    └─────┘ └─────┘ └─────┘ └─────┘ └─────┘
```

---

## Lưu ý quan trọng

1. **Luôn review code** trước khi merge bất kỳ PR nào.
2. **Không push trực tiếp** vào `prod` và `staging` — chỉ merge qua PR.
3. **Luôn pull trước khi tạo nhánh mới** để đảm bảo code mới nhất.
4. **Đồng bộ các nhánh sau hotfix** (`prod` → `staging` → `dev`).
5. **Xóa nhánh feature/hotfix** sau khi đã merge xong để giữ repo sạch sẽ:
   ```bash
   # Xóa local
   git branch -d feat/<feature_name>
   # Xóa remote
   git push origin --delete feat/<feature_name>
   ```
6. **Giải quyết conflict** tại nhánh feature trước khi tạo PR:
   ```bash
   git checkout feat/<feature_name>
   git merge dev
   # Giải quyết conflict nếu có
   git push origin feat/<feature_name>
   ```
