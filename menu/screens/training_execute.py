"""训练执行页面"""

from __future__ import annotations

import os

import pygame

from bci.data_reader import BCIDataReader
from config import (
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SETTINGS_PANEL_IMG,
)
from game.font_utils import load_chinese_font
from menu.components import MenuItem


class _PlainButton(MenuItem):
    def trigger_click(self) -> None:
        pass


class TrainingExecuteScreen:
    """训练执行页面"""

    def __init__(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
        title_font: pygame.font.Font,
        audio=None,
        bg: pygame.Surface | None = None,
        rounds: int = 16,
        stage1_minutes: int = 3,
        stage2_minutes: int = 7,
        stage3_minutes: int = 5,
        profile=None,
        control_mode: str = "bci",
        skip_connection: bool = False,
    ) -> None:
        self.screen = screen
        self.font = font
        self.title_font = title_font
        self._audio = audio
        self._bg = bg
        self._rounds = rounds
        self._profile = profile
        self._big_font = load_chinese_font(72)
        self.clock = pygame.time.Clock()
        self.running = True
        self.result = None
        self._external_control_mode = control_mode
        self._skip_connection = skip_connection

        self._stage_durations = [stage1_minutes, stage2_minutes, stage3_minutes]
        self._stage_names = ["原萃阶段", "特调阶段", "忆调阶段"]
        self._current_stage_index = 0

        self._phase: str = "intro" if skip_connection else "idle"
        self._phase_timer: float = 0.0

        self._intro_texts = [
            ["决定您在下一阶段的", "基线值和游戏难度"],
            ["根据个性化调节了", "本阶段的游戏难度"],
        ]
        self._attn_samples: list[float] = []
        self._baseline: float = 40.0
        self._clearing_timer: float = 0.0

        self._panel_w, self._panel_h = 820, 560
        self._panel_x = (SCREEN_WIDTH - self._panel_w) // 2
        self._panel_y = (SCREEN_HEIGHT - self._panel_h) // 2

        self._panel_img = None
        if os.path.exists(SETTINGS_PANEL_IMG):
            try:
                img = pygame.image.load(SETTINGS_PANEL_IMG).convert_alpha()
                self._panel_img = pygame.transform.smoothscale(img, (self._panel_w, self._panel_h))
            except Exception:
                pass

        cx = SCREEN_WIDTH // 2
        btn_y = SCREEN_HEIGHT // 2 + 220

        self.back_btn = _PlainButton(
            "返回",
            cx - 150,
            btn_y,
            title_font,
            (80, 80, 80),
            (100, 100, 100),
            (60, 60, 60),
            padding=(30, 15),
            radius=15,
            width=120,
        )
        self.training_btn = _PlainButton(
            "开始训练",
            cx + 150,
            btn_y,
            title_font,
            (60, 160, 100),
            (80, 200, 130),
            (40, 120, 70),
            padding=(30, 15),
            radius=15,
            width=160,
        )

        self._conn_dialog_active = False
        self._conn_dialog_state = "connecting"
        self._conn_dialog_timer = 0.0
        self._conn_bci_reader = None
        self._conn_last_connect_attempt = 0.0
        self._rect_direct = pygame.Rect(0, 0, 0, 0)
        self._rect_cancel = pygame.Rect(0, 0, 0, 0)

        self._session = None

        if self._skip_connection:
            self._init_game()

    def _init_connection(self) -> None:
        self._conn_dialog_active = True
        self._conn_dialog_state = "connecting"
        self._conn_dialog_timer = 0.0
        self._conn_last_connect_attempt = 0.0
        try:
            self._conn_bci_reader = BCIDataReader()
            self._conn_bci_reader.connect(connect_timeout=0.1)
        except Exception:
            self._conn_bci_reader = None

    def _try_bci_read(self) -> bool:
        if self._conn_bci_reader is None:
            return False
        try:
            result = self._conn_bci_reader.read_with_timeout()
            if result and result[0] is not None:
                return True
        except Exception:
            pass
        return False

    def _init_game(self) -> None:
        if self._session is not None:
            return

        from game.session import GameSession

        stage_idx = self._current_stage_index
        duration = self._stage_durations[stage_idx] * 60

        self._session = GameSession(
            self.screen,
            self.clock,
            game_mode="infinite",
            profile=self._profile,
            control_mode=self._external_control_mode,
            audio=self._audio,
            training_duration=duration,
        )

    def _start_training(self) -> None:
        self._init_connection()

    def _enter_intro(self) -> None:
        bci_ok = False
        if self._conn_bci_reader and self._conn_bci_reader.connected:
            bci_ok = True
            self._session._bci_available = True
            self._session._bci_reader = self._conn_bci_reader
            self._session.use_yaw_control = True
            self._session.cup.yaw_control = True
            self._conn_bci_reader = None
        self._phase = "intro"
        self._phase_timer = 0.0

    def _enter_game(self) -> None:
        self._init_game()
        self._session.start_training()
        self._phase = "game"

    def _get_remaining_seconds(self) -> float:
        if self._session is None:
            return 0.0
        return self._session.training_remaining()

    def run(self) -> str | None:
        while self.running:
            dt_sec = self.clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    self.result = "quit"
                elif self._conn_dialog_active:
                    self._handle_connection_event(event)
                elif self._phase in ("game", "clearing"):
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                        self.running = False
                        self.result = "back"
                elif self._phase == "idle":
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                        self.running = False
                        self.result = "back"
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        if self.back_btn.handle_event(event):
                            self.running = False
                            self.result = "back"
                        if self.training_btn.handle_event(event):
                            self._start_training()
                elif self._phase == "intro":
                    pass

            self._update(dt_sec)
            self._draw()
            pygame.display.flip()

        self._cleanup()
        return self.result

    def _cleanup(self) -> None:
        if self._session is not None:
            self._session._end_game()
            self._session = None
        if self._conn_bci_reader:
            try:
                self._conn_bci_reader.disconnect()
            except Exception:
                pass

    def _handle_connection_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            can_click = self._conn_dialog_state not in ("connecting", "reconnecting")
            if self._rect_direct.collidepoint(event.pos):
                self._conn_dialog_active = False
                self._enter_intro()
            elif self._rect_cancel.collidepoint(event.pos):
                self._conn_dialog_active = False
                self._conn_bci_reader = None
                self._conn_dialog_state = "connecting"
                self._conn_dialog_timer = 0.0
            elif can_click and hasattr(self, "_rect_retry"):
                if self._rect_retry.collidepoint(event.pos):
                    self._conn_dialog_state = "reconnecting"
                    self._conn_dialog_timer = 0.0
                    self._conn_last_connect_attempt = 0.0
                    if self._conn_bci_reader:
                        self._conn_bci_reader.connect(connect_timeout=0.1)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._conn_dialog_active = False
            self._conn_bci_reader = None
            self._conn_dialog_state = "connecting"
            self._conn_dialog_timer = 0.0

    def _update(self, dt_sec: float) -> None:
        if self._conn_dialog_active:
            self._update_connecting(dt_sec)
        elif self._phase == "intro":
            self._phase_timer += dt_sec
            if self._phase_timer >= 2.0:
                self._enter_game()
        elif self._phase == "game":
            self._update_game(dt_sec)
        elif self._phase == "clearing":
            self._clearing_timer += dt_sec
            if self._clearing_timer >= 2.0:
                self._start_next_stage()
        elif self._phase == "idle":
            self.back_btn.update(dt_sec)
            self.training_btn.update(dt_sec)

    def _update_connecting(self, dt_sec: float) -> None:
        self._conn_dialog_timer += dt_sec
        if self._conn_dialog_state in ("connecting", "reconnecting"):
            if self._conn_bci_reader and self._conn_bci_reader.connected:
                if self._try_bci_read():
                    self._conn_dialog_active = False
                    self._enter_intro()
                    return
            elif self._conn_bci_reader and self._conn_dialog_timer - self._conn_last_connect_attempt >= 1.0:
                self._conn_bci_reader.connect(connect_timeout=0.1)
                self._conn_last_connect_attempt = self._conn_dialog_timer
            elif self._conn_dialog_timer >= 5.0:
                self._conn_dialog_state = "failed"

    def _update_game(self, dt_sec: float) -> None:
        session = self._session
        if session is None:
            return

        keys = pygame.key.get_pressed()

        session._update_bci_data()
        session._update_cup(keys, dt_sec)
        session._update_pause_state(dt_sec)
        session._check_artifact(dt_sec)
        session._update_artifact_freeze(dt_sec)

        if not session._game_frozen:
            session._update_attention_variance()
            session._update_formal_speed()
            session._check_secret_recipe(dt_sec)
            session._check_cup_end()

        if not session.running:
            self._finish_stage()
            return

        if not session._game_frozen:
            session._update_game_objects(dt_sec)
            session._handle_collisions()

        if session.attention is not None:
            self._attn_samples.append(session.attention)

        if self._get_remaining_seconds() <= 0:
            session.running = False
            self._finish_stage()

    def _finish_stage(self) -> None:
        session = self._session
        if session is None:
            return

        if self._attn_samples:
            self._baseline = sum(self._attn_samples) / len(self._attn_samples)

        session.ingredients.empty()
        session.catch_effects.empty()
        session.miss_effects.empty()
        session.particles.empty()

        self._clearing_timer = 0.0
        self._phase = "clearing"

    def _start_next_stage(self) -> None:
        old_session = self._session
        if old_session is not None:
            old_session._end_game()

        self._current_stage_index += 1
        self._attn_samples = []
        self._session = None

        from game.session import GameSession

        stage_idx = self._current_stage_index
        duration = self._stage_durations[stage_idx] * 60

        norm_lower = max(self._baseline - 10, 0.0)
        norm_upper = 70.0
        if old_session is not None and old_session.focus_samples:
            n_last = min(len(old_session.focus_samples), 30 * 60)
            last_30_focus = old_session.focus_samples[-n_last:]
            if last_30_focus:
                norm_upper = max(last_30_focus)

        self._session = GameSession(
            self.screen,
            self.clock,
            game_mode="regular",
            profile=self._profile,
            control_mode=self._external_control_mode,
            audio=self._audio,
            training_duration=duration,
            fixed_baseline=self._baseline,
            norm_lower=norm_lower,
            norm_upper=norm_upper,
        )
        self._session.bci_mode = True

        self._phase = "intro"
        self._phase_timer = 0.0

    def _draw(self) -> None:
        if self._conn_dialog_active:
            self._draw_idle_bg()
            self._draw_connection_dialog()
        elif self._phase == "intro":
            if self._skip_connection:
                self._draw_game_bg()
            else:
                self._draw_idle_bg()
            self._draw_intro()
        elif self._phase in ("game", "done", "clearing"):
            self._draw_game()
        else:
            self._draw_idle_bg()

    def _draw_idle_bg(self) -> None:
        if self._bg:
            self.screen.blit(self._bg, (0, 0))
        else:
            self.screen.fill((30, 30, 40))

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        panel_surf = pygame.Surface((self._panel_w, self._panel_h), pygame.SRCALPHA)
        if self._panel_img:
            panel_surf.blit(self._panel_img, (0, 0))
        else:
            pygame.draw.rect(panel_surf, (30, 28, 20, 230), (0, 0, self._panel_w, self._panel_h), border_radius=16)
            pygame.draw.rect(panel_surf, (200, 160, 100, 180), (0, 0, self._panel_w, self._panel_h), 3, border_radius=16)
        self.screen.blit(panel_surf, (self._panel_x, self._panel_y))

        progress_text = f"轮次 0/{self._rounds}"
        progress_surf = self._big_font.render(progress_text, True, (30, 30, 30))
        tx = SCREEN_WIDTH // 2 - progress_surf.get_width() // 2
        ty = SCREEN_HEIGHT // 2 - progress_surf.get_height() // 2 - 30
        self.screen.blit(progress_surf, (tx, ty))

        self.back_btn.draw(self.screen)
        self.training_btn.draw(self.screen)

    def _draw_intro(self) -> None:
        dark = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dark.fill((0, 0, 0, 160))
        self.screen.blit(dark, (0, 0))

        stage_idx = self._current_stage_index
        title_text = self._big_font.render(self._stage_names[stage_idx], True, (255, 255, 255))
        tx = SCREEN_WIDTH // 2 - title_text.get_width() // 2
        ty = SCREEN_HEIGHT // 2 - 80
        self.screen.blit(title_text, (tx, ty))

        lines = self._intro_texts[min(stage_idx, len(self._intro_texts) - 1)]
        for i, line in enumerate(lines):
            line_surf = self.title_font.render(line, True, (220, 220, 220))
            lx = SCREEN_WIDTH // 2 - line_surf.get_width() // 2
            ly = ty + title_text.get_height() + 20 + i * 45
            self.screen.blit(line_surf, (lx, ly))

    def _draw_game_bg(self) -> None:
        if self._session is None:
            return
        s = self._session
        if s.has_background and s.background:
            self.screen.blit(s.background, (0, 0))
            from config import BACKGROUND_OVERLAY_ALPHA, OVERLAY_CLEAR_REGIONS
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 10, BACKGROUND_OVERLAY_ALPHA))
            for rx, ry, rw, rh in OVERLAY_CLEAR_REGIONS:
                overlay.fill((0, 0, 0, 0), pygame.Rect(rx, ry, rw, rh))
            self.screen.blit(overlay, (0, 0))
        else:
            self.screen.fill((255, 255, 255))
        s.all_sprites.draw(self.screen)
        s.particles.draw(self.screen)
        s.ingredients.draw(self.screen)
        s.catch_effects.draw(self.screen)
        s.miss_effects.draw(self.screen)
        s._render_formal_hud()

    def _draw_game(self) -> None:
        if self._session is not None:
            s = self._session
            if s.has_background and s.background:
                self.screen.blit(s.background, (0, 0))
                from config import BACKGROUND_OVERLAY_ALPHA, OVERLAY_CLEAR_REGIONS
                overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 10, BACKGROUND_OVERLAY_ALPHA))
                for rx, ry, rw, rh in OVERLAY_CLEAR_REGIONS:
                    overlay.fill((0, 0, 0, 0), pygame.Rect(rx, ry, rw, rh))
                self.screen.blit(overlay, (0, 0))
            else:
                self.screen.fill((255, 255, 255))

            if self._phase == "clearing":
                s.all_sprites.draw(self.screen)
            else:
                s.all_sprites.draw(self.screen)
                s.particles.draw(self.screen)
                s.ingredients.draw(self.screen)
                s.catch_effects.draw(self.screen)
                s.miss_effects.draw(self.screen)

            s._render_formal_hud()
            if s._secret_popup_timer > 0:
                s._draw_secret_popup()

        remaining = int(self._get_remaining_seconds())
        mm = remaining // 60
        ss = remaining % 60
        time_str = f"{mm:02d}:{ss:02d}"
        stage_idx = self._current_stage_index
        label = self._stage_names[stage_idx]

        hud_font = load_chinese_font(28)
        stage_surf = hud_font.render(label, True, (40, 40, 40))
        time_surf = hud_font.render(time_str, True, (40, 40, 40))
        self.screen.blit(stage_surf, (SCREEN_WIDTH - stage_surf.get_width() - 12, SCREEN_HEIGHT - 62))
        self.screen.blit(time_surf, (SCREEN_WIDTH - time_surf.get_width() - 12, SCREEN_HEIGHT - 34))

        if self._phase == "done":
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            self.screen.blit(overlay, (0, 0))
            done_text = self.title_font.render("阶段完成", True, (255, 255, 255))
            tx = SCREEN_WIDTH // 2 - done_text.get_width() // 2
            ty = SCREEN_HEIGHT // 2 - done_text.get_height() // 2
            self.screen.blit(done_text, (tx, ty))

    def _draw_connection_dialog(self) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        self.screen.blit(overlay, (0, 0))

        box_w = 480
        box_h = 260
        bx = SCREEN_WIDTH // 2 - box_w // 2
        by = SCREEN_HEIGHT // 2 - box_h // 2

        box_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        pygame.draw.rect(box_surf, (40, 30, 25, 230), (0, 0, box_w, box_h), border_radius=16)
        pygame.draw.rect(box_surf, (255, 200, 100, 180), (0, 0, box_w, box_h), 3, border_radius=16)

        title = self.font.render("正在连接中......", True, (255, 255, 255))
        box_surf.blit(title, ((box_w - title.get_width()) // 2, 30))

        remaining = max(0, 5.0 - self._conn_dialog_timer)
        timer_text = self.font.render(f"{remaining:.0f}s", True, (180, 180, 180))
        box_surf.blit(timer_text, ((box_w - timer_text.get_width()) // 2, 70))

        btn_w = 150
        btn_h = 44
        btn_y_offset = 115

        is_disabled = self._conn_dialog_state in ("connecting", "reconnecting")
        retry_color = (80, 80, 80) if is_disabled else (200, 150, 50)
        retry_text_color = (120, 120, 120) if is_disabled else (255, 255, 255)
        retry_btn_x = (box_w - btn_w) // 2
        retry_inner = pygame.Rect(retry_btn_x, btn_y_offset, btn_w, btn_h)
        pygame.draw.rect(box_surf, retry_color, retry_inner, border_radius=8)
        pygame.draw.rect(box_surf, (255, 255, 255, 80), retry_inner, 2, border_radius=8)
        retry_text = self.font.render("重新连接", True, retry_text_color)
        box_surf.blit(
            retry_text,
            (
                retry_btn_x + (btn_w - retry_text.get_width()) // 2,
                btn_y_offset + (btn_h - retry_text.get_height()) // 2,
            ),
        )

        direct_btn_x = box_w // 2 - btn_w - 20
        cancel_btn_x = box_w // 2 + 20
        bottom_btn_y = 175

        pygame.draw.rect(box_surf, (60, 160, 100), (direct_btn_x, bottom_btn_y, btn_w, btn_h), border_radius=8)
        pygame.draw.rect(box_surf, (255, 255, 255, 80), (direct_btn_x, bottom_btn_y, btn_w, btn_h), 2, border_radius=8)
        direct_text = self.font.render("直接进入", True, (255, 255, 255))
        box_surf.blit(
            direct_text,
            (
                direct_btn_x + (btn_w - direct_text.get_width()) // 2,
                bottom_btn_y + (btn_h - direct_text.get_height()) // 2,
            ),
        )

        pygame.draw.rect(box_surf, (200, 60, 60), (cancel_btn_x, bottom_btn_y, btn_w, btn_h), border_radius=8)
        pygame.draw.rect(box_surf, (255, 255, 255, 80), (cancel_btn_x, bottom_btn_y, btn_w, btn_h), 2, border_radius=8)
        cancel_text = self.font.render("取消", True, (255, 255, 255))
        box_surf.blit(
            cancel_text,
            (
                cancel_btn_x + (btn_w - cancel_text.get_width()) // 2,
                bottom_btn_y + (btn_h - cancel_text.get_height()) // 2,
            ),
        )

        self.screen.blit(box_surf, (bx, by))

        self._rect_direct = pygame.Rect(bx + direct_btn_x, by + bottom_btn_y, btn_w, btn_h)
        self._rect_cancel = pygame.Rect(bx + cancel_btn_x, by + bottom_btn_y, btn_w, btn_h)
        self._rect_retry = pygame.Rect(bx + retry_btn_x, by + btn_y_offset, btn_w, btn_h)
