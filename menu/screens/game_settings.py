"""游戏设置页面 - 包含BCI设置等子设置项"""

from __future__ import annotations

import pygame

from config import SCREEN_HEIGHT, SCREEN_WIDTH
from menu.bci_button import BCIModeButton
from menu.components import MenuItem
from menu.screens.bci_settings import BCISettingsScreen


class VolumeSlider:
    """音量滑轨组件"""

    def __init__(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
        cx: int,
        cy: int,
        value: float = 0.5,
    ) -> None:
        self.screen = screen
        self.font = font
        self.track_width = 260
        self.track_height = 6
        self.track_x = cx - self.track_width // 2
        self.track_y = cy
        self.handle_radius = 12
        self._value = max(0.0, min(1.0, value))
        self._dragging = False
        self.label_x = self.track_x - 60
        self.pct_x = self.track_x + self.track_width + 20

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, v: float) -> None:
        self._value = max(0.0, min(1.0, v))

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            hx = self.track_x + int(self._value * self.track_width)
            hy = self.track_y
            if (mx - hx) ** 2 + (my - hy) ** 2 <= (self.handle_radius + 6) ** 2:
                self._dragging = True
                return True
            if (
                self.track_x - self.handle_radius <= mx <= self.track_x + self.track_width + self.handle_radius
                and abs(my - self.track_y) <= self.handle_radius + 6
            ):
                self._dragging = True
                self._value = max(0.0, min(1.0, (mx - self.track_x) / self.track_width))
                return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._dragging = False
        elif event.type == pygame.MOUSEMOTION and self._dragging:
            mx, _ = event.pos
            self._value = max(0.0, min(1.0, (mx - self.track_x) / self.track_width))
            return True
        return False

    def draw(self) -> None:
        label = self.font.render("音量", True, (200, 200, 200))
        ly = self.track_y - label.get_height() // 2
        self.screen.blit(label, (self.label_x, ly))

        pct_text = self.font.render(f"{int(self._value * 100)}%", True, (200, 200, 200))
        py = self.track_y - pct_text.get_height() // 2
        self.screen.blit(pct_text, (self.pct_x, py))

        track_rect = pygame.Rect(
            self.track_x, self.track_y - self.track_height // 2,
            self.track_width, self.track_height,
        )
        pygame.draw.rect(self.screen, (60, 60, 70), track_rect, border_radius=4)

        filled_w = int(self._value * self.track_width)
        if filled_w > 0:
            filled_rect = pygame.Rect(
                self.track_x, self.track_y - self.track_height // 2,
                filled_w, self.track_height,
            )
            pygame.draw.rect(self.screen, (60, 160, 100), filled_rect, border_radius=4)

        hx = self.track_x + int(self._value * self.track_width)
        handle_color = (255, 255, 255) if self._dragging else (210, 210, 210)
        pygame.draw.circle(self.screen, handle_color, (hx, self.track_y), self.handle_radius)
        pygame.draw.circle(self.screen, (60, 160, 100), (hx, self.track_y), self.handle_radius, 2)


class GameSettingsScreen:
    """游戏设置页面，包含BCI设置等子设置项"""

    def __init__(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
        title_font: pygame.font.Font,
        audio=None,
    ) -> None:
        self.screen = screen
        self.font = font
        self.title_font = title_font
        self._audio = audio
        self.clock = pygame.time.Clock()
        self.running = True
        self.result = None

        cx, cy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2

        self.bci_btn = BCIModeButton("BCI设置", cx, cy - 60, font, title_font)

        initial_volume = self._audio.get_master_volume() if self._audio else 0.5
        self.volume_slider = VolumeSlider(screen, font, cx, cy + 10, value=initial_volume)

        self.back_btn = MenuItem(
            "返回",
            cx,
            cy + 80,
            title_font,
            (80, 80, 80),
            (100, 100, 100),
            (255, 255, 255),
            padding=(50, 15),
            radius=15,
        )

    def run(self) -> str | None:
        """运行设置页面"""
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
                else:
                    if self.bci_btn.handle_event(event):
                        bci_settings = BCISettingsScreen(self.screen, self.font, self.title_font)
                        bci_settings.run()
                    if self.volume_slider.handle_event(event):
                        if self._audio:
                            self._audio.set_master_volume(self.volume_slider.value)
                    if self.back_btn.handle_event(event):
                        self.running = False
                        self.result = "back"

            self._update(dt)
            self._draw()
            pygame.display.flip()

        return self.result

    def _update(self, dt: float) -> None:
        self.bci_btn.update(dt)
        self.back_btn.update(dt)

    def _draw(self) -> None:
        self.screen.fill((30, 30, 40))

        title = self.title_font.render("游戏设置", True, (255, 255, 255))
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 100))

        desc = self.font.render("请选择需要配置的项目", True, (180, 180, 180))
        self.screen.blit(desc, (SCREEN_WIDTH // 2 - desc.get_width() // 2, 160))

        self.bci_btn.draw(self.screen)
        self.volume_slider.draw()
        self.back_btn.draw(self.screen)

        hint = self.font.render("ESC 返回主菜单", True, (100, 100, 100))
        self.screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, SCREEN_HEIGHT - 50))
