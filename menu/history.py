"""
游戏历史记录列表 + 单局详情界面
"""

from __future__ import annotations

import sys

import pygame

from config import SCREEN_HEIGHT, SCREEN_WIDTH
from game.font_utils import load_chinese_font
from menu.summary import _draw_centered as draw_centered


class HistoryScreen:
    """历史记录列表 + 查看详情"""

    def __init__(self, screen: pygame.Surface, games: list[dict]) -> None:
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.games = list(reversed(games))
        self.title_font = load_chinese_font(48)
        self.font = load_chinese_font(28)
        self.hint_font = load_chinese_font(20)
        self.small_font = load_chinese_font(16)
        self._scroll = 0
        self._item_h = 80
        self._visible = (SCREEN_HEIGHT - 120) // self._item_h

    def run(self) -> None:
        while True:
            self.clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return
                if event.type == pygame.MOUSEWHEEL:
                    self._scroll = max(0, min(len(self.games) - self._visible, self._scroll - event.y))
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos
                    idx = self._scroll + (my - 100) // self._item_h
                    if 0 <= idx < len(self.games):
                        self._show_detail(self.games[idx])

            self.screen.fill((25, 25, 45))
            draw_centered(self.screen, self.title_font, "历史记录", 30, (255, 220, 150))

            pygame.draw.line(self.screen, (80, 80, 100), (100, 80), (SCREEN_WIDTH - 100, 80), 1)

            if not self.games:
                draw_centered(self.screen, self.font, "暂无记录", 200, (150, 150, 150))

            for i in range(self._scroll, min(self._scroll + self._visible + 1, len(self.games))):
                g = self.games[i]
                row_y = 100 + (i - self._scroll) * self._item_h
                row_rect = pygame.Rect(40, row_y, SCREEN_WIDTH - 80, self._item_h - 4)

                hover = row_rect.collidepoint(pygame.mouse.get_pos())
                alpha = 40 if hover else 20
                row_bg = pygame.Surface((row_rect.width, row_rect.height), pygame.SRCALPHA)
                row_bg.fill((255, 255, 255, alpha))
                self.screen.blit(row_bg, row_rect)
                pygame.draw.rect(self.screen, (60, 60, 80), row_rect, 1, border_radius=6)

                date = self.font.render(g.get("date", "未知"), True, (255, 255, 255))
                self.screen.blit(date, (row_rect.x + 15, row_rect.y + 8))

                mode_name = {"regular": "常规", "challenge": "挑战", "creative": "创意", "bci": "BCI"}.get(
                    g.get("mode", ""), ""
                )
                mins = int(g.get("duration", 0)) // 60
                secs = int(g.get("duration", 0)) % 60
                info = self.hint_font.render(
                    f"{mode_name} | 收益:{g.get('revenue', 0)} | {mins}分{secs}秒 | 平均专注:{g.get('avg_attention', 0):.0f}",
                    True,
                    (180, 180, 200),
                )
                self.screen.blit(info, (row_rect.x + 15, row_rect.y + 42))

            esc = self.hint_font.render("ESC 返回 | 滚轮翻页 | 点击查看详情", True, (120, 120, 140))
            self.screen.blit(esc, (SCREEN_WIDTH // 2 - esc.get_width() // 2, SCREEN_HEIGHT - 40))
            pygame.display.flip()

    def _show_detail(self, game: dict) -> None:
        while True:
            self.clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                    return

            self.screen.fill((25, 25, 45))
            y = 60

            draw_centered(self.screen, self.title_font, "游戏详情", y, (255, 220, 150))
            y += 60
            pygame.draw.line(self.screen, (80, 80, 100), (100, y), (SCREEN_WIDTH - 100, y), 1)
            y += 20

            date = game.get("date", "未知")
            draw_centered(self.screen, self.font, date, y, (200, 200, 200))
            y += 40

            mode_name = {"regular": "常规模式", "challenge": "挑战模式", "creative": "创意模式", "bci": "BCI模式"}.get(
                game.get("mode", ""), ""
            )
            draw_centered(self.screen, self.font, mode_name, y, (180, 180, 220))
            y += 40

            draw_centered(self.screen, self.font, f"总收益: {game.get('revenue', 0)}", y, (100, 255, 100))
            y += 35
            draw_centered(
                self.screen,
                self.hint_font,
                f"完成杯数: {game.get('cups', 0)} | 秘方: {game.get('secrets', 0)} 次",
                y,
                (180, 180, 200),
            )
            y += 35
            mins = int(game.get("duration", 0)) // 60
            secs = int(game.get("duration", 0)) % 60
            draw_centered(self.screen, self.hint_font, f"游戏时长: {mins}分{secs}秒", y, (180, 180, 200))
            y += 35
            draw_centered(
                self.screen, self.hint_font, f"平均专注力: {game.get('avg_attention', 0):.1f}", y, (150, 255, 150)
            )
            y += 20

            samples = game.get("focus_samples", [])
            if samples:
                graph_w = 1100
                graph_h = 150
                graph_x = (SCREEN_WIDTH - graph_w) // 2
                graph_y = y
                total_sec = game.get("duration", len(samples) / 60.0)
                self._draw_waveform(graph_x, graph_y, graph_w, graph_h, total_sec, samples)
                y = graph_y + graph_h + 20

            hint = self.hint_font.render("按任意键返回", True, (120, 120, 140))
            self.screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, SCREEN_HEIGHT - 40))
            pygame.display.flip()

    def _draw_waveform(self, x: int, y: int, w: int, h: int, total_sec: float, samples: list):
        pygame.draw.rect(self.screen, (30, 30, 50), (x, y, w, h), border_radius=6)

        for i in range(0, 101, 25):
            py = y + int((1.0 - i / 100.0) * h)
            pygame.draw.line(self.screen, (60, 60, 80), (x, py), (x + w, py), 1)
            label = self.small_font.render(str(i), True, (120, 120, 120))
            self.screen.blit(label, (x - 30, py - 7))

        num_pts = min(150, len(samples))
        step = max(1, len(samples) // num_pts)
        points = []
        for i in range(0, len(samples), step):
            bucket = samples[i : i + step]
            avg = sum(bucket) / len(bucket)
            t = i / max(1, len(samples))
            px = x + int(t * w)
            py = y + int((1.0 - avg / 100.0) * h)
            py = max(y, min(y + h, py))
            points.append((px, py))
        if len(points) >= 2:
            pygame.draw.lines(self.screen, (100, 255, 150), False, points, 2)

        for i in range(6):
            t = i / 5
            tx = x + int(t * w)
            label = self.small_font.render(f"{int(t * total_sec)}s", True, (120, 120, 120))
            self.screen.blit(label, (tx - 10, y + h + 4))

        title = self.small_font.render("专注力曲线", True, (160, 160, 160))
        self.screen.blit(title, (x + 4, y - 16))
