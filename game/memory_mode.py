"""忆调模式游戏会话 - 忆配方→按序接食材"""

from __future__ import annotations

import math
import os
import random
import time

import pygame

import config
from config import (
    BACKGROUND_IMG,
    BADGE_IMGS,
    INFO_BADGE_POS,
    INFO_BADGE_SIZE,
    INFO_BAR_HEIGHT,
    INFO_BAR_IMG,
    INFO_FONT_SIZE,
    INFO_REGIONS,
    INGREDIENT_IMGS,
    MEMORY_SESSION_DURATION,
    MEMORY_SPAWN_MULTIPLIER,
    MEMORY_SPEED_DEFAULT,
    MEMORY_SPEED_MAX,
    MEMORY_SPEED_MIN,
    OUTLET_BLOCK_RADIUS,
    OUTLET_POSITIONS,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)
from data.memory_recipes import MEMORY_RECIPES
from game.font_utils import load_chinese_font
from game.sprites import Cup, Ingredient
from menu.summary import SummaryScreen


class _MemoryParticle(pygame.sprite.Sprite):
    def __init__(self, x: float, y: float, color: tuple[int, int, int]) -> None:
        super().__init__()
        self.x = x
        self.y = y
        self.color = color
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(2, 7)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.life = 1.0
        self.decay = random.uniform(1.5, 3.0)
        self.size = random.randint(2, 6)
        self.image = pygame.Surface((self.size * 2, self.size * 2), pygame.SRCALPHA)
        pygame.draw.circle(self.image, (*color, 255), (self.size, self.size), self.size)
        self.rect = self.image.get_rect(center=(int(x), int(y)))

    def update(self, dt: float = 0.016) -> None:  # type: ignore[override]
        self.life -= self.decay * dt
        if self.life <= 0:
            self.kill()
            return
        self.x += self.vx * dt * 60
        self.y += self.vy * dt * 60
        self.rect.center = (int(self.x), int(self.y))
        self.image.set_alpha(int(self.life * 255))


class MemorySession:
    def __init__(
        self, screen: pygame.Surface, clock: pygame.time.Clock, audio=None, control_mode: str = "bci", profile=None
    ) -> None:
        self.screen = screen
        self.clock = clock
        self._audio = audio
        self._control_mode = control_mode
        self._profile = profile
        self.font = load_chinese_font(36)
        self.big_font = load_chinese_font(48)
        self.small_font = load_chinese_font(20)
        self.pause_font = load_chinese_font(48)
        self.running = True

        self._esc_dialog_active = False
        self._esc_dialog_selected = 0
        self._pending_settings = False
        self._skip_frame = False
        self._result = ""

        self._bg = self._load_bg()

        self._info_bar = None
        if os.path.exists(INFO_BAR_IMG):
            try:
                self._info_bar = pygame.image.load(INFO_BAR_IMG).convert_alpha()
                self._info_bar = pygame.transform.smoothscale(self._info_bar, (SCREEN_WIDTH, INFO_BAR_HEIGHT))
            except Exception:
                pass

        self._badge_img = None
        level = self._profile.level if self._profile else 1
        idx = max(0, min(level - 1, len(BADGE_IMGS) - 1))
        badge_path = BADGE_IMGS[idx]
        if os.path.exists(badge_path):
            try:
                self._badge_img = pygame.image.load(badge_path).convert_alpha()
                self._badge_img = pygame.transform.smoothscale(self._badge_img, INFO_BADGE_SIZE)
            except Exception:
                pass

        self.cup = Cup()
        self._all_ingredients = pygame.sprite.Group()
        self._particles = pygame.sprite.Group()

        self._phase = "rules"
        self._phase_timer = 0.0

        self._recipe = None
        self._recipe_name = ""
        self._recipe_ingredients: list[str] = []
        self._target_index = 0

        self._current_level = 2
        self._consecutive_success = 0
        self._round_failures = 0

        self._max_level = 5
        self._min_level = 2
        self._upgrade_threshold = 3
        self._downgrade_threshold = 2

        self._spawn_timer = 0.0
        self._spawn_interval = 0.8
        self._ingredient_speed = MEMORY_SPEED_DEFAULT

        self._num_lanes = 5
        self._lane_w = SCREEN_WIDTH // self._num_lanes
        self._lane_spacing = 400
        self._max_per_lane = 1

        self._rules_display_time = 3.5
        self._memorize_time = 2.0
        self._result_time = 1.5
        self._rest_time = 2.0

        self._round_result = ""

        self._total_score = 0
        self._total_rounds = 0
        self._total_success = 0

        self._catch_success_timer = 0.0

        self._spawn_multiplier = MEMORY_SPAWN_MULTIPLIER
        self._spawn_list: list[str] = []
        self._spawn_index = 0
        self._all_spawned = False

        self._session_start_time = 0.0
        self._session_duration = MEMORY_SESSION_DURATION
        self._session_ending = False
        self._first_round_started = False

        self._attention = 50
        self._focus_samples: list[float] = []

        self._bci_available = False
        self._bci_reader = None
        self._use_yaw = False
        self._yaw_data_ok = False
        self._platform_focus_x = float(SCREEN_WIDTH // 2)
        self._focus_min = 40
        self._focus_max = SCREEN_WIDTH - 40

        if self._control_mode != "bci_failed":
            from bci.data_reader import BCIDataReader

            self._bci_reader = BCIDataReader()
            self._bci_available = self._bci_reader.connect()
            if self._bci_available:
                self._use_yaw = True
                self.cup.yaw_control = True

    def _load_bg(self) -> pygame.Surface | None:
        if os.path.exists(BACKGROUND_IMG):
            img = pygame.image.load(BACKGROUND_IMG).convert()
            return pygame.transform.scale(img, (SCREEN_WIDTH, SCREEN_HEIGHT))
        return None

    def _pick_recipe(self) -> None:
        recipes = MEMORY_RECIPES.get(self._current_level, MEMORY_RECIPES[2])
        self._recipe = random.choice(recipes)
        self._recipe_name = self._recipe["name"]
        self._recipe_ingredients = list(self._recipe["ingredients"])
        self._target_index = 0
        self._round_result = ""

    def _build_spawn_list(self) -> None:
        n = len(self._recipe_ingredients)
        total = n * self._spawn_multiplier
        self._spawn_list = []
        recipe_idx = 0
        distractor_count = total - n
        recipe_every = self._spawn_multiplier
        after_last_recipe = max(0, total - (n - 1) * recipe_every - 1)
        for i in range(total):
            pos_in_block = i % recipe_every
            blocks_used = i // recipe_every
            if pos_in_block == 0 and recipe_idx < n:
                self._spawn_list.append(self._recipe_ingredients[recipe_idx])
                recipe_idx += 1
            else:
                self._spawn_list.append(self._random_distractor())

    def _enter_phase(self, phase: str) -> None:
        self._phase = phase
        self._phase_timer = 0.0
        if phase == "memorize":
            self._pick_recipe()
        elif phase == "playing":
            self._all_ingredients.empty()
            self._build_spawn_list()
            self._spawn_index = 0
            self._all_spawned = False
            self._spawn_timer = 0.3
            self._catch_success_timer = 0.0
            if not self._first_round_started:
                self._first_round_started = True
                self._session_start_time = time.time()

    def _free_outlet(self) -> int | None:
        indices = list(range(len(OUTLET_POSITIONS)))
        random.shuffle(indices)
        for idx in indices:
            ox, oy = OUTLET_POSITIONS[idx]
            blocked = False
            for ing in self._all_ingredients:
                dx = ing.rect.centerx - ox
                dy = ing.rect.centery - oy
                if dx * dx + dy * dy < OUTLET_BLOCK_RADIUS * OUTLET_BLOCK_RADIUS:
                    if ing.rect.y < self._lane_spacing:
                        blocked = True
                        break
            if not blocked:
                return idx
        return None

    def _spawn_ingredient(self, ing_type: str) -> Ingredient | None:
        idx = self._free_outlet()
        if idx is None:
            return None

        ing = Ingredient(ing_type, speed=self._ingredient_speed, outlet_index=idx)
        ing.rect.width = 80
        ing.rect.height = 80

        self._all_ingredients.add(ing)
        return ing

    def _random_distractor(self) -> str:
        used = set(self._recipe_ingredients)
        pool = [
            "珍珠",
            "椰果",
            "牛奶",
            "红茶",
            "绿茶",
            "芋圆",
            "脆啵啵",
            "芒果",
            "椰奶",
            "草莓",
            "芋泥",
            "燕麦奶",
            "咖啡",
            "特调稀奶油顶",
            "米酿",
            "咸芝士奶盖",
            "茉莉花茶",
        ]
        available = [t for t in pool if t not in used]
        return random.choice(available) if available else random.choice(pool)

    def _compute_speed(self) -> float:
        if not self._bci_available:
            return MEMORY_SPEED_DEFAULT
        attn = max(0, min(100, self._attention))
        return MEMORY_SPEED_MAX - (attn / 100.0) * (MEMORY_SPEED_MAX - MEMORY_SPEED_MIN)

    def _end_game(self) -> None:
        bg_snapshot = self.screen.copy()
        duration = time.time() - self._session_start_time
        avg_attn = 0.0
        if self._focus_samples:
            avg_attn = sum(self._focus_samples) / len(self._focus_samples)
        summary = SummaryScreen(
            self.screen,
            self._total_score,
            game_mode="memory",
            total_money=self._total_score,
            cup_count=self._total_rounds,
            success_count=self._total_success,
            player_level=self._current_level - 1,
            focus_samples=self._focus_samples,
            bg=bg_snapshot,
        )
        result = summary.run()
        if result == "save" and self._profile:
            self._profile.add_game_result(
                revenue=self._total_score,
                mode="memory",
                cups=self._total_rounds,
                secrets=self._total_success,
                avg_attention=avg_attn,
                duration=duration,
                focus_samples=self._focus_samples,
            )
            self._result = "save"

    def _check_catches(self) -> None:
        if self._target_index >= len(self._recipe_ingredients):
            return
        hits = pygame.sprite.spritecollide(self.cup, self._all_ingredients, False)
        for hit in hits:
            is_right = hit.type == self._recipe_ingredients[self._target_index]
            if is_right:
                self._target_index += 1
                self.cup.trigger_bounce()
                hit.kill()
                if self._audio:
                    self._audio.play_sfx("音效/接到食材.wav", volume=0.4)
                for _ in range(8):
                    p = _MemoryParticle(
                        hit.rect.centerx,
                        hit.rect.centery,
                        (255, 200, 50),
                    )
                    self._particles.add(p)
                if self._target_index >= len(self._recipe_ingredients):
                    self._round_result = "success"
                    self._catch_success_timer = 0.6
                    if self._audio:
                        self._audio.play_sfx("音效/接到必接食材.wav", volume=0.6)
                    return
            else:
                hit.kill()
                self._round_result = "wrong"
                if self._audio:
                    self._audio.play_sfx("音效/漏接必接食材.wav", volume=0.5)
                self._enter_phase("result")
                return

    def run(self) -> str:
        self._enter_phase("rules")
        self.screen.fill((0, 0, 0))
        self._draw()
        pygame.display.flip()
        self.clock.tick()  # 重置时钟，避免首帧 dt 过大

        while self.running:
            dt = min(self.clock.tick(60) / 1000.0, 0.05)
            self._phase_timer += dt

            if self._first_round_started and not self._session_ending:
                elapsed = time.time() - self._session_start_time
                if elapsed >= self._session_duration:
                    self._session_ending = True

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    return "quit"
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if self._esc_dialog_active:
                            self._esc_dialog_active = False
                        else:
                            self._esc_dialog_active = True
                            self._esc_dialog_selected = 0
                            self._skip_frame = True
                    elif self._esc_dialog_active:
                        if event.key in (pygame.K_LEFT, pygame.K_UP):
                            self._esc_dialog_selected = (self._esc_dialog_selected - 1) % 3
                        elif event.key in (pygame.K_RIGHT, pygame.K_DOWN, pygame.K_TAB):
                            self._esc_dialog_selected = (self._esc_dialog_selected + 1) % 3
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            self._commit_esc_dialog()
                elif event.type == pygame.MOUSEBUTTONDOWN and self._esc_dialog_active:
                    if event.button == 1:
                        self._handle_esc_dialog_click(event.pos)
                if self._esc_dialog_active:
                    continue

            if self._esc_dialog_active:
                if self._skip_frame:
                    self._skip_frame = False
                else:
                    self._draw()
                    pygame.display.flip()
                continue

            if self._pending_settings:
                self._pending_settings = False
                from menu.screens.game_settings import GameSettingsScreen

                settings_font = load_chinese_font(24)
                settings_title = load_chinese_font(40)
                bg_snapshot = self.screen.copy()
                settings = GameSettingsScreen(
                    self.screen, settings_font, settings_title, audio=self._audio, bg=bg_snapshot
                )
                settings.run()
                continue

            if self._phase == "rules":
                if self._phase_timer >= self._rules_display_time:
                    self._enter_phase("memorize")

            elif self._phase == "memorize":
                if self._phase_timer >= self._memorize_time:
                    self._enter_phase("playing")

            elif self._phase == "playing":
                if self._bci_available:
                    result = self._bci_reader.read_with_timeout()
                    if result[0] is not None:
                        self._attention = result[0]
                    if result[1] is not None:
                        self._platform_focus_x = float(result[1])
                        self._yaw_data_ok = True

                self._focus_samples.append(float(self._attention))

                self._ingredient_speed = self._compute_speed()

                keys = pygame.key.get_pressed()
                kb_pressed = keys[pygame.K_LEFT] or keys[pygame.K_RIGHT]

                if self._use_yaw and not kb_pressed and self._bci_available and self._yaw_data_ok:
                    fx = int(self._platform_focus_x)
                    self.cup.rect.centerx = max(self._focus_min, min(self._focus_max, fx))
                else:
                    self.cup.update(
                        keys={
                            pygame.K_LEFT: keys[pygame.K_LEFT],
                            pygame.K_RIGHT: keys[pygame.K_RIGHT],
                        },
                        dt=dt,
                    )

                if self._catch_success_timer <= 0 and not self._all_spawned:
                    self._spawn_timer -= dt
                    while self._spawn_timer <= 0 and self._spawn_index < len(self._spawn_list):
                        ing_type = self._spawn_list[self._spawn_index]
                        self._spawn_ingredient(ing_type)
                        self._spawn_index += 1
                        self._spawn_timer += self._spawn_interval
                    if self._spawn_index >= len(self._spawn_list):
                        self._all_spawned = True

                for ing in list(self._all_ingredients):
                    ing.speed = self._ingredient_speed
                    ing.update()
                for ing in list(self._all_ingredients):
                    if ing.rect.top > SCREEN_HEIGHT + 50:
                        ing.kill()

                self._check_catches()

                if self._catch_success_timer > 0:
                    self._catch_success_timer -= dt
                    if self._catch_success_timer <= 0:
                        self._enter_phase("result")

                if self._phase == "playing" and self._all_spawned and len(self._all_ingredients) == 0:
                    if self._round_result == "":
                        self._round_result = "missed"
                    self._enter_phase("result")

                self._particles.update(dt)

            elif self._phase == "result":
                if self._phase_timer >= self._result_time:
                    if self._round_result == "success":
                        self._total_success += 1
                        self._consecutive_success += 1
                        self._round_failures = 0
                        if self._consecutive_success >= self._upgrade_threshold:
                            self._current_level = min(
                                self._max_level,
                                self._current_level + 1,
                            )
                            self._consecutive_success = 0
                            if self._audio:
                                self._audio.play_sfx("音效/升级.wav", volume=0.7)
                    else:
                        self._consecutive_success = 0
                        self._round_failures += 1
                        if self._round_failures >= self._downgrade_threshold:
                            self._current_level = max(
                                self._min_level,
                                self._current_level - 1,
                            )
                            self._round_failures = 0
                    self._total_rounds += 1
                    self._total_score += self._current_level
                    if self._session_ending:
                        self.running = False
                    else:
                        self._enter_phase("rest")

            elif self._phase == "rest":
                if self._phase_timer >= self._rest_time:
                    if self._session_ending:
                        self.running = False
                    else:
                        self._enter_phase("memorize")

            self._draw()
            pygame.display.flip()

        if self._bci_available and self._bci_reader:
            self._bci_reader.disconnect()
        if self._session_ending and not self._result:
            self._end_game()
        return self._result if self._result else "menu"

    def _draw(self) -> None:
        self.screen.fill((0, 0, 0))
        if self._bg:
            self.screen.blit(self._bg, (0, 0))
        else:
            self.screen.fill((40, 25, 15))

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, config.BACKGROUND_OVERLAY_ALPHA))
        self.screen.blit(overlay, (0, 0))

        self._draw_info_bar()
        self._draw_hud_circles()

        if self._phase in ("rules", "memorize", "result", "rest"):
            self.cup.rect.centerx = SCREEN_WIDTH // 2
            self.cup.rect.bottom = SCREEN_HEIGHT - 10
        self.screen.blit(self.cup.image, self.cup.rect)

        for ing in self._all_ingredients:
            self.screen.blit(ing.image, ing.rect)

        for p in self._particles:
            self.screen.blit(p.image, p.rect)

        self._draw_session_timer()

        if self._phase == "playing":
            self._draw_attention_indicator()
        elif self._phase == "rules":
            self._draw_rules()
        elif self._phase == "memorize":
            self._draw_memorize()
        elif self._phase == "result":
            self._draw_result()
        elif self._phase == "rest":
            self._draw_rest()

        if self._esc_dialog_active:
            self._draw_esc_dialog()

    def _draw_info_bar(self) -> None:
        if not config.SHOW_HUD_INFO:
            return
        if self._info_bar:
            self.screen.blit(self._info_bar, (0, 0))
            if self._badge_img:
                bx, by = INFO_BADGE_POS
                bw, bh = INFO_BADGE_SIZE
                self.screen.blit(self._badge_img, (bx - bw // 2, by - bh // 2))
            info_font = load_chinese_font(INFO_FONT_SIZE)
            values = [
                f"LV.{self._current_level - 1}",
                "忆调模式",
                f"{self._total_success}/{self._total_rounds}",
                str(self._total_score),
            ]
            texts = [
                (cx, cy, info_font.render(v, True, (255, 255, 255)), info_font.render(v, True, (30, 15, 5)))
                for (cx, cy), v in zip(INFO_REGIONS, values)
            ]
            for cx, cy, txt, shadow in texts:
                tw, th = txt.get_size()
                x = cx - tw // 2
                y = cy - th // 2
                self.screen.blit(shadow, (x + 1, y + 1))
                self.screen.blit(txt, (x, y))

    def _draw_hud_circles(self) -> None:

        if self._phase == "playing" and self._target_index < len(self._recipe_ingredients):
            n = len(self._recipe_ingredients)
            circles_y = 140
            circle_r = 6
            circle_gap = 18
            total_c_w = n * (circle_r * 2) + (n - 1) * circle_gap
            start_x = SCREEN_WIDTH // 2 - total_c_w // 2
            for i in range(n):
                cx = start_x + i * (circle_r * 2 + circle_gap)
                if i < self._target_index:
                    color = (100, 255, 100)
                elif i == self._target_index:
                    pulse = (math.sin(self._phase_timer * 6) + 1) * 0.5
                    color = (
                        int(255 * pulse + 200 * (1 - pulse)),
                        int(200 * pulse + 150 * (1 - pulse)),
                        int(100 * pulse + 50 * (1 - pulse)),
                    )
                else:
                    color = (80, 80, 80)
                pygame.draw.circle(self.screen, color, (cx, circles_y), circle_r)

    def _draw_session_timer(self) -> None:
        if not self._first_round_started:
            remain = self._session_duration
        else:
            elapsed = time.time() - self._session_start_time
            remain = max(0, self._session_duration - elapsed)
        mins = int(remain // 60)
        secs = int(remain % 60)
        text = f"{mins:02d}:{secs:02d}"
        color = (255, 100, 100) if remain < 60 else (200, 200, 200)
        surf = self.small_font.render(text, True, color)
        self.screen.blit(surf, (SCREEN_WIDTH - surf.get_width() - 20, 82))

    def _draw_attention_indicator(self) -> None:
        attn_surf = self.small_font.render(f"专注力: {self._attention}", True, (100, 200, 255))
        self.screen.blit(attn_surf, (20, 82))
        bar_w = 120
        bar_h = 10
        bar_x = 20
        bar_y = 108
        fill = int(bar_w * self._attention / 100.0)
        pygame.draw.rect(self.screen, (60, 60, 60), (bar_x, bar_y, bar_w, bar_h), border_radius=3)
        if fill > 0:
            color = (100, 200, 255)
            pygame.draw.rect(self.screen, color, (bar_x, bar_y, fill, bar_h), border_radius=3)

    def _draw_rules(self) -> None:
        popup = pygame.Surface((700, 340), pygame.SRCALPHA)
        pygame.draw.rect(popup, (30, 25, 20, 220), (0, 0, 700, 340), border_radius=20)
        pygame.draw.rect(popup, (255, 180, 100, 100), (0, 0, 700, 340), 3, border_radius=20)

        lines = [
            ("忆调模式", self.big_font, (255, 200, 100)),
            ("", self.small_font, (255, 255, 255)),
            ("1. 请记住屏幕中央的配方食材组合", self.font, (255, 255, 255)),
            ("2. 食材消失后，按顺序接住配方中的食材", self.font, (255, 255, 255)),
            ("3. 必须严格按顺序！接错顺序即失败", self.font, (255, 220, 100)),
            ("", self.small_font, (255, 255, 255)),
        ]

        y = 30
        for text, fnt, color in lines:
            if text:
                surf = fnt.render(text, True, color)
                popup.blit(surf, ((700 - surf.get_width()) // 2, y))
                y += 42 if fnt == self.font else 55 if fnt == self.big_font else 20

        px = (SCREEN_WIDTH - 700) // 2
        py = (SCREEN_HEIGHT - 340) // 2
        self.screen.blit(popup, (px, py))

    def _draw_memorize(self) -> None:
        shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 180))
        self.screen.blit(shade, (0, 0))

        n = len(self._recipe_ingredients)
        img_size = 90
        gap = 15
        total_w = n * img_size + (n - 1) * gap
        start_x = (SCREEN_WIDTH - total_w) // 2
        y = SCREEN_HEIGHT // 2 - 70

        for i, ing_type in enumerate(self._recipe_ingredients):
            x = start_x + i * (img_size + gap)
            path = INGREDIENT_IMGS.get(ing_type, "")
            if path and os.path.exists(path):
                img = pygame.image.load(path).convert_alpha()
                img = pygame.transform.scale(img, (img_size, img_size))
            else:
                img = pygame.Surface((img_size, img_size), pygame.SRCALPHA)
                pygame.draw.circle(img, (200, 160, 100), (img_size // 2, img_size // 2), img_size // 2)
            self.screen.blit(img, (x, y))

        name_surf = self.font.render(self._recipe_name, True, (255, 220, 100))
        self.screen.blit(
            name_surf,
            (SCREEN_WIDTH // 2 - name_surf.get_width() // 2, y + img_size + 18),
        )

        remain = max(0, self._memorize_time - self._phase_timer)
        bar_w = int(300 * remain / self._memorize_time)
        bar_rect = pygame.Rect(SCREEN_WIDTH // 2 - 150, SCREEN_HEIGHT - 60, bar_w, 8)
        pygame.draw.rect(self.screen, (255, 180, 100), bar_rect, border_radius=4)
        timer_text = self.small_font.render(f"记忆时间 {remain:.1f}s", True, (40, 40, 40))
        self.screen.blit(timer_text, (SCREEN_WIDTH // 2 - timer_text.get_width() // 2, SCREEN_HEIGHT - 250))

    def _draw_result(self) -> None:
        if self._round_result == "success":
            text = f"成功制作 {self._recipe_name}"
            color = (100, 255, 100)
        elif self._round_result == "wrong":
            text = "接错食材，制作失败"
            color = (255, 120, 100)
        else:
            text = "未完成，制作失败"
            color = (255, 180, 60)

        popup = pygame.Surface((500, 120), pygame.SRCALPHA)
        pygame.draw.rect(popup, (25, 20, 15, 220), (0, 0, 500, 120), border_radius=16)
        pygame.draw.rect(popup, (*color, 120), (0, 0, 500, 120), 3, border_radius=16)

        surf = self.font.render(text, True, color)
        popup.blit(surf, ((500 - surf.get_width()) // 2, (120 - surf.get_height()) // 2))

        px = (SCREEN_WIDTH - 500) // 2
        py = SCREEN_HEIGHT // 2 - 60
        self.screen.blit(popup, (px, py))

    def _draw_rest(self) -> None:
        remain = max(0, self._rest_time - self._phase_timer)
        elapsed = self._session_start_time
        if self._first_round_started:
            elapsed = time.time() - self._session_start_time
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        text = "训练结束，正在结算..." if self._session_ending else f"下一杯即将开始... {remain:.0f}s"
        surf = self.font.render(text, True, (40, 40, 40))
        self.screen.blit(surf, (SCREEN_WIDTH // 2 - surf.get_width() // 2, SCREEN_HEIGHT // 2 - 230))

        lvl_text = self.small_font.render(
            f"已训练 {mins:02d}:{secs:02d} | "
            f"当前等级: {self._current_level}食材配方 | "
            f"连续成功: {self._consecutive_success}/{self._upgrade_threshold} | "
            f"失败: {self._round_failures}/{self._downgrade_threshold}",
            True,
            (40, 40, 40),
        )
        self.screen.blit(lvl_text, (SCREEN_WIDTH // 2 - lvl_text.get_width() // 2, SCREEN_HEIGHT // 2 - 180))

    def _commit_esc_dialog(self) -> None:
        if self._esc_dialog_selected == 0:
            self._esc_dialog_active = False
        elif self._esc_dialog_selected == 1:
            self._esc_dialog_active = False
            self.running = False
            self._end_game()
        else:
            self._esc_dialog_active = False
            self._pending_settings = True

    def _handle_esc_dialog_click(self, pos: tuple[int, int]) -> None:
        if hasattr(self, "_esc_continue_rect") and self._esc_continue_rect.collidepoint(pos):
            self._esc_dialog_active = False
        elif hasattr(self, "_esc_exit_rect") and self._esc_exit_rect.collidepoint(pos):
            self._esc_dialog_active = False
            self.running = False
            self._end_game()
        elif hasattr(self, "_esc_settings_rect") and self._esc_settings_rect.collidepoint(pos):
            self._esc_dialog_active = False
            self._pending_settings = True

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

        title = self.pause_font.render("暂停", True, (255, 255, 255))
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
        continue_text = self.font.render("继续游戏", True, (255, 255, 255))
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
        exit_text = self.font.render("退出游戏", True, (255, 255, 255))
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


def run_memory_game(
    screen: pygame.Surface, clock: pygame.time.Clock, audio=None, control_mode: str = "bci", profile=None
) -> str:
    session = MemorySession(screen, clock, audio=audio, control_mode=control_mode, profile=profile)
    return session.run()
