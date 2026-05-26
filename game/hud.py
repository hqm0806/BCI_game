"""游戏 HUD 模块 - HUD 渲染逻辑"""

import math
import os

import pygame

from config import (
    CUP_DURATION,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SECRET_RECIPE_SUSTAIN,
)

from game.font_utils import load_chinese_font

_glow_alpha = 0.0
_glow_phase = 0.0


def draw_hud(
    screen,
    score_manager,
    mode_name,
    cup_manager,
    game_start_time,
    font,
    hint_font,
    recipe_font,
    attention=None,
    bci_mode=False,
    free_combine=False,
    recipe_result=None,
    creative_ingredients=None,
    attention_curve=None,
    bci_connected=False,
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
    attn_baseline=0.0,
):
    global _glow_alpha, _glow_phase
    import time as time_module

    current_time = time_module.time()
    game_elapsed = current_time - game_start_time
    total_max_time = cup_manager.total_cups * CUP_DURATION
    game_remaining = max(0.0, total_max_time - game_elapsed)

    bar_w = 1280
    bar_x = (SCREEN_WIDTH - bar_w) // 2
    bar_y = 0
    bar_h = 60
    bar_center_x = SCREEN_WIDTH // 2
    bar_right = bar_x + bar_w
    bar_font = load_chinese_font(38)
    spacing = 200

    money_text = bar_font.render(f"收益: {score_manager.total_money}", True, (20, 20, 20))
    cy = bar_y + (bar_h - money_text.get_height()) // 2
    screen.blit(money_text, (bar_center_x - money_text.get_width() // 2, cy))

    mode_text = bar_font.render(mode_name, True, (20, 20, 20))
    screen.blit(mode_text, (bar_x + spacing, cy))

    cup_text = bar_font.render(
        f"第 {cup_manager.cup_number}/{cup_manager.total_cups} 杯",
        True,
        (20, 20, 20),
    )
    screen.blit(cup_text, (bar_right - spacing - cup_text.get_width(), cy))

    cup_rem = max(0, CUP_DURATION - (time_module.time() - cup_manager.cup_start_time))

    total_time_text = bar_font.render(
        f"总局 {int(game_remaining)}s",
        True,
        (60, 60, 60),
    )
    screen.blit(total_time_text, (SCREEN_WIDTH - total_time_text.get_width() - 12, SCREEN_HEIGHT - 36))

    cup_timer_text = hint_font.render(
        f"杯倒计时 {cup_rem:.0f}s",
        True,
        (20, 20, 20),
    )
    screen.blit(cup_timer_text, (SCREEN_WIDTH - cup_timer_text.get_width() - 12, SCREEN_HEIGHT - 60))

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

    if bci_mode and attn_baseline > 0:
        bl_text = hint_font.render(f"基线: {attn_baseline:.0f}", True, (200, 200, 200))
        screen.blit(bl_text, (10, 120))

    if bci_mode and attention is not None:
        if free_combine and attention_curve:
            multiplier = attention_curve.map_attention(attention)
            tier = attention_curve.get_rating_tier(attention)
            bci_text = hint_font.render(
                f"{tier} x{multiplier:.2f}",
                True,
                (255, 255, 255),
            )
            screen.blit(bci_text, (10, 235))
    elif bci_mode and attention is None:
        bci_text = hint_font.render("BCI设备未连接", True, (200, 0, 0))
        screen.blit(bci_text, (10, 235))

    if bci_mode and not cup_manager.secret_recipe_spawned:
        progress = min(1.0, focus_above_seconds / SECRET_RECIPE_SUSTAIN)
        bar_x = SCREEN_WIDTH // 2 - 60
        bar_y = SCREEN_HEIGHT - 50
        bar_w = 120
        bar_h = 10
        pygame.draw.rect(screen, (80, 80, 80), (bar_x, bar_y, bar_w, bar_h), border_radius=5)
        fill_w = int(bar_w * progress)
        if fill_w > 0:
            bar_color = (255, 215, 0) if progress >= 1.0 else (100, 200, 100)
            pygame.draw.rect(screen, bar_color, (bar_x, bar_y, fill_w, bar_h), border_radius=5)

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
        attention_text = f"注意力 {int(attention_value)}"
    else:
        attention_text = f"注意力: {int(attention_value)}"
    attention_surface = font.render(attention_text, True, (0, 255, 0) if bci_connected else (255, 0, 0))
    attention_rect = attention_surface.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
    screen.blit(attention_surface, attention_rect)
