"""训练计划配置页面"""

from __future__ import annotations

import pygame

from config import SCREEN_HEIGHT, SCREEN_WIDTH
from data.training_plan import TrainingPlan
from game.font_utils import load_chinese_font

_MODE_OPTIONS = [
    ("infinite", "原萃模式"),
    ("bci", "特调模式"),
    ("memory", "忆调模式"),
    ("experiment", "实验模式"),
]


class TrainingPlanScreen:
    def __init__(
        self,
        screen: pygame.Surface,
        username: str,
        bg: pygame.Surface | None = None,
    ) -> None:
        self.screen = screen
        self._username = username
        self._bg = bg
        self.clock = pygame.time.Clock()
        self.title_font = load_chinese_font(48)
        self.font = load_chinese_font(28)
        self.small_font = load_chinese_font(20)
        self.running = True
        self._result = "menu"

        self._plan = TrainingPlan.load_for_user(username)
        self._phases = [dict(p) for p in self._plan.phases]
        self._total_sessions = self._plan.total_sessions
        self._editing_phase = -1
        self._editing_sessions = False
        self._scroll = 0

    def run(self) -> tuple[str, TrainingPlan]:
        while self.running:
            self.clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    self._result = "quit"
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_RETURN:
                        self._result = "start_training"
                        self._save()
                        self.running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._handle_click(event.pos)

            self._draw()

        return self._result, self._plan

    def _save(self) -> None:
        self._plan.phases = self._phases
        self._plan.total_sessions = self._total_sessions
        self._plan.reset_progress()
        self._plan.save()

    def _handle_click(self, pos: tuple[int, int]) -> None:
        mx, my = pos
        start_y = 120
        row_h = 42
        for i, phase in enumerate(self._phases):
            y = start_y + i * row_h - self._scroll
            if 600 < mx < 680 and y < my < y + row_h:
                # delete button
                if len(self._phases) > 1:
                    self._phases.pop(i)
                return
            if 480 < mx < 560 and y < my < y + row_h:
                # duration - button
                phase["duration"] = max(1, phase["duration"] - 1)
                return
            if 560 < mx < 600 and y < my < y + row_h:
                # duration + button
                phase["duration"] = min(3600, phase["duration"] + 1)
                return
            if 200 < mx < 450 and y < my < y + row_h:
                # mode selector
                current = phase["mode"]
                idx = next((j for j, (k, _) in enumerate(_MODE_OPTIONS) if k == current), 0)
                idx = (idx + 1) % len(_MODE_OPTIONS)
                phase["mode"] = _MODE_OPTIONS[idx][0]
                phase["name"] = _MODE_OPTIONS[idx][1]
                return
        # add phase button
        if 200 < mx < 400 and start_y + len(self._phases) * row_h - self._scroll < my < start_y + (len(self._phases) + 1) * row_h - self._scroll:
            self._phases.append({"mode": "infinite", "name": "原萃阶段", "duration": 180})
            return
        # sessions +/-
        sessions_y = start_y + (len(self._phases) + 2) * row_h - self._scroll
        if 400 < mx < 460 and sessions_y < my < sessions_y + row_h:
            self._total_sessions = max(1, self._total_sessions - 1)
            return
        if 460 < mx < 520 and sessions_y < my < sessions_y + row_h:
            self._total_sessions = min(999, self._total_sessions + 1)
            return
        # save button
        if 250 < mx < 430 and sessions_y + 60 < my < sessions_y + 108:
            self._save()
            self.running = False
            self._result = "menu"
            return
        # start button
        if 480 < mx < 660 and sessions_y + 60 < my < sessions_y + 108 and not self._plan.is_complete():
            self._save()
            self.running = False
            self._result = "start_training"
            return

    def _draw(self) -> None:
        if self._bg:
            self.screen.blit(self._bg, (0, 0))
        else:
            self.screen.fill((30, 25, 20))

        shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 220))
        self.screen.blit(shade, (0, 0))

        title = self.title_font.render("训练计划", True, (255, 220, 100))
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 30))

        progress_text = f"已完成 {self._plan.completed_sessions}/{self._plan.total_sessions} 轮"
        if self._plan.is_complete():
            progress_text += " — 全部完成！"
        p_surf = self.font.render(progress_text, True, (100, 255, 100) if self._plan.is_complete() else (200, 200, 200))
        self.screen.blit(p_surf, (SCREEN_WIDTH // 2 - p_surf.get_width() // 2, 80))

        start_y = 120
        row_h = 42
        total_secs = sum(p.get("duration", 0) for p in self._phases) * self._total_sessions

        for i, phase in enumerate(self._phases):
            y = start_y + i * row_h - self._scroll
            mode_name = next((n for k, n in _MODE_OPTIONS if k == phase["mode"]), "原萃模式")
            dur = phase["duration"]
            dur_str = f"{dur // 60}分{dur % 60}秒" if dur >= 60 else f"{dur}秒"

            line = f"阶段 {i+1}:" if len(self._phases) > 1 else "训练内容:"

            # phase label
            s1 = self.font.render(line, True, (180, 180, 180))
            self.screen.blit(s1, (50, y))
            # mode
            s2 = self.font.render(f"[{mode_name}]", True, (200, 180, 255))
            self.screen.blit(s2, (220, y))
            # duration
            s3 = self.small_font.render(f"时长: [-] {dur_str} [+]", True, (180, 180, 180))
            self.screen.blit(s3, (480, y + 10))
            # delete
            s4 = self.small_font.render("[X]", True, (200, 80, 80))
            self.screen.blit(s4, (610, y + 10))

        # add button
        add_y = start_y + len(self._phases) * row_h - self._scroll
        add_s = self.small_font.render("[+ 新增阶段]", True, (100, 200, 100))
        self.screen.blit(add_s, (200, add_y + 10))

        # sessions
        sessions_y = start_y + (len(self._phases) + 2) * row_h - self._scroll
        ss = self.font.render(f"总训练轮数: [-] {self._total_sessions} [+]", True, (255, 255, 255))
        self.screen.blit(ss, (200, sessions_y))

        # total time
        total_min = total_secs / 60
        ts = self.small_font.render(f"总时长: {total_min:.0f} 分钟", True, (150, 150, 150))
        self.screen.blit(ts, (200, sessions_y + 35))

        # buttons
        btn_y = sessions_y + 75
        btn_w, btn_h = 180, 48
        save_rect = pygame.Rect(260, btn_y, btn_w, btn_h)
        start_rect = pygame.Rect(480, btn_y, btn_w, btn_h)

        mx, my = pygame.mouse.get_pos()
        save_hover = save_rect.collidepoint(mx, my)
        start_hover = start_rect.collidepoint(mx, my)
        completed = self._plan.is_complete()

        save_bg = (100, 60, 25) if save_hover else (50, 28, 12)
        start_bg = (60, 130, 60) if (start_hover and not completed) else ((25, 50, 20) if not completed else (70, 70, 70))

        pygame.draw.rect(self.screen, save_bg, save_rect, border_radius=10)
        pygame.draw.rect(self.screen, (255, 255, 255, 60), save_rect, 2, border_radius=10)
        save_text = self.font.render("保存计划", True, (255, 255, 255))
        self.screen.blit(save_text, (save_rect.centerx - save_text.get_width() // 2, save_rect.centery - save_text.get_height() // 2))

        pygame.draw.rect(self.screen, start_bg, start_rect, border_radius=10)
        pygame.draw.rect(self.screen, (255, 255, 255, 80), start_rect, 2, border_radius=10)
        start_text = self.font.render("开始训练", True, (255, 255, 255))
        self.screen.blit(start_text, (start_rect.centerx - start_text.get_width() // 2, start_rect.centery - start_text.get_height() // 2))

        hint = self.small_font.render("ESC 返回 | Enter 快速开始", True, (150, 150, 150))
        self.screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, SCREEN_HEIGHT - 30))

        pygame.display.flip()
