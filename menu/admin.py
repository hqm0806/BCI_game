"""管理后台 — 查看所有用户数据（含专注力曲线）"""

from __future__ import annotations

import json
import os

import pygame

from config import SCREEN_HEIGHT, SCREEN_WIDTH
from data.player_profile import PlayerProfile
from game.font_utils import load_chinese_font

_ACCOUNTS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "accounts.json")
_BG_COLOR = (15, 15, 25)
_CARD_BG = (35, 35, 55)
_CARD_HOVER = (50, 50, 75)
_GOLD = (255, 215, 0)
_WHITE = (240, 240, 245)
_GRAY = (150, 150, 160)
_RED = (220, 80, 80)
_BLUE = (80, 160, 220)
_ORANGE = (220, 160, 60)
_GREEN = (80, 200, 120)
_LIST_W = 280
_ROW_H = 36
_CHART_W = 650
_CHART_H = 200
_RIGHT_W = SCREEN_WIDTH - _LIST_W - 30


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

        back_w = 120
        self._back_rect = pygame.Rect(SCREEN_WIDTH - back_w - 20, 12, back_w, 40)
        self._back_hover = False

        self._list_rect = pygame.Rect(0, 60, _LIST_W, SCREEN_HEIGHT - 60)

        self._expanded_training: int | None = None
        self._expanded_game: int | None = None
        self._training_rects: list[pygame.Rect] = []
        self._game_rects: list[pygame.Rect] = []

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
            self._expanded_training = None
            self._expanded_game = None

    def run(self) -> None:
        while self.running:
            self.clock.tick(60)
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
                    for r, i in self._game_rects:
                        if r.collidepoint(mx, my):
                            self._expanded_game = None if self._expanded_game == i else i
                            self._expanded_training = None
                            break
                    for r, i in self._training_rects:
                        if r.collidepoint(mx, my):
                            self._expanded_training = None if self._expanded_training == i else i
                            self._expanded_game = None
                            break
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
        self._training_rects.clear()
        label = self._body_font.render("── 训练记录 ──", True, _GOLD)
        self.screen.blit(label, (base_x, y))
        y += 36

        for idx, t in enumerate(reversed(p.training_history)):
            if y > SCREEN_HEIGHT + 100:
                break
            orig_idx = len(p.training_history) - 1 - idx
            card_w = SCREEN_WIDTH - base_x - 20
            card_h = 90
            rect = pygame.Rect(base_x, y, card_w, card_h)
            self._training_rects.append((rect, orig_idx))

            if y + card_h > 0:
                is_expanded = self._expanded_training == orig_idx
                bg = _CARD_HOVER if is_expanded else _CARD_BG
                pygame.draw.rect(self.screen, bg, rect, border_radius=6)
                if is_expanded:
                    pygame.draw.rect(self.screen, _GOLD, rect, 2, border_radius=6)

                line_y = y + 8
                num = self._small_font.render(f"#{idx + 1}", True, _GOLD)
                self.screen.blit(num, (base_x + 10, line_y))
                date = self._small_font.render(str(t.get("date", "")), True, _WHITE)
                self.screen.blit(date, (base_x + 50, line_y))
                dur = self._small_font.render(
                    f"时长: {int(t.get('duration', 0) // 60)}分{int(t.get('duration', 0) % 60)}秒",
                    True, _GRAY)
                self.screen.blit(dur, (base_x + 260, line_y))
                hint = self._small_font.render("点击收起△" if is_expanded else "点击展开▼", True, _GRAY)
                self.screen.blit(hint, (base_x + card_w - 110, line_y))
                line_y += 24

                rev = self._small_font.render(
                    f"收益:{t.get('total_money', 0)}  杯数:{t.get('total_cups', 0)}  "
                    f"秘方:{t.get('secret_count', 0)}  失败杯:{t.get('failed_cup_count', 0)}  "
                    f"记忆成功:{t.get('memory_successes', 0)}  记忆失败:{t.get('memory_failures', 0)}",
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

            if is_expanded:
                fs = t.get("focus_samples") or []
                if fs:
                    chart_y = y
                    self._draw_focus_chart(base_x + 10, chart_y, _CHART_W, _CHART_H, fs,
                                            t.get("avg_attention", 0), "专注力曲线")
                    y = chart_y + _CHART_H + 6
                    # stage color bar
                    stage1_min = t.get("stage1_min", 0)
                    stage2_min = t.get("stage2_min", 0)
                    stage3_min = t.get("stage3_min", 0)
                    total_min = stage1_min + stage2_min + stage3_min
                    if total_min > 0:
                        bar_y = y
                        bar_h = 14
                        pygame.draw.rect(self.screen, (30, 30, 45), (base_x + 10, bar_y, _CHART_W, bar_h), border_radius=3)
                        s1_w = int(_CHART_W * stage1_min / total_min)
                        s2_w = int(_CHART_W * stage2_min / total_min)
                        s3_w = _CHART_W - s1_w - s2_w
                        if s1_w > 0:
                            pygame.draw.rect(self.screen, _ORANGE, (base_x + 10, bar_y, s1_w, bar_h), border_radius=3)
                        if s2_w > 0:
                            pygame.draw.rect(self.screen, _BLUE, (base_x + 10 + s1_w, bar_y, s2_w, bar_h))
                        if s3_w > 0:
                            pygame.draw.rect(self.screen, _GREEN, (base_x + 10 + s1_w + s2_w, bar_y, s3_w, bar_h),
                                             border_top_right_radius=3, border_bottom_right_radius=3)
                        txt = self._small_font.render(
                            f"原萃{stage1_min}min({t.get('stage1_avg', 0):.1f})  "
                            f"特调{stage2_min}min({t.get('stage2_avg', 0):.1f})  "
                            f"忆调{stage3_min}min({t.get('stage3_avg', 0):.1f})",
                            True, _GRAY)
                        self.screen.blit(txt, (base_x + 10, bar_y + bar_h + 6))
                        y = bar_y + bar_h + 28
                y += 6

        return y

    def _draw_games_section(self, base_x: int, y: int, p: PlayerProfile) -> None:
        self._game_rects.clear()
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
            row_h = 24
            rect = pygame.Rect(base_x, y, SCREEN_WIDTH - base_x - 20, row_h)
            orig_idx = len(p.games_history) - 1 - list(reversed(p.games_history)).index(g)
            self._game_rects.append((rect, orig_idx))
            is_expanded = self._expanded_game == orig_idx

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
            row_color = _CARD_HOVER if is_expanded else _CARD_BG
            pygame.draw.rect(self.screen, row_color, rect, border_radius=4)
            if is_expanded:
                pygame.draw.rect(self.screen, _GOLD, rect, 1, border_radius=4)

            for val, cx in zip(values, cols):
                txt = self._small_font.render(val, True, _WHITE)
                self.screen.blit(txt, (base_x + cx + 4, y + 2))
            expand_hint = self._small_font.render("▼" if not is_expanded else "△", True, _GRAY)
            self.screen.blit(expand_hint, (base_x + 640, y + 2))
            y += row_h + 4

            if is_expanded:
                fs = g.get("focus_samples") or []
                if fs:
                    chart_y = y
                    self._draw_focus_chart(base_x + 10, chart_y, _CHART_W, _CHART_H, fs,
                                            g.get("avg_attention", 0), "专注力曲线")
                    y = chart_y + _CHART_H + 12
                y += 4

    def _draw_focus_chart(self, x: int, y: int, w: int, h: int,
                           samples: list, avg: float, label: str = "") -> None:
        """绘制专注力曲线图"""
        if len(samples) < 2:
            return

        # background
        pygame.draw.rect(self.screen, (22, 22, 38), (x - 2, y - 2, w + 4, h + 4), border_radius=6)
        pygame.draw.rect(self.screen, (40, 40, 60), (x, y, w, h), border_radius=4)

        margin_l = 36
        margin_r = 10
        margin_t = 16
        margin_b = 22
        plot_w = w - margin_l - margin_r
        plot_h = h - margin_t - margin_b

        # grid
        for pct in (0, 25, 50, 75, 100):
            gy = y + margin_t + plot_h - int(plot_h * pct / 100)
            pygame.draw.line(self.screen, (50, 50, 70), (x + margin_l, gy), (x + margin_l + plot_w, gy), 1)
            txt = self._small_font.render(str(pct), True, _GRAY)
            self.screen.blit(txt, (x + 2, gy - txt.get_height() // 2))

        # X label
        xlbl = self._small_font.render(f"0", True, _GRAY)
        self.screen.blit(xlbl, (x + margin_l - xlbl.get_width() // 2, y + h - margin_b + 4))
        xlbl2 = self._small_font.render(str(len(samples)), True, _GRAY)
        self.screen.blit(xlbl2, (x + margin_l + plot_w - xlbl2.get_width() // 2, y + h - margin_b + 4))
        xlbl3 = self._small_font.render("采样点", True, _GRAY)
        self.screen.blit(xlbl3, (x + margin_l + plot_w // 2 - xlbl3.get_width() // 2, y + h - margin_b + 4))

        # title
        if label:
            ttl = self._small_font.render(label, True, _GOLD)
            self.screen.blit(ttl, (x + margin_l, y + 2))

        # average line
        avg_y = y + margin_t + plot_h - int(plot_h * min(avg, 100) / 100)
        dash_len = 6
        for dx in range(0, plot_w, dash_len * 2):
            ex = min(x + margin_l + dx + dash_len, x + margin_l + plot_w)
            pygame.draw.line(self.screen, _RED, (x + margin_l + dx, avg_y), (ex, avg_y), 1)
        avg_txt = self._small_font.render(f"avg={avg:.1f}", True, _RED)
        self.screen.blit(avg_txt, (x + margin_l + plot_w - avg_txt.get_width() - 4, avg_y - avg_txt.get_height() - 2))

        # line chart
        n = len(samples)
        step = max(1, n / plot_w)
        pts: list[tuple[int, int]] = []
        for i in range(min(n, int(plot_w / step) + 2)):
            si = min(int(i * step), n - 1)
            val = max(0, min(100, samples[si]))
            px = x + margin_l + int(plot_w * si / (n - 1)) if n > 1 else x + margin_l
            py = y + margin_t + plot_h - int(plot_h * val / 100)
            pts.append((px, py))

        if len(pts) >= 2:
            pygame.draw.aalines(self.screen, _GOLD, False, pts, 1)
