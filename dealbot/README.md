# dealbot - Bot Affiliate Facebook & Kênh Telegram Tự Động Hóa 95%

## 1. Cài đặt & Chuẩn bị
1. Cài đặt thư viện:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
2. Cấu hình biến môi trường:
   - Copy `.env.example` -> `.env`
   - Điền các API Key: `ANTHROPIC_API_KEY`, `GOOGLE_CSE_KEY`, `GOOGLE_CSE_CX`, `ACCESSTRADE_TOKEN`
   - Điền Telegram:
     - `TELEGRAM_BOT_TOKEN` & `TELEGRAM_CHAT_ID`: nhận cảnh báo admin & báo cáo hàng ngày
     - `TELEGRAM_CHANNEL_ID` & `TELEGRAM_INVITE_LINK`: kênh Telegram riêng đăng bản tin chính thức & kéo phễu
3. Chuẩn bị Cookie 2 nick Facebook:
   - Đăng nhập 2 nick trên cùng máy/mạng với máy chạy bot (tránh checkpoint IP lạ).
   - Dùng extension Cookie-Editor, bấm Export dạng JSON và lưu vào:
     - `cookies/nick_a.json`
     - `cookies/nick_b.json`

## 2. Các chức năng mới nâng cấp
1. **Gắn Sub-ID theo dõi chuyển đổi (`modules/affiliate.py`)**:
   - Tự động gắn Sub-ID (`sub1`..`sub4` cho Accesstrade, `sub_id1`..`sub_id3` cho Shopee, và chuẩn UTM) theo định dạng: `[nick]__[group]__[deal_id]__[goc_viet]`.
   - Giúp bạn xem báo cáo trên network affiliate để biết chính xác nhóm nào, nick nào ra đơn thật.
2. **Tự học & Chấm điểm uy tín Group (`modules/poster.py`)**:
   - Mỗi nhóm có `priority_score` (mặc định 100 điểm).
   - Đăng thành công: +5 điểm, ưu tiên đăng nhiều hơn.
   - Thất bại hoặc bị từ chối: -25 điểm. Nếu dính **3 lỗi liên tiếp**, tự động chuyển sang `cooling_down` (tạm dừng 7 ngày) và thông báo về Telegram.
3. **Cơ chế Retry Comment Link (`modules/poster.py`)**:
   - Phát hiện nhóm bật duyệt bài ("bài viết đang chờ phê duyệt").
   - Hẹn giờ tự động quay lại sau 45 - 60 phút kiểm tra. Nếu admin đã duyệt, bot tự động vào comment link affiliate.
4. **Phễu & Phát sóng Kênh Telegram riêng (`modules/telegram_channel.py`)**:
   - Đăng trực tiếp bản tin mã giảm giá & top deal lên Kênh Telegram của bạn bằng Bot API (100% an toàn, xây dựng tài sản cá nhân lâu dài).
   - Tự động chèn câu kêu gọi tham gia nhóm Telegram vào cuối comment hoặc bài viết Facebook.
5. **Kiểm tra giá thật & deal còn hàng (`modules/deals.py`)**:
   - Hàm `still_valid()` kiểm tra mã HTTP và nội dung trang trước khi đăng, loại bỏ sản phẩm bị 404, bị xóa hoặc báo hết hàng.
6. **Nuôi nick tự động nhẹ (`warmup`)**:
   - Lướt newsfeed, đọc bài, thả tim nhẹ nhàng 2 lần/ngày (10h & 15h) để giữ cookie hoạt động ổn định và tránh bị Facebook gắn cờ.

## 3. Vòng chạy hàng ngày (Daily Schedule)
| Giờ | Công việc | Module |
|---|---|---|
| **Thứ 2, 05:00** | Sinh từ khóa bằng AI, gom group ứng viên qua Google CSE API, xuất `groups_review.csv` | `groups` |
| **Mỗi 30 phút** | Nhập lại file bạn đã duyệt, gán group cố định cho nick, hồi phục nhóm `cooling_down` | `groups` |
| **Mỗi 3 tiếng** | Cào deal, lọc ngưỡng, chấm điểm chất lượng, vẽ badge ảnh | `deals` |
| **06h, 10h, 16h** | Cập nhật mã giảm giá từ Accesstrade và `events.yaml` | `coupons` |
| **07:30** | Lên lịch trong ngày: chọn top deal, ghép nick + group, AI viết caption, gắn Sub-ID, đặt phễu | `planner` |
| **Mỗi 5 phút** | Đăng các bài đến giờ, kiểm tra deal còn hợp lệ, retry comment duyệt bài | `poster` |
| **10:00 & 15:00** | Nuôi nick tự động nhẹ (lướt newsfeed, thả tim tự nhiên) | `poster` |
| **11:15 & 19:15** | Đăng bản tin mã giảm giá lên Kênh Telegram chính thức | `telegram_channel` |
| **22:30** | Gửi báo cáo tổng kết chi tiết hoạt động trong ngày qua Telegram | `main` |

## 4. Các lệnh chạy thử / thao tác nhanh
- Khám phá nhóm mới: `python main.py discover`
- Nhập nhóm đã duyệt: `python main.py import`
- Cào deal: `python main.py deals`
- Cào mã giảm giá: `python main.py coupons`
- Lập lịch ngày hôm nay: `python main.py plan`
- Đăng bài đang chờ: `python main.py post`
- Chạy nuôi tương tác nick: `python main.py warmup`
- Đăng bản tin lên kênh Telegram: `python main.py channel`
- Xem báo cáo ngày: `python main.py report`
- Khởi động toàn bộ lịch trình chạy ngầm: `python main.py`
