"""音乐管理器 - 管理背景音乐播放和切换"""

from __future__ import annotations

import logging
import os

import pygame

from config import SOUNDS_DIR

logger = logging.getLogger(__name__)


class AudioManager:
    """管理背景音乐（BGM）的加载、播放和切换

    使用方式:
        audio = AudioManager()
        audio.play_bgm("菜单音乐.ogg")
        audio.play_bgm("游戏音乐.ogg", crossfade=1.0)
        audio.stop_bgm()
    """

    def __init__(self) -> None:
        self._current: str | None = None

    def play_bgm(self, sound_file: str, volume: float = 0.5) -> None:
        """播放背景音乐（循环）

        参数:
            sound_file: 音频文件名（相对于 sounds 目录）
            volume: 音量（0.0 ~ 1.0），默认 0.5
        """
        full_path = os.path.join(SOUNDS_DIR, sound_file)

        if self._current == sound_file:
            return

        if not os.path.exists(full_path):
            logger.warning("音乐文件不存在: %s", full_path)
            return

        try:
            pygame.mixer.music.load(full_path)
            pygame.mixer.music.set_volume(volume)
            pygame.mixer.music.play(-1)
            self._current = sound_file
            logger.info("播放背景音乐: %s", sound_file)
        except pygame.error as e:
            logger.warning("音乐播放失败 %s: %s", sound_file, e)

    def stop_bgm(self) -> None:
        """停止背景音乐"""
        pygame.mixer.music.stop()
        self._current = None

    def set_volume(self, volume: float) -> None:
        """设置背景音乐音量

        参数:
            volume: 音量（0.0 ~ 1.0）
        """
        pygame.mixer.music.set_volume(max(0.0, min(1.0, volume)))

    @staticmethod
    def init() -> None:
        """初始化 pygame.mixer"""
        pygame.mixer.init()
