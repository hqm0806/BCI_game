# 疯狂奶茶杯

基于 Pygame 的脑机接口（BCI）奶茶制作游戏。玩家通过键盘或头环（脑机接口设备）控制奶茶杯，接住从天而降的食材，完成一杯杯奶茶。通过科创平台实时获取专注力和头动数据，专注力影响食材速度和必接概率，最终累积营业额提升等级。

## 项目结构

```
BCI_gane/
├── main.py                      # 游戏主入口，状态机管理界面跳转
├── config.py                    # 全局配置（分辨率、食材属性、BCI参数、等级等）
├── requirements.txt
├── accounts.json                # 账号密码存储
├── profiles/                    # 各用户游戏存档
│
├── menu/                        # 菜单系统
│   ├── login.py                 # 登录/注册界面
│   ├── splash.py                # 启动动画
│   ├── calibration.py           # BCI 专注力校准界面
│   ├── summary.py               # 游戏结算界面（含专注力波形图）
│   ├── components.py            # 基础组件（MenuItem, Badge, ClickParticle）
│   ├── mode_selector.py         # 模式选择器（辉光粒子风格）
│   ├── bci_button.py            # 通用辉光按钮（GlowButton）
│   └── screens/
│       ├── main_menu.py         # 主菜单
│       └── game_settings.py     # 游戏设置
│
├── game/                        # 游戏核心
│   ├── session.py               # 游戏会话（一杯制主循环）
│   ├── sprites.py               # 精灵（杯子、食材、粒子、特效）
│   ├── ingredient_manager.py    # 食材生成（等级/概率/速度）
│   ├── hud.py                   # 游戏 HUD（背景板、数据面板、进度条）
│   ├── cup_manager.py           # 杯生命周期管理器
│   ├── patience_bar.py          # 耐心条（已废弃）
│   └── font_utils.py            # 中文字体加载
│
├── bci/                         # 脑机接口模块
│   ├── data_reader.py           # TCP 连接科创平台，解析焦点/注意力/陀螺仪
│   ├── filter.py                # 信号滤波器 + AttentionToSpeedCurve
│   └── config.py                # BCI 连接配置
│
├── data/                        # 数据管理
│   ├── score_manager.py         # 得分/金钱管理
│   ├── player_profile.py        # 玩家档案（等级、营业额、历史）
│   └── recipes.py               # 创意模式配方评分
│
├── core/                        # 核心框架
│   ├── state_machine.py         # 通用状态机
│   └── audio_manager.py         # 音频管理
│
├── assets/
│   ├── images/
│   │   ├── ingredients/         # 19 种食材图片
│   │   ├── cups/                # 奶茶杯1/2/3.png
│   │   ├── badges/              # badge1-4.png（4 等级徽章）
│   │   ├── backgrounds/         # 背景图片
│   │   └── other/               # 其他素材（横.png, focus_teapot.png等）
│   ├── fonts/                   # ZCOOLKuaiLe-Regular.ttf
│   └── sounds/                  # 音频文件
│
└── tests/                       # 测试用例
```

## 快速开始

```bash
pip install -r requirements.txt
python main.py
```

启动 → 登录/注册 → 主菜单 → 选择模式 →（BCI 校准）→ 游戏 → 结算

## 游戏控制

| 操作 | 方式 |
|------|------|
| ← / → | 键盘左右移动杯子 |
| ESC | 返回菜单 / 双击跳过结算 |
| 头环 | BCI 模式下头部转动控制杯子（影子式跟随焦点坐标） |
| F11 | 全屏/窗口切换 |
| 右上角 □/❐ | 点击最大化/恢复窗口 |

## 游戏机制

### 一杯制规则

- 一局共 **5 杯**，每杯最长 **15 秒**
- 杯结束时：无必接食材 → 金额 0；有必接 → 累加所有接住食材值
- 秘方翻倍：专注力 > 基线+10 持续 5 秒（非 BCI 模式每 N 杯触发一次）

### 4 级食材系统

| 等级 | 升级条件 | 选接食材 | 必接食材 |
|------|---------|---------|---------|
| Lv.1 | 默认 | 珍珠(3) 椰果(3) | 牛奶(5) 红茶(5) 绿茶(5) |
| Lv.2 | 累计 ≥ 35 | +芋圆(8) 脆啵啵(8) | +芒果(10) 椰奶(10) |
| Lv.3 | 累计 ≥ 100 | +草莓(12) 芋泥(12) | +燕麦奶(15) 咖啡(15) |
| Lv.4 | 累计 ≥ 300 | +稀奶油顶(20) 米酿(20) 咸芝士奶盖(20) | +茉莉花茶(20) |

每级保留所有前级食材，等级越高可选种类越多。

### 专注力 → 食材速度（3 段线性曲线）

```
[0, 基线-20]       → speed = 8.0  最快（不专注）
[基线-20, 基线+20]  → 8.0 → 2.0   线性减速
[基线+20, 100]     → speed = 2.0  最慢（高专注）
```

速度每秒应用到屏幕上所有食材。

### 必接概率（注意力方差调节）

| 方差 | 模式 | 必接概率 |
|------|------|---------|
| < 50 | 简单 | 70% |
| 50-150 | 中等 | 50% |
| > 150 | 困难 | 30% |

### 低专注保护

- 注意力 **≤ 5 持续 5 秒** → 游戏暂停，屏幕黑化，大字提示"请调整身心状态"
- 注意力 **≥ 10 持续 5 秒** → 恢复游戏

## 脑机接口

### 连接流程

1. 主菜单点击"脑机接口"按钮
2. 进入校准界面（3 秒倒计时 → 30 秒记录专注力）
3. 取最后 5 秒均值作为个人基线
4. 校准可选跳过（基线默认 40）
5. 游戏中使用头环控制奶茶杯 + 专注力影响食材

### 协议

基于 IPC 通信协议，通过 TCP Socket 连接科创平台（默认 `127.0.0.1:8000`）：

```
连接 → 发送就绪消息
     → 发送 ipc_algorithm_start_test (gyroscope)
     ← 接收 ipc_algorithm_test (attention / gyroscope)
     
gyroscope 数据格式:
  {"msg":"ipc_algorithm_test", "algorithm_name":"gyroscope",
   "result_args":{"data":{"focus_x":640, "focus_y":360, 
    "gyroscope_x":9.5, "gyroscope_y":258.0, "gyroscope_z":176.0}}}
```

杯子直接取 `focus_x` 作为屏幕位置，不额外平滑（平台已处理）。

### 配置文件

`bci_config.json`：
```json
{"server_ip": "127.0.0.1", "server_port": 8000}
```

## 帐户系统

- 首次启动需创建账号密码
- 每个账号独立存档（`profiles/用户名.json`）
- 存档保存：等级、累计营业额、游戏历史

## 配置说明

常用可调参数在 `config.py`：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `CUP_DURATION` | 15 | 每杯时间（秒） |
| `TOTAL_CUPS` | 5 | 总杯数 |
| `CALIBRATION_DURATION` | 30 | 校准采集时长（秒） |
| `CALIBRATION_BASELINE_WINDOW` | 5 | 基线取最后 N 秒均值 |
| `CUP_SPEED_MIN` | 2.0 | 专注高时最低速度 |
| `CUP_SPEED_MAX` | 8.0 | 专注低时最高速度 |
| `SECRET_RECIPE_OFFSET` | 10 | 秘方阈值偏移量 |
| `LEVEL_THRESHOLDS` | [0,35,100,300] | 升级所需累计营业额 |
| `INGREDIENT_SIZE` | 70 | 食材显示尺寸 |
| `INGREDIENT_SPAWN_INTERVAL` | 1000 | 基础生成间隔（毫秒） |

## 开发阶段

- [x] 基础游戏框架 + 一杯制
- [x] 4 级食材 + 等级系统
- [x] BCI 头动控制 + 专注力校准
- [x] 登录/注册 + 存档
- [x] 专注力波形图（结算界面）
- [x] 低专注保护暂停
- [x] 秘方粒子特效
- [x] 全屏/窗口切换
- [ ] 音效完善
- [ ] 更多游戏模式

## 许可证

仅供学习和研究使用。
