"""游戏 HUD 模块 - 专注力茶壶 UI + HUD 渲染逻辑"""

import math
import os

import pygame

from config import (
    CUP_DURATION,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)

from game.font_utils import load_chinese_font

_glow_alpha = 0.0
_glow_phase = 0.0


class FocusTeapotUI:
    """专注力茶壶 UI - 液面高度代表专注力数值（0-100）"""

    def __init__(self, image_path=None, x=10, y=90, width=100, height=120):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.focus_value = 0
        self._liquid_color = (144, 238, 144)
        self._teapot_img = None

        if image_path and os.path.exists(image_path):
            try:
                self._teapot_img = pygame.image.load(image_path).convert_alpha()
                self._teapot_img = pygame.transform.scale(self._teapot_img, (self.width, self.height))
            except (pygame.error, OSError):
                pass

    def update(self, value):
        self.focus_value = max(0, min(100, value))
        t = self.focus_value / 100.0
        r = int(144 + (255 - 144) * t)
        g = int(238 + (215 - 238) * t)
        b = int(144 + (0 - 144) * t)
        self._liquid_color = (r, g, b)

    def draw(self, screen):
        if self._teapot_img:
            screen.blit(self._teapot_img, (self.x, self.y))
        else:
            self._draw_fallback(screen)

    def _draw_fallback(self, screen):
        cx = self.x + self.width // 2
        cy = self.y + self.height // 2
        body_r = self.width * 0.38

        handle_rect = pygame.Rect(cx + body_r - 5, cy - body_r * 0.6, self.width * 0.35, body_r * 1.2)
        pygame.draw.rect(screen, (139, 69, 19), handle_rect, 6, border_radius=10)

        spout_pts = [
            (cx - body_r + 5, cy - body_r * 0.2),
            (cx - body_r - self.width * 0.35, cy - body_r * 0.8),
            (cx - body_r - self.width * 0.25, cy - body_r * 0.6),
            (cx - body_r + 5, cy + body_r * 0.4),
        ]
        pygame.draw.polygon(screen, (139, 69, 19), spout_pts, 6)

        body_rect = pygame.Rect(cx - body_r, cy - body_r, body_r * 2, body_r * 2)

        liquid_h = body_rect.height * (self.focus_value / 100.0)
        if liquid_h > 0:
            clip_surf = pygame.Surface((body_rect.width, body_rect.height), pygame.SRCALPHA)
            pygame.draw.ellipse(clip_surf, (255, 255, 255), (0, 0, body_rect.width, body_rect.height))
            pygame.draw.rect(
                clip_surf,
                self._liquid_color,
                (0, body_rect.height - liquid_h, body_rect.width, liquid_h),
            )
            if liquid_h > 4:
                pygame.draw.line(
                    clip_surf,
                    (255, 255, 255),
                    (4, body_rect.height - liquid_h + 2),
                    (body_rect.width - 4, body_rect.height - liquid_h + 2),
                    2,
                )
            screen.blit(clip_surf, (body_rect.x, body_rect.y))

        glass_surf = pygame.Surface((body_rect.width, body_rect.height), pygame.SRCALPHA)
        pygame.draw.ellipse(glass_surf, (200, 200, 200, 80), (0, 0, body_rect.width, body_rect.height))
        screen.blit(glass_surf, (body_rect.x, body_rect.y))
        pygame.draw.ellipse(screen, (139, 69, 19), body_rect, 6)

        lid_rect = pygame.Rect(cx - body_r * 0.8, cy - body_r - 10, body_r * 1.6, 14)
        pygame.draw.rect(screen, (139, 69, 19), lid_rect, 6, border_radius=8)
        knob_rect = pygame.Rect(cx - 8, cy - body_r - 18, 16, 10)
        pygame.draw.ellipse(screen, (160, 82, 45), knob_rect)

        font = pygame.font.Font(None, 28)
        val_surf = font.render(f"{int(self.focus_value)}", True, (255, 255, 255))
        screen.blit(
            val_surf,
            (
                body_rect.x + (body_rect.width - val_surf.get_width()) // 2,
                body_rect.y + body_rect.height // 2 - val_surf.get_height() // 2,
            ),
        )


def draw_hud(
    screen,
    score_manager,
    mode_name,
    cup_manager,
    game_start_time,
    font,
    hint_font,
    recipe_font,
    focus_teapot=None,
    attention=None,
    smoothed_yaw=0,
    bci_mode=False,
    free_combine=False,
    recipe_result=None,
    creative_ingredients=None,
    attention_curve=None,
    bci_connected=False,
    difficulty_adapter=None,
    focus_above_seconds=0.0,
    raw_gyro_x=0.0,
    raw_gyro_y=0.0,
    raw_gyro_z=0.0,
    platform_focus_x=640.0,
    platform_focus_y=620.0,
    cup_x=0,
    cup_y=0,
    rolling_attention=0.0,
    attn_variance=0.0,
    attn_mode="",
):
    global _glow_alpha, _glow_phase
    import time as time_module

    current_time = time_module.time()
    game_elapsed = current_time - game_start_time
    total_max_time = cup_manager.total_cups * CUP_DURATION
    game_remaining = max(0.0, total_max_time - game_elapsed)

    bar_w = 1000
    bar_x = (SCREEN_WIDTH - bar_w) // 2
    bar_y = 0
    bar_h = 50
    bar_center_x = SCREEN_WIDTH // 2
    bar_right = bar_x + bar_w
    bar_font = load_chinese_font(38)  # 调整字体大小
    money_text = bar_font.render(f"收益: {score_manager.total_money}", True, (20, 20, 20))
    cy = bar_y + (bar_h - money_text.get_height()) // 2 + 5
    screen.blit(money_text, (bar_center_x - money_text.get_width() // 2, cy))

    mode_text = bar_font.render(mode_name, True, (20, 20, 20))
    screen.blit(mode_text, (bar_x + 80, cy))

    cup_text = bar_font.render(
        f"第 {cup_manager.cup_number}/{cup_manager.total_cups} 杯",
        True,
        (20, 20, 20),
    )
    screen.blit(cup_text, (bar_right - 80 - cup_text.get_width(), cy))

    total_time_text = hint_font.render(
        f"总局 {int(game_remaining)}s",
        True,
        (20, 20, 20),
    )
    screen.blit(total_time_text, (8, 4))

    if bci_mode:
        gyro_x = SCREEN_WIDTH - 300
        gyro_y = 52
        line_h = 22
        gyro_data = [
            f"偏航角: {raw_gyro_x:.2f}",
            f"俯仰角: {raw_gyro_y:.2f}",
            f"翻滚角: {raw_gyro_z:.2f}",
            f"平台焦点X: {platform_focus_x:.0f}",
            f"平台焦点Y: {platform_focus_y:.0f}",
            f"杯子屏幕X: {cup_x}",
            f"杯子屏幕Y: {cup_y}",
        ]
        if attn_mode:
            gyro_data.append(f"--必接概率调整--")
            gyro_data.append(f"方差: {attn_variance:.0f} | {attn_mode}")
        bg_rect = pygame.Rect(gyro_x - 8, gyro_y - 4, 290, line_h * len(gyro_data) + 8)
        bg_surf = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
        bg_surf.fill((0, 0, 0, 120))
        screen.blit(bg_surf, (bg_rect.x, bg_rect.y))
        for i, line in enumerate(gyro_data):
            color = (200, 200, 200)
            if "平台焦点" in line:
                color = (100, 255, 100)
            txt = hint_font.render(line, True, color)
            screen.blit(txt, (gyro_x, gyro_y + i * line_h))

    if focus_teapot:
        if attention is not None:
            focus_teapot.update(attention)
        else:
            focus_teapot.update(0)
        focus_teapot.draw(screen)

    if bci_mode and attention is not None:
        if free_combine and attention_curve:
            multiplier = attention_curve.map_attention(attention)
            tier = attention_curve.get_rating_tier(attention)
            bci_text = hint_font.render(
                f"{tier} x{multiplier:.2f}",
                True,
                (255, 255, 255),
            )
        else:
            bci_text = hint_font.render(
                f"头动: {smoothed_yaw:.1f}",
                True,
                (255, 255, 255),
            )
        screen.blit(bci_text, (10, 235))

        if difficulty_adapter:
            bl = difficulty_adapter.baseline
            bli_text = hint_font.render(
                f"基线: {bl:.0f}  阈值: {difficulty_adapter.get_secret_threshold():.0f}",
                True,
                (200, 200, 200),
            )
            screen.blit(bli_text, (10, 260))
    elif bci_mode and attention is None:
        bci_text = hint_font.render("BCI设备未连接", True, (200, 0, 0))
        screen.blit(bci_text, (10, 235))

    if cup_manager.secret_recipe_spawned and not cup_manager.secret_recipe_caught:
        _glow_phase += 0.06
        alpha_val = int(128 + 127 * math.sin(_glow_phase))
        secret_surf = recipe_font.render("秘方已掉落!", True, (255, 215, 0))
        secret_surf.set_alpha(alpha_val)
        screen.blit(
            secret_surf,
            (SCREEN_WIDTH // 2 - secret_surf.get_width() // 2, SCREEN_HEIGHT - 100),
        )
    elif cup_manager.secret_recipe_caught:
        _glow_phase += 0.06
        alpha_val = int(128 + 127 * math.sin(_glow_phase))
        double_surf = recipe_font.render("2x 收益!", True, (255, 215, 0))
        double_surf.set_alpha(alpha_val)
        screen.blit(
            double_surf,
            (SCREEN_WIDTH // 2 - double_surf.get_width() // 2, SCREEN_HEIGHT - 100),
        )

    if bci_mode and not cup_manager.secret_recipe_spawned:
        threshold = 75.0
        if difficulty_adapter:
            threshold = difficulty_adapter.get_secret_threshold()
        progress = min(1.0, focus_above_seconds / 5.0)
        bar_x = SCREEN_WIDTH // 2 - 60
        bar_y = SCREEN_HEIGHT - 75
        bar_w = 120
        bar_h = 10
        pygame.draw.rect(screen, (80, 80, 80), (bar_x, bar_y, bar_w, bar_h), border_radius=5)
        fill_w = int(bar_w * progress)
        if fill_w > 0:
            bar_color = (255, 215, 0) if progress >= 1.0 else (100, 200, 100)
            pygame.draw.rect(screen, bar_color, (bar_x, bar_y, fill_w, bar_h), border_radius=5)
        threshold_text = hint_font.render(
            f"秘方: {focus_above_seconds:.1f}s / 5s  (需>{threshold:.0f})",
            True,
            (200, 200, 200),
        )
        screen.blit(threshold_text, (SCREEN_WIDTH // 2 - threshold_text.get_width() // 2, bar_y - 20))

    if free_combine and recipe_result:
        recipe_name = recipe_result["recipe_name"]
        rating = recipe_result["rating"]
        total_score = recipe_result["total_score"]

        name_surf = recipe_font.render(f"{rating['emoji']} {recipe_name}", True, rating["color"])
        screen.blit(name_surf, (SCREEN_WIDTH // 2 - name_surf.get_width() // 2, 140))

        grade_surf = recipe_font.render(f"评分: {rating['name']} ({total_score})", True, rating["color"])
        screen.blit(grade_surf, (SCREEN_WIDTH // 2 - grade_surf.get_width() // 2, 175))

        if creative_ingredients:
            ing_text = hint_font.render(f"食材: {' + '.join(creative_ingredients)}", True, (80, 80, 80))
            screen.blit(ing_text, (SCREEN_WIDTH // 2 - ing_text.get_width() // 2, 210))

    if bci_mode:
        hint_text = "脑机接口模式 | ESC 返回"
    elif free_combine:
        hint_text = "自由搭配，创造你的专属奶茶 | ESC 返回"
    else:
        hint_text = "方向键: 左右移动 | ESC: 返回"

    hint1 = hint_font.render(hint_text, True, (50, 50, 50))
    screen.blit(hint1, (10, SCREEN_HEIGHT - 40))

    attention_value = attention if attention is not None else 0
    if bci_mode:
        attention_text = f"注意力 {int(attention_value)}  |  3秒均值 {int(rolling_attention)}"
    else:
        attention_text = f"注意力: {int(attention_value)}"
    attention_surface = font.render(attention_text, True, (0, 255, 0) if bci_connected else (255, 0, 0))
    attention_rect = attention_surface.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
    screen.blit(attention_surface, attention_rect)
