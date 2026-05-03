"""疯狂奶茶杯 - 游戏主入口
负责初始化 pygame、管理界面跳转（主菜单 -> 模式选择 -> 游戏）
"""

from __future__ import annotations

import logging
import os
import sys

import pygame

from config import IMAGES_DIR, SCREEN_HEIGHT, SCREEN_WIDTH
from core.state_machine import GameEvent, GameState, State, StateMachine
from game.font_utils import load_chinese_font
from game.session import run_game
from menu import GameSettingsScreen, MainMenu
from menu.splash import SplashScreen
from menu.transition import StartTransition
from utils.logging_config import get_logger, setup_logging

logger = get_logger(__name__)


class SplashState(State):
    """启动动画状态"""

    def __init__(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        self.screen = screen
        self.font = font
        self.splash = SplashScreen(screen, font)

    def enter(self) -> GameState | None:
        self.splash.run()
        return GameState.MENU

    def handle_event(self, event: GameEvent) -> GameState | None:
        return None

    def update(self) -> None:
        pass


class MenuState(State):
    """主菜单状态"""

    def __init__(self, screen: pygame.Surface, context: dict) -> None:
        self.screen = screen
        self.font = load_chinese_font(24)
        self.title_font = load_chinese_font(40)
        self._context = context

    def enter(self) -> GameState | None:
        menu = MainMenu(self.screen, self.font, self.title_font)
        result, mode = menu.run()
        result = result or "quit"
        mode = mode or "regular"
        self._context["game_mode"] = mode

        if result == "quit":
            return GameState.QUIT
        if result == "settings":
            return GameState.SETTINGS
        if result == "start":
            return GameState.TRANSITION
        return None

    def handle_event(self, event: GameEvent) -> GameState | None:
        return None

    def update(self) -> None:
        pass


class QuitState(State):
    """退出状态（空操作，仅用于标记退出）"""

    def enter(self) -> GameState | None:
        return None

    def handle_event(self, event: GameEvent) -> GameState | None:
        return None

    def update(self) -> None:
        pass


class SettingsState(State):
    """设置页面状态"""

    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.font = load_chinese_font(24)
        self.title_font = load_chinese_font(40)

    def enter(self) -> GameState | None:
        settings_screen = GameSettingsScreen(self.screen, self.font, self.title_font)
        settings_screen.run()
        return GameState.MENU

    def handle_event(self, event: GameEvent) -> GameState | None:
        return None

    def update(self) -> None:
        pass


class TransitionState(State):
    """过场动画状态"""

    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen

    def enter(self) -> GameState | None:
        StartTransition(self.screen).run()
        return GameState.GAME

    def handle_event(self, event: GameEvent) -> GameState | None:
        return None

    def update(self) -> None:
        pass


class GameStateImpl(State):
    """游戏运行状态"""

    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock, context: dict) -> None:
        self.screen = screen
        self.clock = clock
        self._context = context

    def enter(self) -> GameState | None:
        mode = self._context.get("game_mode", "regular")
        game_result = run_game(self.screen, self.clock, game_mode=mode)
        if game_result == "quit":
            return GameState.QUIT
        return GameState.MENU

    def handle_event(self, event: GameEvent) -> GameState | None:
        return GameState.MENU

    def update(self) -> None:
        pass


def main() -> None:
    """游戏主入口，管理界面循环跳转"""
    setup_logging(level=logging.INFO, log_file="game.log")
    logger.info("游戏启动")

    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("疯狂奶茶杯 - 第1周")
    icon_path = os.path.join(IMAGES_DIR, "other", "游戏图标.png")
    if os.path.exists(icon_path):
        pygame.display.set_icon(pygame.image.load(icon_path))

    clock = pygame.time.Clock()
    context: dict = {}

    sm = StateMachine()
    sm.register(GameState.SPLASH, SplashState(screen, load_chinese_font(110)))
    sm.register(GameState.MENU, MenuState(screen, context))
    sm.register(GameState.SETTINGS, SettingsState(screen))
    sm.register(GameState.TRANSITION, TransitionState(screen))
    sm.register(GameState.GAME, GameStateImpl(screen, clock, context))
    sm.register(GameState.QUIT, QuitState())

    sm.start(GameState.SPLASH)

    while sm.running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sm.quit()
                break

        sm.process_events()
        sm.update()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
