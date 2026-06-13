"""游戏 HUD 模块 - HUD 渲染逻辑"""

import pygame

from config import (
    CUP_DURATION,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)

from game.font_utils import load_chinese_font


def draw_hud(
    screen,
    score_manager,
    mode_name,
    cup_manager,
    game_start_time,
    font,
    hint_font,
    attention=None,
    bci_mode=False,
    free_combine=False,
    bci_connected=False,
    focus_above_seconds=0.0,
    raw_gyro_x=0.0,
    raw_gyro_y=0.0,
    raw_gyro_z=0.0,
    platform_focus_x=640.0,
    platform_focus_y=620.0,
    cup_x=0,
    cup_y=0,
    attn_variance=0.0,
    attn_mode="",
    attn_baseline=0.0,
    skip_top_info=False,
):
    import time

    current_time = time.time()
    game_elapsed = current_time - game_start_time
    is_infinite = cup_manager.total_cups < 0
    total_max_time = -1.0 if is_infinite else cup_manager.total_cups * CUP_DURATION
    game_remaining = -1.0 if is_infinite else max(0.0, total_max_time - game_elapsed)

    bar_w = SCREEN_WIDTH
    bar_x = (SCREEN_WIDTH - bar_w) // 2
    bar_y = 0
    bar_h = 60
    bar_center_x = SCREEN_WIDTH // 2
    bar_right = bar_x + bar_w
    bar_font = load_chinese_font(38)
    spacing = 200

    money_text = bar_font.render(f"收益: {score_manager.total_money}", True, (20, 20, 20))
    cy = bar_y + (bar_h - money_text.get_height()) // 2

    if not skip_top_info:
        screen.blit(money_text, (bar_center_x - money_text.get_width() // 2, cy))
        mode_color = (139, 0, 0) if (bci_mode and not bci_connected) else (20, 20, 20)
        mode_text = bar_font.render(mode_name, True, mode_color)
        screen.blit(mode_text, (bar_x + spacing, cy))

        if is_infinite:
            cup_text = bar_font.render("已接杯数: ∞", True, (20, 20, 20))
        else:
            cup_text = bar_font.render(
                f"已接杯数: {cup_manager.cup_number}",
                True,
                (20, 20, 20),
            )
        screen.blit(cup_text, (bar_right - spacing - cup_text.get_width(), cy))

    cup_rem = max(0, CUP_DURATION - (time.time() - cup_manager.cup_start_time))

    if not is_infinite:
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

    attention_value = attention if attention is not None else 0
    if bci_mode and bci_connected:
        attention_text = f"注意力 {int(attention_value)}"
        attention_surface = font.render(attention_text, True, (0, 255, 0))
        attention_rect = attention_surface.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
        screen.blit(attention_surface, attention_rect)
