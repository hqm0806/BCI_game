"""训练计划页面"""

from __future__ import annotations

import os

import pygame

from config import SCREEN_HEIGHT, SCREEN_WIDTH, SETTINGS_PANEL_IMG
from menu.components import MenuItem

_CTRL_WIDTH = 260
_CTRL_LEFT = SCREEN_WIDTH // 2 - _CTRL_WIDTH // 2 - 100
_LABEL_RIGHT = _CTRL_LEFT - 20

_last_values: dict[str, int] = {}


class StageSlider:
    """阶段滑轨组件（整数 0-10，步长 1）"""

    def __init__(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
        cx: int,
        cy: int,
        label: str,
        default_value: int = 0,
    ) -> None:
        self.screen = screen
        self.font = font
        self.track_width = _CTRL_WIDTH
        self.track_height = 6
        self.track_x = _CTRL_LEFT
        self.track_y = cy
        self.handle_radius = 12
        self._min = 0
        self._max = 10
        self._value = max(self._min, min(self._max, default_value))
        self._dragging = False
        self._label_surf = font.render(label, True, (40, 40, 40))
        self.label_x = _LABEL_RIGHT - self._label_surf.get_width()

    @property
    def value(self) -> int:
        return self._value

    @value.setter
    def value(self, v: int) -> None:
        self._value = max(self._min, min(self._max, v))

    def _pos_to_value(self, mx: int) -> int:
        ratio = max(0.0, min(1.0, (mx - self.track_x) / self.track_width))
        return int(round(ratio * (self._max - self._min) + self._min))

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            ratio = (self._value - self._min) / (self._max - self._min)
            hx = self.track_x + int(ratio * self.track_width)
            hy = self.track_y
            if (mx - hx) ** 2 + (my - hy) ** 2 <= (self.handle_radius + 6) ** 2:
                self._dragging = True
                return True
            if (
                self.track_x - self.handle_radius <= mx <= self.track_x + self.track_width + self.handle_radius
                and abs(my - self.track_y) <= self.handle_radius + 6
            ):
                self._dragging = True
                self._value = self._pos_to_value(mx)
                return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._dragging = False
        elif event.type == pygame.MOUSEMOTION and self._dragging:
            mx, _ = event.pos
            self._value = self._pos_to_value(mx)
            return True
        return False

    def draw(self) -> None:
        ly = self.track_y - self._label_surf.get_height() // 2
        self.screen.blit(self._label_surf, (self.label_x, ly))

        val_text = self.font.render(f"{self._value}min", True, (40, 40, 40))
        val_x = self.track_x + self.track_width + 20
        vy = self.track_y - val_text.get_height() // 2
        self.screen.blit(val_text, (val_x, vy))

        track_rect = pygame.Rect(
            self.track_x, self.track_y - self.track_height // 2,
            self.track_width, self.track_height,
        )
        pygame.draw.rect(self.screen, (60, 60, 70), track_rect, border_radius=4)

        ratio = (self._value - self._min) / (self._max - self._min)
        filled_w = int(ratio * self.track_width)
        if filled_w > 0:
            filled_rect = pygame.Rect(
                self.track_x, self.track_y - self.track_height // 2,
                filled_w, self.track_height,
            )
            pygame.draw.rect(self.screen, (100, 140, 200), filled_rect, border_radius=4)

        hx = self.track_x + int(ratio * self.track_width)
        handle_color = (255, 255, 255) if self._dragging else (210, 210, 210)
        pygame.draw.circle(self.screen, handle_color, (hx, self.track_y), self.handle_radius)
        pygame.draw.circle(self.screen, (100, 140, 200), (hx, self.track_y), self.handle_radius, 2)


class NumberInputBox:
    """整数输入框（1-100）"""

    def __init__(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
        cx: int,
        cy: int,
        label: str,
        default_value: int = 16,
    ) -> None:
        self.screen = screen
        self.font = font
        self._min = 1
        self._max = 100
        self._value = max(self._min, min(self._max, default_value))
        self._text = str(self._value)
        self._active = False
        self._blink_t = 0.0

        self.box_w = 80
        self.box_h = 36
        self.box_x = _CTRL_LEFT
        self.box_y = cy - self.box_h // 2
        self.rect = pygame.Rect(self.box_x, self.box_y, self.box_w, self.box_h)

        self._label_surf = font.render(label, True, (40, 40, 40))
        self.label_x = _LABEL_RIGHT - self._label_surf.get_width()

    @property
    def value(self) -> int:
        return self._value

    def _apply_text(self) -> None:
        try:
            v = int(self._text)
        except ValueError:
            v = self._min
        self._value = max(self._min, min(self._max, v))
        self._text = str(self._value)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            was_active = self._active
            self._active = self.rect.collidepoint(event.pos)
            if was_active and not self._active:
                self._apply_text()
            return self._active
        elif event.type == pygame.KEYDOWN and self._active:
            if event.key == pygame.K_RETURN:
                self._active = False
                self._apply_text()
            elif event.key == pygame.K_BACKSPACE:
                self._text = self._text[:-1]
            elif event.unicode.isdigit() and len(self._text) < 3:
                self._text += event.unicode
            return True
        return False

    def update(self, dt: float) -> None:
        self._blink_t += dt * 4

    def draw(self) -> None:
        ly = self.box_y + self.box_h // 2 - self._label_surf.get_height() // 2
        self.screen.blit(self._label_surf, (self.label_x, ly))

        border_color = (0, 150, 200) if self._active else (100, 100, 100)
        pygame.draw.rect(self.screen, border_color, self.rect, 2, border_radius=8)

        bg_color = (0, 150, 200, 30) if self._active else (40, 40, 50, 50)
        bg_surf = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        pygame.draw.rect(bg_surf, bg_color, (0, 0, *self.rect.size), border_radius=8)
        self.screen.blit(bg_surf, self.rect.topleft)

        display_text = self._text if self._active else str(self._value)
        text_surf = self.font.render(display_text, True, (40, 40, 40))
        tx = self.rect.centerx - text_surf.get_width() // 2
        ty = self.rect.centery - text_surf.get_height() // 2
        self.screen.blit(text_surf, (tx, ty))

        if self._active and int(self._blink_t) % 2 == 0:
            cursor_x = text_surf.get_width() + tx + 2
            pygame.draw.line(
                self.screen,
                (40, 40, 40),
                (cursor_x, self.rect.y + 8),
                (cursor_x, self.rect.y + self.box_h - 8),
                2,
            )


class TrainingPlanScreen:
    """训练计划页面"""

    def __init__(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
        title_font: pygame.font.Font,
        audio=None,
        bg: pygame.Surface | None = None,
    ) -> None:
        self.screen = screen
        self.font = font
        self.title_font = title_font
        self._audio = audio
        self._bg = bg
        self.clock = pygame.time.Clock()
        self.running = True
        self.result = None

        self._panel_w, self._panel_h = 820, 560
        self._panel_x = (SCREEN_WIDTH - self._panel_w) // 2
        self._panel_y = (SCREEN_HEIGHT - self._panel_h) // 2

        self._panel_img = None
        if os.path.exists(SETTINGS_PANEL_IMG):
            try:
                img = pygame.image.load(SETTINGS_PANEL_IMG).convert_alpha()
                self._panel_img = pygame.transform.smoothscale(img, (self._panel_w, self._panel_h))
            except Exception:
                pass

        cx = SCREEN_WIDTH // 2
        cy = SCREEN_HEIGHT // 2

        self.stage1_slider = StageSlider(screen, font, cx, cy - 110, "原萃阶段", default_value=_last_values.get("stage1", 3))
        self.stage2_slider = StageSlider(screen, font, cx, cy - 60, "特调阶段", default_value=_last_values.get("stage2", 7))
        self.stage3_slider = StageSlider(screen, font, cx, cy - 10, "忆调阶段", default_value=_last_values.get("stage3", 5))

        self.round_input = NumberInputBox(screen, font, cx, cy + 40, "轮次", default_value=_last_values.get("rounds", 16))

        btn_y = cy + 220
        self.back_btn = MenuItem(
            "返回",
            cx,
            btn_y,
            title_font,
            (80, 80, 80),
            (100, 100, 100),
            (60, 60, 60),
            padding=(30, 15),
            radius=15,
            width=260,
        )

    def run(self) -> str | None:
        """运行训练计划页面"""
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    self.result = "quit"
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                        self.result = "back"
                    self.round_input.handle_event(event)
                else:
                    if self.back_btn.handle_event(event):
                        self.running = False
                        self.result = "back"
                    self.stage1_slider.handle_event(event)
                    self.stage2_slider.handle_event(event)
                    self.stage3_slider.handle_event(event)
                    self.round_input.handle_event(event)

            self._update(dt)
            self._draw()
            pygame.display.flip()

        _last_values["stage1"] = self.stage1_slider.value
        _last_values["stage2"] = self.stage2_slider.value
        _last_values["stage3"] = self.stage3_slider.value
        _last_values["rounds"] = self.round_input.value
        return self.result

    def _update(self, dt: float) -> None:
        self.back_btn.update(dt)
        self.round_input.update(dt)

    def _draw(self) -> None:
        if self._bg:
            self.screen.blit(self._bg, (0, 0))
        else:
            self.screen.fill((30, 30, 40))

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        panel_surf = pygame.Surface((self._panel_w, self._panel_h), pygame.SRCALPHA)
        if self._panel_img:
            panel_surf.blit(self._panel_img, (0, 0))
        else:
            pygame.draw.rect(panel_surf, (30, 28, 20, 230), (0, 0, self._panel_w, self._panel_h), border_radius=16)
            pygame.draw.rect(panel_surf, (200, 160, 100, 180), (0, 0, self._panel_w, self._panel_h), 3, border_radius=16)
        self.screen.blit(panel_surf, (self._panel_x, self._panel_y))

        self.stage1_slider.draw()
        self.stage2_slider.draw()
        self.stage3_slider.draw()
        self.round_input.draw()

        self.back_btn.draw(self.screen)
