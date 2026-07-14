"""训练执行页面"""

from __future__ import annotations

import os
import random
import time

import pygame

from bci.data_reader import BCIDataReader
from config import (
    INGREDIENT_IMGS,
    OUTLET_POSITIONS,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TRAINING_INGREDIENT_POINTS,
    TRAINING_PANEL_IMG,
)
from data.memory_recipes import MEMORY_RECIPES
from game.font_utils import load_chinese_font
from game.sprites import Ingredient
from menu.components import MenuItem


_MEMORY_LEVEL = 2
_MEMORY_SPAWN_INTERVAL = 1.0
_MEMORY_INITIAL_DELAY = 0.3
_MEMORIZE_DURATION = 2.0
_MEMORY_RESULT_DURATION = 1.0
_MEMORY_REST_DURATION = 2.0
_MEMORY_UPGRADE_THRESHOLD = 3
_MEMORY_DOWNGRADE_THRESHOLD = 2


def _random_distractor(exclude: set[str]) -> str:
    pool = [
        "珍珠", "椰果", "牛奶", "红茶", "绿茶", "芋圆", "脆啵啵",
        "芒果", "椰奶", "草莓", "芋泥", "燕麦奶", "咖啡",
        "米酿", "咸芝士奶盖", "茉莉花茶",
    ]
    available = [t for t in pool if t not in exclude]
    return random.choice(available) if available else random.choice(pool)


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
        completed_rounds: int = 0,
    ) -> None:
        self.screen = screen
        self.font = font
        self.title_font = title_font
        self._audio = audio
        self._bg = bg
        self._rounds = rounds
        self._completed_rounds = completed_rounds
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

        self._phase: str = "splash" if skip_connection else "idle"
        self._phase_timer: float = 0.0

        self._intro_texts = [
            ["决定您在下一阶段的", "基线值和游戏难度"],
            ["根据个性化调节了", "本阶段的游戏难度"],
            ["记住屏幕的小料并顺序接住", "注意避开干扰食材"],
        ]
        self._attn_samples: list[float] = []
        self._baseline: float = 40.0
        self._clearing_timer: float = 0.0

        self._memory_phase = ""
        self._memory_timer = 0.0
        self._memory_level = _MEMORY_LEVEL
        self._consecutive_success = 0
        self._consecutive_failures = 0
        self._recipe_ingredients: list[str] = []
        self._recipe_name = ""
        self._target_index = 0
        self._caught_wrong = False
        self._missed_recipe = False
        self._spawn_list: list[str] = []
        self._spawn_index = 0
        self._all_spawned = False
        self._spawn_timer = _MEMORY_INITIAL_DELAY
        self._round_successes = 0
        self._round_failures = 0
        self._memory_result_text = ""
        self._memory_ingredients = pygame.sprite.Group()
        self._memory_particles = pygame.sprite.Group()

        self._accumulated_cups = 0
        self._accumulated_money = 0
        self._accumulated_money_before_stage = 0
        self._accumulated_secret_count = 0
        self._accumulated_failed_cups = 0
        self._all_focus_samples: list[float] = []
        self._stage_focus_samples: list[list[float]] = []
        self._training_start_time = 0.0
        self._current_norm_lower = 0.0
        self._current_norm_upper = 0.0

        self._panel_w, self._panel_h = 820, 560
        self._panel_x = (SCREEN_WIDTH - self._panel_w) // 2
        self._panel_y = (SCREEN_HEIGHT - self._panel_h) // 2

        self._panel_img = None
        if os.path.exists(TRAINING_PANEL_IMG):
            try:
                img = pygame.image.load(TRAINING_PANEL_IMG).convert_alpha()
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

        self._esc_dialog_active: bool = False
        self._esc_dialog_selected: int = 0
        self._pending_settings: bool = False
        self._skip_frame: bool = False

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

        if stage_idx == 2:
            game_mode = "regular"
        else:
            game_mode = "infinite"

        self._session = GameSession(
            self.screen,
            self.clock,
            game_mode=game_mode,
            profile=self._profile,
            control_mode=self._external_control_mode,
            audio=self._audio,
            training_duration=duration,
            ingredient_points=TRAINING_INGREDIENT_POINTS,
            secret_threshold=None if stage_idx == 2 else 50,
            secret_sustain=None if stage_idx == 2 else 5,
            secret_disabled=(stage_idx == 2),
        )
        self._session.cup_manager.cup_number = self._accumulated_cups
        if stage_idx != 2:
            self._session.has_required = True
            self._session.cup_manager.has_required = True

        if stage_idx == 2:
            self._pick_memory_recipe()
            self._enter_memory_phase("memorize")

    def _pick_memory_recipe(self) -> None:
        recipes = MEMORY_RECIPES.get(self._memory_level, MEMORY_RECIPES[_MEMORY_LEVEL])
        recipe = random.choice(recipes)
        self._recipe_name = recipe["name"]
        self._recipe_ingredients = list(recipe["ingredients"])
        self._target_index = 0
        self._caught_wrong = False
        self._missed_recipe = False
        self._memory_result_text = ""

    def _build_spawn_list(self) -> None:
        n = len(self._recipe_ingredients)
        recipe_pattern = self._recipe_ingredients * 2
        distractor_pool = set()
        for _ in range(2 * n):
            distractor_pool.add(_random_distractor(set(self._recipe_ingredients)))
        distractors = list(distractor_pool)
        while len(distractors) < 2 * n:
            distractors.append(_random_distractor(set(self._recipe_ingredients)))
        random.shuffle(distractors)
        distractors = distractors[:2 * n]

        total = 4 * n
        slots = list(range(total))
        random.shuffle(slots)
        recipe_slots = sorted(slots[:2 * n])
        dist_slots = list(slots[2 * n:])

        self._spawn_list = [""] * total
        for i, pos in enumerate(recipe_slots):
            self._spawn_list[pos] = recipe_pattern[i]
        for pos in dist_slots:
            self._spawn_list[pos] = distractors.pop()

        self._spawn_index = 0
        self._all_spawned = False
        self._spawn_timer = _MEMORY_INITIAL_DELAY

    def _enter_memory_phase(self, phase: str) -> None:
        self._memory_phase = phase
        self._memory_timer = 0.0
        if phase == "memorize":
            self._pick_memory_recipe()
        elif phase == "playing":
            self._build_spawn_list()
            self._memory_ingredients.empty()
            self._memory_particles.empty()

    def _start_training(self) -> None:
        self._init_connection()

    def _start_splash(self) -> None:
        if self._audio:
            self._audio.stop_bgm()
            self._audio.play_bgm("晨光木盒.mp3", volume=0.5)
        from menu.splash import SplashScreen
        SplashScreen(self.screen, load_chinese_font(110)).run()

    def _enter_intro(self) -> None:
        self._init_game()
        if self._conn_bci_reader and self._conn_bci_reader.connected:
            self._session.bci_available = True
            self._session.bci_reader = self._conn_bci_reader
            self._session.use_yaw_control = True
            self._session.cup.yaw_control = True
            self._conn_bci_reader = None
        self._phase = "splash"
        self._phase_timer = 0.0

    def _enter_game(self) -> None:
        self._init_game()
        self._accumulated_money_before_stage = self._accumulated_money
        if self._current_stage_index == 0 and self._training_start_time == 0.0:
            self._training_start_time = time.time()
        if self._current_stage_index == 2:
            self._pick_memory_recipe()
            self._enter_memory_phase("memorize")
        self._session.score_manager.total_money = self._accumulated_money
        self._session.score_manager.cup_count = self._accumulated_cups
        self._session.cup_manager.cup_number = self._accumulated_cups
        if self._current_stage_index != 2:
            self._session.ingredient_manager.set_pixel_spacing(250)
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
                elif self._phase in ("game", "clearing", "intro", "done"):
                    if self._esc_dialog_active:
                        if event.type == pygame.KEYDOWN:
                            if event.key == pygame.K_ESCAPE:
                                self._esc_dialog_active = False
                            elif event.key in (pygame.K_LEFT, pygame.K_UP):
                                self._esc_dialog_selected = (self._esc_dialog_selected - 1) % 3
                            elif event.key in (pygame.K_RIGHT, pygame.K_DOWN, pygame.K_TAB):
                                self._esc_dialog_selected = (self._esc_dialog_selected + 1) % 3
                            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                                self._commit_esc_dialog()
                        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                            self._handle_esc_dialog_click(event.pos)
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            self._show_esc_dialog()
                        elif event.key == pygame.K_o:
                            if self._phase == "intro":
                                self._enter_game()
                            else:
                                self._finish_stage()
                        elif event.key == pygame.K_SPACE:
                            if self._session is not None:
                                yaw = not self._session.use_yaw_control
                                self._session.use_yaw_control = yaw
                                self._session.cup.yaw_control = yaw
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
        if self._audio:
            self._audio.stop_bgm()
            self._audio.play_bgm("玻璃糖果园.mp3", volume=0.5)
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
        if self._esc_dialog_active:
            if getattr(self, "_skip_frame", False):
                self._skip_frame = False
            return
        if self._pending_settings:
            self._pending_settings = False
            from menu.screens.game_settings import GameSettingsScreen
            settings_font = load_chinese_font(32)
            settings_title = load_chinese_font(60)
            bg_snapshot = self.screen.copy()
            settings = GameSettingsScreen(self.screen, settings_font, settings_title, audio=self._audio, bg=bg_snapshot)
            settings.run()
            return
        if self._conn_dialog_active:
            self._update_connecting(dt_sec)
        elif self._phase == "splash":
            self._start_splash()
            self._phase = "intro"
            self._phase_timer = 0.0
        elif self._phase == "intro":
            self._phase_timer += dt_sec
            if self._session is not None:
                keys = pygame.key.get_pressed()
                self._session._update_cup(keys, dt_sec)
            if self._phase_timer >= 3.0:
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

    def _update_memory_game(self, dt_sec: float) -> None:
        session = self._session
        if session is None:
            return

        keys = pygame.key.get_pressed()
        session._update_bci_data()
        session._update_cup(keys, dt_sec)
        session._update_formal_speed()

        if self._memory_phase == "memorize":
            self._memory_timer += dt_sec
            if self._memory_timer >= _MEMORIZE_DURATION:
                self._enter_memory_phase("playing")
        elif self._memory_phase == "playing":
            self._update_memory_playing(dt_sec)
        elif self._memory_phase == "result":
            self._memory_timer += dt_sec
            if self._memory_timer >= _MEMORY_RESULT_DURATION:
                self._enter_memory_phase("rest")
        elif self._memory_phase == "rest":
            self._memory_timer += dt_sec
            if self._memory_timer >= _MEMORY_REST_DURATION:
                self._enter_memory_phase("memorize")

        if self._get_remaining_seconds() <= 0:
            session.running = False
            self._finish_stage()

    def _update_memory_playing(self, dt_sec: float) -> None:
        session = self._session
        memory_speed = session.ingredient_manager._current_speed if session else 3.0
        if memory_speed <= 0:
            memory_speed = 3.0

        if not self._all_spawned:
            can_spawn = True
            if len(self._memory_ingredients) > 0:
                nearest = min(self._memory_ingredients, key=lambda i: i.rect.y - i._spawn_y)
                if (nearest.rect.y - nearest._spawn_y) < 250:
                    can_spawn = False
            if can_spawn:
                self._spawn_timer -= dt_sec
                if self._spawn_timer <= 0 and self._spawn_index < len(self._spawn_list):
                    ing_type = self._spawn_list[self._spawn_index]
                    ing = Ingredient(ing_type, speed=memory_speed)
                    self._memory_ingredients.add(ing)
                    self._spawn_index += 1
                    self._spawn_timer = _MEMORY_INITIAL_DELAY
            if self._spawn_index >= len(self._spawn_list):
                self._all_spawned = True

        for ing in self._memory_ingredients:
            ing.speed = memory_speed

        self._memory_ingredients.update()
        self._memory_particles.update(dt_sec)
        self._check_memory_catches()

        for ing in list(self._memory_ingredients):
            if ing.rect.top > SCREEN_HEIGHT:
                if ing.type in self._recipe_ingredients:
                    self._missed_recipe = True
                ing.kill()

        if self._all_spawned and len(self._memory_ingredients) == 0:
            self._judge_round()
            self._enter_memory_phase("result")

    def _check_memory_catches(self) -> None:
        session = self._session
        if session is None:
            return
        hits = pygame.sprite.spritecollide(session.cup, self._memory_ingredients, False)
        for ing in hits:
            if self._target_index < len(self._recipe_ingredients):
                expected = self._recipe_ingredients[self._target_index]
            else:
                expected = None

            if expected is not None and ing.type == expected:
                self._target_index += 1
                ing.kill()
                for _ in range(8):
                    from game.sprites import Particle
                    p = Particle(int(ing.rect.centerx), int(ing.rect.centery), (255, 200, 50))
                    self._memory_particles.add(p)
            else:
                self._caught_wrong = True
                ing.kill()
                for _ in range(4):
                    from game.sprites import Particle
                    p = Particle(int(ing.rect.centerx), int(ing.rect.centery), (255, 80, 80))
                    p.vx *= 0.4
                    p.vy *= 0.4
                    self._memory_particles.add(p)

    def _judge_round(self) -> None:
        caught_all = self._target_index >= len(self._recipe_ingredients)
        if caught_all and not self._caught_wrong and not self._missed_recipe:
            self._memory_result_text = "记忆正确"
            self._consecutive_success += 1
            self._consecutive_failures = 0
            self._round_successes += 1
            if self._session is not None:
                self._session.score_manager.add_cup_money(self._memory_level, had_secret=False)
            if self._consecutive_success >= _MEMORY_UPGRADE_THRESHOLD:
                self._memory_level = min(5, self._memory_level + 1)
                self._consecutive_success = 0
        else:
            self._memory_result_text = "记忆失败"
            self._consecutive_success = 0
            self._consecutive_failures += 1
            self._round_failures += 1
            if self._consecutive_failures >= _MEMORY_DOWNGRADE_THRESHOLD:
                self._memory_level = max(2, self._memory_level - 1)
                self._consecutive_failures = 0

    def _update_connecting(self, dt_sec: float) -> None:
        self._conn_dialog_timer += dt_sec
        if self._conn_dialog_state in ("connecting", "reconnecting"):
            if self._conn_bci_reader and self._conn_bci_reader.connected:
                if self._try_bci_read() and self._conn_dialog_timer >= 0.5:
                    self._conn_dialog_active = False
                    self._enter_intro()
                    return
            elif self._conn_bci_reader and self._conn_dialog_timer - self._conn_last_connect_attempt >= 1.0:
                self._conn_bci_reader.connect(connect_timeout=0.1)
                self._conn_last_connect_attempt = self._conn_dialog_timer
            elif self._conn_dialog_timer >= 5.0:
                self._conn_dialog_state = "failed"

    def _update_game(self, dt_sec: float) -> None:
        if self._current_stage_index == 2:
            self._update_memory_game(dt_sec)
            return

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
        if session is None and self._phase != "done":
            return

        if self._attn_samples:
            self._baseline = sum(self._attn_samples) / len(self._attn_samples)

        if session is not None and session.training_remaining() <= 0:
            session.running = False

        if self._current_stage_index >= len(self._stage_durations) - 1:
            if session is not None:
                sm = session.score_manager
                cm = session.cup_manager
                if self._current_stage_index == 2:
                    self._accumulated_cups += self._round_successes
                else:
                    self._accumulated_cups += sum(1 for m in cm.cup_money_history if m > 0)
                self._accumulated_money += sm.total_money - self._accumulated_money_before_stage
                self._accumulated_secret_count += sm.secret_recipe_count
                self._accumulated_failed_cups += sum(1 for m in cm.cup_money_history if m == 0)
                if session.focus_samples:
                    self._all_focus_samples.extend(session.focus_samples)
                    self._stage_focus_samples.append(list(session.focus_samples))
                self._show_training_summary()
            self.running = False
            self._phase = "done"
            return

        self._start_next_stage()

    def _show_training_summary(self) -> None:
        from menu.training_summary import TrainingSummaryScreen

        if self._audio:
            self._audio.stop_bgm()

        avg_focus = sum(self._all_focus_samples) / len(self._all_focus_samples) if self._all_focus_samples else 0.0
        stage_avgs = []
        for samples in self._stage_focus_samples:
            stage_avgs.append(sum(samples) / len(samples) if samples else 0.0)
        while len(stage_avgs) < 3:
            stage_avgs.append(0.0)

        duration = time.time() - self._training_start_time if self._training_start_time > 0 else sum(self._stage_durations) * 60.0

        bg_snapshot = self.screen.copy()
        summary = TrainingSummaryScreen(
            self.screen,
            total_money=self._accumulated_money,
            total_cups=self._accumulated_cups,
            secret_count=self._accumulated_secret_count,
            failed_cup_count=self._accumulated_failed_cups,
            memory_successes=self._round_successes,
            memory_failures=self._round_failures,
            avg_focus=avg_focus,
            stage1_avg=stage_avgs[0],
            stage2_avg=stage_avgs[1],
            stage3_avg=stage_avgs[2],
            all_focus_samples=self._all_focus_samples,
            stage1_focus=self._stage_focus_samples[0] if len(self._stage_focus_samples) > 0 else [],
            stage2_focus=self._stage_focus_samples[1] if len(self._stage_focus_samples) > 1 else [],
            stage3_focus=self._stage_focus_samples[2] if len(self._stage_focus_samples) > 2 else [],
            player_level=self._profile.level if self._profile else 1,
            cumulative_revenue=self._profile.cumulative_revenue if self._profile else 0,
            baseline=self._baseline,
            norm_lower=self._current_norm_lower,
            norm_upper=self._current_norm_upper,
            duration=duration,
            stage1_min=self._stage_durations[0],
            stage2_min=self._stage_durations[1],
            stage3_min=self._stage_durations[2],
            bg=bg_snapshot,
        )
        result = summary.run()
        if result == "save" and self._profile:
            self._profile.add_training_result(
                total_money=self._accumulated_money,
                total_cups=self._accumulated_cups,
                secret_count=self._accumulated_secret_count,
                failed_cup_count=self._accumulated_failed_cups,
                memory_successes=self._round_successes,
                memory_failures=self._round_failures,
                avg_attention=avg_focus,
                stage1_avg=stage_avgs[0],
                stage2_avg=stage_avgs[1],
                stage3_avg=stage_avgs[2],
                all_focus_samples=self._all_focus_samples,
                stage1_focus=self._stage_focus_samples[0] if len(self._stage_focus_samples) > 0 else None,
                stage2_focus=self._stage_focus_samples[1] if len(self._stage_focus_samples) > 1 else None,
                stage3_focus=self._stage_focus_samples[2] if len(self._stage_focus_samples) > 2 else None,
                duration=duration,
                stage1_min=self._stage_durations[0],
                stage2_min=self._stage_durations[1],
                stage3_min=self._stage_durations[2],
                rounds=self._rounds,
            )
            self._profile.save()

            if duration > 15 * 60 and self._profile and self._profile._username:
                from menu.screens.training_plan import _load_plan, _save_plan
                plan = _load_plan(self._profile._username)
                completed = plan.get("completed_rounds", 0)
                plan["completed_rounds"] = min(completed + 1, plan.get("rounds", self._rounds))
                _save_plan(self._profile._username, plan)

    def _start_next_stage(self) -> None:
        old_session = self._session
        old_bci_reader = None
        old_cup_x = None

        if old_session is not None:
            if old_session.bci_available and old_session.bci_reader:
                old_bci_reader = old_session.bci_reader
                old_session.bci_reader = None
            old_cup_x = old_session.cup.rect.centerx

            sm = old_session.score_manager
            cm = old_session.cup_manager
            if self._current_stage_index == 2:
                self._accumulated_cups += self._round_successes
            else:
                self._accumulated_cups += sum(1 for m in cm.cup_money_history if m > 0)
            self._accumulated_money += sm.total_money - self._accumulated_money_before_stage
            self._accumulated_secret_count += sm.secret_recipe_count
            self._accumulated_failed_cups += sum(1 for m in cm.cup_money_history if m == 0)
            if old_session.focus_samples:
                self._all_focus_samples.extend(old_session.focus_samples)
                self._stage_focus_samples.append(list(old_session.focus_samples))
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

        self._current_norm_lower = norm_lower
        self._current_norm_upper = norm_upper

        if stage_idx == 1:
            secret_kwargs = dict(secret_threshold=self._baseline + 10, secret_sustain=8)
            require_override = True
        else:
            secret_kwargs = dict(secret_disabled=True)
            require_override = False

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
            ingredient_points=TRAINING_INGREDIENT_POINTS,
            **secret_kwargs,
        )
        self._session.bci_mode = True
        if require_override:
            self._session.has_required = True
            self._session.cup_manager.has_required = True
        self._session.score_manager.total_money = self._accumulated_money
        self._session.score_manager.cup_count = self._accumulated_cups
        self._session.cup_manager.cup_number = self._accumulated_cups

        if old_bci_reader:
            self._session.bci_reader = old_bci_reader
            self._session.bci_available = True
            self._session.use_yaw_control = True
            self._session.cup.yaw_control = True
        if old_cup_x is not None:
            self._session.cup.rect.centerx = old_cup_x

        self._phase = "intro"
        self._phase_timer = 0.0

    def _draw(self) -> None:
        if self._conn_dialog_active:
            self._draw_idle_bg()
            self._draw_connection_dialog()
        elif self._phase == "intro":
            if self._session is not None:
                self._draw_game_bg()
            else:
                self._draw_idle_bg()
            self._draw_intro()
        elif self._phase in ("game", "done", "clearing"):
            if self._current_stage_index == 2:
                self._draw_memory()
            else:
                self._draw_game()
        else:
            self._draw_idle_bg()

        if self._esc_dialog_active:
            self._draw_esc_dialog()

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

        progress_text = f"轮次 {self._completed_rounds}/{self._rounds}"
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

        if stage_idx == 1:
            y_base = ty + title_text.get_height() + 20 + len(lines) * 45 + 20
            bline = self.font.render(f"基线: {self._baseline:.0f}", True, (200, 200, 200))
            bx = SCREEN_WIDTH // 2 - bline.get_width() // 2
            self.screen.blit(bline, (bx, y_base))
            norm = self.font.render(
                f"归一化: [{self._current_norm_lower:.0f}, {self._current_norm_upper:.0f}]",
                True, (200, 200, 200))
            nx = SCREEN_WIDTH // 2 - norm.get_width() // 2
            self.screen.blit(norm, (nx, y_base + 30))

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

    def _draw_memory(self) -> None:
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
            s.all_sprites.draw(self.screen)
            s._render_formal_hud()

        if self._memory_phase == "memorize":
            self._draw_memory_memorize()
        elif self._memory_phase == "playing":
            self._memory_particles.draw(self.screen)
            self._memory_ingredients.draw(self.screen)
            self._draw_memory_hud()
        elif self._memory_phase == "result":
            self._draw_memory_result_popup()
        elif self._memory_phase == "rest":
            self._draw_memory_rest()

        remaining = int(self._get_remaining_seconds())
        mm = remaining // 60
        ss = remaining % 60
        time_str = f"{mm:02d}:{ss:02d}"
        label = self._stage_names[2]
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

    def _draw_memory_memorize(self) -> None:
        shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 180))
        self.screen.blit(shade, (0, 0))

        ing_size = 90
        gap = 15
        n = len(self._recipe_ingredients)
        total_w = n * ing_size + (n - 1) * gap
        start_x = SCREEN_WIDTH // 2 - total_w // 2
        ing_y = SCREEN_HEIGHT // 2 - 80
        for i, ing_type in enumerate(self._recipe_ingredients):
            img_path = INGREDIENT_IMGS.get(ing_type, "")
            if img_path and os.path.exists(img_path):
                img = pygame.image.load(img_path).convert_alpha()
                img = pygame.transform.scale(img, (ing_size, ing_size))
            else:
                img = pygame.Surface((ing_size, ing_size), pygame.SRCALPHA)
                pygame.draw.circle(img, (200, 200, 200), (ing_size // 2, ing_size // 2), ing_size // 2)
            self.screen.blit(img, (start_x + i * (ing_size + gap), ing_y))

        recipe_font = load_chinese_font(48)
        name_text = recipe_font.render(self._recipe_name, True, (255, 220, 100))
        nx = SCREEN_WIDTH // 2 - name_text.get_width() // 2
        ny = ing_y + ing_size + 20
        self.screen.blit(name_text, (nx, ny))

        remain = max(0, _MEMORIZE_DURATION - self._memory_timer)
        bar_w = int(300 * remain / _MEMORIZE_DURATION)
        bar_y = ny + name_text.get_height() + 20
        bar_x = SCREEN_WIDTH // 2 - 150
        pygame.draw.rect(self.screen, (60, 60, 60), (bar_x, bar_y, 300, 8), border_radius=4)
        if bar_w > 0:
            pygame.draw.rect(self.screen, (255, 180, 100), (bar_x, bar_y, bar_w, 8), border_radius=4)

    def _draw_memory_hud(self) -> None:
        n = len(self._recipe_ingredients)
        total_w = n * 12 + (n - 1) * 8
        start_x = SCREEN_WIDTH // 2 - total_w // 2
        cy = 150
        for i in range(n):
            cx = start_x + i * 20
            if i < self._target_index:
                color = (100, 255, 100)
            elif i == self._target_index:
                pulse = abs(self._memory_timer % 0.3 - 0.15)
                r = int(255 - pulse * 300)
                g = int(200 - pulse * 200)
                b = int(100 - pulse * 100)
                color = (max(200, r), max(50, g), max(50, b))
            else:
                color = (80, 80, 80)
            pygame.draw.circle(self.screen, color, (cx, cy), 6)

    def _draw_memory_result_popup(self) -> None:
        popup_w, popup_h = 500, 120
        popup_x = (SCREEN_WIDTH - popup_w) // 2
        popup_y = (SCREEN_HEIGHT - popup_h) // 2
        popup = pygame.Surface((popup_w, popup_h), pygame.SRCALPHA)
        pygame.draw.rect(popup, (30, 25, 20, 220), (0, 0, popup_w, popup_h), border_radius=12)
        pygame.draw.rect(popup, (255, 180, 100, 100), (0, 0, popup_w, popup_h), 3, border_radius=12)

        is_success = self._memory_result_text == "记忆正确"
        result_color = (100, 255, 100) if is_success else (255, 120, 100)
        result_text = self.title_font.render(self._memory_result_text, True, result_color)
        rx = (popup_w - result_text.get_width()) // 2
        ry = (popup_h - result_text.get_height()) // 2 - 10
        popup.blit(result_text, (rx, ry))
        self.screen.blit(popup, (popup_x, popup_y))

    def _draw_memory_rest(self) -> None:
        remain = max(0, _MEMORY_REST_DURATION - self._memory_timer)
        rest_text = self.font.render(f"下一杯即将开始... {remain:.0f}s", True, (200, 200, 200))
        self.screen.blit(
            rest_text,
            (SCREEN_WIDTH // 2 - rest_text.get_width() // 2, SCREEN_HEIGHT // 2 + 80),
        )

    def _show_esc_dialog(self) -> None:
        self._esc_dialog_active = True
        self._esc_dialog_selected = 0
        self._skip_frame = True

    def _commit_esc_dialog(self) -> None:
        if self._esc_dialog_selected == 0:
            self._esc_dialog_active = False
        elif self._esc_dialog_selected == 1:
            self._exit_to_summary()
        else:
            self._esc_dialog_active = False
            self._pending_settings = True

    def _handle_esc_dialog_click(self, pos: tuple[int, int]) -> None:
        if hasattr(self, "_esc_continue_rect") and self._esc_continue_rect.collidepoint(pos):
            self._esc_dialog_active = False
        elif hasattr(self, "_esc_exit_rect") and self._esc_exit_rect.collidepoint(pos):
            self._exit_to_summary()
        elif hasattr(self, "_esc_settings_rect") and self._esc_settings_rect.collidepoint(pos):
            self._esc_dialog_active = False
            self._pending_settings = True

    def _exit_to_summary(self) -> None:
        self._esc_dialog_active = False
        session = self._session
        if session is not None:
            sm = session.score_manager
            cm = session.cup_manager
            if self._current_stage_index == 2:
                self._accumulated_cups += self._round_successes
            else:
                self._accumulated_cups += sum(1 for m in cm.cup_money_history if m > 0)
            self._accumulated_money += sm.total_money - self._accumulated_money_before_stage
            self._accumulated_secret_count += sm.secret_recipe_count
            self._accumulated_failed_cups += sum(1 for m in cm.cup_money_history if m == 0)
            if session.focus_samples:
                self._all_focus_samples.extend(session.focus_samples)
                self._stage_focus_samples.append(list(session.focus_samples))
        self._show_training_summary()
        self.running = False
        self.result = "back"

    def _draw_esc_dialog(self) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        box_w, box_h = 380, 260
        box_x = (SCREEN_WIDTH - box_w) // 2
        box_y = (SCREEN_HEIGHT - box_h) // 2
        box_rect = pygame.Rect(box_x, box_y, box_w, box_h)
        pygame.draw.rect(self.screen, (30, 28, 20), box_rect, border_radius=16)
        pygame.draw.rect(self.screen, (200, 160, 100), box_rect, 3, border_radius=16)

        title = self.title_font.render("暂停", True, (255, 255, 255))
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, box_y + 25))

        btn_w, btn_h = 150, 48
        btn_y = box_y + 90
        gap = 20
        left_x = SCREEN_WIDTH // 2 - btn_w - gap // 2
        right_x = SCREEN_WIDTH // 2 + gap // 2

        continue_selected = self._esc_dialog_selected == 0
        exit_selected = self._esc_dialog_selected == 1
        settings_selected = self._esc_dialog_selected == 2

        selected_border = (255, 255, 255)
        normal_border = (100, 100, 100)

        self._esc_continue_rect = pygame.Rect(left_x, btn_y, btn_w, btn_h)
        continue_border = selected_border if continue_selected else normal_border
        pygame.draw.rect(self.screen, (80, 180, 80), self._esc_continue_rect, border_radius=10)
        pygame.draw.rect(self.screen, continue_border, self._esc_continue_rect, 3, border_radius=10)
        continue_text = self.font.render("继续训练", True, (255, 255, 255))
        self.screen.blit(
            continue_text,
            (
                self._esc_continue_rect.centerx - continue_text.get_width() // 2,
                self._esc_continue_rect.centery - continue_text.get_height() // 2,
            ),
        )

        self._esc_exit_rect = pygame.Rect(right_x, btn_y, btn_w, btn_h)
        exit_border = selected_border if exit_selected else normal_border
        pygame.draw.rect(self.screen, (200, 60, 60), self._esc_exit_rect, border_radius=10)
        pygame.draw.rect(self.screen, exit_border, self._esc_exit_rect, 3, border_radius=10)
        exit_text = self.font.render("退出训练", True, (255, 255, 255))
        self.screen.blit(
            exit_text,
            (
                self._esc_exit_rect.centerx - exit_text.get_width() // 2,
                self._esc_exit_rect.centery - exit_text.get_height() // 2,
            ),
        )

        settings_btn_w = 200
        settings_btn_y = btn_y + btn_h + 16
        settings_btn_x = SCREEN_WIDTH // 2 - settings_btn_w // 2
        self._esc_settings_rect = pygame.Rect(settings_btn_x, settings_btn_y, settings_btn_w, btn_h)
        settings_border = selected_border if settings_selected else normal_border
        pygame.draw.rect(self.screen, (220, 160, 60), self._esc_settings_rect, border_radius=10)
        pygame.draw.rect(self.screen, settings_border, self._esc_settings_rect, 3, border_radius=10)
        settings_text = self.font.render("游戏设置", True, (255, 255, 255))
        self.screen.blit(
            settings_text,
            (
                self._esc_settings_rect.centerx - settings_text.get_width() // 2,
                self._esc_settings_rect.centery - settings_text.get_height() // 2,
            ),
        )

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
