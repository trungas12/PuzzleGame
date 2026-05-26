import array
import json
import math
import os
import random
import sys
import time
from dataclasses import dataclass

import pygame


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
SAVE_PATH = os.path.join(BASE_DIR, "du_lieu_game.json")

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

BG_COLOR = (246, 248, 252)
PANEL_COLOR = (255, 255, 255)
TEXT_COLOR = (30, 41, 59)
MUTED_COLOR = (100, 116, 139)
LINE_COLOR = (203, 213, 225)
BOARD_BG_COLOR = (226, 232, 240)
BORDER_COLOR = (51, 65, 85)
BLUE = (37, 99, 235)
BLUE_DARK = (29, 78, 216)
GREEN = (22, 163, 74)
ORANGE = (234, 88, 12)
RED = (220, 38, 38)
SLATE = (71, 85, 105)
GOLD = (245, 158, 11)
PURPLE = (124, 58, 237)
TEAL = (13, 148, 136)


class SoundManager:
    def __init__(self):
        self.muted = False
        self.slide_sound = None
        self.click_sound = None
        self.win_sound = None
        self._init_sounds()

    def _init_sounds(self):
        try:
            # Check if mixer is already initialized
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
        else: # win
            duration = 0.8
            # Major chord: C5 (523.25), E5 (659.25), G5 (783.99), C6 (1046.5)
            freqs = [523.25, 659.25, 783.99, 1046.5]

        num_samples = int(sample_rate * duration)
        data = array.array('h')

        for i in range(num_samples):
            t = i / sample_rate
            envelope = 1.0 - (t / duration)
            
            if type == "win":
                value = 0
                for f in freqs:
                    value += math.sin(2 * math.pi * f * t)
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
        if not self.muted and self.click_sound:
            self.click_sound.play()

    def play_slide(self):
        if not self.muted and self.slide_sound:
            self.slide_sound.play()

    def play_win(self):
        if not self.muted and self.win_sound:
            self.win_sound.play()

    def toggle_mute(self):
        self.muted = not self.muted
        return self.muted


class Particle:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = random.uniform(-5, 5)
        self.vy = random.uniform(-10, -3)
        self.color = random.choice([
            (255, 99, 71),   # Tomato
            (50, 205, 50),   # Lime Green
            (30, 144, 255),  # Dodger Blue
            (245, 158, 11),  # Gold
            (124, 58, 237),  # Purple
            (234, 88, 12)    # Orange
        ])
        self.radius = random.uniform(3, 7)
        self.gravity = 0.3
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


@dataclass(frozen=True)
class Level:
    level_id: str
    name: str
    file_name: str
    description: str


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
        return self.current_row == self.target_row and self.current_col == self.target_col

    def number(self, grid_size):
        return self.target_row * grid_size + self.target_col + 1


LEVELS = [
    Level(
        "pho_den_long",
        "Phố đèn lồng",
        "level_river_town.png",
        "Phố ven sông rực rỡ, nhiều chi tiết dễ nhận biết.",
    ),
    Level(
        "dao_nhiet_doi",
        "Đảo nhiệt đới",
        "level_beach.png",
        "Biển xanh, thuyền nhỏ, san hô và nắng vàng.",
    ),
    Level(
        "thanh_pho_sao",
        "Thành phố sao",
        "level_city.png",
        "Đêm hiện đại, ánh đèn, phố đi bộ và bầu trời sao.",
    ),
    Level(
        "vuon_nui",
        "Vườn núi",
        "level_mountain.png",
        "Ruộng bậc thang, hoa, thác nước và ánh sáng buổi sớm.",
    ),
]


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
        self.tiles = []
        tile_size = BOARD_SIZE // self.grid_size

        for row in range(self.grid_size):
            row_tiles = []
            for col in range(self.grid_size):
                if row == self.grid_size - 1 and col == self.grid_size - 1:
                    row_tiles.append(None)
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
        self.paused = False
        self.started_at = time.time()
        self.elapsed_before_pause = 0
        self.finished_elapsed = None

    def shuffle(self, steps=300):
        self._create_solved_board()
        previous_empty = None

        for _ in range(steps):
            movable_positions = self._movable_positions()
            if previous_empty in movable_positions and len(movable_positions) > 1:
                movable_positions.remove(previous_empty)

            chosen_pos = random.choice(movable_positions)
            previous_empty = self.empty_pos
            self._swap_with_empty(chosen_pos, count_move=False)
            self.solution_stack.append(previous_empty)

        if self.is_completed():
            self.shuffle(steps)
            return

        self.moves = 0
        self.assisted_moves = 0
        self.history = []
        self.won = False
        self._reset_timer()

    def _movable_positions(self):
        empty_row, empty_col = self.empty_pos
        positions = []
        for row_delta, col_delta in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            row = empty_row + row_delta
            col = empty_col + col_delta
            if 0 <= row < self.grid_size and 0 <= col < self.grid_size:
                positions.append((row, col))
        return positions

    def can_move(self, row, col):
        empty_row, empty_col = self.empty_pos
        return abs(row - empty_row) + abs(col - empty_col) == 1

    def move_tile(self, row, col, assisted=False):
        if self.won or self.paused or not self.can_move(row, col):
            return False

        previous_empty = self.empty_pos
        old_solution_stack = self.solution_stack.copy()
        self._swap_with_empty((row, col), count_move=True)
        self.history.append((previous_empty, old_solution_stack, self.assisted_moves))

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
        empty_row, empty_col = self.empty_pos
        row = empty_row + row_delta
        col = empty_col + col_delta
        if 0 <= row < self.grid_size and 0 <= col < self.grid_size:
            return self.move_tile(row, col)
        return False

    def undo(self):
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
        if self.solution_stack:
            return self.solution_stack[-1]
        movable = self._movable_positions()
        return movable[0] if movable else None

    def assist_one_step(self):
        hint = self.hint_position()
        if hint and self.can_move(*hint):
            return self.move_tile(*hint, assisted=True)
        return False

    def toggle_pause(self):
        if self.won:
            return

        if self.paused:
            self.started_at = time.time()
            self.paused = False
        else:
            self.elapsed_before_pause = self.elapsed_seconds()
            self.paused = True

    def _swap_with_empty(self, pos, count_move):
        row, col = pos
        empty_row, empty_col = self.empty_pos
        tile = self.tiles[row][col]

        self.tiles[empty_row][empty_col] = tile
        self.tiles[row][col] = None

        if tile is not None:
            tile.current_row = empty_row
            tile.current_col = empty_col

        self.empty_pos = (row, col)
        if count_move:
            self.moves += 1

    def is_completed(self):
        for row in self.tiles:
            for tile in row:
                if tile is not None and not tile.is_correct():
                    return False
        return True

    def elapsed_seconds(self):
        if self.finished_elapsed is not None:
            return int(self.finished_elapsed)
        if self.paused:
            return int(self.elapsed_before_pause)
        return int(self.elapsed_before_pause + time.time() - self.started_at)


class PuzzleGame:
    def __init__(self):
        pygame.init()
        pygame.key.set_repeat(180, 90)
        pygame.display.set_caption("Puzzle Game")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()

        self.font_title = self._load_font(38, bold=True)
        self.font_heading = self._load_font(24, bold=True)
        self.font_button = self._load_font(17, bold=True)
        self.font_body = self._load_font(18)
        self.font_small = self._load_font(15)
        self.font_tiny = self._load_font(13)

        self.data = self._load_data()
        settings = self.data.setdefault("settings", {})
        self.current_level_index = min(settings.get("level_index", 0), len(LEVELS) - 1)
        self.show_reference = settings.get("show_reference", True)
        self.show_numbers = settings.get("show_numbers", False)
        self.beginner_mode = settings.get("beginner_mode", True)
        self.high_contrast = settings.get("high_contrast", False)

        # Initialize SoundManager and load setting
        self.sound_manager = SoundManager()
        self.sound_manager.muted = settings.get("muted", False)

        # Initialize victory particles
        self.particles = []

        # Settings overlay state
        self.show_settings = False

        # Settings Overlay button layout definitions
        modal_width = 460
        modal_height = 420
        modal_left = (SCREEN_WIDTH - modal_width) // 2
        modal_top = (SCREEN_HEIGHT - modal_height) // 2
        self.settings_buttons = {
            "toggle_sound": pygame.Rect(modal_left + 300, modal_top + 70, 120, 32),
            "toggle_beginner": pygame.Rect(modal_left + 300, modal_top + 120, 120, 32),
            "toggle_numbers": pygame.Rect(modal_left + 300, modal_top + 170, 120, 32),
            "toggle_contrast": pygame.Rect(modal_left + 300, modal_top + 220, 120, 32),
            "toggle_reference": pygame.Rect(modal_left + 300, modal_top + 270, 120, 32),
            "open_help": pygame.Rect(modal_left + 40, modal_top + 320, 380, 34),
            "close": pygame.Rect(modal_left + 160, modal_top + 370, 140, 36),
        }

        grid_size = settings.get("grid_size", 4)
        if grid_size not in (3, 4, 5, 6):
            grid_size = 4

        self.source_image = self._load_current_level_image()
        self.board = Board(self.source_image, grid_size=grid_size)
        self.board.shuffle(self._shuffle_steps())

        self.show_help = False
        self.hint_until = 0
        self.peek_until = 0
        self.hovered_button = None
        self.hovered_cell = None
        self.last_win_stars = 0

        self.buttons = {
            "prev_level": pygame.Rect(PANEL_LEFT + 24, 282, 92, 36),
            "next_level": pygame.Rect(PANEL_LEFT + 124, 282, 92, 36),
            "random_level": pygame.Rect(PANEL_LEFT + 224, 282, 126, 36),
            "level_next_win": pygame.Rect(PANEL_LEFT + 358, 282, 126, 36),
            "grid_3": pygame.Rect(PANEL_LEFT + 24, 354, 80, 36),
            "grid_4": pygame.Rect(PANEL_LEFT + 112, 354, 80, 36),
            "grid_5": pygame.Rect(PANEL_LEFT + 200, 354, 80, 36),
            "grid_6": pygame.Rect(PANEL_LEFT + 288, 354, 80, 36),
            "reset": pygame.Rect(PANEL_LEFT + 24, 462, 116, 38),
            "undo": pygame.Rect(PANEL_LEFT + 148, 462, 116, 38),
            "hint": pygame.Rect(PANEL_LEFT + 272, 462, 96, 38),
            "assist": pygame.Rect(PANEL_LEFT + 376, 462, 108, 38),
            "peek": pygame.Rect(PANEL_LEFT + 24, 514, 146, 38),
            "pause": pygame.Rect(PANEL_LEFT + 181, 514, 146, 38),
            "quit": pygame.Rect(PANEL_LEFT + 338, 514, 146, 38),
            "settings": pygame.Rect(PANEL_LEFT + PANEL_WIDTH - 64, PANEL_TOP + 16, 40, 40),
        }

    def _load_font(self, size, bold=False):
        for name in ("segoeui", "arial", "tahoma", "dejavusans"):
            path = pygame.font.match_font(name, bold=bold)
            if path:
                font = pygame.font.Font(path, size)
                font.set_bold(bold)
                return font
        return pygame.font.SysFont("arial", size, bold=bold)

    def _load_data(self):
        if not os.path.exists(SAVE_PATH):
            return {"scores": {}, "settings": {}}

        try:
            with open(SAVE_PATH, "r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            return {"scores": {}, "settings": {}}

        data.setdefault("scores", {})
        data.setdefault("settings", {})
        return data

    def _save_data(self):
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
        except OSError:
            pass

    def _load_current_level_image(self):
        level = self.current_level()
        image_path = os.path.join(ASSETS_DIR, level.file_name)
        if os.path.exists(image_path):
            image = pygame.image.load(image_path).convert()
            return pygame.transform.smoothscale(image, (BOARD_SIZE, BOARD_SIZE))
        return self._create_default_image()

    def _create_default_image(self):
        image = pygame.Surface((BOARD_SIZE, BOARD_SIZE))
        image.fill((126, 191, 216))

        for y in range(BOARD_SIZE):
            ratio = y / BOARD_SIZE
            color = (
                int(105 + 60 * ratio),
                int(179 + 35 * ratio),
                int(210 - 25 * ratio),
            )
            pygame.draw.line(image, color, (0, y), (BOARD_SIZE, y))

        pygame.draw.circle(image, (255, 211, 77), (410, 86), 50)
        pygame.draw.polygon(image, (65, 103, 80), [(0, 320), (140, 160), (280, 320)])
        pygame.draw.polygon(image, (34, 86, 64), [(170, 326), (340, 132), (530, 326)])
        pygame.draw.rect(image, (68, 145, 90), (0, 320, BOARD_SIZE, 200))
        pygame.draw.polygon(image, (69, 123, 157), [(0, 392), (160, 350), (350, 452), (520, 410), (520, 520), (0, 520)])
        pygame.draw.rect(image, (241, 196, 126), (205, 312, 150, 112))
        pygame.draw.polygon(image, (245, 158, 66), [(180, 312), (280, 232), (380, 312)])
        return image.convert()

    def current_level(self):
        return LEVELS[self.current_level_index]

    def run(self):
        while True:
            self._handle_events()
            self._update_particles()
            self._draw()
            pygame.display.flip()
            self.clock.tick(FPS)

    def _update_particles(self):
        for p in self.particles[:]:
            p.update()
            if p.life <= 0:
                self.particles.remove(p)

        if self.board.won and len(self.particles) < 80:
            for _ in range(random.randint(1, 2)):
                px = BOARD_LEFT + random.uniform(20, BOARD_SIZE - 20)
                py = BOARD_TOP + BOARD_SIZE
                p = Particle(px, py)
                p.vy = random.uniform(-13, -7)
                self.particles.append(p)

    def _draw_particles(self):
        for p in self.particles:
            p.draw(self.screen)

    def _handle_events(self):
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
        if key == pygame.K_ESCAPE:
            self.sound_manager.play_click()
            if self.show_help:
                self.show_help = False
            elif self.show_settings:
                self.show_settings = False
            else:
                self._quit()
        elif key == pygame.K_F1:
            self.sound_manager.play_click()
            self.show_help = not self.show_help
        elif key == pygame.K_r:
            self.sound_manager.play_click()
            self._reset_board()
        elif key == pygame.K_u:
            self.sound_manager.play_click()
            if self.board.undo():
                self.sound_manager.play_slide()
        elif key == pygame.K_h:
            self.sound_manager.play_click()
            self.hint_until = time.time() + 2.5
        elif key == pygame.K_g:
            self.sound_manager.play_click()
            self._assist_one_step()
        elif key == pygame.K_SPACE:
            self.sound_manager.play_click()
            self.peek_until = time.time() + 2.5
        elif key == pygame.K_p:
            self.sound_manager.play_click()
            self.board.toggle_pause()
        elif key == pygame.K_n:
            self.sound_manager.play_click()
            self._change_level(1)
        elif key == pygame.K_b:
            self.sound_manager.play_click()
            self._change_level(-1)
        elif key == pygame.K_1:
            self.sound_manager.play_click()
            self._change_difficulty(3)
        elif key == pygame.K_2:
            self.sound_manager.play_click()
            self._change_difficulty(4)
        elif key == pygame.K_3:
            self.sound_manager.play_click()
            self._change_difficulty(5)
        elif key == pygame.K_4:
            self.sound_manager.play_click()
            self._change_difficulty(6)
        elif key in (pygame.K_LEFT, pygame.K_a):
            self._move_and_score(0, -1)
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self._move_and_score(0, 1)
        elif key in (pygame.K_UP, pygame.K_w):
            self._move_and_score(-1, 0)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self._move_and_score(1, 0)

    def _handle_click(self, mouse_pos):
        if self.show_help:
            help_box = pygame.Rect(210, 118, 740, 464)
            if not help_box.collidepoint(mouse_pos):
                self.sound_manager.play_click()
                self.show_help = False
            return

        if self.show_settings:
            clicked_settings_btn = None
            for key, rect in self.settings_buttons.items():
                if rect.collidepoint(mouse_pos):
                    clicked_settings_btn = key
                    break

            if clicked_settings_btn:
                self._handle_settings_click(clicked_settings_btn)
            else:
                modal_width = 460
                modal_height = 420
                modal_left = (SCREEN_WIDTH - modal_width) // 2
                modal_top = (SCREEN_HEIGHT - modal_height) // 2
                modal_rect = pygame.Rect(modal_left, modal_top, modal_width, modal_height)
                if not modal_rect.collidepoint(mouse_pos):
                    self.sound_manager.play_click()
                    self.show_settings = False
            return

        clicked_button = self._button_at(mouse_pos)
        if clicked_button:
            self._handle_button(clicked_button)
            return

        row_col = self._mouse_to_cell(mouse_pos)
        if row_col and self.board.move_tile(*row_col):
            self.sound_manager.play_slide()
            self._register_win_if_needed()

    def _handle_button(self, key):
        self.sound_manager.play_click()

        if key == "reset":
            self._reset_board()
        elif key == "undo":
            if self.board.undo():
                self.sound_manager.play_slide()
        elif key == "hint":
            self.hint_until = time.time() + 2.5
        elif key == "assist":
            self._assist_one_step()
        elif key == "peek":
            self.peek_until = time.time() + 2.5
        elif key == "pause":
            self.board.toggle_pause()
        elif key == "settings":
            self.show_settings = not self.show_settings
        elif key == "quit":
            self._quit()
        elif key == "prev_level":
            self._change_level(-1)
        elif key in ("next_level", "level_next_win"):
            self._change_level(1)
        elif key == "random_level":
            self._random_level()
        elif key.startswith("grid_"):
            self._change_difficulty(int(key[-1]))

    def _handle_settings_click(self, key):
        if key == "toggle_sound":
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
        elif key == "open_help":
            self.show_help = True
            self.show_settings = False
        elif key == "close":
            self.show_settings = False

        self.sound_manager.play_click()

    def _move_and_score(self, row_delta, col_delta):
        if self.board.move_empty(row_delta, col_delta):
            self.sound_manager.play_slide()
            self._register_win_if_needed()

    def _assist_one_step(self):
        if self.board.assist_one_step():
            self.sound_manager.play_slide()
            self._register_win_if_needed()

    def _register_win_if_needed(self):
        if not self.board.won:
            return

        self.sound_manager.play_win()
        self._spawn_victory_particles()

        stars = self._calculate_stars()
        self.last_win_stars = stars
        current = {
            "moves": self.board.moves,
            "time": self.board.elapsed_seconds(),
            "stars": stars,
            "assisted": self.board.assisted_moves,
        }

        scores = self.data.setdefault("scores", {})
        best = scores.get(self._score_key())
        if best is None or self._is_better_score(current, best):
            scores[self._score_key()] = current
            self._save_data()

    def _spawn_victory_particles(self):
        self.particles = []
        for _ in range(120):
            px = BOARD_LEFT + BOARD_SIZE // 2 + random.uniform(-100, 100)
            py = BOARD_TOP + BOARD_SIZE // 2 + random.uniform(-100, 100)
            self.particles.append(Particle(px, py))

    def _is_better_score(self, current, best):
        if current["stars"] != best.get("stars", 0):
            return current["stars"] > best.get("stars", 0)
        if current["moves"] != best.get("moves", 999999):
            return current["moves"] < best.get("moves", 999999)
        return current["time"] < best.get("time", 999999)

    def _calculate_stars(self):
        targets = {
            3: (90, 150),
            4: (190, 330),
            5: (420, 650),
            6: (760, 980),
        }
        move_target, time_target = targets[self.board.grid_size]
        stars = 1
        if self.board.moves <= move_target or self.board.elapsed_seconds() <= time_target:
            stars = 2
        if self.board.moves <= int(move_target * 0.65) and self.board.elapsed_seconds() <= int(time_target * 0.65):
            stars = 3
        if self.board.assisted_moves:
            stars = min(stars, 2)
        return stars

    def _change_difficulty(self, grid_size):
        if self.board.grid_size == grid_size:
            self._reset_board()
            return
        self.board = Board(self.source_image, grid_size=grid_size)
        self.board.shuffle(self._shuffle_steps())
        self.hint_until = 0
        self.peek_until = 0
        self.particles = []
        self._save_data()

    def _change_level(self, direction):
        self.current_level_index = (self.current_level_index + direction) % len(LEVELS)
        self.source_image = self._load_current_level_image()
        self.board = Board(self.source_image, grid_size=self.board.grid_size)
        self.board.shuffle(self._shuffle_steps())
        self.hint_until = 0
        self.peek_until = 0
        self.particles = []
        self._save_data()

    def _random_level(self):
        if len(LEVELS) <= 1:
            return

        next_index = self.current_level_index
        while next_index == self.current_level_index:
            next_index = random.randrange(len(LEVELS))

        self.current_level_index = next_index
        self.source_image = self._load_current_level_image()
        self.board = Board(self.source_image, grid_size=self.board.grid_size)
        self.board.shuffle(self._shuffle_steps())
        self.hint_until = 0
        self.peek_until = 0
        self.particles = []
        self._save_data()

    def _reset_board(self):
        self.board.shuffle(self._shuffle_steps())
        self.hint_until = 0
        self.peek_until = 0
        self.last_win_stars = 0
        self.particles = []
        self._save_data()

    def _shuffle_steps(self):
        if self.board.grid_size == 3:
            return 120
        if self.board.grid_size == 5:
            return 520
        if self.board.grid_size == 6:
            return 820
        return 300

    def _update_hover(self, mouse_pos):
        if self.show_settings:
            self.hovered_cell = None
            self.hovered_button = None
            for key, rect in self.settings_buttons.items():
                if rect.collidepoint(mouse_pos):
                    self.hovered_button = key
                    break
            if self.hovered_button:
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
            else:
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
            return

        self.hovered_button = self._button_at(mouse_pos)
        self.hovered_cell = self._mouse_to_cell(mouse_pos)

        hovering_move = (
            self.hovered_cell is not None
            and not self.board.paused
            and self.board.can_move(*self.hovered_cell)
        )
        if self.hovered_button or hovering_move:
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
        else:
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)

    def _button_at(self, mouse_pos):
        for key, rect in self.buttons.items():
            if rect.collidepoint(mouse_pos):
                return key
        return None

    def _mouse_to_cell(self, mouse_pos):
        x, y = mouse_pos
        if not (BOARD_LEFT <= x < BOARD_LEFT + BOARD_SIZE and BOARD_TOP <= y < BOARD_TOP + BOARD_SIZE):
            return None

        cell_size = BOARD_SIZE // self.board.grid_size
        col = (x - BOARD_LEFT) // cell_size
        row = (y - BOARD_TOP) // cell_size
        return row, col

    def _draw(self):
        if self.high_contrast:
            self.screen.fill((232, 240, 254))
        else:
            self.screen.fill(BG_COLOR)

        self._draw_header()
        self._draw_board()
        self._draw_panel()
        self._draw_particles()

        if self.show_settings:
            self._draw_settings_overlay()

        if self.show_help:
            self._draw_help_overlay()

    def _draw_header(self):
        title = self.font_title.render("Puzzle Game", True, TEXT_COLOR)
        subtitle = self.font_body.render(
            "Nhiều màn chơi, hỗ trợ người mới, gợi ý thông minh và lưu kỷ lục.",
            True,
            MUTED_COLOR,
        )
        level = self.current_level()
        progress = self.font_small.render(
            f"Màn {self.current_level_index + 1}/{len(LEVELS)}: {level.name}  •  Độ khó {self.board.grid_size}x{self.board.grid_size}",
            True,
            BLUE_DARK,
        )
        self.screen.blit(title, (BOARD_LEFT, 28))
        self.screen.blit(subtitle, (BOARD_LEFT, 72))
        self.screen.blit(progress, (BOARD_LEFT, 100))

    def _draw_settings_overlay(self):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((15, 23, 42, 160))
        self.screen.blit(overlay, (0, 0))

        modal_width = 460
        modal_height = 420
        modal_left = (SCREEN_WIDTH - modal_width) // 2
        modal_top = (SCREEN_HEIGHT - modal_height) // 2
        modal_rect = pygame.Rect(modal_left, modal_top, modal_width, modal_height)

        # Draw modal shadow & card
        shadow_rect = modal_rect.move(3, 5)
        pygame.draw.rect(self.screen, (10, 15, 30, 80), shadow_rect, border_radius=16)
        pygame.draw.rect(self.screen, (255, 255, 255), modal_rect, border_radius=16)
        pygame.draw.rect(self.screen, LINE_COLOR, modal_rect, width=2, border_radius=16)

        # Title
        title = self.font_heading.render("Cài đặt Game", True, TEXT_COLOR)
        self.screen.blit(title, title.get_rect(center=(modal_rect.centerx, modal_top + 34)))
        pygame.draw.line(self.screen, LINE_COLOR, (modal_left + 24, modal_top + 54), (modal_left + modal_width - 24, modal_top + 54), width=1)

        # Settings options list (No emojis to avoid rendering boxes)
        options = [
            ("toggle_sound", "Âm thanh", "Tắt tiếng" if self.sound_manager.muted else "Bật tiếng", RED if self.sound_manager.muted else TEAL),
            ("toggle_beginner", "Chế độ người mới", "Bật" if self.beginner_mode else "Tắt", GREEN if self.beginner_mode else SLATE),
            ("toggle_numbers", "Hiển thị số trên ô", "Hiện" if self.show_numbers else "Ẩn", TEAL if self.show_numbers else SLATE),
            ("toggle_contrast", "Tương phản dễ nhìn", "Bật" if self.high_contrast else "Tắt", ORANGE if self.high_contrast else SLATE),
            ("toggle_reference", "Hiển thị ảnh thu nhỏ", "Hiện" if self.show_reference else "Ẩn", BLUE if self.show_reference else SLATE),
        ]

        for key, label, val_text, color in options:
            rect = self.settings_buttons[key]
            
            # Label on the left
            lbl_surface = self.font_body.render(label, True, TEXT_COLOR)
            self.screen.blit(lbl_surface, (modal_left + 32, rect.y + 4))

            # Button on the right
            fill = color
            if self.hovered_button == key:
                fill = self._lighten(color, 20)
            
            pygame.draw.rect(self.screen, fill, rect, border_radius=6)
            pygame.draw.rect(self.screen, self._darken(fill, 20), rect, width=1, border_radius=6)
            btn_text = self.font_small.render(val_text, True, (255, 255, 255))
            self.screen.blit(btn_text, btn_text.get_rect(center=rect.center))

        # Open Help button
        help_rect = self.settings_buttons["open_help"]
        help_fill = BLUE_DARK if self.hovered_button == "open_help" else SLATE
        pygame.draw.rect(self.screen, help_fill, help_rect, border_radius=6)
        help_text = self.font_button.render("Xem hướng dẫn phím tắt", True, (255, 255, 255))
        self.screen.blit(help_text, help_text.get_rect(center=help_rect.center))

        # Close button
        close_rect = self.settings_buttons["close"]
        close_fill = self._lighten(RED, 20) if self.hovered_button == "close" else RED
        pygame.draw.rect(self.screen, close_fill, close_rect, border_radius=6)
        close_text = self.font_button.render("Đóng", True, (255, 255, 255))
        self.screen.blit(close_text, close_text.get_rect(center=close_rect.center))

    def _draw_board(self):
        shadow_rect = pygame.Rect(BOARD_LEFT + 5, BOARD_TOP + 7, BOARD_SIZE, BOARD_SIZE)
        pygame.draw.rect(self.screen, (215, 221, 232), shadow_rect, border_radius=10)
        pygame.draw.rect(self.screen, BOARD_BG_COLOR, (BOARD_LEFT, BOARD_TOP, BOARD_SIZE, BOARD_SIZE), border_radius=10)

        cell_size = BOARD_SIZE // self.board.grid_size
        show_hint = time.time() < self.hint_until
        hint_pos = self.board.hint_position()

        for row in range(self.board.grid_size):
            for col in range(self.board.grid_size):
                tile = self.board.tiles[row][col]

                if tile is None:
                    cell_rect = pygame.Rect(
                        BOARD_LEFT + col * cell_size,
                        BOARD_TOP + row * cell_size,
                        cell_size,
                        cell_size,
                    )
                    inner_rect = cell_rect.inflate(-6, -6)
                    self._draw_empty_cell(inner_rect)
                    continue

                # Calculate target screen coordinate
                target_x = BOARD_LEFT + col * cell_size
                target_y = BOARD_TOP + row * cell_size

                # Initialize or interpolate slide position
                if tile.draw_x is None:
                    tile.draw_x = target_x
                    tile.draw_y = target_y
                else:
                    tile.draw_x += (target_x - tile.draw_x) * 0.25
                    tile.draw_y += (target_y - tile.draw_y) * 0.25
                    if abs(tile.draw_x - target_x) < 0.5:
                        tile.draw_x = target_x
                    if abs(tile.draw_y - target_y) < 0.5:
                        tile.draw_y = target_y

                cell_rect = pygame.Rect(
                    tile.draw_x,
                    tile.draw_y,
                    cell_size,
                    cell_size,
                )
                inner_rect = cell_rect.inflate(-6, -6)

                self.screen.blit(pygame.transform.smoothscale(tile.image, inner_rect.size), inner_rect)
                self._draw_tile_state(tile, row, col, inner_rect, show_hint, hint_pos)

                if self.show_numbers:
                    self._draw_tile_number(tile, inner_rect)

        border_width = 5 if self.high_contrast else 3
        pygame.draw.rect(self.screen, BORDER_COLOR, (BOARD_LEFT, BOARD_TOP, BOARD_SIZE, BOARD_SIZE), width=border_width, border_radius=10)

        if time.time() < self.peek_until:
            self._draw_peek_overlay()
        if self.board.paused:
            self._draw_board_message("Tạm dừng", "Bấm P hoặc nút Tiếp tục để chơi tiếp")
        if self.board.won:
            stars = self._stars_text(self.last_win_stars or self._calculate_stars())
            self._draw_board_message("Chiến thắng!", f"{stars}  •  {self.board.moves} bước  •  {self._format_time(self.board.elapsed_seconds())}")

    def _draw_tile_state(self, tile, row, col, rect, show_hint, hint_pos):
        can_move = self.board.can_move(row, col)
        is_hovered = self.hovered_cell == (row, col)

        if show_hint and hint_pos == (row, col):
            pygame.draw.rect(self.screen, GOLD, rect.inflate(6, 6), width=5, border_radius=7)
            return

        if is_hovered and can_move and not self.board.paused:
            pygame.draw.rect(self.screen, BLUE, rect.inflate(5, 5), width=4, border_radius=7)
            return

        if self.beginner_mode:
            border_color = GREEN if tile.is_correct() else ORANGE
        else:
            border_color = BORDER_COLOR

        if self.high_contrast:
            pygame.draw.rect(self.screen, border_color, rect, width=4, border_radius=5)
        else:
            pygame.draw.rect(self.screen, border_color, rect, width=2, border_radius=5)

    def _draw_tile_number(self, tile, rect):
        number = str(tile.number(self.board.grid_size))
        bubble = pygame.Rect(rect.x + 8, rect.y + 8, 34, 28)
        pygame.draw.rect(self.screen, (15, 23, 42), bubble, border_radius=14)
        text = self.font_small.render(number, True, (255, 255, 255))
        self.screen.blit(text, text.get_rect(center=bubble.center))

    def _draw_empty_cell(self, rect):
        color = (255, 255, 255) if self.high_contrast else (241, 245, 249)
        pygame.draw.rect(self.screen, color, rect, border_radius=6)
        pygame.draw.rect(self.screen, (100, 116, 139), rect, width=3 if self.high_contrast else 2, border_radius=6)
        center = rect.center
        pygame.draw.line(self.screen, (148, 163, 184), (center[0] - 18, center[1]), (center[0] + 18, center[1]), width=3)
        pygame.draw.line(self.screen, (148, 163, 184), (center[0], center[1] - 18), (center[0], center[1] + 18), width=3)

    def _draw_peek_overlay(self):
        image = self.source_image.copy()
        image.set_alpha(222)
        self.screen.blit(image, (BOARD_LEFT, BOARD_TOP))
        self._draw_badge(BOARD_LEFT + 16, BOARD_TOP + 16, "Ảnh gốc")

    def _draw_badge(self, x, y, text):
        label = self.font_button.render(text, True, (255, 255, 255))
        badge = pygame.Rect(x, y, label.get_width() + 28, 34)
        pygame.draw.rect(self.screen, (15, 23, 42), badge, border_radius=17)
        self.screen.blit(label, label.get_rect(center=badge.center))

    def _draw_board_message(self, title, detail):
        overlay = pygame.Surface((BOARD_SIZE, BOARD_SIZE), pygame.SRCALPHA)
        overlay.fill((15, 23, 42, 154))
        self.screen.blit(overlay, (BOARD_LEFT, BOARD_TOP))

        box = pygame.Rect(BOARD_LEFT + 70, BOARD_TOP + 178, BOARD_SIZE - 140, 138)
        pygame.draw.rect(self.screen, (255, 255, 255), box, border_radius=12)
        pygame.draw.rect(self.screen, LINE_COLOR, box, width=2, border_radius=12)

        title_color = GREEN if title == "Chiến thắng!" else TEXT_COLOR
        title_surface = self.font_heading.render(title, True, title_color)
        detail_surface = self.font_body.render(detail, True, MUTED_COLOR)
        self.screen.blit(title_surface, title_surface.get_rect(center=(box.centerx, box.y + 44)))
        self.screen.blit(detail_surface, detail_surface.get_rect(center=(box.centerx, box.y + 88)))

    def _draw_panel(self):
        panel_rect = pygame.Rect(PANEL_LEFT, PANEL_TOP, PANEL_WIDTH, PANEL_HEIGHT)
        pygame.draw.rect(self.screen, (218, 226, 236), panel_rect.move(3, 5), border_radius=14)
        pygame.draw.rect(self.screen, PANEL_COLOR, panel_rect, border_radius=14)
        pygame.draw.rect(self.screen, LINE_COLOR, panel_rect, width=1, border_radius=14)

        self._draw_level_info()
        self._draw_difficulty()
        self._draw_stats()
        self._draw_controls()

    def _draw_level_info(self):
        level = self.current_level()
        self._panel_text("Màn chơi", PANEL_LEFT + 24, 62, self.font_heading, TEXT_COLOR)
        preview_rect = pygame.Rect(PANEL_LEFT + 24, 100, 154, 154)

        if self.show_reference:
            preview = pygame.transform.smoothscale(self.source_image, (154, 154))
            self.screen.blit(preview, preview_rect.topleft)
        else:
            pygame.draw.rect(self.screen, (241, 245, 249), preview_rect, border_radius=8)
            hidden = self.font_body.render("Đang ẩn ảnh", True, MUTED_COLOR)
            self.screen.blit(hidden, hidden.get_rect(center=preview_rect.center))
        pygame.draw.rect(self.screen, BORDER_COLOR, preview_rect, width=2, border_radius=8)

        info_x = PANEL_LEFT + 198
        self._panel_text(f"{self.current_level_index + 1}. {level.name}", info_x, 98, self.font_heading, TEXT_COLOR)
        self._draw_wrapped_text(level.description, info_x, 132, 302, self.font_small, MUTED_COLOR, line_height=20)
        self._panel_text("Thành tích màn này", info_x, 190, self.font_small, MUTED_COLOR)
        self._panel_text(self._level_best_text(), info_x, 214, self.font_body, BLUE_DARK)
        self._panel_text("Space: xem nhanh ảnh gốc", PANEL_LEFT + 24, 262, self.font_small, MUTED_COLOR)

        self._draw_button("prev_level", "Trước", SLATE)
        self._draw_button("next_level", "Sau", SLATE)
        self._draw_button("random_level", "Ngẫu nhiên", TEAL)
        self._draw_button("level_next_win", "Màn tiếp", PURPLE)

    def _draw_difficulty(self):
        self._panel_text("Độ khó", PANEL_LEFT + 24, 330, self.font_body, TEXT_COLOR)
        for size in (3, 4, 5, 6):
            self._draw_button(f"grid_{size}", f"{size}x{size}", SLATE, active=self.board.grid_size == size)

    def _draw_stats(self):
        y = 406
        self._draw_stat_card(PANEL_LEFT + 24, y, "Bước", str(self.board.moves))
        self._draw_stat_card(PANEL_LEFT + 148, y, "Thời gian", self._format_time(self.board.elapsed_seconds()))
        self._draw_stat_card(PANEL_LEFT + 272, y, "Trợ giúp", str(self.board.assisted_moves))
        self._draw_stat_card(PANEL_LEFT + 396, y, "Kỷ lục", self._best_score_text())

    def _draw_stat_card(self, x, y, label, value):
        rect = pygame.Rect(x, y, 108, 48)
        pygame.draw.rect(self.screen, (241, 245, 249), rect, border_radius=10)
        pygame.draw.rect(self.screen, (226, 232, 240), rect, width=1, border_radius=10)
        label_surface = self.font_tiny.render(label, True, MUTED_COLOR)
        value_surface = self.font_body.render(value, True, TEXT_COLOR)
        self.screen.blit(label_surface, (x + 12, y + 6))
        self.screen.blit(value_surface, (x + 12, y + 22))

    def _draw_controls(self):
        self._draw_button("reset", "Chơi lại", BLUE)
        self._draw_button("undo", "Hoàn tác", SLATE, disabled=not self.board.history)
        self._draw_button("hint", "Gợi ý", GOLD)
        self._draw_button("assist", "Giải 1 bước", PURPLE)

        self._draw_button("peek", "Xem ảnh", SLATE)
        pause_label = "Tiếp tục" if self.board.paused else "Tạm dừng"
        self._draw_button("pause", pause_label, GREEN if self.board.paused else SLATE)
        self._draw_button("settings", "⚙️", TEAL)
        self._draw_button("quit", "Thoát", RED)

    def _draw_help_overlay(self):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((15, 23, 42, 152))
        self.screen.blit(overlay, (0, 0))

        box = pygame.Rect(210, 118, 740, 464)
        pygame.draw.rect(self.screen, (255, 255, 255), box, border_radius=14)
        pygame.draw.rect(self.screen, LINE_COLOR, box, width=2, border_radius=14)

        self._panel_text("Hướng dẫn nhanh", box.x + 32, box.y + 26, self.font_heading, TEXT_COLOR)
        lines = [
            "Click vào mảnh ghép nằm cạnh ô trống để di chuyển.",
            "Phím mũi tên hoặc W A S D: di chuyển ô trống.",
            "R: chơi lại, U: hoàn tác, H: gợi ý, G: giải 1 bước.",
            "Space: xem nhanh ảnh gốc. P: tạm dừng. F1: mở hướng dẫn.",
            "N/B: chuyển màn sau/trước. Phím 1-4: chọn 3x3, 4x4, 5x5, 6x6.",
            "Bật Người mới để tô viền mảnh đúng/sai. Bật Số ô nếu cần dễ nhận diện hơn.",
            "Bật Dễ nhìn để tăng tương phản cho người dùng cần giao diện rõ hơn.",
            "Dùng Giải 1 bước nếu bị kẹt; lượt trợ giúp sẽ được ghi trong thành tích.",
        ]
        y = box.y + 78
        for line in lines:
            text = self.font_body.render(line, True, MUTED_COLOR)
            self.screen.blit(text, (box.x + 32, y))
            y += 42

        close = self.font_small.render("Bấm Esc hoặc click ra ngoài để đóng", True, BLUE_DARK)
        self.screen.blit(close, (box.x + 32, box.bottom - 42))

    def _draw_button(self, key, label, color, active=False, disabled=False):
        rect = self.buttons[key]
        fill = color
        
        # Customized gear icon for settings button
        if key == "settings":
            if self.hovered_button == "settings":
                fill = (226, 232, 240)
                icon_color = TEAL
            else:
                fill = (255, 255, 255)
                icon_color = TEXT_COLOR
            pygame.draw.rect(self.screen, fill, rect, border_radius=8)
            self._draw_gear_icon(self.screen, rect, icon_color, fill)
            return

        if disabled:
            fill = (203, 213, 225)
        elif active:
            fill = GREEN
        elif self.hovered_button == key:
            fill = self._lighten(color, 20)

        pygame.draw.rect(self.screen, fill, rect, border_radius=8)
        pygame.draw.rect(self.screen, self._darken(fill, 24), rect, width=1, border_radius=8)
        text_color = (255, 255, 255) if not disabled else (100, 116, 139)
        text = self._render_fit(label, self.font_button, text_color, rect.width - 12)
        self.screen.blit(text, text.get_rect(center=rect.center))

    def _draw_gear_icon(self, surface, rect, color, bg_color):
        center_x, center_y = rect.center
        outer_radius = 10
        inner_radius = 4
        num_teeth = 8
        tooth_width = 3
        tooth_length = 3

        # Draw 8 teeth radiating outwards
        for i in range(num_teeth):
            angle = i * (2 * math.pi / num_teeth)
            dx = math.cos(angle)
            dy = math.sin(angle)
            
            start_x = center_x + dx * (outer_radius - 2)
            start_y = center_y + dy * (outer_radius - 2)
            end_x = center_x + dx * (outer_radius + tooth_length)
            end_y = center_y + dy * (outer_radius + tooth_length)
            
            pygame.draw.line(surface, color, (start_x, start_y), (end_x, end_y), width=tooth_width)

        # Draw outer ring
        pygame.draw.circle(surface, color, (center_x, center_y), outer_radius)
        # Draw inner hole
        pygame.draw.circle(surface, bg_color, (center_x, center_y), inner_radius)

    def _render_fit(self, text, font, color, max_width):
        surface = font.render(text, True, color)
        if surface.get_width() <= max_width:
            return surface

        for size in range(16, 10, -1):
            small_font = self._load_font(size, bold=True)
            surface = small_font.render(text, True, color)
            if surface.get_width() <= max_width:
                return surface
        return surface

    def _panel_text(self, text, x, y, font=None, color=TEXT_COLOR):
        surface = (font or self.font_body).render(text, True, color)
        self.screen.blit(surface, (x, y))

    def _draw_wrapped_text(self, text, x, y, max_width, font, color, line_height=22):
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
        if line:
            self._panel_text(line, x, y, font, color)

    def _score_key(self):
        return f"{self.current_level().level_id}:{self.board.grid_size}x{self.board.grid_size}"

    def _best_score(self):
        return self.data.get("scores", {}).get(self._score_key())

    def _best_score_text(self):
        best = self._best_score()
        if not best:
            return "--"
        return f"{best.get('moves', 0)} / {self._stars_text(best.get('stars', 0))}"

    def _level_best_text(self):
        best_entries = []
        scores = self.data.get("scores", {})
        for size in (3, 4, 5, 6):
            key = f"{self.current_level().level_id}:{size}x{size}"
            if key in scores:
                best_entries.append(f"{size}x{size}: {self._stars_text(scores[key].get('stars', 0))}")
        return "  ".join(best_entries) if best_entries else "Chưa có kỷ lục"

    def _stars_text(self, count):
        count = max(0, min(3, int(count)))
        return "★" * count + "☆" * (3 - count)

    def _format_time(self, seconds):
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
