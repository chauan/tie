# Replay Radar chạy bằng Windows Service

Mở **ReplayRadar.exe** để quản lý ứng dụng bằng cửa sổ đồ họa. Không cần mở CMD hay PowerShell khi sử dụng.

1. Giải nén đầy đủ gói vào thư mục trên máy Windows x64.
2. Mở `ReplayRadar.exe`, bấm **Chọn folder…** ở mục 1 để chọn thư mục chứa `demo.replay` (hoặc replay khác), chọn file ở mục 2. Chọn **Tự chọn file mới nhất** nếu muốn đổi theo phiên chơi.
3. Ở mục 3, chọn **thư mục bản sao để quét** riêng, rồi bấm **Lưu / cập nhật dịch vụ** và chấp nhận yêu cầu quản trị Windows (UAC). Hai thư mục phải tách rời; không chọn thư mục gốc, thư mục con của nó hoặc thư mục chương trình làm nơi quét.
4. Bấm **Mở web**, nhập/chọn SteamID làm tâm radar. Sau khi cài, có thể đóng cửa sổ quản lý; Windows tiếp tục chạy service và tự chạy lại khi khởi động máy.

Trình quản lý có nút **Chạy**, **Dừng**, **Gỡ dịch vụ**, **Mở web** và **Mở thư mục log**. Gỡ dịch vụ giữ dữ liệu và trình quản lý để có thể cài lại. Nếu chuyển sang thư mục replay riêng khác, mở trình quản lý và cài/cập nhật lại để cấp quyền đọc cho thư mục mới.

Luồng xử lý: **thư mục gốc → copy file vào thư mục bản sao đã chọn → đọc cấu trúc và giải mã bản sao → cập nhật web**. Việc đọc cấu trúc/chunk không chạy trên file gốc. Bản đang ghi dở được copy đến kích thước đã chụp, xác định chunk hoàn chỉnh trên bản copy rồi cắt bỏ phần dở trước khi giải mã. Có nút **Mở bản sao** để kiểm tra; service giữ 3 bản raw do nó tạo và không tự xóa file khác được đặt trong thư mục đó.

Tên dịch vụ trong Services là `ReplayRadar`, tên hiển thị **Replay Radar (The Isle)**. Đây là Windows Service thông thường, vẫn được Windows liệt kê trong Services/Task Manager. Không có cơ chế che giấu tiến trình hoặc né phần mềm kiểm tra.

- Chương trình cài tại `%ProgramFiles%\ReplayRadar`, dữ liệu/cấu hình/log tại `%ProgramData%\ReplayRadar`.
- Tài khoản service riêng `NT SERVICE\ReplayRadar` được cấp quyền đọc thư mục replay đã chọn và quyền ghi thư mục dữ liệu; thư mục chương trình giữ quyền thực thi/đọc. Service không chạy bằng LocalSystem.
- Service host khởi chạy Python đi kèm trực tiếp, không chạy `cmd.exe`, PowerShell hay batch ở nền. Khi dừng, host yêu cầu backend thoát; Windows job object dọn các tiến trình con thuộc ứng dụng nếu cần.
- Bản cài mới không có SteamID mặc định. Khi chuyển từ bản đã dùng, thiết lập tài khoản và lịch sử nén hiện có được giữ lại; replay gốc không bị sửa/xóa và bản replay thô không được sao chép vào thư mục cài.
- Log backend xoay ở 5 MiB, giữ 3 bản dự phòng; log host giữ một bản dự phòng. Service chỉ phục vụ tại `127.0.0.1`.
- Hai EXE cần .NET Framework 4.8 của Windows, bên cạnh Python/.NET 10 đi kèm gói.

Kỹ thuật dùng API [ServiceBase của Microsoft](https://learn.microsoft.com/en-us/dotnet/api/system.serviceprocess.servicebase?view=netframework-4.8.1), tài khoản service và [Windows job object](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).

Kiểm tra không cần quyền quản trị: `python tests/test_windows_service.py` chạy chính service host ở chế độ kiểm tra riêng, xác nhận giải mã replay thật, cấu hình ngoài thư mục chương trình, dừng backend và dọn tiến trình khi host kết thúc. Kiểm tra đăng ký/khởi động thực tế qua Windows Service Control Manager cần UAC/quyền quản trị.
