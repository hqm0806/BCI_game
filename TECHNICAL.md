# 疯狂奶茶杯 (Crazy Milk Tea Cup) — 技术文档

> 版本 1.0 | 2026-06 | 基于脑机接口与多模态交互的专注力训练游戏

---

## 目录

1. [项目概述](#1-项目概述)
2. [技术栈](#2-技术栈)
3. [系统架构](#3-系统架构)
4. [模块详解](#4-模块详解)
   - [4.1 核心框架 (core/)](#41-核心框架-core)
   - [4.2 BCI 接口 (bci/)](#42-bci-接口-bci)
   - [4.3 游戏引擎 (game/)](#43-游戏引擎-game)
   - [4.4 菜单系统 (menu/)](#44-菜单系统-menu)
   - [4.5 数据管理 (data/)](#45-数据管理-data)
   - [4.6 入口与配置](#46-入口与配置)
5. [数据流](#5-数据流)
6. [核心算法](#6-核心算法)
7. [通信协议](#7-通信协议)
8. [配置参考](#8-配置参考)
9. [运行与打包](#9-运行与打包)
10. [目录结构](#10-目录结构)

---

## 1. 项目概述

**疯狂奶茶杯** 是一款多模态脑机接口 (BCI) 专注力训练游戏。玩家使用可穿戴脑电头环，通过专注力控制食材下落速度、头动偏角控制奶茶杯位置，在 15 分钟内完成 36 杯奶茶的制作。系统通过实时自适应难度调节、方差驱动的冰块干扰、防伪迹仲裁等机制，为 ADHD 儿童及普通用户提供高趣味性的居家神经反馈训练方案。

**关键特性**:
- TCP 实时通信 HybridBCI 科创平台，获取专注力/头动/陀螺仪数据
- 多级信号滤波管线（死区 → 指数平滑 → 灵敏度映射）
- 热身归一化 + 方差驱动的动态难度自适应
- 陀螺仪-专注力双阈值防作弊仲裁
- 4 级累进式等级系统，3 种游戏模式（常规/记忆/键盘）
- JSON 持久化存档，PyInstaller 独立打包

---

## 2. 技术栈

| 类别 | 技术 | 用途 |
|------|------|------|
| 语言 | Python 3.8+ | 主开发语言 |
| 游戏引擎 | Pygame 2.0+ | 渲染、输入、音频、碰撞检测 |
| 科学计算 | NumPy 1.20+ | 浮点运算辅助 |
| GUI (备选) | PyQt5 5.15+ | bci_cup_control.py 独立 Qt 客户端 |
| 网络通信 | Python stdlib `socket` | TCP 原生 Socket |
| 协议解析 | `struct`, `json` | 大端长度前缀 + JSON 载荷 |
| 打包 | PyInstaller | 生成独立 .exe |
| 测试 | pytest, ruff | 单元测试、代码规范 |
| 字体 | ZCOOLKuaiLe-Regular.ttf | 卡通中文 UI 字体 |

---

## 3. 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        main.py (入口)                           │
│                    StateMachine (状态机调度)                     │
├─────────────────────────────────────────────────────────────────┤
│  menu/                     game/                  bci/          │
│  ┌────────────┐   ┌──────────────────┐   ┌────────────────┐   │
│  │ Splash     │   │ GameSession       │   │ BCIDataReader  │   │
│  │ Login      │   │  ├ Cup            │   │  ├ TCP connect  │   │
│  │ MainMenu   │   │  ├ Ingredient     │   │  ├ IPC parse    │   │
│  │ Settings   │   │  ├ Particle       │   │  └ sliding win  │   │
│  │ Summary    │   │  ├ IngredientMgr  │   ├────────────────┤   │
│  │ History    │   │  ├ CupManager     │   │ filter.py      │   │
│  └────────────┘   │  ├ ScoreManager   │   │  ├ DeadZone     │   │
│                    │  ├ HUD            │   │  ├ ExpSmooth    │   │
│  data/             │  └ MemorySession  │   │  ├ SensCurve    │   │
│  ┌────────────┐   └──────────────────┘   │  ├ Attn→Speed   │   │
│  │ Profile    │                           │  └ Attn→Multi   │   │
│  │ Recipes    │   core/                   └────────────────┘   │
│  │ MemoryRecp │   ┌────────────────┐                           │
│  │ ScoreMgr   │   │ StateMachine   │   config.py              │
│  └────────────┘   │ AudioManager   │   (全局参数)              │
│                    └────────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                     TCP :8000 (127.0.0.1)
                              │
                 ┌────────────▼────────────┐
                 │   HybridBCI 科创平台     │
                 │   ├ attention 算法       │
                 │   └ gyroscope 焦点算法   │
                 └─────────────────────────┘
```

### 状态流转

```
SPLASH → LOGIN → MENU ⇄ SETTINGS
                │
                ▼
          TRANSITION
                │
                ▼
           GAME / GAME_MEMORY
                │
                ▼
         (Summary 结算)
                │
                ▼
              MENU  →  QUIT
```

- `StateMachine`（`core/state_machine.py`）为通用状态机，各状态实现 `enter()` / `handle_event()` / `update()` / `exit()`
- `enter()` 可返回下一个 `GameState` 触发自动转换（适用于阻塞型界面如启动动画）

---

## 4. 模块详解

### 4.1 核心框架 (core/)

#### 4.1.1 StateMachine (`core/state_machine.py`)

```
GameState (Enum)
├── SPLASH / LOGIN / MENU / SETTINGS
├── TRANSITION / GAME / GAME_MEMORY
└── QUIT

State (ABC)
├── enter()       → GameState | None    阻塞型界面返回下一状态
├── handle_event(event) → GameState|None
├── update()
└── exit()

StateMachine
├── register(state_id, state)           注册状态实例
├── start(initial_state)                启动
├── transition_to(next_state)           请求转换
├── process_events()                    每帧处理待转换
├── update()                            委托当前状态 update()
└── handle_event(event)                 委托当前状态处理
```

#### 4.1.2 AudioManager (`core/audio_manager.py`)

- BGM: `pygame.mixer.music` 管理，支持循环播放和跨屏 crossfade
- SFX: 惰性加载缓存 (`dict[str, pygame.mixer.Sound]`)，16 个混音通道
- 10+ 音效事件：接食材、碰撞、升级、秘方触发 等

```python
audio = AudioManager()
audio.play_bgm("菜单音乐.wav", volume=0.5)
audio.play_sfx("音效/接到食材.wav", volume=0.7)
audio.crossfade_bgm("游戏音乐.wav", duration=1.0)
```

---

### 4.2 BCI 接口 (bci/)

#### 4.2.1 BCIDataReader (`bci/data_reader.py`)

TCP 客户端，连接 HybridBCI 平台并接收实时数据。

**连接流程**:
1. 建立 TCP Socket → `127.0.0.1:8000`（可从 `bci_config.json` 覆盖）
2. `setsockopt(SO_KEEPALIVE, 1)`，设为非阻塞 (`settimeout(0)`)
3. 发送就绪消息: `{"type": "ready", "client": "crazy_milk_tea_cup"}`
4. 启动陀螺仪焦点算法: `{"msg": "ipc_algorithm_start_test", "algorithm_name": "gyroscope", "algorithm_args": {"left":0, "top":0, "width":1280, "height":720, "sensitivityX":8, "sensitivityY":8}}`

**数据读取**:
```python
def read_data() -> tuple:
    # 返回 (attention, focus_x, focus_y, gyro_x, gyro_y, gyro_z)
    # 每帧批量消费缓冲区，仅保留最新值
    # 断线检测: 2s 无数据 → connected = False
```

**关键字段**:

| 字段 | 类型 | 范围 | 说明 |
|------|------|------|------|
| `attention` | int | 0–100 | 专注力指数 |
| `focus_x` | float | 0–1280 | 焦点映射 X 坐标 |
| `focus_y` | float | 0–720 | 焦点映射 Y 坐标 |
| `gyroscope_x/y/z` | float | deg | 三轴陀螺仪角度 |

**3 秒滑动窗口**: `_attention_history` 维护 `(timestamp, value)` 列表，`get_rolling_attention()` 实时返回近 3 秒均值。

#### 4.2.2 信号滤波器 (`bci/filter.py`)

| 类 | 公式/逻辑 | 参数 | 用途 |
|----|-----------|------|------|
| `DeadZoneFilter` | `abs(x) < threshold → 0` | threshold=5 | 消除微小头动抖动 |
| `ExponentialSmoothing` | `y_n = α·x_n + (1-α)·y_{n-1}` | α=0.3 | 平滑头动信号 |
| `SensitivityCurve` | `y = sign(x) · base · |x|^exp` | base=1.0, exp=1.5 | 非线性映射，压缩小信号 |
| `AttentionToSpeedCurve` | 3 段线性 (见[算法](#6-核心算法)) | Vmin=2.0, Vmax=5.0, baseline=60 | 专注力 → 食材速度 |
| `AttentionMappingCurve` | 3 段分段函数 | low=30, high=70, max=1.5 | 专注力 → 收益倍率 |

**滤波管线**（头动信号）:
```
raw_gyro → DeadZoneFilter → ExponentialSmoothing → SensitivityCurve → cup_x
```

#### 4.2.3 配置管理 (`bci/config.py`)
```python
def load_bci_config() -> dict:
    # 读取 bci_config.json，返回 {"server_ip": "...", "server_port": ...}
    # 支持 PyInstaller 打包路径 (sys._MEIPASS)
```

---

### 4.3 游戏引擎 (game/)

#### 4.3.1 GameSession (`game/session.py`, 1279 行)

管理单局游戏完整生命周期。核心入口类。

**初始化参数**:
```python
GameSession(
    screen,           # pygame.Surface
    clock,            # pygame.time.Clock
    game_mode="bci",  # "regular" | "bci"
    control_mode="bci",# "bci" | "keyboard" | "bci_failed"
    profile=None,     # PlayerProfile
    audio=None,       # AudioManager
)
```

**内部组合**:
- `IngredientManager` — 食材生成、车道管理
- `CupManager` — 单杯生命周期（20s 计时、结算）
- `ScoreManager` — 得分追踪、秘方计数
- `BCIDataReader` — BCI 数据源

**阶段状态机**:
```
warmup_intro (3s 渐入) → warmup (180s 热身)
→ warmup_summary (5s 归一化展示) → formal (36 杯)
```

**热身阶段关键逻辑**:
1. 采集全程注意力数据 → `warmup_all_attn`
2. 取最后 30 秒数据 → 计算 `lower = max(μ-10, 0)`, `upper = min(μ+10, 100)`
3. 归一化: `norm = clamp((raw - lower) / (upper - lower) * 99 + 1, 1, 100)`

**正式阶段关键逻辑** (每帧):
1. 读取 BCI 数据 → 滤波 → 计算速度/位置
2. 计算注意力方差 → 更新冰块概率
3. `IngredientManager.update()` → 生成食材
4. 碰撞检测 → `ScoreManager` / `CupManager`
5. 防伪迹检测 (陀螺仪静止 + 高专注力)
6. 低专注力保护 (专注力 <15 持续 5s → 冻结)
7. 渲染 HUD + 精灵

**结算逻辑** (每杯结束):
```python
# 无必接食材 → cup_money = 0
# 有必接食材 → cup_money = Σ ingredient_points
# 秘方触发 → cup_money *= 2
# 专注力系数 → cup_money *= attention_coefficient(normalized_attn)
```

#### 4.3.2 Sprites (`game/sprites.py`)

| 类 | 父类 | 说明 |
|----|------|------|
| `Cup` | `pygame.sprite.Sprite` | 奶茶杯，3 级图片切换，yaw/键盘双控，倾斜动画，弹跳特效 |
| `Ingredient` | `pygame.sprite.Sprite` | 下落食材，浮动动画 (±5px sin)，必接标记 (红框)，粒子拖尾 |
| `Particle` | `pygame.sprite.Sprite` | 爆炸粒子，重力模拟，alpha 衰减 |
| `CatchEffect` | `pygame.sprite.Sprite` | 接住特效，飞向杯子 + 缩小 |
| `MissEffect` | `pygame.sprite.Sprite` | 错过特效，渐变消失 |

**Cup 控制**:
```python
# 键盘模式:
cup.rect.x += (right - left) * cup.speed

# BCI 模式:
# 头动偏角经滤波管线后映射为 focus_x
cup.rect.centerx = int(focus_x)
cup.rect.centerx = clamp(cup.rect.centerx, CUP_WIDTH//2, SCREEN_WIDTH - CUP_WIDTH//2)
```

**Ingredient 生成**:
```python
Ingredient(ing_type, is_required, speed, allowed_lanes)
# lane = random.choice(allowed_lanes)  →  x = lane * LANE_WIDTH + LANE_WIDTH//2
# y = -INGREDIENT_SIZE (屏幕顶部外)
# speed 由专注力映射决定
```

#### 4.3.3 IngredientManager (`game/ingredient_manager.py`)

```python
class IngredientManager:
    # 配置
    set_tier(tier)            # 按等级设置 available/required 食材列表
    set_current_speed(speed)  # 当前食材下落速度
    set_spawn_interval(t)     # 生成间隔 (秒)
    set_ice_probability(p)    # 冰块替入概率 (0.0-1.0)
    set_required_probability(p) # 必接标记概率

    # 生成
    should_spawn() → bool     # 是否到达生成时间
    spawn_ingredient() → Ingredient
    spawn_secret_recipe() → Ingredient

    # 车道管理 (仅检查顶部 35% 屏幕空间)
    _free_lanes(group) → list[int]  # 可用的非占用车道
```

**车道系统**:
- 6 条垂直车道 (1280 / 6 = 213px/道)
- 中间 2 条 (index 2, 3) 合并为安全区，不掉落食材
- 有效车道: [0, 1, 4, 5]
- 每条有效车道同时最多 1 个食材 (上方 35% 区域)

#### 4.3.4 CupManager (`game/cup_manager.py`)

```python
class CupManager:
    start_new_cup()                     # 开始新一杯
    add_catch(type, is_required) → int  # 记录接住，返回分值
    settle_cup() → int                  # 结算，返回本杯金额
    check_timeout() → bool              # 是否超时 (20s)

    # 状态
    cup_number: int          # 当前杯号 (1-36)
    cup_money_history: list  # 每杯营收
    secret_recipe_count: int # 累计秘方数
    total_money: int         # 累计营收
```

**DifficultyAdapter** (内嵌):
```python
class DifficultyAdapter:
    # 基于最近 30 秒专注力滚动均值更新难度基线
    update(attn_window: deque) → baseline
```

#### 4.3.5 MemorySession (`game/memory_mode.py`, 500 行)

独立的记忆模式，回合制规则。

**阶段流程**:
```
rules(3.5s) → memorize(2s) → play(15s) → result(1.5s) → rest(2s) → 下一轮
```

**难度系统**:
- 4 个等级 (2/3/4/5 种食材)，初始等级 2
- 35 个预定义配方 (来自 `data/memory_recipes.py`)
- 3 连成功 → 升 1 级，2 连失败 → 降 1 级
- 目标/干扰食材比例 1:2
- 必须按序接取，顺序错误计为失败

**车道**: 独立 5 车道系统 (256px/道)

#### 4.3.6 HUD (`game/hud.py`)

```python
def draw_hud(
    screen, score_manager, mode_name, cup_manager,
    game_start_time, font, hint_font, recipe_font,
    attention, bci_mode, free_combine, recipe_result,
    creative_ingredients, attention_curve, bci_connected,
    focus_above_seconds, raw_gyro_x/y/z,
    platform_focus_x/y, cup_x, cup_y,
    rolling_attention, attn_variance, attn_mode, attn_baseline,
):
```

渲染内容:
- 顶部栏: 营收、模式名、杯号 (X/36)、等级徽章
- 底部: 倒计时进度条
- BCI 调试信息: 陀螺仪角度、焦点坐标、方差模式
- 秘方进度条 (专注力持续达标计时)
- 配方评价弹窗
- 低专注力/伪迹冻结覆盖层

---

### 4.4 菜单系统 (menu/)

| 文件 | 类 | 说明 |
|------|-----|------|
| `login.py` | `LoginScreen` | 用户名/密码输入、注册/登录、accounts.json 读写 |
| `screens/main_menu.py` | `MainMenu` | 3 按钮布局 (开始/模式/设置)，BCI 连接对话框，等级徽章 |
| `mode_selector.py` | `ModeSelector` | 发光按钮轮播 (常规/记忆/键盘)，预览弹窗 |
| `screens/game_settings.py` | 设置入口 | 游戏设置 + BCI 设置入口 |
| `screens/bci_settings.py` | `BCISettingsScreen` | IP/端口输入框、测试连接、保存配置 |
| `summary.py` | `SummaryScreen` | 结算界面 (收入、秘方数、等级、注意力波形图、评语) |
| `history.py` | `HistoryScreen` | 游戏历史列表 (左) + 趋势折线图 (右) |
| `components.py` | `MenuItem`, `Badge` | UI 组件 (按钮、徽章、悬停特效、点击粒子) |
| `bci_button.py` | `GlowButton` | 脉冲发光按钮 |
| `particles.py` | — | 主菜单背景浮动食材+蒸汽粒子 |
| `text_input.py` | `TextInputBox` | 可复用文本输入框 |

---

### 4.5 数据管理 (data/)

#### 4.5.1 PlayerProfile (`data/player_profile.py`)

```python
@dataclass
class PlayerProfile:
    level: int = 1
    cumulative_revenue: int = 0
    total_games: int = 0
    games_history: list[dict] = []

    # 类方法
    load_for_user(username: str) → PlayerProfile  # 从 profiles/{username}.json

    # 实例方法
    save()                                         # 持久化 (保留最近 20 条)
    add_game_result(revenue, mode, cups, secrets,
                    avg_attention, focus_samples) → int  # 返回新等级(升级时)
    remove_game(index) / clear_history()
```

**等级阈值**:
```
LEVEL_THRESHOLDS = [0, 80, 250, 600]
累计营收 >= 80  → Lv.2
累计营收 >= 250 → Lv.3
累计营收 >= 600 → Lv.4
```

**存档格式** (`profiles/{username}.json`):
```json
{
  "level": 3,
  "cumulative_revenue": 480,
  "total_games": 5,
  "games_history": [
    {
      "mode": "bci",
      "revenue": 120,
      "cups": 36,
      "secrets": 5,
      "avg_attention": 61.5,
      "duration": 780.0,
      "date": "2026-06-04 15:30",
      "focus_samples": [55,62,58,...]
    }
  ]
}
```

#### 4.5.2 ScoreManager (`data/score_manager.py`)

```python
class ScoreManager:
    add_score(ingredient_type: str, is_required: bool) → int
    add_cup_money(amount: int)
    get_summary() → dict
    get_level() → int                          # 基于累计营收
```

#### 4.5.3 Recipes (`data/recipes.py`)

30+ 预定义创意配方，评分 0-100:

```python
CREATIVE_RECIPES = {
    frozenset(["红茶","牛奶","珍珠"]): {"name":"珍珠奶茶·祖师爷", "score":95},
    ...
}

def evaluate_recipe(ingredients: set) → dict:
    # 匹配预定义配方 → 返回 {name, score, rating, description}
    # 未知组合 → 启发式评分 (茶底+奶底+小料 = 80+, 单食材 = 30)
```

**评级**:
```
0 → 黑暗料理 | 15 → 勉强能喝 | 30 → 普通奶茶
45 → 好喝推荐 | 60 → 网红爆款 | 75 → 匠心之作
90 → 米其林一星 | 100 → 米其林三星
```

#### 4.5.4 MemoryRecipes (`data/memory_recipes.py`)

35 个记忆模式配方，按食材数分组:
- 2 种: 11 个 | 3 种: 10 个 | 4 种: 8 个 | 5 种: 6 个

---

### 4.6 入口与配置

#### main.py
```python
def main():
    pygame.init()
    screen = pygame.display.set_mode((1280, 720))
    clock = pygame.time.Clock()
    audio = AudioManager()
    sm = StateMachine()
    sm.register(GameState.SPLASH, SplashState(screen, clock))
    sm.register(GameState.LOGIN, LoginState(screen, clock, audio))
    # ...注册所有状态
    sm.start(GameState.SPLASH)
    while sm.running:
        sm.process_events()
        sm.update()
        pygame.display.flip()
        clock.tick(60)
```

#### config.py (关键参数)

| 分类 | 参数 | 默认值 | 说明 |
|------|------|--------|------|
| 屏幕 | `SCREEN_WIDTH/HEIGHT` | 1280×720 | 窗口尺寸 |
| 帧率 | `FPS` | 60 | 游戏帧率 |
| 杯子 | `CUP_SPEED` | 5 | 键盘移动速度 (px/帧) |
| 食材 | `INGREDIENT_SPEED` | 3.5 | 默认下落速度 |
| 一杯制 | `CUP_DURATION` | 20 | 每杯时限 (秒) |
| 一杯制 | `TOTAL_CUPS` | 36 | 总局数 |
| 热身 | `WARMUP_DURATION` | 180 | 热身时长 (秒) |
| 防伪迹 | `ARTIFACT_STILL_THRESHOLD` | 0.5 | 静止判定 (°) |
| 防伪迹 | `ARTIFACT_STILL_DURATION` | 5.0 | 静止持续时间 |
| 防伪迹 | `ARTIFACT_ATTENTION_THRESHOLD` | 80 | 专注力阈值 |
| 秘方 | `SECRET_RECIPE_SUSTAIN` | 4 | 触发所需持续秒数 |
| 秘方 | `SECRET_RECIPE_OFFSET` | 5 | 阈值偏移量 |
| 速度 | `FORMAL_SPEED_MIN/MAX` | 2.0 / 4.5 | 正式速度范围 |
| 速度 | `WARMUP_SPEED_MIN/MAX` | 1.5 / 6.0 | 热身速度范围 |

**食材配置**:
```python
INGREDIENT_TIERS = {
    1: {"available": ["珍珠","椰果","牛奶","红茶","绿茶"],
        "required":  ["牛奶","红茶","绿茶"]},
    2: {"available": [..., "芋圆","脆啵啵","芒果","椰奶"],
        "required":  [..., "芒果","椰奶"]},
    3: {"available": [..., "草莓","芋泥","燕麦奶","咖啡"],
        "required":  [..., "燕麦奶","咖啡"]},
    4: {"available": [..., "特调稀奶油顶","米酿","咸芝士奶盖","茉莉花茶"],
        "required":  [..., "茉莉花茶"]},
}

INGREDIENT_POINTS = {
    "珍珠":1, "椰果":1, "牛奶":2, "红茶":2, "绿茶":2,
    "芋圆":2, "脆啵啵":2, "芒果":3, "椰奶":3, "草莓":3,
    "芋泥":3, "燕麦奶":4, "咖啡":4, "特调稀奶油顶":5,
    "米酿":5, "咸芝士奶盖":6, "茉莉花茶":6,
    "秘方":0, "冰块":0,
}
```

---

## 5. 数据流

```
[HybridBCI 平台]
    │ TCP :8000, 4B len + JSON
    ▼
BCIDataReader._recv_data()
    │ 每帧批量消费，latest-wins
    ▼
┌───────────────────────────────────────────────────┐
│ GameSession.run() 60 FPS 主循环                    │
│                                                    │
│  1. read_data() → (attn, fx, fy, gx, gy, gz)      │
│  2. 滤波管线:                                      │
│     attn → rolling_avg(3s) → normalize → speed    │
│     gx/gy/gz → deadzone → smooth → sensitivity    │
│  3. 防伪迹检测:                                    │
│     gyro_still>5s & attn>80 → freeze 5s           │
│  4. 低专注力保护:                                  │
│     attn<15 for 5s → pause                         │
│  5. 方差计算:                                      │
│     60-frame window → variance → ice_prob          │
│  6. IngredientManager.update() → 生成食材         │
│  7. 碰撞检测 → ScoreManager + CupManager          │
│  8. 杯超时检测 → settle_cup()                      │
│  9. 渲染: background → sprites → HUD              │
└──────────────┬────────────────────────────────────┘
               │ 游戏结束
               ▼
SummaryScreen → PlayerProfile.add_game_result()
                    │
                    ▼
              profiles/{user}.json
```

---

## 6. 核心算法

### 6.1 专注力归一化

**目的**: 消除个体基线差异。

```
热身最后 30s 采样 → μ (均值)
lower = max(μ - 10, 0)
upper = min(μ + 10, 100)
width = max(upper - lower, 10)

正式阶段:
norm = clamp((raw - lower) / width * 99 + 1, 1, 100)
```

### 6.2 注意力 → 速度映射 (AttentionToSpeedCurve)

3 段线性，以校准基线为中心:

```
attn ∈ [0,            baseline-20]   → speed = Vmax (最快)
attn ∈ [baseline-20,  baseline+20]   → speed = Vmax → Vmin (线性)
attn ∈ [baseline+20,  100]           → speed = Vmin (最慢)

Vmin = 2.0 px/frame, Vmax = 4.5 px/frame (正式)
Vmin = 1.5 px/frame, Vmax = 6.0 px/frame (热身, 故意拉大感知度)
```

### 6.3 方差驱动的冰块概率

以每杯为粒度，60 帧窗口追踪注意力方差:

```
attn_offsets = [|attn_i - cup_baseline| for last 60 frames]
variance = mean(attn_offsets)

variance < 50   → ice_prob = 20% (低干扰)
50 ≤ var < 150  → ice_prob = 50% (中干扰)
var ≥ 150       → ice_prob = 80% (高干扰)
var > 150 & attn < 20 → ice_prob = 100% (冰雪风暴)
```

每杯的 baseline 由上一杯的平均注意力决定。

### 6.4 防伪迹仲裁

三条件 AND 判定:

```
1. max(|gx - prev_gx|, |gy - prev_gy|, |gz - prev_gz|) < 0.5°  (头部静止)
2. 持续时间 > 5 秒
3. attention > 80
→ freeze 5s + "请放松面部肌肉" 文字覆盖
```

### 6.5 低专注力保护

```
attention ≤ 15 持续 5 秒 → 画面冻结 (alpha 渐变为 0.85)
attention > 15 持续 5 秒 → 解冻 (alpha 渐变为 0)
```

### 6.6 秘方触发

```
BCI 模式: attention > min(baseline + 5, 88) 持续 4 秒 → 触发
非 BCI 模式: 每 N 杯触发一次 (bci模式 N=3, 常规 N=1)
```

### 6.7 专注力收益系数

```python
def get_attention_coefficient(norm_attn):
    if norm_attn >= 80:     return 1.0
    elif norm_attn >= 40:   return 0.5 + 0.5 * (norm_attn - 40) / 40
    else:                   return 0.5
```

---

## 7. 通信协议

### HybridBCI 平台 IPC 协议

**传输层**: TCP (默认 `127.0.0.1:8000`)

**帧格式**:
```
┌────────────────┬──────────────────────────┐
│  4 bytes (BE)  │  N bytes                  │
│  payload_len   │  UTF-8 JSON payload       │
└────────────────┴──────────────────────────┘
```

**客户端 → 平台**:

就绪消息:
```json
{"type": "ready", "client": "crazy_milk_tea_cup"}
```

启动陀螺仪算法:
```json
{
  "msg": "ipc_algorithm_start_test",
  "algorithm_name": "gyroscope",
  "algorithm_args": {
    "left": 0, "top": 0,
    "width": 1280, "height": 720,
    "sensitivityX": 8, "sensitivityY": 8
  }
}
```

停止算法:
```json
{"msg": "ipc_algorithm_stop_test"}
```

**平台 → 客户端**:

专注力数据:
```json
{
  "msg": "ipc_algorithm_test",
  "algorithm_name": "attention",
  "result_args": {"data": 65}
}
```

陀螺仪焦点数据:
```json
{
  "msg": "ipc_algorithm_test",
  "algorithm_name": "gyroscope",
  "result_args": {
    "data": {
      "focus_x": 640.0, "focus_y": 550.0,
      "gyroscope_x": -2.3, "gyroscope_y": 1.5, "gyroscope_z": 0.8
    }
  }
}
```

**解析实现**:
```python
# 循环缓冲区粘包/半包处理
while len(recv_buffer) >= 4:
    payload_len = struct.unpack(">I", recv_buffer[:4])[0]
    if payload_len > 1048576:  # 安全检查: >1MB 视为异常
        disconnect()
    if len(recv_buffer) < 4 + payload_len:
        break  # 半包，等待更多数据
    payload = recv_buffer[4:4+payload_len]
    recv_buffer = recv_buffer[4+payload_len:]
    return json.loads(payload)
```

---

## 8. 配置参考

### bci_config.json
```json
{
  "server_ip": "127.0.0.1",
  "server_port": 8000
}
```

### accounts.json
```json
{
  "username": "password"
}
```

### 游戏模式配置 (config.py)
```python
GAME_MODES = {
    "regular": {
        "name": "常规模式",
        "has_required": True,       # 有必接食材
        "free_combine": False,      # 固定配方
        "bci_mode": False,
        "ingredient_speed": 3,
        "spawn_interval": 1000,     # ms
        "total_cups": 36,
        "secret_recipe_cup_interval": 1,
    },
    "bci": {
        "name": "脑机接口模式",
        "has_required": False,
        "free_combine": True,       # 自由搭配 + 配方评分
        "bci_mode": True,
        "ingredient_speed": 3,
        "spawn_interval": 1200,
        "total_cups": 36,
        "secret_recipe_cup_interval": 3,
    },
}

CONTROL_MODES = [
    {"key": "bci_normal", "name": "常规模式", "desc": "BCI头环控制杯子"},
    {"key": "memory",     "name": "记忆模式", "desc": "记忆食材序列"},
    {"key": "keyboard",   "name": "键盘模式", "desc": "键盘控制杯子移动"},
]
```

---

## 9. 运行与打包

### 开发环境
```bash
pip install -r requirements.txt
python main.py
```

### 独立工具
```bash
python calibration.py         # 注意力方差校准工具
python test_bci_connection.py # BCI 连接测试
python bci_cup_control.py     # PyQt5 BCI 控制客户端 (备选)
```

### 单元测试
```bash
pytest tests/ -v
# tests/test_score_manager.py  — ScoreManager 单元测试
# tests/test_recipes.py        — 配方评分单元测试
# tests/test_filters.py        — 滤波器单元测试
```

### 打包为 exe
```bash
pyinstaller CrazyMilkTea.spec
# 输出: dist/CrazyMilkTea.exe (~65MB)
# 自动包含 assets/ 和 JSON 配置文件
```

### 代码规范
```bash
ruff check .       # 代码检查
ruff format .      # 代码格式化
```

---

## 10. 目录结构

```
BCI_game/
├── main.py                    # 入口
├── config.py                  # 全局参数 (395 行)
├── calibration.py             # 注意力方差校准工具
├── test_bci_connection.py     # BCI 连接测试
├── bci_cup_control.py         # PyQt5 BCI 替代客户端
├── requirements.txt           # Python 依赖
├── pyproject.toml             # Ruff 配置
├── CrazyMilkTea.spec          # PyInstaller 配置
├── accounts.json              # 用户密码字典
├── player_profile.json        # 默认存档
├── bci_config.json            # BCI 服务器地址配置
│
├── core/
│   ├── state_machine.py       # 通用状态机 (133 行)
│   └── audio_manager.py       # BGM/SFX 管理 (92 行)
│
├── bci/
│   ├── data_reader.py         # TCP 客户端 + 协议解析 (234 行)
│   ├── filter.py              # 信号滤波器 (5 个类, 215 行)
│   └── config.py              # BCI 配置加载
│
├── game/
│   ├── session.py             # 游戏主循环 (1279 行)
│   ├── sprites.py             # 精灵类 (Cup, Ingredient, Particle 等, 349 行)
│   ├── ingredient_manager.py  # 食材生成管理 (111 行)
│   ├── cup_manager.py         # 单杯生命周期 (172 行)
│   ├── hud.py                 # HUD 渲染 (184 行)
│   ├── memory_mode.py         # 记忆模式 (500 行)
│   └── font_utils.py          # 中文字体加载
│
├── menu/
│   ├── login.py               # 登录/注册
│   ├── splash.py              # 启动动画
│   ├── components.py          # UI 组件 (MenuItem, Badge)
│   ├── mode_selector.py       # 模式选择器
│   ├── bci_button.py          # 发光按钮
│   ├── particles.py           # 背景特效
│   ├── history.py             # 历史记录界面
│   ├── summary.py             # 结算界面
│   ├── text_input.py          # 文本输入框
│   └── screens/
│       ├── main_menu.py       # 主菜单
│       ├── game_settings.py   # 游戏设置
│       └── bci_settings.py    # BCI 设置
│
├── data/
│   ├── player_profile.py      # 玩家存档 (134 行)
│   ├── score_manager.py       # 得分管理
│   ├── recipes.py             # 创意配方库 (346 行)
│   ├── memory_recipes.py      # 记忆模式配方
│   └── ingredient_config.py   # 食材配置 (遗留)
│
├── tests/
│   ├── test_score_manager.py
│   ├── test_recipes.py
│   └── test_filters.py
│
├── utils/
│   └── logging_config.py      # 日志配置
│
├── assets/
│   ├── images/
│   │   ├── ingredients/       # 19 种食材 PNG
│   │   ├── cups/              # 3 级杯子 PNG
│   │   ├── badges/            # 4 级徽章 PNG
│   │   ├── backgrounds/       # 背景图
│   │   └── other/             # 其他 UI 素材
│   ├── sounds/
│   │   ├── 音效/              # SFX
│   │   └── *.wav              # BGM
│   └── fonts/
│       └── ZCOOLKuaiLe-Regular.ttf
│
└── profiles/                  # 用户存档目录 (运行时生成)
    └── {username}.json
```
