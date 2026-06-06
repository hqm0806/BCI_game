"""记忆模式游戏会话 - 记忆配方→按序接食材"""

from __future__ import annotations

import math
import os
import random

import pygame

from config import (
    BACKGROUND_IMG,
    INGREDIENT_IMGS,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)
from data.memory_recipes import MEMORY_RECIPES
from game.font_utils import load_chinese_font
from game.sprites import Cup, Ingredient


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
    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock, audio=None,
                 control_mode: str = "keyboard", profile=None) -> None:
        self.screen = screen
        self.clock = clock
        self._audio = audio
        self._control_mode = control_mode
        self._profile = profile
        self.font = load_chinese_font(36)
        self.big_font = load_chinese_font(48)
        self.small_font = load_chinese_font(20)
        self.running = True

        self._bg = self._load_bg()

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
        self._spawn_count = 0
        self._recipe_spawn_index = 0
        self._recipe_ratio = 3
        self._ingredient_speed = 5.5

        self._num_lanes = 5
        self._lane_w = SCREEN_WIDTH // self._num_lanes
        self._lane_spacing = 400
        self._max_per_lane = 1

        self._rules_display_time = 3.5
        self._memorize_time = 2.0   # 每轮记忆阶段持续时间
        self._drop_window = 15.0
        self._result_time = 1.5
        self._rest_time = 2.0

        self._round_result = ""

        self._total_score = 0
        self._total_rounds = 0
        self._total_success = 0

        self._catch_success_timer = 0.0

        self._bci_available = False
        self._bci_reader = None
        self._use_yaw = False
        self._platform_focus_x = float(SCREEN_WIDTH // 2)
        self._focus_min = 40
        self._focus_max = SCREEN_WIDTH - 40

        if self._control_mode not in ("keyboard", "bci_failed"):
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

    def _enter_phase(self, phase: str) -> None:
        self._phase = phase
        self._phase_timer = 0.0
        if phase == "memorize":
            self._pick_recipe()
        elif phase == "playing":
            self._all_ingredients.empty()
            self._spawn_timer = 0.3
            self._spawn_count = 0
            self._recipe_spawn_index = 0

    def _free_lane(self) -> int | None:
        lanes = list(range(self._num_lanes))
        random.shuffle(lanes)
        for lane in lanes:
            lane_left = lane * self._lane_w
            lane_right = lane_left + self._lane_w
            count = 0
            blocked = False
            for ing in self._all_ingredients:
                if lane_left <= ing.rect.centerx < lane_right:
                    count += 1
                    if ing.rect.y < self._lane_spacing:
                        blocked = True
                        break
            if not blocked and count < self._max_per_lane:
                return lane
        return None

    def _spawn_ingredient(self, ing_type: str) -> Ingredient | None:
        lane = self._free_lane()
        if lane is None:
            return None
        center = lane * self._lane_w + self._lane_w // 2
        x = random.randint(center - 30, center + 30)
        x = max(lane * self._lane_w + 10, min((lane + 1) * self._lane_w - 90, x))

        ing = Ingredient(ing_type, speed=self._ingredient_speed)
        ing.rect.width = 80
        ing.rect.height = 80
        ing.rect.centerx = x
        ing.rect.y = -80

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

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    return "quit"
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.running = False
                    return "menu"

            if self._phase == "rules":
                if self._phase_timer >= self._rules_display_time:
                    self._enter_phase("memorize")

            elif self._phase == "memorize":
                if self._phase_timer >= self._memorize_time:
                    self._enter_phase("playing")

            elif self._phase == "playing":
                if self._bci_available:
                    result = self._bci_reader.read_with_timeout()
                    if result[1] is not None:
                        self._platform_focus_x = float(result[1])

                keys = pygame.key.get_pressed()
                kb_pressed = keys[pygame.K_LEFT] or keys[pygame.K_RIGHT]

                if self._use_yaw and not kb_pressed:
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

                n = len(self._recipe_ingredients)
                if n == 0:
                    self._enter_phase("result")
                    continue
                if self._catch_success_timer <= 0:
                    self._spawn_timer -= dt
                    while self._spawn_timer <= 0:
                        if self._spawn_count % self._recipe_ratio == 0:
                            ing_type = self._recipe_ingredients[self._recipe_spawn_index % n]
                            self._recipe_spawn_index += 1
                        else:
                            ing_type = self._random_distractor()
                        self._spawn_ingredient(ing_type)
                        self._spawn_count += 1
                        self._spawn_timer += self._spawn_interval

                for ing in list(self._all_ingredients):
                    ing.update()
                for ing in list(self._all_ingredients):
                    if ing.rect.top > SCREEN_HEIGHT + 50:
                        ing.kill()

                self._check_catches()

                if self._catch_success_timer > 0:
                    self._catch_success_timer -= dt
                    if self._catch_success_timer <= 0:
                        self._enter_phase("result")

                if self._phase == "playing" and self._phase_timer >= self._drop_window:
                    if self._target_index < len(self._recipe_ingredients):
                        self._round_result = "timeout"
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
                    self._enter_phase("rest")

            elif self._phase == "rest":
                if self._phase_timer >= self._rest_time:
                    self._enter_phase("memorize")

            self._draw()
            pygame.display.flip()

        if self._bci_available and self._bci_reader:
            self._bci_reader.disconnect()
        return "menu"

    def _draw(self) -> None:
        self.screen.fill((0, 0, 0))
        if self._bg:
            self.screen.blit(self._bg, (0, 0))
        else:
            self.screen.fill((40, 25, 15))

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 40))
        self.screen.blit(overlay, (0, 0))

        self._draw_hud()

        if self._phase in ("rules", "memorize", "result", "rest"):
            self.cup.rect.centerx = SCREEN_WIDTH // 2
            self.cup.rect.bottom = SCREEN_HEIGHT - 10
        self.screen.blit(self.cup.image, self.cup.rect)

        for ing in self._all_ingredients:
            self.screen.blit(ing.image, ing.rect)

        for p in self._particles:
            self.screen.blit(p.image, p.rect)

        if self._phase == "rules":
            self._draw_rules()
        elif self._phase == "memorize":
            self._draw_memorize()
        elif self._phase == "result":
            self._draw_result()
        elif self._phase == "rest":
            self._draw_rest()

    def _draw_hud(self) -> None:
        level_text = self.small_font.render(
            f"难度 Lv.{self._current_level - 1} | 配方 {self._current_level}食材 | 得分 {self._total_score} | ESC 退出",
            True,
            (200, 180, 140),
        )
        self.screen.blit(level_text, (SCREEN_WIDTH // 2 - level_text.get_width() // 2, 10))

        if self._phase == "playing" and self._target_index < len(self._recipe_ingredients):
            n = len(self._recipe_ingredients)
            circles_y = 40
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

    def _draw_rules(self) -> None:
        popup = pygame.Surface((700, 340), pygame.SRCALPHA)
        pygame.draw.rect(popup, (30, 25, 20, 220), (0, 0, 700, 340), border_radius=20)
        pygame.draw.rect(popup, (255, 180, 100, 100), (0, 0, 700, 340), 3, border_radius=20)

        lines = [
            ("记忆模式", self.big_font, (255, 200, 100)),
            ("", self.small_font, (255, 255, 255)),
            ("1. 请记住屏幕中央的配方食材组合", self.font, (255, 255, 255)),
            ("2. 食材消失后，按顺序接住配方中的食材", self.font, (255, 255, 255)),
            ("3. 必须严格按顺序！接错顺序即失败", self.font, (255, 220, 100)),
            # ("4. 连续成功 3 次升级难度，失败 2 次降级", self.font, (255, 255, 255)),
            # ("5. 最高 5 种食材配方", self.font, (255, 255, 255)),
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
        timer_text = self.small_font.render(f"记忆时间 {remain:.1f}s", True, (200, 180, 140))
        self.screen.blit(timer_text, (SCREEN_WIDTH // 2 - timer_text.get_width() // 2, SCREEN_HEIGHT - 50))

    def _draw_result(self) -> None:
        if self._round_result == "success":
            text = f"成功制作 {self._recipe_name}"
            color = (100, 255, 100)
        elif self._round_result == "wrong":
            text = "接错食材，制作失败"
            color = (255, 120, 100)
        else:
            text = "超时，制作失败"
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
        text = f"下一杯即将开始... {remain:.0f}s"
        surf = self.font.render(text, True, (200, 180, 140))
        self.screen.blit(surf, (SCREEN_WIDTH // 2 - surf.get_width() // 2, SCREEN_HEIGHT // 2 - 30))

        lvl_text = self.small_font.render(
            f"当前等级: {self._current_level}食材配方 | "
            f"连续成功: {self._consecutive_success}/{self._upgrade_threshold} | "
            f"失败: {self._round_failures}/{self._downgrade_threshold}",
            True,
            (180, 160, 120),
        )
        self.screen.blit(lvl_text, (SCREEN_WIDTH // 2 - lvl_text.get_width() // 2, SCREEN_HEIGHT // 2 + 20))


def run_memory_game(screen: pygame.Surface, clock: pygame.time.Clock, audio=None,
                    control_mode: str = "keyboard", profile=None) -> str:
    session = MemorySession(screen, clock, audio=audio, control_mode=control_mode, profile=profile)
    return session.run()
