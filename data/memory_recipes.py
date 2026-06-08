"""忆调模式配方库 - 按食材数量分组的配方定义"""

from __future__ import annotations

MEMORY_RECIPES: dict[int, list[dict]] = {
    2: [
        {"name": "经典奶茶", "ingredients": ["红茶", "牛奶"]},
        {"name": "清新茉莉绿", "ingredients": ["绿茶", "茉莉花茶"]},
        {"name": "双Q奶茶", "ingredients": ["珍珠", "椰果"]},
        {"name": "拿铁咖啡", "ingredients": ["牛奶", "咖啡"]},
        {"name": "热带水果茶", "ingredients": ["芒果", "草莓"]},
        {"name": "双芋奶茶", "ingredients": ["芋圆", "芋泥"]},
        {"name": "植物双奶", "ingredients": ["椰奶", "燕麦奶"]},
        {"name": "芝士红茶", "ingredients": ["红茶", "咸芝士奶盖"]},
        {"name": "雪顶绿茶", "ingredients": ["绿茶", "特调稀奶油顶"]},
        {"name": "米酿红茶", "ingredients": ["米酿", "红茶"]},
        {"name": "脆啵奶茶", "ingredients": ["牛奶", "脆啵啵"]},
    ],
    3: [
        {"name": "珍珠奶茶", "ingredients": ["红茶", "牛奶", "珍珠"]},
        {"name": "椰果奶茶", "ingredients": ["红茶", "牛奶", "椰果"]},
        {"name": "草莓茉莉绿", "ingredients": ["绿茶", "茉莉花茶", "草莓"]},
        {"name": "芝士拿铁", "ingredients": ["咖啡", "牛奶", "咸芝士奶盖"]},
        {"name": "三重奏奶茶", "ingredients": ["珍珠", "椰果", "脆啵啵"]},
        {"name": "芋香红茶", "ingredients": ["红茶", "芋圆", "芋泥"]},
        {"name": "植物拿铁", "ingredients": ["椰奶", "燕麦奶", "咖啡"]},
        {"name": "奶油奶茶", "ingredients": ["红茶", "牛奶", "特调稀奶油顶"]},
        {"name": "米酿奶茶", "ingredients": ["米酿", "红茶", "牛奶"]},
        {"name": "芒果椰绿", "ingredients": ["绿茶", "芒果", "椰奶"]},
    ],
    4: [
        {"name": "经典四宝茶", "ingredients": ["红茶", "牛奶", "珍珠", "椰果"]},
        {"name": "缤纷水果绿", "ingredients": ["绿茶", "茉莉花茶", "芒果", "草莓"]},
        {"name": "芝士脆啵拿铁", "ingredients": ["咖啡", "牛奶", "咸芝士奶盖", "脆啵啵"]},
        {"name": "芋泥波波茶", "ingredients": ["红茶", "芋圆", "芋泥", "椰奶"]},
        {"name": "草莓椰绿雪顶", "ingredients": ["绿茶", "草莓", "椰果", "特调稀奶油顶"]},
        {"name": "养生植物奶茶", "ingredients": ["椰奶", "燕麦奶", "珍珠", "米酿"]},
        {"name": "醇香芋泥奶", "ingredients": ["牛奶", "芋泥", "芋圆", "燕麦奶"]},
        {"name": "芒果椰脆", "ingredients": ["芒果", "椰奶", "椰果", "脆啵啵"]},
    ],
    5: [
        {"name": "满料奶茶", "ingredients": ["红茶", "牛奶", "珍珠", "椰果", "脆啵啵"]},
        {"name": "缤纷茉莉水果茶", "ingredients": ["绿茶", "茉莉花茶", "草莓", "芒果", "椰果"]},
        {"name": "豪华芝士拿铁", "ingredients": ["咖啡", "牛奶", "咸芝士奶盖", "珍珠", "脆啵啵"]},
        {"name": "芋泥奶油波波", "ingredients": ["红茶", "牛奶", "芋圆", "芋泥", "特调稀奶油顶"]},
        {"name": "全料植物奶茶", "ingredients": ["椰奶", "燕麦奶", "珍珠", "椰果", "米酿"]},
        {"name": "特调米酿水果绿", "ingredients": ["绿茶", "芒果", "草莓", "米酿", "茉莉花茶"]},
    ],
}
