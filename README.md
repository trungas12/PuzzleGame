# Puzzle Game

Game xếp hình ảnh viết bằng Python và Pygame theo mô hình OOP.

## Chức năng chính

- Cắt ảnh thành các mảnh ghép theo lưới `3x3`, `4x4`, `5x5` hoặc `6x6`.
- Có 4 màn chơi với 4 ảnh khác nhau trong thư mục `assets`.
- Xáo trộn bằng cách giả lập nhiều bước di chuyển hợp lệ từ trạng thái hoàn chỉnh, nên bàn chơi luôn giải được.
- Click chuột vào mảnh ghép cạnh ô trống để di chuyển.
- Hỗ trợ phím mũi tên hoặc `W A S D`.
- Đếm số bước, thời gian và số lần dùng trợ giúp.
- Lưu kỷ lục theo từng màn chơi và từng độ khó trong `du_lieu_game.json`.

## Tính năng nâng cấp

- Chọn màn trước, màn sau hoặc màn ngẫu nhiên.
- Chế độ `Người mới`: tô viền mảnh đúng/sai để dễ học.
- Chế độ `Số ô`: hiện số thứ tự trên mảnh ghép.
- Chế độ `Dễ nhìn`: tăng tương phản giao diện.
- `Gợi ý`: làm nổi bật mảnh nên di chuyển.
- `Giải 1 bước`: tự đi một bước hợp lệ nếu người chơi bị kẹt.
- `Xem ảnh`: xem nhanh ảnh gốc trên bàn chơi.
- `Ẩn ảnh / Hiện ảnh`: phù hợp cho người muốn tăng độ khó.
- `Tạm dừng`, `Hoàn tác`, `Chơi lại`, bảng hướng dẫn trong game.
- Giao diện tiếng Việt có dấu, dùng font Unicode để tránh lỗi font.

## Cài đặt

```bash
python -m pip install -r requirements.txt
```

Máy đang dùng Python 3.14 nên dự án dùng `pygame-ce`.
Thư viện này vẫn import và lập trình bằng `pygame` bình thường.

## Chạy game

```bash
python main.py
```

## Phím tắt

- Mũi tên hoặc `W A S D`: di chuyển ô trống.
- `R`: chơi lại.
- `U`: hoàn tác.
- `H`: gợi ý.
- `G`: giải 1 bước.
- `Space`: xem nhanh ảnh gốc.
- `P`: tạm dừng hoặc tiếp tục.
- `N`: màn sau.
- `B`: màn trước.
- `1`, `2`, `3`, `4`: chọn độ khó `3x3`, `4x4`, `5x5`, `6x6`.
- `F1`: mở hướng dẫn.
- `Esc`: đóng hướng dẫn hoặc thoát game.

## Cấu trúc lập trình

- `Tile`: lưu ảnh của từng mảnh ghép, vị trí hiện tại và vị trí đích.
- `Board`: quản lý bàn chơi, xáo trộn, di chuyển, hoàn tác, gợi ý và kiểm tra chiến thắng.
- `PuzzleGame`: quản lý giao diện Pygame, màn chơi, dữ liệu lưu, nút bấm và sự kiện.
- `Level`: lưu thông tin từng màn chơi như tên, file ảnh và mô tả.

## Thay ảnh màn chơi

Các ảnh nằm trong thư mục `assets`:

- `level_river_town.png`
- `level_beach.png`
- `level_city.png`
- `level_mountain.png`

Muốn thay ảnh, chỉ cần thay file tương ứng bằng ảnh vuông khác.
