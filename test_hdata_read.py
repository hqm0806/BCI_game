"""HData 头动信号读取测试"""
import os, sys, time
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())

import pygame
pygame.init()
screen = pygame.display.set_mode((660, 240))
pygame.display.set_caption("HData 头动测试 - 转动头部观察数字变化")
clock = pygame.time.Clock()
font = pygame.font.Font(None, 30)

from bci.hdata_interface import HDataInterface
from bci.hdata_gyro import HDataGyroMapper
from bci.hdata_attention import HDataAttentionEstimator

hd = HDataInterface()
gyro_mapper = HDataGyroMapper()
attn = HDataAttentionEstimator()

hd.start_search()
state = "searching"
t0 = time.time()
connected = False

print("HData 头动测试启动")
print("转动头部观察 gyro Y 和 focus_x 变化")
print("按 ESC 退出")

while True:
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            hd.destroy(); pygame.quit(); sys.exit()
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            hd.destroy(); pygame.quit(); sys.exit()

    if not connected:
        if state == "searching":
            if hd.searched_devices:
                dev = hd.searched_devices[0]
                hd.stop_search()
                hd.connect_device(dev)
                state = "connecting"
                t0 = time.time()
                print(f"连接: {dev}")
            elif time.time() - t0 > 15:
                print("搜索超时"); break
        elif state == "connecting":
            if hd.connected:
                state = "waiting_amp"
                t0 = time.time()
                print("等待放大器...")
            elif time.time() - t0 > 10:
                print("连接超时"); break
        elif state == "waiting_amp":
            if hd.sampling_rate > 0:
                hd.start_acquisition()
                connected = True
                print(f"就绪 sr={hd.sampling_rate} ch={hd.eeg_channels}  转动头部!")
    else:
        gx, gy, gz = hd.gyro
        focus_x = gyro_mapper.update(gy)
        eeg = hd.poll_stream_data()
        if eeg:
            for block in eeg: attn.feed(block)

        screen.fill((20, 20, 30))
        lines = [
            f"gyro X:{gx:+7.1f}  Y:{gy:+7.1f}  Z:{gz:+7.1f}",
            f"focus_x: {focus_x:6.1f}  (杯子位置)",
            f"attention: {attn.attention:5.1f} | 电池:{hd.battery}",
            f"sampling={hd.sampling_rate}Hz  channels={hd.eeg_channels}",
            f"<-- 左转  --> 右转  观察 Y 和 focus_x 变化",
            f"ESC 退出",
        ]
        for i, line in enumerate(lines):
            s = font.render(line, True, (200, 255, 200))
            screen.blit(s, (20, 10 + i * 34))

    pygame.display.flip()
    clock.tick(60)

hd.destroy()
pygame.quit()
