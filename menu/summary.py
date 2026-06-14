"""游戏结束总结界面 — 结算面板 + 双按钮"""

from __future__ import annotations

import os
import sys
import time

import pygame

from config import (
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SUMMARY_BTN_GAP,
    SUMMARY_BTN_H,
    SUMMARY_BTN_W,
    SUMMARY_PANEL_IMG,
    SUMMARY_PANEL_POS,
    SUMMARY_PANEL_SIZE,
)
from game.font_utils import load_chinese_font


class SummaryScreen:
    def __init__(
        self,
        screen: pygame.Surface,
        score: int,
        focus_value: float = 0.0,
        game_mode: str = "regular",
        total_money: int = 0,
        cup_count: int = 0,
        secret_count: int = 0,
        max_cup_money: int = 0,
        player_level: int = 1,
        cumulative_revenue: int = 0,
        upgraded: bool = False,
        focus_samples: list | None = None,
        bg: pygame.Surface | None = None,
    ) -> None:
        self.screen = screen
        self._bg = bg
        self.clock = pygame.time.Clock()
        self.score = score
        self.focus_value = focus_value
        self.game_mode = game_mode
        self.total_money = total_money
        self.cup_count = cup_count
        self.secret_count = secret_count
        self.max_cup_money = max_cup_money
        self.player_level = player_level
        self.cumulative_revenue = cumulative_revenue
        self.upgraded = upgraded
        self.focus_samples = focus_samples or []

        self.panel_img = None
        if os.path.exists(SUMMARY_PANEL_IMG):
            try:
                self.panel_img = pygame.image.load(SUMMARY_PANEL_IMG).convert_alpha()
                self.panel_img = pygame.transform.smoothscale(self.panel_img, SUMMARY_PANEL_SIZE)
            except Exception:
                pass

        px, py = SUMMARY_PANEL_POS
        pw, ph = SUMMARY_PANEL_SIZE
        total_btn_w = SUMMARY_BTN_W * 2 + SUMMARY_BTN_GAP
        btn_start_x = px + (pw - total_btn_w) // 2
        btn_y = py + ph - SUMMARY_BTN_H - 40
        self._btn_save_rect = pygame.Rect(btn_start_x, btn_y, SUMMARY_BTN_W, SUMMARY_BTN_H)
        self._btn_quit_rect = pygame.Rect(btn_start_x + SUMMARY_BTN_W + SUMMARY_BTN_GAP, btn_y, SUMMARY_BTN_W, SUMMARY_BTN_H)
        self._btn_hover_save = False
        self._btn_hover_quit = False

        self.title_font = load_chinese_font(50)
        self.info_font = load_chinese_font(36)
        self.big_font = load_chinese_font(48)
        self.hint_font = load_chinese_font(22)
        self.small_font = load_chinese_font(16)
        self.btn_font = load_chinese_font(30)

        self.comment = self._generate_comment()

    def _generate_comment(self) -> str:
        if self.upgraded:
            return f"升级！已达到 Lv.{self.player_level}！"
        if self.game_mode == "bci":
            if self.focus_value >= 70:
                return "专注大师！脑波与奶茶的完美共鸣！"
            if self.focus_value >= 50:
                return "表现不错，继续保持专注！"
            return "调整呼吸，再试一次！"
        else:
            if self.total_money >= 100:
                return "奶茶大师！手艺精湛！"
            if self.total_money >= 50:
                return "一杯好奶茶！再接再厉！"
            return "多练练习，手艺会越来越好的！"

    def _build_waveform_points(self, graph_x: int, graph_y: int, graph_w: int, graph_h: int):
        if not self.focus_samples:
            return []
        num_points = min(200, len(self.focus_samples))
        step = max(1, len(self.focus_samples) // num_points)
        points = []
        for i in range(0, len(self.focus_samples), step):
            bucket = self.focus_samples[i : i + step]
            avg = sum(bucket) / len(bucket)
            t = i / max(1, len(self.focus_samples))
            x = graph_x + int(t * graph_w)
            y = graph_y + int((1.0 - avg / 100.0) * graph_h)
            y = max(graph_y, min(graph_y + graph_h, y))
            points.append((x, y))
        return points

    def _draw_waveform(
        self,
        graph_x: int,
        graph_y: int,
        graph_w: int,
        graph_h: int,
        total_sec: float,
    ):
        pygame.draw.rect(self.screen, (30, 30, 50), (graph_x, graph_y, graph_w, graph_h), border_radius=6)

        for i in range(0, 101, 25):
            y = graph_y + int((1.0 - i / 100.0) * graph_h)
            pygame.draw.line(self.screen, (60, 60, 80), (graph_x, y), (graph_x + graph_w, y), 1)
            label = self.small_font.render(str(i), True, (120, 120, 120))
            self.screen.blit(label, (graph_x - 30, y - 7))

        baseline_y = graph_y + graph_h // 2
        pygame.draw.line(self.screen, (100, 100, 120, 60), (graph_x, baseline_y), (graph_x + graph_w, baseline_y), 1)

        num_ticks = 5
        for i in range(num_ticks + 1):
            t = i / num_ticks
            x = graph_x + int(t * graph_w)
            sec = int(t * total_sec)
            label = self.small_font.render(f"{sec}s", True, (120, 120, 120))
            self.screen.blit(label, (x - 10, graph_y + graph_h + 4))

        points = self._build_waveform_points(graph_x, graph_y, graph_w, graph_h)
        if len(points) >= 2:
            pygame.draw.lines(self.screen, (180, 130, 60), False, points, 2)

        title = self.small_font.render("专注力曲线", True, (100, 70, 35))
        self.screen.blit(title, (graph_x + 4, graph_y - 18))

    def _draw_button(self, rect: pygame.Rect, text: str, hovered: bool, is_quit: bool = False) -> None:
        if is_quit:
            bg = (120, 35, 35) if hovered else (55, 15, 15)
        else:
            bg = (100, 60, 25) if hovered else (50, 28, 12)
        pygame.draw.rect(self.screen, bg, rect, border_radius=12)
        pygame.draw.rect(self.screen, (255, 255, 255, 60), rect, 2, border_radius=12)

        txt = self.btn_font.render(text, True, (255, 255, 255))
        tx = rect.centerx - txt.get_width() // 2
        ty = rect.centery - txt.get_height() // 2
        self.screen.blit(txt, (tx, ty))

    def run(self) -> str:
        start = time.time()
        last_esc = 0.0
        while True:
            self.clock.tick(60)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.MOUSEMOTION:
                    self._btn_hover_save = self._btn_save_rect.collidepoint(event.pos)
                    self._btn_hover_quit = self._btn_quit_rect.collidepoint(event.pos)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self._btn_save_rect.collidepoint(event.pos):
                        return "save"
                    if self._btn_quit_rect.collidepoint(event.pos):
                        return "menu"
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    now = time.time()
                    if now - last_esc < 0.5:
                        return "menu"
                    last_esc = now

            if self._bg:
                self.screen.blit(self._bg, (0, 0))

            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 90))
            self.screen.blit(overlay, (0, 0))

            px, py = SUMMARY_PANEL_POS
            if self.panel_img:
                self.screen.blit(self.panel_img, (px, py))

            y = 180
            _draw_centered(self.screen, self.info_font, f"Lv.{self.player_level}", y, (80, 50, 20))

            y += 50
            _draw_centered(self.screen, self.info_font, f"总收益: {self.total_money}", y, (80, 50, 20))

            y += 45
            _draw_centered(self.screen, self.hint_font, f"累计营业额: {self.cumulative_revenue}", y, (100, 75, 45))

            y += 40
            _draw_centered(
                self.screen,
                self.hint_font,
                f"完成杯数: {self.cup_count} | 秘方: {self.secret_count} 次 | 最高单杯: {self.max_cup_money}",
                y,
                (90, 65, 35),
            )

            y += 50
            if self.upgraded:
                up_surf = self.big_font.render(f"升到 Lv.{self.player_level}！新食材已解锁", True, (140, 70, 20))
                self.screen.blit(up_surf, (SCREEN_WIDTH // 2 - up_surf.get_width() // 2, y))
                y += 60

            y += 25
            _draw_centered(self.screen, self.info_font, f"平均专注力: {self.focus_value:.1f}%", y, (80, 50, 20))

            y += 30

            if self.focus_samples:
                graph_w = 800
                graph_h = 120
                graph_x = (SCREEN_WIDTH - graph_w) // 2
                graph_y = y + 5
                total_sec = len(self.focus_samples) / 60.0
                self._draw_waveform(graph_x, graph_y, graph_w, graph_h, total_sec)
                y = graph_y + graph_h + 20

            y += 5
            comment_surf = self.hint_font.render(self.comment, True, (110, 80, 40))
            self.screen.blit(comment_surf, (SCREEN_WIDTH // 2 - comment_surf.get_width() // 2, y))

            self._draw_button(self._btn_save_rect, "保存", self._btn_hover_save, is_quit=False)
            self._draw_button(self._btn_quit_rect, "退出", self._btn_hover_quit, is_quit=True)

            pygame.display.flip()


def _draw_centered(
    screen: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    y: int,
    color: tuple[int, int, int],
) -> None:
    surf = font.render(text, True, color)
    screen.blit(surf, (SCREEN_WIDTH // 2 - surf.get_width() // 2, y))
