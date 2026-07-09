"""训练执行页面"""

from __future__ import annotations

import os

import pygame

from config import SCREEN_HEIGHT, SCREEN_WIDTH, SETTINGS_PANEL_IMG
from menu.components import MenuItem


class _PlainButton(MenuItem):
    def trigger_click(self) -> None:
        pass


class TrainingExecuteScreen:
    """训练执行页面"""

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
        btn_y = SCREEN_HEIGHT // 2 + 220

        self.back_btn = _PlainButton(
            "返回",
            cx - 150,
            btn_y,
            title_font,
            (80, 80, 80),
            (100, 100, 100),
            (60, 60, 60),
            padding=(30, 15),
            radius=15,
            width=120,
        )
        self.training_btn = _PlainButton(
            "进入训练",
            cx + 150,
            btn_y,
            title_font,
            (60, 160, 100),
            (80, 200, 130),
            (40, 120, 70),
            padding=(30, 15),
            radius=15,
            width=160,
        )

    def run(self) -> str | None:
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
                    if self.back_btn.handle_event(event):
                        self.running = False
                        self.result = "back"
                    self.training_btn.handle_event(event)

            self._update(dt)
            self._draw()
            pygame.display.flip()

        return self.result

    def _update(self, dt: float) -> None:
        self.back_btn.update(dt)
        self.training_btn.update(dt)

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

        self.back_btn.draw(self.screen)
        self.training_btn.draw(self.screen)
