# VMconsole

Web xem replay The Isle trên Windows x64, chạy tại **http://127.0.0.1:8765** bằng CMD hoặc PowerShell.

## Cài và chạy

Tải mã nguồn, giải nén vào thư mục có quyền ghi, mở PowerShell tại thư mục đó rồi chạy:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
.\VMconsole.cmd
```

Lần cài đầu cần Internet để tải Python, .NET 10 SDK và ảnh bản đồ Gateway. Script tự biên dịch decoder; không cần npm hoặc pip. Sau khi cài xong, giữ cửa sổ VMconsole mở trong lúc dùng web. Nhấn Ctrl+C hoặc đóng cửa sổ để dừng.

Lần chạy đầu chọn lần lượt:

1. Thư mục chứa replay của game, thường là `%LOCALAPPDATA%\TheIsle\Saved\Demos`.
2. File `.replay` muốn theo dõi; bấm Cancel ở hộp chọn file để tự chọn file mới nhất.
3. Thư mục riêng lưu bản sao để quét, ví dụ `D:\ReplayCopies`.

Thư mục bản sao phải tách khỏi thư mục nguồn. Chương trình sao chép file trước rồi đọc và giải mã trên bản sao. Mặc định kiểm tra mỗi 180 giây; bản không đổi được bỏ qua. Có thể đổi nguồn và thư mục bản sao trên web. Để mở lại hộp chọn, dừng phiên đang chạy rồi dùng:

```powershell
.\VMconsole.cmd -Configure
```

Hoặc truyền đường dẫn trực tiếp:

```powershell
.\VMconsole.cmd -SourceFolder 'D:\GameReplays' -ReplayFile 'demo.replay' -CopyFolder 'D:\ReplayCopies'
```

## Tính năng

- Bản đồ Gateway, vị trí người chơi và AI có trong replay.
- Nhập SteamID 17 chữ số để chọn tâm radar; không cài sẵn tài khoản.
- Khoảng cách, hướng, mũi tên và cảnh báo gần với tên loài, phần trăm trưởng thành khi replay có dữ liệu.
- Mặc định cảnh báo người chơi và AI trong 500 m; có bộ lọc, đồng đội, âm thanh và nhật ký.
- Xem lịch sử, tua timeline, đường di chuyển, theo dõi đối tượng, đo khoảng cách và xuất CSV/JSON.

Vị trí và cảnh báo phản ánh thời điểm được ghi trong replay. Replay có thể chỉ chứa các đối tượng trong phạm vi ghi hình; cập nhật mỗi 3 phút không phải vị trí trực tiếp từ game. Bản đồ cộng đồng có thể khác phiên bản địa hình đang chơi.

## Dữ liệu trên máy

Thiết lập và lịch sử mặc định nằm trong `data/`. Có thể dùng `-DataDirectory 'D:\RadarData'`. Các thư mục dữ liệu, bản replay, cấu hình tài khoản và runtime tải về đều bị loại khỏi Git. Đồng đội và một số tùy chọn giao diện được lưu trong trình duyệt.

`VMconsole` là tên script và tiêu đề cửa sổ. Tiến trình chạy dùng tên PowerShell, Python và .NET bình thường.

## Kiểm tra và đóng gói

Các kiểm tra tự động dùng dữ liệu giả, không cần replay cá nhân. Node.js chỉ cần để chạy kiểm tra JavaScript:

```powershell
.\runtime\python\python.exe -X utf8 -m unittest discover -s tests -p 'test_*.py' -q
node .\tests\test_projection.cjs
node .\tests\test_replay_model.cjs
node .\tests\test_proximity.cjs
```

Tạo ZIP script kèm runtime để chép sang máy Windows x64 khác:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build-vmconsole.ps1
```

Kết quả ở `dist/VMconsole-win-x64.zip`. Giải nén toàn bộ và chạy `VMconsole.cmd`; chọn lại đường dẫn và tài khoản trên máy mới. Bộ đóng gói từ chối trộn vào thư mục bản build đã tồn tại. ZIP dùng ảnh bản đồ được tải khi setup; xem nguồn và quyền của bên thứ ba trong [MAP-SOURCES.md](MAP-SOURCES.md).

Mã nguồn vẫn giữ các script portable/Windows Service cũ để tham khảo; cách chạy chính của phiên bản này là `VMconsole.cmd`.

## Thành phần bên thứ ba

Decoder sử dụng mã Unreal.Core từ Shiqan/FortniteReplayDecompressor, giấy phép MIT tại [vendor/UNREAL-LICENSE.txt](vendor/UNREAL-LICENSE.txt). Runtime Python và .NET được tải từ nhà phát hành chính thức. Ảnh Gateway được tải riêng từ VulnonaMAP và không nằm trong repository này; xem [MAP-SOURCES.md](MAP-SOURCES.md).
