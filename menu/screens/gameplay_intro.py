"""玩法介绍弹窗"""

from __future__ import annotations

import math
import os
import random

import pygame

from config import IMAGES_DIR, INGREDIENT_IMGS, SCREEN_HEIGHT, SCREEN_WIDTH
from game.font_utils import load_chinese_font

_INTRO_PANEL_IMG = os.path.join(IMAGES_DIR, "other", "玩法介绍面板.png")

_REQUIRED_INGREDIENTS = ["牛奶", "红茶", "绿茶"]
_OPTIONAL_INGREDIENTS = ["珍珠", "椰果"]

_PAGE_TITLES = ["游戏规则", "食材说明", "四种模式"]


class _Particle:
    __slots__ = ("life", "vx", "vy", "x", "y")

    def __init__(self, x: float, y: float) -> None:
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(15, 35)
        self.x = x + math.cos(angle) * dist
        self.y = y + math.sin(angle) * dist
        speed = random.uniform(0.5, 1.5)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed - 1.5
        self.life = 1.0

    def update(self, dt: float) -> bool:
        self.life -= 2.5 * dt
        if self.life <= 0:
            return True
        self.x += self.vx * dt * 60
        self.y += self.vy * dt * 60
        self.vy += 0.15 * dt * 60
        return False


class GameplayIntroScreen:
    """玩法介绍弹窗"""

    def __init__(self, screen: pygame.Surface, bg: pygame.Surface | None = None) -> None:
        self.screen = screen
        self._bg = bg
        self.clock = pygame.time.Clock()
        self.running = True

        self._title_font = load_chinese_font(44)
        self._sub_font = load_chinese_font(32)
        self._body_font = load_chinese_font(30)
        self._small_font = load_chinese_font(20)
        self._btn_font = load_chinese_font(36)

        pw, ph = 1000, 612
        self._panel_x = (SCREEN_WIDTH - pw) // 2
        self._panel_y = (SCREEN_HEIGHT - ph) // 2
        self._panel_rect = pygame.Rect(self._panel_x, self._panel_y, pw, ph)

        self._panel_img = None
        if os.path.exists(_INTRO_PANEL_IMG):
            try:
                img = pygame.image.load(_INTRO_PANEL_IMG).convert_alpha()
                self._panel_img = pygame.transform.smoothscale(img, (pw, ph))
            except Exception:
                pass

        self._current_page = 0

        arrow_size = 42
        cy = self._panel_y + ph // 2
        self._left_arrow_rect = pygame.Rect(self._panel_x + 15, cy - arrow_size // 2, arrow_size, arrow_size)
        self._right_arrow_rect = pygame.Rect(self._panel_x + pw - 15 - arrow_size, cy - arrow_size // 2, arrow_size, arrow_size)

        close_size = 36
        self._close_rect = pygame.Rect(self._panel_x + pw - close_size - 27, self._panel_y + 100, close_size, close_size)

        self._ing_img_size = 60
        self._ing_gap = 20
        self._particles: list[_Particle] = []
        self._req_positions: list[tuple[int, int]] = []

        self._wobble_time = 0.0
        self._load_ingredient_images()
        self._load_recipe_icon()

    def _load_ingredient_images(self) -> None:
        self._req_imgs: list[pygame.Surface] = []
        for name in _REQUIRED_INGREDIENTS:
            path = INGREDIENT_IMGS.get(name, "")
            img = self._load_scaled_ing(path)
            self._req_imgs.append(img)

        self._opt_imgs: list[pygame.Surface] = []
        for name in _OPTIONAL_INGREDIENTS:
            path = INGREDIENT_IMGS.get(name, "")
            img = self._load_scaled_ing(path)
            self._opt_imgs.append(img)

    def _load_scaled_ing(self, path: str) -> pygame.Surface:
        size = self._ing_img_size
        if path and os.path.exists(path):
            try:
                img = pygame.image.load(path).convert_alpha()
                return pygame.transform.smoothscale(img, (size, size))
            except Exception:
                pass
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(surf, (180, 180, 180), (size // 2, size // 2), size // 2)
        return surf

    def _load_recipe_icon(self) -> None:
        path = INGREDIENT_IMGS.get("秘方", "")
        self._recipe_icon = None
        if path and os.path.exists(path):
            try:
                img = pygame.image.load(path).convert_alpha()
                icon_h = self._body_font.get_height()
                self._recipe_icon = pygame.transform.smoothscale(img, (icon_h, icon_h))
            except Exception:
                pass

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(60) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return
                    if event.key == pygame.K_LEFT and self._current_page > 0:
                        self._current_page -= 1
                    elif event.key == pygame.K_RIGHT and self._current_page < 2:
                        self._current_page += 1
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self._close_rect.collidepoint(event.pos):
                        return
                    if self._current_page > 0 and self._left_arrow_rect.collidepoint(event.pos):
                        self._current_page -= 1
                    elif self._current_page < 2 and self._right_arrow_rect.collidepoint(event.pos):
                        self._current_page += 1

            self._update_particles(dt)
            self._draw()
            pygame.display.flip()

    def _content_area(self) -> tuple[int, int, int, int]:
        px, py, pw, ph = self._panel_rect
        margin = 70
        return px + margin, py + 115, pw - margin * 2, ph - 115 - 60

    def _draw_close_button(self) -> None:
        r = self._close_rect
        mx, my = pygame.mouse.get_pos()
        hover = r.collidepoint(mx, my)
        color = (200, 50, 50) if hover else (140, 30, 30)
        text = self._btn_font.render("X", True, color)
        self.screen.blit(text, (r.centerx - text.get_width() // 2, r.centery - text.get_height() // 2))

    def _draw_arrow(self, rect: pygame.Rect, direction: str) -> None:
        mx, my = pygame.mouse.get_pos()
        hover = rect.collidepoint(mx, my)
        color = (120, 60, 30) if hover else (80, 40, 20)
        text = self._btn_font.render(direction, True, color)
        self.screen.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))

    def _draw_page_indicator(self) -> None:
        px, py, pw, ph = self._panel_rect
        dot_y = py + ph - 30
        total = 3
        for i in range(total):
            cx = px + pw // 2 - (total - 1) * 12 + i * 24
            if i == self._current_page:
                pygame.draw.circle(self.screen, (80, 30, 20), (cx, dot_y), 5)
            else:
                pygame.draw.circle(self.screen, (160, 150, 140), (cx, dot_y), 4)

    def _draw_page1(self, cx: int, y: int) -> None:
        rules = [
            ("一杯奶茶制作时间为20 秒，每杯奶茶需要至少接住一个必接食材", "否则\n整杯收益为 0。"),
            ("专注力指数越高，单杯收益越高；持续保持高专注力下","还会触发神秘\n加倍秘方。"),
            ("累计收益达到一定值，", "将提升店面等级，解锁更多食材！！！"),
            ("头环失灵时，","按空格键切换为键盘操控，不要移动头环位置。"),
        ]
        left_margin = self._panel_x + 60
        normal_color = (20, 20, 30)
        red_color = (160, 20, 20)
        font = self._body_font
        for i, (text, red_text) in enumerate(rules):
            prefix = f"{i + 1}. "
            surf = font.render(prefix + text, True, normal_color)
            self.screen.blit(surf, (left_margin, y))
            cx_offset = left_margin + surf.get_width()
            if red_text:
                parts = red_text.split("\n")
                surf2 = font.render(parts[0], True, red_color)
                self.screen.blit(surf2, (cx_offset, y))
                y += font.get_height() + 12
                extra_parts = parts[1:]
                for j, rp in enumerate(extra_parts):
                    if rp:
                        surf3 = font.render(rp, True, red_color)
                        self.screen.blit(surf3, (left_margin, y))
                        if i == 1 and j == len(extra_parts) - 1 and self._recipe_icon:
                            icon_x = left_margin + surf3.get_width() + 8
                            icon_y = y
                            wobble_x = int(math.sin(self._wobble_time * 4.0) * 1.5)
                            wobble_y = int(math.cos(self._wobble_time * 3.5) * 2)
                            wobble_angle = math.sin(self._wobble_time * 3.0) * 3
                            rotated = pygame.transform.rotozoom(self._recipe_icon, wobble_angle, 1.0)
                            rx = icon_x + wobble_x - (rotated.get_width() - self._recipe_icon.get_width()) // 2
                            ry = icon_y + wobble_y - (rotated.get_height() - self._recipe_icon.get_height()) // 2
                            self.screen.blit(rotated, (rx, ry))
                        y += font.get_height() + 12
            else:
                y += font.get_height() + 12

    def _draw_page2(self, cx: int, y: int) -> None:
        hint1 = self._body_font.render("金色粒子标记为必接，无标记为选接", True, (20, 20, 30))
        self.screen.blit(hint1, (cx - hint1.get_width() // 2, y))
        y += hint1.get_height() + 20

        opt_label = self._sub_font.render("选接", True, (30, 90, 30))
        req_label = self._sub_font.render("必接", True, (160, 30, 20))
        label_gap = 420
        self.screen.blit(opt_label, (cx - label_gap - opt_label.get_width() // 2, y))
        self.screen.blit(req_label, (cx + label_gap - req_label.get_width() // 2, y))
        y += opt_label.get_height() + 16

        opt_x = cx - label_gap - (len(self._opt_imgs) * (self._ing_img_size + self._ing_gap) - self._ing_gap) // 2
        req_x = cx + label_gap - (len(self._req_imgs) * (self._ing_img_size + self._ing_gap) - self._ing_gap) // 2

        self._req_positions = []
        for i, img in enumerate(self._opt_imgs):
            ix = opt_x + i * (self._ing_img_size + self._ing_gap)
            self.screen.blit(img, (ix, y))
        for i, img in enumerate(self._req_imgs):
            ix = req_x + i * (self._ing_img_size + self._ing_gap)
            self.screen.blit(img, (ix, y))
            self._req_positions.append((ix + self._ing_img_size // 2, y + self._ing_img_size // 2))
        y += self._ing_img_size + 30

        rule1 = self._body_font.render("必接：必须接住，否则整杯 0 分", True, (160, 20, 20))
        rule2 = self._body_font.render("选接：接的越多，收益越高", True, (30, 80, 30))
        self.screen.blit(rule1, (cx - rule1.get_width() // 2, y))
        y += rule1.get_height() + 8
        self.screen.blit(rule2, (cx - rule2.get_width() // 2, y))

    def _draw_page3(self, cx: int, y: int) -> None:
        modes = [
            ("原萃", "专注力直接控制", "驱动食材速度"),
            ("特调", "自适应难度调节", "玩家个性化体验"),
            ("忆调", "先记忆食材顺序", "再依次接住"),
            ("训练", "原萃 + 特调 + 忆调", "三阶段组合训练"),
        ]
        col_gap = 280
        row_gap = 180
        base_x = cx - col_gap // 2 - 80

        for idx, (name, line1, line2) in enumerate(modes):
            mx = base_x + (idx % 2) * col_gap
            my = y + (idx // 2) * row_gap

            name_surf = self._sub_font.render(name, True, (80, 30, 20))
            self.screen.blit(name_surf, (mx - name_surf.get_width() // 2, my))
            my += name_surf.get_height() + 8

            for line in (line1, line2):
                line_surf = self._body_font.render(line, True, (20, 20, 30))
                self.screen.blit(line_surf, (mx - line_surf.get_width() // 2, my))
                my += line_surf.get_height() + 4

    def _update_particles(self, dt: float) -> None:
        self._wobble_time += dt
        if self._current_page != 1:
            self._particles.clear()
            return

        for pos in self._req_positions:
            if len(self._particles) < 80:
                for _ in range(2):
                    self._particles.append(_Particle(float(pos[0]), float(pos[1])))

        self._particles = [p for p in self._particles if not p.update(dt)]

    def _draw(self) -> None:
        if self._bg is not None:
            self.screen.blit(self._bg, (0, 0))
        else:
            self.screen.fill((30, 30, 40))

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        if self._panel_img:
            self.screen.blit(self._panel_img, self._panel_rect.topleft)
        else:
            _px, _py, _pw, _ph = self._panel_rect
            pygame.draw.rect(self.screen, (30, 28, 20, 230), self._panel_rect, border_radius=16)
            pygame.draw.rect(self.screen, (200, 160, 100, 180), self._panel_rect, 3, border_radius=16)

        _cx, y_area, _w, _h = self._content_area()
        cx = self._panel_rect.centerx
        y = y_area + 20

        if self._current_page == 0:
            self._draw_page1(cx, y + 10)
        elif self._current_page == 1:
            self._draw_page2(cx, y)
        else:
            self._draw_page3(cx, y)

        for p in self._particles:
            alpha = int(p.life * 255)
            if alpha > 0:
                r = int(2 + (1 - p.life) * 2)
                color = (255, 215, 0, alpha)
                surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                pygame.draw.circle(surf, color, (r, r), r)
                self.screen.blit(surf, (int(p.x - r), int(p.y - r)))

        if self._current_page > 0:
            self._draw_arrow(self._left_arrow_rect, "<")
        if self._current_page < 2:
            self._draw_arrow(self._right_arrow_rect, ">")

        self._draw_page_indicator()
        self._draw_close_button()
