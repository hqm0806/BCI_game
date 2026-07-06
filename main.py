"""疯狂奶茶杯 - 游戏主入口
负责初始化 pygame、管   理界面跳转（主菜单 -> 模式选择 -> 游戏）
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
from game.experiment_mode import run_experiment
from game.memory_mode import run_memory_game
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
        self._audio.play_bgm("玻璃糖果园.mp3", volume=0.5)

        profile = self._context.get("profile")
        player_level = profile.level if profile else 1
        history_games = profile.games_history if profile else []
        menu = MainMenu(
            self.screen, self.font, self.title_font, player_level, history_games, profile=profile, audio=self._audio
        )
        result, game_mode, control_mode = menu.run()
        result = result or "quit"
        game_mode = game_mode or "bci"
        control_mode = control_mode or "bci"
        self._context["game_mode"] = game_mode
        self._context["control_mode"] = control_mode

        if result == "quit":
            return GameState.QUIT
        if result == "settings":
            return GameState.SETTINGS
        if result == "start_memory":
            return GameState.GAME_MEMORY
        if result == "start_experiment":
            return GameState.TRANSITION
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

    def __init__(self, screen: pygame.Surface, audio: AudioManager) -> None:
        self.screen = screen
        self._audio = audio
        self.font = load_chinese_font(24)
        self.title_font = load_chinese_font(40)

    def enter(self) -> GameState | None:
        bg_snapshot = self.screen.copy()
        settings_screen = GameSettingsScreen(self.screen, self.font, self.title_font, audio=self._audio, bg=bg_snapshot)
        settings_screen.run()
        return GameState.MENU

    def handle_event(self, event: GameEvent) -> GameState | None:
        return None

    def update(self) -> None:
        pass


class TransitionState(State):
    """过场动画状态"""

    def __init__(self, screen: pygame.Surface, audio: AudioManager, context: dict) -> None:
        self.screen = screen
        self._audio = audio
        self._context = context

    def enter(self) -> GameState | None:
        self._audio.stop_bgm()
        self._audio.play_bgm("晨光木盒.mp3", volume=0.5)
        SplashScreen(self.screen, load_chinese_font(110)).run()
        game_mode = self._context.get("game_mode", "bci")
        if game_mode == "experiment":
            return GameState.GAME_EXPERIMENT
        return GameState.GAME

    def handle_event(self, event: GameEvent) -> GameState | None:
        return None

    def update(self) -> None:
        pass


class MemoryGameState(State):
    """忆调模式游戏状态"""

    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock, context: dict) -> None:
        self.screen = screen
        self.clock = clock
        self._context = context

    def enter(self) -> GameState | None:
        audio = self._context.get("audio")
        control_mode = self._context.get("control_mode", "bci")
        profile = self._context.get("profile")
        result = run_memory_game(self.screen, self.clock, audio=audio, control_mode=control_mode, profile=profile)
        if profile and result == "save":
            profile.save()
        if result == "quit":
            return GameState.QUIT
        return GameState.MENU

    def handle_event(self, event: GameEvent) -> GameState | None:
        return GameState.MENU

    def update(self) -> None:
        pass


class ExperimentState(State):
    """实验模式游戏状态 - 3min热身+7min特调+5min忆调"""

    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock, context: dict) -> None:
        self.screen = screen
        self.clock = clock
        self._context = context

    def enter(self) -> GameState | None:
        audio = self._context.get("audio")
        control_mode = self._context.get("control_mode", "bci")
        profile = self._context.get("profile")
        result = run_experiment(self.screen, self.clock, profile=profile, control_mode=control_mode, audio=audio)
        if result == "quit":
            return GameState.QUIT
        return GameState.MENU

    def handle_event(self, event: GameEvent) -> GameState | None:
        return GameState.MENU

    def update(self) -> None:
        pass


class GameStateImpl(State):
    """游戏运行状态"""

    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock, context: dict) -> None:
        self.screen = screen
        self.clock = clock
        self._context = context

    def enter(self) -> GameState | None:
        game_mode = self._context.get("game_mode", "bci")
        control_mode = self._context.get("control_mode", "bci")
        profile = self._context.get("profile")
        audio = self._context.get("audio")
        game_result = run_game(
            self.screen, self.clock, game_mode=game_mode, profile=profile, control_mode=control_mode, audio=audio
        )
        if profile and game_result == "save":
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
    audio.play_bgm("背景乐3.mp3", volume=0.4)
    context["audio"] = audio

    sm = StateMachine()
    sm.register(GameState.SPLASH, SplashState(screen, load_chinese_font(110)))
    sm.register(GameState.LOGIN, LoginState(screen, context))
    sm.register(GameState.MENU, MenuState(screen, context, audio))
    sm.register(GameState.SETTINGS, SettingsState(screen, audio))
    sm.register(GameState.TRANSITION, TransitionState(screen, audio, context))
    sm.register(GameState.GAME, GameStateImpl(screen, clock, context))
    sm.register(GameState.GAME_MEMORY, MemoryGameState(screen, clock, context))
    sm.register(GameState.GAME_EXPERIMENT, ExperimentState(screen, clock, context))
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
