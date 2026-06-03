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


class MainMenu:
    def __init__(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
        title_font: pygame.font.Font,
        player_level: int = 1,
        history_games: list | None = None,
        profile=None,
    ) -> None:
        self.screen = screen
        self.font = font
        self.title_font = title_font
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
        # 按键布局参数
        # ==========================================
        cx = SCREEN_WIDTH // 2
        cy = SCREEN_HEIGHT // 2
        btn_spacing = 105
        start_y = cy - 50
        # ==========================================

        self.start_btn = GlowButton(
            "游戏开始",
            cx,
            start_y,
            title_font,
            title_font,
            glow_color=(255, 180, 100),
            bg_color=(50, 25, 12),
            hover_color=(85, 40, 20),
            text_color=(255, 255, 255),
        )

        self.mode_selector = ModeSelector(
            cx,
            start_y + btn_spacing,
            font,
            title_font,
            control_modes=CONTROL_MODES,
        )

        self.settings_btn = GlowButton(
            "游戏设置",
            cx,
            start_y + btn_spacing * 2,
            title_font,
            title_font,
            glow_color=(255, 190, 110),
            bg_color=(70, 35, 15),
            hover_color=(115, 55, 25),
            text_color=(255, 255, 255),
        )

        self.btn_cx = cx

        self.title_y = start_y - 175  # 疯狂奶茶杯的y坐标
        self.title_phase = 0.0

        self._dialog_active = False
        self._dialog_text = ""
        self._dialog_confirm_rect = pygame.Rect(0, 0, 160, 50)
        self._dialog_result = None
        self._dialog_click_frames = 0

    def _load_bg(self) -> pygame.Surface | None:
        path = os.path.join(IMAGES_DIR, "backgrounds", "吧台.png")
        if os.path.exists(path):
            img = pygame.image.load(path).convert()
            return pygame.transform.scale(img, (SCREEN_WIDTH, SCREEN_HEIGHT))
        return None

    def _try_bci_connect(self) -> bool:
        reader = BCIDataReader()
        return reader.connect()

    def _show_dialog(self, text: str) -> None:
        self._dialog_active = True
        self._dialog_text = text
        self._dialog_result = None
        self._dialog_click_frames = 0
        w = 160
        h = 50
        self._dialog_confirm_rect = pygame.Rect(
            SCREEN_WIDTH // 2 - w // 2,
            SCREEN_HEIGHT // 2 + 30,
            w,
            h,
        )

    def _start_game(self, control_key: str, click_frames: list) -> None:
        if control_key == "bci_normal":
            if self._try_bci_connect():
                self.result = "start"
                self.current_mode = "bci"
                self._control_mode = "bci"
                click_frames[0] = 15
            else:
                self._show_dialog("BCI头环未连接，将使用键盘控制")
        elif control_key == "keyboard":
            self.result = "start"
            self.current_mode = "bci"
            self._control_mode = "keyboard"
            click_frames[0] = 15
        elif control_key == "memory":
            self.result = "start_memory"
            self.current_mode = "bci"
            self._control_mode = "bci"
            click_frames[0] = 15

    def run(self) -> tuple[str | None, str, str]:
        click_frames = [0]

        while self.running:
            dt = self.clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    self.result = "quit"

                if self._dialog_active:
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if self._dialog_confirm_rect.collidepoint(event.pos):
                            self._dialog_active = False
                            self.result = "start"
                            self.current_mode = "bci"
                            self._control_mode = "bci_failed"
                            click_frames[0] = 15
                    elif event.type == pygame.KEYDOWN:
                        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            self._dialog_active = False
                            self.result = "start"
                            self.current_mode = "bci"
                            self._control_mode = "bci_failed"
                            click_frames[0] = 15
                    continue

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                        self.result = "quit"
                    elif event.key == pygame.K_RETURN or event.key == pygame.K_1:
                        self.start_btn.trigger_click()
                        self._start_game(self.mode_selector.current_key, click_frames)
                    elif event.key == pygame.K_2:
                        self.mode_selector.cycle_mode()
                    elif event.key == pygame.K_3:
                        self.settings_btn.trigger_click()
                        self.result = "settings"
                        click_frames[0] = 15
                else:
                    if self.badge.handle_event(event):
                        HistoryScreen(self.screen, self._history_games, profile=self._profile).run()
                        if self._profile:
                            self._history_games = list(self._profile.games_history)
                    if self.start_btn.handle_event(event):
                        self._start_game(self.mode_selector.current_key, click_frames)
                    mode = self.mode_selector.handle_event(event)
                    if mode:
                        self.current_mode = mode
                    if self.settings_btn.handle_event(event):
                        self.settings_btn.trigger_click()
                        self.result = "settings"
                        click_frames[0] = 15

            self._update(dt)
            self._draw()
            pygame.display.flip()

            if click_frames[0] > 0:
                click_frames[0] -= 1
                if click_frames[0] == 0:
                    if self.result == "settings":
                        settings_screen = GameSettingsScreen(self.screen, self.font, self.title_font)
                        settings_screen.run()
                        self.result = None
                    else:
                        self.running = False

        return self.result, self.current_mode, self._control_mode

    def _update(self, dt: float) -> None:
        self.badge.update(dt)
        self.start_btn.update(dt)
        self.mode_selector.update(dt)
        self.settings_btn.update(dt)

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

        title_offset = math.sin(self.title_phase) * 8
        title_chars = list("疯狂奶茶杯")
        char_spacing = 15
        char_surfs = [self.big_title_font.render(c, True, (255, 220, 150)) for c in title_chars]
        char_shadows = [self.big_title_font.render(c, True, (80, 40, 10)) for c in title_chars]
        total_w = sum(s.get_width() for s in char_surfs) + char_spacing * (len(char_surfs) - 1)

        tx = self.btn_cx - total_w // 2
        ty = self.title_y + title_offset - 3
        cx = tx
        for surf, shadow in zip(char_surfs, char_shadows):
            self.screen.blit(shadow, (cx + 3, ty + 3))
            self.screen.blit(surf, (cx, ty))
            cx += surf.get_width() + char_spacing

        sub_surf = self.font.render("接住食材 · 制作属于你的美味奶茶", True, (220, 200, 170))
        sw = sub_surf.get_width()
        self.screen.blit(sub_surf, (self.btn_cx - sw // 2, ty + 60))

        self.start_btn.draw(self.screen)
        self.mode_selector.draw(self.screen)
        self.settings_btn.draw(self.screen)

        if self._dialog_active:
            self._draw_dialog()

        hint = self.font.render("ESC 退出", True, (180, 180, 180))
        self.screen.blit(hint, (SCREEN_WIDTH - hint.get_width() - 20, SCREEN_HEIGHT - 35))
