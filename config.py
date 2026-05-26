"""
疯狂奶茶杯 - 游戏配置文件
所有游戏参数、资源路径、颜色、尺寸等集中在此管理
修改游戏数值时，优先在此文件中查找对应参数
"""

import os
import sys

import pygame


def _get_base_path():
    """获取资源基础路径，支持 PyInstaller 打包"""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.abspath(".")


# ============================================================
# 屏幕配置
# ============================================================
SCREEN_WIDTH = 1280  # 游戏窗口宽度（像素），修改此项可改变窗口宽度
SCREEN_HEIGHT = 720  # 游戏窗口高度（像素），修改此项可改变窗口高度
FPS = 60  # 游戏帧率，值越高画面越流畅，但会增加 CPU/GPU 负担
TITLE = "疯狂奶茶杯 - 第1周"  # 游戏窗口标题栏文字

# ============================================================
# 资源路径配置
# ============================================================
ASSETS_DIR = os.path.join(_get_base_path(), "assets")  # 资源文件夹根目录
IMAGES_DIR = os.path.join(ASSETS_DIR, "images")  # 图片资源目录
SOUNDS_DIR = os.path.join(ASSETS_DIR, "sounds")  # 音效资源目录

# ============================================================
# 图片资源路径
# 新增图片时只需将文件放入 images 目录，然后在此处添加路径即可
# ============================================================
BACKGROUND_IMG = os.path.join(IMAGES_DIR, "backgrounds", "吧台.png")  # 背景图
CUP_IMGS = [  # 杯子阶段图片：0接→1, 1接→2, 2+接→3
    os.path.join(IMAGES_DIR, "cups", "奶茶杯1.png"),
    os.path.join(IMAGES_DIR, "cups", "奶茶杯2.png"),
    os.path.join(IMAGES_DIR, "cups", "奶茶杯3.png"),
]
INGREDIENT_IMGS = {  # 食材图片字典
    "红茶": os.path.join(IMAGES_DIR, "ingredients", "红茶.png"),
    "绿茶": os.path.join(IMAGES_DIR, "ingredients", "绿茶.png"),
    "牛奶": os.path.join(IMAGES_DIR, "ingredients", "牛奶.png"),
    "珍珠": os.path.join(IMAGES_DIR, "ingredients", "珍珠.png"),
    "椰果": os.path.join(IMAGES_DIR, "ingredients", "椰果.png"),
    "芋圆": os.path.join(IMAGES_DIR, "ingredients", "芋圆.png"),
    "脆啵啵": os.path.join(IMAGES_DIR, "ingredients", "脆啵啵.png"),
    "芒果": os.path.join(IMAGES_DIR, "ingredients", "芒果.png"),
    "椰奶": os.path.join(IMAGES_DIR, "ingredients", "椰奶.png"),
    "草莓": os.path.join(IMAGES_DIR, "ingredients", "草莓.png"),
    "芋泥": os.path.join(IMAGES_DIR, "ingredients", "芋泥.png"),
    "燕麦奶": os.path.join(IMAGES_DIR, "ingredients", "燕麦奶.png"),
    "咖啡": os.path.join(IMAGES_DIR, "ingredients", "咖啡.png"),
    "特调稀奶油顶": os.path.join(IMAGES_DIR, "ingredients", "特调稀奶油顶.png"),
    "米酿": os.path.join(IMAGES_DIR, "ingredients", "米酿.png"),
    "咸芝士奶盖": os.path.join(IMAGES_DIR, "ingredients", "咸芝士奶盖.png"),
    "茉莉花茶": os.path.join(IMAGES_DIR, "ingredients", "茉莉花茶.png"),
    "秘方": os.path.join(IMAGES_DIR, "ingredients", "秘方.png"),
}
BADGE_IMGS = [  # 徽章图片列表，按等级排列
    os.path.join(IMAGES_DIR, "badges", "badge1.png"),
    os.path.join(IMAGES_DIR, "badges", "badge2.png"),
    os.path.join(IMAGES_DIR, "badges", "badge3.png"),
    os.path.join(IMAGES_DIR, "badges", "badge4.png"),
]
PATIENCE_BAR_IMG = os.path.join(IMAGES_DIR, "other", "耐心条.png")
TOP_BAR_IMG = os.path.join(IMAGES_DIR, "other", "横.png")  # 游戏顶部背景板
PATIENCE_BAR_SIZE = (350, 35)
PATIENCE_BAR_TIMEOUT = 90.0  # 接住小料的超时时间（秒）

# ============================================================
# 中文字体配置（按加载优先级排列）
# 系统会依次尝试加载，直到成功为止
# ============================================================
CHINESE_FONTS = [
    os.path.join(ASSETS_DIR, "fonts", "ZCOOLKuaiLe-Regular.ttf"),  # 站酷快乐体（项目内置卡通字体，优先使用）
    "simhei.ttf",  # 黑体（Windows 系统字体）
    "simkai.ttf",  # 楷体（Windows 系统字体）
    "msyh.ttf",  # 微软雅黑（Windows 系统字体）
    "msyhbd.ttf",  # 微软雅黑粗体（Windows 系统字体）
    os.path.join(ASSETS_DIR, "fonts", "simhei.ttf"),  # 项目内置黑体（备用）
]

# ============================================================
# 颜色定义（RGB 三元组，范围 0-255）
# ============================================================
WHITE = (255, 255, 255)  # 白色
BLACK = (0, 0, 0)  # 黑色
BROWN = (139, 69, 19)  # 棕色
RED = (255, 0, 0)  # 红色
GREEN = (0, 255, 0)  # 绿色

# ============================================================
# 杯子配置
# ============================================================
CUP_WIDTH = 80  # 杯子宽度（像素），修改此项可改变杯子大小
CUP_HEIGHT = 100  # 杯子高度（像素），修改此项可改变杯子大小
CUP_SPEED = 5  # 杯子左右移动速度（像素/帧），值越大移动越快
CUP_COLOR = BROWN  # 杯子默认颜色（无图片时使用）

# ============================================================
# 食材配置
# ============================================================
INGREDIENT_SIZE = 70  # 食材图片尺寸（像素），修改此项可同时改变所有食材大小
INGREDIENT_SPEED = 3.5  # 食材下落速度（像素/帧），值越大下落越快，游戏难度越高
INGREDIENT_TYPES = [  # 所有食材种类
    "珍珠",
    "椰果",
    "牛奶",
    "红茶",
    "绿茶",
    "芋圆",
    "脆啵啵",
    "芒果",
    "椰奶",
    "草莓",
    "芋泥",
    "燕麦奶",
    "咖啡",
    "特调稀奶油顶",
    "米酿",
    "咸芝士奶盖",
    "茉莉花茶",
]

INGREDIENT_COLORS = {  # 食材默认颜色（无图片时使用，RGB 格式）
    "珍珠": (60, 50, 40),
    "椰果": (240, 230, 140),
    "牛奶": (255, 250, 240),
    "红茶": (160, 82, 45),
    "绿茶": (120, 180, 80),
    "芋圆": (180, 140, 100),
    "脆啵啵": (200, 180, 220),
    "芒果": (140, 100, 60),
    "椰奶": (255, 245, 230),
    "草莓": (220, 50, 80),
    "芋泥": (170, 120, 160),
    "燕麦奶": (230, 210, 170),
    "咖啡": (90, 60, 40),
    "特调稀奶油顶": (255, 245, 200),
    "米酿": (240, 220, 160),
    "咸芝士奶盖": (250, 240, 180),
    "茉莉花茶": (180, 210, 100),
}

INGREDIENT_POINTS = {  # 食材分值/金钱值，接到对应食材时获得的价格（元）
    "珍珠": 1,
    "椰果": 1,
    "牛奶": 2,
    "红茶": 2,
    "绿茶": 2,
    "芋圆": 2,
    "脆啵啵": 2,
    "芒果": 3,
    "椰奶": 3,
    "草莓": 3,
    "芋泥": 3,
    "燕麦奶": 4,
    "咖啡": 4,
    "特调稀奶油顶": 5,
    "米酿": 5,
    "咸芝士奶盖": 6,
    "茉莉花茶": 6,
    "秘方": 0,
}

INGREDIENT_TIERS = {  # 等级系统：每个等级的可用食材和必接食材（含之前等级所有食材）
    1: {
        "available": ["珍珠", "椰果", "牛奶", "红茶", "绿茶"],
        "required": ["牛奶", "红茶", "绿茶"],
    },
    2: {
        "available": [
            "珍珠", "椰果", "牛奶", "红茶", "绿茶",
            "芋圆", "脆啵啵", "芒果", "椰奶",
        ],
        "required": ["牛奶", "红茶", "绿茶", "芒果", "椰奶"],
    },
    3: {
        "available": [
            "珍珠", "椰果", "牛奶", "红茶", "绿茶",
            "芋圆", "脆啵啵", "芒果", "椰奶",
            "草莓", "芋泥", "燕麦奶", "咖啡",
        ],
        "required": ["牛奶", "红茶", "绿茶", "芒果", "椰奶", "燕麦奶", "咖啡"],
    },
    4: {
        "available": [
            "珍珠", "椰果", "牛奶", "红茶", "绿茶",
            "芋圆", "脆啵啵", "芒果", "椰奶",
            "草莓", "芋泥", "燕麦奶", "咖啡",
            "特调稀奶油顶", "米酿", "咸芝士奶盖", "茉莉花茶",
        ],
        "required": [
            "牛奶", "红茶", "绿茶", "芒果", "椰奶",
            "燕麦奶", "咖啡", "茉莉花茶",
        ],
    },
}

# ============================================================
# 脑电（BCI）数据配置
# 注意：BCI服务器IP和端口请在游戏中点击"BCI设置"按钮进行配置
# 配置文件保存在 bci_config.json
# ============================================================
DEFAULT_ATTENTION = 50  # 默认专注力值（0-100）
DEAD_ZONE = 2  # 死区阈值，头动信号绝对值小于此值时视为静止（防抖动）
SMOOTHING_FACTOR = 0.15  # 指数平滑因子（0-1），值越大响应越快但越抖动
FOCUS_SENSITIVITY = 100  # 焦点灵敏度：头动 yaw 到像素的映射强度，越大杯子移动越快
BCI_CONNECTION_TIMEOUT = 5  # 连接超时时间（秒）

# ============================================================
# 一杯制配置
# ============================================================
CUP_DURATION = 15  # 每杯时间上限 T（秒），超时则结算
TOTAL_CUPS = 5  # 本局共需制作的奶茶杯数，游戏最大时长 = TOTAL_CUPS × CUP_DURATION
SECRET_RECIPE_SUSTAIN = 4  # 秘方触发所需持续专注秒数 a
SECRET_RECIPE_OFFSET = 5  # 秘方阈值偏移量 m，阈值 = min(基线 + m, 88)
DIFFICULTY_BASELINE = 60  # 难度基线初始值（0-100），自适应调节
DIFFICULTY_ADAPT_WINDOW = 30  # 难度自适应窗口（秒），取此窗口内平均专注力更新基线
CUP_SPEED_MIN = 2.0  # 专注力高时的最低食材速度（px/frame），约可接住 ≥8 个/杯
CUP_SPEED_MAX = 5.0  # 专注力低时的最高食材速度（px/frame），约可接住 ≤6 个/杯
DIFFICULTY_BASELINE_MIN = 40  # 基线调节下限
DIFFICULTY_BASELINE_MAX = 80  # 基线调节上限

# ============================================================
# 热身阶段配置
# 进入正式游戏前进行 3 分钟热身，收集注意力数据用于归一化
# ============================================================
WARMUP_DURATION = 180  # 热身阶段时长（秒），修改此项可改变热身时间
WARMUP_LOW_THRESHOLD = 20  # 低注意力阈值，注意力低于此值时开始计时冻结
WARMUP_FREEZE_TIME = 3.0  # 低注意力持续多久冻结画面（秒）
WARMUP_RESUME_TIME = 5.0  # 注意力恢复后持续多久解冻（秒）
WARMUP_SMOOTH_WINDOW = 3.0  # 注意力平滑窗口（秒），用于速度计算
WARMUP_SPEED_MIN = 1.5  # 热身阶段最低速度（专注力高时，pixels/frame）
WARMUP_SPEED_MAX = 6.0  # 热身阶段最高速度（专注力低时，pixels/frame），变化幅度大、感知明显

# ============================================================
# 正式游戏速度配置（热身结束后使用）
# 速度变化范围比热身阶段窄，减轻感知
# ============================================================
FORMAL_SPEED_MIN = 2.0  # 正式游戏最低速度（归一化值=100时，pixels/frame）
FORMAL_SPEED_MAX = 4.5  # 正式游戏最高速度（归一化值=1时，pixels/frame）

# ============================================================
# 游戏模式配置
# ============================================================
GAME_MODES = {
    "regular": {
        "name": "常规模式",
        "description": "接住必接食材，完成标准配方",
        "has_required": True,
        "free_combine": False,
        "bci_mode": False,
        "ingredient_speed": 3,
        "spawn_interval": 1000,
        "ui_color": (60, 160, 100),
        "total_cups": 5,
        "secret_recipe_cup_interval": 1,
    },
    "challenge": {
        "name": "挑战模式",
        "description": "更快更密集，考验你的手速",
        "has_required": True,
        "free_combine": False,
        "bci_mode": False,
        "ingredient_speed": 5,
        "spawn_interval": 600,
        "ui_color": (200, 80, 60),
        "total_cups": 5,
        "secret_recipe_cup_interval": 1,
    },
    "creative": {
        "name": "创意模式",
        "description": "自由搭配，创造你的专属奶茶",
        "has_required": False,
        "free_combine": True,
        "bci_mode": False,
        "ingredient_speed": 3,
        "spawn_interval": 1200,
        "ui_color": (120, 80, 200),
        "total_cups": 5,
        "secret_recipe_cup_interval": 1,
    },
    "bci": {
        "name": "脑机接口模式",
        "description": "使用BCI设备读取专注力和头动数据",
        "has_required": False,
        "free_combine": True,
        "bci_mode": True,
        "ingredient_speed": 3,
        "spawn_interval": 1200,
        "ui_color": (0, 150, 200),
        "total_cups": 5,
        "secret_recipe_cup_interval": 3,
    },
}

DEFAULT_GAME_MODE = "regular"  # 默认游戏模式
GAME_DURATION = 120  # （已废弃，由一杯制 CUP_DURATION × TOTAL_CUPS 替代）

# ============================================================
# 生成间隔（毫秒）
# 注：实际间隔由 GAME_MODES 中对应模式的 spawn_interval 决定
# ============================================================
INGREDIENT_SPAWN_INTERVAL = 1000  # 兼容旧代码的默认值
