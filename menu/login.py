"""
登录/注册界面 — 账号系统入口
"""

from __future__ import annotations

import json
import os

import pygame

from config import IMAGES_DIR, SCREEN_HEIGHT, SCREEN_WIDTH
from game.font_utils import load_chinese_font

ACCOUNTS_FILE = "accounts.json"


def _load_accounts() -> dict:
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_accounts(accounts: dict) -> None:
    os.makedirs("profiles", exist_ok=True)
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(accounts, f, ensure_ascii=False)


class LoginScreen:
    """登录/注册界面"""

    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.clock = pygame.time.Clock()

        self.title_font = load_chinese_font(56)
        self.font = load_chinese_font(32)
        self.hint_font = load_chinese_font(22)

        self._result: str | None = None
        self._username = ""
        self._password = ""
        self._active_field = "username"
        self._message = ""
        self._message_color = (200, 200, 200)
        self._accounts = _load_accounts()

        self._bg = self._load_bg()

        self._input_x = SCREEN_WIDTH // 2 - 160
        self._label_x = SCREEN_WIDTH // 2 - 310
        self._input_y_user = SCREEN_HEIGHT // 2 - 50
        self._input_y_pass = SCREEN_HEIGHT // 2 + 30

        self._btn_login = pygame.Rect(SCREEN_WIDTH // 2 - 190, self._input_y_pass + 70, 170, 42)
        self._btn_register = pygame.Rect(SCREEN_WIDTH // 2 + 20, self._input_y_pass + 70, 170, 42)

    def _load_bg(self) -> pygame.Surface | None:
        path = os.path.join(IMAGES_DIR, "backgrounds", "login.png")
        if os.path.exists(path):
            try:
                img = pygame.image.load(path).convert()
                return pygame.transform.scale(img, (SCREEN_WIDTH, SCREEN_HEIGHT))
            except (pygame.error, OSError):
                pass
        return None

    def run(self) -> str | None:
        while self._result is None:
            self.clock.tick(60)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return None
                if event.type == pygame.KEYDOWN:
                    self._handle_key(event)
                elif event.type == pygame.TEXTINPUT:
                    self._handle_textinput(event)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._handle_click(event.pos)

            self._draw()
            pygame.display.flip()

        return self._result

    def _handle_key(self, event: pygame.event.Event) -> None:
        if event.key == pygame.K_ESCAPE:
            self._result = "quit"
            return

        if event.key == pygame.K_TAB:
            self._active_field = "password" if self._active_field == "username" else "username"
            return

        if event.key == pygame.K_RETURN:
            self._do_login()
            return

        if event.key == pygame.K_BACKSPACE:
            if self._active_field == "username" and self._username:
                self._username = self._username[:-1]
            elif self._active_field == "password" and self._password:
                self._password = self._password[:-1]
            self._message = ""

    def _handle_textinput(self, event: pygame.event.Event) -> None:
        for ch in event.text:
            if self._active_field == "username" and len(self._username) < 16:
                self._username += ch
            elif self._active_field == "password" and len(self._password) < 16:
                self._password += ch
        self._message = ""

    def _handle_click(self, pos: tuple[int, int]) -> None:
        if self._btn_login.collidepoint(pos):
            self._do_login()
        elif self._btn_register.collidepoint(pos):
            self._do_register()
        elif self._input_x <= pos[0] <= self._input_x + 320:
            if self._input_y_user <= pos[1] <= self._input_y_user + 42:
                self._active_field = "username"
            elif self._input_y_pass <= pos[1] <= self._input_y_pass + 42:
                self._active_field = "password"

    def _do_login(self) -> None:
        user = self._username.strip()
        pwd = self._password.strip()

        if not user or not pwd:
            self._message = "请输入账号和密码"
            self._message_color = (255, 150, 100)
            return

        if user not in self._accounts:
            self._message = "账号不存在，请先注册"
            self._message_color = (255, 150, 100)
            return

        if self._accounts[user] != pwd:
            self._message = "密码错误"
            self._message_color = (255, 100, 100)
            return

        self._result = user

    def _do_register(self) -> None:
        user = self._username.strip()
        pwd = self._password.strip()

        if not user or not pwd:
            self._message = "请输入账号和密码"
            self._message_color = (255, 150, 100)
            return

        if user in self._accounts:
            self._message = "账号已存在，请直接登录"
            self._message_color = (255, 150, 100)
            return

        self._accounts[user] = pwd
        _save_accounts(self._accounts)
        self._username = ""
        self._password = ""
        self._active_field = "username"
        self._message = "注册成功，请登录"
        self._message_color = (100, 255, 100)

    def _draw(self) -> None:
        if self._bg:
            self.screen.blit(self._bg, (0, 0))
        else:
            self.screen.fill((25, 25, 45))
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        title = self.title_font.render("疯狂奶茶杯", True, (255, 220, 150))
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 180))

        sub = self.hint_font.render("登录你的账号", True, (200, 200, 220))
        self.screen.blit(sub, (SCREEN_WIDTH // 2 - sub.get_width() // 2, 250))  # 位置

        label_user = self.font.render("账号", True, (200, 200, 220))
        self.screen.blit(label_user, (self._label_x, self._input_y_user + 5))
        self._draw_input(
            self._username,
            self._input_x,
            self._input_y_user,
            320,
            42,
            self._active_field == "username",
        )

        label_pass = self.font.render("密码", True, (200, 200, 220))
        self.screen.blit(label_pass, (self._label_x, self._input_y_pass + 5))
        self._draw_input(
            "*" * len(self._password),
            self._input_x,
            self._input_y_pass,
            320,
            42,
            self._active_field == "password",
        )

        self._draw_button(self._btn_login, "登录", (100, 200, 100))
        self._draw_button(self._btn_register, "注册", (200, 160, 100))

        hint = self.hint_font.render("Tab 切换输入框 | Enter 登录", True, (150, 150, 170))
        self.screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, self._btn_login.bottom + 25))

        if self._message:
            msg = self.hint_font.render(self._message, True, self._message_color)
            self.screen.blit(msg, (SCREEN_WIDTH // 2 - msg.get_width() // 2, self._btn_login.bottom + 55))

        esc = self.hint_font.render("ESC 退出", True, (120, 120, 140))
        self.screen.blit(esc, (SCREEN_WIDTH // 2 - esc.get_width() // 2, SCREEN_HEIGHT - 40))

    def _draw_button(
        self,
        rect: pygame.Rect,
        text: str,
        color: tuple[int, int, int],
    ) -> None:
        pygame.draw.rect(self.screen, color, rect, 2, border_radius=8)
        bg = pygame.Surface((rect.width - 4, rect.height - 4), pygame.SRCALPHA)
        bg.fill((*color, 30))
        self.screen.blit(bg, (rect.x + 2, rect.y + 2))
        txt = self.font.render(text, True, color)
        self.screen.blit(txt, (rect.x + (rect.width - txt.get_width()) // 2, rect.y + 5))

    def _draw_input(
        self,
        text: str,
        x: int,
        y: int,
        w: int,
        h: int,
        active: bool,
    ) -> None:
        border = (255, 220, 150) if active else (80, 80, 110)
        pygame.draw.rect(self.screen, border, (x, y, w, h), 3, border_radius=8)
        bg = pygame.Surface((w - 6, h - 6), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 80))
        self.screen.blit(bg, (x + 3, y + 3))

        display_text = text
        if active and len(text) < 16:
            cursor = "|" if pygame.time.get_ticks() % 1000 < 500 else ""
            display_text = text + cursor

        txt = self.font.render(display_text, True, (220, 220, 240))
        self.screen.blit(txt, (x + 10, y + 6))
