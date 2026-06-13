"""音乐管理器 - 管理背景音乐和音效的播放和切换"""

from __future__ import annotations

import logging
import os

import pygame

from config import SOUNDS_DIR

logger = logging.getLogger(__name__)


class AudioManager:
    """管理背景音乐（BGM）和音效（SFX）的加载与播放

    使用方式:
        audio = AudioManager()
        audio.play_bgm("菜单音乐.wav")
        audio.play_sfx("音效/接到食材.wav")
        audio.stop_bgm()
    """

    def __init__(self) -> None:
        self._current: str | None = None
        self._sfx_cache: dict[str, pygame.mixer.Sound] = {}
        self._master_volume: float = 0.5
        self._bgm_base_volume: float = 0.5

    def _load_sfx(self, sound_file: str) -> pygame.mixer.Sound | None:
        if sound_file in self._sfx_cache:
            return self._sfx_cache[sound_file]
        full_path = os.path.join(SOUNDS_DIR, sound_file)
        if not os.path.exists(full_path):
            logger.warning("音效文件不存在: %s", full_path)
            return None
        try:
            sfx = pygame.mixer.Sound(full_path)
            self._sfx_cache[sound_file] = sfx
            return sfx
        except pygame.error as e:
            logger.warning("音效加载失败 %s: %s", sound_file, e)
            return None

    def preload_sfx(self, *sound_files: str) -> None:
        for f in sound_files:
            self._load_sfx(f)

    def play_sfx(self, sound_file: str, volume: float = 0.7) -> None:
        sfx = self._load_sfx(sound_file)
        if sfx:
            final_volume = volume * self._master_volume
            sfx.set_volume(max(0.0, min(1.0, final_volume)))
            sfx.play()

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
            self._bgm_base_volume = volume
            pygame.mixer.music.set_volume(volume * self._master_volume)
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
        """设置背景音乐音量"""
        pygame.mixer.music.set_volume(max(0.0, min(1.0, volume * self._master_volume)))

    def get_master_volume(self) -> float:
        """获取全局音量 (0.0 ~ 1.0)"""
        return self._master_volume

    def set_master_volume(self, volume: float) -> None:
        """设置全局音量 (0.0 ~ 1.0)，同时生效于BGM和SFX"""
        self._master_volume = max(0.0, min(1.0, volume))
        if self._current is not None:
            pygame.mixer.music.set_volume(self._bgm_base_volume * self._master_volume)

    @staticmethod
    def init() -> None:
        """初始化 pygame.mixer"""
        pygame.mixer.init()
        pygame.mixer.set_num_channels(16)
