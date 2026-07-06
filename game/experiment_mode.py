"""实验模式游戏会话 - 3min热身原萃 + 7min特调 + 5min忆调"""

from __future__ import annotations

import logging
import math
import os
import random
import time as time_module
from typing import Any

import pygame

import config
from bci.data_reader import BCIDataReader
from config import (
    ARTIFACT_ATTENTION_THRESHOLD,
    ARTIFACT_PENALTY_DURATION,
    ARTIFACT_STILL_DURATION,
    ARTIFACT_STILL_THRESHOLD,
    BACKGROUND_IMG,
    BADGE_IMGS,
    CUP_WIDTH,
    DIGIT_HEIGHT,
    DIGIT_SPACING,
    DIGIT_WIDTH,
    EXPERIMENT_FORMAL_DURATION,
    EXPERIMENT_WARMUP_DURATION,
    EXPERIMENT_WARMUP_NORM_WINDOW,
    EXPERIMENT_WARMUP_NOTICE_DURATION,
    EXPERIMENT_WARMUP_SPEED_MAX,
    EXPERIMENT_WARMUP_SPEED_MIN,
    FOCUS_BALL_IMG,
    FOCUS_BALL_POS,
    FOCUS_BALL_SIZE,
    FORMAL_SPEED_MAX,
    FORMAL_SPEED_MIN,
    GAME_MODES,
    INFO_BAR_HEIGHT,
    INFO_BAR_IMG,
    INFO_BADGE_POS,
    INFO_BADGE_SIZE,
    INFO_FONT_SIZE,
    INFO_REGIONS,
    INGREDIENT_COLORS,
    INGREDIENT_IMGS,
    INGREDIENT_TIERS,
    NUM_IMG_DIR,
    OUTLET_POSITIONS,
    OVERLAY_CLEAR_REGIONS,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SECRET_RECIPE_SUSTAIN,
    WARMUP_FREEZE_TIME,
    WARMUP_LOW_THRESHOLD,
    WARMUP_RESUME_TIME,
    get_attention_coefficient,
)
from data.score_manager import ScoreManager
from game.cup_manager import CupManager
from game.font_utils import load_chinese_font
from game.ingredient_manager import IngredientManager
from game.sprites import CatchEffect, Cup, Ingredient, MissEffect, Particle

logger = logging.getLogger(__name__)


class ExperimentSession:
    def __init__(
        self,
        screen: pygame.Surface,
        clock: pygame.time.Clock,
        profile=None,
        control_mode: str = "bci",
        audio=None,
    ) -> None:
        self.screen = screen
        self.clock = clock
        self._profile = profile
        self._control_mode = control_mode
        self._audio = audio

        self.game_mode = "experiment"
        self._load_mode_config()
        self._load_fonts()
        self._init_game_objects()
        self._init_bci()
        self._load_background()
        self._init_state()
        self._draw_initial_frame()

    def _load_mode_config(self) -> None:
        mode_config = GAME_MODES.get(self.game_mode, GAME_MODES["bci"])
        self.mode_name = mode_config["name"]
        self.has_required = mode_config["has_required"]
        self.free_combine = mode_config["free_combine"]
        self.bci_mode = mode_config["bci_mode"]
        self.spawn_interval = mode_config["spawn_interval"] / 1000.0
        self.mode_speed = float(mode_config["ingredient_speed"])
        self._mode_total_cups = mode_config.get("total_cups", 45)
        self._mode_secret_interval = mode_config.get("secret_recipe_cup_interval", 3)
        self._raw_attention = True

        if self._control_mode in ("bci", "bci_failed"):
            self.mode_name = "实验模式"

    def _load_fonts(self) -> None:
        self.font = load_chinese_font(36)
        self.hint_font = load_chinese_font(20)
        self.pause_font = load_chinese_font(48)
        self.phase_font = load_chinese_font(32)

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

        tier_required = INGREDIENT_TIERS.get(start_tier, INGREDIENT_TIERS[1]).get("required", ["红茶"])
        first_required = tier_required[0] if tier_required else "红茶"
        self.score_manager.set_required_ingredient(first_required)

        self.cup_manager = CupManager(
            has_required=True,
            required_type=first_required,
            total_cups=999,
            secret_recipe_interval=self._mode_secret_interval,
        )
        self._current_tier = 1

    def _init_bci(self) -> None:
        self.bci_reader = BCIDataReader()
        self.bci_available = False
        if self.bci_mode and self._control_mode != "bci_failed":
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

        self._info_bar = None
        if os.path.exists(INFO_BAR_IMG):
            try:
                self._info_bar = pygame.image.load(INFO_BAR_IMG).convert_alpha()
                self._info_bar = pygame.transform.smoothscale(self._info_bar, (SCREEN_WIDTH, INFO_BAR_HEIGHT))
            except Exception:
                pass

        self._badge_img = None
        level = self._profile.level if self._profile else 1
        idx = max(0, min(level - 1, len(BADGE_IMGS) - 1))
        badge_path = BADGE_IMGS[idx]
        if os.path.exists(badge_path):
            try:
                self._badge_img = pygame.image.load(badge_path).convert_alpha()
                self._badge_img = pygame.transform.smoothscale(self._badge_img, INFO_BADGE_SIZE)
            except Exception:
                pass

        self._focus_ball = None
        if os.path.exists(FOCUS_BALL_IMG):
            try:
                self._focus_ball = pygame.image.load(FOCUS_BALL_IMG).convert_alpha()
                self._focus_ball = pygame.transform.smoothscale(self._focus_ball, FOCUS_BALL_SIZE)
            except Exception:
                pass

        self._digit_imgs: list[pygame.Surface] = []
        for i in range(10):
            path = os.path.join(NUM_IMG_DIR, f"{i}.png")
            try:
                img = pygame.image.load(path).convert_alpha()
                img = pygame.transform.smoothscale(img, (DIGIT_WIDTH, DIGIT_HEIGHT))
                self._digit_imgs.append(img)
            except Exception:
                self._digit_imgs.append(pygame.Surface((DIGIT_WIDTH, DIGIT_HEIGHT), pygame.SRCALPHA))

        self._secret_img = None
        img_path = INGREDIENT_IMGS.get("秘方", "")
        if img_path and os.path.exists(img_path):
            img = pygame.image.load(img_path).convert_alpha()
            self._secret_img = pygame.transform.scale(img, (160, 160))

    def _init_state(self) -> None:
        self.running = True
        self.phase = "warmup"
        self.phase_start_time = 0.0
        self.use_yaw_control = self.bci_available
        self.cup.yaw_control = self.use_yaw_control

        self.attention = None
        self.raw_gyro_x = 0.0
        self.raw_gyro_y = 0.0
        self.raw_gyro_z = 0.0
        self.platform_focus_x = float(SCREEN_WIDTH // 2)
        self.platform_focus_y = float(SCREEN_HEIGHT - 100)

        self.focus_min = CUP_WIDTH // 2
        self.focus_max = SCREEN_WIDTH - CUP_WIDTH // 2

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

        self._warmup_samples: list[tuple[float, float]] = []
        self._warmup_baseline: float = 50.0
        self._warmup_norm_max: float = 80.0
        self._warmup_norm_min: float = 20.0

        self._notice_timer = EXPERIMENT_WARMUP_NOTICE_DURATION
        self._show_notice = True
        self._game_active = False
        self._secret_popup_timer = 0.0
        self._focus_above_seconds = 0.0
        self._cup_attn_samples: list[float] = []
        self._cup_baseline: float = 40.0
        self._warmup_cup_start = 0.0

        self.normalization_lower = 30.0
        self.normalization_upper = 70.0
        self.phase_formal_start = 0.0

        self._esc_dialog_active = False
        self._esc_dialog_selected = 0
        self._pause_accumulated = 0.0
        self._pause_start = 0.0

        self._player_level = self._profile.level if self._profile else 1

        if not self.bci_available and self.bci_mode:
            logger.warning("BCI设备未连接，无法使用头动控制，将自动切换到键盘控制")
            self.use_yaw_control = False
            self.cup.yaw_control = False

        self._current_tier = self._profile.level if self._profile else 1

    def _draw_initial_frame(self) -> None:
        if self.has_background and self.background:
            self.screen.blit(self.background, (0, 0))
        else:
            self.screen.fill((255, 255, 255))
        self.all_sprites.draw(self.screen)
        mode_text = self.font.render(f"{self.mode_name}", True, (100, 50, 150))
        self.screen.blit(mode_text, (10, 10))
        pygame.display.flip()

    @property
    def _game_frozen(self) -> bool:
        return self._paused or self._artifact_frozen

    def _update_warmup_speed(self) -> None:
        if self.bci_mode:
            attn = self.attention if self.attention is not None else 50.0
            speed = EXPERIMENT_WARMUP_SPEED_MAX - (attn / 100.0) * (
                EXPERIMENT_WARMUP_SPEED_MAX - EXPERIMENT_WARMUP_SPEED_MIN
            )
        else:
            speed = self.mode_speed

        base_speed = speed
        self.ingredient_manager.set_current_speed(speed)
        for ing in self.ingredients:
            ing.speed = speed

        if self.bci_mode:
            speed_ratio = base_speed / self.mode_speed if self.mode_speed > 0 else 1.0
            adjusted = self.spawn_interval * (0.7 + 0.6 * speed_ratio)
            self.ingredient_manager.set_spawn_interval(max(0.3, min(3.0, adjusted)))
        else:
            self.ingredient_manager.set_spawn_interval(self.spawn_interval)

    def _update_bci_data(self) -> None:
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

        if self.attention is not None and self._game_active:
            now = time_module.time()
            self._warmup_samples.append((now, self.attention))
            self._cup_attn_samples.append(self.attention)

    def _update_cup(self, keys: pygame.key.ScancodeWrapper, dt_sec: float) -> None:
        self.cup.update(keys=keys, dt=dt_sec)
        kb_pressed = keys[pygame.K_LEFT] or keys[pygame.K_RIGHT]
        if not kb_pressed and self.use_yaw_control and self.bci_available:
            fx = int(self.platform_focus_x)
            self.cup.rect.centerx = max(self.focus_min, min(self.focus_max, fx))

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
        if self._artifact_frozen or not self.bci_mode or not self.bci_available:
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

    def _check_warmup_secret_recipe(self, dt_sec: float) -> None:
        if self._secret_popup_timer > 0:
            return
        if self.cup_manager.secret_recipe_spawned:
            return
        if self.cup_manager.cup_ended:
            return

        if self.bci_mode and self.bci_available:
            threshold = self._cup_baseline + 10
            attn = self.attention if self.attention is not None else 50.0
            if attn > threshold:
                self._focus_above_seconds += dt_sec
            else:
                self._focus_above_seconds = 0.0

            if self._focus_above_seconds >= SECRET_RECIPE_SUSTAIN and self.cup_manager.trigger_secret_recipe():
                self._secret_popup_timer = 4.0
                self._focus_above_seconds = 0.0
                if self._audio:
                    self._audio.play_sfx("音效/触发秘方.wav", volume=0.7)
                logger.info("热身秘方触发！专注力持续高于阈值 %.0f 达 %d 秒", threshold, SECRET_RECIPE_SUSTAIN)

    def _draw_secret_popup(self) -> None:
        timer = self._secret_popup_timer
        if timer > 3.5:
            alpha = (4.0 - timer) / 0.5
        elif timer < 0.5:
            alpha = timer / 0.5
        else:
            alpha = 1.0
        alpha = max(0.0, min(1.0, alpha))

        overlay_alpha = int(80 * alpha)
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, overlay_alpha))
        self.screen.blit(overlay, (0, 0))

        popup_w, popup_h = 260, 270
        popup_x = (SCREEN_WIDTH - popup_w) // 2
        popup_y = (SCREEN_HEIGHT - popup_h) // 2

        popup_surf = pygame.Surface((popup_w, popup_h), pygame.SRCALPHA)
        bg_alpha = int(200 * alpha)
        border_alpha = int(180 * alpha)
        pygame.draw.rect(popup_surf, (30, 25, 20, bg_alpha), (0, 0, popup_w, popup_h), border_radius=16)
        pygame.draw.rect(popup_surf, (255, 180, 100, border_alpha), (0, 0, popup_w, popup_h), 3, border_radius=16)
        self.screen.blit(popup_surf, (popup_x, popup_y))

        text_surf = self.font.render("触发秘方！", True, (255, 220, 100))
        text_surf.set_alpha(int(255 * alpha))
        text_x = popup_x + (popup_w - text_surf.get_width()) // 2
        text_y = popup_y + popup_h - text_surf.get_height() - 20
        self.screen.blit(text_surf, (text_x, text_y))

        if self._secret_img is not None:
            t = pygame.time.get_ticks() / 1000.0
            wobble_x = int(math.sin(t * 4) * 5)
            angle = math.sin(t * 3) * 2
            rotated = pygame.transform.rotate(self._secret_img, angle)
            rotated.set_alpha(int(255 * alpha))
            rx = popup_x + (popup_w - rotated.get_width()) // 2 + wobble_x
            ry = popup_y + 25
            self.screen.blit(rotated, (rx, ry))

    def _finish_warmup(self) -> None:
        if not self._warmup_samples:
            self._warmup_baseline = 50.0
            self._warmup_norm_max = 80.0
            self._warmup_norm_min = 20.0
            logger.info("热身结束：无专注力数据，使用默认归一化参数")
            return

        all_values = [v for _, v in self._warmup_samples]
        self._warmup_baseline = sum(all_values) / len(all_values)

        last_time = self._warmup_samples[-1][0]
        cutoff_time = last_time - EXPERIMENT_WARMUP_NORM_WINDOW
        last_30s = [v for t, v in self._warmup_samples if t >= cutoff_time]

        if last_30s:
            self._warmup_norm_max = max(last_30s)
            self._warmup_norm_min = min(last_30s)
            if self._warmup_norm_max - self._warmup_norm_min < 5.0:
                mid = (self._warmup_norm_max + self._warmup_norm_min) / 2.0
                self._warmup_norm_max = min(mid + 10.0, 100.0)
                self._warmup_norm_min = max(mid - 10.0, 0.0)
        else:
            self._warmup_norm_max = max(all_values)
            self._warmup_norm_min = min(all_values)

        logger.info(
            "热身结束！基线=%.1f  归一化范围: [%.1f, %.1f]  (最后30s内最高=%.1f 最低=%.1f)",
            self._warmup_baseline,
            self._warmup_norm_min,
            self._warmup_norm_max,
            self._warmup_norm_max,
            self._warmup_norm_min,
        )

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
        else:
            speed = self.mode_speed

        base_speed = speed
        self.ingredient_manager.set_current_speed(speed)
        for ing in self.ingredients:
            ing.speed = speed

        if self.bci_mode:
            speed_ratio = base_speed / self.mode_speed if self.mode_speed > 0 else 1.0
            adjusted = self.spawn_interval * (0.7 + 0.6 * speed_ratio)
            self.ingredient_manager.set_spawn_interval(max(0.3, min(3.0, adjusted)))
        else:
            self.ingredient_manager.set_spawn_interval(self.spawn_interval)

    def _check_formal_secret_recipe(self, dt_sec: float) -> None:
        if self._secret_popup_timer > 0:
            return
        if self.cup_manager.secret_recipe_spawned:
            return
        if self.cup_manager.cup_ended:
            return

        if self.bci_mode and self.bci_available:
            threshold = self._warmup_baseline + 10
            attn = self.attention if self.attention is not None else 50.0
            if attn > threshold:
                self._focus_above_seconds += dt_sec
            else:
                self._focus_above_seconds = 0.0

            if self._focus_above_seconds >= SECRET_RECIPE_SUSTAIN and self.cup_manager.trigger_secret_recipe():
                self._secret_popup_timer = 4.0
                self._focus_above_seconds = 0.0
                if self._audio:
                    self._audio.play_sfx("音效/触发秘方.wav", volume=0.7)
                logger.info("特调秘方触发！专注力持续高于阈值 %.0f 达 %d 秒", threshold, SECRET_RECIPE_SUSTAIN)

    def _check_cup_end(self) -> None:
        if self.cup_manager.check_cup_end():
            if self._cup_attn_samples:
                self._cup_baseline = sum(self._cup_attn_samples) / len(self._cup_attn_samples)

            self._cup_attn_samples = []

            cup_money = self.cup_manager.settle_cup()
            had_secret = self.cup_manager.secret_recipe_spawned
            required_caught = self.cup_manager.cup_required_caught

            if cup_money > 0 and required_caught:
                if self.bci_mode:
                    attn = self.attention if self.attention is not None else 50.0
                    if self.phase == "warmup":
                        coeff = get_attention_coefficient(attn)
                    else:
                        norm = self._normalize_to_range(attn)
                        coeff = get_attention_coefficient(norm)
                    cup_money = int(cup_money * coeff)

                self.score_manager.add_cup_money(cup_money, had_secret)
                if self._audio:
                    self._audio.play_sfx("音效/加金币.wav", volume=0.5)

            self.score_manager.reset_cup_ingredients()
            self._focus_above_seconds = 0.0

            self.cup_manager.start_new_cup()
            self.cup.update_level(0)
            self.score_manager.reset_cup_ingredients()

    def _draw_focus_ball(self) -> None:
        if self._focus_ball is None or not self._digit_imgs:
            return

        bx, by = FOCUS_BALL_POS
        bw, bh = FOCUS_BALL_SIZE
        self.screen.blit(self._focus_ball, (bx - bw // 2, by - bh // 2))

        val = int(self.attention) if self.attention is not None else 0
        if self.bci_available:
            s = f"{min(val, 99):02d}"
            total_w = len(s) * DIGIT_WIDTH + (len(s) - 1) * DIGIT_SPACING
            start_x = bx - total_w // 2
            digit_y = by - DIGIT_HEIGHT // 2
            for ch in s:
                idx = ord(ch) - 48
                if 0 <= idx < len(self._digit_imgs):
                    self.screen.blit(self._digit_imgs[idx], (start_x, digit_y))
                start_x += DIGIT_WIDTH + DIGIT_SPACING

    def _draw_badge(self) -> None:
        if self._badge_img is None:
            return
        bx, by = INFO_BADGE_POS
        bw, bh = INFO_BADGE_SIZE
        self.screen.blit(self._badge_img, (bx - bw // 2, by - bh // 2))

    def _draw_info_labels(self) -> None:
        info_font = load_chinese_font(INFO_FONT_SIZE)
        values = [
            f"LV.{self._player_level}",
            self.mode_name,
            str(self.score_manager.cup_count),
            str(self.score_manager.total_money),
        ]
        texts = [
            (cx, cy, info_font.render(v, True, (255, 255, 255)), info_font.render(v, True, (30, 15, 5)))
            for (cx, cy), v in zip(INFO_REGIONS, values)
        ]
        for cx, cy, txt, shadow in texts:
            tw, th = txt.get_size()
            x = cx - tw // 2
            y = cy - th // 2
            self.screen.blit(shadow, (x + 1, y + 1))
            self.screen.blit(txt, (x, y))

    def _draw_warmup_notice(self) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        alpha = int(min(self._notice_timer / 0.5, 1.0) * 160)
        overlay.fill((0, 0, 0, alpha))
        self.screen.blit(overlay, (0, 0))

        notice_surf = pygame.Surface((500, 160), pygame.SRCALPHA)
        pygame.draw.rect(notice_surf, (30, 25, 20, 220), (0, 0, 500, 160), border_radius=16)
        pygame.draw.rect(notice_surf, (220, 140, 255, 200), (0, 0, 500, 160), 3, border_radius=16)

        title = self.phase_font.render("热身阶段 - 原萃模式", True, (255, 200, 100))
        sub = self.hint_font.render("请保持专注，数据将用于后续阶段校准", True, (200, 200, 200))
        sub2 = self.hint_font.render(f"倒计时 3 分钟", True, (180, 180, 180))

        nx = 500 // 2 - title.get_width() // 2
        notice_surf.blit(title, (nx, 30))
        sx = 500 // 2 - sub.get_width() // 2
        notice_surf.blit(sub, (sx, 75))
        sx2 = 500 // 2 - sub2.get_width() // 2
        notice_surf.blit(sub2, (sx2, 105))

        bx = SCREEN_WIDTH // 2 - 250
        by = SCREEN_HEIGHT // 2 - 80
        self.screen.blit(notice_surf, (bx, by))

    def _draw_phase_transition(self, text: str) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        box_surf = pygame.Surface((500, 120), pygame.SRCALPHA)
        pygame.draw.rect(box_surf, (30, 25, 20, 220), (0, 0, 500, 120), border_radius=16)
        pygame.draw.rect(box_surf, (220, 140, 255, 200), (0, 0, 500, 120), 3, border_radius=16)

        title = self.phase_font.render(text, True, (255, 200, 100))
        sub = self.hint_font.render("热身阶段已结束，进入下一阶段", True, (200, 200, 200))

        nx = 500 // 2 - title.get_width() // 2
        box_surf.blit(title, (nx, 25))
        sx = 500 // 2 - sub.get_width() // 2
        box_surf.blit(sub, (sx, 70))

        bx = SCREEN_WIDTH // 2 - 250
        by = SCREEN_HEIGHT // 2 - 60
        self.screen.blit(box_surf, (bx, by))

    def _draw_phase_label(self) -> None:
        if self.phase == "warmup" or self.phase == "transition":
            label = "热身阶段"
        elif self.phase == "formal":
            label = "特调阶段"
        else:
            label = self.mode_name
        label_surf = self.phase_font.render(label, True, (200, 150, 255))
        shadow = self.phase_font.render(label, True, (30, 20, 10))

        x = SCREEN_WIDTH - label_surf.get_width() - 30
        y = SCREEN_HEIGHT - label_surf.get_height() - 45
        self.screen.blit(shadow, (x + 2, y + 2))
        self.screen.blit(label_surf, (x, y))

    @property
    def _total_pause(self) -> float:
        if self._esc_dialog_active:
            return self._pause_accumulated + time_module.time() - self._pause_start
        return self._pause_accumulated

    def _draw_phase_countdown(self) -> None:
        if self.phase == "warmup" or self.phase == "transition":
            if not self._game_active:
                countdown_text = "热身 3:00"
            else:
                elapsed = time_module.time() - self.phase_start_time - self._total_pause
                remaining = max(0, EXPERIMENT_WARMUP_DURATION - elapsed)
                mins = int(remaining // 60)
                secs = int(remaining % 60)
                countdown_text = f"热身 {mins}:{secs:02d}"
        elif self.phase == "formal":
            elapsed = time_module.time() - self.phase_formal_start - self._total_pause
            remaining = max(0, EXPERIMENT_FORMAL_DURATION - elapsed)
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            countdown_text = f"特调 {mins}:{secs:02d}"
        else:
            return

        cd_surf = self.phase_font.render(countdown_text, True, (255, 200, 100))
        shadow = self.phase_font.render(countdown_text, True, (30, 20, 10))

        x = SCREEN_WIDTH - cd_surf.get_width() - 30
        y = SCREEN_HEIGHT - cd_surf.get_height() - 15
        self.screen.blit(shadow, (x + 2, y + 2))
        self.screen.blit(cd_surf, (x, y))

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
                    if event.key in (pygame.K_LEFT, pygame.K_UP):
                        self._esc_dialog_selected = (self._esc_dialog_selected - 1) % 2
                    elif event.key in (pygame.K_RIGHT, pygame.K_DOWN, pygame.K_TAB):
                        self._esc_dialog_selected = (self._esc_dialog_selected + 1) % 2
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
        self._pause_start = time_module.time()

    def _commit_esc_dialog(self) -> None:
        if self._esc_dialog_selected == 0:
            self._esc_dialog_active = False
            self._pause_accumulated += time_module.time() - self._pause_start
        else:
            self.running = False

    def _handle_esc_dialog_click(self, pos: tuple[int, int]) -> None:
        if hasattr(self, "_esc_continue_rect") and self._esc_continue_rect.collidepoint(pos):
            self._esc_dialog_active = False
            self._pause_accumulated += time_module.time() - self._pause_start
        elif hasattr(self, "_esc_exit_rect") and self._esc_exit_rect.collidepoint(pos):
            self.running = False

    def _draw_esc_dialog(self) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        box_w, box_h = 380, 220
        box_x = (SCREEN_WIDTH - box_w) // 2
        box_y = (SCREEN_HEIGHT - box_h) // 2
        box_rect = pygame.Rect(box_x, box_y, box_w, box_h)
        pygame.draw.rect(self.screen, (30, 28, 20), box_rect, border_radius=16)
        pygame.draw.rect(self.screen, (200, 160, 100), box_rect, 3, border_radius=16)

        title = self.pause_font.render("暂停", True, (255, 255, 255))
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, box_y + 25))

        btn_w, btn_h = 150, 48
        btn_y = box_y + 90
        gap = 20
        left_x = SCREEN_WIDTH // 2 - btn_w - gap // 2
        right_x = SCREEN_WIDTH // 2 + gap // 2

        continue_selected = self._esc_dialog_selected == 0
        exit_selected = self._esc_dialog_selected == 1

        selected_border = (255, 255, 255)
        normal_border = (100, 100, 100)

        self._esc_continue_rect = pygame.Rect(left_x, btn_y, btn_w, btn_h)
        continue_border = selected_border if continue_selected else normal_border
        pygame.draw.rect(self.screen, (80, 180, 80), self._esc_continue_rect, border_radius=10)
        pygame.draw.rect(self.screen, continue_border, self._esc_continue_rect, 3, border_radius=10)
        continue_text = self.font.render("继续热身", True, (255, 255, 255))
        self.screen.blit(
            continue_text,
            (
                self._esc_continue_rect.centerx - continue_text.get_width() // 2,
                self._esc_continue_rect.centery - continue_text.get_height() // 2,
            ),
        )

        self._esc_exit_rect = pygame.Rect(right_x, btn_y, btn_w, btn_h)
        exit_border = selected_border if exit_selected else normal_border
        pygame.draw.rect(self.screen, (200, 60, 60), self._esc_exit_rect, border_radius=10)
        pygame.draw.rect(self.screen, exit_border, self._esc_exit_rect, 3, border_radius=10)
        exit_text = self.font.render("退出", True, (255, 255, 255))
        self.screen.blit(
            exit_text,
            (
                self._esc_exit_rect.centerx - exit_text.get_width() // 2,
                self._esc_exit_rect.centery - exit_text.get_height() // 2,
            ),
        )

        sub_text = self.hint_font.render("ESC 关闭对话框", True, (180, 180, 180))
        self.screen.blit(
            sub_text,
            (SCREEN_WIDTH // 2 - sub_text.get_width() // 2, box_y + box_h - 30),
        )

    def _render(self) -> None:
        if self.has_background and self.background:
            self.screen.blit(self.background, (0, 0))
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 10, config.BACKGROUND_OVERLAY_ALPHA))
            for rx, ry, rw, rh in OVERLAY_CLEAR_REGIONS:
                overlay.fill((0, 0, 0, 0), pygame.Rect(rx, ry, rw, rh))
            self.screen.blit(overlay, (0, 0))
        else:
            self.screen.fill((255, 255, 255))

        self.all_sprites.draw(self.screen)
        self.particles.draw(self.screen)
        self.ingredients.draw(self.screen)
        self.catch_effects.draw(self.screen)
        self.miss_effects.draw(self.screen)

        if config.SHOW_HUD_INFO and self._info_bar:
            self.screen.blit(self._info_bar, (0, 0))
            self._draw_badge()
            self._draw_info_labels()

        if config.SHOW_FOCUS_BALL:
            self._draw_focus_ball()

        if self.bci_mode:
            bci_status_color = (0, 255, 0) if self.bci_available else (255, 100, 100)
            bci_status_text = self.hint_font.render(
                f"头环: {'已连接' if self.bci_available else '未连接'}",
                True,
                bci_status_color,
            )
            self.screen.blit(bci_status_text, (10, SCREEN_HEIGHT - 30))

        self._draw_phase_label()
        self._draw_phase_countdown()

        if self._show_notice:
            if self._notice_timer > 0:
                self._draw_warmup_notice()
            else:
                self._show_notice = False

        if self._blackout_alpha > 1:
            blk = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            blk.fill((0, 0, 0, int(self._blackout_alpha)))
            self.screen.blit(blk, (0, 0))

            if self._paused:
                pause_text = self.pause_font.render("请调整身心状态", True, (255, 255, 255))
                self.screen.blit(
                    pause_text,
                    (SCREEN_WIDTH // 2 - pause_text.get_width() // 2, SCREEN_HEIGHT // 2 - 60),
                )
                sub_text = self.hint_font.render(
                    f"保持专注力 >15 持续 {max(0, int(WARMUP_RESUME_TIME) - self._high_attn_seconds):.0f}s 恢复",
                    True,
                    (200, 200, 200),
                )
                self.screen.blit(
                    sub_text,
                    (SCREEN_WIDTH // 2 - sub_text.get_width() // 2, SCREEN_HEIGHT // 2 + 20),
                )

        if self._artifact_alpha > 1:
            blk = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            blk.fill((0, 0, 0, int(self._artifact_alpha)))
            self.screen.blit(blk, (0, 0))

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

        if self._esc_dialog_active:
            self._draw_esc_dialog()

        if self._secret_popup_timer > 0:
            self._draw_secret_popup()

        if self.phase == "transition":
            self._draw_phase_transition("热身结束 - 准备进入特调阶段")
            sub = self.hint_font.render(
                f"基线: {self._warmup_baseline:.0f}  归一化: [{self._warmup_norm_min:.0f}, {self._warmup_norm_max:.0f}]",
                True,
                (180, 180, 180),
            )
            self.screen.blit(sub, (SCREEN_WIDTH // 2 - sub.get_width() // 2, SCREEN_HEIGHT // 2 + 40))

        if self.phase == "transition_memory":
            self._draw_phase_transition("特调结束 - 准备进入忆调阶段")
            sub = self.hint_font.render(
                f"累计成功杯数: {self.score_manager.cup_count}  收益: {self.score_manager.total_money}",
                True,
                (180, 180, 180),
            )
            self.screen.blit(sub, (SCREEN_WIDTH // 2 - sub.get_width() // 2, SCREEN_HEIGHT // 2 + 40))

        pygame.display.flip()

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
                self._render()
                continue

            self._update_bci_data()

            if self.phase == "warmup" and self._game_active and keys[pygame.K_o]:
                self._finish_warmup()
                self.normalization_lower = self._warmup_norm_min
                self.normalization_upper = self._warmup_norm_max
                self.phase = "transition"
                self._transition_start = time_module.time()
                self._pause_accumulated = 0.0
                logger.info("热身阶段被手动跳过（按O）")
                self._render()
                continue

            if not self._game_active:
                self._notice_timer -= dt_sec
                if self._notice_timer <= 0:
                    self._game_active = True
                    self._show_notice = False
                    self.phase_start_time = time_module.time()
                    self._pause_accumulated = 0.0
                    self.cup_manager.start_new_cup()
                    self._warmup_cup_start = time_module.time()
                    logger.info("热身阶段正式开始，计时开始")
                self._render()
                continue

            self._update_cup(keys, dt_sec)
            self._update_pause_state(dt_sec)
            self._check_artifact(dt_sec)
            self._update_artifact_freeze(dt_sec)

            if not self._game_frozen:
                if self.phase == "warmup":
                    self._update_warmup_speed()
                elif self.phase == "formal":
                    self._update_formal_speed()

                if self.phase == "warmup":
                    self._check_warmup_secret_recipe(dt_sec)
                elif self.phase == "formal":
                    self._check_formal_secret_recipe(dt_sec)

                self._check_cup_end()

                if self._secret_popup_timer <= 0 and self.phase not in ("transition", "transition_memory"):
                    self._update_game_objects(dt_sec)
                    self._handle_collisions()

            if self._secret_popup_timer > 0:
                self._secret_popup_timer -= dt_sec

            if self.phase == "warmup":
                elapsed = time_module.time() - self.phase_start_time - self._total_pause
                if elapsed >= EXPERIMENT_WARMUP_DURATION:
                    self._finish_warmup()
                    self.normalization_lower = self._warmup_norm_min
                    self.normalization_upper = self._warmup_norm_max
                    self.phase = "transition"
                    self._transition_start = time_module.time()
                    self._pause_accumulated = 0.0

            if self.phase == "transition":
                if time_module.time() - self._transition_start >= 2.0:
                    self.phase = "formal"
                    self.phase_formal_start = time_module.time()
                    self._pause_accumulated = 0.0
                    self.cup_manager.start_new_cup()
                    self.score_manager.reset_cup_ingredients()
                    self._cup_attn_samples = []
                    self._focus_above_seconds = 0.0
                    self._secret_popup_timer = 0.0
                    logger.info(
                        "进入特调阶段！基线=%.1f 归一化=[%.1f, %.1f]  计时开始",
                        self._warmup_baseline,
                        self.normalization_lower,
                        self.normalization_upper,
                    )

            if self.phase == "formal":
                elapsed = time_module.time() - self.phase_formal_start - self._total_pause
                if elapsed >= EXPERIMENT_FORMAL_DURATION:
                    logger.info(
                        "特调阶段结束！累计成功杯数=%d 收益=%d",
                        self.score_manager.cup_count,
                        self.score_manager.total_money,
                    )
                    self.phase = "transition_memory"
                    self._transition_start = time_module.time()
                    self._pause_accumulated = 0.0

            if self.phase == "transition_memory":
                if time_module.time() - self._transition_start >= 2.0:
                    self.running = False

            self._render()

        return self._end_game()

    def _update_game_objects(self, dt_sec: float) -> None:
        if self.ingredient_manager.should_spawn():
            allowed = self.ingredient_manager._free_outlets(self.ingredients)
            if allowed is None or allowed:
                tier_required = INGREDIENT_TIERS.get(self._current_tier, INGREDIENT_TIERS[1])["required"]

                if random.random() < 0.2 and tier_required:
                    ing_type = random.choice(tier_required)
                    is_req = True
                else:
                    available = [t for t in self.ingredient_manager._available if t not in tier_required]
                    if not available:
                        available = list(self.ingredient_manager._available)
                    ing_type = random.choice(available)
                    is_req = False

                speed = self.ingredient_manager._current_speed
                if speed < 0:
                    speed = self.mode_speed
                ingredient = Ingredient(ing_type, is_req, speed, allowed_lanes=allowed)
                self.ingredients.add(ingredient)
                if is_req:
                    ingredient.set_particle_group(self.particles)
                self.ingredient_manager._on_spawned()

        self.ingredients.update()
        self.catch_effects.update(dt=dt_sec)
        self.miss_effects.update(dt=dt_sec)
        self.particles.update(dt=dt_sec)

    def _handle_collisions(self) -> None:
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

                self.score_manager.add_ingredient(hit.type, is_required=hit.is_required)
                self.cup_manager.add_catch(hit.type, is_required=hit.is_required)
                self.cup.update_level(self.cup_manager.catch_count)

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

    def _end_game(self) -> str:
        if self.bci_available:
            self.bci_reader.disconnect()
        return ""


def run_experiment(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    profile=None,
    control_mode: str = "bci",
    audio=None,
) -> str:
    session = ExperimentSession(screen, clock, profile, control_mode=control_mode, audio=audio)
    return session.run()
