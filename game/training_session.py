"""训练计划执行引擎 — 多阶段 × 多轮次自动轮转"""

from __future__ import annotations

import logging
import math
import os
import random
import time as time_module

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
    INGREDIENT_POINTS,
    INGREDIENT_TIERS,
    MEMORY_SPEED_MAX,
    MEMORY_SPEED_MIN,
    NUM_IMG_DIR,
    OUTLET_BLOCK_RADIUS,
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
from data.memory_recipes import MEMORY_RECIPES
from data.score_manager import ScoreManager
from data.training_plan import TrainingPlan
from game.cup_manager import CupManager
from game.font_utils import load_chinese_font
from game.ingredient_manager import IngredientManager
from game.sprites import CatchEffect, Cup, Ingredient, MissEffect, Particle

logger = logging.getLogger(__name__)


class _TrainingParticle(pygame.sprite.Sprite):
    def __init__(self, x: float, y: float, color: tuple[int, int, int]) -> None:
        super().__init__()
        self.x = x
        self.y = y
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(2, 7)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.life = 1.0
        self.decay = random.uniform(1.5, 3.0)
        self.size = random.randint(2, 6)
        self.image = pygame.Surface((self.size * 2, self.size * 2), pygame.SRCALPHA)
        pygame.draw.circle(self.image, (*color, 255), (self.size, self.size), self.size)
        self.rect = self.image.get_rect(center=(int(x), int(y)))

    def update(self, dt: float = 0.016) -> None:
        self.life -= self.decay * dt
        if self.life <= 0:
            self.kill()
            return
        self.x += self.vx * dt * 60
        self.y += self.vy * dt * 60
        self.rect.center = (int(self.x), int(self.y))
        self.image.set_alpha(int(self.life * 255))


class TrainingSession:
    def __init__(
        self,
        screen: pygame.Surface,
        clock: pygame.time.Clock,
        plan: TrainingPlan,
        username: str,
        profile=None,
        control_mode: str = "bci",
        audio=None,
    ) -> None:
        self.screen = screen
        self.clock = clock
        self._plan = plan
        self._username = username
        self._profile = profile
        self._control_mode = control_mode
        self._audio = audio

        self._load_fonts()
        self._init_game_objects()
        self._init_bci()
        self._load_background()
        self._init_state()

    def _load_fonts(self) -> None:
        self.font = load_chinese_font(36)
        self.hint_font = load_chinese_font(20)
        self.small_font = load_chinese_font(18)
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
        self._memory_ingredients = pygame.sprite.Group()
        self._memory_particles = pygame.sprite.Group()

        self.score_manager = ScoreManager()
        start_tier = self._profile.level if self._profile else 1
        self.ingredient_manager = IngredientManager(tier=start_tier)
        self.ingredient_manager.spawn_interval = 1.0
        tier_required = INGREDIENT_TIERS.get(start_tier, INGREDIENT_TIERS[1]).get("required", ["红茶"])
        first_required = tier_required[0] if tier_required else "红茶"
        self.score_manager.set_required_ingredient(first_required)
        self.cup_manager = CupManager(has_required=True, required_type=first_required, total_cups=999, secret_recipe_interval=3)

        self._memory_level = 2
        self._memory_recipe_ingredients: list[str] = []
        self._memory_recipe_name = ""
        self._memory_spawn_sequence: list[str] = []
        self._memory_spawn_index = 0
        self._memory_catch_index = 0
        self._memory_fail_reason = ""
        self._memory_round_failed = False
        self._memory_all_spawned = False
        self._memory_last_spawn_time = 0.0

    def _init_bci(self) -> None:
        self.bci_reader = BCIDataReader()
        self.bci_available = False
        if self._control_mode != "bci_failed":
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

    def _init_state(self) -> None:
        self.running = True
        self.attention = None
        self.raw_gyro_x = 0.0
        self.raw_gyro_y = 0.0
        self.raw_gyro_z = 0.0
        self.platform_focus_x = float(SCREEN_WIDTH // 2)
        self.platform_focus_y = float(SCREEN_HEIGHT - 100)
        self.focus_min = CUP_WIDTH // 2
        self.focus_max = SCREEN_WIDTH - CUP_WIDTH // 2
        self.use_yaw_control = self.bci_available
        self.cup.yaw_control = self.use_yaw_control
        if not self.bci_available and self._control_mode != "bci_failed":
            self.use_yaw_control = False
            self.cup.yaw_control = False

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
        self._esc_dialog_active = False
        self._esc_dialog_selected = 0
        self._pause_accumulated = 0.0
        self._pause_start = 0.0
        self._pending_settings = False
        self._player_level = self._profile.level if self._profile else 1

    def run_one_session(self) -> str:
        session = self._plan.completed_sessions + 1
        if session > self._plan.total_sessions:
            return "complete"

        for phase_idx, phase in enumerate(self._plan.phases):
            if phase_idx < self._plan.current_phase:
                continue
            result = self._run_phase(phase, session, phase_idx + 1, len(self._plan.phases))
            if result == "quit":
                self._plan.save_progress(session, phase_idx)
                return "quit"
            if result == "skip":
                continue
            self._plan.save_progress(session, phase_idx + 1)

        self._plan.save_progress(session, 0)
        return self._show_summary()

    def _run_phase(self, phase: dict, session: int, phase_num: int, total_phases: int) -> str:
        mode = phase["mode"]
        duration = phase["duration"]
        phase_name = phase.get("name", mode)

        if mode == "memory":
            return self._run_memory_phase(duration, session, phase_num, total_phases, phase_name)
        elif mode == "experiment":
            return self._run_experiment_package(session, phase_num, total_phases)
        else:
            return self._run_cup_phase(mode, duration, session, phase_num, total_phases, phase_name)

    def _run_cup_phase(self, mode: str, duration: float, session: int, phase_num: int, total_phases: int, phase_name: str) -> str:
        """运行接杯类阶段（原萃/特调）"""
        self.cup_manager.start_new_cup()
        self.phase_start_time = time_module.time()
        self._phase_duration = duration
        self._session_str = f"{session}/{self._plan.total_sessions} 轮"
        self._phase_label = phase_name
        self._phase_mode = mode

        self._render_initial()
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
            if self._pending_settings:
                self._open_settings()
                continue
            self._update_bci_data()
            if keys[pygame.K_o]:
                return "skip"
            self._update_cup(keys, dt_sec)
            self._update_pause_state(dt_sec)
            self._check_artifact(dt_sec)
            self._update_artifact_freeze(dt_sec)
            if not (self._paused or self._artifact_frozen):
                self._update_cup_speed(mode)
                self._update_game_objects(dt_sec)
                self._handle_collisions()
                self._check_cup_end()
            elapsed = time_module.time() - self.phase_start_time - self._total_pause
            if elapsed >= duration:
                break
            self._render()
        return ""

    def _run_memory_phase(self, duration: float, session: int, phase_num: int, total_phases: int, phase_name: str) -> str:
        """运行忆调阶段"""
        self._phase_duration = duration
        self._session_str = f"{session}/{self._plan.total_sessions} 轮"
        self._phase_label = phase_name
        self._memory_phase = "rules"
        self._memory_phase_timer = 0.0
        self._memory_level = 2
        self._memory_success_rounds = 0
        self._memory_total_rounds = 0
        self._memory_ingredients.empty()
        self._memory_particles.empty()
        self._memory_first_round = True
        self._memory_session_ending = False
        memory_start = time_module.time()
        self._memory_ingredient_speed = MEMORY_SPEED_MIN + (MEMORY_SPEED_MAX - MEMORY_SPEED_MIN) * 0.5

        self._render_initial()
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
            if self._pending_settings:
                self._open_settings()
                continue
            self._update_bci_data()
            if keys[pygame.K_o]:
                return "skip"
            self._update_memory_speed()
            self._update_memory_game(dt_sec)
            if self._memory_phase == "playing":
                self._update_memory_cup(keys, dt_sec)
            else:
                self.cup.rect.centerx = SCREEN_WIDTH // 2
                self.cup.rect.bottom = SCREEN_HEIGHT - 10
            elapsed = time_module.time() - memory_start - self._total_pause
            if elapsed >= duration:
                self._memory_session_ending = True
            self._render_memory()
        return ""

    def _run_experiment_package(self, session: int, phase_num: int, total_phases: int) -> str:
        """运行完整实验模式包"""
        from game.experiment_mode import ExperimentSession
        exp = ExperimentSession(self.screen, self.clock, profile=self._profile, control_mode=self._control_mode, audio=self._audio)
        return exp.run()

    def _render_initial(self) -> None:
        if self.has_background and self.background:
            self.screen.blit(self.background, (0, 0))
        else:
            self.screen.fill((255, 255, 255))
        self.all_sprites.draw(self.screen)
        self._draw_transition_overlay(self._phase_label, self._session_str)
        pygame.display.flip()

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
            self._draw_info_labels()
        if self._focus_ball:
            self._draw_focus_ball()
        self._draw_bottom_hud()
        if self._blackout_alpha > 1:
            blk = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            blk.fill((0, 0, 0, int(self._blackout_alpha)))
            self.screen.blit(blk, (0, 0))
        if self._artifact_alpha > 1:
            blk = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            blk.fill((0, 0, 0, int(self._artifact_alpha)))
            self.screen.blit(blk, (0, 0))
        if self._esc_dialog_active:
            self._draw_esc_dialog()
        pygame.display.flip()

    def _render_memory(self) -> None:
        self._render()
        for ing in self._memory_ingredients:
            self.screen.blit(ing.image, ing.rect)
        for p in self._memory_particles:
            self.screen.blit(p.image, p.rect)
        self.screen.blit(self.cup.image, self.cup.rect)
        self._draw_memory_hud()
        if self._esc_dialog_active:
            self._draw_esc_dialog()
        pygame.display.flip()

    def _draw_bottom_hud(self) -> None:
        label_surf = self.phase_font.render(self._phase_label, True, (200, 150, 255))
        shadow = self.phase_font.render(self._phase_label, True, (30, 20, 10))
        x = SCREEN_WIDTH - label_surf.get_width() - 30
        y = SCREEN_HEIGHT - label_surf.get_height() - 75
        self.screen.blit(shadow, (x + 2, y + 2))
        self.screen.blit(label_surf, (x, y))
        session_s = self.small_font.render(self._session_str, True, (180, 180, 180))
        self.screen.blit(session_s, (SCREEN_WIDTH - session_s.get_width() - 30, SCREEN_HEIGHT - 50))
        elapsed = time_module.time() - self.phase_start_time - self._total_pause
        remaining = max(0, self._phase_duration - elapsed)
        mins = int(remaining // 60)
        secs = int(remaining % 60)
        cd_text = f"{mins}:{secs:02d}"
        cd_surf = self.phase_font.render(cd_text, True, (255, 200, 100))
        self.screen.blit(cd_surf, (SCREEN_WIDTH - cd_surf.get_width() - 30, SCREEN_HEIGHT - cd_surf.get_height() - 15))

    def _draw_info_labels(self) -> None:
        info_font = load_chinese_font(INFO_FONT_SIZE)
        values = [
            f"LV.{self._player_level}",
            self._phase_label,
            str(self.score_manager.cup_count),
            str(self.score_manager.total_money),
        ]
        for (cx, cy), v in zip(INFO_REGIONS, values):
            t = info_font.render(v, True, (255, 255, 255))
            tw, th = t.get_size()
            self.screen.blit(t, (cx - tw // 2, cy - th // 2))

    def _draw_focus_ball(self) -> None:
        if not self._digit_imgs:
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

    def _draw_transition_overlay(self, title: str, subtitle: str) -> None:
        shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 180))
        self.screen.blit(shade, (0, 0))
        t1 = self.phase_font.render(title, True, (255, 220, 100))
        t2 = self.font.render(subtitle, True, (255, 255, 255))
        self.screen.blit(t1, (SCREEN_WIDTH // 2 - t1.get_width() // 2, SCREEN_HEIGHT // 2 - 60))
        self.screen.blit(t2, (SCREEN_WIDTH // 2 - t2.get_width() // 2, SCREEN_HEIGHT // 2))

    def _handle_events(self) -> None:
        show_dialog = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self._esc_dialog_active:
                        self._esc_dialog_active = False
                    else:
                        show_dialog = True
                elif self._esc_dialog_active:
                    if event.key in (pygame.K_LEFT, pygame.K_UP):
                        self._esc_dialog_selected = (self._esc_dialog_selected - 1) % 3
                    elif event.key in (pygame.K_RIGHT, pygame.K_DOWN, pygame.K_TAB):
                        self._esc_dialog_selected = (self._esc_dialog_selected + 1) % 3
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self._commit_esc_dialog()
            elif event.type == pygame.MOUSEBUTTONDOWN and self._esc_dialog_active:
                if event.button == 1:
                    self._handle_esc_click(event.pos)
        if show_dialog:
            self._esc_dialog_active = True
            self._esc_dialog_selected = 0
            self._pause_start = time_module.time()

    def _commit_esc_dialog(self) -> None:
        if self._esc_dialog_selected == 0:
            self._esc_dialog_active = False
            self._pause_accumulated += time_module.time() - self._pause_start
        elif self._esc_dialog_selected == 1:
            self._esc_dialog_active = False
            self._pause_accumulated += time_module.time() - self._pause_start
            self.running = False
        else:
            self._esc_dialog_active = False
            self._pending_settings = True

    def _handle_esc_click(self, pos) -> None:
        if hasattr(self, "_esc_continue_rect") and self._esc_continue_rect.collidepoint(pos):
            self._esc_dialog_active = False
            self._pause_accumulated += time_module.time() - self._pause_start
        elif hasattr(self, "_esc_exit_rect") and self._esc_exit_rect.collidepoint(pos):
            self._esc_dialog_active = False
            self._pause_accumulated += time_module.time() - self._pause_start
            self.running = False
        elif hasattr(self, "_esc_settings_rect") and self._esc_settings_rect.collidepoint(pos):
            self._esc_dialog_active = False
            self._pending_settings = True

    def _draw_esc_dialog(self) -> None:
        ol = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        ol.fill((0, 0, 0, 160))
        self.screen.blit(ol, (0, 0))
        box_w, box_h = 380, 280
        bx = (SCREEN_WIDTH - box_w) // 2
        by = (SCREEN_HEIGHT - box_h) // 2
        pygame.draw.rect(self.screen, (30, 28, 20), pygame.Rect(bx, by, box_w, box_h), border_radius=16)
        pygame.draw.rect(self.screen, (200, 160, 100), pygame.Rect(bx, by, box_w, box_h), 3, border_radius=16)
        title = self.pause_font.render("暂停", True, (255, 255, 255))
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, by + 25))
        btn_w, btn_h = 150, 48
        btn_y = by + 90
        gap = 20
        lx = SCREEN_WIDTH // 2 - btn_w - gap // 2
        rx = SCREEN_WIDTH // 2 + gap // 2
        sel_b = (255, 255, 255)
        nor_b = (100, 100, 100)
        self._esc_continue_rect = pygame.Rect(lx, btn_y, btn_w, btn_h)
        cb = sel_b if self._esc_dialog_selected == 0 else nor_b
        pygame.draw.rect(self.screen, (80, 180, 80), self._esc_continue_rect, border_radius=10)
        pygame.draw.rect(self.screen, cb, self._esc_continue_rect, 3, border_radius=10)
        ct = self.font.render("继续训练", True, (255, 255, 255))
        self.screen.blit(ct, (self._esc_continue_rect.centerx - ct.get_width() // 2, self._esc_continue_rect.centery - ct.get_height() // 2))
        self._esc_exit_rect = pygame.Rect(rx, btn_y, btn_w, btn_h)
        eb = sel_b if self._esc_dialog_selected == 1 else nor_b
        pygame.draw.rect(self.screen, (200, 60, 60), self._esc_exit_rect, border_radius=10)
        pygame.draw.rect(self.screen, eb, self._esc_exit_rect, 3, border_radius=10)
        et = self.font.render("退出并保存", True, (255, 255, 255))
        self.screen.blit(et, (self._esc_exit_rect.centerx - et.get_width() // 2, self._esc_exit_rect.centery - et.get_height() // 2))
        st_w = 200
        st_y = btn_y + btn_h + 16
        st_x = SCREEN_WIDTH // 2 - st_w // 2
        self._esc_settings_rect = pygame.Rect(st_x, st_y, st_w, btn_h)
        sb = sel_b if self._esc_dialog_selected == 2 else nor_b
        pygame.draw.rect(self.screen, (220, 160, 60), self._esc_settings_rect, border_radius=10)
        pygame.draw.rect(self.screen, sb, self._esc_settings_rect, 3, border_radius=10)
        st = self.font.render("游戏设置", True, (255, 255, 255))
        self.screen.blit(st, (self._esc_settings_rect.centerx - st.get_width() // 2, self._esc_settings_rect.centery - st.get_height() // 2))

    def _open_settings(self) -> None:
        self._pending_settings = False
        from menu.screens.game_settings import GameSettingsScreen
        sf = load_chinese_font(24)
        stf = load_chinese_font(40)
        bg_snap = self.screen.copy()
        GameSettingsScreen(self.screen, sf, stf, audio=self._audio, bg=bg_snap).run()

    @property
    def _total_pause(self) -> float:
        if self._esc_dialog_active:
            return self._pause_accumulated + time_module.time() - self._pause_start
        return self._pause_accumulated

    def _update_bci_data(self) -> None:
        if self.bci_available:
            result = self.bci_reader.read_with_timeout()
            self.bci_available = self.bci_reader.connected
            if self.bci_available and result[0] is not None:
                self.attention, self.platform_focus_x, self.platform_focus_y, self.raw_gyro_x, self.raw_gyro_y, self.raw_gyro_z = result
            else:
                self.attention = 50

    def _update_cup(self, keys, dt_sec) -> None:
        self.cup.update(keys=keys, dt=dt_sec)
        if not (keys[pygame.K_LEFT] or keys[pygame.K_RIGHT]) and self.use_yaw_control and self.bci_available:
            self.cup.rect.centerx = max(self.focus_min, min(self.focus_max, int(self.platform_focus_x)))

    def _update_pause_state(self, dt_sec) -> None:
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
        target_alpha = 180 if self._paused else 0
        self._blackout_alpha += (target_alpha - self._blackout_alpha) * 0.05

    def _check_artifact(self, dt_sec) -> None:
        if self._artifact_frozen or not self.bci_available:
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

    def _update_artifact_freeze(self, dt_sec) -> None:
        if not self._artifact_frozen:
            return
        self._artifact_penalty_timer -= dt_sec
        if self._artifact_penalty_timer <= 0.0:
            self._artifact_frozen = False
            self._artifact_penalty_timer = 0.0
        target_alpha = 180 if self._artifact_frozen else 0
        self._artifact_alpha += (target_alpha - self._artifact_alpha) * 0.1

    def _update_cup_speed(self, mode: str) -> None:
        if mode == "infinite":
            attn = self.attention if self.attention is not None else 50.0
            speed = EXPERIMENT_WARMUP_SPEED_MAX - (attn / 100.0) * (EXPERIMENT_WARMUP_SPEED_MAX - EXPERIMENT_WARMUP_SPEED_MIN)
        elif mode == "bci":
            norm = max(1.0, min(100.0, (self.attention or 50) - 30.0) / 40.0 * 99.0 + 1.0)
            speed = FORMAL_SPEED_MAX - (norm - 1.0) / 99.0 * (FORMAL_SPEED_MAX - FORMAL_SPEED_MIN)
        else:
            speed = 3.0
        self.ingredient_manager.set_current_speed(speed)
        for ing in self.ingredients:
            ing.speed = speed
        self.ingredient_manager.set_spawn_interval(1.0)

    def _update_game_objects(self, dt_sec) -> None:
        if self.ingredient_manager.should_spawn():
            allowed = self.ingredient_manager._free_outlets(self.ingredients)
            if allowed is None or allowed:
                tier_required = INGREDIENT_TIERS.get(1, INGREDIENT_TIERS[1])["required"]
                if random.random() < 0.2 and tier_required:
                    ing_type = random.choice(tier_required)
                    is_req = True
                else:
                    available = [t for t in self.ingredient_manager._available if t not in tier_required]
                    available.append("冰块")
                    ing_type = random.choice(available)
                    is_req = False
                speed = self.ingredient_manager._current_speed
                if speed < 0:
                    speed = 3.0
                ingredient = Ingredient(ing_type, is_req, speed)
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
                for _ in range(4):
                    p = Particle(hit.rect.centerx, int(threshold_y), INGREDIENT_COLORS.get(hit.type, (200, 200, 200)))
                    p.vx *= 0.4
                    p.vy *= 0.4
                    p.decay *= 1.5
                    self.particles.add(p)
                self.ingredients.remove(hit)
            else:
                self.ingredients.remove(hit)
                self.catch_effects.add(CatchEffect(hit, self.cup.rect))
                for _ in range(8):
                    self.particles.add(Particle(hit.rect.centerx, hit.rect.centery, INGREDIENT_COLORS.get(hit.type, (255, 200, 0))))
                self.cup.trigger_bounce()
                self.score_manager.add_ingredient(hit.type, is_required=hit.is_required)
                self.cup_manager.add_catch(hit.type, is_required=hit.is_required)
        for ing in self.ingredients.sprites():
            if ing.rect.bottom > threshold_y:
                ing.rect.bottom = int(threshold_y)
                self.miss_effects.add(MissEffect(ing))
                for _ in range(4):
                    p = Particle(ing.rect.centerx, int(threshold_y), INGREDIENT_COLORS.get(ing.type, (200, 200, 200)))
                    p.vx *= 0.4
                    p.vy *= 0.4
                    p.decay *= 1.5
                    self.particles.add(p)
                self.ingredients.remove(ing)

    def _check_cup_end(self) -> None:
        if self.cup_manager.check_cup_end():
            cup_money = self.cup_manager.settle_cup()
            had_secret = self.cup_manager.secret_recipe_spawned
            if cup_money > 0 and self.cup_manager.cup_required_caught:
                self.score_manager.add_cup_money(cup_money, had_secret)
            self.score_manager.reset_cup_ingredients()
            self.cup_manager.start_new_cup()
            self.cup.update_level(0)
            self.score_manager.reset_cup_ingredients()

    def _update_memory_speed(self) -> None:
        if not self.bci_available:
            self._memory_ingredient_speed = 4.5
            return
        attn = max(0, min(100, self.attention if self.attention is not None else 50))
        self._memory_ingredient_speed = MEMORY_SPEED_MAX - (attn / 100.0) * (MEMORY_SPEED_MAX - MEMORY_SPEED_MIN)

    def _update_memory_cup(self, keys, dt_sec) -> None:
        kb = keys[pygame.K_LEFT] or keys[pygame.K_RIGHT]
        if self.bci_available and not kb:
            self.cup.rect.centerx = max(self.focus_min, min(self.focus_max, int(self.platform_focus_x)))
        else:
            self.cup.update(keys={pygame.K_LEFT: keys[pygame.K_LEFT], pygame.K_RIGHT: keys[pygame.K_RIGHT]}, dt=dt_sec)

    def _update_memory_game(self, dt_sec) -> None:
        self._memory_phase_timer += dt_sec
        if self._memory_phase == "rules":
            if self._memory_phase_timer >= 3.5:
                self._pick_memory_recipe()
                self._gen_memory_sequence()
                self._memory_phase = "memorize"
                self._memory_phase_timer = 0.0
        elif self._memory_phase == "memorize":
            if self._memory_phase_timer >= 2.0:
                self._memory_phase = "playing"
                self._memory_spawn_index = 0
                self._memory_catch_index = 0
                self._memory_fail_reason = ""
                self._memory_round_failed = False
                self._memory_all_spawned = False
                self._memory_ingredients.empty()
                self._memory_last_spawn_time = time_module.time()
                if self._memory_first_round:
                    self._memory_first_round = False
        elif self._memory_phase == "playing":
            if not self._memory_all_spawned:
                if time_module.time() - self._memory_last_spawn_time >= 1.2:
                    self._memory_last_spawn_time = time_module.time()
                    ing_type = self._memory_spawn_sequence[self._memory_spawn_index]
                    allowed = self._memory_free_outlets()
                    if allowed:
                        idx = random.choice(allowed)
                        ing = Ingredient(ing_type, speed=self._memory_ingredient_speed, outlet_index=idx)
                        ing.rect.width = 80
                        ing.rect.height = 80
                        self._memory_ingredients.add(ing)
                        self._memory_spawn_index += 1
                        if self._memory_spawn_index >= len(self._memory_spawn_sequence):
                            self._memory_all_spawned = True
                    else:
                        self._memory_last_spawn_time += 0.2
            self._memory_ingredients.update()
            self._memory_particles.update(dt_sec)
            self._check_memory_collisions()
            for ing in list(self._memory_ingredients):
                if ing.rect.top > SCREEN_HEIGHT:
                    self._memory_ingredients.remove(ing)
            if len(self._memory_ingredients) == 0 and self._memory_all_spawned:
                if not self._memory_round_failed and self._memory_catch_index < len(self._memory_recipe_ingredients):
                    self._memory_round_failed = True
                    self._memory_fail_reason = "incomplete"
                self._memory_phase = "result"
                self._memory_phase_timer = 0.0
        elif self._memory_phase == "result":
            if self._memory_phase_timer >= 1.5:
                self._memory_total_rounds += 1
                if not self._memory_round_failed:
                    self._memory_success_rounds += 1
                    self.score_manager.add_cup_money(len(self._memory_recipe_ingredients) * 10, False)
                if self._memory_session_ending:
                    self.running = False
                else:
                    self._memory_phase = "rest"
                    self._memory_phase_timer = 0.0
        elif self._memory_phase == "rest":
            if self._memory_phase_timer >= 2.0:
                if self._memory_session_ending:
                    self.running = False
                else:
                    self._pick_memory_recipe()
                    self._gen_memory_sequence()
                    self._memory_phase = "memorize"
                    self._memory_phase_timer = 0.0

    def _pick_memory_recipe(self) -> None:
        level = max(2, min(5, self._memory_level))
        recipes = MEMORY_RECIPES.get(level, [])
        if not recipes:
            recipes = MEMORY_RECIPES.get(2, [])
        recipe = random.choice(recipes)
        self._memory_recipe_ingredients = list(recipe["ingredients"])
        self._memory_recipe_name = recipe["name"]

    def _gen_memory_sequence(self) -> None:
        recipe = self._memory_recipe_ingredients
        n = len(recipe)
        dist_pool = INGREDIENT_TIERS.get(1, INGREDIENT_TIERS[1])["available"]
        recipe_seq = list(recipe) * 2
        total_dist = n * 3
        gaps = len(recipe_seq)
        per_gap = total_dist / max(1, gaps)
        result: list[str] = []
        dist_used = 0
        for i, ri in enumerate(recipe_seq):
            target = int(per_gap * (i + 1)) - dist_used
            for _ in range(target):
                result.append(random.choice(dist_pool))
                dist_used += 1
            result.append(ri)
        while dist_used < total_dist:
            result.append(random.choice(dist_pool))
            dist_used += 1
        self._memory_spawn_sequence = result

    def _memory_free_outlets(self) -> list[int]:
        occupied = set()
        for ing in self._memory_ingredients:
            if ing.rect.y < SCREEN_HEIGHT * 0.35:
                for i, (ox, oy) in enumerate(OUTLET_POSITIONS):
                    dx = ing.rect.centerx - ox
                    dy = ing.rect.centery - oy
                    if dx * dx + dy * dy < OUTLET_BLOCK_RADIUS * OUTLET_BLOCK_RADIUS:
                        occupied.add(i)
        return [i for i in range(len(OUTLET_POSITIONS)) if i not in occupied]

    def _check_memory_collisions(self) -> None:
        threshold_y = self.cup.rect.top + self.cup.rect.height * 0.8
        hits = pygame.sprite.spritecollide(self.cup, self._memory_ingredients, False)
        for hit in hits:
            if hit.rect.bottom > threshold_y:
                hit.rect.bottom = int(threshold_y)
                self._memory_ingredients.remove(hit)
                continue
            self._memory_ingredients.remove(hit)
            color = INGREDIENT_COLORS.get(hit.type, (255, 200, 0))
            for _ in range(8):
                self._memory_particles.add(_TrainingParticle(hit.rect.centerx, hit.rect.centery, color))
            self.cup.trigger_bounce()
            if self._memory_catch_index < len(self._memory_recipe_ingredients):
                expected = self._memory_recipe_ingredients[self._memory_catch_index]
                if hit.type == expected:
                    self._memory_catch_index += 1
                else:
                    self._memory_round_failed = True
                    self._memory_fail_reason = "wrong_order"

    def _draw_memory_hud(self) -> None:
        if self._memory_phase == "rules":
            shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 180))
            self.screen.blit(shade, (0, 0))
            rules = ["忆调阶段 — 记忆配方，按序接食材", "", "1. 记住下方食材和名称", "2. 按配方顺序依次接住"]
            y = SCREEN_HEIGHT // 2 - 80
            for line in rules:
                s = self.font.render(line, True, (255, 255, 255))
                self.screen.blit(s, (SCREEN_WIDTH // 2 - s.get_width() // 2, y))
                y += 36
        elif self._memory_phase == "memorize":
            shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 180))
            self.screen.blit(shade, (0, 0))
            cx = SCREEN_WIDTH // 2
            cy = SCREEN_HEIGHT // 2 - 40
            total_w = len(self._memory_recipe_ingredients) * 120
            start_x = cx - total_w // 2
            for i, ing_type in enumerate(self._memory_recipe_ingredients):
                path = INGREDIENT_IMGS.get(ing_type, "")
                if path and os.path.exists(path):
                    img = pygame.image.load(path).convert_alpha()
                    img = pygame.transform.scale(img, (90, 90))
                    self.screen.blit(img, (start_x + i * 120, cy - 45))
            name_s = self.font.render(self._memory_recipe_name, True, (255, 220, 100))
            self.screen.blit(name_s, (cx - name_s.get_width() // 2, cy + 60))
            remain = max(0, 2.0 - self._memory_phase_timer)
            bar_w = int(300 * remain / 2.0)
            pygame.draw.rect(self.screen, (60, 60, 60), (cx - 150, cy + 100, 300, 10))
            if bar_w > 0:
                pygame.draw.rect(self.screen, (255, 220, 100), (cx - 150, cy + 100, bar_w, 10))
        elif self._memory_phase == "result":
            shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 160))
            self.screen.blit(shade, (0, 0))
            if not self._memory_round_failed:
                t = f"正确调配  {self._memory_recipe_name}"
                c = (100, 255, 100)
            elif self._memory_fail_reason == "wrong_order":
                t = "错误调配"
                c = (255, 100, 100)
            else:
                t = "未完成"
                c = (255, 180, 50)
            s = self.font.render(t, True, c)
            self.screen.blit(s, (SCREEN_WIDTH // 2 - s.get_width() // 2, SCREEN_HEIGHT // 2 - 40))
        elif self._memory_phase == "rest":
            remain = max(0, 2.0 - self._memory_phase_timer)
            t = f"下一杯即将开始... {int(remain + 0.9)}s"
            s = self.font.render(t, True, (0, 0, 0))
            self.screen.blit(s, (SCREEN_WIDTH // 2 - s.get_width() // 2, 180))

    def _show_summary(self) -> str:
        if self._audio:
            self._audio.play_sfx("音效/游戏结束.wav", volume=0.6)
        from menu.summary import SummaryScreen
        bg_snapshot = self.screen.copy()
        summary = SummaryScreen(
            self.screen, 0,
            game_mode="experiment",
            total_money=self.score_manager.total_money,
            cup_count=self.score_manager.cup_count,
            player_level=self._player_level,
            bg=bg_snapshot,
        )
        result = summary.run()
        if result == "save" and self._profile:
            self._profile.add_game_result(
                revenue=self.score_manager.total_money,
                mode="training",
                cups=self.score_manager.cup_count,
                secrets=0,
                avg_attention=0.0,
                duration=0.0,
            )
        if self.bci_available and hasattr(self, "bci_reader"):
            self.bci_reader.disconnect()
        self._plan.save_progress(self._plan.total_sessions, 0)
        return result


def run_training(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    plan: TrainingPlan,
    username: str,
    profile=None,
    control_mode: str = "bci",
    audio=None,
) -> str:
    session = TrainingSession(screen, clock, plan, username, profile=profile, control_mode=control_mode, audio=audio)
    return session.run_one_session()
