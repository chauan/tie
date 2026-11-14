# Chạy Replay Radar trên máy Windows khác

1. Chép `ReplayRadar-win-x64.zip` sang máy Windows x64 và **giải nén toàn bộ** vào thư mục bạn có quyền ghi, ví dụ thư mục Downloads. Không chạy từ bên trong ZIP.
2. Mở `check.cmd` để kiểm tra Python, hai runtime .NET và bộ giải mã đã đi kèm. Bản ZIP đủ không cần cài Python, .NET SDK, npm hoặc quyền administrator.
3. Mở `start.cmd`, giữ cửa sổ service và truy cập **http://127.0.0.1:8765**. Nhấn Ctrl+C để dừng.
4. Nhập **SteamID 17 chữ số** trong khối Radar của bạn, tên gợi nhớ là tùy chọn, rồi bấm **Lưu tài khoản**. Hoặc chọn một người chơi và bấm **Dùng làm tâm radar**. Bản mới không chứa sẵn tài khoản nào.
5. Service tự tìm `%LOCALAPPDATA%\TheIsle\Saved\Demos` của tài khoản Windows hiện tại. Nếu game lưu chỗ khác, mở **Nguồn replay** để chọn lại. Cần có replay Gateway được game ghi và có vị trí tài khoản đã chọn; nhập SteamID không làm xuất hiện người chơi ngoài dữ liệu replay.

Muốn chạy nền: `powershell -NoProfile -ExecutionPolicy Bypass -File .\service.ps1 -Action Start`. Dừng bằng `stop.cmd`, hoặc `service.ps1 -Action Stop`. Không chạy hai bản cùng cổng. Có thể dùng `service.ps1 -Action Start -Port 8767` và mở cổng đó nếu cần một phiên riêng.

Thiết lập nguồn và tài khoản nằm trong `data/config.json` / `data/player-profile.json` của từng bản chạy portable. Thiết lập `config.json` ở thư mục gốc của bản cũ vẫn được đọc khi chưa có cấu hình mới. Đồng đội, âm thanh và nhật ký lưu trong trình duyệt; nhật ký tách theo SteamID làm tâm radar. Bộ cài không chứa replay, đường dẫn cá nhân, SteamID hay nhật ký từ máy đóng gói. Lần nâng cấp trên máy cũ tự chuyển thiết lập tài khoản cũ sang định dạng mới.

Nếu muốn dùng Windows Service không mở CMD, dùng gói `ReplayRadar-Service-win-x64.zip` và mở **ReplayRadar.exe**. Hướng dẫn tại [WINDOWS-SERVICE.md](WINDOWS-SERVICE.md); chế độ này cần UAC khi cài và lưu dữ liệu riêng dưới ProgramData.

Bản portable kèm Python embeddable [từ Python Software Foundation](https://www.python.org/downloads/release/python-31410/), kiểm tra SHA-256 khi tải, và hai runtime .NET đang dùng để chạy decoder. Giấy phép Python ở `runtime/python/LICENSE.txt`, .NET ở `runtime/dotnet/LICENSE.txt`, bộ đọc Unreal ở `licenses/UNREAL-LICENSE.txt`; nguồn bản đồ ghi trong `MAP-SOURCES.md`.

Khả năng chuyển máy được thử bằng cách giải nén sang thư mục có dấu/khoảng trắng, đổi LOCALAPPDATA, loại Python/.NET hệ thống khỏi PATH và chạy toàn bộ pipeline với replay thật. Đây là thử nghiệm môi trường độc lập trên cùng máy Windows, chưa phải kiểm thử trên một máy vật lý khác.

Để tạo một đợt phát hành mới và giữ gói cũ, truyền `-OutputDirectory` cho `build-portable.ps1`, `build-vmconsole.ps1` hoặc `build-service-package.ps1`, ví dụ `powershell -NoProfile -ExecutionPolicy Bypass -File .\build-vmconsole.ps1 -OutputDirectory 'G:\tte\releases\2026-11-14'`. Bộ đóng gói hỗ trợ Python 3.10 trở lên và từ chối ghi đè thư mục gói đã tồn tại. Bản mới đi kèm toàn bộ ảnh giao diện, font Barlow Condensed và giấy phép để hiển thị khi không có Internet.
