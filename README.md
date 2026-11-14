# VMconsole

Web xem replay The Isle trên Windows x64, chạy tại **http://127.0.0.1:8765** bằng CMD hoặc PowerShell.

Giao diện sinh tồn dùng nền rừng/núi lửa, viền đồng, chân dung Allosaurus/Carnotaurus và font Barlow Condensed đi kèm. Bản đồ nằm cạnh bảng chỉ số dino trên desktop và xếp dọc trên điện thoại. Chọn dino bằng bàn phím giữ nguyên focus khi dữ liệu được vẽ lại. Thiết lập radar/Telegram mở từ nút trên đầu trang hoặc khối thu gọn bên dưới. Ảnh và font chạy offline; nguồn và giấy phép tại [SURVIVAL-ART.md](web/assets/SURVIVAL-ART.md).

Mục **Hiệu ứng đang dính** hiện tên từng trạng thái, mốc ghi nhận và độ cũ so với thời điểm đang xem: vệ sinh kém, thiếu dịch cơ thể, đục thủy tinh thể, xương giòn, bệnh và gãy xương đầu/thân/chân. Hiệu ứng của bạn cũng hiện ở thanh tổng quan; CSV có tên hiệu ứng. Trạng thái chưa có dữ liệu được phân biệt với đã ghi nhận không có hiệu ứng. Nguồn đối chiếu tại [EFFECTS-SOURCES.md](EFFECTS-SOURCES.md).

## Cài và chạy

Tải mã nguồn, giải nén vào thư mục có quyền ghi, mở PowerShell tại thư mục đó rồi chạy:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
.\VMconsole.cmd
```

Lần cài đầu cần Internet để tải Python, .NET 10 SDK và ảnh bản đồ Gateway. Script tự biên dịch decoder; không cần npm hoặc pip. Sau khi cài xong, giữ cửa sổ VMconsole mở trong lúc dùng web. Nhấn Ctrl+C hoặc đóng cửa sổ để dừng.

Để đóng gói bản mới vào thư mục riêng và giữ gói cũ, chạy `powershell -NoProfile -ExecutionPolicy Bypass -File .\build-vmconsole.ps1 -OutputDirectory '.\dist\release-moi'`. Bộ đóng gói hỗ trợ Python 3.10 trở lên và kèm Python/.NET để chạy trên máy khác.

Lần chạy đầu chọn lần lượt:

1. Thư mục chứa replay của game, thường là `%LOCALAPPDATA%\TheIsle\Saved\Demos`.
2. File `.replay` muốn theo dõi; bấm Cancel ở hộp chọn file để tự chọn file mới nhất.
3. Thư mục riêng lưu bản sao để quét, ví dụ `D:\ReplayCopies`.

Thư mục bản sao phải tách khỏi thư mục nguồn. Chương trình sao chép file trước rồi đọc và giải mã trên bản sao. Mặc định kiểm tra mỗi 20 giây; bản không đổi được bỏ qua. Có thể đổi nguồn và thư mục bản sao trên web. Để mở lại hộp chọn, dừng phiên đang chạy rồi dùng:

```powershell
.\VMconsole.cmd -Configure
```

Hoặc truyền đường dẫn trực tiếp:

```powershell
.\VMconsole.cmd -SourceFolder 'D:\GameReplays' -ReplayFile 'demo.replay' -CopyFolder 'D:\ReplayCopies'
```

## Tính năng

- **Stamina (thể lực):** chọn một đối tượng để xem thanh stamina, giá trị hiện tại/tối đa, phần trăm và mốc ghi nhận. Danh sách đối tượng và CSV cũng có stamina. Chỉ số theo đúng thời điểm đang xem trên timeline; replay cũ hoặc đối tượng thiếu dữ liệu sẽ hiện chưa có, không mặc định đầy thể lực. Dữ liệu cập nhật theo lần đồng bộ replay.
- **Chỉ số mở rộng:** Weight đọc trực tiếp, Blood, FoodValue/RottenValue, hướng quay, vận tốc, GroupId/trưởng nhóm và trạng thái hành động/hiệu ứng. Giao diện ưu tiên bản đồ và dino đang chọn; bỏ Coelacanth và các cách viết tương đương. Chi tiết tại [VITALS-SOURCES.md](VITALS-SOURCES.md).
- **Telegram:** cảnh báo dino trong 1.000 m lớn hơn bạn ít nhất 10% theo cân nặng ước tính. Chạy từ service, chống lặp, có thể bỏ qua đồng đội. Nhập Bot Token/Chat ID trong mục **Cảnh báo Telegram**; hướng dẫn tại [TELEGRAM.md](TELEGRAM.md). Có thể báo độc lập khi HP hiện tại của mục tiêu dưới 50% HP hiện tại của bạn; tin kèm thông tin dino và tuổi dữ liệu.
- Bản đồ Gateway, vị trí người chơi và AI có trong replay.
- Mục **Khu đông AI**: tô mật độ theo ô 250, 500 hoặc 1.000 m; xếp hạng top 5 hoặc xem toàn bộ ô có AI, lọc theo loài và bấm một ô để phóng tới trên map. Số lượng đổi theo mốc timeline; không tính AI đã chết hoặc mất dấu. Khoảng cách/hướng tới tâm ô chỉ hiện khi có vị trí tài khoản được chọn tại cùng mốc.
- Nhập SteamID 17 chữ số để chọn tâm radar; không cài sẵn tài khoản.
- Bấm một dino để xem **máu hiện tại/tối đa, % HP và thanh máu** tại mốc đang xem. Cân nặng có nhãn **ước tính từ máu tối đa**, chỉ áp dụng cho lớp khủng long; chưa có nguồn kg riêng được xác minh. Không gán cân nặng của động vật AI từ HP. Xem cách đọc và giới hạn tại [VITALS-SOURCES.md](VITALS-SOURCES.md).
- Khoảng cách, hướng, mũi tên và cảnh báo gần với tên loài, phần trăm trưởng thành khi replay có dữ liệu.
- Mặc định cảnh báo người chơi và AI trong 500 m; có bộ lọc, đồng đội, âm thanh và nhật ký.
- Xem lịch sử, tua timeline, đường di chuyển, theo dõi đối tượng, đo khoảng cách và xuất CSV/JSON.

Vị trí và cảnh báo phản ánh thời điểm được ghi trong replay. Replay có thể chỉ chứa các đối tượng trong phạm vi ghi hình; cập nhật mỗi 20 giây không phải vị trí trực tiếp từ game. Bản đồ cộng đồng có thể khác phiên bản địa hình đang chơi.

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
node .\tests\test_ai_density.cjs
node .\tests\test_vitals.cjs
.\runtime\dotnet\dotnet.exe run --project .\tests\VitalsDecoderChecks -c Release
```

Khi web đang chạy, `tests/browser_ai_density.py` kiểm tra dữ liệu thật qua API chỉ đọc, rồi kiểm tra giao diện với dữ liệu giả trong một browser context riêng. Kiểm tra này cần Python có Playwright và Chrome; ảnh kiểm tra lưu trong `qa/`, không đưa lên Git.

`tests/browser_vitals.py` kiểm tra HP trên bản replay có dữ liệu máu, rồi kiểm tra tua timeline, dữ liệu thiếu/cũ, nhãn cân nặng ước tính, CSV và màn hình nhỏ bằng dữ liệu giả trong context riêng.

Sau khi cập nhật mã nguồn có thay đổi decoder, chạy `powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1 -Rebuild`. Bản sao cũ dùng lịch sử schema 1 sẽ hiện chưa có chỉ số HP; kết quả giải mã mới dùng schema 2. Máu hiển thị là giá trị cuối cùng được ghi ở hoặc trước mốc đang xem, kèm thời điểm quan sát trong bảng chi tiết.

Tạo ZIP script kèm runtime để chép sang máy Windows x64 khác:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build-vmconsole.ps1
```

Kết quả ở `dist/VMconsole-win-x64.zip`. Giải nén toàn bộ và chạy `VMconsole.cmd`; chọn lại đường dẫn và tài khoản trên máy mới. Bộ đóng gói từ chối trộn vào thư mục bản build đã tồn tại. ZIP dùng ảnh bản đồ được tải khi setup; xem nguồn và quyền của bên thứ ba trong [MAP-SOURCES.md](MAP-SOURCES.md).

Mã nguồn vẫn giữ các script portable/Windows Service cũ để tham khảo; cách chạy chính của phiên bản này là `VMconsole.cmd`.

## Thành phần bên thứ ba

Decoder sử dụng mã Unreal.Core từ Shiqan/FortniteReplayDecompressor, giấy phép MIT tại [vendor/UNREAL-LICENSE.txt](vendor/UNREAL-LICENSE.txt). Runtime Python và .NET được tải từ nhà phát hành chính thức. Ảnh Gateway được tải riêng từ VulnonaMAP và không nằm trong repository này; xem [MAP-SOURCES.md](MAP-SOURCES.md).
