"""游戏状态机 - 管理界面之间的跳转"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import Enum, auto

logger = logging.getLogger(__name__)


class GameState(Enum):
    """游戏状态枚举"""

    SPLASH = auto()
    LOGIN = auto()
    MENU = auto()
    SETTINGS = auto()
    TRANSITION = auto()
    GAME = auto()
    GAME_MEMORY = auto()
    QUIT = auto()


class GameEvent:
    """状态机事件"""

    def __init__(self, name: str, **kwargs) -> None:
        self.name = name
        self.data = kwargs

    def __repr__(self) -> str:
        return f"GameEvent({self.name}, {self.data})"


class State(ABC):
    """状态基类

    enter() 可以返回下一个 GameState 来触发自动转换，
    适用于阻塞型界面（如启动动画、设置页等）。
    """

    @abstractmethod
    def enter(self) -> GameState | None:
        """进入状态时调用，返回下一个状态可触发自动转换"""

    @abstractmethod
    def handle_event(self, event: GameEvent) -> GameState | None:
        """处理事件，返回下一个状态或 None"""

    @abstractmethod
    def update(self) -> None:
        """每帧更新"""

    def exit(self) -> None:
        """退出状态时调用"""


class StateMachine:
    """游戏状态机

    使用方式:
        sm = StateMachine()
        sm.register(GameState.MENU, MenuState(screen))
        sm.register(GameState.GAME, GameState(screen, clock))
        sm.start(GameState.MENU)
        while sm.running:
            sm.process_events()
            sm.update()
    """

    def __init__(self) -> None:
        self._states: dict[GameState, State] = {}
        self._current_state: GameState | None = None
        self._pending_transition: GameState | None = None
        self.running = False

    def register(self, state_id: GameState, state: State) -> None:
        """注册状态"""
        self._states[state_id] = state

    def start(self, initial_state: GameState) -> None:
        """启动状态机"""
        if initial_state not in self._states:
            raise ValueError(f"未注册状态: {initial_state}")
        self._current_state = initial_state
        self.running = True
        self._enter_state(initial_state)

    def transition_to(self, next_state: GameState) -> None:
        """请求状态转换"""
        self._pending_transition = next_state

    def process_events(self) -> None:
        """处理所有待转换"""
        if self._pending_transition is not None:
            self._do_transition(self._pending_transition)
            self._pending_transition = None

    def update(self) -> None:
        """更新当前状态"""
        if self._current_state is not None:
            self._states[self._current_state].update()

    def handle_event(self, event: GameEvent) -> None:
        """处理事件"""
        if self._current_state is None:
            return
        next_state = self._states[self._current_state].handle_event(event)
        if next_state is not None:
            self.transition_to(next_state)

    def _do_transition(self, target: GameState) -> None:
        if target not in self._states:
            raise ValueError(f"未注册状态: {target}")
        if self._current_state is not None:
            self._states[self._current_state].exit()
        logger.info("状态转换: %s -> %s", self._current_state, target)
        self._current_state = target
        if target == GameState.QUIT:
            self.running = False
        else:
            self._enter_state(target)

    def _enter_state(self, state_id: GameState) -> None:
        """进入状态，处理自动转换"""
        next_state = self._states[state_id].enter()
        if next_state is not None and next_state != state_id:
            self._do_transition(next_state)

    def quit(self) -> None:
        """退出状态机"""
        self.running = False
