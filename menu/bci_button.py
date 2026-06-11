"""通用辉光按钮 - 霓虹发光 + 粒子效果风格（原 BCI 模式按钮改造为通用版）"""

from __future__ import annotations

import math
import random

import pygame

from menu.components import ClickParticle, MenuItem


class GlowButton(MenuItem):
    """通用辉光按钮 - 脉冲光晕边框 + 悬停粒子 + 发光文字

    参数:
        text: 按钮文字
        x, y: 按钮中心坐标
        font: 按钮字体
        title_font: 标题字体
        glow_color: 辉光颜色 (R, G, B)，粒子、边框、光晕均基于此色
        bg_color: 按钮底色 (R, G, B)
        hover_color: 悬停时的底色
        text_color: 文字颜色
    """

    def __init__(
        self,
        text: str,
        x: int,
        y: int,
        font: pygame.font.Font,
        title_font: pygame.font.Font,
        glow_color: tuple[int, int, int] = (0, 200, 255),
        bg_color: tuple[int, int, int] = (0, 40, 80),
        hover_color: tuple[int, int, int] = (0, 80, 150),
        text_color: tuple[int, int, int] = (255, 255, 255),
        width: int | None = None,
        padding: tuple[int, int] | None = None,
    ) -> None:
        self.text = text
        self.font = font
        self.title_font = title_font
        self.glow_color = glow_color
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.text_color = text_color
        self.padding = padding if padding is not None else (50, 18)
        self.radius = 25

        self._text_surf = title_font.render(text, True, text_color)
        w = width if width is not None else self._text_surf.get_width() + self.padding[0] * 2
        h = self._text_surf.get_height() + self.padding[1] * 2
        self.rect = pygame.Rect(x - w // 2, y - h // 2, w, h)

        self.hovered = False
        self.scale_t = 0.0
        self.click_t = 0.0
        self.click_particles: list[ClickParticle] = []
        self.pulse_t = 0.0
        self.glow_particles: list[ClickParticle] = []

    def update(self, dt: float = 0.016) -> None:
        target = 1.0 if self.hovered else 0.0
        self.scale_t += (target - self.scale_t) * 0.15
        if self.click_t > 0:
            self.click_t -= dt * 3
        self.click_particles = [p for p in self.click_particles if p.update(dt)]

        self.pulse_t += dt * 2.5
        if self.hovered and random.random() < 0.3:
            angle = random.uniform(0, 2 * math.pi)
            r = random.uniform(self.rect.width / 2, self.rect.width / 2 + 8)
            px = self.rect.centerx + math.cos(angle) * r
            py = self.rect.centery + math.sin(angle) * r
            self.glow_particles.append(ClickParticle(px, py, self.glow_color))
        self.glow_particles = [p for p in self.glow_particles if p.update(dt)]

    def draw(self, screen: pygame.Surface) -> None:
        pulse = math.sin(self.pulse_t) * 0.5 + 0.5
        glow_alpha = int(30 + pulse * 50)

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
                (*self.glow_color, layer_alpha),
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

        border_color = self.hover_color if self.hovered else self.glow_color
        border_alpha = int(180 + pulse * 75)

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

        bg = (*self.bg_color, (180 + (1 if self.hovered else 0) * 40))
        pygame.draw.rect(surf, bg, (2, 2, w - 4, h - 4), border_radius=int(self.radius * s - 1))

        if self.click_t > 0:
            click_surf = pygame.Surface((w, h), pygame.SRCALPHA)
            click_alpha = int(self.click_t * 150)
            pygame.draw.rect(
                click_surf,
                (*self.glow_color, click_alpha),
                (0, 0, w, h),
                border_radius=int(self.radius * s),
            )
            surf.blit(click_surf, (0, 0))

        text_glow = self.title_font.render(
            self.text,
            True,
            (
                min(255, self.glow_color[0] + 80),
                min(255, self.glow_color[1] + 60),
                min(255, self.glow_color[2] + 40),
            ),
        )
        text_glow.set_alpha(int(100 + pulse * 60))
        tw = text_glow.get_width()
        th = text_glow.get_height()
        surf.blit(text_glow, ((w - tw) // 2 + 1, (h - th) // 2 + 1))

        surf.blit(self._text_surf, ((w - tw) // 2, (h - th) // 2))

        screen.blit(surf, (self.rect.centerx - w // 2, self.rect.centery - h // 2))

        for p in self.glow_particles:
            p.draw(screen)
        for p in self.click_particles:
            p.draw(screen)

    def trigger_click(self) -> None:
        self.click_t = 1.0
        for _ in range(30):
            self.click_particles.append(ClickParticle(self.rect.centerx, self.rect.centery, self.glow_color))
        for _ in range(15):
            self.click_particles.append(ClickParticle(self.rect.centerx, self.rect.centery, (255, 255, 255)))


class BCIModeButton(GlowButton):
    """BCI 模式按钮 - 保持向后兼容（默认蓝色辉光）"""

    def __init__(self, text: str, x: int, y: int, font: pygame.font.Font, title_font: pygame.font.Font) -> None:
        super().__init__(
            text=text,
            x=x,
            y=y,
            font=font,
            title_font=title_font,
            glow_color=(0, 200, 255),
            bg_color=(0, 40, 80),
            hover_color=(0, 80, 150),
            text_color=(255, 255, 255),
        )
