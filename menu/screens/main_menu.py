"""主菜单 - 游戏启动后的第一个界面"""

from __future__ import annotations

import math
import os
import random

import pygame

from bci.data_reader import BCIDataReader
from config import (
    BADGE_IMGS,
    CONTROL_MODES,
    IMAGES_DIR,
    INGREDIENT_COLORS,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)
from game.font_utils import load_chinese_font
from menu.bci_button import GlowButton
from menu.components import Badge
from menu.history import HistoryScreen
from menu.mode_selector import ModeSelector
from menu.particles import FloatingItem, SteamParticle
from menu.screens.game_settings import GameSettingsScreen
from menu.screens.training_plan import TrainingPlanScreen


class MainMenu:
    def __init__(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
        title_font: pygame.font.Font,
        player_level: int = 1,
        history_games: list | None = None,
        profile=None,
        audio=None,
    ) -> None:
        self.screen = screen
        self.font = font
        self.title_font = title_font
        self._audio = audio
        self.big_title_font = load_chinese_font(64)
        self.clock = pygame.time.Clock()
        self.running = True
        self.result = None
        self.current_mode = "bci_normal"
        self._control_mode = "bci"
        self._history_games = history_games or []
        self._profile = profile

        self.bg = self._load_bg()
        self.badge = Badge(
            BADGE_IMGS,
            40,
            10,
            size=(100, 100),
            level_text=f"Lv.{player_level}",
            font=load_chinese_font(28),
            text_color=(30, 30, 30),
        )
        self.badge.set_level(player_level - 1)
        self.floating_items = [
            FloatingItem(SCREEN_WIDTH, SCREEN_HEIGHT, c)
            for c in list(INGREDIENT_COLORS.values()) + [(255, 180, 100)] * 3
        ]
        self.steam_particles = []
        self.steam_spawn_timer = 0

        # ==========================================
        # 2×2 按钮布局 - 基于背景图原始坐标 (46,761)-(1183,1047) 映射到 1280x720
        # 原始图 1920x1078, 缩放比 sx=1280/1920, sy=720/1078
        # ==========================================
        sx = SCREEN_WIDTH / 1920.0
        sy = SCREEN_HEIGHT / 1078.0
        area_left = int(46 * sx)
        area_top = int(761 * sy)
        area_w = int((1183 - 46) * sx)
        area_h = int((1047 - 761) * sy)

        h_gap = 350   # 按钮水平间距 (原379的90%)
        v_gap = 95    # 按钮垂直间距 (原96的90%)
        col1_x = area_left + (area_w - h_gap) // 2
        col2_x = col1_x + h_gap
        row1_y = area_top + (area_h - v_gap) // 2
        row2_y = row1_y + v_gap
        btn_w = 300                             # 固定按钮宽度
        btn_padding = (30, 16)                   # 紧凑垂直padding
        # ==========================================

        self.start_btn = GlowButton(
            "游戏开始",
            col1_x,
            row1_y,
            title_font,
            title_font,
            glow_color=(255, 180, 100),
            bg_color=(50, 25, 12),
            hover_color=(85, 40, 20),
            text_color=(255, 255, 255),
            width=btn_w,
            padding=btn_padding,
            image_path=os.path.join(IMAGES_DIR, "buttons", "游戏开始.png"),
        )

        self.settings_btn = GlowButton(
            "游戏设置",
            col1_x,
            row2_y,
            title_font,
            title_font,
            glow_color=(255, 190, 110),
            bg_color=(70, 35, 15),
            hover_color=(115, 55, 25),
            text_color=(255, 255, 255),
            width=btn_w,
            padding=btn_padding,
            image_path=os.path.join(IMAGES_DIR, "buttons", "设置.png"),
        )

        self.mode_selector = ModeSelector(
            col2_x,
            row1_y,
            font,
            title_font,
            control_modes=CONTROL_MODES,
            width=btn_w,
            padding=btn_padding,
            image_path=os.path.join(IMAGES_DIR, "buttons", "选择模式.png"),
        )

        self.exit_btn = GlowButton(
            "退出",
            col2_x,
            row2_y,
            title_font,
            title_font,
            glow_color=(255, 180, 100),
            bg_color=(50, 25, 12),
            hover_color=(85, 40, 20),
            text_color=(255, 255, 255),
            width=btn_w,
            padding=btn_padding,
            image_path=os.path.join(IMAGES_DIR, "buttons", "退出.png"),
        )

        train_w = 185
        train_x = int(col2_x + btn_w / 2 + 75 + train_w / 2)
        train_y = int((row1_y + row2_y) / 2)
        self.train_btn = GlowButton(
            "训练计划",
            train_x,
            train_y,
            title_font,
            title_font,
            glow_color=(255, 180, 100),
            bg_color=(50, 25, 12),
            hover_color=(85, 40, 20),
            text_color=(255, 255, 255),
            width=train_w,
            padding=(30, 68),
        )

        self.btn_cx = (col1_x + col2_x) // 2  # 标题居中于四个按钮上方

        self.title_y = 400  # 疯狂奶茶杯的y坐标
        self.title_phase = 0.0

        self._dialog_active = False
        self._dialog_text = ""
        self._dialog_confirm_rect = pygame.Rect(0, 0, 160, 50)
        self._dialog_result = None
        self._dialog_click_frames = 0

        self._conn_dialog_active = False
        self._conn_dialog_state = "connecting"
        self._conn_dialog_timer = 0.0
        self._conn_callback_result = ""
        self._conn_callback_mode = "bci"
        self._conn_bci_reader = None
        self._conn_rect_direct = pygame.Rect(0, 0, 0, 0)
        self._conn_rect_cancel = pygame.Rect(0, 0, 0, 0)
        self._conn_rect_retry = pygame.Rect(0, 0, 0, 0)
        self._conn_last_connect_attempt = 0.0

    def _load_bg(self) -> pygame.Surface | None:
        path = os.path.join(IMAGES_DIR, "backgrounds", "菜单页1.jpg")
        if os.path.exists(path):
            img = pygame.image.load(path).convert()
            return pygame.transform.scale(img, (SCREEN_WIDTH, SCREEN_HEIGHT))
        return None

    def _show_connection_dialog(self, callback_result: str, callback_mode: str) -> None:
        self._conn_dialog_active = True
        self._conn_dialog_state = "connecting"
        self._conn_dialog_timer = 0.0
        self._conn_callback_result = callback_result
        self._conn_callback_mode = callback_mode
        self._conn_last_connect_attempt = 0.0
        try:
            self._conn_bci_reader = BCIDataReader()
            self._conn_bci_reader.connect(connect_timeout=0.1)
        except Exception:
            self._conn_bci_reader = None

    def _try_bci_read(self) -> bool:
        if self._conn_bci_reader is None:
            return False
        try:
            result = self._conn_bci_reader.read_with_timeout()
            if result and result[0] is not None:
                return True
        except Exception:
            pass
        return False

    def _start_game(self, control_key: str, click_frames: list) -> None:
        if control_key == "bci_normal":
            self._show_connection_dialog("start", "bci")
        elif control_key == "memory":
            self._show_connection_dialog("start_memory", "bci")
        elif control_key == "infinite":
            self._show_connection_dialog("start", "infinite")

    def run(self) -> tuple[str | None, str, str]:
        click_frames = [0]

        while self.running:
            dt = self.clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    self.result = "quit"
                    if self._audio:
                        self._audio.play_sfx("音效/按键2.mp3", volume=0.5)

                if self._conn_dialog_active:
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        can_click = (
                            self._conn_dialog_state != "connecting" and self._conn_dialog_state != "reconnecting"
                        )
                        if self._conn_rect_direct.collidepoint(event.pos):
                            self._conn_dialog_active = False
                            self._conn_bci_reader = None
                            self.result = self._conn_callback_result
                            self.current_mode = self._conn_callback_mode
                            self._control_mode = "bci_failed"
                            click_frames[0] = 15
                        elif self._conn_rect_cancel.collidepoint(event.pos):
                            self._conn_dialog_active = False
                            self._conn_bci_reader = None
                        elif can_click and self._conn_rect_retry.collidepoint(event.pos):
                            self._conn_dialog_state = "reconnecting"
                            self._conn_dialog_timer = 0.0
                            self._conn_last_connect_attempt = 0.0
                            if self._conn_bci_reader:
                                self._conn_bci_reader.connect(connect_timeout=0.1)
                    continue

                if self._dialog_active:
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if self._dialog_confirm_rect.collidepoint(event.pos):
                            self._dialog_active = False
                            pending = getattr(self, "_dialog_pending_result", "start")
                            if pending is not None:
                                self.result = pending
                                self.current_mode = getattr(self, "_dialog_pending_mode", "bci")
                                self._control_mode = "bci_failed"
                                click_frames[0] = 15
                    elif event.type == pygame.KEYDOWN:
                        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            self._dialog_active = False
                            pending = getattr(self, "_dialog_pending_result", "start")
                            if pending is not None:
                                self.result = pending
                                self.current_mode = getattr(self, "_dialog_pending_mode", "bci")
                                self._control_mode = "bci_failed"
                                click_frames[0] = 15
                    continue

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                        self.result = "quit"
                        if self._audio:
                            self._audio.play_sfx("音效/按键2.mp3", volume=0.5)
                    elif event.key == pygame.K_RETURN or event.key == pygame.K_1:
                        self.start_btn.trigger_click()
                        self._start_game(self.mode_selector.current_key, click_frames)
                        if self._audio:
                            self._audio.play_sfx("音效/按键1.mp3", volume=0.5)
                    elif event.key == pygame.K_2:
                        self.settings_btn.trigger_click()
                        self.result = "settings"
                        click_frames[0] = 15
                        if self._audio:
                            self._audio.play_sfx("音效/按键1.mp3", volume=0.5)
                    elif event.key == pygame.K_3:
                        self.mode_selector.cycle_mode()
                        if self._audio:
                            self._audio.play_sfx("音效/按键1.mp3", volume=0.5)
                    elif event.key == pygame.K_4:
                        self.exit_btn.trigger_click()
                        self.running = False
                        self.result = "quit"
                        if self._audio:
                            self._audio.play_sfx("音效/按键2.mp3", volume=0.5)
                else:
                    if self.badge.handle_event(event):
                        HistoryScreen(self.screen, self._history_games, profile=self._profile).run()
                        if self._profile:
                            self._history_games = list(self._profile.games_history)
                    if self.start_btn.handle_event(event):
                        self._start_game(self.mode_selector.current_key, click_frames)
                        if self._audio:
                            self._audio.play_sfx("音效/按键1.mp3", volume=0.5)
                    mode = self.mode_selector.handle_event(event)
                    if mode:
                        self.current_mode = mode
                        if self._audio:
                            self._audio.play_sfx("音效/按键1.mp3", volume=0.5)
                    if self.settings_btn.handle_event(event):
                        self.settings_btn.trigger_click()
                        self.result = "settings"
                        click_frames[0] = 15
                        if self._audio:
                            self._audio.play_sfx("音效/按键1.mp3", volume=0.5)
                    if self.exit_btn.handle_event(event):
                        self.exit_btn.trigger_click()
                        self.running = False
                        self.result = "quit"
                        if self._audio:
                            self._audio.play_sfx("音效/按键2.mp3", volume=0.5)
                    if self.train_btn.handle_event(event):
                        self.train_btn.trigger_click()
                        self.result = "training"
                        click_frames[0] = 15
                        if self._audio:
                            self._audio.play_sfx("音效/按键1.mp3", volume=0.5)

            if self._conn_dialog_active:
                self._conn_dialog_timer += dt
                if self._conn_dialog_state in ("connecting", "reconnecting"):
                    if self._conn_bci_reader and self._conn_bci_reader.connected:
                        if self._try_bci_read():
                            self._conn_dialog_active = False
                            self._conn_bci_reader = None
                            self.result = self._conn_callback_result
                            self.current_mode = self._conn_callback_mode
                            self._control_mode = "bci"
                            click_frames[0] = 15
                    elif self._conn_bci_reader and self._conn_dialog_timer - self._conn_last_connect_attempt >= 1.0:
                        self._conn_bci_reader.connect(connect_timeout=0.1)
                        self._conn_last_connect_attempt = self._conn_dialog_timer
                    elif self._conn_dialog_timer >= 5.0:
                        self._conn_dialog_state = "failed"

            self._update(dt)
            self._draw()
            pygame.display.flip()

            if click_frames[0] > 0:
                click_frames[0] -= 1
                if click_frames[0] == 0:
                    if self.result == "settings":
                        bg_snapshot = self.screen.copy()
                        settings_screen = GameSettingsScreen(self.screen, self.font, self.title_font, audio=self._audio, bg=bg_snapshot)
                        settings_screen.run()
                        self.result = None
                    elif self.result == "training":
                        bg_snapshot = self.screen.copy()
                        training_screen = TrainingPlanScreen(self.screen, self.font, self.title_font, audio=self._audio, bg=bg_snapshot, profile=self._profile)
                        training_screen.run()
                        self.result = None
                    else:
                        self.running = False

        return self.result, self.current_mode, self._control_mode

    def _update(self, dt: float) -> None:
        self.badge.update(dt)
        self.start_btn.update(dt)
        self.mode_selector.update(dt)
        self.settings_btn.update(dt)
        self.exit_btn.update(dt)
        self.train_btn.update(dt)

        for item in self.floating_items:
            item.update()

        self.steam_spawn_timer += dt
        if self.steam_spawn_timer > 0.05:
            self.steam_spawn_timer = 0
            spawn_x = random.uniform(SCREEN_WIDTH * 0.3, SCREEN_WIDTH * 0.7)
            self.steam_particles.append(SteamParticle(int(spawn_x), SCREEN_HEIGHT + 10))
        self.steam_particles = [p for p in self.steam_particles if p.update()]

        self.title_phase += dt * 2

    def _draw_dialog(self) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        self.screen.blit(overlay, (0, 0))

        box_w = 420
        box_h = 160
        box_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        pygame.draw.rect(box_surf, (40, 30, 25, 230), (0, 0, box_w, box_h), border_radius=16)
        pygame.draw.rect(box_surf, (255, 200, 100, 180), (0, 0, box_w, box_h), 3, border_radius=16)

        text_surf = self.font.render(self._dialog_text, True, (255, 255, 255))
        tx = (box_w - text_surf.get_width()) // 2
        ty = 30
        box_surf.blit(text_surf, (tx, ty))

        btn_x = (box_w - 160) // 2
        btn_y = 85
        btn_rect_inner = pygame.Rect(btn_x, btn_y, 160, 50)
        pygame.draw.rect(box_surf, (100, 140, 200), btn_rect_inner, border_radius=12)
        pygame.draw.rect(box_surf, (255, 255, 255), btn_rect_inner, 2, border_radius=12)

        confirm_text = self.font.render("确认", True, (255, 255, 255))
        ctx = btn_x + (160 - confirm_text.get_width()) // 2
        cty = btn_y + (50 - confirm_text.get_height()) // 2
        box_surf.blit(confirm_text, (ctx, cty))

        bx = SCREEN_WIDTH // 2 - box_w // 2
        by = SCREEN_HEIGHT // 2 - box_h // 2
        self.screen.blit(box_surf, (bx, by))

        self._dialog_confirm_rect = pygame.Rect(bx + btn_x, by + btn_y, 160, 50)

    def _draw_connection_dialog(self) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        self.screen.blit(overlay, (0, 0))

        box_w = 480
        box_h = 260
        bx = SCREEN_WIDTH // 2 - box_w // 2
        by = SCREEN_HEIGHT // 2 - box_h // 2

        box_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        pygame.draw.rect(box_surf, (40, 30, 25, 230), (0, 0, box_w, box_h), border_radius=16)
        pygame.draw.rect(box_surf, (255, 200, 100, 180), (0, 0, box_w, box_h), 3, border_radius=16)

        title = self.font.render("正在连接中......", True, (255, 255, 255))
        tx = (box_w - title.get_width()) // 2
        box_surf.blit(title, (tx, 30))

        remaining = max(0, 5.0 - self._conn_dialog_timer)
        timer_text = self.font.render(f"{remaining:.0f}s", True, (180, 180, 180))
        box_surf.blit(timer_text, ((box_w - timer_text.get_width()) // 2, 70))

        btn_w = 150
        btn_h = 44

        is_disabled = self._conn_dialog_state in ("connecting", "reconnecting")

        retry_color = (80, 80, 80) if is_disabled else (200, 150, 50)
        retry_text_color = (120, 120, 120) if is_disabled else (255, 255, 255)

        retry_btn_x = (box_w - btn_w) // 2
        retry_btn_y = 115
        retry_inner = pygame.Rect(retry_btn_x, retry_btn_y, btn_w, btn_h)
        pygame.draw.rect(box_surf, retry_color, retry_inner, border_radius=8)
        pygame.draw.rect(box_surf, (255, 255, 255, 80), retry_inner, 2, border_radius=8)
        retry_text = self.font.render("重新连接", True, retry_text_color)
        box_surf.blit(
            retry_text,
            (
                retry_btn_x + (btn_w - retry_text.get_width()) // 2,
                retry_btn_y + (btn_h - retry_text.get_height()) // 2,
            ),
        )

        direct_btn_x = box_w // 2 - btn_w - 20
        cancel_btn_x = box_w // 2 + 20
        bottom_btn_y = 175

        direct_color = (60, 160, 100)
        direct_text_color = (255, 255, 255)
        direct_inner = pygame.Rect(direct_btn_x, bottom_btn_y, btn_w, btn_h)
        pygame.draw.rect(box_surf, direct_color, direct_inner, border_radius=8)
        pygame.draw.rect(box_surf, (255, 255, 255, 80), direct_inner, 2, border_radius=8)
        direct_text = self.font.render("直接进入", True, direct_text_color)
        box_surf.blit(
            direct_text,
            (
                direct_btn_x + (btn_w - direct_text.get_width()) // 2,
                bottom_btn_y + (btn_h - direct_text.get_height()) // 2,
            ),
        )

        cancel_color = (200, 60, 60)
        cancel_text_color = (255, 255, 255)
        cancel_inner = pygame.Rect(cancel_btn_x, bottom_btn_y, btn_w, btn_h)
        pygame.draw.rect(box_surf, cancel_color, cancel_inner, border_radius=8)
        pygame.draw.rect(box_surf, (255, 255, 255, 80), cancel_inner, 2, border_radius=8)
        cancel_text = self.font.render("取消", True, cancel_text_color)
        box_surf.blit(
            cancel_text,
            (
                cancel_btn_x + (btn_w - cancel_text.get_width()) // 2,
                bottom_btn_y + (btn_h - cancel_text.get_height()) // 2,
            ),
        )

        self.screen.blit(box_surf, (bx, by))

        self._conn_rect_direct = pygame.Rect(bx + direct_btn_x, by + bottom_btn_y, btn_w, btn_h)
        self._conn_rect_cancel = pygame.Rect(bx + cancel_btn_x, by + bottom_btn_y, btn_w, btn_h)
        self._conn_rect_retry = pygame.Rect(bx + retry_btn_x, by + retry_btn_y, btn_w, btn_h)

    def _draw(self) -> None:
        if self.bg:
            self.screen.blit(self.bg, (0, 0))
        else:
            self.screen.fill((255, 240, 220))

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 25))
        self.screen.blit(overlay, (0, 0))

        for p in self.steam_particles:
            p.draw(self.screen)

        self.badge.draw(self.screen)

        for item in self.floating_items:
            item.draw(self.screen)

        # title_offset = math.sin(self.title_phase) * 8
        # title_chars = list("疯狂奶茶杯")
        # char_spacing = 15
        # char_surfs = [self.big_title_font.render(c, True, (165, 85, 30)) for c in title_chars]
        # char_shadows = [self.big_title_font.render(c, True, (60, 25, 5)) for c in title_chars]
        # total_w = sum(s.get_width() for s in char_surfs) + char_spacing * (len(char_surfs) - 1)

        # tx = self.btn_cx - total_w // 2
        # ty = self.title_y + title_offset - 3
        # cx = tx
        # for surf, shadow in zip(char_surfs, char_shadows):
        #     self.screen.blit(shadow, (cx + 3, ty + 3))
        #     self.screen.blit(surf, (cx, ty))
        #     cx += surf.get_width() + char_spacing

        # sub_surf = self.font.render("接住食材 · 制作属于你的美味奶茶", True, (200, 160, 125))
        # sub_shadow = self.font.render("接住食材 · 制作属于你的美味奶茶", True, (30, 15, 5))
        # sw = sub_surf.get_width()
        # self.screen.blit(sub_shadow, (self.btn_cx - sw // 2 + 2, ty + 62))
        # self.screen.blit(sub_surf, (self.btn_cx - sw // 2, ty + 60))

        self.start_btn.draw(self.screen)
        self.mode_selector.draw(self.screen)
        self.settings_btn.draw(self.screen)
        self.exit_btn.draw(self.screen)
        self.train_btn.draw(self.screen)

        if self._conn_dialog_active:
            self._draw_connection_dialog()
        elif self._dialog_active:
            self._draw_dialog()

        hint = self.font.render("ESC 退出", True, (180, 180, 180))
        self.screen.blit(hint, (SCREEN_WIDTH - hint.get_width() - 20, SCREEN_HEIGHT - 35))
