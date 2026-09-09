# -*- coding: utf-8 -*-
"""Generate a KiloCode Token Dashboard preview image."""
from PIL import Image, ImageDraw, ImageFont
import os

W, H = 1600, 900
BG = "#0f1115"
CARD = "#1a1d23"
BORDER = "#2a2d35"
TXT = "#e8e8ea"
TXT2 = "#a0a3ab"
TXT3 = "#6e717a"
BRAND = "#3b82f6"
OK = "#22c55e"
WARN = "#f59e0b"
ALGO = "#ef4444"

img = Image.new("RGB", (W, H), BG)
draw = ImageDraw.Draw(img)

def get_font(size, bold=False):
    paths = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simkai.ttf",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    try:
        for p in paths:
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
    except Exception:
        pass
    return ImageFont.load_default()

font_bold = get_font(22, bold=True)
font_title = get_font(28, bold=True)
font_big = get_font(36, bold=True)
font_num = get_font(48, bold=True)
font_sm = get_font(16)
font_xs = get_font(13)
font_hdr = get_font(15, bold=True)

def round_rect(draw, xy, radius, fill, outline=None, width=1):
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill, outline=outline, width=width)

def text(draw, x, y, txt, font, fill, anchor="lt"):
    draw.text((x, y), txt, font=font, fill=fill, anchor=anchor)

# Header
text(draw, 30, 20, "● KiloCode Token 统计面板", font_title, TXT, anchor="lt")
text(draw, W - 30, 20, "● 实时更新", font_sm, TXT3, anchor="rt")

y = 70
# Top stats cards
cx = 30
cy = y
cw = 280
ch = 140
gap = 20
labels = [
    ("累计 Token 数", "12,345,678", "用了 12,345,678 tokens", BRAND),
    ("选中日期消耗", "234,567", "全部时间消耗", BRAND),
    ("今日用量", "89,012", "今日 89,012 tokens", OK),
]
for i, (lbl, val, sub, col) in enumerate(labels):
    x = cx + i * (cw + gap)
    round_rect(draw, [x, cy, x + cw, cy + ch], 14, CARD, BORDER)
    text(draw, x + 18, cy + 18, lbl, font_sm, TXT3, anchor="lt")
    text(draw, x + 18, cy + 50, val, font_num, col, anchor="lt")
    text(draw, x + 18, cy + 110, sub, font_xs, TXT3, anchor="lt")

y = cy + ch + 20
# Middle section: heatmap + model chart
left_w = 580
right_w = W - left_w - 60
rh = 420

round_rect(draw, [30, y, 30 + left_w, y + rh], 14, CARD, BORDER)
text(draw, 50, y + 16, "Token 活动", font_hdr, TXT, anchor="lt")
text(draw, 30 + left_w - 20, y + 16, "2026-01-01 ~ 2026-09-08", font_xs, TXT3, anchor="rt")

# Simulated heatmap
cell_size = 22
cell_gap = 6
hm_x = 50
hm_y = y + 60
for row in range(5):
    for col in range(12):
        cx_ = hm_x + col * (cell_size + cell_gap)
        cy_ = hm_y + row * (cell_size + cell_gap)
        level = [BORDER, f"{OK}40", f"{OK}80", OK][(row + col) % 4]
        draw.rounded_rectangle([cx_, cy_, cx_ + cell_size, cy_ + cell_size], 4, fill=level)

round_rect(draw, [30 + left_w + 20, y, W - 30, y + rh], 14, CARD, BORDER)
text(draw, 50 + left_w, y + 16, "模型用量", font_hdr, TXT, anchor="lt")

# Doughnut chart placeholder
chart_cx = 30 + left_w + 20 + 180
chart_cy = y + rh // 2 + 20
chart_r = 120
draw.ellipse([chart_cx - chart_r, chart_cy - chart_r, chart_cx + chart_r, chart_cy + chart_r], outline=BRAND, width=18)
draw.ellipse([chart_cx - chart_r + 30, chart_cy - chart_r + 30, chart_cx + chart_r - 30, chart_cy + chart_r - 30], fill=CARD)

# Model list
list_x = chart_cx + chart_r + 40
list_y = y + 50
colors = [BRAND, OK, WARN, ALGO, "#8b5cf6", "#ec4899", "#06b6d4", "#84cc16"]
models = ["Anthropic / claude-3.5-sonnet", "OpenAI / gpt-4o", "Google / gemini-pro", "OpenAI / gpt-4o-mini"]
for i, m in enumerate(models):
    draw.rounded_rectangle([list_x, list_y + i * 36, list_x + 12, list_y + i * 36 + 12], 3, fill=colors[i])
    text(draw, list_x + 20, list_y + i * 36 - 2, m, font_sm, TXT2, anchor="lt")
    text(draw, list_x + 380, list_y + i * 36 - 2, f"{(10000 - i * 1500):,}", font_sm, TXT, anchor="rt")

y = y + rh + 20
# Session board
round_rect(draw, [30, y, W - 30, y + 180], 14, CARD, BORDER)
text(draw, 50, y + 16, "会话看板", font_hdr, TXT, anchor="lt")
text(draw, W - 50, y + 16, "最近 100 条请求 · 每秒刷新", font_xs, TXT3, anchor="rt")

# Table header
col_x = [50, 150, 280, 420, 520, 620, 720, 820, 920]
headers = ["时间", "路由", "模型", "输入", "输出", "推理", "缓存读", "总计", "所属会话"]
for i, h in enumerate(headers):
    text(draw, col_x[i], y + 55, h, font_xs, TXT3, anchor="lt")

# Table rows
rows = [
    ["09-08 14:22:01", "Anthropic", "claude-3.5-sonnet", "12,345", "5,678", "2,100", "3,200", "23,423", "abc12345"],
    ["09-08 14:20:15", "OpenAI", "gpt-4o", "8,900", "4,500", "1,800", "2,100", "17,300", "def67890"],
    ["09-08 14:18:30", "Google", "gemini-pro", "5,600", "2,300", "900", "1,500", "10,300", "ghi11111"],
]
for r_i, row in enumerate(rows):
    ry = y + 85 + r_i * 30
    for c_i, cell in enumerate(row):
        color = TXT if c_i in (3, 4, 5, 6, 7) else TXT2
        if c_i == 7:
            color = OK
        text(draw, col_x[c_i], ry, cell, font_xs, color, anchor="lt")

# Footer
text(draw, W // 2, H - 10, "数据来源：KiloCode 本地数据库 (kilo.db) · 每秒自动刷新", font_xs, TXT3, anchor="mm")

out_path = r"C:\Users\CatJiang\Desktop\KiloTokenPanel\preview.png"
img.save(out_path, "PNG")
print(f"Saved preview to {out_path}")
