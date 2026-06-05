"""模式选择器 - 循环切换控制模式并显示预览（辉光粒子风格）"""

from __future__ import annotations

import math
import random

import pygame

from config import CONTROL_MODES
from menu.components import ClickParticle, MenuItem


class ModePreviewDisplay:
    """模式预览显示框 - 鼠标靠近时显示模式列表"""

    def __init__(
        self,
        x: int,
        y: int,
        font: pygame.font.Font,
        small_font: pygame.font.Font,
        control_modes: list[dict],
        current_key: str = "bci_normal",
    ) -> None:
        self.x = x
        self.y = y
        self.font = font
        self.small_font = small_font
        self.control_modes = control_modes
        self.current_key = current_key
        self.alpha = 0
        self.target_alpha = 0
        self.width = 280
        self.height = 15 + len(self.control_modes) * (45 + 10)

    def update(self, dt: float = 0.016) -> None:
        self.alpha += (self.target_alpha - self.alpha) * 0.2

    def set_mode(self, mode_key: str) -> None:
        self.current_key = mode_key
        self.target_alpha = 200

    def hide(self) -> None:
        self.target_alpha = 0

    def draw(self, screen: pygame.Surface) -> None:
        if self.alpha < 5:
            return

        surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)

        pygame.draw.rect(
            surf,
            (30, 30, 40, int(self.alpha * 0.6)),
            (0, 0, self.width, self.height),
            border_radius=12,
        )
        pygame.draw.rect(
            surf,
            (255, 255, 255, int(self.alpha * 0.3)),
            (0, 0, self.width, self.height),
            2,
            border_radius=12,
        )

        btn_h = 45
        gap = 10
        start_y = 15

        for i, mode in enumerate(self.control_modes):
            key = mode["key"]
            name = mode["name"]
            enabled = mode["enabled"]
            color = mode["color"]
            is_active = key == self.current_key

            y = start_y + i * (btn_h + gap)

            if enabled:
                bg = (*color, int(self.alpha * 0.5))
                hov = (*color, int(self.alpha * 0.8))
                bg_color = hov if is_active else bg
            else:
                bg_color = (60, 60, 60, int(self.alpha * 0.35))

            pygame.draw.rect(surf, bg_color, (10, y, self.width - 20, btn_h), border_radius=8)

            if is_active and enabled:
                pygame.draw.rect(
                    surf,
                    (255, 255, 255, int(self.alpha * 0.8)),
                    (10, y, self.width - 20, btn_h),
                    2,
                    border_radius=8,
                )

            text_alpha = int(self.alpha * 0.6) if not enabled else int(self.alpha)
            text_color = (160, 160, 160) if not enabled else (255, 255, 255)

            display_name = name
            if not enabled:
                display_name = f"{name}（开发中）"

            txt = self.font.render(display_name, True, text_color)
            txt.set_alpha(text_alpha)
            surf.blit(
                txt,
                (
                    10 + (self.width - 20 - txt.get_width()) // 2,
                    y + (btn_h - txt.get_height()) // 2,
                ),
            )

        screen.blit(surf, (self.x, self.y))


class ModeSelector(MenuItem):
    """模式选择按钮 - 辉光风格，点击循环切换控制模式，按钮显示当前模式名"""

    def __init__(
        self,
        x: int,
        y: int,
        font: pygame.font.Font,
        title_font: pygame.font.Font,
        control_modes: list[dict] | None = None,
    ) -> None:
        self.control_modes = control_modes or CONTROL_MODES
        self.current_index = 0
        self.font = font
        self.title_font = title_font
        self.x = x
        self.y = y

        self.hovered = False
        self.scale_t = 0.0
        self.click_t = 0.0
        self.ripple = 0.0
        self.pulse_t = 0.0

        padding = (50, 14)
        self.padding = padding
        self.radius = 25

        self._rebuild_text_surf()
        w = self._text_surf.get_width() + padding[0] * 2
        h = self._text_surf.get_height() + padding[1] * 2
        self.rect = pygame.Rect(x - w // 2, y - h // 2, w, h)

        self.click_particles: list[ClickParticle] = []
        self.glow_particles: list[ClickParticle] = []
        self.info_display = ModePreviewDisplay(
            self.rect.right + 20,
            self.rect.top - 10,
            font,
            font,
            self.control_modes,
            self.control_modes[self.current_index]["key"],
        )

    @property
    def current_key(self) -> str:
        return self.control_modes[self.current_index]["key"]

    @property
    def current_name(self) -> str:
        return self.control_modes[self.current_index]["name"]

    @property
    def current_enabled(self) -> bool:
        return self.control_modes[self.current_index]["enabled"]

    def _rebuild_text_surf(self) -> None:
        mode = self.control_modes[self.current_index]
        name = mode["name"]
        enabled = mode["enabled"]
        display_text = name
        color = (255, 255, 255) if enabled else (130, 130, 130)
        self._text_surf = self.title_font.render(display_text, True, color)

    def _update_text(self) -> None:
        self._rebuild_text_surf()
        w = self._text_surf.get_width() + self.padding[0] * 2
        h = self._text_surf.get_height() + self.padding[1] * 2
        old_center = self.rect.center
        self.rect = pygame.Rect(old_center[0] - w // 2, old_center[1] - h // 2, w, h)
        self.info_display = ModePreviewDisplay(
            self.rect.right + 20,
            self.rect.top - 10,
            self.font,
            self.font,
            self.control_modes,
            self.control_modes[self.current_index]["key"],
        )

    @property
    def _glow_color(self) -> tuple[int, int, int]:
        return (255, 180, 100)

    @property
    def _bg_color_info(self) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
        if not self.current_enabled:
            return ((55, 35, 25), (75, 50, 35))
        return ((50, 25, 12), (85, 40, 20))

    def cycle_mode(self) -> str:
        self.current_index = (self.current_index + 1) % len(self.control_modes)
        self.click_t = 1.0
        self.ripple = 1.0
        self._update_text()
        glow = self._glow_color

        for _ in range(20):
            self.click_particles.append(ClickParticle(self.rect.centerx, self.rect.centery, glow))
        for _ in range(10):
            self.click_particles.append(ClickParticle(self.rect.centerx, self.rect.centery, (255, 255, 255)))

        return self.current_key

    def update(self, dt: float = 0.016) -> None:
        target = 1.0 if self.hovered else 0.0
        self.scale_t += (target - self.scale_t) * 0.15
        if self.click_t > 0:
            self.click_t -= dt * 3
        if self.ripple > 0:
            self.ripple -= dt * 2

        self.pulse_t += dt * 2.5
        if self.hovered and random.random() < 0.3:
            angle = random.uniform(0, 2 * math.pi)
            r = random.uniform(self.rect.width / 2, self.rect.width / 2 + 8)
            px = self.rect.centerx + math.cos(angle) * r
            py = self.rect.centery + math.sin(angle) * r
            self.glow_particles.append(ClickParticle(px, py, self._glow_color))

        self.click_particles = [p for p in self.click_particles if p.update(dt)]
        self.glow_particles = [p for p in self.glow_particles if p.update(dt)]
        self.info_display.update(dt)

    def draw(self, screen: pygame.Surface) -> None:
        pulse = math.sin(self.pulse_t) * 0.5 + 0.5
        glow = self._glow_color
        enabled = self.current_enabled

        glow_alpha = int(30 + pulse * 50) if enabled else int(10 + pulse * 15)
        glow_size = int(8 + pulse * 12)
        glow_surf = pygame.Surface(
            (self.rect.width + glow_size * 2, self.rect.height + glow_size * 2),
            pygame.SRCALPHA,
        )
        for layer in range(3):
            layer_size = glow_size - layer * 3
            layer_alpha = glow_alpha // (layer + 1)
            pygame.draw.rect(
                glow_surf,
                (*glow, layer_alpha),
                (0, 0, glow_surf.get_width(), glow_surf.get_height()),
                border_radius=self.radius + layer_size,
            )
        screen.blit(
            glow_surf,
            (self.rect.x - glow_size, self.rect.y - glow_size),
        )

        s = 1.0 + 0.06 * self.scale_t
        w = int(self.rect.width * s)
        h = int(self.rect.height * s)
        surf = pygame.Surface((w, h), pygame.SRCALPHA)

        bg_color, hover_color = self._bg_color_info
        color = hover_color if self.hovered else bg_color

        border_color = hover_color if self.hovered else glow
        border_alpha = int(180 + pulse * 75) if enabled else int(60 + pulse * 25)

        for i in range(4, 0, -1):
            thick = i * 2
            alpha = border_alpha // (i + 1)
            pygame.draw.rect(
                surf,
                (*border_color, alpha),
                (-i, -i, w + i * 2, h + i * 2),
                thick,
                border_radius=int(self.radius * s + i),
            )

        pygame.draw.rect(
            surf,
            (*border_color, border_alpha),
            (0, 0, w, h),
            3,
            border_radius=int(self.radius * s),
        )

        bg_a = 180 + (1 if self.hovered else 0) * 40
        if not enabled:
            bg_a = 80
        pygame.draw.rect(surf, (*color, bg_a), (2, 2, w - 4, h - 4), border_radius=int(self.radius * s - 1))

        if self.click_t > 0:
            click_surf = pygame.Surface((w, h), pygame.SRCALPHA)
            click_alpha = int(self.click_t * 150)
            pygame.draw.rect(
                click_surf,
                (*glow, click_alpha),
                (0, 0, w, h),
                border_radius=int(self.radius * s),
            )
            surf.blit(click_surf, (0, 0))

        if self.ripple > 0:
            ripple_r = int((1 - self.ripple) * max(w, h) * 0.3)
            ripple_surf = pygame.Surface((ripple_r * 2, ripple_r * 2), pygame.SRCALPHA)
            pygame.draw.circle(
                ripple_surf,
                (255, 255, 255, int(self.ripple * 80)),
                (ripple_r, ripple_r),
                ripple_r,
            )
            screen.blit(
                ripple_surf,
                (self.rect.centerx - ripple_r, self.rect.centery - ripple_r),
            )

        if enabled:
            text_glow = self.title_font.render(
                self.control_modes[self.current_index]["name"],
                True,
                (
                    min(255, glow[0] + 60),
                    min(255, glow[1] + 40),
                    min(255, glow[2] + 30),
                ),
            )
            text_glow.set_alpha(int(100 + pulse * 60))
            tw = text_glow.get_width()
            th = text_glow.get_height()
            surf.blit(text_glow, ((w - tw) // 2 + 1, (h - th) // 2 + 1))

        tw = self._text_surf.get_width()
        th = self._text_surf.get_height()
        surf.blit(self._text_surf, ((w - tw) // 2, (h - th) // 2))

        screen.blit(surf, (self.rect.centerx - w // 2, self.rect.centery - h // 2))

        for p in self.glow_particles:
            p.draw(screen)
        for p in self.click_particles:
            p.draw(screen)

        if self.hovered:
            self.info_display.set_mode(self.control_modes[self.current_index]["key"])
            self.info_display.draw(screen)

    def handle_event(self, event: pygame.event.Event) -> str | None:  # type: ignore[override]
        if event.type == pygame.MOUSEMOTION:
            was_hovered = self.hovered
            self.hovered = self.rect.collidepoint(event.pos)
            if self.hovered:
                self.info_display.set_mode(self.control_modes[self.current_index]["key"])
            elif was_hovered:
                self.info_display.hide()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                return self.cycle_mode()
        return None
