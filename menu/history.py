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

    _MODE_LABELS = {"all": "全部", "bci": "BCI", "memory": "忆调", "infinite": "原萃", "regular": "特调"}

    def __init__(self, screen: pygame.Surface, games: list[dict], profile=None) -> None:
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.games = list(reversed(games))
        self._profile = profile
        self.title_font = load_chinese_font(48)
        self.font = load_chinese_font(28)
        self.hint_font = load_chinese_font(20)
        self.small_font = load_chinese_font(16)
        self._scroll = 0
        self._item_h = 80
        self._visible = (SCREEN_HEIGHT - 140) // self._item_h
        self._mode_filter = "all"
        self._dialog_active = False
        self._dialog_text = ""
        self._dialog_delete_idx = -1
        self._dialog_delete_all = False
        self._dlg_confirm_rect = pygame.Rect(0, 0, 0, 0)
        self._dlg_cancel_rect = pygame.Rect(0, 0, 0, 0)

    @property
    def _filtered_games(self) -> list[dict]:
        if self._mode_filter == "all":
            return self.games
        return [g for g in self.games if g.get("mode", "") == self._mode_filter]

    def run(self) -> None:
        LEFT_W = 580
        RIGHT_X = LEFT_W + 10
        RIGHT_W = SCREEN_WIDTH - RIGHT_X

        clear_btn_rect = pygame.Rect(LEFT_W - 130, 50, 120, 30)
        filter_btns: list[tuple[pygame.Rect, str]] = []
        btn_x = 40
        for key in ["all", "bci", "memory", "infinite", "regular"]:
            r = pygame.Rect(btn_x, 88, 56, 24)
            filter_btns.append((r, key))
            btn_x += 60

        while True:
            self.clock.tick(60)
            mx, my = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                if self._dialog_active:
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if self._dlg_confirm_rect.collidepoint(event.pos):
                            self._execute_delete()
                            self._dialog_active = False
                        elif self._dlg_cancel_rect.collidepoint(event.pos):
                            self._dialog_active = False
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_RETURN:
                            self._execute_delete()
                            self._dialog_active = False
                        elif event.key == pygame.K_ESCAPE:
                            self._dialog_active = False
                    continue

                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return
                if event.type == pygame.MOUSEWHEEL:
                    filtered = self._filtered_games
                    max_scroll = max(0, len(filtered) - self._visible)
                    self._scroll = max(0, min(max_scroll, self._scroll - event.y))
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        if mx < LEFT_W:
                            for r, key in filter_btns:
                                if r.collidepoint(mx, my):
                                    self._mode_filter = key
                                    self._scroll = 0
                                    break
                            else:
                                filtered = self._filtered_games
                                idx = self._scroll + (my - 120) // self._item_h
                                if 0 <= idx < len(filtered):
                                    self._show_detail(filtered[idx])
                        if clear_btn_rect.collidepoint(mx, my) and self.games:
                            self._show_confirm_dialog("确认清除全部历史记录？", delete_all=True)
                    elif event.button == 3:
                        if mx < LEFT_W:
                            filtered = self._filtered_games
                            idx = self._scroll + (my - 120) // self._item_h
                            if 0 <= idx < len(filtered):
                                self._show_confirm_dialog("确认删除该条历史记录？", delete_idx=idx)

            self.screen.fill((25, 25, 45))

            left_bg = pygame.Surface((LEFT_W, SCREEN_HEIGHT), pygame.SRCALPHA)
            left_bg.fill((255, 255, 255, 10))
            self.screen.blit(left_bg, (0, 0))

            left_title = self.title_font.render("历史记录", True, (255, 220, 150))
            self.screen.blit(left_title, (LEFT_W // 2 - left_title.get_width() // 2, 30))

            pygame.draw.line(self.screen, (80, 80, 100), (40, 80), (LEFT_W - 40, 80), 1)

            for r, key in filter_btns:
                active = self._mode_filter == key
                fill = (255, 180, 60) if active else (50, 50, 70)
                hover = r.collidepoint(mx, my)
                if hover and not active:
                    fill = (70, 70, 100)
                pygame.draw.rect(self.screen, fill, r, border_radius=6)
                label = self.small_font.render(self._MODE_LABELS[key], True, (255, 255, 255) if active else (180, 180, 200))
                self.screen.blit(label, (r.centerx - label.get_width() // 2, r.centery - label.get_height() // 2))

            filtered = self._filtered_games
            if not self.games:
                no_rec = self.font.render("暂无记录", True, (150, 150, 150))
                self.screen.blit(no_rec, (LEFT_W // 2 - no_rec.get_width() // 2, 200))
            elif not filtered:
                no_rec = self.font.render("该模式暂无记录", True, (150, 150, 150))
                self.screen.blit(no_rec, (LEFT_W // 2 - no_rec.get_width() // 2, 200))

            for i in range(self._scroll, min(self._scroll + self._visible + 1, len(filtered))):
                g = filtered[i]
                row_y = 120 + (i - self._scroll) * self._item_h
                row_rect = pygame.Rect(20, row_y, LEFT_W - 40, self._item_h - 4)

                hover = row_rect.collidepoint(pygame.mouse.get_pos())
                alpha = 40 if hover else 20
                row_bg = pygame.Surface((row_rect.width, row_rect.height), pygame.SRCALPHA)
                row_bg.fill((255, 255, 255, alpha))
                self.screen.blit(row_bg, row_rect)
                pygame.draw.rect(self.screen, (60, 60, 80), row_rect, 1, border_radius=6)

                date = self.hint_font.render(g.get("date", "未知"), True, (255, 255, 255))
                self.screen.blit(date, (row_rect.x + 10, row_rect.y + 6))

                mode_name = {"regular": "特调", "bci": "BCI", "memory": "忆调", "infinite": "原萃"}.get(
                    g.get("mode", ""), ""
                )
                mins = int(g.get("duration", 0)) // 60
                secs = int(g.get("duration", 0)) % 60
                info = self.hint_font.render(
                    f"{mode_name} | 收益:{g.get('revenue', 0)} | {mins}分{secs}秒 | 专注:{g.get('avg_attention', 0):.0f}",
                    True,
                    (180, 180, 200),
                )
                self.screen.blit(info, (row_rect.x + 10, row_rect.y + 40))

            if self.games:
                btn_hover = clear_btn_rect.collidepoint(mx, my)
                btn_fill = (180, 60, 60) if btn_hover else (120, 40, 40)
                pygame.draw.rect(self.screen, btn_fill, clear_btn_rect, border_radius=5)
                pygame.draw.rect(self.screen, (200, 80, 80), clear_btn_rect, 1, border_radius=5)
                btn_text = self.small_font.render("一键清除", True, (255, 255, 255))
                self.screen.blit(
                    btn_text,
                    (
                        clear_btn_rect.centerx - btn_text.get_width() // 2,
                        clear_btn_rect.centery - btn_text.get_height() // 2,
                    ),
                )

            right_bg = pygame.Surface((RIGHT_W, SCREEN_HEIGHT), pygame.SRCALPHA)
            right_bg.fill((255, 255, 255, 10))
            self.screen.blit(right_bg, (RIGHT_X, 0))

            pygame.draw.line(self.screen, (80, 80, 100), (LEFT_W, 60), (LEFT_W, SCREEN_HEIGHT), 2)

            curve_title = self.title_font.render("时间-专注力趋势曲线", True, (255, 220, 150))
            self.screen.blit(curve_title, (RIGHT_X + RIGHT_W // 2 - curve_title.get_width() // 2, 30))

            pygame.draw.line(self.screen, (80, 80, 100), (RIGHT_X + 40, 80), (SCREEN_WIDTH - 40, 80), 1)

            self._draw_trend_curve(RIGHT_X, RIGHT_W)

            esc = self.hint_font.render("ESC 返回 | 滚轮翻页 | 左键详情 | 右键删除", True, (120, 120, 140))
            self.screen.blit(esc, (SCREEN_WIDTH // 2 - esc.get_width() // 2, SCREEN_HEIGHT - 40))

            if self._dialog_active:
                self._draw_dialog()

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

            mode_name = {"regular": "特调模式", "bci": "BCI模式", "memory": "忆调模式", "infinite": "原萃模式"}.get(
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

    def _draw_trend_curve(self, right_x: int, right_w: int) -> None:
        regular_games = [g for g in self.games if g.get("mode") in ("regular", "bci")]
        regular_games.sort(key=lambda g: g.get("date", ""))

        graph_x = right_x + 60
        graph_y = 110
        graph_w = right_w - 100
        graph_h = 280

        pygame.draw.rect(self.screen, (30, 30, 50), (graph_x, graph_y, graph_w, graph_h), border_radius=6)

        for i in range(0, 101, 25):
            py = graph_y + int((1.0 - i / 100.0) * graph_h)
            pygame.draw.line(self.screen, (60, 60, 80), (graph_x, py), (graph_x + graph_w, py), 1)
            label = self.small_font.render(str(i), True, (120, 120, 120))
            self.screen.blit(label, (graph_x - 30, py - 7))

        y_label = self.small_font.render("专注力", True, (140, 140, 160))
        self.screen.blit(y_label, (graph_x - 30, graph_y - 18))

        if not regular_games:
            no_data = self.font.render("暂无特调模式数据", True, (150, 150, 150))
            self.screen.blit(
                no_data,
                (graph_x + graph_w // 2 - no_data.get_width() // 2, graph_y + graph_h // 2 - 10),
            )
        else:
            n = len(regular_games)
            points = []
            for idx, g in enumerate(regular_games):
                val = g.get("last_5min_avg_attention", g.get("avg_attention", 0))
                if n > 1:
                    px = graph_x + int((idx / (n - 1)) * graph_w)
                else:
                    px = graph_x + graph_w // 2
                py = graph_y + int((1.0 - val / 100.0) * graph_h)
                py = max(graph_y, min(graph_y + graph_h, py))
                points.append((px, py))

            if len(points) >= 2:
                pygame.draw.lines(self.screen, (100, 255, 150), False, points, 2)

            for px, py in points:
                pygame.draw.circle(self.screen, (255, 200, 100), (px, py), 4)

            if n <= 12:
                for idx, g in enumerate(regular_games):
                    date_str = g.get("date", "")[5:10]
                    label = self.small_font.render(date_str, True, (120, 120, 120))
                    if n > 1:
                        px = graph_x + int((idx / (n - 1)) * graph_w)
                    else:
                        px = graph_x + graph_w // 2
                    self.screen.blit(label, (px - 12, graph_y + graph_h + 4))
            else:
                step = max(1, n // 10)
                for idx in range(0, n, step):
                    date_str = regular_games[idx].get("date", "")[5:10]
                    label = self.small_font.render(date_str, True, (120, 120, 120))
                    px = graph_x + int((idx / (n - 1)) * graph_w)
                    self.screen.blit(label, (px - 12, graph_y + graph_h + 4))

        text_box_y = graph_y + graph_h + 45
        text_box_h = SCREEN_HEIGHT - text_box_y - 40
        pygame.draw.rect(self.screen, (40, 40, 60), (graph_x, text_box_y, graph_w, text_box_h), border_radius=6)
        pygame.draw.rect(self.screen, (100, 100, 140), (graph_x, text_box_y, graph_w, text_box_h), 2, border_radius=6)

        lines = [
            "专注力训练小贴士",
            "",
            "• 稳定的专注力是制作美味奶茶的关键",
            "• 保持放松，让头部自然微动",
            "• 避免刻意僵直或咬牙",
            "• 秘方触发需要持续高专注",
            "• 深呼吸有助于提升专注表现",
        ]
        line_h = self.hint_font.get_height() + 6
        start_y = text_box_y + 12
        for i, line in enumerate(lines):
            if not line:
                continue
            color = (255, 220, 150) if i == 0 else (180, 180, 200)
            surf = self.hint_font.render(line, True, color)
            self.screen.blit(surf, (graph_x + 16, start_y + i * line_h))

    def _show_confirm_dialog(self, text: str, delete_idx: int = -1, delete_all: bool = False) -> None:
        self._dialog_active = True
        self._dialog_text = text
        self._dialog_delete_idx = delete_idx
        self._dialog_delete_all = delete_all

    def _execute_delete(self) -> None:
        if not self._profile:
            return
        if self._dialog_delete_all:
            self._profile.clear_history()
            self.games = []
        elif self._dialog_delete_idx >= 0:
            filtered = self._filtered_games
            if self._dialog_delete_idx < len(filtered):
                target = filtered[self._dialog_delete_idx]
                try:
                    real_idx = self.games.index(target)
                except ValueError:
                    real_idx = -1
                if real_idx >= 0:
                    original_len = len(self._profile.games_history)
                    reversed_idx = original_len - 1 - real_idx
                    if 0 <= reversed_idx < original_len:
                        self._profile.remove_game(reversed_idx)
            self._refresh_games()
        self._profile.save()
        self._scroll = 0

    def _refresh_games(self) -> None:
        if self._profile:
            self.games = list(reversed(self._profile.games_history))

    def _draw_dialog(self) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        dlg_w = 480
        dlg_h = 200
        dlg_x = (SCREEN_WIDTH - dlg_w) // 2
        dlg_y = (SCREEN_HEIGHT - dlg_h) // 2

        pygame.draw.rect(self.screen, (40, 35, 30), (dlg_x, dlg_y, dlg_w, dlg_h), border_radius=16)
        pygame.draw.rect(self.screen, (200, 120, 80), (dlg_x, dlg_y, dlg_w, dlg_h), 3, border_radius=16)

        text_surf = self.font.render(self._dialog_text, True, (255, 255, 255))
        self.screen.blit(text_surf, (dlg_x + (dlg_w - text_surf.get_width()) // 2, dlg_y + 35))

        btn_w = 140
        btn_h = 45
        btn_y = dlg_y + 105
        gap = 60
        total_btn_w = btn_w * 2 + gap
        btn_start_x = dlg_x + (dlg_w - total_btn_w) // 2

        confirm_rect = pygame.Rect(btn_start_x, btn_y, btn_w, btn_h)
        cancel_rect = pygame.Rect(btn_start_x + btn_w + gap, btn_y, btn_w, btn_h)

        self._dlg_confirm_rect = confirm_rect
        self._dlg_cancel_rect = cancel_rect

        mx, my = pygame.mouse.get_pos()

        c_hover = confirm_rect.collidepoint(mx, my)
        confirm_fill = (200, 70, 50) if c_hover else (160, 50, 30)
        pygame.draw.rect(self.screen, confirm_fill, confirm_rect, border_radius=8)
        pygame.draw.rect(self.screen, (220, 100, 80), confirm_rect, 2, border_radius=8)
        confirm_text = self.hint_font.render("确认", True, (255, 255, 255))
        self.screen.blit(
            confirm_text,
            (
                confirm_rect.centerx - confirm_text.get_width() // 2,
                confirm_rect.centery - confirm_text.get_height() // 2,
            ),
        )

        x_hover = cancel_rect.collidepoint(mx, my)
        cancel_fill = (100, 100, 110) if x_hover else (70, 70, 80)
        pygame.draw.rect(self.screen, cancel_fill, cancel_rect, border_radius=8)
        pygame.draw.rect(self.screen, (140, 140, 150), cancel_rect, 2, border_radius=8)
        cancel_text = self.hint_font.render("取消", True, (255, 255, 255))
        self.screen.blit(
            cancel_text,
            (cancel_rect.centerx - cancel_text.get_width() // 2, cancel_rect.centery - cancel_text.get_height() // 2),
        )
