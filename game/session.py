"""游戏会话模块 - 管理单局游戏的初始化、循环和结算（一杯制改造）"""

from __future__ import annotations

import logging
import os
import time as time_module
from typing import Any

import pygame

from bci.data_reader import BCIDataReader
from bci.filter import (
    AttentionMappingCurve,
    AttentionToSpeedCurve,
)
from config import (
    BACKGROUND_IMG,
    CUP_DURATION,
    CUP_SPEED_MAX,
    CUP_SPEED_MIN,
    CUP_WIDTH,
    DEFAULT_GAME_MODE,
    DIFFICULTY_BASELINE,
    FOCUS_TEAPOT_IMG,
    GAME_MODES,
    INGREDIENT_COLORS,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TOTAL_CUPS,
)
from data.recipes import evaluate_recipe
from data.score_manager import ScoreManager
from game.cup_manager import CupManager, DifficultyAdapter
from game.font_utils import load_chinese_font
from game.hud import FocusTeapotUI, draw_hud
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
    difficulty_adapter: DifficultyAdapter | None
    attention_speed_curve: AttentionToSpeedCurve

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

    focus_teapot: FocusTeapotUI | None

    focus_min: int
    focus_max: int

    def __init__(
        self,
        screen: pygame.Surface,
        clock: pygame.time.Clock,
        game_mode: str = "regular",
        calibration: dict | None = None,
        profile=None,
    ) -> None:
        self.screen = screen
        self.clock = clock
        self.game_mode = game_mode
        self._calibration = calibration or {}
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

        self.attention_speed_curve = AttentionToSpeedCurve(
            speed_min=CUP_SPEED_MIN,
            speed_max=CUP_SPEED_MAX,
            baseline=DIFFICULTY_BASELINE,
        )
        self.difficulty_adapter = DifficultyAdapter() if self.bci_mode else None

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

    def _init_state(self) -> None:
        self.creative_ingredients = []
        self.recipe_result = None

        self.running = True
        self.show_summary = False
        self.use_yaw_control = self.bci_mode and self.bci_available
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

        self.focus_min = CUP_WIDTH // 2
        self.focus_max = SCREEN_WIDTH - CUP_WIDTH // 2

        teapot_img_path = FOCUS_TEAPOT_IMG if os.path.exists(FOCUS_TEAPOT_IMG) else None
        self.focus_teapot = None
        if teapot_img_path:
            self.focus_teapot = FocusTeapotUI(image_path=teapot_img_path, x=10, y=90, width=120, height=140)

        if self.bci_mode and not self.bci_available:
            logger.warning("BCI设备未连接，无法使用头动控制，将自动切换到键盘控制")
            self.use_yaw_control = False
            self.cup.yaw_control = False

        self.cup_manager.start_new_cup()
        self._current_tier = self._profile.level if self._profile else 1

        calib_baseline = self._calibration.get("baseline", DIFFICULTY_BASELINE)
        self.attention_speed_curve.set_baseline(calib_baseline)
        if self.difficulty_adapter:
            self.difficulty_adapter.baseline = calib_baseline

    def _print_mode_rules(self) -> None:
        logger.info("=" * 50)
        logger.info("疯狂奶茶杯 - %s（一杯制）", self.mode_name)
        logger.info("=" * 50)
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
        score_text = self.font.render(f"分数: {self.score_manager.score}", True, (0, 0, 0))
        self.screen.blit(score_text, (10, 10))
        mode_text = self.font.render(f"{self.mode_name}", True, (100, 50, 150))
        self.screen.blit(mode_text, (10, 50))
        pygame.display.flip()

    def run(self) -> str:
        while self.running:
            dt = self.clock.tick(60)
            keys = pygame.key.get_pressed()
            dt_sec = dt / 1000.0

            self._handle_events()
            if not self.running:
                break

            self._update_bci_data()
            self._update_attention_variance()
            self._update_cup(keys, dt_sec)
            self._update_ingredient_speed()
            self._update_difficulty(dt_sec)
            self._check_secret_recipe(dt_sec)
            self._check_cup_end()

            if not self.running:
                break

            self._update_game_objects(dt_sec)
            self._handle_collisions()
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
            self.attention = None

        if self.attention is not None:
            self.focus_samples.append(self.attention)

    def _normalize_attention(self, raw: float) -> float:
        norm_min = self._calibration.get("norm_min", 0.0)
        norm_max = self._calibration.get("norm_max", 100.0)
        if norm_max - norm_min < 1:
            return raw
        return max(0.0, min(100.0, (raw - norm_min) / (norm_max - norm_min) * 100.0))

    def _update_attention_variance(self) -> None:
        if self.attention is None or self._calibration is None:
            return
        baseline = self._calibration.get("baseline", 50.0)
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
        if self.use_yaw_control:
            fx = int(self.platform_focus_x)
            self.cup.rect.centerx = max(self.focus_min, min(self.focus_max, fx))
        else:
            self.cup.update(keys=keys, dt=dt_sec)

    def _update_ingredient_speed(self) -> None:
        if self.bci_mode and self.bci_available and self.attention is not None:
            normalized = self._normalize_attention(self.attention)
            speed = self.attention_speed_curve.get_speed(normalized)
            self.ingredient_manager.set_current_speed(speed)

            speed_ratio = speed / self.mode_speed if self.mode_speed > 0 else 1.0
            adjusted = self.spawn_interval * (0.7 + 0.6 * speed_ratio)
            self.ingredient_manager.set_spawn_interval(max(0.3, min(3.0, adjusted)))
        else:
            self.ingredient_manager.set_current_speed(self.mode_speed)
            self.ingredient_manager.set_spawn_interval(self.spawn_interval)

    def _update_difficulty(self, dt_sec: float) -> None:
        if self.difficulty_adapter is not None and self.attention is not None:
            normalized = self._normalize_attention(self.attention)
            baseline = self.difficulty_adapter.update(normalized, dt_sec)
            self.attention_speed_curve.set_baseline(baseline)

    def _check_secret_recipe(self, dt_sec: float) -> None:
        if self.cup_manager.secret_recipe_spawned:
            return
        if self.cup_manager.cup_ended:
            return

        if self.bci_mode and self.bci_available and self.attention is not None:
            threshold = self.difficulty_adapter.get_secret_threshold() if self.difficulty_adapter else 75.0
            if self.attention > threshold:
                self.focus_above_seconds += dt_sec
            else:
                self.focus_above_seconds = 0.0

            if self.focus_above_seconds >= 5.0 and self.cup_manager.trigger_secret_recipe():
                secret = self.ingredient_manager.spawn_secret_recipe()
                self.ingredients.add(secret)
                self.focus_above_seconds = 0.0
                logger.info("秘方掉落！专注力持续高于阈值 %.0f 达 5 秒", threshold)
        else:
            if self.cup_manager.should_force_secret_recipe() and self.cup_manager.catch_count == 0:
                if self.cup_manager.trigger_secret_recipe():
                    secret = self.ingredient_manager.spawn_secret_recipe()
                    self.ingredients.add(secret)
                    logger.info("第 %s 杯触发秘方掉落！", self.cup_manager.cup_number)

    def _check_cup_end(self) -> None:
        if self.cup_manager.check_cup_end():
            cup_money = self.cup_manager.settle_cup()
            had_secret = self.cup_manager.secret_recipe_caught
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
        ingredient = self.ingredient_manager.update(required_types=None)
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

        draw_hud(
            screen=self.screen,
            score_manager=self.score_manager,
            mode_name=self.mode_name,
            cup_manager=self.cup_manager,
            game_start_time=self.game_start_time,
            font=self.font,
            hint_font=self.hint_font,
            recipe_font=self.recipe_font,
            focus_teapot=self.focus_teapot,
            attention=self.attention,
            bci_mode=self.bci_mode,
            free_combine=self.free_combine,
            recipe_result=self.recipe_result,
            creative_ingredients=self.creative_ingredients,
            attention_curve=self.attention_curve,
            bci_connected=self.bci_available,
            difficulty_adapter=self.difficulty_adapter,
            focus_above_seconds=self.focus_above_seconds,
            raw_gyro_x=self.raw_gyro_x,
            raw_gyro_y=self.raw_gyro_y,
            raw_gyro_z=self.raw_gyro_z,
            platform_focus_x=self.platform_focus_x,
            platform_focus_y=self.platform_focus_y,
            cup_x=self.cup.rect.centerx,
            cup_y=self.cup.rect.centery,
            rolling_attention=self.bci_reader.get_rolling_attention() if self.bci_available else 0.0,
            attn_variance=self._attn_variance,
            attn_mode=self._attn_mode,
        )

        pygame.display.flip()

    def _end_game(self) -> str:
        if self.show_summary:
            avg_focus = sum(self.focus_samples) / len(self.focus_samples) if self.focus_samples else 0.0
            if not self.bci_mode:
                avg_focus = 0.0

            if self._profile:
                old_level = self._profile.level
                upgraded = self._profile.add_game_result(
                    revenue=self.score_manager.total_money,
                    mode=self.game_mode,
                    cups=self.score_manager.cup_count,
                    secrets=self.score_manager.secret_recipe_count,
                    avg_attention=avg_focus,
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
            )
            return summary.run()

        return "quit"


def run_game(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    game_mode: str = "regular",
    calibration: dict | None = None,
    profile=None,
) -> str:
    session = GameSession(screen, clock, game_mode, calibration, profile)
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
            logger.info("接住 %s！分数: %s", hit.type, score_manager.score)

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
