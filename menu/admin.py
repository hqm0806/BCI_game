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
        self._max_scroll_users = max(0, len(self._users) * _ROW_H - (SCREEN_HEIGHT - 110))

        back_w = 120
        self._back_rect = pygame.Rect(SCREEN_WIDTH - back_w - 20, 12, back_w, 40)
        self._back_hover = False

        self._list_rect = pygame.Rect(0, 90, _LIST_W, SCREEN_HEIGHT - 90)

        self._expanded_entry: int | None = None
        self._entry_rects: list[tuple[pygame.Rect, int]] = []
        self._sorted_entries: list[dict] = []
        self._delete_target: str | None = None
        self._confirm_rect = pygame.Rect(0, 0, 100, 36)
        self._cancel_rect = pygame.Rect(0, 0, 100, 36)

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
            self._expanded_entry = None

    def run(self) -> None:
        while self.running:
            self.clock.tick(60)
            mx, my = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if self._delete_target:
                            self._delete_target = None
                        else:
                            self.running = False
                    if self._delete_target:
                        break
                    if event.key == pygame.K_UP and self._selected_idx > 0:
                        self._selected_idx -= 1
                        self._load_profile(self._selected_idx)
                    if event.key == pygame.K_DOWN and self._selected_idx < len(self._users) - 1:
                        self._selected_idx += 1
                        self._load_profile(self._selected_idx)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self._delete_target:
                        if self._confirm_rect.collidepoint(mx, my):
                            self._do_delete(self._delete_target)
                        elif self._cancel_rect.collidepoint(mx, my):
                            self._delete_target = None
                        break
                    if self._back_rect.collidepoint(mx, my):
                        self.running = False
                    if self._list_rect.collidepoint(mx, my):
                        clicked = (my - 90 + self._scroll_users) // _ROW_H
                        if 0 <= clicked < len(self._users):
                            self._selected_idx = clicked
                            self._load_profile(clicked)
                    for r, i in self._entry_rects:
                        if r.collidepoint(mx, my):
                            self._expanded_entry = None if self._expanded_entry == i else i
                            break
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                    if not self._delete_target and self._list_rect.collidepoint(mx, my):
                        clicked = (my - 90 + self._scroll_users) // _ROW_H
                        if 0 <= clicked < len(self._users):
                            self._delete_target = self._users[clicked]
                if event.type == pygame.MOUSEWHEEL:
                    if self._delete_target:
                        continue
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
        pygame.draw.line(self.screen, (50, 50, 70), (_LIST_W, 90), (_LIST_W, SCREEN_HEIGHT), 2)

        self._draw_user_list()
        if self._profile:
            self._draw_user_detail()
        else:
            hint = self._body_font.render("请选择用户", True, _GRAY)
            self.screen.blit(hint, (_LIST_W + 40, 100))

        if self._delete_target:
            self._draw_delete_dialog()

    def _do_delete(self, username: str) -> None:
        try:
            with open(_ACCOUNTS_PATH, "r", encoding="utf-8") as f:
                accounts = json.load(f)
            accounts.pop(username, None)
            with open(_ACCOUNTS_PATH, "w", encoding="utf-8") as f:
                json.dump(accounts, f, ensure_ascii=False, indent=4)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        profiles_dir = os.path.join(os.path.dirname(__file__), "..", "profiles")
        for suffix in ("", "_training"):
            p = os.path.join(profiles_dir, f"{username}{suffix}.json")
            if os.path.exists(p):
                os.remove(p)

        if username in self._users:
            old_idx = self._users.index(username)
            self._users.remove(username)
            if self._users:
                self._selected_idx = min(old_idx, len(self._users) - 1)
                self._load_profile(self._selected_idx)
            else:
                self._selected_idx = 0
                self._profile = None
        self._max_scroll_users = max(0, len(self._users) * _ROW_H - (SCREEN_HEIGHT - 110))
        self._scroll_users = min(self._scroll_users, self._max_scroll_users)
        self._delete_target = None

    def _draw_delete_dialog(self) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        dw, dh = 420, 160
        dx = (SCREEN_WIDTH - dw) // 2
        dy = (SCREEN_HEIGHT - dh) // 2
        pygame.draw.rect(self.screen, (40, 40, 60), (dx, dy, dw, dh), border_radius=12)
        pygame.draw.rect(self.screen, _GOLD, (dx, dy, dw, dh), 2, border_radius=12)

        msg = self._body_font.render(f"确认删除用户 {self._delete_target}？", True, _WHITE)
        self.screen.blit(msg, (dx + (dw - msg.get_width()) // 2, dy + 30))

        btn_w, btn_h = 100, 36
        confirm_x = dx + dw // 2 - btn_w - 20
        cancel_x = dx + dw // 2 + 20
        btn_y = dy + dh - btn_h - 24

        self._confirm_rect = pygame.Rect(confirm_x, btn_y, btn_w, btn_h)
        self._cancel_rect = pygame.Rect(cancel_x, btn_y, btn_w, btn_h)
        mx, my = pygame.mouse.get_pos()

        cc = (200, 50, 50) if self._confirm_rect.collidepoint(mx, my) else _RED
        pygame.draw.rect(self.screen, cc, self._confirm_rect, border_radius=6)
        c_txt = self._small_font.render("确认", True, _WHITE)
        self.screen.blit(c_txt, (self._confirm_rect.centerx - c_txt.get_width() // 2,
                                  self._confirm_rect.centery - c_txt.get_height() // 2))

        nc = (80, 80, 100) if self._cancel_rect.collidepoint(mx, my) else _GRAY
        pygame.draw.rect(self.screen, nc, self._cancel_rect, border_radius=6)
        n_txt = self._small_font.render("取消", True, _WHITE)
        self.screen.blit(n_txt, (self._cancel_rect.centerx - n_txt.get_width() // 2,
                                  self._cancel_rect.centery - n_txt.get_height() // 2))

    def _draw_user_list(self) -> None:
        count_txt = self._small_font.render(f"共 {len(self._users)} 人", True, _GRAY)
        self.screen.blit(count_txt, (12, 62))
        visible_start = self._scroll_users // _ROW_H
        visible_end = min(len(self._users), visible_start + (SCREEN_HEIGHT - 90) // _ROW_H + 1)

        for i in range(visible_start, visible_end):
            y = 90 + i * _ROW_H - self._scroll_users
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

        self._build_entries(p)

        chart_bottom = SCREEN_HEIGHT - 20
        chart_h = 220
        chart_top = chart_bottom - chart_h
        max_list_y = chart_top - 24

        self._draw_unified_section(base_x, y, max_list_y)

        chart_w = SCREEN_WIDTH - base_x - 40
        self._draw_overall_trend(base_x + 20, chart_top, chart_w - 20, chart_h - 30)

    def _build_entries(self, p: PlayerProfile) -> None:
        self._sorted_entries = []
        for g in p.games_history:
            e = dict(g)
            e["_type"] = "game"
            self._sorted_entries.append(e)
        for t in p.training_history:
            e = dict(t)
            e["_type"] = "training"
            self._sorted_entries.append(e)
        self._sorted_entries.sort(key=lambda x: x.get("date", ""), reverse=True)

    def _draw_unified_section(self, base_x: int, y: int, max_list_y: int) -> None:
        self._entry_rects.clear()
        label = self._body_font.render("【游戏记录】", True, _GOLD)
        self.screen.blit(label, (base_x, y))
        y += 36

        headers = ["模式", "日期", "时长", "收益", "杯数", "秘方", "专注"]
        cols = [0, 90, 280, 410, 480, 530, 580]
        for hdr, cx in zip(headers, cols):
            txt = self._small_font.render(hdr, True, _GRAY)
            self.screen.blit(txt, (base_x + cx, y))
        y += 26

        for idx, entry in enumerate(self._sorted_entries):
            if y > max_list_y:
                break
            row_h = 24
            rect = pygame.Rect(base_x, y, SCREEN_WIDTH - base_x - 20, row_h)
            self._entry_rects.append((rect, idx))
            is_expanded = self._expanded_entry == idx

            is_training = entry["_type"] == "training"
            if is_training:
                mode_str = "训练"
            else:
                mode_str = {"regular": "特调", "bci": "BCI", "memory": "忆调", "infinite": "原萃"}.get(
                    entry.get("mode", ""), entry.get("mode", ""))

            dur = entry.get("duration", 0)
            dur_str = f"{int(dur // 60)}分{int(dur % 60)}秒" if dur else "—"
            values = [
                mode_str,
                str(entry.get("date", "")),
                dur_str,
                str(entry.get("revenue", entry.get("total_money", 0))),
                str(entry.get("cups", entry.get("total_cups", 0))),
                str(entry.get("secrets", entry.get("secret_count", 0))),
                f"{entry.get('avg_attention', 0):.1f}",
            ]
            row_color = _CARD_HOVER if is_expanded else _CARD_BG
            pygame.draw.rect(self.screen, row_color, rect, border_radius=4)
            if is_expanded:
                pygame.draw.rect(self.screen, _GOLD, rect, 1, border_radius=4)

            for val, cx in zip(values, cols):
                txt = self._small_font.render(val, True, _WHITE)
                self.screen.blit(txt, (base_x + cx + 4, y + 2))
            expand_hint = self._small_font.render("[展开]" if not is_expanded else "[收起]", True, _GRAY)
            self.screen.blit(expand_hint, (base_x + 650, y + 2))
            y += row_h + 4

            if is_expanded:
                if y > max_list_y:
                    y += row_h + 4
                    continue
                fs = entry.get("focus_samples") or []
                if fs:
                    chart_y = y
                    self._draw_focus_chart(base_x + 10, chart_y, _CHART_W, _CHART_H, fs,
                                            entry.get("avg_attention", 0), "专注力曲线",
                                            duration=entry.get("duration", 0))
                    y = chart_y + _CHART_H + 6

                    if is_training:
                        stage1_min = entry.get("stage1_min", 0)
                        stage2_min = entry.get("stage2_min", 0)
                        stage3_min = entry.get("stage3_min", 0)
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
                                f"原萃{stage1_min}min({entry.get('stage1_avg', 0):.1f})  "
                                f"特调{stage2_min}min({entry.get('stage2_avg', 0):.1f})  "
                                f"忆调{stage3_min}min({entry.get('stage3_avg', 0):.1f})",
                                True, _GRAY)
                            self.screen.blit(txt, (base_x + 10, bar_y + bar_h + 6))
                            y = bar_y + bar_h + 28
                y += 6

        if not self._sorted_entries:
            hint = self._small_font.render("暂无游戏记录", True, _GRAY)
            self.screen.blit(hint, (base_x, y))

    def _draw_overall_trend(self, x: int, y: int, w: int, h: int) -> None:
        entries = [e for e in self._sorted_entries if e.get("avg_attention", 0) > 0]
        entries.reverse()
        if not entries:
            hint = self._small_font.render("暂无游戏数据", True, _GRAY)
            self.screen.blit(hint, (x + w // 2 - hint.get_width() // 2, y + h // 2))
            return

        pygame.draw.rect(self.screen, (30, 30, 50), (x, y, w, h), border_radius=6)

        for i in range(0, 101, 25):
            py = y + int((1.0 - i / 100.0) * h)
            pygame.draw.line(self.screen, (60, 60, 80), (x, py), (x + w, py), 1)
            lbl = self._small_font.render(str(i), True, _GRAY)
            self.screen.blit(lbl, (x - 28, py - 7))

        y_label = self._small_font.render("专注力", True, _GRAY)
        self.screen.blit(y_label, (x - 28, y - 18))

        n = len(entries)
        points = []
        for idx, e in enumerate(entries):
            val = e.get("avg_attention", 0)
            px = x + int((idx / (n - 1)) * w) if n > 1 else x + w // 2
            py = y + int((1.0 - val / 100.0) * h)
            py = max(y, min(y + h, py))
            points.append((px, py))

        if len(points) >= 2:
            pygame.draw.lines(self.screen, (100, 255, 150), False, points, 2)

        for px, py in points:
            pygame.draw.circle(self.screen, (255, 200, 100), (px, py), 4)

        if n <= 12:
            for idx, e in enumerate(entries):
                date_str = str(e.get("date", ""))[5:10]
                lbl = self._small_font.render(date_str, True, _GRAY)
                self.screen.blit(lbl, (points[idx][0] - lbl.get_width() // 2, y + h + 4))
        else:
            step = max(1, n // 10)
            for idx in range(0, n, step):
                date_str = str(entries[idx].get("date", ""))[5:10]
                lbl = self._small_font.render(date_str, True, _GRAY)
                self.screen.blit(lbl, (points[idx][0] - lbl.get_width() // 2, y + h + 4))

    def _draw_focus_chart(self, x: int, y: int, w: int, h: int,
                           samples: list, avg: float, label: str = "",
                           duration: float = 0) -> None:
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
        xlbl = self._small_font.render("0min", True, _GRAY)
        self.screen.blit(xlbl, (x + margin_l - xlbl.get_width() // 2, y + h - margin_b + 4))
        total_min = int(duration / 60) if duration > 0 else 0
        xlbl2 = self._small_font.render(f"{total_min}min", True, _GRAY)
        self.screen.blit(xlbl2, (x + margin_l + plot_w - xlbl2.get_width() // 2, y + h - margin_b + 4))

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
