"""游戏会话模块 - 管理单局游戏的初始化、循环和结算（一杯制改造）"""

from __future__ import annotations

import logging
import math
import os
import time as time_module
from typing import Any

import pygame

from bci.data_reader import BCIDataReader
from config import (
    ARTIFACT_ATTENTION_THRESHOLD,
    ARTIFACT_PENALTY_DURATION,
    ARTIFACT_STILL_DURATION,
    ARTIFACT_STILL_THRESHOLD,
    BACKGROUND_IMG,
    CUP_DURATION,
    CUP_WIDTH,
    FORMAL_SPEED_MAX,
    FORMAL_SPEED_MIN,
    GAME_MODES,
    INGREDIENT_COLORS,
    INGREDIENT_IMGS,
    LANE_LINE_COLOR,
    LANE_WIDTH,
    NUM_LANES,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SECRET_RECIPE_SUSTAIN,
    TOP_BAR_IMG,
    TOTAL_CUPS,
    WARMUP_FREEZE_TIME,
    WARMUP_LOW_THRESHOLD,
    WARMUP_RESUME_TIME,
    get_attention_coefficient,
)
from data.score_manager import ScoreManager
from game.cup_manager import CupManager
from game.font_utils import load_chinese_font
from game.hud import draw_hud
from game.ingredient_manager import IngredientManager
from game.sprites import CatchEffect, Cup, MissEffect, Particle
from menu.summary import SummaryScreen

logger = logging.getLogger(__name__)


class GameSession:
    """管理单局游戏的完整生命周期（一杯制）"""

    screen: pygame.Surface
    clock: pygame.time.Clock
    game_mode: str

    mode_name: str
    has_required: bool
    free_combine: bool
    bci_mode: bool
    spawn_interval: float
    mode_speed: float

    font: pygame.font.Font
    hint_font: pygame.font.Font

    cup: Cup
    all_sprites: pygame.sprite.Group
    ingredients: pygame.sprite.Group
    catch_effects: pygame.sprite.Group
    miss_effects: pygame.sprite.Group
    particles: pygame.sprite.Group

    score_manager: ScoreManager
    ingredient_manager: IngredientManager
    cup_manager: CupManager

    bci_reader: BCIDataReader
    bci_available: bool

    background: pygame.Surface | None
    has_background: bool

    running: bool
    show_summary: bool
    use_yaw_control: bool
    game_start_time: float
    focus_samples: list[float]
    focus_above_seconds: float

    attention: float | None
    raw_gyro_x: float
    raw_gyro_y: float
    raw_gyro_z: float
    platform_focus_x: float
    platform_focus_y: float

    focus_min: int
    focus_max: int

    phase: str

    _esc_dialog_active: bool = False
    _esc_dialog_selected: int = 0

    def __init__(
        self,
        screen: pygame.Surface,
        clock: pygame.time.Clock,
        game_mode: str = "regular",
        profile=None,
        control_mode: str = "bci",
        audio=None,
    ) -> None:
        self.screen = screen
        self.clock = clock
        self.game_mode = game_mode
        self.control_mode = control_mode
        self._profile = profile
        self._upgrade_level = 0
        self._audio = audio

        self._load_mode_config()
        self._load_fonts()
        self._init_game_objects()
        self._cache_secret_popup_image()
        self._init_bci()
        self._load_background()
        self._init_state()
        self._print_mode_rules()
        self._draw_initial_frame()

    def _load_mode_config(self) -> None:
        mode_config = GAME_MODES.get(self.game_mode, GAME_MODES["bci"])
        self.mode_name = mode_config["name"]
        self.has_required = mode_config["has_required"]
        self.free_combine = mode_config["free_combine"]
        self.bci_mode = mode_config["bci_mode"]
        self.spawn_interval = mode_config["spawn_interval"] / 1000.0
        self.mode_speed = float(mode_config["ingredient_speed"])
        self._mode_total_cups = mode_config.get("total_cups", TOTAL_CUPS)
        self._mode_secret_interval = mode_config.get("secret_recipe_cup_interval", 3)
        self._infinite = mode_config.get("infinite", False)

    def _load_fonts(self) -> None:
        self.font = load_chinese_font(36)
        self.hint_font = load_chinese_font(20)
        self.recipe_font = load_chinese_font(28)
        self.pause_font = load_chinese_font(48)

    def _init_game_objects(self) -> None:
        self.cup = Cup()
        self.all_sprites = pygame.sprite.Group()
        self.all_sprites.add(self.cup)

        self.ingredients = pygame.sprite.Group()
        self.catch_effects = pygame.sprite.Group()
        self.miss_effects = pygame.sprite.Group()
        self.particles = pygame.sprite.Group()

        self.score_manager = ScoreManager()
        start_tier = self._profile.level if self._profile else 1
        self.ingredient_manager = IngredientManager(tier=start_tier)
        self.ingredient_manager.spawn_interval = self.spawn_interval

        if self.has_required:
            self.score_manager.set_required_ingredient("红茶")

        self.cup_manager = CupManager(
            has_required=self.has_required,
            required_type="红茶" if self.has_required else None,
            total_cups=self._mode_total_cups,
            secret_recipe_interval=self._mode_secret_interval,
        )
        self._current_tier = 1

    def _init_bci(self) -> None:
        self.bci_reader = BCIDataReader()
        self.bci_available = False
        if self.bci_mode and self.control_mode not in ("keyboard", "bci_failed"):
            self.bci_available = self.bci_reader.connect()

    def _load_background(self) -> None:
        self.background = None
        self.has_background = False
        try:
            if os.path.exists(BACKGROUND_IMG):
                self.background = pygame.image.load(BACKGROUND_IMG).convert()
                self.background = pygame.transform.scale(self.background, (SCREEN_WIDTH, SCREEN_HEIGHT))
                self.has_background = True
        except Exception:
            pass

        self._top_bar = None
        if os.path.exists(TOP_BAR_IMG):
            try:
                self._top_bar = pygame.image.load(TOP_BAR_IMG).convert_alpha()
                self._top_bar = pygame.transform.smoothscale(self._top_bar, (1280, 60))
            except Exception:
                pass

    def _init_state(self) -> None:
        self.running = True
        self.show_summary = False
        self.use_yaw_control = self.bci_available
        self.cup.yaw_control = self.use_yaw_control
        self.game_start_time = time_module.time()
        self.focus_samples = []
        self.focus_above_seconds = 0.0

        self.attention = None
        self.raw_gyro_x = 0.0
        self.raw_gyro_y = 0.0
        self.raw_gyro_z = 0.0
        self.platform_focus_x = float(SCREEN_WIDTH // 2)
        self.platform_focus_y = float(SCREEN_HEIGHT - 100)

        self._attn_offsets: list[float] = []
        self._attn_variance = 0.0
        self._attn_mode = "中等模式"

        self._paused = False
        self._low_attn_seconds = 0.0
        self._high_attn_seconds = 0.0
        self._blackout_alpha = 0.0

        self._prev_gyro_x = 0.0
        self._prev_gyro_y = 0.0
        self._prev_gyro_z = 0.0
        self._gyro_still_timer = 0.0
        self._artifact_frozen = False
        self._artifact_penalty_timer = 0.0
        self._artifact_alpha = 0.0
        self._secret_popup_timer = 0.0
        self._cup_attn_samples: list[float] = []
        self._cup_baseline: float = 40.0

        self.focus_min = CUP_WIDTH // 2
        self.focus_max = SCREEN_WIDTH - CUP_WIDTH // 2

        if not self.bci_available and self.bci_mode:
            logger.warning("BCI设备未连接，无法使用头动控制，将自动切换到键盘控制")
            self.use_yaw_control = False
            self.cup.yaw_control = False

        self._current_tier = self._profile.level if self._profile else 1

        self.phase = "formal"
        self.normalization_lower = 30.0
        self.normalization_upper = 70.0
        self.cup_manager.start_new_cup()

    def _print_mode_rules(self) -> None:
        logger.info("=" * 50)
        logger.info("疯狂奶茶杯 - %s（一杯制）", self.mode_name)
        logger.info("=" * 50)
        logger.info("直接开始正式游戏，第一杯结束后计算归一化值")
        if self.bci_mode:
            logger.info("脑机接口模式规则：")
            if self._infinite:
                logger.info("  无限杯数，按 ESC 退出")
            else:
                logger.info("  共 %s 杯，每杯最多 %s 秒", self._mode_total_cups, CUP_DURATION)
            logger.info("  专注力越高食材越慢，持续高专注触发秘方翻倍")
            if not self.bci_available:
                logger.warning("  [警告] BCI设备未连接，无法读取数据")
        elif self.free_combine:
            logger.info("创意模式规则：")
            if self._infinite:
                logger.info("  无限杯数，按 ESC 退出")
            else:
                logger.info("  共 %s 杯，每杯最多 %s 秒", self._mode_total_cups, CUP_DURATION)
            logger.info("  自由搭配食材，每 %s 杯触发秘方", self._mode_secret_interval)
        else:
            logger.info("控制说明:")
            logger.info("  共 %s 杯，每杯最多 %s 秒，需接住红茶", self._mode_total_cups, CUP_DURATION)
            logger.info("  每 %s 杯触发秘方翻倍", self._mode_secret_interval)
        logger.info("=" * 50)

    def _draw_initial_frame(self) -> None:
        if self.has_background and self.background:
            self.screen.blit(self.background, (0, 0))
        else:
            self.screen.fill((255, 255, 255))

        self.all_sprites.draw(self.screen)
        if self._top_bar:
            self.screen.blit(self._top_bar, (0, 0))
            mask = pygame.Surface((1280, 60), pygame.SRCALPHA)
            mask.fill((0, 0, 0, 60))
            self.screen.blit(mask, (0, 0))
        mode_text = self.font.render(f"{self.mode_name}", True, (100, 50, 150))
        self.screen.blit(mode_text, (10, 10))
        pygame.display.flip()

    def _normalize_to_range(self, attention: float) -> float:
        if self.normalization_upper - self.normalization_lower < 1.0:
            return 50.0
        normalized = (attention - self.normalization_lower) / (
            self.normalization_upper - self.normalization_lower
        ) * 99.0 + 1.0
        return max(1.0, min(100.0, normalized))

    def _update_formal_speed(self) -> None:
        if self.bci_mode:
            attn = self.attention if self.attention is not None else 50.0
            norm = self._normalize_to_range(attn)
            speed = FORMAL_SPEED_MAX - (norm - 1.0) / 99.0 * (FORMAL_SPEED_MAX - FORMAL_SPEED_MIN)
            self.ingredient_manager.set_current_speed(speed)
            for ing in self.ingredients:
                ing.speed = speed

            speed_ratio = speed / self.mode_speed if self.mode_speed > 0 else 1.0
            adjusted = self.spawn_interval * (0.7 + 0.6 * speed_ratio)
            self.ingredient_manager.set_spawn_interval(max(0.3, min(3.0, adjusted)))
        else:
            self.ingredient_manager.set_current_speed(self.mode_speed)
            self.ingredient_manager.set_spawn_interval(self.spawn_interval)

    def _update_pause_state(self, dt_sec: float) -> None:
        if self.attention is None:
            return
        if self.attention <= WARMUP_LOW_THRESHOLD:
            self._low_attn_seconds += dt_sec
            self._high_attn_seconds = 0.0
        elif self.attention > 15:
            self._high_attn_seconds += dt_sec
            self._low_attn_seconds = 0.0
        else:
            self._low_attn_seconds = 0.0
            self._high_attn_seconds = 0.0

        if not self._paused and self._low_attn_seconds >= WARMUP_FREEZE_TIME:
            self._paused = True
        elif self._paused and self._high_attn_seconds >= WARMUP_RESUME_TIME:
            self._paused = False
            self._low_attn_seconds = 0.0
            self._high_attn_seconds = 0.0
            self.ingredient_manager.reset_spawn_timer()

        target_alpha = 180 if self._paused else 0
        self._blackout_alpha += (target_alpha - self._blackout_alpha) * 0.05

    def _check_artifact(self, dt_sec: float) -> None:
        if self._artifact_frozen or not self.bci_mode:
            return

        gx = abs(self.raw_gyro_x - self._prev_gyro_x)
        gy = abs(self.raw_gyro_y - self._prev_gyro_y)
        gz = abs(self.raw_gyro_z - self._prev_gyro_z)

        self._prev_gyro_x = self.raw_gyro_x
        self._prev_gyro_y = self.raw_gyro_y
        self._prev_gyro_z = self.raw_gyro_z

        is_still = gx < ARTIFACT_STILL_THRESHOLD and gy < ARTIFACT_STILL_THRESHOLD and gz < ARTIFACT_STILL_THRESHOLD

        attn = self.attention if self.attention is not None else 50.0

        if is_still and attn > ARTIFACT_ATTENTION_THRESHOLD:
            self._gyro_still_timer += dt_sec
        else:
            self._gyro_still_timer = 0.0

        if self._gyro_still_timer >= ARTIFACT_STILL_DURATION:
            self._artifact_frozen = True
            self._artifact_penalty_timer = ARTIFACT_PENALTY_DURATION
            self._gyro_still_timer = 0.0
            self.ingredient_manager.reset_spawn_timer()
            logger.info(
                "防伪迹触发：头部静止 %.0f 秒且专注力 > %d", ARTIFACT_STILL_DURATION, ARTIFACT_ATTENTION_THRESHOLD
            )

    def _update_artifact_freeze(self, dt_sec: float) -> None:
        if not self._artifact_frozen:
            return

        self._artifact_penalty_timer -= dt_sec
        if self._artifact_penalty_timer <= 0.0:
            self._artifact_frozen = False
            self._artifact_penalty_timer = 0.0
            self._prev_gyro_x = self.raw_gyro_x
            self._prev_gyro_y = self.raw_gyro_y
            self._prev_gyro_z = self.raw_gyro_z
            self.ingredient_manager.reset_spawn_timer()
            logger.info("防伪迹惩罚结束，恢复游戏")

        target_alpha = 180 if self._artifact_frozen else 0
        self._artifact_alpha += (target_alpha - self._artifact_alpha) * 0.1

    @property
    def _game_frozen(self) -> bool:
        return self._paused or self._artifact_frozen

    def run(self) -> str:
        self._render()
        self.clock.tick(60)
        while self.running:
            dt = self.clock.tick(60)
            keys = pygame.key.get_pressed()
            dt_sec = dt / 1000.0

            self._handle_events()
            if not self.running:
                break

            if self._esc_dialog_active:
                if getattr(self, "_skip_frame", False):
                    self._skip_frame = False
                else:
                    self._render()
                continue

            self._update_bci_data()

            self._update_cup(keys, dt_sec)
            self._update_pause_state(dt_sec)
            self._check_artifact(dt_sec)
            self._update_artifact_freeze(dt_sec)

            if not self._game_frozen:
                self._update_attention_variance()
                self._update_formal_speed()
                self._check_secret_recipe(dt_sec)
                self._check_cup_end()

            if not self.running:
                break

            if not self._game_frozen:
                self._update_game_objects(dt_sec)
                self._handle_collisions()

            self._render()

        return self._end_game()

    def _handle_events(self) -> None:
        show_dialog = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self._esc_dialog_active:
                        self._esc_dialog_active = False
                    else:
                        show_dialog = True
                elif self._esc_dialog_active:
                    if event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_TAB):
                        self._esc_dialog_selected = 1 - self._esc_dialog_selected
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self._commit_esc_dialog()
            elif event.type == pygame.MOUSEBUTTONDOWN and self._esc_dialog_active:
                if event.button == 1:
                    self._handle_esc_dialog_click(event.pos)
        if show_dialog:
            self._show_esc_dialog()

    def _show_esc_dialog(self) -> None:
        self._esc_dialog_active = True
        self._esc_dialog_selected = 0
        self._skip_frame = True

    def _commit_esc_dialog(self) -> None:
        if self._esc_dialog_selected == 0:
            self._esc_dialog_active = False
        else:
            self.show_summary = False
            self.running = False

    def _handle_esc_dialog_click(self, pos: tuple[int, int]) -> None:
        if hasattr(self, "_esc_continue_rect") and self._esc_continue_rect.collidepoint(pos):
            self._esc_dialog_active = False
        elif hasattr(self, "_esc_exit_rect") and self._esc_exit_rect.collidepoint(pos):
            self.show_summary = False
            self.running = False

    def _draw_esc_dialog(self) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        box_w, box_h = 380, 200
        box_x = (SCREEN_WIDTH - box_w) // 2
        box_y = (SCREEN_HEIGHT - box_h) // 2
        box_rect = pygame.Rect(box_x, box_y, box_w, box_h)
        pygame.draw.rect(self.screen, (30, 28, 20), box_rect, border_radius=16)
        pygame.draw.rect(self.screen, (200, 160, 100), box_rect, 3, border_radius=16)

        title = self.pause_font.render("暂停", True, (255, 255, 255))
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, box_y + 25))

        btn_w, btn_h = 150, 48
        btn_y = box_y + 105
        gap = 20
        left_x = SCREEN_WIDTH // 2 - btn_w - gap // 2
        right_x = SCREEN_WIDTH // 2 + gap // 2

        continue_selected = self._esc_dialog_selected == 0
        exit_selected = self._esc_dialog_selected == 1

        continue_color = (80, 180, 80)
        exit_color = (200, 60, 60)
        selected_border = (255, 255, 255)
        normal_border = (100, 100, 100) if not exit_selected else (80, 80, 80)

        self._esc_continue_rect = pygame.Rect(left_x, btn_y, btn_w, btn_h)
        continue_border = selected_border if continue_selected else normal_border
        pygame.draw.rect(self.screen, continue_color, self._esc_continue_rect, border_radius=10)
        pygame.draw.rect(self.screen, continue_border, self._esc_continue_rect, 3, border_radius=10)
        continue_text = self.font.render("继续游戏", True, (255, 255, 255))
        self.screen.blit(
            continue_text,
            (
                self._esc_continue_rect.centerx - continue_text.get_width() // 2,
                self._esc_continue_rect.centery - continue_text.get_height() // 2,
            ),
        )

        self._esc_exit_rect = pygame.Rect(right_x, btn_y, btn_w, btn_h)
        exit_border = selected_border if exit_selected else normal_border
        pygame.draw.rect(self.screen, exit_color, self._esc_exit_rect, border_radius=10)
        pygame.draw.rect(self.screen, exit_border, self._esc_exit_rect, 3, border_radius=10)
        exit_text = self.font.render("退出游戏", True, (255, 255, 255))
        self.screen.blit(
            exit_text,
            (
                self._esc_exit_rect.centerx - exit_text.get_width() // 2,
                self._esc_exit_rect.centery - exit_text.get_height() // 2,
            ),
        )

    def _update_bci_data(self) -> None:
        if self.control_mode == "keyboard":
            self.attention = 50.0
            return
        if self.bci_available:
            result = self.bci_reader.read_with_timeout()
            self.bci_available = self.bci_reader.connected
            if self.bci_available and result[0] is not None:
                (
                    self.attention,
                    self.platform_focus_x,
                    self.platform_focus_y,
                    self.raw_gyro_x,
                    self.raw_gyro_y,
                    self.raw_gyro_z,
                ) = result
            else:
                self.attention = 50
        else:
            if not self.bci_mode:
                self.attention = None

        if self.attention is not None:
            self.focus_samples.append(self.attention)
            self._cup_attn_samples.append(self.attention)

    def _update_attention_variance(self) -> None:
        if self.attention is None:
            return
        baseline = self._cup_baseline if self._cup_baseline > 0 else 40.0
        offset = self.attention - baseline
        self._attn_offsets.append(offset)
        if len(self._attn_offsets) > 60:
            self._attn_offsets = self._attn_offsets[-60:]

        if len(self._attn_offsets) >= 5:
            mean = sum(self._attn_offsets) / len(self._attn_offsets)
            self._attn_variance = sum((x - mean) ** 2 for x in self._attn_offsets) / len(self._attn_offsets)

            if self._attn_variance < 50:
                self._attn_mode = "简单模式"
                ice_prob = 0.2
            elif self._attn_variance < 150:
                self._attn_mode = "中等模式"
                ice_prob = 0.5
            else:
                self._attn_mode = "困难模式"
                if self.attention is not None and self.attention < 20:
                    ice_prob = 1.0
                else:
                    ice_prob = 0.8

            self.ingredient_manager.set_ice_probability(ice_prob)

    def _update_cup(self, keys: pygame.key.ScancodeWrapper, dt_sec: float) -> None:
        self.cup.update(keys=keys, dt=dt_sec)
        kb_pressed = keys[pygame.K_LEFT] or keys[pygame.K_RIGHT]
        if not kb_pressed and self.use_yaw_control:
            fx = int(self.platform_focus_x)
            self.cup.rect.centerx = max(self.focus_min, min(self.focus_max, fx))

    def _check_secret_recipe(self, dt_sec: float) -> None:
        if self._secret_popup_timer > 0:
            self._secret_popup_timer -= dt_sec
            return
        if self.cup_manager.secret_recipe_spawned:
            return
        if self.cup_manager.cup_ended:
            return

        if self.bci_mode:
            threshold = self._cup_baseline + 10
            attn = self.attention if self.attention is not None else 50.0
            if attn > threshold:
                self.focus_above_seconds += dt_sec
            else:
                self.focus_above_seconds = 0.0

            if self.focus_above_seconds >= SECRET_RECIPE_SUSTAIN and self.cup_manager.trigger_secret_recipe():
                self._secret_popup_timer = 2.0
                self.focus_above_seconds = 0.0
                if self._audio:
                    self._audio.play_sfx("音效/触发秘方.wav", volume=0.7)
                logger.info("秘方触发！专注力持续高于阈值 %.0f 达 %d 秒", threshold, SECRET_RECIPE_SUSTAIN)
        else:
            if self.cup_manager.should_force_secret_recipe() and self.cup_manager.catch_count == 0:
                if self.cup_manager.trigger_secret_recipe():
                    self._secret_popup_timer = 2.0
                    if self._audio:
                        self._audio.play_sfx("音效/触发秘方.wav", volume=0.7)
                    logger.info("第 %s 杯触发秘方！", self.cup_manager.cup_number)

    def _check_cup_end(self) -> None:
        if self.cup_manager.check_cup_end():
            if self._cup_attn_samples:
                self._cup_baseline = sum(self._cup_attn_samples) / len(self._cup_attn_samples)

            if self.cup_manager.cup_number == 1 and self._cup_attn_samples:
                max_attn = max(self._cup_attn_samples)
                avg_attn = sum(self._cup_attn_samples) / len(self._cup_attn_samples)
                self.normalization_lower = max(avg_attn - 15.0, 0.0)
                self.normalization_upper = min(max_attn, 100.0)
                if self.normalization_upper - self.normalization_lower < 10.0:
                    mid = (self.normalization_upper + self.normalization_lower) / 2.0
                    self.normalization_lower = max(mid - 5.0, 0.0)
                    self.normalization_upper = min(mid + 5.0, 100.0)
                logger.info(
                    "第一杯结束！最高=%.1f 平均=%.1f  归一化范围: [%.1f, %.1f]",
                    max_attn,
                    avg_attn,
                    self.normalization_lower,
                    self.normalization_upper,
                )

            self._cup_attn_samples = []

            cup_money = self.cup_manager.settle_cup()
            had_secret = self.cup_manager.secret_recipe_spawned

            if self.bci_mode and cup_money > 0:
                attn = self.attention if self.attention is not None else 50.0
                norm = self._normalize_to_range(attn)
                coeff = get_attention_coefficient(norm)
                cup_money = int(cup_money * coeff)

            self.score_manager.add_cup_money(cup_money, had_secret)
            if self._audio and cup_money > 0:
                self._audio.play_sfx("音效/加金币.wav", volume=0.5)
            self.score_manager.reset_cup_ingredients()
            self.focus_above_seconds = 0.0

            if not self._infinite:
                if self.cup_manager.all_cups_done():
                    self.show_summary = True
                    self.running = False
                    logger.info("全部 %s 杯完成，游戏结束！", self.cup_manager.total_cups)
                    return

                if self.cup_manager.is_game_time_exceeded(self.game_start_time):
                    self.show_summary = True
                    self.running = False
                    logger.info("总局时间已到，游戏结束！")
                    return

            self.cup_manager.start_new_cup()
            self.cup.update_level(0)
            self.score_manager.reset_cup_ingredients()
            self.creative_ingredients = []
            self.recipe_result = None

    def _update_game_objects(self, dt_sec: float) -> None:
        ingredient = self.ingredient_manager.update(required_types=None, ingredients_group=self.ingredients)
        if ingredient:
            self.ingredients.add(ingredient)
            if ingredient.is_required:
                ingredient.set_particle_group(self.particles)

        self.ingredients.update()
        self.catch_effects.update(dt=dt_sec)
        self.miss_effects.update(dt=dt_sec)
        self.particles.update(dt=dt_sec)

    def _handle_collisions(self) -> None:
        threshold_y = self.cup.rect.top + self.cup.rect.height * 0.8
        hits = pygame.sprite.spritecollide(self.cup, self.ingredients, False)

        _handle_catches(
            hits,
            self.cup,
            threshold_y,
            self.ingredients,
            self.miss_effects,
            self.catch_effects,
            self.particles,
            self.score_manager,
            self.cup_manager,
            audio=self._audio,
        )

        _handle_misses(self.ingredients, threshold_y, self.miss_effects, self.particles, audio=self._audio)

    def _render(self) -> None:
        if self.has_background and self.background:
            self.screen.blit(self.background, (0, 0))
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 10, 90))
            self.screen.blit(overlay, (0, 0))
        else:
            self.screen.fill((255, 255, 255))

        self.all_sprites.draw(self.screen)
        self.particles.draw(self.screen)
        self.ingredients.draw(self.screen)
        self.catch_effects.draw(self.screen)
        self.miss_effects.draw(self.screen)

        self._render_formal_hud()

        if self._esc_dialog_active:
            self._draw_esc_dialog()

        pygame.display.flip()

    def _draw_lane_lines(self) -> None:
        lane_overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        for i in range(1, NUM_LANES):
            if i == NUM_LANES // 2:
                continue
            x = i * LANE_WIDTH
            pygame.draw.line(lane_overlay, LANE_LINE_COLOR, (x, 60), (x, SCREEN_HEIGHT), 2)
        self.screen.blit(lane_overlay, (0, 0))

    def _render_formal_hud(self) -> None:
        self._draw_lane_lines()
        if self._top_bar:
            self.screen.blit(self._top_bar, (0, 0))
            mask = pygame.Surface((1280, 60), pygame.SRCALPHA)
            mask.fill((0, 0, 0, 60))
            self.screen.blit(mask, (0, 0))

        draw_hud(
            screen=self.screen,
            score_manager=self.score_manager,
            mode_name=self.mode_name,
            cup_manager=self.cup_manager,
            game_start_time=self.game_start_time,
            font=self.font,
            hint_font=self.hint_font,
            attention=self.attention,
            bci_mode=self.bci_mode,
            free_combine=self.free_combine,
            bci_connected=self.bci_available,
            # focus_above_seconds=self.focus_above_seconds,
            # raw_gyro_x=self.raw_gyro_x,
            # raw_gyro_y=self.raw_gyro_y,
            # raw_gyro_z=self.raw_gyro_z,
            # platform_focus_x=self.platform_focus_x,
            # platform_focus_y=self.platform_focus_y,
            # cup_x=self.cup.rect.centerx,
            # cup_y=self.cup.rect.centery,
            # attn_variance=self._attn_variance,
            # attn_mode=self._attn_mode,
            # attn_baseline=40.0,
        )

        if self.bci_mode:
            bci_status_color = (0, 255, 0) if self.bci_available else (255, 100, 100)
            bci_status_text = self.hint_font.render(
                f"头环: {'已连接' if self.bci_available else '未连接'}",
                True,
                bci_status_color,
            )
            self.screen.blit(bci_status_text, (10, SCREEN_HEIGHT - 60))

        if self._blackout_alpha > 1:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, int(self._blackout_alpha)))
            self.screen.blit(overlay, (0, 0))

            if self._paused:
                pause_text = self.pause_font.render("请调整身心状态", True, (255, 255, 255))
                self.screen.blit(
                    pause_text,
                    (SCREEN_WIDTH // 2 - pause_text.get_width() // 2, SCREEN_HEIGHT // 2 - 60),
                )
                sub_text = self.hint_font.render(
                    f"保持专注力 >15 持续 {max(0, int(WARMUP_RESUME_TIME) - self._high_attn_seconds):.0f}s 恢复游戏",
                    True,
                    (200, 200, 200),
                )
                self.screen.blit(
                    sub_text,
                    (SCREEN_WIDTH // 2 - sub_text.get_width() // 2, SCREEN_HEIGHT // 2 + 20),
                )

        if self._artifact_alpha > 1:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, int(self._artifact_alpha)))
            self.screen.blit(overlay, (0, 0))

            if self._artifact_frozen:
                pause_text = self.pause_font.render("请放松面部肌肉", True, (255, 255, 255))
                self.screen.blit(
                    pause_text,
                    (SCREEN_WIDTH // 2 - pause_text.get_width() // 2, SCREEN_HEIGHT // 2 - 60),
                )
                sub_text = self.hint_font.render(
                    f"检测到伪迹，冻结 {self._artifact_penalty_timer:.0f}s",
                    True,
                    (200, 200, 200),
                )
                self.screen.blit(
                    sub_text,
                    (SCREEN_WIDTH // 2 - sub_text.get_width() // 2, SCREEN_HEIGHT // 2 + 20),
                )

        if self._secret_popup_timer > 0:
            self._draw_secret_popup()

    def _cache_secret_popup_image(self) -> None:
        self._secret_img = None
        img_path = INGREDIENT_IMGS.get("秘方", "")
        if img_path and os.path.exists(img_path):
            img = pygame.image.load(img_path).convert_alpha()
            self._secret_img = pygame.transform.scale(img, (80, 80))

    def _draw_secret_popup(self) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 80))
        self.screen.blit(overlay, (0, 0))

        popup_w, popup_h = 260, 220
        popup_x = (SCREEN_WIDTH - popup_w) // 2
        popup_y = (SCREEN_HEIGHT - popup_h) // 2

        pygame.draw.rect(self.screen, (30, 25, 20), (popup_x, popup_y, popup_w, popup_h), border_radius=16)
        pygame.draw.rect(self.screen, (255, 180, 100), (popup_x, popup_y, popup_w, popup_h), 3, border_radius=16)

        text_surf = self.font.render("触发秘方！", True, (255, 220, 100))
        self.screen.blit(text_surf, (popup_x + (popup_w - text_surf.get_width()) // 2, popup_y + 25))

        if self._secret_img is not None:
            t = pygame.time.get_ticks() / 1000.0
            wobble_x = int(math.sin(t * 4) * 10)
            angle = math.sin(t * 3) * 5
            rotated = pygame.transform.rotate(self._secret_img, angle)
            rx = popup_x + (popup_w - rotated.get_width()) // 2 + wobble_x
            ry = popup_y + 80 + (rotated.get_height() - 80) // 2
            self.screen.blit(rotated, (rx, ry))

    def _end_game(self) -> str:
        if self._audio:
            self._audio.play_sfx("音效/游戏结束.wav", volume=0.6)
        if self.show_summary:
            avg_focus = sum(self.focus_samples) / len(self.focus_samples) if self.focus_samples else 0.0
            if not self.bci_mode:
                avg_focus = 0.0

            game_duration = time_module.time() - self.game_start_time
            last_5min_avg = avg_focus
            if self.focus_samples and game_duration > 0:
                sps = len(self.focus_samples) / game_duration
                n = max(1, int(sps * 300))
                last_samples = self.focus_samples[-n:]
                last_5min_avg = sum(last_samples) / len(last_samples)

            if self._profile:
                skip_history = self._infinite or (
                    self.control_mode in ("bci", "bci_failed", "keyboard") and self.bci_mode and not self.bci_available
                )
                if skip_history:
                    is_upgraded = False
                    p_level = self._profile.level
                    p_rev = self._profile.cumulative_revenue
                    self._upgrade_level = self._profile.level
                else:
                    old_level = self._profile.level
                    upgraded = self._profile.add_game_result(
                        revenue=self.score_manager.total_money,
                        mode=self.game_mode,
                        cups=self.score_manager.cup_count,
                        secrets=self.score_manager.secret_recipe_count,
                        avg_attention=avg_focus,
                        duration=game_duration,
                        focus_samples=self.focus_samples,
                        last_5min_avg_attention=last_5min_avg,
                    )
                    self._upgrade_level = old_level if upgraded else self._profile.level
                    is_upgraded = upgraded > 0
                    if is_upgraded and self._audio:
                        self._audio.play_sfx("音效/升级.wav", volume=0.7)
                    p_level = self._profile.level
                    p_rev = self._profile.cumulative_revenue
            else:
                self._upgrade_level = 1
                is_upgraded = False
                p_level = 1
                p_rev = 0

            summary = SummaryScreen(
                self.screen,
                self.score_manager.score,
                avg_focus,
                self.game_mode,
                total_money=self.score_manager.total_money,
                cup_count=self.score_manager.cup_count,
                secret_count=self.score_manager.secret_recipe_count,
                max_cup_money=self.score_manager.get_max_cup_money(),
                player_level=p_level,
                cumulative_revenue=p_rev,
                upgraded=is_upgraded,
                focus_samples=self.focus_samples,
            )
            return summary.run()

        if self.bci_available:
            self.bci_reader.disconnect()
        return ""


def run_game(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    game_mode: str = "regular",
    profile=None,
    control_mode: str = "bci",
    audio=None,
) -> str:
    session = GameSession(screen, clock, game_mode, profile, control_mode=control_mode, audio=audio)
    return session.run()


def _handle_catches(
    hits: list[Any],
    cup: Cup,
    threshold_y: float,
    ingredients: pygame.sprite.Group,
    miss_effects: pygame.sprite.Group,
    catch_effects: pygame.sprite.Group,
    particles: pygame.sprite.Group,
    score_manager: ScoreManager,
    cup_manager: CupManager,
    audio=None,
) -> None:
    for hit in hits:
        if hit.rect.bottom > threshold_y:
            hit.rect.bottom = int(threshold_y)
            miss_effects.add(MissEffect(hit))
            color = INGREDIENT_COLORS.get(hit.type, (200, 200, 200))
            for _ in range(4):
                p = Particle(hit.rect.centerx, int(threshold_y), color)
                p.vx *= 0.4
                p.vy *= 0.4
                p.decay *= 1.5
                particles.add(p)
            ingredients.remove(hit)
        else:
            ingredients.remove(hit)
            effect = CatchEffect(hit, cup.rect)
            catch_effects.add(effect)
            for _ in range(8):
                color = INGREDIENT_COLORS.get(hit.type, (255, 200, 0))
                particles.add(Particle(hit.rect.centerx, hit.rect.centery, color))
            cup.trigger_bounce()

            score_manager.add_ingredient(hit.type, is_required=hit.is_required)
            cup_manager.add_catch(hit.type, is_required=hit.is_required)

            cup.update_level(cup_manager.catch_count)
            logger.info("接住 %s！收益: %s", hit.type, score_manager.total_money)

            if audio:
                if hit.is_required:
                    audio.play_sfx("音效/接到必接食材.wav", volume=0.3)
                else:
                    audio.play_sfx("音效/接到食材.wav", volume=0.2)


def _handle_misses(
    ingredients: pygame.sprite.Group,
    threshold_y: float,
    miss_effects: pygame.sprite.Group,
    particles: pygame.sprite.Group,
    audio=None,
) -> None:
    for ing in ingredients.sprites():
        if ing.rect.bottom > threshold_y:
            ing.rect.bottom = int(threshold_y)
            miss_effects.add(MissEffect(ing))
            color = INGREDIENT_COLORS.get(ing.type, (200, 200, 200))
            for _ in range(4):
                p = Particle(ing.rect.centerx, int(threshold_y), color)
                p.vx *= 0.4
                p.vy *= 0.4
                p.decay *= 1.5
                particles.add(p)
            ingredients.remove(ing)
            if audio and getattr(ing, "is_required", False):
                audio.play_sfx("音效/漏接必接食材.wav", volume=0.5)
