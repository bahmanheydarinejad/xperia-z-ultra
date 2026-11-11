#!/usr/bin/env python3
"""
==============================================================================
Sony Xperia Z Ultra (togari) — PS5 DualSense Controller Kiosk Application
==============================================================================
Direct Framebuffer (/dev/graphics/fb0) UI with Multitouch & Hardware Volume Backlight.
==============================================================================
"""

import os
import sys
import time
import json
import mmap
import math
import struct
import socket
import select
import threading
from typing import Dict, List, Tuple

# Framebuffer & Hardware Nodes
FB_NODE = "/dev/graphics/fb0" if os.path.exists("/dev/graphics/fb0") else "/dev/fb0"
TOUCH_NODE = "/dev/input/event1"
KEYS_NODE = "/dev/input/event4"
BACKLIGHT_FILE = "/sys/class/leds/lcd-backlight/brightness"
BACKLIGHT_MAX_FILE = "/sys/class/leds/lcd-backlight/max_brightness"
FB_BLANK_FILE = "/sys/class/graphics/fb0/blank"

# Physical Display Specs (Portrait Native)
PHYS_WIDTH = 1080
PHYS_HEIGHT = 1920
BPP = 4  # 32-bit ARGB

# Virtual Landscape Resolution (Gamepad View)
# When phone is held horizontally:
# Width = 1920 (X), Height = 1080 (Y)
V_WIDTH = 1920
V_HEIGHT = 1080

# Colors (ARGB 32-bit format)
C_BLACK      = 0xFF0B0E14
C_DARK_BG    = 0xFF10141D
C_PANEL_BG   = 0xFF181F2C
C_PANEL_BORD = 0xFF2A364F
C_WHITE      = 0xFFF0F3F6
C_GRAY       = 0xFF8A99AD
C_DARK_GRAY  = 0xFF3A475D

# PS5 Signature Colors
C_LIGHTBAR   = 0xFF00B4D8  # Cyan / Electric Blue
C_LIGHTBAR_GLOW = 0xFF0077B6
C_CROSS      = 0xFF29B6F6  # Cyan
C_CIRCLE     = 0xFFFF3D71  # Coral Red
C_TRIANGLE   = 0xFF00E676  # Neon Emerald Green
C_SQUARE     = 0xFFFF4081  # Neon Pink
C_PRESSED    = 0xFFFFFFFF  # Active Button Highlight
C_STICK_BASE = 0xFF1A2230
C_STICK_HEAD = 0xFF2E3D55
C_STICK_HEAD_ACT = 0xFF00B4D8


class BacklightManager:
    """Manages LCD backlight brightness via hardware sysfs."""
    def __init__(self):
        self.max_val = 4095
        if os.path.exists(BACKLIGHT_MAX_FILE):
            try:
                with open(BACKLIGHT_MAX_FILE, "r") as f:
                    self.max_val = int(f.read().strip())
            except Exception:
                pass
        self.min_val = int(self.max_val * 0.05)  # 5% minimum so never pitch black
        self.step = int(self.max_val * 0.08)     # ~8% per volume step
        self.current = self.get_brightness()

    def get_brightness(self) -> int:
        if os.path.exists(BACKLIGHT_FILE):
            try:
                with open(BACKLIGHT_FILE, "r") as f:
                    return int(f.read().strip())
            except Exception:
                pass
        return self.max_val // 2

    def set_brightness(self, val: int):
        val = max(self.min_val, min(self.max_val, val))
        self.current = val
        if os.path.exists(BACKLIGHT_FILE):
            try:
                with open(BACKLIGHT_FILE, "w") as f:
                    f.write(f"{val}\n")
            except Exception:
                pass

    def increase(self):
        self.set_brightness(self.current + self.step)

    def decrease(self):
        self.set_brightness(self.current - self.step)

    @property
    def percentage(self) -> int:
        return int((self.current / self.max_val) * 100)


class GamepadState:
    """Stores full PS5 DualSense controller state."""
    def __init__(self):
        # Analog Sticks: Normalized -1.0 to 1.0 (X, Y)
        self.lx = 0.0
        self.ly = 0.0
        self.rx = 0.0
        self.ry = 0.0

        # Buttons (True when pressed)
        self.cross = False
        self.circle = False
        self.square = False
        self.triangle = False

        self.dpad_up = False
        self.dpad_down = False
        self.dpad_left = False
        self.dpad_right = False

        self.l1 = False
        self.l2 = False
        self.r1 = False
        self.r2 = False

        self.l3 = False
        self.r3 = False

        self.ps_button = False
        self.create_button = False
        self.options_button = False
        self.touchpad_click = False

        # Touchpad touch coordinates (0..1 inside touchpad, or None)
        self.touchpad_x = None
        self.touchpad_y = None

        # Last action timestamp for animations
        self.last_button_pressed = ""
        self.last_press_time = 0.0

    def to_dict(self, brightness_pct: int) -> dict:
        return {
            "timestamp": time.time(),
            "axes": {
                "lx": round(self.lx, 3),
                "ly": round(self.ly, 3),
                "rx": round(self.rx, 3),
                "ry": round(self.ry, 3)
            },
            "buttons": {
                "cross": self.cross,
                "circle": self.circle,
                "square": self.square,
                "triangle": self.triangle,
                "dpad_up": self.dpad_up,
                "dpad_down": self.dpad_down,
                "dpad_left": self.dpad_left,
                "dpad_right": self.dpad_right,
                "l1": self.l1,
                "l2": self.l2,
                "r1": self.r1,
                "r2": self.r2,
                "l3": self.l3,
                "r3": self.r3,
                "ps": self.ps_button,
                "create": self.create_button,
                "options": self.options_button,
                "touchpad": self.touchpad_click
            },
            "brightness": brightness_pct
        }


class FramebufferRenderer:
    """High performance software rasterizer drawing directly into /dev/graphics/fb0."""
    def __init__(self, rotation=90):
        self.rotation = rotation  # 90 degrees rotates 1080x1920 portrait to 1920x1080 landscape
        self.fb_file = None
        self.mmap_fb = None
        self._init_fb()

        # 5x7 Basic Bitmap Font
        self.FONT = {
            'A': [0x0C, 0x12, 0x12, 0x1E, 0x12, 0x12, 0x12],
            'B': [0x1C, 0x12, 0x12, 0x1C, 0x12, 0x12, 0x1C],
            'C': [0x0E, 0x10, 0x10, 0x10, 0x10, 0x10, 0x0E],
            'D': [0x1C, 0x12, 0x12, 0x12, 0x12, 0x12, 0x1C],
            'E': [0x1E, 0x10, 0x10, 0x1C, 0x10, 0x10, 0x1E],
            'F': [0x1E, 0x10, 0x10, 0x1C, 0x10, 0x10, 0x10],
            'G': [0x0E, 0x10, 0x10, 0x16, 0x12, 0x12, 0x0E],
            'H': [0x12, 0x12, 0x12, 0x1E, 0x12, 0x12, 0x12],
            'I': [0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E],
            'J': [0x02, 0x02, 0x02, 0x02, 0x12, 0x12, 0x0C],
            'K': [0x12, 0x14, 0x18, 0x10, 0x18, 0x14, 0x12],
            'L': [0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1E],
            'M': [0x11, 0x1B, 0x15, 0x11, 0x11, 0x11, 0x11],
            'N': [0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11],
            'O': [0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E],
            'P': [0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10],
            'Q': [0x0E, 0x11, 0x11, 0x11, 0x15, 0x13, 0x0D],
            'R': [0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11],
            'S': [0x0E, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E],
            'T': [0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04],
            'U': [0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E],
            'V': [0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04],
            'W': [0x11, 0x11, 0x11, 0x15, 0x15, 0x15, 0x0A],
            'X': [0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11],
            'Y': [0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04],
            'Z': [0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F],
            '0': [0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E],
            '1': [0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E],
            '2': [0x0E, 0x11, 0x01, 0x06, 0x08, 0x10, 0x1F],
            '3': [0x0E, 0x11, 0x01, 0x06, 0x01, 0x11, 0x0E],
            '4': [0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02],
            '5': [0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E],
            '6': [0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E],
            '7': [0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08],
            '8': [0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E],
            '9': [0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C],
            ':': [0x00, 0x0C, 0x0C, 0x00, 0x0C, 0x0C, 0x00],
            '%': [0x19, 0x19, 0x02, 0x04, 0x08, 0x13, 0x13],
            '+': [0x00, 0x04, 0x04, 0x1F, 0x04, 0x04, 0x00],
            '-': [0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00],
            '.': [0x00, 0x00, 0x00, 0x00, 0x00, 0x0C, 0x0C],
            '[': [0x0E, 0x08, 0x08, 0x08, 0x08, 0x08, 0x0E],
            ']': [0x0E, 0x02, 0x02, 0x02, 0x02, 0x02, 0x0E],
            ' ': [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        }

    def _init_fb(self):
        # Unblank screen
        if os.path.exists(FB_BLANK_FILE):
            try:
                with open(FB_BLANK_FILE, "w") as f:
                    f.write("0\n")
            except Exception:
                pass
        try:
            self.fb_file = open(FB_NODE, "r+b")
            total_bytes = PHYS_WIDTH * PHYS_HEIGHT * BPP
            self.mmap_fb = mmap.mmap(self.fb_file.fileno(), total_bytes)
        except Exception as e:
            print(f"[!] Framebuffer mmap failed: {e}")
            self.mmap_fb = None

    def put_pixel(self, vx: int, vy: int, argb: int):
        """Maps virtual landscape coordinate (vx, vy) to physical portrait fb0."""
        if not self.mmap_fb:
            return
        if vx < 0 or vx >= V_WIDTH or vy < 0 or vy >= V_HEIGHT:
            return

        if self.rotation == 90:
            # Held horizontally: Phone Top is Left
            # Physical: px = vy, py = (V_WIDTH - 1 - vx)
            px = vy
            py = (V_WIDTH - 1) - vx
        elif self.rotation == 270:
            # Phone Top is Right
            px = (V_HEIGHT - 1) - vy
            py = vx
        else:
            px = vx
            py = vy

        if 0 <= px < PHYS_WIDTH and 0 <= py < PHYS_HEIGHT:
            offset = (py * PHYS_WIDTH + px) * BPP
            self.mmap_fb[offset:offset + 4] = struct.pack("<I", argb)

    def fill_rect(self, vx: int, vy: int, w: int, h: int, argb: int):
        """Draws filled rectangle in virtual landscape space."""
        for y in range(vy, vy + h):
            for x in range(vx, vx + w):
                self.put_pixel(x, y, argb)

    def draw_circle(self, cx: int, cy: int, radius: int, argb: int, filled=True):
        """Draws filled or outlined circle."""
        r2 = radius * radius
        if filled:
            for dy in range(-radius, radius + 1):
                dx_max = int(math.isqrt(max(0, r2 - dy * dy)))
                for dx in range(-dx_max, dx_max + 1):
                    self.put_pixel(cx + dx, cy + dy, argb)
        else:
            # Circle boundary (2px thick)
            for dy in range(-radius, radius + 1):
                dx = int(math.isqrt(max(0, r2 - dy * dy)))
                self.put_pixel(cx + dx, cy + dy, argb)
                self.put_pixel(cx - dx, cy + dy, argb)
                self.put_pixel(cx + dx - 1, cy + dy, argb)
                self.put_pixel(cx - dx + 1, cy + dy, argb)

    def draw_text(self, text: str, vx: int, vy: int, scale=3, argb=C_WHITE):
        """Draws bitmap text."""
        cursor_x = vx
        for ch in text.upper():
            glyph = self.FONT.get(ch, self.FONT[' '])
            for r_idx, row in enumerate(glyph):
                for c_idx in range(5):
                    if (row >> (4 - c_idx)) & 1:
                        self.fill_rect(cursor_x + c_idx * scale, vy + r_idx * scale, scale, scale, argb)
            cursor_x += 6 * scale

    def clear(self, color=C_BLACK):
        if not self.mmap_fb:
            return
        total_pixels = PHYS_WIDTH * PHYS_HEIGHT
        pixel_bytes = struct.pack("<I", color) * 1024
        chunks = total_pixels // 1024
        self.mmap_fb.seek(0)
        for _ in range(chunks):
            self.mmap_fb.write(pixel_bytes)


class TouchManager:
    """Multitouch event reader from /dev/input/event1."""
    def __init__(self, rotation=90):
        self.rotation = rotation
        # Active touch slots: slot_id -> (vx, vy, is_down)
        self.slots: Dict[int, Dict] = {}
        self.current_slot = 0
        self.running = True
        self._lock = threading.Lock()

    def start(self):
        t = threading.Thread(target=self._read_loop, daemon=True)
        t.start()

    def _read_loop(self):
        if not os.path.exists(TOUCH_NODE):
            return
        try:
            with open(TOUCH_NODE, "rb") as f:
                cur_x = 0
                cur_y = 0
                while self.running:
                    data = f.read(16)
                    if not data:
                        break
                    # Linux input_event struct: llHHI
                    sec, usec, ev_type, ev_code, ev_value = struct.unpack("llHHI", data)

                    if ev_type == 3:  # EV_ABS
                        if ev_code == 0x2f:  # ABS_MT_SLOT
                            self.current_slot = ev_value
                        elif ev_code == 0x39:  # ABS_MT_TRACKING_ID
                            with self._lock:
                                if ev_value == 0xFFFFFFFF or ev_value == -1:
                                    if self.current_slot in self.slots:
                                        self.slots[self.current_slot]["down"] = False
                                else:
                                    if self.current_slot not in self.slots:
                                        self.slots[self.current_slot] = {"x": 0, "y": 0, "down": True}
                                    self.slots[self.current_slot]["down"] = True
                        elif ev_code == 0x35:  # ABS_MT_POSITION_X (0..1079)
                            cur_x = ev_value
                        elif ev_code == 0x36:  # ABS_MT_POSITION_Y (0..1919)
                            cur_y = ev_value
                            # Convert physical touch to virtual landscape space
                            if self.rotation == 90:
                                vx = (PHYS_HEIGHT - 1) - cur_y
                                vy = cur_x
                            elif self.rotation == 270:
                                vx = cur_y
                                vy = (PHYS_WIDTH - 1) - cur_x
                            else:
                                vx = cur_x
                                vy = cur_y

                            with self._lock:
                                if self.current_slot not in self.slots:
                                    self.slots[self.current_slot] = {"x": vx, "y": vy, "down": True}
                                else:
                                    self.slots[self.current_slot]["x"] = vx
                                    self.slots[self.current_slot]["y"] = vy

                    elif ev_type == 0 and ev_code == 0:  # SYN_REPORT
                        pass
        except Exception as e:
            print(f"[!] Touch listener error: {e}")

    def get_active_touches(self) -> List[Tuple[int, int]]:
        with self._lock:
            return [(s["x"], s["y"]) for s in self.slots.values() if s.get("down", False)]


class KeyManager:
    """Hardware volume key monitor for screen backlight control."""
    def __init__(self, backlight: BacklightManager, on_key_callback=None):
        self.backlight = backlight
        self.on_key_callback = on_key_callback
        self.running = True

    def start(self):
        t = threading.Thread(target=self._keys_loop, daemon=True)
        t.start()

    def _keys_loop(self):
        if not os.path.exists(KEYS_NODE):
            return
        try:
            with open(KEYS_NODE, "rb") as f:
                while self.running:
                    data = f.read(16)
                    if not data:
                        break
                    sec, usec, ev_type, ev_code, ev_value = struct.unpack("llHHI", data)
                    if ev_type == 1 and ev_value in [1, 2]:  # EV_KEY, Key Press or Hold
                        if ev_code == 115:  # KEY_VOLUMEUP
                            self.backlight.increase()
                            if self.on_key_callback:
                                self.on_key_callback("VOL_UP", self.backlight.percentage)
                        elif ev_code == 114:  # KEY_VOLUMEDOWN
                            self.backlight.decrease()
                            if self.on_key_callback:
                                self.on_key_callback("VOL_DOWN", self.backlight.percentage)
        except Exception as e:
            print(f"[!] Key listener error: {e}")


class PS5ControllerApp:
    """Main PS5 DualSense Kiosk Controller."""
    def __init__(self):
        self.renderer = FramebufferRenderer(rotation=90)
        self.backlight = BacklightManager()
        self.state = GamepadState()
        self.touch_mgr = TouchManager(rotation=90)
        self.last_key_name = ""
        self.last_key_time = 0.0

        self.key_mgr = KeyManager(self.backlight, on_key_callback=self._on_hw_key)

        # Network UDP Broadcast Socket
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        # Layout Geometry (Virtual 1920x1080)
        # Left Stick Base
        self.LS_CX = 340
        self.LS_CY = 720
        self.LS_R_OUTER = 140
        self.LS_R_STICK = 65

        # Right Stick Base
        self.RS_CX = 1580
        self.RS_CY = 720
        self.RS_R_OUTER = 140
        self.RS_R_STICK = 65

        # D-Pad Center
        self.DPAD_CX = 340
        self.DPAD_CY = 360
        self.DPAD_BTN_R = 48

        # Action Buttons Center
        self.ACT_CX = 1580
        self.ACT_CY = 360
        self.ACT_BTN_R = 48

        # Triggers
        self.L1_RECT = (180, 50, 220, 75)
        self.L2_RECT = (180, 140, 220, 75)
        self.R1_RECT = (1520, 50, 220, 75)
        self.R2_RECT = (1520, 140, 220, 75)

        # Center Console
        self.TOUCHPAD_RECT = (710, 220, 500, 280)
        self.PS_BTN_CIRCLE = (960, 680, 50)
        self.CREATE_BTN_RECT = (580, 260, 90, 50)
        self.OPTIONS_BTN_RECT = (1250, 260, 90, 50)

    def _on_hw_key(self, name: str, pct: int):
        self.last_key_name = f"{name} ({pct}%)"
        self.last_key_time = time.time()

    def start(self):
        print("[*] Starting PS5 Controller App...")
        self.touch_mgr.start()
        self.key_mgr.start()

        # Clear Screen Initially
        self.renderer.clear(C_DARK_BG)

        # Main Render & State Update Loop
        fps = 30
        frame_time = 1.0 / fps

        try:
            while True:
                t0 = time.time()
                self._update_input_state()
                self._render_frame()
                self._broadcast_state()

                elapsed = time.time() - t0
                if elapsed < frame_time:
                    time.sleep(frame_time - elapsed)
        except KeyboardInterrupt:
            print("[*] Controller app exiting.")

    def _update_input_state(self):
        touches = self.touch_mgr.get_active_touches()

        # Reset button press flags
        self.state.cross = False
        self.state.circle = False
        self.state.square = False
        self.state.triangle = False
        self.state.dpad_up = False
        self.state.dpad_down = False
        self.state.dpad_left = False
        self.state.dpad_right = False
        self.state.l1 = False
        self.state.l2 = False
        self.state.r1 = False
        self.state.r2 = False
        self.state.ps_button = False
        self.state.create_button = False
        self.state.options_button = False
        self.state.touchpad_click = False

        ls_touched = False
        rs_touched = False

        # Action Button Positions (Cross=Down, Circle=Right, Square=Left, Triangle=Up)
        btn_dist = 110
        p_tri = (self.ACT_CX, self.ACT_CY - btn_dist)
        p_cir = (self.ACT_CX + btn_dist, self.ACT_CY)
        p_cro = (self.ACT_CX, self.ACT_CY + btn_dist)
        p_squ = (self.ACT_CX - btn_dist, self.ACT_CY)

        # D-Pad Positions
        d_up = (self.DPAD_CX, self.DPAD_CY - btn_dist)
        d_rt = (self.DPAD_CX + btn_dist, self.DPAD_CY)
        d_dn = (self.DPAD_CX, self.DPAD_CY + btn_dist)
        d_lt = (self.DPAD_CX - btn_dist, self.DPAD_CY)

        def in_circle(tx, ty, cx, cy, r):
            return (tx - cx)**2 + (ty - cy)**2 <= r**2

        def in_rect(tx, ty, rx, ry, rw, rh):
            return rx <= tx <= rx + rw and ry <= ty <= ry + rh

        for (tx, ty) in touches:
            # 1. Left Stick (Draggable)
            if in_circle(tx, ty, self.LS_CX, self.LS_CY, self.LS_R_OUTER + 40):
                ls_touched = True
                dx = tx - self.LS_CX
                dy = ty - self.LS_CY
                dist = math.hypot(dx, dy)
                max_d = self.LS_R_OUTER - 20
                if dist > max_d:
                    dx = (dx / dist) * max_d
                    dy = (dy / dist) * max_d
                self.state.lx = dx / max_d
                self.state.ly = -(dy / max_d)  # Up is positive
                continue

            # 2. Right Stick (Draggable)
            if in_circle(tx, ty, self.RS_CX, self.RS_CY, self.RS_R_OUTER + 40):
                rs_touched = True
                dx = tx - self.RS_CX
                dy = ty - self.RS_CY
                dist = math.hypot(dx, dy)
                max_d = self.RS_R_OUTER - 20
                if dist > max_d:
                    dx = (dx / dist) * max_d
                    dy = (dy / dist) * max_d
                self.state.rx = dx / max_d
                self.state.ry = -(dy / max_d)
                continue

            # 3. Action Buttons
            if in_circle(tx, ty, p_cro[0], p_cro[1], self.ACT_BTN_R + 15):
                self.state.cross = True
            elif in_circle(tx, ty, p_cir[0], p_cir[1], self.ACT_BTN_R + 15):
                self.state.circle = True
            elif in_circle(tx, ty, p_squ[0], p_squ[1], self.ACT_BTN_R + 15):
                self.state.square = True
            elif in_circle(tx, ty, p_tri[0], p_tri[1], self.ACT_BTN_R + 15):
                self.state.triangle = True

            # 4. D-Pad
            elif in_circle(tx, ty, d_up[0], d_up[1], self.DPAD_BTN_R + 15):
                self.state.dpad_up = True
            elif in_circle(tx, ty, d_rt[0], d_rt[1], self.DPAD_BTN_R + 15):
                self.state.dpad_right = True
            elif in_circle(tx, ty, d_dn[0], d_dn[1], self.DPAD_BTN_R + 15):
                self.state.dpad_down = True
            elif in_circle(tx, ty, d_lt[0], d_lt[1], self.DPAD_BTN_R + 15):
                self.state.dpad_left = True

            # 5. Triggers & Bumpers
            elif in_rect(tx, ty, *self.L1_RECT):
                self.state.l1 = True
            elif in_rect(tx, ty, *self.L2_RECT):
                self.state.l2 = True
            elif in_rect(tx, ty, *self.R1_RECT):
                self.state.r1 = True
            elif in_rect(tx, ty, *self.R2_RECT):
                self.state.r2 = True

            # 6. Center Console
            elif in_rect(tx, ty, *self.TOUCHPAD_RECT):
                self.state.touchpad_click = True
            elif in_circle(tx, ty, self.PS_BTN_CIRCLE[0], self.PS_BTN_CIRCLE[1], self.PS_BTN_CIRCLE[2] + 10):
                self.state.ps_button = True
            elif in_rect(tx, ty, *self.CREATE_BTN_RECT):
                self.state.create_button = True
            elif in_rect(tx, ty, *self.OPTIONS_BTN_RECT):
                self.state.options_button = True

        # Return sticks to center if released
        if not ls_touched:
            self.state.lx = 0.0
            self.state.ly = 0.0
        if not rs_touched:
            self.state.rx = 0.0
            self.state.ry = 0.0

    def _render_frame(self):
        # Background Clean
        self.renderer.clear(C_DARK_BG)

        # 1. DualSense Lightbar Accent (Top Curved Light Line)
        self.renderer.fill_rect(480, 16, 960, 8, C_LIGHTBAR)
        self.renderer.fill_rect(520, 24, 880, 4, C_LIGHTBAR_GLOW)

        # Header Title & Status
        self.renderer.draw_text("PS5 DUALSENSE KIOSK", 740, 50, scale=3, argb=C_WHITE)
        self.renderer.draw_text("SONY XPERIA Z ULTRA SBC", 780, 85, scale=2, argb=C_LIGHTBAR)

        # 2. Screen Brightness HUD & Hardware Key Notification
        pct = self.backlight.percentage
        hud_text = f"BRIGHTNESS: {pct}%"
        self.renderer.draw_text(hud_text, 780, 130, scale=2, argb=C_GRAY)

        # Brightness Progress Bar
        bar_x = 760
        bar_y = 155
        bar_w = 400
        bar_h = 16
        self.renderer.fill_rect(bar_x, bar_y, bar_w, bar_h, C_PANEL_BG)
        fill_w = int((pct / 100.0) * bar_w)
        self.renderer.fill_rect(bar_x, bar_y, fill_w, bar_h, C_LIGHTBAR)

        # Hardware Volume Button Popup (if pressed recently)
        if time.time() - self.last_key_time < 2.0:
            self.renderer.draw_text(f"HW KEY: {self.last_key_name}", 800, 180, scale=2, argb=C_TRIANGLE)

        # 3. Triggers & Bumpers (L1, L2, R1, R2)
        def draw_btn_rect(rect, label, pressed, color=C_PANEL_BG):
            rx, ry, rw, rh = rect
            col = C_PRESSED if pressed else color
            txt_col = C_BLACK if pressed else C_WHITE
            self.renderer.fill_rect(rx, ry, rw, rh, col)
            self.renderer.draw_text(label, rx + rw // 2 - 20, ry + rh // 2 - 12, scale=3, argb=txt_col)

        draw_btn_rect(self.L1_RECT, "L1", self.state.l1, C_PANEL_BG)
        draw_btn_rect(self.L2_RECT, "L2", self.state.l2, C_PANEL_BG)
        draw_btn_rect(self.R1_RECT, "R1", self.state.r1, C_PANEL_BG)
        draw_btn_rect(self.R2_RECT, "R2", self.state.r2, C_PANEL_BG)

        # 4. Touchpad (Center)
        t_col = C_LIGHTBAR if self.state.touchpad_click else C_PANEL_BG
        self.renderer.fill_rect(*self.TOUCHPAD_RECT, t_col)
        self.renderer.draw_text("DUALSENSE TOUCHPAD", 780, 340, scale=3, argb=C_WHITE if not self.state.touchpad_click else C_BLACK)

        # 5. Create & Options Buttons
        draw_btn_rect(self.CREATE_BTN_RECT, "<", self.state.create_button, C_PANEL_BG)
        draw_btn_rect(self.OPTIONS_BTN_RECT, ">", self.state.options_button, C_PANEL_BG)

        # 6. PS Home Button
        ps_col = C_LIGHTBAR if self.state.ps_button else C_PANEL_BG
        self.renderer.draw_circle(self.PS_BTN_CIRCLE[0], self.PS_BTN_CIRCLE[1], self.PS_BTN_CIRCLE[2], ps_col)
        self.renderer.draw_text("PS", self.PS_BTN_CIRCLE[0] - 18, self.PS_BTN_CIRCLE[1] - 14, scale=3, argb=C_WHITE if not self.state.ps_button else C_BLACK)

        # 7. D-Pad Directional Buttons
        btn_dist = 110
        d_up = (self.DPAD_CX, self.DPAD_CY - btn_dist)
        d_rt = (self.DPAD_CX + btn_dist, self.DPAD_CY)
        d_dn = (self.DPAD_CX, self.DPAD_CY + btn_dist)
        d_lt = (self.DPAD_CX - btn_dist, self.DPAD_CY)

        def draw_round_btn(pos, label, pressed, symbol_col=C_WHITE):
            cx, cy = pos
            r = self.DPAD_BTN_R
            bg_col = C_PRESSED if pressed else C_PANEL_BG
            self.renderer.draw_circle(cx, cy, r, bg_col)
            lbl_col = C_BLACK if pressed else symbol_col
            self.renderer.draw_text(label, cx - 10, cy - 12, scale=3, argb=lbl_col)

        draw_round_btn(d_up, "U", self.state.dpad_up, C_WHITE)
        draw_round_btn(d_rt, "R", self.state.dpad_right, C_WHITE)
        draw_round_btn(d_dn, "D", self.state.dpad_down, C_WHITE)
        draw_round_btn(d_lt, "L", self.state.dpad_left, C_WHITE)

        # 8. Action Buttons (Triangle, Circle, Cross, Square)
        p_tri = (self.ACT_CX, self.ACT_CY - btn_dist)
        p_cir = (self.ACT_CX + btn_dist, self.ACT_CY)
        p_cro = (self.ACT_CX, self.ACT_CY + btn_dist)
        p_squ = (self.ACT_CX - btn_dist, self.ACT_CY)

        draw_round_btn(p_tri, "T", self.state.triangle, C_TRIANGLE)
        draw_round_btn(p_cir, "O", self.state.circle, C_CIRCLE)
        draw_round_btn(p_cro, "X", self.state.cross, C_CROSS)
        draw_round_btn(p_squ, "S", self.state.square, C_SQUARE)

        # 9. Left Analog Stick (L3)
        self.renderer.draw_circle(self.LS_CX, self.LS_CY, self.LS_R_OUTER, C_STICK_BASE)
        self.renderer.draw_circle(self.LS_CX, self.LS_CY, self.LS_R_OUTER, C_PANEL_BORD, filled=False)

        # Deflected Stick Head Position
        max_d = self.LS_R_OUTER - 20
        ls_hx = int(self.LS_CX + self.state.lx * max_d)
        ls_hy = int(self.LS_CY - self.state.ly * max_d)
        head_col = C_STICK_HEAD_ACT if (abs(self.state.lx) > 0.05 or abs(self.state.ly) > 0.05) else C_STICK_HEAD
        self.renderer.draw_circle(ls_hx, ls_hy, self.LS_R_STICK, head_col)
        self.renderer.draw_text("L3", ls_hx - 12, ls_hy - 12, scale=3, argb=C_WHITE)

        # Normalized coordinates text
        ls_coord = f"LX:{self.state.lx:+.2f} LY:{self.state.ly:+.2f}"
        self.renderer.draw_text(ls_coord, self.LS_CX - 120, self.LS_CY + self.LS_R_OUTER + 25, scale=2, argb=C_GRAY)

        # 10. Right Analog Stick (R3)
        self.renderer.draw_circle(self.RS_CX, self.RS_CY, self.RS_R_OUTER, C_STICK_BASE)
        self.renderer.draw_circle(self.RS_CX, self.RS_CY, self.RS_R_OUTER, C_PANEL_BORD, filled=False)

        rs_hx = int(self.RS_CX + self.state.rx * max_d)
        rs_hy = int(self.RS_CY - self.state.ry * max_d)
        head_col_r = C_STICK_HEAD_ACT if (abs(self.state.rx) > 0.05 or abs(self.state.ry) > 0.05) else C_STICK_HEAD
        self.renderer.draw_circle(rs_hx, rs_hy, self.RS_R_STICK, head_col_r)
        self.renderer.draw_text("R3", rs_hx - 12, rs_hy - 12, scale=3, argb=C_WHITE)

        rs_coord = f"RX:{self.state.rx:+.2f} RY:{self.state.ry:+.2f}"
        self.renderer.draw_text(rs_coord, self.RS_CX - 120, self.RS_CY + self.RS_R_OUTER + 25, scale=2, argb=C_GRAY)

        # Bottom System Info Footer
        self.renderer.fill_rect(0, 1020, V_WIDTH, 60, C_BLACK)
        self.renderer.draw_text("HARDWARE CONTROLS: VOL UP=BRIGHTNESS+ | VOL DOWN=BRIGHTNESS-", 360, 1040, scale=2, argb=C_GRAY)

    def _broadcast_state(self):
        """Sends UDP telemetry packet."""
        try:
            payload = json.dumps(self.state.to_dict(self.backlight.percentage)).encode("utf-8")
            self.udp_sock.sendto(payload, ("127.0.0.1", 5555))
        except Exception:
            pass


if __name__ == "__main__":
    app = PS5ControllerApp()
    app.start()
