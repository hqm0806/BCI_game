"""游戏结束总结界面（一杯制改造）"""

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

        self.bg_path = os.path.join(ASSETS_DIR, "images", "backgrounds", "summary_bg.png")
        self.icon_path = os.path.join(ASSETS_DIR, "images", "other", "summary_icon.png")

        self.bg = None
        if os.path.exists(self.bg_path):
            self.bg = pygame.image.load(self.bg_path).convert()
            self.bg = pygame.transform.scale(self.bg, (SCREEN_WIDTH, SCREEN_HEIGHT))

        self.title_font = _load_font(60)
        self.info_font = _load_font(40)
        self.comment_font = _load_font(32)
        self.hint_font = _load_font(24)

        self.comment = self._generate_comment()

    def _generate_comment(self) -> str:
        is_bci = self.game_mode == "bci"

        if is_bci:
            if self.score >= 200 and self.focus_value >= 70:
                return "专注大师！脑波与奶茶的完美共鸣！"
            if self.score >= 100:
                return "表现不错，继续保持专注！"
            if self.score >= 50:
                return "初露锋芒，调整呼吸再试一次！"
            return "万事开头难，放松心态，专注力会慢慢提升的！"
        else:
            if self.score >= 200:
                return "奶茶大师！你的手速快如闪电！"
            if self.score >= 100:
                return "手艺精湛！是一杯好奶茶！"
            if self.score >= 50:
                return "初露锋芒，再接再厉！"
            return "万事开头难，多喝奶茶多练习！"

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

            _draw_centered_text(self.screen, self.title_font, "游戏结束", 80, (255, 255, 255))

            pygame.draw.line(self.screen, (100, 100, 120), (200, 155), (SCREEN_WIDTH - 200, 155), 3)

            _draw_centered_text(self.screen, self.info_font, "最终得分", 190, (180, 180, 200))
            _draw_centered_text(self.screen, self.info_font, str(self.score), 240, (255, 220, 100))

            _draw_centered_text(self.screen, self.info_font, f"总收益: {self.total_money}", 300, (100, 255, 100))
            _draw_centered_text(self.screen, self.hint_font, f"完成杯数: {self.cup_count}", 345, (180, 180, 200))
            _draw_centered_text(self.screen, self.hint_font, f"秘方触发: {self.secret_count} 次", 375, (255, 215, 0))
            _draw_centered_text(
                self.screen, self.hint_font, f"最高单杯收益: {self.max_cup_money}", 405, (200, 200, 200)
            )

            _draw_centered_text(self.screen, self.info_font, "平均专注力", 460, (180, 180, 200))
            _draw_centered_text(self.screen, self.info_font, f"{self.focus_value:.1f}%", 510, (150, 255, 150))

            comment_surf = self.comment_font.render(self.comment, True, (220, 220, 240))
            self.screen.blit(comment_surf, (SCREEN_WIDTH // 2 - comment_surf.get_width() // 2, 570))

            hint_surf = self.hint_font.render("按 任意键 / 点击屏幕 返回主菜单", True, (140, 140, 150))
            self.screen.blit(
                hint_surf,
                (SCREEN_WIDTH // 2 - hint_surf.get_width() // 2, SCREEN_HEIGHT - 50),
            )

            pygame.display.flip()


def _draw_centered_text(
    screen: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    y: int,
    color: tuple[int, int, int],
) -> None:
    surf = font.render(text, True, color)
    screen.blit(surf, (SCREEN_WIDTH // 2 - surf.get_width() // 2, y))
