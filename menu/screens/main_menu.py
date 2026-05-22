"""主菜单 - 游戏启动后的第一个界面"""

from __future__ import annotations

import math
import os
import random

import pygame

from config import (
    BADGE_IMGS,
    IMAGES_DIR,
    INGREDIENT_COLORS,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)
from game.font_utils import load_chinese_font
from menu.bci_button import GlowButton
from menu.components import Badge
from menu.mode_selector import ModeSelector
from menu.particles import FloatingItem, SteamParticle
from menu.screens.game_settings import GameSettingsScreen


class MainMenu:
    def __init__(self, screen: pygame.Surface, font: pygame.font.Font, title_font: pygame.font.Font) -> None:
        self.screen = screen
        self.font = font
        self.title_font = title_font
        self.big_title_font = load_chinese_font(64)
        self.clock = pygame.time.Clock()
        self.running = True
        self.result = None
        self.current_mode = "regular"

        self.bg = self._load_bg()
        self.badge = Badge(BADGE_IMGS, SCREEN_WIDTH - 85, 12, size=(80, 80))
        self.floating_items = [
            FloatingItem(SCREEN_WIDTH, SCREEN_HEIGHT, c)
            for c in list(INGREDIENT_COLORS.values()) + [(255, 180, 100)] * 3
        ]
        self.steam_particles = []
        self.steam_spawn_timer = 0

        # ==========================================
        # 按键布局参数
        # ==========================================
        cx = SCREEN_WIDTH // 2  # 按钮组水平中心：屏幕正中央
        cy = SCREEN_HEIGHT // 2  # 屏幕垂直中心
        btn_spacing = 105  # 按钮垂直间距（像素），数值越大按钮间距越大
        start_y = cy - 100  # 按钮 1 坐标：从中心往上偏移，让整体按钮组居中（已下调）
        # ==========================================

        self.start_btn = GlowButton(
            "开始游戏",
            cx,
            start_y,
            title_font,
            title_font,
            glow_color=(255, 160, 90),
            bg_color=(60, 30, 15),
            hover_color=(100, 50, 25),
            text_color=(255, 255, 255),
        )

        self.mode_selector = ModeSelector(
            cx,
            start_y + btn_spacing,
            font,
            title_font,
            mode_keys=["regular", "challenge", "creative"],
        )

        self.bci_btn = GlowButton(
            "脑机接口",
            cx,
            start_y + btn_spacing * 2,
            font,
            title_font,
            glow_color=(220, 150, 100),
            bg_color=(50, 25, 12),
            hover_color=(85, 40, 20),
            text_color=(255, 255, 255),
        )

        self.settings_btn = GlowButton(
            "游戏设置",
            cx,
            start_y + btn_spacing * 3,
            title_font,
            title_font,
            glow_color=(255, 190, 110),
            bg_color=(70, 35, 15),
            hover_color=(115, 55, 25),
            text_color=(255, 255, 255),
        )

        self.btn_cx = cx  # 保存按钮组水平中心，用于标题对齐

        self.title_y = start_y - 175
        self.title_phase = 0.0

    def _load_bg(self) -> pygame.Surface | None:
        """
        加载背景图片
        :return: 背景图片
        """
        path = os.path.join(IMAGES_DIR, "backgrounds", "吧台.png")
        if os.path.exists(path):
            img = pygame.image.load(path).convert()
            return pygame.transform.scale(img, (SCREEN_WIDTH, SCREEN_HEIGHT))
        return None

    def run(self) -> tuple[str | None, str]:
        click_frames = 0  # 点击后等待的帧数

        while self.running:
            dt = self.clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    self.result = "quit"
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                        self.result = "quit"
                    elif event.key == pygame.K_RETURN or event.key == pygame.K_1:
                        self.start_btn.trigger_click()
                        self.result = "start"
                        click_frames = 15
                    elif event.key == pygame.K_2:
                        self.mode_selector.cycle_mode()
                    elif event.key == pygame.K_3:
                        self.settings_btn.trigger_click()
                        self.result = "settings"
                        click_frames = 15  # 等粒子播完再打开设置页
                else:
                    if self.badge.handle_event(event):
                        pass
                    if self.start_btn.handle_event(event):
                        self.result = "start"
                        click_frames = 15
                    mode = self.mode_selector.handle_event(event)
                    if mode:
                        self.current_mode = mode
                    if self.bci_btn.handle_event(event):
                        self.result = "start"
                        self.current_mode = "bci"
                        click_frames = 15
                    if self.settings_btn.handle_event(event):
                        self.settings_btn.trigger_click()
                        self.result = "settings"
                        click_frames = 15  # 等粒子播完再打开设置页

            self._update(dt)
            self._draw(dt)
            pygame.display.flip()

            # 点击后延迟 15 帧（约 0.25 秒），让粒子动画播放完
            if click_frames > 0:
                click_frames -= 1
                if click_frames == 0:
                    if self.result == "settings":
                        settings_screen = GameSettingsScreen(self.screen, self.font, self.title_font)
                        settings_screen.run()
                        self.result = None  # 返回主菜单，继续运行
                    else:
                        self.running = False

        return self.result, self.current_mode

    def _update(self, dt: float) -> None:
        self.badge.update(dt)
        self.start_btn.update(dt)
        self.mode_selector.update(dt)
        self.bci_btn.update(dt)
        self.settings_btn.update(dt)

        for item in self.floating_items:
            item.update()

        # 注释：取消背景呼吸缩放效果
        # self.bg_breathe_phase += dt * 0.5
        # self.bg_breathe_scale = 1.0 + math.sin(self.bg_breathe_phase) * 0.008

        self.steam_spawn_timer += dt
        if self.steam_spawn_timer > 0.05:
            self.steam_spawn_timer = 0
            spawn_x = random.uniform(SCREEN_WIDTH * 0.3, SCREEN_WIDTH * 0.7)
            self.steam_particles.append(SteamParticle(int(spawn_x), SCREEN_HEIGHT + 10))
        self.steam_particles = [p for p in self.steam_particles if p.update()]

        self.title_phase += dt * 2

    def _draw(self, dt: float) -> None:
        # 取消背景呼吸缩放效果，直接绘制
        if self.bg:
            self.screen.blit(self.bg, (0, 0))
        else:
            self.screen.fill((255, 240, 220))

        # 增加半透明遮罩层，提升标题和按钮的可读性
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 25))  # 参数说明：(r, g, b, a) 表示 RGBA 颜色
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
        self.screen.blit(sub_surf, (self.btn_cx - sw // 2, ty + 60))  # 副标题水平对齐到按钮组

        self.start_btn.draw(self.screen)
        self.mode_selector.draw(self.screen)
        self.bci_btn.draw(self.screen)
        self.settings_btn.draw(self.screen)

        hint = self.font.render("ESC 退出", True, (180, 180, 180))
        self.screen.blit(hint, (SCREEN_WIDTH - hint.get_width() - 20, SCREEN_HEIGHT - 35))
