"""疯狂奶茶杯 - 游戏主入口
负责初始化 pygame、管理界面跳转（主菜单 -> 模式选择 -> 游戏）
"""

from __future__ import annotations

import logging
import os
import sys

import pygame

from config import IMAGES_DIR
from core.audio_manager import AudioManager
from core.state_machine import GameEvent, GameState, State, StateMachine
from data.player_profile import PlayerProfile
from game.font_utils import load_chinese_font
from game.session import run_game
from menu import GameSettingsScreen, MainMenu
from menu.login import LoginScreen
from menu.splash import SplashScreen
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
        return GameState.LOGIN

    def handle_event(self, event: GameEvent) -> GameState | None:
        return None

    def update(self) -> None:
        pass


class LoginState(State):
    """登录状态"""

    def __init__(self, screen: pygame.Surface, context: dict) -> None:
        self.screen = screen
        self._context = context

    def enter(self) -> GameState | None:
        login = LoginScreen(self.screen)
        username = login.run()
        if username is None or username == "quit":
            return GameState.QUIT
        self._context["username"] = username
        self._context["profile"] = PlayerProfile.load_for_user(username)
        return GameState.MENU

    def handle_event(self, event: GameEvent) -> GameState | None:
        return None

    def update(self) -> None:
        pass


class MenuState(State):
    """主菜单状态"""

    def __init__(self, screen: pygame.Surface, context: dict, audio: AudioManager) -> None:
        self.screen = screen
        self.font = load_chinese_font(24)
        self.title_font = load_chinese_font(40)
        self._context = context
        self._audio = audio

    def enter(self) -> GameState | None:
        self._audio.play_bgm("玻璃糖果园.wav", volume=0.5)

        profile = self._context.get("profile")
        player_level = profile.level if profile else 1
        history_games = profile.games_history if profile else []
        menu = MainMenu(self.screen, self.font, self.title_font, player_level, history_games)
        result, mode, use_bci = menu.run()
        result = result or "quit"
        mode = mode or "regular"
        self._context["game_mode"] = mode
        self._context["use_bci"] = use_bci

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

    def __init__(self, screen: pygame.Surface, audio: AudioManager) -> None:
        self.screen = screen
        self._audio = audio

    def enter(self) -> GameState | None:
        self._audio.play_bgm("晨光木盒.wav", volume=0.5)
        SplashScreen(self.screen, load_chinese_font(110)).run()
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
        use_bci = self._context.get("use_bci", False)
        if use_bci:
            mode = "bci"
        profile = self._context.get("profile")
        game_result = run_game(self.screen, self.clock, game_mode=mode, profile=profile)
        if profile:
            profile.save()
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
    screen = pygame.display.set_mode((1280, 720), pygame.SCALED | pygame.RESIZABLE)
    pygame.display.set_caption("疯狂奶茶杯")
    icon_path = os.path.join(IMAGES_DIR, "other", "游戏图标.png")
    if os.path.exists(icon_path):
        pygame.display.set_icon(pygame.image.load(icon_path))

    clock = pygame.time.Clock()
    context: dict = {}
    audio = AudioManager()
    audio.init()

    sm = StateMachine()
    sm.register(GameState.SPLASH, SplashState(screen, load_chinese_font(110)))
    sm.register(GameState.LOGIN, LoginState(screen, context))
    sm.register(GameState.MENU, MenuState(screen, context, audio))
    sm.register(GameState.SETTINGS, SettingsState(screen))
    sm.register(GameState.TRANSITION, TransitionState(screen, audio))
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
