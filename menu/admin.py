"""管理后台 — 查看所有用户数据"""

from __future__ import annotations

import json
import os

import pygame

from config import SCREEN_HEIGHT, SCREEN_WIDTH
from data.player_profile import PlayerProfile
from game.font_utils import load_chinese_font

_ACCOUNTS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "accounts.json")
_BG_COLOR = (15, 15, 25)
_PANEL_BG = (25, 25, 40)
_CARD_BG = (35, 35, 55)
_GOLD = (255, 215, 0)
_WHITE = (240, 240, 245)
_GRAY = (150, 150, 160)
_RED = (220, 80, 80)
_GREEN = (80, 200, 120)
_BLUE = (80, 160, 220)
_ORANGE = (220, 160, 60)
_LIST_W = 280
_ROW_H = 36


class AdminScreen:
    """管理后台页面"""

    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.running = True

        self._title_font = load_chinese_font(36)
        self._body_font = load_chinese_font(22)
        self._small_font = load_chinese_font(18)

        self._users = self._load_users()
        self._selected_idx = 0
        self._profile: PlayerProfile | None = None
        if self._users:
            self._load_profile(0)

        self._scroll_users = 0
        self._scroll_detail = 0
        self._max_scroll_users = max(0, len(self._users) * _ROW_H - (SCREEN_HEIGHT - 80))
        self._hovered_idx = -1

        back_w = 120
        self._back_rect = pygame.Rect(SCREEN_WIDTH - back_w - 20, 12, back_w, 40)
        self._back_hover = False

        self._list_rect = pygame.Rect(0, 60, _LIST_W, SCREEN_HEIGHT - 60)

    @staticmethod
    def _load_users() -> list[str]:
        try:
            with open(_ACCOUNTS_PATH, "r", encoding="utf-8") as f:
                accounts = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
        return sorted([u for u in accounts if u != "admin"])

    def _load_profile(self, idx: int) -> None:
        if 0 <= idx < len(self._users):
            username = self._users[idx]
            self._profile = PlayerProfile.load_for_user(username)
            self._scroll_detail = 0

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            mx, my = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    if event.key == pygame.K_UP and self._selected_idx > 0:
                        self._selected_idx -= 1
                        self._load_profile(self._selected_idx)
                    if event.key == pygame.K_DOWN and self._selected_idx < len(self._users) - 1:
                        self._selected_idx += 1
                        self._load_profile(self._selected_idx)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self._back_rect.collidepoint(mx, my):
                        self.running = False
                    if self._list_rect.collidepoint(mx, my):
                        clicked = (my - 60 + self._scroll_users) // _ROW_H
                        if 0 <= clicked < len(self._users):
                            self._selected_idx = clicked
                            self._load_profile(clicked)
                if event.type == pygame.MOUSEWHEEL:
                    if mx < _LIST_W:
                        self._scroll_users = max(0, min(self._max_scroll_users, self._scroll_users - event.y * 30))
                    else:
                        self._scroll_detail = max(0, self._scroll_detail - event.y * 30)

            self._back_hover = self._back_rect.collidepoint(mx, my)

            self._draw()
            pygame.display.flip()

    def _draw(self) -> None:
        self.screen.fill(_BG_COLOR)

        title = self._title_font.render("管理后台", True, _GOLD)
        self.screen.blit(title, (20, 10))

        bc = _RED if self._back_hover else _GRAY
        pygame.draw.rect(self.screen, bc, self._back_rect, border_radius=6)
        back_txt = self._body_font.render("返回登录", True, _WHITE)
        self.screen.blit(back_txt, (self._back_rect.centerx - back_txt.get_width() // 2,
                                     self._back_rect.centery - back_txt.get_height() // 2))

        pygame.draw.line(self.screen, (50, 50, 70), (0, 58), (SCREEN_WIDTH, 58), 2)
        pygame.draw.line(self.screen, (50, 50, 70), (_LIST_W, 60), (_LIST_W, SCREEN_HEIGHT), 2)

        self._draw_user_list()
        if self._profile:
            self._draw_user_detail()
        else:
            hint = self._body_font.render("请选择用户", True, _GRAY)
            self.screen.blit(hint, (_LIST_W + 40, 100))

    def _draw_user_list(self) -> None:
        visible_start = self._scroll_users // _ROW_H
        visible_end = min(len(self._users), visible_start + (SCREEN_HEIGHT - 60) // _ROW_H + 1)

        for i in range(visible_start, visible_end):
            y = 60 + i * _ROW_H - self._scroll_users
            if i == self._selected_idx:
                pygame.draw.rect(self.screen, (40, 40, 70), (4, y, _LIST_W - 8, _ROW_H), border_radius=4)

            color = _GOLD if i == self._selected_idx else _WHITE
            txt = self._small_font.render(self._users[i], True, color)
            self.screen.blit(txt, (16, y + _ROW_H // 2 - txt.get_height() // 2))

    def _draw_user_detail(self) -> None:
        p = self._profile
        base_x = _LIST_W + 30
        y = 80 - self._scroll_detail

        lvl_txt = self._body_font.render(f"Lv.{p.level}", True, _GOLD)
        self.screen.blit(lvl_txt, (base_x, y))
        cum = self._body_font.render(f"累计收益: {p.cumulative_revenue}", True, _WHITE)
        self.screen.blit(cum, (base_x + 100, y))
        stats = self._small_font.render(
            f"训练: {len(p.training_history)} 次    正式游戏: {len(p.games_history)} 局", True, _GRAY)
        self.screen.blit(stats, (base_x + 380, y))
        y += 50

        if p.training_history:
            y = self._draw_training_section(base_x, y, p)
        if p.games_history:
            self._draw_games_section(base_x, y, p)

    def _draw_training_section(self, base_x: int, y: int, p: PlayerProfile) -> int:
        label = self._body_font.render("── 训练记录 ──", True, _GOLD)
        self.screen.blit(label, (base_x, y))
        y += 36

        for idx, t in enumerate(reversed(p.training_history)):
            if y > SCREEN_HEIGHT + 100:
                break
            card_h = 90
            if y + card_h > 0:
                pygame.draw.rect(self.screen, _CARD_BG, (base_x, y, SCREEN_WIDTH - base_x - 20, card_h), border_radius=6)

                line_y = y + 8
                num = self._small_font.render(f"#{len(p.training_history) - idx}", True, _GOLD)
                self.screen.blit(num, (base_x + 10, line_y))
                date = self._small_font.render(str(t.get("date", "")), True, _WHITE)
                self.screen.blit(date, (base_x + 50, line_y))
                dur = self._small_font.render(f"时长: {int(t.get('duration', 0) // 60)}分{int(t.get('duration', 0) % 60)}秒", True, _GRAY)
                self.screen.blit(dur, (base_x + 260, line_y))
                line_y += 24

                rev = self._small_font.render(
                    f"收益:{t.get('total_money', 0)}  杯数:{t.get('total_cups', 0)}  秘方:{t.get('secret_count', 0)}  "
                    f"失败杯:{t.get('failed_cup_count', 0)}  记忆成功:{t.get('memory_successes', 0)}  记忆失败:{t.get('memory_failures', 0)}",
                    True, _WHITE)
                self.screen.blit(rev, (base_x + 14, line_y))
                line_y += 24

                attn = self._small_font.render(
                    f"专注:{t.get('avg_attention', 0):.1f}  轮次:{t.get('rounds', 0)}  "
                    f"原萃{t.get('stage1_min', 0)}min({t.get('stage1_avg', 0):.1f})  "
                    f"特调{t.get('stage2_min', 0)}min({t.get('stage2_avg', 0):.1f})  "
                    f"忆调{t.get('stage3_min', 0)}min({t.get('stage3_avg', 0):.1f})",
                    True, _GRAY)
                self.screen.blit(attn, (base_x + 14, line_y))
            y += card_h + 8
        return y

    def _draw_games_section(self, base_x: int, y: int, p: PlayerProfile) -> None:
        label = self._body_font.render("── 游戏记录 ──", True, _GOLD)
        self.screen.blit(label, (base_x, y))
        y += 36

        headers = ["日期", "模式", "收益", "杯数", "秘方", "专注", "时长"]
        cols = [0, 170, 260, 320, 370, 420, 500]
        for hdr, cx in zip(headers, cols):
            txt = self._small_font.render(hdr, True, _GRAY)
            self.screen.blit(txt, (base_x + cx, y))
        y += 26

        for g in reversed(p.games_history):
            if y > SCREEN_HEIGHT + 100:
                break
            mode_name = {"regular": "特调", "bci": "BCI", "memory": "忆调", "infinite": "原萃"}.get(
                g.get("mode", ""), g.get("mode", ""))
            values = [
                str(g.get("date", "")),
                mode_name,
                str(g.get("revenue", 0)),
                str(g.get("cups", 0)),
                str(g.get("secrets", 0)),
                f"{g.get('avg_attention', 0):.1f}",
                f"{int(g.get('duration', 0) // 60)}分{int(g.get('duration', 0) % 60)}秒",
            ]
            for val, cx in zip(values, cols):
                txt = self._small_font.render(val, True, _WHITE)
                self.screen.blit(txt, (base_x + cx, y))
            y += 24
