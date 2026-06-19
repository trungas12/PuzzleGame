import array
import json
import math
import os
import random
import sys
import time
from dataclasses import dataclass
import pygame

# Đường dẫn thư mục gốc và file lưu trữ cấu hình game
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
SAVE_PATH = os.path.join(BASE_DIR, "du_lieu_game.json")

# Kích thước màn hình chính và các thông số layout chuẩn
SCREEN_WIDTH = 1160
SCREEN_HEIGHT = 720
BOARD_SIZE = 520
BOARD_LEFT = 34
BOARD_TOP = 126
PANEL_LEFT = 590
PANEL_TOP = 42
PANEL_WIDTH = 536
PANEL_HEIGHT = 640
FPS = 60

# BẢNG MÀU CHỦ ĐẠO - MODERN INK & INDIGO DESIGN (Thiết kế phong cách tối thanh lịch, thống nhất)
BG_COLOR = (10, 15, 26)          # Nền cửa sổ chính (Ink Black - Đen mực sâu thẳm)
PANEL_COLOR = (24, 30, 48)       # Nền panel điều khiển (Deep Navy Slate)
TEXT_COLOR = (241, 245, 249)     # Chữ màu sáng chính (Slate 100)
MUTED_COLOR = (148, 163, 184)    # Chữ phụ / thông tin phụ (Slate 400)
LINE_COLOR = (39, 45, 69)        # Đường viền ngăn cách tinh tế (Slate 750)
BOARD_BG_COLOR = (10, 15, 26)    # Nền của bảng chơi trượt hình
BORDER_COLOR = (71, 85, 105)     # Viền mặc định của mảnh ghép (Slate 600)

# MÀU SẮC ĐIỂM NHẤN (Phát quang nhẹ dạng Neon Accent trên viền và văn bản)
BLUE = (14, 165, 233)            # Xanh Cyan (Reset / Chỉ số bước / Tiêu đề)
GREEN = (16, 185, 129)           # Xanh Emerald (Active / Âm thanh / Đúng vị trí)
RED = (244, 63, 94)              # Đỏ Rose (Thoát / Sai vị trí)
SLATE = (71, 85, 105)            # Xám Slate (Viền phụ)
GOLD = (245, 158, 11)            # Vàng Amber (Gợi ý / Kỷ lục tốt nhất)
PURPLE = (139, 92, 246)          # Tím Violet (Giải thuật AI)
TEAL = (20, 184, 166)            # Xanh Teal (Cài đặt)

# =====================================================================
# 1. LỚP QUẢN LÝ ÂM THANH (SoundManager)
# Tự tổng hợp âm thanh bằng sóng hình sin số trực tiếp trên RAM (Sound Synthesis)
# tránh lỗi không tìm thấy file tài nguyên và giúp game chạy độc lập hoàn toàn.
# =====================================================================
class SoundManager:
    def __init__(self):
        self.muted = False
        self.slide_sound = None
        self.click_sound = None
        self.win_sound = None
        self._init_sounds()

    def _init_sounds(self):
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=1)
        except Exception:
            pass
        self.slide_sound = self._synthesize_sound(type="slide")
        self.click_sound = self._synthesize_sound(type="click")
        self.win_sound = self._synthesize_sound(type="win")

    def _synthesize_sound(self, type="click"):
        sample_rate = 44100
        if type == "click":
            duration = 0.05
            freq_start, freq_end = 1000, 800
        elif type == "slide":
            duration = 0.12
            freq_start, freq_end = 450, 200
        else: # Hợp âm mừng chiến thắng
            duration = 0.8
            freqs = [523.25, 659.25, 783.99, 1046.5] # Hợp âm Đô trưởng (C5, E5, G5, C6)

        num_samples = int(sample_rate * duration)
        data = array.array('h')

        for i in range(num_samples):
            t = i / sample_rate
            envelope = 1.0 - (t / duration) # Âm lượng giảm dần theo thời gian (decay)
            
            if type == "win":
                value = sum(math.sin(2 * math.pi * f * t) for f in freqs)
                value = int((16384 / len(freqs)) * value * envelope)
            else:
                freq = freq_start + (freq_end - freq_start) * (t / duration)
                value = int(12288 * math.sin(2 * math.pi * freq * t) * envelope)
            data.append(value)

        try:
            return pygame.mixer.Sound(buffer=data)
        except Exception:
            return None

    def play_click(self):
        if not self.muted and self.click_sound: self.click_sound.play()

    def play_slide(self):
        if not self.muted and self.slide_sound: self.slide_sound.play()

    def play_win(self):
        if not self.muted and self.win_sound: self.win_sound.play()

    def toggle_mute(self):
        self.muted = not self.muted
        return self.muted

# =====================================================================
# 2. LỚP HIỆU ỨNG HẠT (Particle)
# Phục vụ hiệu ứng pháo hoa khi người chơi giành chiến thắng.
# =====================================================================
class Particle:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = random.uniform(-4, 4)
        self.vy = random.uniform(-8, -3)
        self.color = random.choice([TEAL, GREEN, BLUE, GOLD, PURPLE, (255, 99, 71)])
        self.radius = random.uniform(3, 6)
        self.gravity = 0.25
        self.life = 1.0
        self.decay = random.uniform(0.015, 0.03)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += self.gravity
        self.vx *= 0.98
        self.life -= self.decay

    def draw(self, screen):
        if self.life > 0:
            r = max(1, int(self.radius * self.life))
            pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), r)

# =====================================================================
# 3. LỚP MÀN CHƠI (Level)
# Lưu trữ thông tin định danh và tài nguyên của mỗi màn chơi.
# =====================================================================
@dataclass(frozen=True)
class Level:
    level_id: str
    name: str
    file_name: str
    description: str

# =====================================================================
# 4. LỚP Ô MẢNH GHÉP (Tile)
# Lưu trữ hình ảnh cắt nhỏ, tọa độ lưới hiện tại, tọa độ lưới đích
# và hỗ trợ hiệu ứng LERP (trượt mượt mà).
# =====================================================================
@dataclass
class Tile:
    image: pygame.Surface
    current_row: int
    current_col: int
    target_row: int
    target_col: int
    draw_x: float = None
    draw_y: float = None

    def is_correct(self):
        """Kiểm tra xem ô hiện tại đã nằm đúng vị trí đích hay chưa."""
        return self.current_row == self.target_row and self.current_col == self.target_col

    def number(self, grid_size):
        """Số thứ tự hiển thị của ô (tính từ 1 đến grid_size^2 - 1)."""
        return self.target_row * grid_size + self.target_col + 1

# Các màn chơi mặc định trong thư mục assets
LEVELS = [
    Level("pho_den_long", "Phố đèn lồng", "level_river_town.png", "Phố cổ ven sông rực rỡ đèn lồng, nhiều chi tiết dễ nhận biết."),
    Level("dao_nhiet_doi", "Đảo nhiệt đới", "level_beach.png", "Biển xanh cát trắng, thuyền nhỏ ven bờ và nắng vàng rực rỡ."),
    Level("thanh_pho_sao", "Thành phố sao", "level_city.png", "Bầu trời đêm hiện đại rực rỡ ánh đèn đường và ngàn sao lấp lánh."),
    Level("vuon_nui", "Vườn núi", "level_mountain.png", "Ruộng bậc thang xanh ngát, mây phủ sương mờ lung linh ánh bình minh.")
]

# =====================================================================
# 5. LỚP QUẢN LÝ BẢNG CHƠI (Board)
# Quản lý lưới ô mảnh ghép, các thuật toán xáo trộn đi ngược (backward shuffling)
# đảm bảo bàn chơi luôn giải được, tính năng gợi ý tối ưu và hoàn tác (Undo).
# =====================================================================
class Board:
    def __init__(self, source_image, grid_size=4):
        self.source_image = source_image
        self.grid_size = grid_size
        self.tiles = []
        self.empty_pos = (grid_size - 1, grid_size - 1)
        self.moves = 0
        self.assisted_moves = 0
        self.history = []
        self.solution_stack = []
        self.won = False
        self.paused = False
        self.started_at = time.time()
        self.elapsed_before_pause = 0
        self.finished_elapsed = None
        self._create_solved_board()

    def _create_solved_board(self):
        """Khởi tạo lưới mảnh ghép ở trạng thái đã hoàn thành (solved)."""
        self.tiles = []
        tile_size = BOARD_SIZE // self.grid_size

        for row in range(self.grid_size):
            row_tiles = []
            for col in range(self.grid_size):
                if row == self.grid_size - 1 and col == self.grid_size - 1:
                    row_tiles.append(None) # Ô trống cuối cùng
                    continue
                image_rect = pygame.Rect(col * tile_size, row * tile_size, tile_size, tile_size)
                tile_image = self.source_image.subsurface(image_rect).copy()
                row_tiles.append(Tile(tile_image, row, col, row, col))
            self.tiles.append(row_tiles)

        self.empty_pos = (self.grid_size - 1, self.grid_size - 1)
        self.moves = 0
        self.assisted_moves = 0
        self.history = []
        self.solution_stack = []
        self.won = False
        self._reset_timer()

    def _reset_timer(self):
        """Đặt lại bộ đếm thời gian chơi game."""
        self.paused = False
        self.started_at = time.time()
        self.elapsed_before_pause = 0
        self.finished_elapsed = None

    def shuffle(self, steps=300):
        """
        Xáo trộn đi lùi (Backward Shuffling): Đi ngẫu nhiên từ trạng thái hoàn chỉnh,
        đảm bảo bàn chơi được tạo ra luôn giải được 100% (tránh lỗi toán học không giải được).
        """
        self._create_solved_board()
        previous_empty = None

        for _ in range(steps):
            movable_positions = self._movable_positions()
            if previous_empty in movable_positions and len(movable_positions) > 1:
                movable_positions.remove(previous_empty)

            chosen_pos = random.choice(movable_positions)
            previous_empty = self.empty_pos
            self._swap_with_empty(chosen_pos, count_move=False)
            self.solution_stack.append(previous_empty) # Lưu các bước đi ngược để làm gợi ý giải tối ưu

        if self.is_completed():
            self.shuffle(steps)
            return

        self.moves = 0
        self.assisted_moves = 0
        self.history = []
        self.won = False
        self._reset_timer()

    def _movable_positions(self):
        """Tìm các vị trí lưới liền kề ô trống để có thể di chuyển."""
        empty_row, empty_col = self.empty_pos
        positions = []
        for r_delta, c_delta in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            r, c = empty_row + r_delta, empty_col + c_delta
            if 0 <= r < self.grid_size and 0 <= c < self.grid_size:
                positions.append((r, c))
        return positions

    def can_move(self, row, col):
        """Kiểm tra xem ô (row, col) có nằm cạnh ô trống hay không."""
        empty_row, empty_col = self.empty_pos
        return abs(row - empty_row) + abs(col - empty_col) == 1

    def move_tile(self, row, col, assisted=False):
        """Thực hiện di chuyển ô ghép, đẩy trạng thái cũ vào lịch sử phục vụ Undo."""
        if self.won or self.paused or not self.can_move(row, col):
            return False

        previous_empty = self.empty_pos
        old_solution_stack = self.solution_stack.copy()
        self._swap_with_empty((row, col), count_move=True)
        self.history.append((previous_empty, old_solution_stack, self.assisted_moves))

        # Cập nhật ngăn xếp gợi ý nước đi tối ưu (nếu đi đúng bước đi lùi thì rút ngăn xếp, ngược lại thì thêm vào)
        if self.solution_stack and (row, col) == self.solution_stack[-1]:
            self.solution_stack.pop()
        else:
            self.solution_stack.append(previous_empty)

        if assisted:
            self.assisted_moves += 1

        if self.is_completed():
            self.won = True
            self.finished_elapsed = self.elapsed_seconds()
        return True

    def move_empty(self, row_delta, col_delta):
        """Di chuyển ô trống theo phím mũi tên điều hướng."""
        empty_row, empty_col = self.empty_pos
        r, c = empty_row + row_delta, empty_col + col_delta
        if 0 <= r < self.grid_size and 0 <= c < self.grid_size:
            return self.move_tile(r, c)
        return False

    def undo(self):
        """Hoàn tác (Undo) nước đi trước đó bằng cách pop từ lịch sử."""
        if self.paused or not self.history:
            return False
        previous_empty, old_solution_stack, old_assisted_moves = self.history.pop()
        self._swap_with_empty(previous_empty, count_move=False)
        self.solution_stack = old_solution_stack
        self.assisted_moves = old_assisted_moves
        self.moves = max(0, self.moves - 1)
        self.won = False
        self.finished_elapsed = None
        return True

    def hint_position(self):
        """Tìm nước đi tối ưu dựa vào solution_stack tích lũy từ xáo trộn đi lùi."""
        if self.solution_stack:
            return self.solution_stack[-1]
        movable = self._movable_positions()
        return movable[0] if movable else None

    def assist_one_step(self):
        """Tự động thực hiện 1 bước đi đúng thay cho người chơi."""
        hint = self.hint_position()
        if hint and self.can_move(*hint):
            return self.move_tile(*hint, assisted=True)
        return False

    def toggle_pause(self):
        """Tạm dừng hoặc tiếp tục trò chơi (để dừng bộ đếm thời gian)."""
        if self.won: return
        if self.paused:
            self.started_at = time.time()
            self.paused = False
        else:
            self.elapsed_before_pause = self.elapsed_seconds()
            self.paused = True

    def _swap_with_empty(self, pos, count_move):
        """Tráo đổi vị trí của một mảnh ghép với ô trống."""
        r, c = pos
        er, ec = self.empty_pos
        tile = self.tiles[r][c]
        self.tiles[er][ec] = tile
        self.tiles[r][c] = None

        if tile is not None:
            tile.current_row = er
            tile.current_col = ec

        self.empty_pos = (r, c)
        if count_move:
            self.moves += 1

    def is_completed(self):
        """Kiểm tra xem toàn bộ bàn chơi đã được xếp đúng hoàn toàn hay chưa."""
        for r in self.tiles:
            for t in r:
                if t is not None and not t.is_correct():
                    return False
        return True

    def correct_count(self):
        """Đếm số ô mảnh ghép đang ở đúng vị trí đích (phục vụ thanh tiến độ)."""
        count = 0
        for r in self.tiles:
            for t in r:
                if t is not None and t.is_correct():
                    count += 1
        return count

    def total_tiles(self):
        """Tổng số ô ghép cần xếp (không tính ô trống)."""
        return self.grid_size * self.grid_size - 1

    def elapsed_seconds(self):
        """Tính toán tổng thời gian đã trôi qua kể từ lúc bắt đầu (giây)."""
        if self.finished_elapsed is not None:
            return int(self.finished_elapsed)
        if self.paused:
            return int(self.elapsed_before_pause)
        return int(self.elapsed_before_pause + time.time() - self.started_at)

# =====================================================================
# 6. LỚP CHÍNH TRÒ CHƠI (PuzzleGame)
# Quản lý khởi tạo màn hình Pygame, vòng lặp game chính, lắng nghe sự kiện,
# dựng giao diện tối Dark Mode đối xứng hiện đại, vẽ nút 3D và các thành phần UI.
# =====================================================================
class PuzzleGame:
    def __init__(self):
        pygame.init()
        pygame.key.set_repeat(180, 90)
        pygame.display.set_caption("Puzzle Game - Đồ án Python")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()

        # Khởi tạo hệ thống font chữ hỗ trợ Unicode tránh lỗi font tiếng Việt
        self.font_title = self._load_font(32, bold=True)
        self.font_heading = self._load_font(21, bold=True)
        self.font_button = self._load_font(15, bold=True)
        self.font_body = self._load_font(15)
        self.font_small = self._load_font(14)
        self.font_tiny = self._load_font(12)

        # Tải cấu hình và dữ liệu điểm số
        self.data = self._load_data()
        settings = self.data.setdefault("settings", {})
        self.current_level_index = min(settings.get("level_index", 0), len(LEVELS) - 1)
        self.show_reference = settings.get("show_reference", True)
        self.show_numbers = settings.get("show_numbers", False)
        self.beginner_mode = settings.get("beginner_mode", True)
        self.high_contrast = settings.get("high_contrast", False)

        self.sound_manager = SoundManager()
        self.sound_manager.muted = settings.get("muted", False)
        self.particles = []
        self.show_settings = False
        self.show_help = False
        self.hint_until = 0
        self.peek_until = 0
        self.hovered_button = None
        self.hovered_cell = None
        self.is_new_record = False

        # Thiết lập toạ độ của Modal Cài đặt đối xứng
        modal_width = 460
        modal_height = 440
        modal_left = (SCREEN_WIDTH - modal_width) // 2
        modal_top = (SCREEN_HEIGHT - modal_height) // 2
        self.settings_buttons = {
            "toggle_sound": pygame.Rect(modal_left + 350, modal_top + 70, 54, 26),
            "toggle_beginner": pygame.Rect(modal_left + 350, modal_top + 120, 54, 26),
            "toggle_numbers": pygame.Rect(modal_left + 350, modal_top + 170, 54, 26),
            "toggle_contrast": pygame.Rect(modal_left + 350, modal_top + 220, 54, 26),
            "toggle_reference": pygame.Rect(modal_left + 350, modal_top + 270, 54, 26),
            "open_help": pygame.Rect(modal_left + 40, modal_top + 320, 380, 36),
            "close": pygame.Rect(modal_left + 160, modal_top + 375, 140, 36),
        }

        # Khởi tạo bố cục các nút bấm trong Panel điều khiển (Đối xứng hoàn hảo - 4 cột)
        # Usable width = 488px (PANEL_WIDTH 536 - margin trái/phải 24px)
        # Nút ở phần chọn màn chơi (3 nút lớn): width = 154px, khoảng cách = 13px
        # Nút ở phần chọn độ khó, Stats, Gameplay (4 nút): width = 113px, khoảng cách = 12px
        btn_y_level = PANEL_TOP + 218 # 260
        self.buttons = {
            "prev_level": pygame.Rect(PANEL_LEFT + 24, btn_y_level, 154, 36),
            "random_level": pygame.Rect(PANEL_LEFT + 191, btn_y_level, 154, 36),
            "next_level": pygame.Rect(PANEL_LEFT + 358, btn_y_level, 154, 36),
        }

        # Các nút kích thước lưới 3x3 -> 6x6
        btn_y_grid = PANEL_TOP + 305 # 347
        for size in (3, 4, 5, 6):
            col_idx = size - 3
            self.buttons[f"grid_{size}"] = pygame.Rect(PANEL_LEFT + 24 + col_idx * 125, btn_y_grid, 113, 36)

        # Các nút gameplay hàng 1
        btn_y_ctrl1 = PANEL_TOP + 478 # 520
        self.buttons["reset"] = pygame.Rect(PANEL_LEFT + 24, btn_y_ctrl1, 113, 38)
        self.buttons["undo"] = pygame.Rect(PANEL_LEFT + 149, btn_y_ctrl1, 113, 38)
        self.buttons["hint"] = pygame.Rect(PANEL_LEFT + 274, btn_y_ctrl1, 113, 38)
        self.buttons["assist"] = pygame.Rect(PANEL_LEFT + 399, btn_y_ctrl1, 113, 38)

        # Các nút gameplay hàng 2
        btn_y_ctrl2 = PANEL_TOP + 530 # 572
        self.buttons["peek"] = pygame.Rect(PANEL_LEFT + 24, btn_y_ctrl2, 113, 38)
        self.buttons["pause"] = pygame.Rect(PANEL_LEFT + 149, btn_y_ctrl2, 113, 38)
        self.buttons["settings"] = pygame.Rect(PANEL_LEFT + 274, btn_y_ctrl2, 113, 38)
        self.buttons["quit"] = pygame.Rect(PANEL_LEFT + 399, btn_y_ctrl2, 113, 38)

        grid_size = settings.get("grid_size", 4)
        self.source_image = self._load_current_level_image()
        self.board = Board(self.source_image, grid_size=grid_size)
        self.board.shuffle(self._shuffle_steps())

    def _load_font(self, size, bold=False):
        """Tải font hệ thống có sẵn trên máy Windows để dựng chữ chuẩn tiếng Việt."""
        for name in ("segoeui", "arial", "tahoma", "dejavusans"):
            path = pygame.font.match_font(name, bold=bold)
            if path: return pygame.font.Font(path, size)
        return pygame.font.SysFont("arial", size, bold=bold)

    def _load_data(self):
        """Đọc file lưu kỷ lục du_lieu_game.json."""
        if not os.path.exists(SAVE_PATH):
            return {"scores": {}, "settings": {}}
        try:
            with open(SAVE_PATH, "r", encoding="utf-8") as file:
                return json.load(file)
        except Exception:
            return {"scores": {}, "settings": {}}

    def _save_data(self):
        """Ghi cấu hình cài đặt hiện tại và kỷ lục điểm số vào du_lieu_game.json."""
        settings = self.data.setdefault("settings", {})
        settings["level_index"] = self.current_level_index
        settings["grid_size"] = self.board.grid_size
        settings["show_reference"] = self.show_reference
        settings["show_numbers"] = self.show_numbers
        settings["beginner_mode"] = self.beginner_mode
        settings["high_contrast"] = self.high_contrast
        settings["muted"] = self.sound_manager.muted
        try:
            with open(SAVE_PATH, "w", encoding="utf-8") as file:
                json.dump(self.data, file, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_current_level_image(self):
        """Tải hình ảnh của màn chơi hiện tại từ thư mục assets."""
        level = self.current_level()
        image_path = os.path.join(ASSETS_DIR, level.file_name)
        if os.path.exists(image_path):
            image = pygame.image.load(image_path).convert()
            return pygame.transform.smoothscale(image, (BOARD_SIZE, BOARD_SIZE))
        return self._create_default_image()

    def _create_default_image(self):
        """Tạo ảnh mặc định dự phòng nếu thiếu file trong assets."""
        image = pygame.Surface((BOARD_SIZE, BOARD_SIZE))
        image.fill((30, 41, 59))
        pygame.draw.circle(image, (14, 165, 233), (260, 260), 120)
        return image.convert()

    def current_level(self):
        return LEVELS[self.current_level_index]

    def run(self):
        """Vòng lặp chính điều phối game (Game Loop) ở 60 FPS."""
        while True:
            self._handle_events()
            self._update_particles()
            self._draw()
            pygame.display.flip()
            self.clock.tick(FPS)

    def _update_particles(self):
        """Cập nhật hiệu ứng pháo hoa khi chiến thắng."""
        for p in self.particles[:]:
            p.update()
            if p.life <= 0: self.particles.remove(p)

        # Phun pháo hoa từ đáy bàn chơi
        if self.board.won and len(self.particles) < 100:
            for _ in range(random.randint(1, 2)):
                px = BOARD_LEFT + random.uniform(20, BOARD_SIZE - 20)
                py = BOARD_TOP + BOARD_SIZE
                p = Particle(px, py)
                p.vy = random.uniform(-12, -6)
                self.particles.append(p)

    def _draw_particles(self):
        """Vẽ các hạt pháo hoa lên màn hình."""
        for p in self.particles:
            p.draw(self.screen)

    def _handle_events(self):
        """Lắng nghe các sự kiện đầu vào từ người chơi."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._quit()
            elif event.type == pygame.KEYDOWN:
                self._handle_key(event.key)
            elif event.type == pygame.MOUSEMOTION:
                self._update_hover(event.pos)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_click(event.pos)

    def _handle_key(self, key):
        """Xử lý sự kiện nhấn phím tắt."""
        if key == pygame.K_ESCAPE:
            self.sound_manager.play_click()
            if self.show_help: self.show_help = False
            elif self.show_settings: self.show_settings = False
            else: self._quit()
        elif key == pygame.K_F1:
            self.sound_manager.play_click()
            self.show_help = not self.show_help
        elif key == pygame.K_F12:
            try:
                pygame.image.save(self.screen, os.path.join(BASE_DIR, "ui_preview.png"))
                self.sound_manager.play_click()
            except Exception:
                pass
        elif key == pygame.K_r:
            self.sound_manager.play_click()
            self._reset_board()
        elif key == pygame.K_u:
            self.sound_manager.play_click()
            if self.board.undo(): self.sound_manager.play_slide()
        elif key == pygame.K_h:
            self.sound_manager.play_click()
            self.hint_until = time.time() + 2.0
        elif key == pygame.K_g:
            self.sound_manager.play_click()
            self._trigger_assist()
        elif key == pygame.K_p:
            self.sound_manager.play_click()
            self.board.toggle_pause()
        elif key == pygame.K_SPACE:
            self.peek_until = time.time() + 999999
        
        # Di chuyển ô trống bằng phím tắt
        moved = False
        if key in (pygame.K_UP, pygame.K_w):
            moved = self.board.move_empty(1, 0)
        elif key in (pygame.K_DOWN, pygame.K_s):
            moved = self.board.move_empty(-1, 0)
        elif key in (pygame.K_LEFT, pygame.K_a):
            moved = self.board.move_empty(0, 1)
        elif key in (pygame.K_RIGHT, pygame.K_d):
            moved = self.board.move_empty(0, -1)

        if moved:
            self.sound_manager.play_slide()
            self._check_win_and_save()

    def _update_hover(self, pos):
        """Cập nhật nút hoặc ô lưới mà chuột đang chỉ vào để hiển thị trạng thái Hover."""
        self.hovered_button = None
        self.hovered_cell = None

        if self.show_settings:
            for key, rect in self.settings_buttons.items():
                if rect.collidepoint(pos):
                    self.hovered_button = key
            return

        for key, rect in self.buttons.items():
            if rect.collidepoint(pos):
                self.hovered_button = key
                return

        board_rect = pygame.Rect(BOARD_LEFT, BOARD_TOP, BOARD_SIZE, BOARD_SIZE)
        if board_rect.collidepoint(pos) and not self.board.won and not self.board.paused:
            tile_size = BOARD_SIZE / self.board.grid_size
            col = int((pos[0] - BOARD_LEFT) / tile_size)
            row = int((pos[1] - BOARD_TOP) / tile_size)
            if 0 <= row < self.board.grid_size and 0 <= col < self.board.grid_size:
                self.hovered_cell = (row, col)

    def _handle_click(self, pos):
        """Xử lý nhấp chuột trái."""
        self.sound_manager.play_click()
        
        if self.show_help:
            self.show_help = False
            return

        if self.show_settings:
            self._handle_settings_click(pos)
            return

        # Click di chuyển mảnh trên bảng chơi
        if not self.board.won and not self.board.paused:
            board_rect = pygame.Rect(BOARD_LEFT, BOARD_TOP, BOARD_SIZE, BOARD_SIZE)
            if board_rect.collidepoint(pos):
                tile_size = BOARD_SIZE / self.board.grid_size
                col = int((pos[0] - BOARD_LEFT) / tile_size)
                row = int((pos[1] - BOARD_TOP) / tile_size)
                if 0 <= row < self.board.grid_size and 0 <= col < self.board.grid_size:
                    if self.board.move_tile(row, col):
                        self.sound_manager.play_slide()
                        self._check_win_and_save()
                return

        # Click nút bấm trên Panel
        for key, rect in self.buttons.items():
            if rect.collidepoint(pos):
                self._handle_button_click(key)
                break

    def _handle_button_click(self, key):
        """Xử lý kích hoạt khi click nút trên Panel điều khiển."""
        if key == "prev_level": self._change_level(-1)
        elif key == "next_level": self._change_level(1)
        elif key == "random_level": self._change_level(random.randint(1, len(LEVELS) - 1))
        elif key.startswith("grid_"):
            size = int(key.split("_")[1])
            self._change_grid_size(size)
        elif key == "reset": self._reset_board()
        elif key == "undo":
            if self.board.undo(): self.sound_manager.play_slide()
        elif key == "hint": self.hint_until = time.time() + 2.0
        elif key == "assist": self._trigger_assist()
        elif key == "peek": self.peek_until = time.time() + 2.0
        elif key == "pause": self.board.toggle_pause()
        elif key == "settings":
            self.show_settings = True
            if not self.board.paused: self.board.toggle_pause()
        elif key == "quit": self._quit()

    def _handle_settings_click(self, pos):
        """Xử lý click chuột trong bảng Cài đặt Overlay."""
        for key, rect in self.settings_buttons.items():
            if rect.collidepoint(pos):
                if key == "close":
                    self.show_settings = False
                    if self.board.paused: self.board.toggle_pause()
                elif key == "open_help":
                    self.show_help = True
                    self.show_settings = False
                elif key == "toggle_sound":
                    self.sound_manager.toggle_mute()
                    self._save_data()
                elif key == "toggle_beginner":
                    self.beginner_mode = not self.beginner_mode
                    self._save_data()
                elif key == "toggle_numbers":
                    self.show_numbers = not self.show_numbers
                    self._save_data()
                elif key == "toggle_contrast":
                    self.high_contrast = not self.high_contrast
                    self._save_data()
                elif key == "toggle_reference":
                    self.show_reference = not self.show_reference
                    self._save_data()
                break

    def _change_level(self, delta):
        """Đổi sang màn chơi khác."""
        self.current_level_index = (self.current_level_index + delta) % len(LEVELS)
        self.source_image = self._load_current_level_image()
        self.board.source_image = self.source_image
        self._reset_board()

    def _change_grid_size(self, size):
        """Thay đổi kích thước lưới ô ghép."""
        self.board = Board(self.source_image, grid_size=size)
        self._reset_board()

    def _reset_board(self):
        """Chơi lại màn chơi bằng cách xáo trộn mới."""
        self.board.shuffle(self._shuffle_steps())
        self.particles = []
        self.hint_until = 0
        self.peek_until = 0
        self.is_new_record = False
        self._save_data()

    def _shuffle_steps(self):
        """Số bước xáo trộn đi ngược tương thích với kích thước lưới."""
        return {3: 40, 4: 80, 5: 120, 6: 180}.get(self.board.grid_size, 80)

    def _trigger_assist(self):
        """Thực hiện một nước đi đúng do AI giải hộ."""
        if self.board.assist_one_step():
            self.sound_manager.play_slide()
            self._check_win_and_save()

    def _save_score(self):
        """Lưu kỷ lục thành tích người chơi theo thời gian giải ngắn nhất."""
        current = {
            "moves": self.board.moves,
            "time": self.board.elapsed_seconds(),
            "assisted": self.board.assisted_moves,
        }
        scores = self.data.setdefault("scores", {})
        best = scores.get(self._score_key())
        
        self.is_new_record = False
        if best is None or current["time"] < best.get("time", 999999):
            scores[self._score_key()] = current
            self._save_data()
            self.is_new_record = True

    def _check_win_and_save(self):
        """Kiểm tra chiến thắng để kích hoạt âm thanh, pháo hoa và lưu trữ kỷ lục."""
        if self.board.won:
            self.sound_manager.play_win()
            self._save_score()

    def _draw(self):
        """Hàm dựng hình vẽ toàn bộ màn hình chính."""
        self.screen.fill(BG_COLOR)
        
        # Vẽ Header chương trình phong cách logo hiện đại
        title_surf1 = self.font_title.render("PUZZLE ", True, TEXT_COLOR)
        title_surf2 = self.font_title.render("GAME", True, BLUE)
        self.screen.blit(title_surf1, (BOARD_LEFT, PANEL_TOP))
        self.screen.blit(title_surf2, (BOARD_LEFT + title_surf1.get_width(), PANEL_TOP))
        
        # Đèn chấm trạng thái live màu xanh Emerald
        pygame.draw.circle(self.screen, GREEN, (BOARD_LEFT + title_surf1.get_width() + title_surf2.get_width() + 12, PANEL_TOP + 20), 4)
        
        self._panel_text("Đồ án lập trình ứng dụng Python", BOARD_LEFT, PANEL_TOP + 46, self.font_body, MUTED_COLOR)

        self._draw_board()
        self._draw_panel()
        self._draw_particles()

        # Hiển thị các bảng hội thoại đè (Overlay)
        if self.board.paused and not self.show_settings:
            self._draw_overlay_dialog("Tạm dừng", f"Bấm nút 'Tiếp tục' hoặc phím 'P' để chơi tiếp")
        elif self.board.won:
            rec_text = " - KỶ LỤC MỚI!" if self.is_new_record else ""
            self._draw_overlay_dialog("Chiến thắng!", f"Số bước: {self.board.moves} | Thời gian: {self._format_time(self.board.elapsed_seconds())}{rec_text}")

        if self.show_settings:
            self._draw_settings_overlay()
        elif self.show_help:
            self._draw_help_overlay()

    def _draw_board(self):
        """Vẽ bảng lưới chơi game chính (bên trái)."""
        board_rect = pygame.Rect(BOARD_LEFT - 4, BOARD_TOP - 4, BOARD_SIZE + 8, BOARD_SIZE + 8)
        pygame.draw.rect(self.screen, LINE_COLOR, board_rect, width=2, border_radius=12)
        pygame.draw.rect(self.screen, BOARD_BG_COLOR, (BOARD_LEFT, BOARD_TOP, BOARD_SIZE, BOARD_SIZE), border_radius=10)

        tile_size = BOARD_SIZE // self.board.grid_size
        peek_active = time.time() < self.peek_until or pygame.key.get_pressed()[pygame.K_SPACE]

        for r in range(self.board.grid_size):
            for c in range(self.board.grid_size):
                tile = self.board.tiles[r][c]
                if tile is None: continue

                target_x = BOARD_LEFT + c * tile_size
                target_y = BOARD_TOP + r * tile_size

                # Thuật toán LERP trượt mảnh ghép mượt mà
                if tile.draw_x is None:
                    tile.draw_x, tile.draw_y = target_x, target_y
                else:
                    tile.draw_x += (target_x - tile.draw_x) * 0.22
                    tile.draw_y += (target_y - tile.draw_y) * 0.22

                x_val, y_val = (target_x, target_y) if peek_active else (tile.draw_x, tile.draw_y)
                self.screen.blit(tile.image, (x_val, y_val))

                border_color = BORDER_COLOR
                if self.beginner_mode and not peek_active:
                    border_color = GREEN if tile.is_correct() else RED
                pygame.draw.rect(self.screen, border_color, (x_val, y_val, tile_size, tile_size), width=1)

                if self.show_numbers and not peek_active:
                    circle_surface = pygame.Surface((30, 30), pygame.SRCALPHA)
                    pygame.draw.circle(circle_surface, (15, 23, 42, 160), (15, 15), 15)
                    self.screen.blit(circle_surface, (x_val + 6, y_val + 6))
                    num_text = self.font_tiny.render(str(tile.number(self.board.grid_size)), True, (255, 255, 255))
                    self.screen.blit(num_text, num_text.get_rect(center=(x_val + 21, y_val + 21)))

        if time.time() < self.hint_until and not self.board.won and not self.board.paused:
            hint_pos = self.board.hint_position()
            if hint_pos:
                hr, hc = hint_pos
                pygame.draw.rect(self.screen, GOLD, (BOARD_LEFT + hc * tile_size, BOARD_TOP + hr * tile_size, tile_size, tile_size), width=4)

    def _draw_overlay_dialog(self, title, detail):
        """Vẽ hộp thoại hội thoại đè lên bảng chơi."""
        overlay = pygame.Surface((BOARD_SIZE, BOARD_SIZE), pygame.SRCALPHA)
        overlay.fill((15, 23, 42, 180))
        self.screen.blit(overlay, (BOARD_LEFT, BOARD_TOP))

        box = pygame.Rect(BOARD_LEFT + 70, BOARD_TOP + 178, BOARD_SIZE - 140, 142)
        pygame.draw.rect(self.screen, PANEL_COLOR, box, border_radius=14)
        
        border_clr = GREEN if title == "Chiến thắng!" else BLUE
        pygame.draw.rect(self.screen, border_clr, box, width=2, border_radius=14)

        title_color = GREEN if title == "Chiến thắng!" else TEXT_COLOR
        title_surface = self.font_heading.render(title, True, title_color)
        detail_surface = self.font_small.render(detail, True, MUTED_COLOR)
        
        self.screen.blit(title_surface, title_surface.get_rect(center=(box.centerx, box.y + 44)))
        self.screen.blit(detail_surface, detail_surface.get_rect(center=(box.centerx, box.y + 88)))

        if title == "Chiến thắng!" and self.is_new_record:
            rec_surf = self.font_button.render("★ KỶ LỤC MỚI ĐÃ ĐƯỢC THIẾT LẬP ★", True, GOLD)
            self.screen.blit(rec_surf, rec_surf.get_rect(center=(box.centerx, box.y + 116)))

    def _draw_panel(self):
        """Vẽ khung Panel bên phải."""
        panel_rect = pygame.Rect(PANEL_LEFT, PANEL_TOP, PANEL_WIDTH, PANEL_HEIGHT)
        pygame.draw.rect(self.screen, PANEL_COLOR, panel_rect, border_radius=16)
        pygame.draw.rect(self.screen, LINE_COLOR, panel_rect, width=1, border_radius=16)

        footer_text = "Nhấn F1 để xem phím tắt  |  F12 để chụp ảnh màn hình"
        foot_surface = self.font_tiny.render(footer_text, True, MUTED_COLOR)
        self.screen.blit(foot_surface, foot_surface.get_rect(center=(PANEL_LEFT + PANEL_WIDTH // 2, PANEL_TOP + PANEL_HEIGHT - 20)))

        self._draw_level_info()
        self._draw_difficulty()
        self._draw_stats()
        self._draw_progress_bar()
        self._draw_controls()

    def _draw_section_heading(self, label, x, y):
        """Vẽ tiêu đề phân vùng."""
        self._panel_text(label, x, y, self.font_heading, BLUE)

    def _draw_level_info(self):
        """Vẽ thông tin màn chơi hiện tại."""
        self._draw_section_heading("MÀN CHƠI", PANEL_LEFT + 24, PANEL_TOP + 18)
        preview_rect = pygame.Rect(PANEL_LEFT + 24, PANEL_TOP + 50, 154, 154)

        if self.show_reference:
            preview = pygame.transform.smoothscale(self.source_image, (154, 154))
            self.screen.blit(preview, preview_rect.topleft)
        else:
            pygame.draw.rect(self.screen, BG_COLOR, preview_rect, border_radius=8)
            hidden = self.font_body.render("Đang ẩn ảnh", True, MUTED_COLOR)
            self.screen.blit(hidden, hidden.get_rect(center=preview_rect.center))
        pygame.draw.rect(self.screen, LINE_COLOR, preview_rect, width=1, border_radius=8)

        info_x = PANEL_LEFT + 194
        level = self.current_level()
        self._panel_text(f"{self.current_level_index + 1}. {level.name}", info_x, PANEL_TOP + 50, self.font_heading, TEXT_COLOR)
        self._draw_wrapped_text(level.description, info_x, PANEL_TOP + 82, 318, self.font_small, MUTED_COLOR, line_height=18)
        
        self._panel_text("Kỷ lục màn này (Thời gian):", info_x, PANEL_TOP + 144, self.font_tiny, MUTED_COLOR)
        self._panel_text(self._level_best_text(), info_x, PANEL_TOP + 162, self.font_small, GREEN)

        self._draw_button("prev_level", "Trở về", SLATE)
        self._draw_button("random_level", "Ngẫu nhiên", TEAL)
        self._draw_button("next_level", "Kế tiếp", SLATE)

    def _draw_difficulty(self):
        """Vẽ nhóm nút chọn kích thước lưới."""
        self._draw_section_heading("ĐỘ KHÓ", PANEL_LEFT + 24, PANEL_TOP + 276)
        for size in (3, 4, 5, 6):
            self._draw_button(f"grid_{size}", f"{size}x{size}", SLATE, active=self.board.grid_size == size)

    def _draw_stats(self):
        """Vẽ thẻ chỉ số với vạch màu bên trái mượt mà."""
        y = PANEL_TOP + 360
        self._draw_stat_card(PANEL_LEFT + 24, y, "Bước đi", str(self.board.moves), BLUE)
        self._draw_stat_card(PANEL_LEFT + 149, y, "Thời gian", self._format_time(self.board.elapsed_seconds()), GREEN)
        self._draw_stat_card(PANEL_LEFT + 274, y, "Trợ giúp", str(self.board.assisted_moves), PURPLE)
        self._draw_stat_card(PANEL_LEFT + 399, y, "Kỷ lục", self._best_score_text(), GOLD)

    def _draw_progress_bar(self):
        """Vẽ thanh tiến độ xếp hình mỏng và tinh tế."""
        y = PANEL_TOP + 428
        correct = self.board.correct_count()
        total = self.board.total_tiles()
        percent = int((correct / total) * 100) if total > 0 else 0

        prog_text = f"Tiến độ hoàn thành: {percent}% ({correct}/{total} ô đúng)"
        self._panel_text(prog_text, PANEL_LEFT + 24, y, self.font_tiny, MUTED_COLOR)

        # Thanh chạy mảnh 6px nền Slate sâu
        bar_rect = pygame.Rect(PANEL_LEFT + 24, y + 18, 488, 6)
        pygame.draw.rect(self.screen, (15, 23, 42), bar_rect, border_radius=3)
        pygame.draw.rect(self.screen, LINE_COLOR, bar_rect, width=1, border_radius=3)
        
        if percent > 0:
            fill_rect = pygame.Rect(PANEL_LEFT + 24, y + 18, int(488 * (percent / 100)), 6)
            pygame.draw.rect(self.screen, GREEN, fill_rect, border_radius=3)

    def _draw_controls(self):
        """Vẽ hai hàng nút bấm điều khiển Gameplay ở đáy panel."""
        self._draw_button("reset", "Chơi lại", BLUE)
        self._draw_button("undo", "Hoàn tác", SLATE, disabled=not self.board.history)
        self._draw_button("hint", "Gợi ý", GOLD)
        self._draw_button("assist", "Giải 1 bước", PURPLE)
        
        self._draw_button("peek", "Xem ảnh", SLATE)
        pause_label = "Tiếp tục" if self.board.paused else "Tạm dừng"
        self._draw_button("pause", pause_label, GREEN if self.board.paused else SLATE)
        self._draw_button("settings", "Cài đặt", TEAL)
        self._draw_button("quit", "Thoát", RED)

    def _draw_help_overlay(self):
        """Hiển thị Modal hướng dẫn phím tắt chơi game."""
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((15, 23, 42, 192))
        self.screen.blit(overlay, (0, 0))

        box = pygame.Rect(230, 120, 700, 480)
        pygame.draw.rect(self.screen, PANEL_COLOR, box, border_radius=16)
        pygame.draw.rect(self.screen, LINE_COLOR, box, width=2, border_radius=16)

        self._panel_text("HƯỚNG DẪN CHƠI GAME & PHÍM TẮT", box.x + 32, box.y + 26, self.font_heading, BLUE)
        lines = [
            "• Click chuột trái vào mảnh ghép nằm cạnh ô trống để trượt ô.",
            "• Nhấn phím Mũi tên hoặc W A S D để trượt ô trống nhanh.",
            "• Phím R: Chơi lại bằng cách xáo trộn bàn chơi mới.",
            "• Phím U: Hoàn tác lại nước đi trước đó (Undo).",
            "• Phím H: Xem gợi ý ô nên di chuyển (Viền vàng hổ phách).",
            "• Phím G: AI tự động thực hiện giùm một bước đi đúng.",
            "• Nhấn giữ Space: Xem nhanh ảnh gốc. Phím P: Tạm dừng game.",
            "• Phím F1: Bật/tắt bảng hướng dẫn phím tắt này.",
            "• Phím F12: Chụp lại ảnh màn hình game lưu vào ui_preview.png."
        ]
        y = box.y + 78
        for line in lines:
            text = self.font_body.render(line, True, TEXT_COLOR)
            self.screen.blit(text, (box.x + 32, y))
            y += 38

        close_hint = "Bấm phím Esc hoặc click bất kỳ bên ngoài bảng để đóng"
        close_surf = self.font_small.render(close_hint, True, BLUE)
        self.screen.blit(close_surf, (box.x + 32, box.bottom - 42))

    def _draw_settings_overlay(self):
        """Hiển thị Modal thiết lập cài đặt với các nút gạt Capsule iOS-style cực đẹp."""
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((15, 23, 42, 192))
        self.screen.blit(overlay, (0, 0))

        modal_width = 460
        modal_height = 440
        modal_left = (SCREEN_WIDTH - modal_width) // 2
        modal_top = (SCREEN_HEIGHT - modal_height) // 2
        box = pygame.Rect(modal_left, modal_top, modal_width, modal_height)
        
        pygame.draw.rect(self.screen, PANEL_COLOR, box, border_radius=16)
        pygame.draw.rect(self.screen, LINE_COLOR, box, width=2, border_radius=16)

        self._panel_text("CÀI ĐẶT TRÒ CHƠI", modal_left + 40, modal_top + 24, self.font_heading, BLUE)

        settings_options = [
            ("Âm thanh trò chơi", not self.sound_manager.muted, "toggle_sound"),
            ("Viền đỏ/xanh hỗ trợ", self.beginner_mode, "toggle_beginner"),
            ("Hiển thị số thứ tự ô", self.show_numbers, "toggle_numbers"),
            ("Tăng tương phản chữ", self.high_contrast, "toggle_contrast"),
            ("Hiển thị ảnh xem trước", self.show_reference, "toggle_reference"),
        ]

        y = modal_top + 70
        for label, is_on, key in settings_options:
            self._panel_text(label, modal_left + 40, y + 3, self.font_body, TEXT_COLOR)
            self._draw_switch(self.settings_buttons[key], is_on)
            y += 50

        self._draw_button("open_help", "Xem hướng dẫn phím tắt chi tiết", SLATE)
        self._draw_button("close", "Đóng cài đặt", BLUE)

    def _draw_button(self, key, label, color, active=False, disabled=False):
        """Vẽ nút bấm 3D phong cách hiện đại với viền phát sáng động và bevel highlight."""
        rect = self.buttons[key] if key in self.buttons else self.settings_buttons[key]
        
        # Cấu hình màu nền (fill) và viền (border) cho các trạng thái nút bấm
        if disabled:
            fill = (30, 41, 59) # Slate 800
            border_clr = (51, 65, 85) # Slate 700
        elif active:
            fill = (79, 70, 229) # Indigo 600
            border_clr = (129, 140, 248) # Indigo 400
        else:
            fill = (39, 45, 69) # Slate 750 (Nền tối đồng bộ loại bỏ khối màu sặc sỡ)
            # Tạo đường viền phản quang Neon đặc trưng cho từng loại nút bấm
            border_clr = (71, 85, 105)
            if key == "reset": border_clr = BLUE
            elif key == "hint": border_clr = GOLD
            elif key == "assist": border_clr = PURPLE
            elif key == "settings": border_clr = TEAL
            elif key == "quit": border_clr = RED
            elif key == "random_level": border_clr = TEAL
            elif key == "pause":
                border_clr = GREEN if self.board.paused else border_clr

        # Hiển thị khi di chuột qua (Hover)
        if self.hovered_button == key and not disabled:
            if not active:
                fill = (49, 56, 89) # Làm sáng nền
                # Làm sáng viền phát quang
                if key == "reset": border_clr = (56, 189, 248)
                elif key == "hint": border_clr = (251, 191, 36)
                elif key == "assist": border_clr = (167, 139, 250)
                elif key == "settings": border_clr = (45, 212, 191)
                elif key == "quit": border_clr = (251, 113, 133)
                elif key == "random_level": border_clr = (45, 212, 191)
                else: border_clr = (129, 140, 248)
            else:
                fill = (67, 56, 202) # Hover nút active

        # 1. Vẽ đổ bóng 3D lệch dưới 3px
        if not disabled:
            pygame.draw.rect(self.screen, (10, 15, 26), (rect.x, rect.y + 3, rect.width, rect.height), border_radius=10)

        # 2. Vẽ nền chính của nút
        pygame.draw.rect(self.screen, fill, rect, border_radius=10)
        
        # 3. Vẽ viền phản quang mảnh
        pygame.draw.rect(self.screen, border_clr, rect, width=1, border_radius=10)

        # 4. Vẽ đường Bevel sáng mảnh ở mép trên nút tạo chiều sâu ánh sáng (chỉ nút không bị tắt và không active)
        if not disabled and not active:
            highlight_color = (79, 91, 133) if self.hovered_button == key else (60, 70, 107)
            pygame.draw.line(self.screen, highlight_color, (rect.x + 8, rect.y + 1), (rect.right - 8, rect.y + 1), width=1)

        # 5. Vẽ nhãn văn bản và biểu tượng
        text_color = (255, 255, 255) if not disabled else MUTED_COLOR
        if key == "settings":
            icon_rect = pygame.Rect(rect.x + 14, rect.centery - 8, 16, 16)
            self._draw_gear_icon(self.screen, icon_rect, text_color, fill)
            text_surf = self.font_button.render("Cài đặt", True, text_color)
            self.screen.blit(text_surf, (rect.x + 38, rect.centery - text_surf.get_height() // 2))
            return

        text = self._render_fit(label, self.font_button, text_color, rect.width - 12)
        self.screen.blit(text, text.get_rect(center=rect.center))

    def _draw_switch(self, rect, is_on):
        """Vẽ nút gạt trượt Switch kiểu iOS."""
        bg_color = GREEN if is_on else SLATE
        pygame.draw.rect(self.screen, bg_color, rect, border_radius=rect.height // 2)
        pygame.draw.rect(self.screen, LINE_COLOR, rect, width=1, border_radius=rect.height // 2)
        
        circle_radius = (rect.height - 6) // 2
        circle_y = rect.centery
        if is_on:
            circle_x = rect.right - 3 - circle_radius
        else:
            circle_x = rect.left + 3 + circle_radius
        pygame.draw.circle(self.screen, (255, 255, 255), (circle_x, circle_y), circle_radius)

    def _draw_stat_card(self, x, y, label, value, accent_color):
        """Vẽ thẻ hiển thị chỉ số (Stat Widget Card) có vạch màu đứng ở mép trái."""
        rect = pygame.Rect(x, y, 113, 54)
        
        # Nền Slate 950 sâu làm nổi bật số liệu
        pygame.draw.rect(self.screen, (15, 23, 42), rect, border_radius=10)
        pygame.draw.rect(self.screen, LINE_COLOR, rect, width=1, border_radius=10)
        
        # Vạch kẻ dọc 3px thanh lịch bên trái
        pygame.draw.line(self.screen, accent_color, (x + 3, y + 8), (x + 3, y + 46), width=3)
        
        label_surface = self.font_tiny.render(label, True, MUTED_COLOR)
        value_surface = self.font_heading.render(value, True, TEXT_COLOR) if label == "Thời gian" else self.font_body.render(value, True, TEXT_COLOR)
        
        self.screen.blit(label_surface, (x + 12, y + 6))
        self.screen.blit(value_surface, (x + 12, y + 24))

    def _draw_gear_icon(self, surface, rect, color, bg_color):
        """Vẽ bánh răng cài đặt bằng đa giác vector động theo tỉ lệ."""
        center_x, center_y = rect.center
        W = rect.width
        R_base = W * 0.28
        R_tip = W * 0.44
        delta_base = math.pi / 18
        delta_tip = math.pi / 24
        
        points = []
        num_teeth = 8
        for i in range(num_teeth):
            angle = i * (2 * math.pi / num_teeth)
            a1 = angle - delta_base
            points.append((center_x + R_base * math.cos(a1), center_y + R_base * math.sin(a1)))
            a2 = angle - delta_tip
            points.append((center_x + R_tip * math.cos(a2), center_y + R_tip * math.sin(a2)))
            a3 = angle + delta_tip
            points.append((center_x + R_tip * math.cos(a3), center_y + R_tip * math.sin(a3)))
            a4 = angle + delta_base
            points.append((center_x + R_base * math.cos(a4), center_y + R_base * math.sin(a4)))
            
        pygame.draw.polygon(surface, color, points)
        pygame.draw.circle(surface, bg_color, (center_x, center_y), int(W * 0.18))

    def _render_fit(self, text, font, color, max_width):
        """Tự động co kích thước font chữ nhỏ lại nếu nhãn nút bấm quá dài so với chiều rộng nút."""
        surface = font.render(text, True, color)
        if surface.get_width() <= max_width: return surface
        for size in range(14, 10, -1):
            small_font = self._load_font(size, bold=True)
            surface = small_font.render(text, True, color)
            if surface.get_width() <= max_width: return surface
        return surface

    def _panel_text(self, text, x, y, font=None, color=TEXT_COLOR):
        surface = (font or self.font_body).render(text, True, color)
        self.screen.blit(surface, (x, y))

    def _draw_wrapped_text(self, text, x, y, max_width, font, color, line_height=20):
        """Tự động xuống dòng cho các đoạn văn bản mô tả dài."""
        words = text.split()
        line = ""
        for word in words:
            candidate = f"{line} {word}".strip()
            if font.render(candidate, True, color).get_width() <= max_width:
                line = candidate
            else:
                self._panel_text(line, x, y, font, color)
                y += line_height
                line = word
        if line: self._panel_text(line, x, y, font, color)

    def _score_key(self):
        return f"{self.current_level().level_id}:{self.board.grid_size}x{self.board.grid_size}"

    def _best_score(self):
        return self.data.get("scores", {}).get(self._score_key())

    def _best_score_text(self):
        best = self._best_score()
        if not best: return "--"
        return self._format_time(best.get('time', 0))

    def _level_best_text(self):
        """Đọc và định dạng kỷ lục thời gian của tất cả các chế độ lưới của màn hiện tại."""
        best_entries = []
        scores = self.data.get("scores", {})
        for size in (3, 4, 5, 6):
            key = f"{self.current_level().level_id}:{size}x{size}"
            if key in scores:
                best_entries.append(f"{size}x{size}: {self._format_time(scores[key].get('time', 0))}")
        return "  |  ".join(best_entries) if best_entries else "Chưa có kỷ lục nào được lập"

    def _format_time(self, seconds):
        """Định dạng số giây thành chuỗi thời gian Phút:Giây (MM:SS)."""
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def _lighten(self, color, amount):
        return tuple(min(255, channel + amount) for channel in color)

    def _darken(self, color, amount):
        return tuple(max(0, channel - amount) for channel in color)

    def _quit(self):
        self._save_data()
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    PuzzleGame().run()
