# 🧰 Agent Skills Collection

Kho lưu trữ tập trung các kỹ năng (Skills) chuyên biệt dành cho AI Coding Agents (Antigravity, Gemini, Claude, Cursor, Codex,...).

---

## 📋 Danh Mục Kỹ Năng (Skills Catalog)

Các kỹ năng được quản lý và đánh số theo thứ tự bổ sung. Mỗi kỹ năng đều có tài liệu hướng dẫn quy trình, ràng buộc kỹ thuật và kịch bản thực thi chi tiết.

| STT | Tên Skill | Thư mục | Mô tả ngắn gọn | Trạng thái |
|:---:|---|---|---|:---:|
| **01** | **chinhta** | [`skills/chinhta/`](./skills/chinhta) | Pipeline kiểm tra và sửa lỗi chính tả tiếng Việt 100% OFFLINE thuần thuật toán 8 giai đoạn (Zero-AI, tốc độ ~0.05s). Tra từ điển 74K âm tiết, kho từ ghép 4.8MB VietWords, ma trận âm vị học và N-gram real-word. | `Active` |

---

## 🚀 Hướng Dẫn Cài Đặt & Sử Dụng Cho Agent

### 1. Dành cho Google Antigravity / Gemini CLI
Sao chép thư mục skill cần dùng vào thư mục cấu hình toàn cục hoặc workspace của dự án:
```bash
# Cấu hình toàn cục (Global):
cp -r skills/chinhta ~/.gemini/config/skills/

# Hoặc cấu hình riêng cho từng Workspace:
cp -r skills/chinhta .agents/skills/
```

### 2. Kích hoạt trong Chat
Mỗi skill được kích hoạt thông qua **từ khóa tự nhiên** (Triggers) hoặc **Slash Command**:
- Ví dụ với **#01 chinhta**:
  - Gõ `/chinhta <duong_dan_file.docx>`
  - Hoặc gõ tự nhiên: *"soát lỗi chính tả file này"*, *"kiểm tra chính tả văn bản"*

---

## ➕ Quy Chuẩn Bổ Sung Kỹ Năng Mới
Khi thêm một skill mới vào kho lưu trữ này:
1. Tạo thư mục mới tại `skills/<tên-skill>/` chứa file `SKILL.md` chuẩn format.
2. Thêm một dòng mới tương ứng (**#02**, **#03**,...) vào bảng **Danh Mục Kỹ Năng** ở trên kèm mô tả ngắn gọn.
3. Commit và push thay đổi lên repo.
