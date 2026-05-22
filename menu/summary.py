"""游戏结束总结界面"""

from __future__ import annotations

import os
import sys

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

        self.bg_path = os.path.join(ASSETS_DIR, "images", "backgrounds", "summary_bg.png")

        self.bg = None
        if os.path.exists(self.bg_path):
            self.bg = pygame.image.load(self.bg_path).convert()
            self.bg = pygame.transform.scale(self.bg, (SCREEN_WIDTH, SCREEN_HEIGHT))

        self.title_font = _load_font(50)
        self.info_font = _load_font(36)
        self.big_font = _load_font(48)
        self.hint_font = _load_font(22)

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

    def run(self) -> str:
        while True:
            self.clock.tick(60)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                    return "menu"

            if self.bg:
                self.screen.blit(self.bg, (0, 0))
            else:
                self.screen.fill((40, 40, 55))

            y = 80
            _draw_centered(self.screen, self.title_font, "游戏结束", y, (255, 255, 255))

            y += 70
            pygame.draw.line(self.screen, (100, 100, 120), (200, y), (SCREEN_WIDTH - 200, y), 2)

            y += 30
            _draw_centered(self.screen, self.info_font, f"Lv.{self.player_level}", y, (255, 215, 0))

            y += 40
            _draw_centered(self.screen, self.info_font, f"总收益: {self.total_money}", y, (100, 255, 100))

            y += 30
            _draw_centered(self.screen, self.hint_font, f"累计营业额: {self.cumulative_revenue}", y, (200, 200, 200))

            y += 25
            _draw_centered(
                self.screen,
                self.hint_font,
                f"完成杯数: {self.cup_count} | 秘方: {self.secret_count} 次 | 最高单杯: {self.max_cup_money}",
                y,
                (180, 180, 200),
            )

            y += 35
            if self.upgraded:
                up_surf = self.big_font.render(f"升到 Lv.{self.player_level}！新食材已解锁", True, (255, 200, 50))
                self.screen.blit(up_surf, (SCREEN_WIDTH // 2 - up_surf.get_width() // 2, y))
                y += 50

            y += 15
            _draw_centered(self.screen, self.info_font, f"平均专注力: {self.focus_value:.1f}%", y, (150, 255, 150))

            y += 50
            comment_surf = self.hint_font.render(self.comment, True, (220, 220, 240))
            self.screen.blit(comment_surf, (SCREEN_WIDTH // 2 - comment_surf.get_width() // 2, y))

            hint_surf = self.hint_font.render("按 任意键 / 点击屏幕 返回主菜单", True, (140, 140, 150))
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
