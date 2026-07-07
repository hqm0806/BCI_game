"""HData 完整连接测试"""
import os, sys, time
os.chdir(os.path.dirname(os.path.abspath(__file__)))
import pygame
pygame.init()
pygame.display.set_mode((100, 100), pygame.HIDDEN)
clock = pygame.time.Clock()
from bci.hdata_interface import HDataInterface

hd = HDataInterface()

# 搜索
hd.start_search()
t0 = time.time()
while time.time() - t0 < 10 and not hd.searched_devices:
    pygame.event.pump(); clock.tick(60)
print(f"搜索: {hd.searched_devices}")

# 连接
hd.connect_device(hd.searched_devices[0])
t0 = time.time()
while time.time() - t0 < 10 and not hd.connected:
    pygame.event.pump(); clock.tick(60)
print(f"连接={hd.connected}")

# 等放大器
t0 = time.time()
while time.time() - t0 < 15 and hd.sampling_rate == 0:
    pygame.event.pump(); clock.tick(60)
sr = hd.sampling_rate; ch = hd.eeg_channels
print(f"amp sr={sr} ch={ch}")

if sr > 0:
    hd.start_acquisition()
    print("采集 3s...")
    t0 = time.time()
    while time.time() - t0 < 3:
        pygame.event.pump(); clock.tick(60)
    hd.stop_acquisition()
    print("完成")

hd.destroy()
pygame.quit()
