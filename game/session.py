"""游戏会话模块 - 管理单局游戏的初始化、循环和结算（一杯制改造）"""

from __future__ import annotations

import logging
import os
import time as time_module
from collections import deque
from typing import Any

import pygame

from bci.data_reader import BCIDataReader
from bci.filter import (
    AttentionMappingCurve,
)
from config import (
    ARTIFACT_ATTENTION_THRESHOLD,
    ARTIFACT_PENALTY_DURATION,
    ARTIFACT_STILL_DURATION,
    ARTIFACT_STILL_THRESHOLD,
    BACKGROUND_IMG,
    CUP_DURATION,
    CUP_WIDTH,
    DEFAULT_GAME_MODE,
    FORMAL_SPEED_MAX,
    FORMAL_SPEED_MIN,
    GAME_MODES,
    INGREDIENT_COLORS,
    LANE_LINE_COLOR,
    LANE_WIDTH,
    NUM_LANES,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SECRET_RECIPE_OFFSET,
    SECRET_RECIPE_SUSTAIN,
    TOP_BAR_IMG,
    TOTAL_CUPS,
    WARMUP_DURATION,
    WARMUP_LOW_THRESHOLD,
    WARMUP_SMOOTH_WINDOW,
    WARMUP_SPEED_MAX,
    WARMUP_SPEED_MIN,
    get_attention_coefficient,
)
from data.recipes import evaluate_recipe
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
    recipe_font: pygame.font.Font

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
    attention_curve: AttentionMappingCurve | None

    background: pygame.Surface | None
    has_background: bool

    creative_ingredients: list[str]
    recipe_result: dict[str, Any] | None

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

    phase: str  # "warmup_intro" | "warmup" | "warmup_summary" | "formal"
    warmup_start_time: float
    warmup_elapsed: float
    warmup_paused: bool
    warmup_low_timer: float
    warmup_high_timer: float
    warmup_attn_buffer: deque
    warmup_all_attn: list[float]
    normalization_lower: float
    normalization_upper: float
    warmup_intro_timer: float
    warmup_intro_alpha: float
    warmup_summary_timer: float
    warmup_summary_max: float
    warmup_summary_avg: float

    def __init__(
        self,
        screen: pygame.Surface,
        clock: pygame.time.Clock,
        game_mode: str = "regular",
        profile=None,
    ) -> None:
        self.screen = screen
        self.clock = clock
        self.game_mode = game_mode
        self._profile = profile
        self._upgrade_level = 0

        self._load_mode_config()
        self._load_fonts()
        self._init_game_objects()
        self._init_bci()
        self._load_background()
        self._init_state()
        self._print_mode_rules()
        self._draw_initial_frame()

    def _load_mode_config(self) -> None:
        mode_config = GAME_MODES.get(self.game_mode, GAME_MODES[DEFAULT_GAME_MODE])
        self.mode_name = mode_config["name"]
        self.has_required = mode_config["has_required"]
        self.free_combine = mode_config["free_combine"]
        self.bci_mode = mode_config["bci_mode"]
        self.spawn_interval = mode_config["spawn_interval"] / 1000.0
        self.mode_speed = float(mode_config["ingredient_speed"])
        self._mode_total_cups = mode_config.get("total_cups", TOTAL_CUPS)
        self._mode_secret_interval = mode_config.get("secret_recipe_cup_interval", 3)

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
        if self.bci_mode:
            self.bci_available = self.bci_reader.connect()

        self.attention_curve = None
        if self.free_combine:
            self.attention_curve = AttentionMappingCurve()

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
        self.creative_ingredients = []
        self.recipe_result = None

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

        self.focus_min = CUP_WIDTH // 2
        self.focus_max = SCREEN_WIDTH - CUP_WIDTH // 2

        if not self.bci_available and self.bci_mode:
            logger.warning("BCI设备未连接，无法使用头动控制，将自动切换到键盘控制")
            self.use_yaw_control = False
            self.cup.yaw_control = False

        self._current_tier = self._profile.level if self._profile else 1

        # 热身阶段状态初始化
        self.phase = "warmup_intro"
        self.warmup_intro_timer = 0.0
        self.warmup_intro_alpha = 255.0
        self.warmup_summary_timer = 0.0
        self.warmup_summary_max = 0.0
        self.warmup_summary_avg = 0.0
        self.warmup_start_time = time_module.time()
        self.warmup_elapsed = 0.0
        self.warmup_paused = False
        self.warmup_low_timer = 0.0
        self.warmup_high_timer = 0.0
        self.warmup_attn_buffer = deque(maxlen=int(WARMUP_SMOOTH_WINDOW * 60))
        self.warmup_all_attn = []
        self.normalization_lower = 0.0
        self.normalization_upper = 100.0

    def _print_mode_rules(self) -> None:
        logger.info("=" * 50)
        logger.info("疯狂奶茶杯 - %s（一杯制）", self.mode_name)
        logger.info("=" * 50)
        logger.info("热身阶段 %s 秒，收集注意力数据用于归一化", WARMUP_DURATION)
        logger.info("  热身结束后自动进入正式游戏")
        if self.bci_mode:
            logger.info("脑机接口模式规则：")
            logger.info("  共 %s 杯，每杯最多 %s 秒", self._mode_total_cups, CUP_DURATION)
            logger.info("  专注力越高食材越慢，持续高专注触发秘方翻倍")
            if not self.bci_available:
                logger.warning("  [警告] BCI设备未连接，无法读取数据")
        elif self.free_combine:
            logger.info("创意模式规则：")
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

    def _update_warmup_timer(self, dt_sec: float) -> None:
        self.warmup_elapsed += dt_sec
        if self.warmup_elapsed >= WARMUP_DURATION:
            self._transition_to_formal()

    def _get_warmup_smoothed_attn(self) -> float:
        if not self.warmup_attn_buffer:
            return 50.0
        return sum(self.warmup_attn_buffer) / len(self.warmup_attn_buffer)

    def _update_warmup_speed(self) -> None:
        smoothed = self._get_warmup_smoothed_attn()
        if smoothed < WARMUP_LOW_THRESHOLD:
            speed = WARMUP_SPEED_MAX
        elif smoothed < 47:
            speed = WARMUP_SPEED_MAX
        elif smoothed < 73:
            speed = (WARMUP_SPEED_MAX + WARMUP_SPEED_MIN) / 2.0
        else:
            speed = WARMUP_SPEED_MIN

        self.ingredient_manager.set_current_speed(speed)
        for ing in self.ingredients:
            ing.speed = speed

        speed_ratio = speed / self.mode_speed if self.mode_speed > 0 else 1.0
        adjusted = self.spawn_interval * (0.7 + 0.6 * speed_ratio)
        self.ingredient_manager.set_spawn_interval(max(0.3, min(3.0, adjusted)))

    def _check_warmup_freeze(self, dt_sec: float) -> None:
        if self.attention is None:
            return

        if self.attention <= 15:
            self.warmup_low_timer += dt_sec
            self.warmup_high_timer = 0.0
        elif self.attention >= 10:
            self.warmup_high_timer += dt_sec
            self.warmup_low_timer = 0.0
        else:
            self.warmup_low_timer = 0.0
            self.warmup_high_timer = 0.0

        if not self.warmup_paused and self.warmup_low_timer >= 5.0:
            self.warmup_paused = True
            self.warmup_low_timer = 0.0
            self.warmup_high_timer = 0.0
            logger.info("热身冻结：注意力连续 5 秒低于 15")
        elif self.warmup_paused and self.warmup_high_timer >= 5.0:
            self.warmup_paused = False
            self.warmup_low_timer = 0.0
            self.warmup_high_timer = 0.0
            self.ingredient_manager.reset_spawn_timer()
            logger.info("热身恢复：注意力连续 5 秒高于 15")

    def _transition_to_formal(self) -> None:
        warmup_last_30s_frames = int(30 * 60)
        last_30s = (
            self.warmup_all_attn[-warmup_last_30s_frames:]
            if len(self.warmup_all_attn) >= warmup_last_30s_frames
            else self.warmup_all_attn
        )
        if last_30s:
            max_attn = max(last_30s)
            avg_attn = sum(last_30s) / len(last_30s)
            self.warmup_summary_max = max_attn
            self.warmup_summary_avg = avg_attn
            self.normalization_lower = max(avg_attn - 10.0, 0.0)
            self.normalization_upper = min(max_attn, 100.0)
            if self.normalization_upper - self.normalization_lower < 10.0:
                mid = (self.normalization_upper + self.normalization_lower) / 2.0
                self.normalization_lower = max(mid - 5.0, 0.0)
                self.normalization_upper = min(mid + 5.0, 100.0)
        else:
            self.warmup_summary_max = 0.0
            self.warmup_summary_avg = 0.0
            self.normalization_lower = 30.0
            self.normalization_upper = 70.0

        logger.info(
            "热身阶段结束！最后30s 最高=%.1f 平均=%.1f  归一化范围: [%.1f, %.1f]",
            self.warmup_summary_max,
            self.warmup_summary_avg,
            self.normalization_lower,
            self.normalization_upper,
        )

        self.phase = "warmup_summary"
        self.warmup_summary_timer = 0.0
        self.ingredients.empty()
        self.catch_effects.empty()
        self.miss_effects.empty()
        self.particles.empty()

    def _do_transition_to_formal(self) -> None:
        self.phase = "formal"
        self.game_start_time = time_module.time()
        self.ingredients.empty()
        self.catch_effects.empty()
        self.miss_effects.empty()
        self.particles.empty()
        self.focus_samples = []
        self.cup_manager.start_new_cup()
        self.ingredient_manager.reset_spawn_timer()

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

    def _handle_collisions_warmup(self) -> None:
        threshold_y = self.cup.rect.top + self.cup.rect.height * 0.8
        hits = pygame.sprite.spritecollide(self.cup, self.ingredients, False)

        for hit in hits:
            if hit.rect.bottom > threshold_y:
                hit.rect.bottom = int(threshold_y)
                self.miss_effects.add(MissEffect(hit))
                color = INGREDIENT_COLORS.get(hit.type, (200, 200, 200))
                for _ in range(4):
                    p = Particle(hit.rect.centerx, int(threshold_y), color)
                    p.vx *= 0.4
                    p.vy *= 0.4
                    p.decay *= 1.5
                    self.particles.add(p)
                self.ingredients.remove(hit)
            else:
                self.ingredients.remove(hit)
                effect = CatchEffect(hit, self.cup.rect)
                self.catch_effects.add(effect)
                for _ in range(8):
                    color = INGREDIENT_COLORS.get(hit.type, (255, 200, 0))
                    self.particles.add(Particle(hit.rect.centerx, hit.rect.centery, color))
                self.cup.trigger_bounce()

        for ing in self.ingredients.sprites():
            if ing.rect.bottom > threshold_y:
                ing.rect.bottom = int(threshold_y)
                self.miss_effects.add(MissEffect(ing))
                color = INGREDIENT_COLORS.get(ing.type, (200, 200, 200))
                for _ in range(4):
                    p = Particle(ing.rect.centerx, int(threshold_y), color)
                    p.vx *= 0.4
                    p.vy *= 0.4
                    p.decay *= 1.5
                    self.particles.add(p)
                self.ingredients.remove(ing)

    def _update_pause_state(self, dt_sec: float) -> None:
        if self.attention is None:
            return
        if self.attention <= 15:
            self._low_attn_seconds += dt_sec
            self._high_attn_seconds = 0.0
        elif self.attention >= 10:
            self._high_attn_seconds += dt_sec
            self._low_attn_seconds = 0.0
        else:
            self._low_attn_seconds = 0.0
            self._high_attn_seconds = 0.0

        if not self._paused and self._low_attn_seconds >= 5.0:
            self._paused = True
        elif self._paused and self._high_attn_seconds >= 5.0:
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

            self._update_bci_data()

            if self.phase == "warmup_intro":
                self._update_cup(keys, dt_sec)
                self.warmup_intro_timer += dt_sec

                if self.warmup_intro_timer >= 2.0:
                    self.warmup_intro_alpha = max(0.0, self.warmup_intro_alpha - dt_sec * 420.0)

                    if self.warmup_intro_alpha <= 220.0 and self.attention is not None:
                        self.warmup_attn_buffer.append(self.attention)
                        self.warmup_all_attn.append(self.attention)

                    self._check_warmup_freeze(dt_sec)

                    if not self.warmup_paused:
                        self._update_warmup_timer(dt_sec)
                        self._update_warmup_speed()
                        self._update_game_objects(dt_sec)
                        self._handle_collisions_warmup()

                    if self.warmup_intro_alpha <= 0.0:
                        self.phase = "warmup"
                        self.warmup_intro_alpha = 0.0

            elif self.phase == "warmup_summary":
                self.warmup_summary_timer += dt_sec
                if self.warmup_summary_timer >= 3.0:
                    self._do_transition_to_formal()

            elif self.phase == "warmup":
                self._update_cup(keys, dt_sec)

                if self.attention is not None:
                    self.warmup_attn_buffer.append(self.attention)
                    self.warmup_all_attn.append(self.attention)

                self._check_warmup_freeze(dt_sec)

                if not self.warmup_paused:
                    self._update_warmup_timer(dt_sec)
                    self._update_warmup_speed()
                    self._update_game_objects(dt_sec)
                    self._handle_collisions_warmup()
            else:
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

            self._update_bci_data()

            self._render()

        return self._end_game()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.show_summary = True
                    self.running = False
                    return

    def _update_bci_data(self) -> None:
        if self.bci_available:
            result = self.bci_reader.read_with_timeout()
            if result[0] is not None:
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

    def _update_attention_variance(self) -> None:
        if self.attention is None:
            return
        baseline = self.warmup_summary_avg if self.warmup_summary_avg > 0 else 40.0
        offset = self.attention - baseline
        self._attn_offsets.append(offset)
        if len(self._attn_offsets) > 60:
            self._attn_offsets = self._attn_offsets[-60:]

        if len(self._attn_offsets) >= 5:
            mean = sum(self._attn_offsets) / len(self._attn_offsets)
            self._attn_variance = sum((x - mean) ** 2 for x in self._attn_offsets) / len(self._attn_offsets)

            if self._attn_variance < 50:
                self._attn_mode = "简单模式"
                prob = 0.7
            elif self._attn_variance < 150:
                self._attn_mode = "中等模式"
                prob = 0.5
            else:
                self._attn_mode = "困难模式"
                prob = 0.3

            self.ingredient_manager.set_required_probability(prob)

    def _update_cup(self, keys: pygame.key.ScancodeWrapper, dt_sec: float) -> None:
        self.cup.update(keys=keys, dt=dt_sec)
        kb_pressed = keys[pygame.K_LEFT] or keys[pygame.K_RIGHT]
        if not kb_pressed and self.use_yaw_control:
            fx = int(self.platform_focus_x)
            self.cup.rect.centerx = max(self.focus_min, min(self.focus_max, fx))

    def _check_secret_recipe(self, dt_sec: float) -> None:
        if self.cup_manager.secret_recipe_spawned:
            return
        if self.cup_manager.cup_ended:
            return

        if self.bci_mode:
            threshold = min(88.0, 40.0 + SECRET_RECIPE_OFFSET)
            attn = self.attention if self.attention is not None else 50.0
            if attn > threshold:
                self.focus_above_seconds += dt_sec
            else:
                self.focus_above_seconds = 0.0

            if self.focus_above_seconds >= SECRET_RECIPE_SUSTAIN and self.cup_manager.trigger_secret_recipe():
                allowed = self.ingredient_manager._free_lanes(self.ingredients)
                secret = self.ingredient_manager.spawn_secret_recipe(allowed)
                self.ingredients.add(secret)
                secret.set_particle_group(self.particles)
                self.focus_above_seconds = 0.0
                logger.info("秘方掉落！专注力持续高于阈值 %.0f 达 %d 秒", threshold, SECRET_RECIPE_SUSTAIN)
        else:
            if self.cup_manager.should_force_secret_recipe() and self.cup_manager.catch_count == 0:
                if self.cup_manager.trigger_secret_recipe():
                    allowed = self.ingredient_manager._free_lanes(self.ingredients)
                    secret = self.ingredient_manager.spawn_secret_recipe(allowed)
                    self.ingredients.add(secret)
                    secret.set_particle_group(self.particles)
                    logger.info("第 %s 杯触发秘方掉落！", self.cup_manager.cup_number)

    def _check_cup_end(self) -> None:
        if self.cup_manager.check_cup_end():
            cup_money = self.cup_manager.settle_cup()
            had_secret = self.cup_manager.secret_recipe_caught

            if self.bci_mode and cup_money > 0:
                attn = self.attention if self.attention is not None else 50.0
                norm = self._normalize_to_range(attn)
                coeff = get_attention_coefficient(norm)
                cup_money = int(cup_money * coeff)

            self.score_manager.add_cup_money(cup_money, had_secret)
            self.score_manager.reset_cup_ingredients()
            self.creative_ingredients = []
            self.recipe_result = None
            self.focus_above_seconds = 0.0

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

            cups_per_tier = max(1, self._mode_total_cups // 4)
            new_tier = min(4, (self.cup_manager.cup_number // cups_per_tier) + 1)
            if new_tier != self._current_tier:
                self._current_tier = new_tier
                self.ingredient_manager.set_tier(new_tier)
                logger.info("升级到等级 %s！新食材已解锁", new_tier)

            self.cup_manager.start_new_cup()
            self.cup.update_level(0)
            self.score_manager.reset_cup_ingredients()
            self.creative_ingredients = []
            self.recipe_result = None

    def _update_game_objects(self, dt_sec: float) -> None:
        ingredient = self.ingredient_manager.update(required_types=None, ingredients_group=self.ingredients)
        if ingredient:
            self.ingredients.add(ingredient)

        self.ingredients.update()
        self.catch_effects.update(dt=dt_sec)
        self.miss_effects.update(dt=dt_sec)
        self.particles.update(dt=dt_sec)

    def _handle_collisions(self) -> None:
        threshold_y = self.cup.rect.top + self.cup.rect.height * 0.8
        hits = pygame.sprite.spritecollide(self.cup, self.ingredients, False)

        self.creative_ingredients, self.recipe_result = _handle_catches(
            hits,
            self.cup,
            threshold_y,
            self.ingredients,
            self.miss_effects,
            self.catch_effects,
            self.particles,
            self.score_manager,
            self.cup_manager,
            self.free_combine,
            self.creative_ingredients,
            self.recipe_result,
        )

        _handle_misses(self.ingredients, threshold_y, self.miss_effects, self.particles)

    def _render(self) -> None:
        if self.has_background and self.background:
            self.screen.blit(self.background, (0, 0))
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 10, 90))
            self.screen.blit(overlay, (0, 0))
        else:
            self.screen.fill((255, 255, 255))

        self.all_sprites.draw(self.screen)
        self.ingredients.draw(self.screen)
        self.catch_effects.draw(self.screen)
        self.miss_effects.draw(self.screen)
        self.particles.draw(self.screen)

        if self.phase == "warmup_intro":
            self._render_warmup_intro()
        elif self.phase == "warmup" or self.phase == "warmup_summary":
            self._render_warmup_hud()
        else:
            self._render_formal_hud()

        pygame.display.flip()

    def _render_warmup_hud(self) -> None:
        self._draw_lane_lines()
        if self._top_bar:
            self.screen.blit(self._top_bar, (0, 0))
            mask = pygame.Surface((1280, 60), pygame.SRCALPHA)
            mask.fill((0, 0, 0, 60))
            self.screen.blit(mask, (0, 0))

        if self.phase == "warmup_summary":
            self._render_warmup_summary_overlay()
            return

        remaining = max(0.0, WARMUP_DURATION - self.warmup_elapsed)
        min_rem = int(remaining // 60)
        sec_rem = int(remaining % 60)
        timer_text = self.font.render(f"热身阶段 {min_rem:02d}:{sec_rem:02d}", True, (255, 255, 255))
        self.screen.blit(
            timer_text,
            (SCREEN_WIDTH // 2 - timer_text.get_width() // 2, 12),
        )

        attn_display = self.attention if self.attention is not None else 0
        attn_text = self.font.render(f"注意力: {int(attn_display)}", True, (255, 255, 255))
        attn_rect = attn_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
        self.screen.blit(attn_text, attn_rect)

        ctrl_text = "方向键 / 头环: 左右移动 | ESC: 返回" if self.bci_available else "方向键: 左右移动 | ESC: 返回"
        hint = self.hint_font.render(
            ctrl_text,
            True,
            (50, 50, 50),
        )
        self.screen.blit(hint, (10, SCREEN_HEIGHT - 40))

        bci_status_color = (0, 255, 0) if self.bci_available else (255, 100, 100)
        bci_status_text = self.hint_font.render(
            f"头环: {'已连接' if self.bci_available else '未连接'}",
            True,
            bci_status_color,
        )
        self.screen.blit(bci_status_text, (10, SCREEN_HEIGHT - 60))

        if self.warmup_paused:
            freeze_overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            freeze_overlay.fill((0, 0, 0, 180))
            self.screen.blit(freeze_overlay, (0, 0))

            freeze_text = self.pause_font.render("请调整身心状态", True, (255, 255, 255))
            self.screen.blit(
                freeze_text,
                (SCREEN_WIDTH // 2 - freeze_text.get_width() // 2, SCREEN_HEIGHT // 2 - 60),
            )
            resume_remain = max(0.0, 5.0 - self.warmup_high_timer)
            sub_text = self.hint_font.render(
                f"保持专注力 >10 持续 {resume_remain:.0f}s 恢复游戏",
                True,
                (200, 200, 200),
            )
            self.screen.blit(
                sub_text,
                (SCREEN_WIDTH // 2 - sub_text.get_width() // 2, SCREEN_HEIGHT // 2 + 20),
            )

    def _render_warmup_summary_overlay(self) -> None:
        mask = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        mask.fill((0, 0, 20, 200))
        self.screen.blit(mask, (0, 0))

        lines = [
            "热身阶段结束",
            "",
            f"最后30秒最高专注力: {self.warmup_summary_max:.0f}",
            f"最后30秒平均专注力: {self.warmup_summary_avg:.0f}",
        ]
        y_start = SCREEN_HEIGHT // 2 - 100
        for i, line in enumerate(lines):
            if line:
                text = self.font.render(line, True, (255, 255, 255))
                self.screen.blit(
                    text,
                    (SCREEN_WIDTH // 2 - text.get_width() // 2, y_start + i * 50),
                )

        countdown = max(0, int(3.0 - self.warmup_summary_timer) + 1)
        hint_text = self.hint_font.render(
            f"进入正式游戏... {countdown}s",
            True,
            (200, 200, 200),
        )
        self.screen.blit(
            hint_text,
            (SCREEN_WIDTH // 2 - hint_text.get_width() // 2, SCREEN_HEIGHT // 2 + 120),
        )

    def _draw_lane_lines(self) -> None:
        lane_overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        for i in range(1, NUM_LANES):
            x = i * LANE_WIDTH
            pygame.draw.line(lane_overlay, LANE_LINE_COLOR, (x, 60), (x, SCREEN_HEIGHT), 2)
        self.screen.blit(lane_overlay, (0, 0))

    def _render_warmup_intro(self) -> None:
        alpha = min(200, int(self.warmup_intro_alpha * 0.8))
        if alpha <= 0:
            return

        mask = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        mask.fill((0, 0, 20, alpha))
        self.screen.blit(mask, (0, 0))

        if self.warmup_intro_timer >= 2.0:
            return

        title = self.pause_font.render("热身阶段", True, (255, 255, 255))
        self.screen.blit(
            title,
            (SCREEN_WIDTH // 2 - title.get_width() // 2, SCREEN_HEIGHT // 2 - 80),
        )

        desc = self.font.render("请保持专注，接住掉落的小料", True, (200, 200, 200))
        self.screen.blit(
            desc,
            (SCREEN_WIDTH // 2 - desc.get_width() // 2, SCREEN_HEIGHT // 2),
        )

        countdown = max(0, int(2.0 - self.warmup_intro_timer) + 1)
        count_text = self.font.render(f"{countdown}", True, (255, 255, 255))
        self.screen.blit(
            count_text,
            (SCREEN_WIDTH // 2 - count_text.get_width() // 2, SCREEN_HEIGHT // 2 + 60),
        )

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
            recipe_font=self.recipe_font,
            attention=self.attention,
            bci_mode=self.bci_mode,
            free_combine=self.free_combine,
            recipe_result=self.recipe_result,
            creative_ingredients=self.creative_ingredients,
            attention_curve=self.attention_curve,
            bci_connected=self.bci_mode or self.bci_available,
            focus_above_seconds=self.focus_above_seconds,
            raw_gyro_x=self.raw_gyro_x,
            raw_gyro_y=self.raw_gyro_y,
            raw_gyro_z=self.raw_gyro_z,
            platform_focus_x=self.platform_focus_x,
            platform_focus_y=self.platform_focus_y,
            cup_x=self.cup.rect.centerx,
            cup_y=self.cup.rect.centery,
            rolling_attention=self.bci_reader.get_rolling_attention() if self.bci_mode else 0.0,
            attn_variance=self._attn_variance,
            attn_mode=self._attn_mode,
            attn_baseline=40.0,
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
                    f"保持专注力 >10 持续 {max(0, 5 - self._high_attn_seconds):.0f}s 恢复游戏",
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

    def _end_game(self) -> str:
        if self.show_summary:
            avg_focus = sum(self.focus_samples) / len(self.focus_samples) if self.focus_samples else 0.0
            if not self.bci_mode:
                avg_focus = 0.0

            if self._profile:
                old_level = self._profile.level
                game_duration = time_module.time() - self.game_start_time
                upgraded = self._profile.add_game_result(
                    revenue=self.score_manager.total_money,
                    mode=self.game_mode,
                    cups=self.score_manager.cup_count,
                    secrets=self.score_manager.secret_recipe_count,
                    avg_attention=avg_focus,
                    duration=game_duration,
                    focus_samples=self.focus_samples,
                )
                self._upgrade_level = old_level if upgraded else self._profile.level
                is_upgraded = upgraded > 0
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

        return "quit"


def run_game(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    game_mode: str = "regular",
    profile=None,
) -> str:
    session = GameSession(screen, clock, game_mode, profile)
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
    free_combine: bool,
    creative_ingredients: list[str],
    recipe_result: dict[str, Any] | None,
) -> tuple[list[str], dict[str, Any] | None]:
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

            if free_combine:
                creative_ingredients.append(hit.type)
                recipe_result = evaluate_recipe(creative_ingredients)

            cup.update_level(cup_manager.catch_count)
            logger.info("接住 %s！收益: %s", hit.type, score_manager.total_money)

    return creative_ingredients, recipe_result


def _handle_misses(
    ingredients: pygame.sprite.Group,
    threshold_y: float,
    miss_effects: pygame.sprite.Group,
    particles: pygame.sprite.Group,
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
