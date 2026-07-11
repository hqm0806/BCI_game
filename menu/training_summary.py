"""训练模式结算面板"""

from __future__ import annotations

import os

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


class TrainingSummaryScreen:
    """训练模式结算面板"""

    def __init__(
        self,
        screen: pygame.Surface,
        total_money: int = 0,
        total_cups: int = 0,
        secret_count: int = 0,
        failed_cup_count: int = 0,
        memory_successes: int = 0,
        memory_failures: int = 0,
        avg_focus: float = 0.0,
        stage1_avg: float = 0.0,
        stage2_avg: float = 0.0,
        stage3_avg: float = 0.0,
        all_focus_samples: list | None = None,
        stage1_focus: list | None = None,
        stage2_focus: list | None = None,
        stage3_focus: list | None = None,
        player_level: int = 1,
        cumulative_revenue: int = 0,
        baseline: float = 0.0,
        norm_lower: float = 0.0,
        norm_upper: float = 0.0,
        duration: float = 0.0,
        stage1_min: int = 0,
        stage2_min: int = 0,
        stage3_min: int = 0,
        bg: pygame.Surface | None = None,
    ) -> None:
        self.screen = screen
        self._bg = bg
        self.total_money = total_money
        self.total_cups = total_cups
        self.secret_count = secret_count
        self.failed_cup_count = failed_cup_count
        self.memory_successes = memory_successes
        self.memory_failures = memory_failures
        self.avg_focus = avg_focus
        self.stage1_avg = stage1_avg
        self.stage2_avg = stage2_avg
        self.stage3_avg = stage3_avg
        self.all_focus_samples = all_focus_samples or []
        self.stage1_focus = stage1_focus or []
        self.stage2_focus = stage2_focus or []
        self.stage3_focus = stage3_focus or []
        self.player_level = player_level
        self.cumulative_revenue = cumulative_revenue
        self.baseline = baseline
        self.norm_lower = norm_lower
        self.norm_upper = norm_upper
        self.duration = duration
        self.stage1_min = stage1_min
        self.stage2_min = stage2_min
        self.stage3_min = stage3_min

        self.title_font = load_chinese_font(36)
        self.font = load_chinese_font(24)
        self.small_font = load_chinese_font(18)
        self.clock = pygame.time.Clock()
        self.running = True
        self.result = None

        panel_w, panel_h = SUMMARY_PANEL_SIZE
        panel_x, panel_y = SUMMARY_PANEL_POS
        scale_factor = 1.12
        self._panel_w = int(panel_w * scale_factor)
        self._panel_h = int(panel_h * scale_factor)
        self._panel_x = (SCREEN_WIDTH - self._panel_w) // 2
        self._panel_y = (SCREEN_HEIGHT - self._panel_h) // 2

        self._panel_img = None
        if os.path.exists(SUMMARY_PANEL_IMG):
            try:
                img = pygame.image.load(SUMMARY_PANEL_IMG).convert_alpha()
                self._panel_img = pygame.transform.smoothscale(img, (self._panel_w, self._panel_h))
            except Exception:
                pass

        px, py = self._panel_x, self._panel_y
        pw, ph = self._panel_w, self._panel_h
        total_btn_w = SUMMARY_BTN_W * 2 + SUMMARY_BTN_GAP
        btn_start_x = px + (pw - total_btn_w) // 2
        btn_y = py + ph - SUMMARY_BTN_H - 40
        self._save_rect = pygame.Rect(btn_start_x, btn_y, SUMMARY_BTN_W, SUMMARY_BTN_H)
        self._quit_rect = pygame.Rect(btn_start_x + SUMMARY_BTN_W + SUMMARY_BTN_GAP, btn_y, SUMMARY_BTN_W, SUMMARY_BTN_H)

    def run(self) -> str | None:
        while self.running:
            self.clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.result = "quit"
                    self.running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self._save_rect.collidepoint(event.pos):
                        self.result = "save"
                        self.running = False
                    elif self._quit_rect.collidepoint(event.pos):
                        self.result = "quit"
                        self.running = False
            self._draw()
            pygame.display.flip()
        return self.result

    def _draw(self) -> None:
        if self._bg is not None:
            self.screen.blit(self._bg, (0, 0))
        else:
            self.screen.fill((30, 30, 40))

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        if self._panel_img:
            self.screen.blit(self._panel_img, (self._panel_x, self._panel_y))

        px, py = self._panel_x, self._panel_y

        rev_text = f"累计营业额: {self.cumulative_revenue}"
        rev_surf = self.font.render(rev_text, True, (80, 80, 80))
        self.screen.blit(rev_surf, (px + self._panel_w - rev_surf.get_width() - 40, py + 33))

        y = py + 180
        left_x = px + 60
        right_x = px + self._panel_w // 2 + 30

        stats = [
            (f"总收益: {self.total_money}", f"总杯数: {self.total_cups}"),
            (f"秘方次数: {self.secret_count}", f"制作失败: {self.failed_cup_count}"),
            (f"记忆成功: {self.memory_successes}", f"记忆失败: {self.memory_failures}"),
        ]
        if self.memory_successes + self.memory_failures > 0:
            rate = int(self.memory_successes / (self.memory_successes + self.memory_failures) * 100)
            stats.append((f"记忆成功率: {rate}%", ""))

        for left, right in stats:
            l_surf = self.font.render(left, True, (40, 40, 40))
            r_surf = self.font.render(right, True, (40, 40, 40))
            self.screen.blit(l_surf, (left_x, y))
            self.screen.blit(r_surf, (right_x, y))
            y += 32

        y += 10
        focus_line = self.font.render("专注力分析", True, (100, 70, 35))
        self.screen.blit(focus_line, (px + 60, y))
        y += 30

        focus_stats = [
            f"总平均: {self.avg_focus:.1f}",
            f"原萃: {self.stage1_avg:.1f}  特调: {self.stage2_avg:.1f}  忆调: {self.stage3_avg:.1f}",
        ]
        for fs in focus_stats:
            fs_surf = self.small_font.render(fs, True, (60, 60, 60))
            self.screen.blit(fs_surf, (left_x, y))
            y += 24

        bl = self.small_font.render(
            f"基线: {self.baseline:.0f}  归一化: [{self.norm_lower:.0f}, {self.norm_upper:.0f}]",
            True, (60, 60, 60))
        self.screen.blit(bl, (left_x, y))
        y += 22

        y += 4
        samples = self.all_focus_samples
        if samples:
            wave_w = self._panel_w - 120
            wave_h = 130
            wave_x = px + 60
            wave_y = y
            self._draw_waveform(wave_x, wave_y, wave_w, wave_h, samples)

            s1 = self.stage1_min
            s2 = self.stage2_min
            s3 = self.stage3_min
            total_min = s1 + s2 + s3
            if total_min > 0:
                x1 = wave_x + int(s1 / total_min * wave_w)
                x2 = wave_x + int((s1 + s2) / total_min * wave_w)
                self._draw_dashed_line(x1, wave_y, wave_h)
                self._draw_dashed_line(x2, wave_y, wave_h)

                region_labels = [
                    ("原萃阶段", wave_x, x1),
                    ("特调阶段", x1, x2),
                    ("忆调阶段", x2, wave_x + wave_w),
                ]
                for label_text, lx, rx in region_labels:
                    cx = (lx + rx) // 2
                    label_surf = self.small_font.render(label_text, True, (255, 200, 100))
                    self.screen.blit(label_surf, (cx - label_surf.get_width() // 2, wave_y + 4))

            y = wave_y + wave_h + 10

        save_color = (60, 160, 100)
        pygame.draw.rect(self.screen, save_color, self._save_rect, border_radius=12)
        save_text = self.font.render("保存", True, (255, 255, 255))
        self.screen.blit(save_text, (
            self._save_rect.centerx - save_text.get_width() // 2,
            self._save_rect.centery - save_text.get_height() // 2,
        ))

        quit_color = (160, 60, 60)
        pygame.draw.rect(self.screen, quit_color, self._quit_rect, border_radius=12)
        quit_text = self.font.render("退出", True, (255, 255, 255))
        self.screen.blit(quit_text, (
            self._quit_rect.centerx - quit_text.get_width() // 2,
            self._quit_rect.centery - quit_text.get_height() // 2,
        ))

    def _draw_waveform(self, x: int, y: int, w: int, h: int, samples: list) -> None:
        pygame.draw.rect(self.screen, (30, 30, 50), (x, y, w, h), border_radius=4)
        if len(samples) < 2:
            return
        num_pts = min(150, len(samples))
        step = max(1, len(samples) // num_pts)
        points = []
        for i in range(0, len(samples), step):
            chunk = samples[i:i + step]
            avg = sum(chunk) / len(chunk)
            px = x + int(i / max(1, len(samples)) * w)
            py = y + int((1.0 - avg / 100.0) * h)
            points.append((px, max(y, min(y + h, py))))
        if len(points) >= 2:
            pygame.draw.lines(self.screen, (180, 130, 60), False, points, 2)

    def _draw_dashed_line(self, x: int, y: int, h: int) -> None:
        dash_h = 6
        gap_h = 5
        cy = y
        while cy < y + h:
            end = min(cy + dash_h, y + h)
            pygame.draw.line(self.screen, (255, 180, 60), (x, cy), (x, end), 2)
            cy = end + gap_h
