"""
BCI 专注力校准界面
流程: 提示 → 3秒倒计时 → 30秒记录 → 计算基线
"""

from __future__ import annotations

import time

import pygame

from bci.data_reader import BCIDataReader
from config import (
    CALIBRATION_BASELINE_WINDOW,
    CALIBRATION_DURATION,
    CALIBRATION_WARMUP,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)
from game.font_utils import load_chinese_font


class CalibrationScreen:
    """专注力校准界面"""

    def __init__(self, screen: pygame.Surface, bci_reader: BCIDataReader) -> None:
        self.screen = screen
        self.bci_reader = bci_reader
        self.clock = pygame.time.Clock()

        self.title_font = load_chinese_font(48)
        self.info_font = load_chinese_font(28)
        self.number_font = load_chinese_font(72)

    def run(self) -> dict | None:
        phase = "warmup"

        warmup_start = time.time()
        record_start = 0.0
        samples: list[tuple[float, float]] = []
        warmup_remaining = CALIBRATION_WARMUP

        while True:
            self.clock.tick(60)
            now = time.time()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return None
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return None

            self._poll_attention(samples)

            if phase == "warmup":
                warmup_remaining = max(0, CALIBRATION_WARMUP - (now - warmup_start))
                if warmup_remaining <= 0:
                    phase = "recording"
                    record_start = now
                    samples.clear()

            elif phase == "recording":
                record_elapsed = now - record_start
                if record_elapsed >= CALIBRATION_DURATION:
                    return self._compute_result(samples)

            self._draw(phase, warmup_remaining, now - record_start if phase == "recording" else 0, samples)
            pygame.display.flip()

    def _poll_attention(self, samples: list) -> None:
        result = self.bci_reader.read_with_timeout()
        if result[0] is not None:
            samples.append((time.time(), result[0]))

    def _compute_result(self, samples: list[tuple[float, float]]) -> dict:
        if not samples:
            return {"baseline": 50.0, "norm_min": 0.0, "norm_max": 100.0}

        window_end = samples[-1][0]
        window_start = window_end - CALIBRATION_BASELINE_WINDOW
        window_values = [v for t, v in samples if t >= window_start]

        if window_values:
            baseline = sum(window_values) / len(window_values)
        else:
            all_values = [v for _, v in samples]
            baseline = sum(all_values) / len(all_values)

        all_values = [v for _, v in samples]
        norm_min = min(all_values)
        norm_max = max(all_values)

        if norm_max - norm_min < 5:
            norm_min = max(0, baseline - 15)
            norm_max = min(100, baseline + 15)

        return {"baseline": baseline, "norm_min": norm_min, "norm_max": norm_max}

    def _draw(
        self,
        phase: str,
        warmup_remaining: float,
        record_elapsed: float,
        samples: list[tuple[float, float]],
    ) -> None:
        self.screen.fill((20, 20, 40))

        title = self.title_font.render("专注力校准", True, (255, 220, 150))
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 100))

        if phase == "warmup":
            info = self.info_font.render("即将开始记录，请保持自然专注状态", True, (200, 200, 220))
            self.screen.blit(info, (SCREEN_WIDTH // 2 - info.get_width() // 2, 220))

            countdown = max(0, int(warmup_remaining))
            if countdown == 0:
                countdown_text = self.number_font.render("开始!", True, (100, 255, 100))
            else:
                countdown_text = self.number_font.render(str(countdown), True, (255, 200, 100))
            self.screen.blit(countdown_text, (SCREEN_WIDTH // 2 - countdown_text.get_width() // 2, 310))

            hint = self.info_font.render("不要刻意提高专注，保持日常状态即可", True, (150, 150, 170))
            self.screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, 410))

        elif phase == "recording":
            info = self.info_font.render("记录中... 请保持自然状态", True, (200, 200, 220))
            self.screen.blit(info, (SCREEN_WIDTH // 2 - info.get_width() // 2, 220))

            remain = max(0, int(CALIBRATION_DURATION - record_elapsed))
            remain_text = self.number_font.render(f"{remain} 秒", True, (100, 200, 255))
            self.screen.blit(remain_text, (SCREEN_WIDTH // 2 - remain_text.get_width() // 2, 310))

            bar_w = 600
            bar_h = 20
            bar_x = (SCREEN_WIDTH - bar_w) // 2
            bar_y = 410
            progress = max(0, min(1.0, record_elapsed / CALIBRATION_DURATION))
            pygame.draw.rect(self.screen, (60, 60, 80), (bar_x, bar_y, bar_w, bar_h), border_radius=10)
            fill_w = int(bar_w * progress)
            if fill_w > 0:
                pygame.draw.rect(self.screen, (100, 200, 255), (bar_x, bar_y, fill_w, bar_h), border_radius=10)

            if samples:
                last = samples[-1][1]
                att_text = self.info_font.render(f"当前专注力: {int(last)}", True, (150, 255, 150))
                self.screen.blit(att_text, (SCREEN_WIDTH // 2 - att_text.get_width() // 2, 460))

                if len(samples) >= 2:
                    avg = sum(v for _, v in samples) / len(samples)
                    avg_text = self.info_font.render(f"平均专注力: {int(avg)}", True, (180, 180, 220))
                    self.screen.blit(avg_text, (SCREEN_WIDTH // 2 - avg_text.get_width() // 2, 495))

        esc = self.info_font.render("ESC 跳过校准", True, (120, 120, 140))
        self.screen.blit(esc, (SCREEN_WIDTH // 2 - esc.get_width() // 2, SCREEN_HEIGHT - 60))
