"""BCI模式按钮 - 霓虹发光风格"""

from __future__ import annotations

import math
import random

import pygame

from menu.components import ClickParticle, MenuItem


class BCIModeButton(MenuItem):
    """脑机接口模式按钮 - 霓虹发光效果，半透明底色 + 脉冲光晕边框"""

    def __init__(self, text: str, x: int, y: int, font: pygame.font.Font, title_font: pygame.font.Font) -> None:
        self.text = text
        self.font = font
        self.title_font = title_font
        self.bg_color = (0, 40, 80)
        self.hover_color = (0, 80, 150)
        self.text_color = (255, 255, 255)
        self.padding = (50, 18)
        self.radius = 25

        self._text_surf = title_font.render("脑机接口", True, (255, 255, 255))
        w = self._text_surf.get_width() + self.padding[0] * 2
        h = self._text_surf.get_height() + self.padding[1] * 2
        self.rect = pygame.Rect(x - w // 2, y - h // 2, w, h)

        self.hovered = False
        self.scale_t = 0.0
        self.click_t = 0.0
        self.click_particles = []
        self.pulse_t = 0.0
        self.glow_particles = []

    def update(self, dt: float = 0.016) -> None:
        target = 1.0 if self.hovered else 0.0
        self.scale_t += (target - self.scale_t) * 0.15
        if self.click_t > 0:
            self.click_t -= dt * 3
        self.click_particles = [p for p in self.click_particles if p.update(dt)]

        self.pulse_t += dt * 2.5
        if self.hovered and random.random() < 0.3:
            angle = random.uniform(0, 2 * math.pi)
            r = random.uniform(self.rect.width / 2, self.rect.width / 2 + 8)  # 缩小粒子生成范围
            px = self.rect.centerx + math.cos(angle) * r
            py = self.rect.centery + math.sin(angle) * r
            self.glow_particles.append(ClickParticle(px, py, (0, 200, 255)))
        self.glow_particles = [p for p in self.glow_particles if p.update(dt)]

    def draw(self, screen: pygame.Surface) -> None:
        pulse = math.sin(self.pulse_t) * 0.5 + 0.5
        glow_alpha = int(30 + pulse * 50)

        # 霓虹光晕外层（大范围半透明）
        glow_size = int(8 + pulse * 12)
        glow_surf = pygame.Surface(
            (self.rect.width + glow_size * 2, self.rect.height + glow_size * 2),
            pygame.SRCALPHA,
        )
        # 多层光晕叠加
        for layer in range(3):
            layer_size = glow_size - layer * 3
            layer_alpha = glow_alpha // (layer + 1)
            pygame.draw.rect(
                glow_surf,
                (0, 180, 255, layer_alpha),
                (0, 0, glow_surf.get_width(), glow_surf.get_height()),
                border_radius=self.radius + layer_size,
            )
        screen.blit(
            glow_surf,
            (self.rect.x - glow_size, self.rect.y - glow_size),
        )

        # 霓虹边框（多层发光线）
        s = 1.0 + 0.06 * self.scale_t
        w = int(self.rect.width * s)
        h = int(self.rect.height * s)
        surf = pygame.Surface((w, h), pygame.SRCALPHA)

        border_color = (0, 200, 255) if self.hovered else (0, 150, 220)
        border_alpha = int(180 + pulse * 75)

        # 外层粗边框（扩散光）
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

        # 内层细边框（明亮主线）
        pygame.draw.rect(
            surf,
            (*border_color, border_alpha),
            (0, 0, w, h),
            3,
            border_radius=int(self.radius * s),
        )

        # 底色（半透明深色）
        bg = (*self.bg_color, int(180 + self.hovered * 40))
        pygame.draw.rect(surf, bg, (2, 2, w - 4, h - 4), border_radius=int(self.radius * s - 1))

        # 点击反馈
        if self.click_t > 0:
            click_surf = pygame.Surface((w, h), pygame.SRCALPHA)
            click_alpha = int(self.click_t * 150)
            pygame.draw.rect(
                click_surf,
                (0, 220, 255, click_alpha),
                (0, 0, w, h),
                border_radius=int(self.radius * s),
            )
            surf.blit(click_surf, (0, 0))

        # 文字发光效果
        text_glow = self.title_font.render("脑机接口", True, (150, 230, 255))
        text_glow.set_alpha(int(100 + pulse * 60))
        tw = text_glow.get_width()
        th = text_glow.get_height()
        surf.blit(text_glow, ((w - tw) // 2 + 1, (h - th) // 2 + 1))

        # 主文字
        surf.blit(self._text_surf, ((w - tw) // 2, (h - th) // 2))

        screen.blit(surf, (self.rect.centerx - w // 2, self.rect.centery - h // 2))

        # 发光粒子
        for p in self.glow_particles:
            p.draw(screen)
        for p in self.click_particles:
            p.draw(screen)

    def trigger_click(self) -> None:
        self.click_t = 1.0
        for _ in range(30):
            self.click_particles.append(ClickParticle(self.rect.centerx, self.rect.centery, (0, 200, 255)))
        for _ in range(15):
            self.click_particles.append(ClickParticle(self.rect.centerx, self.rect.centery, (255, 255, 255)))
