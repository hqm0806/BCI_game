"""游戏结束总结界面"""

from __future__ import annotations

import os
import sys
import time

import pygame

from config import ASSETS_DIR, CHINESE_FONTS, SCREEN_HEIGHT, SCREEN_WIDTH


def _load_font(size: int) -> pygame.font.Font:
    for path in CHINESE_FONTS:
        if os.path.exists(path):
            try:
                return pygame.font.Font(path, size)
            except (pygame.error, OSError):
                pass
    return pygame.font.Font(None, size)


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
    ) -> None:
        self.screen = screen
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

        self.bg_path = os.path.join(ASSETS_DIR, "images", "backgrounds", "summary_bg.png")

        self.bg = None
        if os.path.exists(self.bg_path):
            self.bg = pygame.image.load(self.bg_path).convert()
            self.bg = pygame.transform.scale(self.bg, (SCREEN_WIDTH, SCREEN_HEIGHT))

        self.title_font = _load_font(50)
        self.info_font = _load_font(36)
        self.big_font = _load_font(48)
        self.hint_font = _load_font(22)
        self.small_font = _load_font(16)

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
            pygame.draw.lines(self.screen, (100, 255, 150), False, points, 2)

        title = self.small_font.render("专注力曲线", True, (160, 160, 160))
        self.screen.blit(title, (graph_x + 4, graph_y - 18))

    def run(self) -> str:
        start = time.time()
        last_esc = 0.0
        while True:
            self.clock.tick(60)
            elapsed = time.time() - start
            can_exit = elapsed >= 3.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    now = time.time()
                    if now - last_esc < 0.5:
                        return "menu"
                    last_esc = now
                elif can_exit and (event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN):
                    return "menu"

            if self.bg:
                self.screen.blit(self.bg, (0, 0))
            else:
                self.screen.fill((40, 40, 55))

            y = 80
            _draw_centered(self.screen, self.title_font, "游戏结束", y, (255, 255, 255))

            y += 80
            pygame.draw.line(self.screen, (100, 100, 120), (200, y), (SCREEN_WIDTH - 200, y), 2)

            y += 40
            _draw_centered(self.screen, self.info_font, f"Lv.{self.player_level}", y, (255, 215, 0))

            y += 50
            _draw_centered(self.screen, self.info_font, f"总收益: {self.total_money}", y, (100, 255, 100))

            y += 45
            _draw_centered(self.screen, self.hint_font, f"累计营业额: {self.cumulative_revenue}", y, (200, 200, 200))

            y += 40
            _draw_centered(
                self.screen,
                self.hint_font,
                f"完成杯数: {self.cup_count} | 秘方: {self.secret_count} 次 | 最高单杯: {self.max_cup_money}",
                y,
                (180, 180, 200),
            )

            y += 50
            if self.upgraded:
                up_surf = self.big_font.render(f"升到 Lv.{self.player_level}！新食材已解锁", True, (255, 200, 50))
                self.screen.blit(up_surf, (SCREEN_WIDTH // 2 - up_surf.get_width() // 2, y))
                y += 60

            y += 25
            _draw_centered(self.screen, self.info_font, f"平均专注力: {self.focus_value:.1f}%", y, (150, 255, 150))

            y += 30

            if self.focus_samples:
                graph_w = 1100
                graph_h = 160
                graph_x = (SCREEN_WIDTH - graph_w) // 2
                graph_y = y + 5
                total_sec = len(self.focus_samples) / 60.0
                self._draw_waveform(graph_x, graph_y, graph_w, graph_h, total_sec)
                y = graph_y + graph_h + 30

            y += 20
            comment_surf = self.hint_font.render(self.comment, True, (220, 220, 240))
            self.screen.blit(comment_surf, (SCREEN_WIDTH // 2 - comment_surf.get_width() // 2, y))

            if can_exit:
                hint_text = "按 任意键 / 点击屏幕 返回主菜单"
            else:
                remain = max(0, int(3 - elapsed) + 1)
                hint_text = f"请耐心等待 {remain} 秒... 结算中"
            hint_surf = self.hint_font.render(hint_text, True, (140, 140, 150))
            self.screen.blit(
                hint_surf,
                (SCREEN_WIDTH // 2 - hint_surf.get_width() // 2, SCREEN_HEIGHT - 50),
            )

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
