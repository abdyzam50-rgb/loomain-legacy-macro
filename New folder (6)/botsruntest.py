# -*- coding: utf-8 -*-
# --- Core GUI & App Imports ---
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk, Menu
import ttkbootstrap as bstrap
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledText
import os
import sys
import json
import uuid
from PIL import Image, ImageTk
import shutil

# --- Bot Logic Imports ---
import subprocess
import pytesseract
import cv2
import numpy as np
from PIL import ImageGrab
import time
import threading
import keyboard
import requests
from io import BytesIO
from skimage.metrics import structural_similarity as ssim
import random
import pyautogui
import queue
from enum import Enum, auto

# ===================================================================================
# SECTION 1: SHARED UTILITIES & DATA HANDLING
# ===================================================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BOT_ASSETS_DIR = os.path.join(SCRIPT_DIR, "bot_assets")
os.makedirs(BOT_ASSETS_DIR, exist_ok=True)
APP_DATA_FILE = os.path.join(SCRIPT_DIR, "app_data.json")

DEFAULTS = {
    "mouse_x": 100, "mouse_y": 100, "capture_x": 200, "capture_y": 200,
    "ace_disc_x": 300, "ace_disc_y": 300, "use_disk_x": 400, "use_disk_y": 400,
    "no_button_x": 500, "no_button_y": 500,
    "header_topleft_x": 0, "header_topleft_y": 0, "header_bottomright_x": 800, "header_bottomright_y": 600,
    "ocr_topleft_x": 10, "ocr_topleft_y": 10, "ocr_bottomright_x": 110, "ocr_bottomright_y": 40,
    "photo_topleft_x": 10, "photo_topleft_y": 45, "photo_bottomright_x": 110, "photo_bottomright_y": 110,
    "action_scan_topleft_x": 0, "action_scan_topleft_y": 0, "action_scan_bottomright_x": 1920, "action_scan_bottomright_y": 1080,
    "AHK_PATH": "C:/Program Files/AutoHotkey/AutoHotkey.exe",
    "AHK_SCRIPT": "", "AHK_RUNAWAY_SCRIPT": "", "pause_hotkey": "F9", "photo_match_threshold": 0.85,
    "WEBHOOK_URLS": [], "theme": "darkly", "TESSERACT_PATH": "",
    "ITEMS_HEADER_PATH": os.path.join(BOT_ASSETS_DIR, "items_header.png"),
    "ACE_DISC_PATH": os.path.join(BOT_ASSETS_DIR, "ace_disc.png"),
    "USE_IMAGE_PATH": os.path.join(BOT_ASSETS_DIR, "use_button.png"),
    "NO_BUTTON_IMAGE_PATH": os.path.join(BOT_ASSETS_DIR, "no_button.png"),
    "special_capture_forms": ["gamma", "alpha"],
    "run_away_forms": ["dull", "frail"]
}

def save_app_data(settings_data, names_data, name_order_list):
    combined_data = {"settings": settings_data, "names_data": {"data": names_data, "name_order": name_order_list}}
    with open(APP_DATA_FILE, 'w', encoding='utf-8') as f: json.dump(combined_data, f, indent=4)

def load_app_data():
    if os.path.exists(APP_DATA_FILE):
        try:
            with open(APP_DATA_FILE, 'r', encoding='utf-8') as f: combined_data = json.load(f)
            settings_data = DEFAULTS.copy(); settings_data.update(combined_data.get("settings", {}))
            names_section = combined_data.get("names_data", {}); names_data = names_section.get("data", {}); name_order_list = names_section.get("name_order", [])
            return settings_data, names_data, name_order_list
        except (json.JSONDecodeError, IOError):
            print(f"WARNING: '{APP_DATA_FILE}' is corrupt. A new file will be created.")
    print(f"INFO: '{APP_DATA_FILE}' not found. Creating a new one with default values.")
    save_app_data(DEFAULTS.copy(), {}, [])
    return DEFAULTS.copy(), {}, []

def add_placeholder(entry, placeholder_text):
    entry.insert(0, placeholder_text); entry.config(foreground="grey")
    def on_focus_in(e):
        if entry.get() == placeholder_text:
            entry.delete(0, tk.END); entry.config(foreground=bstrap.Style().colors.fg)
    def on_focus_out(e):
        if not entry.get():
            entry.config(foreground="grey"); entry.insert(0, placeholder_text)
    entry.bind("<FocusIn>", on_focus_in); entry.bind("<FocusOut>", on_focus_out)

def save_image_as_png(source_path, name, photo_name, photo_id):
    name_dir = os.path.join(SCRIPT_DIR, "photos_data", name.strip().replace(" ", "_")); os.makedirs(name_dir, exist_ok=True)
    new_path = os.path.join(name_dir, f"{photo_name.strip().replace(' ', '_')}_{photo_id[:8]}.png")
    try:
        with Image.open(source_path) as img: img.save(new_path, "PNG"); return new_path
    except Exception as e: messagebox.showerror("Image Error", f"Could not save image: {e}"); return None

# ===================================================================================
# --- Helper Classes for UI Interaction ---
# ===================================================================================
class CoordinatePicker:
    def __init__(self, root, callback, mode='point'):
        self.root = root; self.callback = callback; self.mode = mode; self.picker_window = bstrap.Toplevel(root)
        self.picker_window.attributes('-fullscreen', True); self.picker_window.attributes('-alpha', 0.4)
        self.picker_window.overrideredirect(True); self.picker_window.wait_visibility(self.picker_window)
        self.canvas = tk.Canvas(self.picker_window, cursor="cross", bg="black", highlightthickness=0); self.canvas.pack(fill="both", expand=True)
        initial_text = "Move to the first corner and press SPACE" if mode == 'area' else "Move mouse to desired location and press SPACE"
        self.instruction_label = bstrap.Label(self.canvas, text=initial_text, font=("Helvetica", 16, "bold"), foreground="white", background="black")
        self.instruction_label.place(relx=0.5, rely=0.5, anchor="center")
        self.current_x=0; self.current_y=0; self.start_x=None; self.start_y=None; self.rect=None; self.first_point_captured=False
        self.root.withdraw(); self.picker_window.bind("<Escape>", self.cancel); self.picker_window.bind("<Motion>", self.on_mouse_move)
        self.picker_window.bind("<space>", self.on_space_press); self.picker_window.focus_force()
    def on_mouse_move(self, event):
        self.current_x, self.current_y = event.x_root, event.y_root
        if self.mode == 'area' and self.first_point_captured: self.canvas.coords(self.rect, self.start_x, self.start_y, self.current_x, self.current_y)
    def on_space_press(self, event):
        if self.mode == 'point': self.finish(self.current_x, self.current_y)
        elif not self.first_point_captured:
            self.start_x = self.current_x; self.start_y = self.current_y; self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='red', width=2)
            self.first_point_captured = True; self.instruction_label.config(text="Move to the second corner and press SPACE to confirm")
        else:
            x1, y1, x2, y2 = min(self.start_x, self.current_x), min(self.start_y, self.current_y), max(self.start_x, self.current_x), max(self.start_y, self.current_y)
            self.finish(x1, y1, x2, y2)
    def finish(self, *coords): self.callback(*coords); self.picker_window.destroy(); self.root.deiconify()
    def cancel(self, event=None): self.picker_window.destroy(); self.root.deiconify()

class SetupWizard(CoordinatePicker):
    def __init__(self, root, steps, callback):
        self.steps = steps; self.current_step_index = -1; self.results = {}
        super().__init__(root, callback, mode='point')
        self.picker_window.withdraw(); self.next_step()
    def next_step(self):
        self.current_step_index += 1
        if self.current_step_index >= len(self.steps):
            super().finish(self.results); return
        step_info = self.steps[self.current_step_index]
        self.key, self.mode = step_info['key'], step_info['mode']
        self.first_point_captured = False; self.rect = None
        self.instruction_label.config(text=step_info['prompt'])
        self.picker_window.deiconify(); self.picker_window.focus_force()
    def on_space_press(self, event):
        if self.mode == 'point':
            self.results[self.key] = (self.current_x, self.current_y)
            self.picker_window.withdraw(); self.next_step()
        elif self.mode == 'area':
            if not self.first_point_captured:
                self.start_x, self.start_y = self.current_x, self.current_y
                self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='red', width=2)
                self.first_point_captured = True; self.instruction_label.config(text="Move to the second corner and press SPACE to confirm")
            else:
                x1, y1 = min(self.start_x, self.current_x), min(self.start_y, self.current_y)
                x2, y2 = max(self.start_x, self.current_x), max(self.start_y, self.current_y)
                self.results[self.key] = (x1, y1, x2, y2)
                self.picker_window.withdraw(); self.next_step()

class SetupSelectionDialog(bstrap.Toplevel):
    def __init__(self, parent, available_steps):
        super().__init__(parent); self.title("Select Locations to Configure"); self.transient(parent); self.grab_set(); self.position_center()
        self.available_steps = available_steps; self.selected_keys = None; self.check_vars = {}
        main_frame = bstrap.Frame(self, padding=20); main_frame.pack(fill="both", expand=True)
        bstrap.Label(main_frame, text="Check the items you want to set up:", font="-weight bold").pack(anchor="w", pady=(0, 10))
        for step in self.available_steps:
            key, label = step['key'], step['label']
            self.check_vars[key] = tk.BooleanVar(value=False)
            bstrap.Checkbutton(main_frame, text=label, variable=self.check_vars[key]).pack(anchor="w", padx=10, pady=2)
        button_frame = bstrap.Frame(main_frame, padding=(0, 20, 0, 0)); button_frame.pack(fill="x", side="bottom")
        bstrap.Button(button_frame, text="Cancel", command=self.on_cancel, bootstyle="secondary").pack(side="right", padx=(5, 0))
        bstrap.Button(button_frame, text="Start Setup", command=self.on_start, bootstyle="success").pack(side="right")
        self.wait_window()
    def on_start(self):
        self.selected_keys = [key for key, var in self.check_vars.items() if var.get()]
        if not self.selected_keys: messagebox.showwarning("No Selection", "Please select at least one item to configure.", parent=self); return
        self.destroy()
    def on_cancel(self): self.selected_keys = []; self.destroy()

class HotkeyRecorder:
    def __init__(self, parent, callback):
        self.callback = callback; self.window = bstrap.Toplevel(parent); self.window.title("Record Hotkey"); self.window.transient(parent); self.window.grab_set(); self.window.geometry("300x100")
        bstrap.Label(self.window, text="Press any key combination...\n(ESC to cancel)", font="-size 12").pack(pady=20)
        self.window.bind("<KeyPress>", self.on_key_press); self.window.bind("<Escape>", lambda e: self.window.destroy()); self.window.focus_force()
    def on_key_press(self, event):
        if event.keysym in ('Control_L', 'Control_R', 'Alt_L', 'Alt_R', 'Shift_L', 'Shift_R'): return
        parts = [mod for mod, mask in [("ctrl", 4), ("shift", 1), ("alt", 0x20000)] if event.state & mask]
        parts.append(event.keysym.lower()); self.callback("+".join(parts)); self.window.destroy()

# ===================================================================================
# SECTION 2: BOT LOGIC
# ===================================================================================
settings = {}; scan_active = False; exit_program = threading.Event()
RARE_PHOTOS = {}; RARE_NAMES = []

class BotState(Enum):
    SEARCHING = auto(); ANALYZING = auto(); ACTION_RUN = auto(); ACTION_CAPTURE = auto(); COOLDOWN = auto()

def load_bot_data_from_gui_file():
    global RARE_PHOTOS, RARE_NAMES, settings; settings_data, names_data, name_order = load_app_data(); settings = settings_data.copy()
    new_rare_photos = {name: {p_name: p_path for _, (p_name, p_path) in data.get("photos", {}).items()} for name, data in names_data.items() if name in name_order}
    RARE_PHOTOS = new_rare_photos; RARE_NAMES = name_order; print(f"[INFO] Loaded: {len(RARE_NAMES)} names, {sum(len(v) for v in RARE_PHOTOS.values())} photos.")

def items_header_detected(screen_image):
    header_region = (settings["header_topleft_x"], settings["header_topleft_y"], settings["header_bottomright_x"], settings["header_bottomright_y"])
    try:
        screen_crop = screen_image.crop(header_region)
        screen_gray = cv2.cvtColor(np.array(screen_crop), cv2.COLOR_RGB2GRAY)
        ref_gray = cv2.cvtColor(np.array(Image.open(settings["ITEMS_HEADER_PATH"]).convert("RGB")), cv2.COLOR_RGB2GRAY)
        found = cv2.minMaxLoc(cv2.matchTemplate(screen_gray, ref_gray, cv2.TM_CCOEFF_NORMED))[1] > 0.90
        return found
    except Exception as e: print(f"[ERROR] Items header detect error: {e}"); return False

def ocr_text(screen_image):
    ocr_region = (settings["ocr_topleft_x"], settings["ocr_topleft_y"], settings["ocr_bottomright_x"], settings["ocr_bottomright_y"])
    try:
        gray = cv2.cvtColor(np.array(screen_image.crop(ocr_region)), cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)
        text = pytesseract.image_to_string(thresh, config=r'--oem 3 --psm 7').replace('_', '').strip()
        return text
    except Exception as e: print(f"[ERROR] OCR failed: {e}"); return ""

def send_webhook_with_image_pil(message, pil_image):
    for url in settings["WEBHOOK_URLS"]:
        if not url: continue
        try:
            buffered = BytesIO(); pil_image.save(buffered, format="PNG"); buffered.seek(0)
            requests.post(url, data={"content": message}, files={'file': ('screenshot.png', buffered, 'image/png')}, timeout=10)
        except Exception as e: print(f"[ERROR] Webhook failed to {url}: {e}")

def move_mouse_humanlike(x, y, p_j=5, b_d=0.2, d_j=0.2):
    pyautogui.moveTo(x+random.randint(-p_j,p_j), y+random.randint(-p_j,p_j), duration=b_d+random.uniform(0,d_j), tween=pyautogui.easeInOutQuad)
    time.sleep(random.uniform(0.05, 0.12))

def ahk_run_away():
    try:
        move_mouse_humanlike(settings["mouse_x"], settings["mouse_y"]); print(f"[ACTION] Running away via AHK script.")
        subprocess.run([settings["AHK_PATH"], settings["AHK_RUNAWAY_SCRIPT"]], check=True, capture_output=True, text=True)
    except Exception as e: print(f"[ERROR] Could not run Run Away AHK script: {e}")

def find_image_on_screen(scene_img, template_path, threshold=0.8, scan_region=None):
    try:
        search_area_img, offset_x, offset_y = scene_img, 0, 0
        if scan_region: search_area_img = scene_img.crop(scan_region); offset_x, offset_y = scan_region[0], scan_region[1]
        scene_cv = cv2.cvtColor(np.array(search_area_img), cv2.COLOR_RGB2GRAY)
        template_cv = cv2.cvtColor(np.array(Image.open(template_path).convert("RGB")), cv2.COLOR_RGB2GRAY)
        res = cv2.matchTemplate(scene_cv, template_cv, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val >= threshold:
            print(f"[INFO] Image match for {os.path.basename(template_path)} with score {max_val:.3f}")
            return offset_x + max_loc[0] + template_cv.shape[1] // 2, offset_y + max_loc[1] + template_cv.shape[0] // 2
    except Exception as e: print(f"[ERROR] Image detection failed: {e}")
    return None

def compare_photos(scene_img, template_path):
    photo_region = (settings['photo_topleft_x'], settings['photo_topleft_y'], settings['photo_bottomright_x'], settings['photo_bottomright_y'])
    try:
        scene_gray = cv2.cvtColor(np.array(scene_img), cv2.COLOR_RGB2GRAY)
        template_gray = cv2.cvtColor(np.array(Image.open(template_path).convert("RGB")), cv2.COLOR_RGB2GRAY)
        scene_cropped = scene_gray[photo_region[1]:photo_region[3], photo_region[0]:photo_region[2]]
        if scene_cropped.size > 0:
            resized_template = cv2.resize(template_gray, (scene_cropped.shape[1], scene_cropped.shape[0]))
            score = ssim(resized_template, scene_cropped)
            return score
        return 0
    except Exception as e: print(f"[ERROR] Photo comparison failed: {e}"); return 0

def handle_search_state(screen_image):
    if items_header_detected(screen_image):
        print("[INFO] Encounter detected. Moving to analysis."); return BotState.ANALYZING, None
    return BotState.SEARCHING, None

def handle_analyzing_state(screen_image):
    name = ocr_text(screen_image)
    print(f"[SCAN] OCR Result: '{name}'")
    if not name: return BotState.SEARCHING, None
    matched_name = next((n for n in RARE_NAMES if n.lower() == name.lower()), None)
    if not matched_name: print(f"[INFO] Common Loomian '{name}' found."); return BotState.ACTION_RUN, None
    print(f"[SUCCESS] Rare Loomian '{matched_name}' found! Checking forms...")
    timeout = time.time() + 10
    while time.time() < timeout:
        if not scan_active or exit_program.is_set(): return BotState.SEARCHING, None
        current_frame = ImageGrab.grab()
        for photo_name, photo_path in RARE_PHOTOS.get(matched_name, {}).items():
            score = compare_photos(current_frame, photo_path)
            print(f"  - Checking '{photo_name}', Score: {score:.3f}")
            if score >= settings["photo_match_threshold"]:
                print(f"[SUCCESS] Matched form '{photo_name}' for '{matched_name}'.")
                send_webhook_with_image_pil(f"Found '{matched_name}' (Form: {photo_name})!", current_frame)
                special_forms = {f.lower() for f in settings.get("special_capture_forms", [])}
                run_away_forms = {f.lower() for f in settings.get("run_away_forms", [])}
                if photo_name.lower() in special_forms: return BotState.ACTION_CAPTURE, None
                elif photo_name.lower() in run_away_forms: return BotState.ACTION_RUN, None
                else: print("[WARNING] Rare form not in any list. Defaulting to run away."); return BotState.ACTION_RUN, None
        time.sleep(0.5)
    print(f"[WARNING] Timeout: No matching form found for '{matched_name}'.")
    send_webhook_with_image_pil(f"Found rare Loomian '{matched_name}' but form is unknown!", screen_image)
    return BotState.ACTION_RUN, None

def handle_capture_state():
    print("[ACTION] Initiating capture sequence.")
    action_scan_region = (settings["action_scan_topleft_x"], settings["action_scan_topleft_y"], settings["action_scan_bottomright_x"], settings["action_scan_bottomright_y"])
    move_mouse_humanlike(settings['capture_x'], settings['capture_y']); subprocess.run([settings["AHK_PATH"], settings["AHK_SCRIPT"]], capture_output=True, text=True)
    timeout = time.time() + 10
    while time.time() < timeout and not exit_program.is_set():
        if find_image_on_screen(ImageGrab.grab(), settings["ACE_DISC_PATH"], 0.8, scan_region=action_scan_region):
            move_mouse_humanlike(settings['ace_disc_x'], settings['ace_disc_y']); subprocess.run([settings["AHK_PATH"], settings["AHK_SCRIPT"]], capture_output=True, text=True); break
        time.sleep(0.5)
    else: print("[ERROR] Capture failed: Ace Disc not found in specified area."); return BotState.COOLDOWN, 5
    timeout = time.time() + 10
    while time.time() < timeout and not exit_program.is_set():
        if find_image_on_screen(ImageGrab.grab(), settings["USE_IMAGE_PATH"], 0.8, scan_region=action_scan_region):
            move_mouse_humanlike(settings['use_disk_x'], settings['use_disk_y']); subprocess.run([settings["AHK_PATH"], settings["AHK_SCRIPT"]], capture_output=True, text=True); break
        time.sleep(0.2)
    else: print("[ERROR] Capture failed: Use Button not found in specified area."); return BotState.COOLDOWN, 5
    print("[ACTION] Waiting for capture result..."); capture_success = False; timeout = time.time() + 25
    while time.time() < timeout and not exit_program.is_set():
        if find_image_on_screen(ImageGrab.grab(), settings["NO_BUTTON_IMAGE_PATH"], 0.8, scan_region=action_scan_region):
            move_mouse_humanlike(settings['no_button_x'], settings['no_button_y']); subprocess.run([settings["AHK_PATH"], settings["AHK_SCRIPT"]], capture_output=True, text=True)
            print("[SUCCESS] Loomian captured successfully!"); send_webhook_with_image_pil("Loomian was captured successfully.", ImageGrab.grab()); capture_success = True; break
        time.sleep(0.5)
    if not capture_success: print("[ERROR] Capture Failed: Loomian broke free or timeout occurred."); send_webhook_with_image_pil("Capture Failed: Loomian broke free or timeout.", ImageGrab.grab())
    return BotState.COOLDOWN, 5

def scan_loop():
    global scan_active; state = BotState.SEARCHING; cooldown_end_time = 0
    while not exit_program.is_set():
        if not scan_active: time.sleep(0.1); continue
        if state == BotState.COOLDOWN:
            if time.time() >= cooldown_end_time: state = BotState.SEARCHING
            else: time.sleep(0.2); continue
        try:
            screen_image = ImageGrab.grab(); next_state, cooldown_seconds = None, None
            if state == BotState.SEARCHING: next_state, _ = handle_search_state(screen_image)
            elif state == BotState.ANALYZING: next_state, _ = handle_analyzing_state(screen_image)
            elif state == BotState.ACTION_RUN: ahk_run_away(); next_state, cooldown_seconds = BotState.COOLDOWN, 3
            elif state == BotState.ACTION_CAPTURE: next_state, cooldown_seconds = handle_capture_state()
            if next_state: state = next_state
            if cooldown_seconds: cooldown_end_time = time.time() + cooldown_seconds
        except Exception as e: print(f"[FATAL_ERROR] Unhandled exception in scan_loop: {e}"); state = BotState.COOLDOWN; cooldown_end_time = time.time() + 5
        time.sleep(0.2)

def keybind_listener(app_instance):
    global scan_active
    hotkey = settings.get("pause_hotkey", "f9")
    def toggle_scan():
        global scan_active
        scan_active = not scan_active
        print(f"============== [STATUS] SCAN {'STARTED' if scan_active else 'PAUSED'} ==============")
    def failsafe_shutdown():
        app_instance.after(0, app_instance.emergency_shutdown)
    try:
        keyboard.add_hotkey(hotkey, toggle_scan)
        keyboard.add_hotkey("f12", failsafe_shutdown)
        print(f"[INFO] Hotkey listener started. Press '{hotkey}' to toggle scanning.")
        print(f"[INFO] Failsafe enabled. Press 'F12' to force close the application immediately.")
        exit_program.wait()
        keyboard.remove_hotkey(hotkey)
        keyboard.remove_hotkey("f12")
    except Exception as e:
        print(f"[ERROR] Could not register hotkey. It may be in use. Error: {e}")

# ===================================================================================
# SECTION 3: TKINTER GUI CLASSES
# ===================================================================================
class SettingsTab(bstrap.Frame):
    def __init__(self, parent, settings_dict):
        super().__init__(parent); self.settings = settings_dict; self.entries = {}
        self.canvas = tk.Canvas(self, highlightthickness=0); self.scrollbar = bstrap.Scrollbar(self, orient="vertical", command=self.canvas.yview); self.scrollable_frame = bstrap.Frame(self.canvas)
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw"); self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True); self.scrollbar.pack(side="right", fill="y")
        self.scrollable_frame.columnconfigure(0, weight=1); self.scrollable_frame.columnconfigure(1, weight=1)
        left_col = bstrap.Frame(self.scrollable_frame); left_col.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        right_col = bstrap.Frame(self.scrollable_frame); right_col.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        bstrap.Button(left_col, text="▶️ Launch Visual Setup Wizard", command=self.run_setup_wizard, bootstyle="success").pack(fill='x', padx=10, pady=10)
        locations_lf = bstrap.LabelFrame(left_col, text="Mouse Click Locations", padding=10); locations_lf.pack(fill="x", padx=10, pady=10); locations_lf.columnconfigure(1, weight=1)
        click_coords = [("Run Away Click:", "mouse_x", "mouse_y"), ("Items Button Click:", "capture_x", "capture_y"), ("Disk Item Click:", "ace_disc_x", "ace_disc_y"), ("Use Disk Click:", "use_disk_x", "use_disk_y"), ("'No' Nickname Click:", "no_button_x", "no_button_y")]
        for i, (label, xk, yk) in enumerate(click_coords):
            bstrap.Label(locations_lf, text=label).grid(row=i, column=0, sticky='w', padx=5, pady=2); entry_x = bstrap.Entry(locations_lf, width=7); entry_x.grid(row=i, column=1, sticky='ew', padx=5); entry_y = bstrap.Entry(locations_lf, width=7); entry_y.grid(row=i, column=2, sticky='ew', padx=5)
            self.entries[xk], self.entries[yk] = entry_x, entry_y; entry_x.insert(0, str(self.settings.get(xk, 100))); entry_y.insert(0, str(self.settings.get(yk, 100)))
        scan_areas_lf = bstrap.LabelFrame(left_col, text="Screen Scan Areas", padding=10); scan_areas_lf.pack(fill="x", padx=10, pady=10, expand=True)
        ocr_lf = bstrap.LabelFrame(scan_areas_lf, text="OCR (Name) Scan Area", padding=5); ocr_lf.pack(fill='x', expand=True, pady=(0,5)); ocr_lf.columnconfigure(1, weight=1)
        ocr_coords = [("Top-Left:", "ocr_topleft_x", "ocr_topleft_y"), ("Bottom-Right:", "ocr_bottomright_x", "ocr_bottomright_y")]
        for i, (label, xk, yk) in enumerate(ocr_coords):
            bstrap.Label(ocr_lf, text=label).grid(row=i, column=0, sticky='w', padx=5, pady=2); entry_x = bstrap.Entry(ocr_lf, width=7); entry_x.grid(row=i, column=1, sticky='ew', padx=5); entry_y = bstrap.Entry(ocr_lf, width=7); entry_y.grid(row=i, column=2, sticky='ew', padx=5)
            self.entries[xk], self.entries[yk] = entry_x, entry_y; entry_x.insert(0, str(self.settings.get(xk, 100))); entry_y.insert(0, str(self.settings.get(yk, 100)))
        photo_lf = bstrap.LabelFrame(scan_areas_lf, text="Photo Match Scan Area", padding=5); photo_lf.pack(fill='x', expand=True); photo_lf.columnconfigure(1, weight=1)
        photo_coords = [("Top-Left:", "photo_topleft_x", "photo_topleft_y"), ("Bottom-Right:", "photo_bottomright_x", "photo_bottomright_y")]
        for i, (label, xk, yk) in enumerate(photo_coords):
            bstrap.Label(photo_lf, text=label).grid(row=i, column=0, sticky='w', padx=5, pady=2); entry_x = bstrap.Entry(photo_lf, width=7); entry_x.grid(row=i, column=1, sticky='ew', padx=5); entry_y = bstrap.Entry(photo_lf, width=7); entry_y.grid(row=i, column=2, sticky='ew', padx=5)
            self.entries[xk], self.entries[yk] = entry_x, entry_y; entry_x.insert(0, str(self.settings.get(xk, 100))); entry_y.insert(0, str(self.settings.get(yk, 100)))
        action_scan_lf = bstrap.LabelFrame(scan_areas_lf, text="Action/Button Scan Area", padding=5); action_scan_lf.pack(fill='x', expand=True, pady=(5,0)); action_scan_lf.columnconfigure(1, weight=1)
        action_scan_coords = [("Top-Left:", "action_scan_topleft_x", "action_scan_topleft_y"), ("Bottom-Right:", "action_scan_bottomright_x", "action_scan_bottomright_y")]
        for i, (label, xk, yk) in enumerate(action_scan_coords):
            bstrap.Label(action_scan_lf, text=label).grid(row=i, column=0, sticky='w', padx=5, pady=2); entry_x = bstrap.Entry(action_scan_lf, width=7); entry_x.grid(row=i, column=1, sticky='ew', padx=5); entry_y = bstrap.Entry(action_scan_lf, width=7); entry_y.grid(row=i, column=2, sticky='ew', padx=5)
            self.entries[xk], self.entries[yk] = entry_x, entry_y; entry_x.insert(0, str(self.settings.get(xk, 0))); entry_y.insert(0, str(self.settings.get(yk, 0)))
        header_lf = bstrap.LabelFrame(scan_areas_lf, text="Header Scan Area", padding=5); header_lf.pack(fill='x', expand=True, pady=(5,0)); header_lf.columnconfigure(1, weight=1)
        header_coords = [("Top-Left:", "header_topleft_x", "header_topleft_y"), ("Bottom-Right:", "header_bottomright_x", "header_bottomright_y")]
        for i, (label, xk, yk) in enumerate(header_coords):
            bstrap.Label(header_lf, text=label).grid(row=i, column=0, sticky='w', padx=5, pady=2); entry_x = bstrap.Entry(header_lf, width=7); entry_x.grid(row=i, column=1, sticky='ew', padx=5); entry_y = bstrap.Entry(header_lf, width=7); entry_y.grid(row=i, column=2, sticky='ew', padx=5)
            self.entries[xk], self.entries[yk] = entry_x, entry_y; entry_x.insert(0, str(self.settings.get(xk, 100))); entry_y.insert(0, str(self.settings.get(yk, 100)))
        test_buttons_frame = bstrap.Frame(left_col); test_buttons_frame.pack(fill='x', padx=10, pady=(0, 10)); test_buttons_frame.columnconfigure((0,1), weight=1)
        bstrap.Button(test_buttons_frame, text="Test Header Detection", command=self.test_header_detection, bootstyle="info-outline").grid(row=0, column=0, sticky='ew', padx=(0,5))
        bstrap.Button(test_buttons_frame, text="Test OCR", command=self.test_ocr, bootstyle="info-outline").grid(row=0, column=1, sticky='ew', padx=(5,0))
        paths_lf = bstrap.LabelFrame(right_col, text="Paths & Scripts", padding=10); paths_lf.pack(fill="x", padx=10, pady=10); paths_content = bstrap.Frame(paths_lf); paths_content.pack(fill="x", padx=10, pady=5); paths_content.columnconfigure(1, weight=1)
        script_paths = [("AHK Path", "AHK_PATH", [("Executable", "*.exe")]), ("AHK Capture Script", "AHK_SCRIPT", [("AHK Script", "*.ahk")]), ("AHK Run Away Script", "AHK_RUNAWAY_SCRIPT", [("AHK Script", "*.ahk")])]
        for i, (label, key, ftypes) in enumerate(script_paths):
            bstrap.Label(paths_content, text=label).grid(row=i, column=0, sticky="w", padx=(0,10), pady=4); entry = bstrap.Entry(paths_content); entry.grid(row=i, column=1, sticky="ew"); entry.insert(0, self.settings.get(key, "")); btn = bstrap.Button(paths_content, text="Browse...", command=lambda e=entry, t=label, ft=ftypes: self.browse_path(e, title=t, filetypes=ft), bootstyle="secondary-outline"); btn.grid(row=i, column=2, sticky="ew", padx=(5,0)); self.entries[key] = entry
        bstrap.Button(paths_content, text="Test Run Away Script", command=self.test_run_away, bootstyle="info-outline").grid(row=len(script_paths), column=1, columnspan=2, sticky='ew', pady=5)
        config_lf = bstrap.LabelFrame(right_col, text="Configuration", padding=10); config_lf.pack(fill="x", padx=10, pady=10); config_content = bstrap.Frame(config_lf); config_content.pack(fill="x", padx=10, pady=5); config_content.columnconfigure(1, weight=1)
        bstrap.Label(config_content, text="Pause Hotkey").grid(row=0, column=0, sticky="w", padx=(0,10), pady=4)
        self.hotkey_var = tk.StringVar(value=self.settings.get("pause_hotkey", "F9")); self.hotkey_button = bstrap.Button(config_content, textvariable=self.hotkey_var, command=self.record_hotkey, bootstyle="secondary"); self.hotkey_button.grid(row=0, column=1, sticky="w"); self.entries["pause_hotkey"] = self.hotkey_var
        bstrap.Label(config_content, text="Match Threshold (0-1)").grid(row=1, column=0, sticky="w", padx=(0,10), pady=4); thresh_entry = bstrap.Entry(config_content); thresh_entry.grid(row=1, column=1, sticky="w"); thresh_entry.insert(0, str(self.settings.get("photo_match_threshold", 0.85))); self.entries["photo_match_threshold"] = thresh_entry
        webhook_lf = bstrap.LabelFrame(right_col, text="Webhook URLs", padding=10); webhook_lf.pack(fill="x", padx=10, pady=10); webhook_text = ScrolledText(webhook_lf, height=3, wrap="none", autohide=True); webhook_text.pack(fill="both", expand=True, padx=5, pady=5); urls = self.settings.get("WEBHOOK_URLS", []); webhook_text.insert("1.0", "\n".join(urls) if urls else ""); self.entries["WEBHOOK_URLS"] = webhook_text
        
        forms_container = bstrap.Frame(right_col); forms_container.pack(fill="x", padx=10, pady=10); forms_container.columnconfigure((0,1), weight=1)
        capture_forms_lf = bstrap.LabelFrame(forms_container, text="Special Capture Forms"); capture_forms_lf.grid(row=0, column=0, sticky="ns", padx=(0,5)); self.create_form_list_ui(capture_forms_lf, "special_capture_forms")
        run_away_forms_lf = bstrap.LabelFrame(forms_container, text="Run Away Forms"); run_away_forms_lf.grid(row=0, column=1, sticky="ns", padx=(5,0)); self.create_form_list_ui(run_away_forms_lf, "run_away_forms")
        bot_resources_lf = bstrap.LabelFrame(self.scrollable_frame, text="Bot Resources", padding=10); bot_resources_lf.grid(row=1, column=0, columnspan=2, padx=20, pady=10, sticky="ew"); bot_resources_lf.columnconfigure(1, weight=1)
        bot_resources = [("Tesseract Path", "TESSERACT_PATH", "tesseract.exe", "Select Tesseract Executable", [("Executables", "*.exe")]), ("Items Header Image", "ITEMS_HEADER_PATH", "items_header.png", "Select Items Header Image", [("Images", "*.png")]), ("Ace Disc Image", "ACE_DISC_PATH", "ace_disc.png", "Select Ace Disc Image", [("Images", "*.png")]), ("Use Button Image", "USE_IMAGE_PATH", "use_button.png", "Select Use Button Image", [("Images", "*.png")]), ("No Button Image", "NO_BUTTON_IMAGE_PATH", "no_button.png", "Select No Button Image", [("Images", "*.png")])]
        for i, (label, key, filename, title, filetypes) in enumerate(bot_resources):
            bstrap.Label(bot_resources_lf, text=label).grid(row=i, column=0, sticky="w", padx=(10,10), pady=4); entry = bstrap.Entry(bot_resources_lf); entry.grid(row=i, column=1, sticky="ew", padx=(0,5)); entry.insert(0, self.settings.get(key, ""))
            browse_command = lambda e=entry, fn=filename, t=title, ft=ftypes: self.browse_and_import_asset(e, fn, t, ft)
            if key == 'TESSERACT_PATH': browse_command = lambda e=entry: self.browse_path(e, title=title, filetypes=filetypes)
            btn = bstrap.Button(bot_resources_lf, text="Browse...", command=browse_command, bootstyle="secondary-outline"); btn.grid(row=i, column=2, sticky="ew", padx=(0,10)); self.entries[key] = entry
            if "Image" in label: bstrap.Button(bot_resources_lf, text="Preview", command=lambda e=entry: self.preview_image(e.get()), bootstyle="info-outline").grid(row=i, column=3, sticky="ew", padx=(0,10))
    def create_form_list_ui(self, parent, key):
        top = bstrap.Frame(parent); top.pack(fill="x", padx=5, pady=5); entry = bstrap.Entry(top); entry.pack(side="left", fill="x", expand=True, padx=(0,5))
        listbox = tk.Listbox(parent, height=3); listbox.pack(fill="both", expand=True, padx=5, pady=(0,5))
        def add(): listbox.insert(tk.END, entry.get().strip().lower()) if entry.get().strip().lower() and entry.get().strip().lower() not in listbox.get(0,tk.END) else None; entry.delete(0,tk.END)
        def remove(): [listbox.delete(i) for i in reversed(listbox.curselection())]
        bstrap.Button(top, text="Add", command=add, bootstyle="info").pack(side="left"); bstrap.Button(parent, text="Remove", command=remove, bootstyle="danger-outline").pack(fill="x", padx=5, pady=5)
        for form in self.settings.get(key, []): listbox.insert(tk.END, form)
        self.entries[key] = listbox
    def apply_changes(self):
        for key, widget in self.entries.items():
            if key in self.settings:
                if isinstance(widget, tk.StringVar): self.settings[key] = widget.get()
                elif isinstance(widget, tk.BooleanVar): self.settings[key] = widget.get()
                elif isinstance(widget, tk.DoubleVar): self.settings[key] = round(widget.get() / 100.0, 2)
                elif isinstance(widget, tk.Listbox): self.settings[key] = list(widget.get(0, tk.END))
                elif isinstance(widget, ScrolledText): self.settings[key] = [url.strip() for url in widget.get("1.0", tk.END).strip().split('\n') if url.strip()]
                else:
                    try: self.settings[key] = int(widget.get())
                    except (ValueError, TypeError):
                        try: self.settings[key] = float(widget.get())
                        except (ValueError, TypeError): self.settings[key] = widget.get()
    def run_setup_wizard(self):
        all_steps = [
            {'key': 'run_away', 'label': 'Run Away Click Point', 'mode': 'point', 'prompt': "Click the 'Run Away' button location and press SPACE"},
            {'key': 'items', 'label': 'Items Button Click Point', 'mode': 'point', 'prompt': "Click the 'Items' button location and press SPACE"},
            {'key': 'disk', 'label': 'Disk Item Click Point', 'mode': 'point', 'prompt': "Click the 'Ace Disc' item location and press SPACE"},
            {'key': 'use_disk', 'label': 'Use Disk Click Point', 'mode': 'point', 'prompt': "Click the 'Use' button location and press SPACE"},
            {'key': 'no_button', 'label': "'No' Nickname Click Point", 'mode': 'point', 'prompt': "Click the 'No' nickname button location and press SPACE"},
            {'key': 'scan_header_area', 'label': 'Battle Header Scan Area', 'mode': 'area', 'prompt': "Click and drag to define the BATTLE HEADER Scan Area"},
            {'key': 'scan_ocr_area', 'label': 'OCR (Name) Scan Area', 'mode': 'area', 'prompt': "Click and drag to define the OCR (Name) Scan Area"},
            {'key': 'scan_photo_area', 'label': 'Photo Match Scan Area', 'mode': 'area', 'prompt': "Click and drag to define the Photo Match Scan Area"},
            {'key': 'scan_action_area', 'label': 'Action/Button Scan Area', 'mode': 'area', 'prompt': "Drag a box around where capture buttons ('Use', 'No') appear"}
        ]
        dialog = SetupSelectionDialog(self, all_steps); selected_keys = dialog.selected_keys
        if not selected_keys: return
        steps_to_run = [step for step in all_steps if step['key'] in selected_keys]
        def wizard_callback(results):
            if not results: return
            click_key_map = {'run_away': ('mouse_x', 'mouse_y'), 'items': ('capture_x', 'capture_y'), 'disk': ('ace_disc_x', 'ace_disc_y'), 'use_disk': ('use_disk_x', 'use_disk_y'), 'no_button': ('no_button_x', 'no_button_y')}
            area_key_map = { 'scan_header_area': ('header_topleft_x', 'header_topleft_y', 'header_bottomright_x', 'header_bottomright_y'), 'scan_ocr_area': ('ocr_topleft_x', 'ocr_topleft_y', 'ocr_bottomright_x', 'ocr_bottomright_y'), 'scan_photo_area': ('photo_topleft_x', 'photo_topleft_y', 'photo_bottomright_x', 'photo_bottomright_y'), 'scan_action_area': ('action_scan_topleft_x', 'action_scan_topleft_y', 'action_scan_bottomright_x', 'action_scan_bottomright_y') }
            for key, (xk, yk) in click_key_map.items():
                if key in results: x, y = results[key]; self.entries[xk].delete(0, tk.END); self.entries[xk].insert(0, str(x)); self.entries[yk].delete(0, tk.END); self.entries[yk].insert(0, str(y))
            for key, (x1k, y1k, x2k, y2k) in area_key_map.items():
                if key in results: x1, y1, x2, y2 = results[key]; self.entries[x1k].delete(0, tk.END); self.entries[x1k].insert(0, str(x1)); self.entries[y1k].delete(0, tk.END); self.entries[y1k].insert(0, str(y1)); self.entries[x2k].delete(0, tk.END); self.entries[x2k].insert(0, str(x2)); self.entries[y2k].delete(0, tk.END); self.entries[y2k].insert(0, str(y2))
            messagebox.showinfo("Setup Complete", "Selected locations have been configured.", parent=self)
        if steps_to_run: SetupWizard(self.winfo_toplevel(), steps_to_run, wizard_callback)
    def test_header_detection(self):
        try:
            self.apply_changes(); global settings; settings = self.settings
            if not os.path.exists(settings["ITEMS_HEADER_PATH"]): messagebox.showerror("Test Error", "Items Header Image path is invalid.", parent=self); return
            found = items_header_detected(ImageGrab.grab())
            if found: messagebox.showinfo("Header Test Result", "Success: Item Header was found in the specified area.", parent=self)
            else: messagebox.showwarning("Header Test Result", "Failure: Item Header was NOT found in the specified area.", parent=self)
        except Exception as e: messagebox.showerror("Test Error", f"Failed to execute header test: {e}", parent=self)
    def test_ocr(self):
        try:
            self.apply_changes(); global settings; settings = self.settings
            tesseract_path = settings.get("TESSERACT_PATH", "");
            if not tesseract_path or not os.path.exists(tesseract_path): messagebox.showerror("OCR Test Error", "Tesseract path is not configured or is invalid.", parent=self); return
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
            text = ocr_text(ImageGrab.grab()); messagebox.showinfo("OCR Test Result", f"Detected text: '{text}'", parent=self)
        except Exception as e: messagebox.showerror("OCR Test Error", f"Could not perform OCR test: {e}", parent=self)
    def test_run_away(self):
        try:
            self.apply_changes(); global settings; settings = self.settings
            if not os.path.exists(settings['AHK_PATH']) or not os.path.exists(settings['AHK_RUNAWAY_SCRIPT']): messagebox.showerror("Test Error", "AHK path or Run Away script path is invalid.", parent=self); return
            threading.Thread(target=ahk_run_away, daemon=True).start(); messagebox.showinfo("Test", "Run Away script has been executed.", parent=self)
        except Exception as e: messagebox.showerror("Test Error", f"Failed to execute test: {e}", parent=self)
    def browse_and_import_asset(self, entry_widget, target_filename, dialog_title, filetypes):
        source_path = filedialog.askopenfilename(title=dialog_title, filetypes=filetypes);
        if not source_path: return
        try:
            dest_path = os.path.join(BOT_ASSETS_DIR, target_filename); shutil.copy2(source_path, dest_path)
            entry_widget.delete(0, tk.END); entry_widget.insert(0, dest_path); messagebox.showinfo("Asset Imported", f"'{os.path.basename(source_path)}' has been copied to '{BOT_ASSETS_DIR}' and the path has been set.")
        except Exception as e: messagebox.showerror("File Copy Error", f"Could not copy file: {e}")
    def browse_path(self, entry, title="Select a file", filetypes=[("All files", "*.*")]):
        path = filedialog.askopenfilename(title=title, filetypes=filetypes);
        if path: entry.delete(0, tk.END); entry.insert(0, path)
    def preview_image(self, path):
        if not path or not os.path.exists(path): messagebox.showwarning("Preview", "Please select a valid image file first."); return
        try:
            preview_window = bstrap.Toplevel(self); preview_window.title("Image Preview"); preview_window.geometry("500x500")
            img = Image.open(path); img.thumbnail((480, 480), Image.Resampling.LANCZOS); photo = ImageTk.PhotoImage(img)
            label = bstrap.Label(preview_window, image=photo); label.image = photo; label.pack(padx=10, pady=10)
            bstrap.Label(preview_window, text=os.path.basename(path), font="-size 10 -weight bold").pack()
        except Exception as e: messagebox.showerror("Preview Error", f"Could not preview image: {e}")
    def record_hotkey(self):
        self.hotkey_button.config(text="Press a key..."); HotkeyRecorder(self, lambda key: (self.hotkey_var.set(key), self.hotkey_button.config(text=key)))

class NamesPhotosTab(bstrap.Frame):
    def __init__(self, parent, main_app_instance, names_data_dict, name_order_list):
        super().__init__(parent); self.app = main_app_instance; self.data = names_data_dict; self.name_order = name_order_list
        self.current_image = None; self.filtered_name_order = []; self.columnconfigure(0, weight=1, minsize=200); self.columnconfigure(1, weight=3); self.rowconfigure(0, weight=1)
        names_frame = bstrap.LabelFrame(self, text="Names", padding=5); names_frame.grid(row=0, column=0, padx=(10,5), pady=10, sticky="nsew"); names_frame.rowconfigure(1, weight=1); names_frame.columnconfigure(0, weight=1)
        self.name_search_var = tk.StringVar(); name_search_entry = bstrap.Entry(names_frame, textvariable=self.name_search_var); name_search_entry.grid(row=0, column=0, sticky="ew", padx=5, pady=5); add_placeholder(name_search_entry, "Search names..."); self.name_search_var.trace_add("write", self.update_name_search)
        listbox_frame = bstrap.Frame(names_frame); listbox_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=(0,5)); listbox_frame.rowconfigure(0, weight=1); listbox_frame.columnconfigure(0, weight=1)
        self.name_list = tk.Listbox(listbox_frame, width=30, exportselection=False); self.name_list.grid(row=0, column=0, sticky="nsew"); self.name_list.bind("<<ListboxSelect>>", self.on_select_name)
        name_scroll = bstrap.Scrollbar(listbox_frame, orient="vertical", command=self.name_list.yview, bootstyle="round"); name_scroll.grid(row=0, column=1, sticky="ns"); self.name_list.config(yscrollcommand=name_scroll.set)
        self.create_toolbar(names_frame, [("➕", self.add_name), ("✏️", self.rename_name), ("🗑️", self.delete_name), ("⬆️", lambda: self.move_name(-1)), ("⬇️", lambda: self.move_name(1))]).grid(row=2, column=0, sticky="ew", padx=5, pady=5)
        photos_and_preview = bstrap.Frame(self); photos_and_preview.grid(row=0, column=1, padx=(0,10), pady=10, sticky="nsew"); photos_and_preview.columnconfigure(0, weight=2); photos_and_preview.columnconfigure(1, weight=1); photos_and_preview.rowconfigure(0, weight=1)
        photos_frame = bstrap.LabelFrame(photos_and_preview, text="Photos"); photos_frame.grid(row=0, column=0, sticky="nsew", padx=(0,5)); photos_frame.rowconfigure(1, weight=1); photos_frame.columnconfigure(0, weight=1)
        self.photo_search_var = tk.StringVar(); photo_search_entry = bstrap.Entry(photos_frame, textvariable=self.photo_search_var); photo_search_entry.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=5); add_placeholder(photo_search_entry, "Search photos..."); self.photo_search_var.trace_add("write", lambda *a: self.on_select_name())
        self.photo_tree = bstrap.Treeview(photos_frame, columns=("Photo Name", "File"), show="headings", selectmode="browse"); self.photo_tree.grid(row=1, column=0, sticky="nsew", padx=(5,0), pady=5); self.photo_tree.heading("Photo Name", text="Photo Name"); self.photo_tree.heading("File", text="File Path"); self.photo_tree.column("Photo Name", width=150); self.photo_tree.bind("<<TreeviewSelect>>", self.on_select_photo)
        style = bstrap.Style(); self.photo_tree.tag_configure('special', foreground=style.colors.success); self.photo_tree.tag_configure('runaway', foreground=style.colors.warning)
        photo_scroll = bstrap.Scrollbar(photos_frame, orient="vertical", command=self.photo_tree.yview, bootstyle="round"); photo_scroll.grid(row=1, column=1, sticky="ns", pady=5); self.photo_tree.config(yscrollcommand=photo_scroll.set)
        self.create_toolbar(photos_frame, [("➕", self.add_photo), ("✏️", self.rename_photo), ("🗑️", self.delete_photo), ("⬆️", lambda: self.move_photo(-1)), ("⬇️", lambda: self.move_photo(1))]).grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        preview_lf = bstrap.LabelFrame(photos_and_preview, text="Photo Preview"); preview_lf.grid(row=0, column=1, sticky="nsew"); self.photo_label = bstrap.Label(preview_lf, text="Select a photo to preview", anchor="center", wraplength=200); self.photo_label.pack(fill="both", expand=True, padx=5, pady=5)
        self.action_preview_label = bstrap.Label(preview_lf, text="", font="-size 10 -weight bold"); self.action_preview_label.pack(pady=(10, 0))
        bstrap.Button(preview_lf, text="Test Match vs. Screen", bootstyle="info-outline", command=self.test_match).pack(fill='x', padx=5, pady=10)
        self.filtered_name_order = self.name_order[:]; self.refresh_name_list(); self.bind_all("<Control-n>", lambda e: self.add_name()); self.bind_all("<Control-p>", lambda e: self.add_photo())
        self.name_list.bind("<Button-3>", self.show_name_context_menu); self.photo_tree.bind("<Button-3>", self.show_photo_context_menu)
    def create_toolbar(self, parent, buttons): toolbar = bstrap.Frame(parent); [bstrap.Button(toolbar, text=text, command=command, width=3, bootstyle="secondary-outline").pack(side="left", padx=2, fill='x', expand=True) for text, command in buttons]; return toolbar
    def update_name_search(self, *args): search = self.name_search_var.get().strip().lower(); self.filtered_name_order = self.name_order[:] if not search or search == "search names..." else [n for n in self.name_order if search in n.lower()]; self.refresh_name_list()
    def refresh_name_list(self):
        last_sel = self.get_selected_name(); self.name_list.delete(0, tk.END)
        for name in self.filtered_name_order: self.name_list.insert(tk.END, name)
        if last_sel and last_sel in self.filtered_name_order: idx = self.filtered_name_order.index(last_sel); self.name_list.selection_set(idx); self.name_list.activate(idx); self.name_list.see(idx)
        self.on_select_name()
    def on_select_name(self, event=None):
        for item in self.photo_tree.get_children(): self.photo_tree.delete(item)
        self.clear_photo_preview(); name = self.get_selected_name();
        if not name: return
        photos_dict, photo_order = self.data[name].get("photos", {}), self.data[name].get("photo_order", [])
        search_term, is_placeholder = self.photo_search_var.get().strip().lower(), self.photo_search_var.get() == "search photos..."
        special_forms, run_away_forms = {f.lower() for f in self.app.settings.get("special_capture_forms", [])}, {f.lower() for f in self.app.settings.get("run_away_forms", [])}
        for photo_id in photo_order:
            if photo_id in photos_dict and isinstance(photos_dict[photo_id], (list, tuple)) and len(photos_dict[photo_id]) >= 2:
                photo_name, photo_path = photos_dict[photo_id]
                if not search_term or is_placeholder or search_term in photo_name.lower():
                    tag = 'special' if photo_name.lower() in special_forms else 'runaway' if photo_name.lower() in run_away_forms else ''
                    self.photo_tree.insert("", tk.END, iid=photo_id, values=(photo_name, os.path.basename(photo_path or "N/A")), tags=(tag,))
    def on_select_photo(self, event=None):
        name, sel = self.get_selected_name(), self.photo_tree.selection();
        if not (name and sel): self.clear_photo_preview(); return
        photo_id = sel[0]; photos = self.data[name].get("photos", {})
        if photo_id in photos:
            photo_name, pic_path = photos[photo_id]; self.show_photo_preview(pic_path)
            special_forms, run_away_forms = {f.lower() for f in self.app.settings.get("special_capture_forms", [])}, {f.lower() for f in self.app.settings.get("run_away_forms", [])}
            action_text, style = ("Action: Run Away (Default)", "secondary")
            if photo_name.lower() in special_forms: action_text, style = "Action: Special Capture", "success"
            elif photo_name.lower() in run_away_forms: action_text, style = "Action: Run Away", "warning"
            self.action_preview_label.config(text=action_text, bootstyle=style)
    def clear_photo_preview(self): self.photo_label.config(image="", text="Select a photo to preview"); self.current_image = None; self.action_preview_label.config(text="", bootstyle="default")
    def show_photo_preview(self, path):
        if path and os.path.exists(path):
            try:
                self.photo_label.update_idletasks(); w, h = max(self.photo_label.winfo_width() - 10, 200), max(self.photo_label.winfo_height() - 10, 200)
                img = Image.open(path); img.thumbnail((w, h), Image.Resampling.LANCZOS); self.current_image = ImageTk.PhotoImage(img)
                self.photo_label.config(image=self.current_image, text="")
            except Exception as e: self.photo_label.config(image="", text=f"Cannot open image:\n{e}"); self.current_image = None
        else: self.clear_photo_preview()
    def _validate_photo_name(self, photo_name):
        special_forms, run_away_forms = {f.lower() for f in self.app.settings.get("special_capture_forms", [])}, {f.lower() for f in self.app.settings.get("run_away_forms", [])}
        if photo_name.lower() not in special_forms and photo_name.lower() not in run_away_forms: messagebox.showerror("Invalid Photo Name", f"The photo name '{photo_name}' is not in the 'Special Capture' or 'Run Away' form lists.\n\nPlease add it to one of those lists in the General Settings tab before adding the photo."); return False
        return True
    def add_photo(self):
        name = self.get_selected_name();
        if not name: messagebox.showerror("Error", "Please select a name first.", parent=self); return
        photo_name = simpledialog.askstring("Add Photo", "Enter a name for this photo:", parent=self)
        if not photo_name or not photo_name.strip(): return
        if not self._validate_photo_name(photo_name.strip()): return
        file_path = filedialog.askopenfilename(title="Select an image file", filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp"), ("All", "*.*")])
        if file_path:
            photo_id = str(uuid.uuid4()); png_path = save_image_as_png(file_path, name, photo_name, photo_id)
            if png_path:
                self.data[name]["photos"][photo_id] = (photo_name, png_path); self.data[name]["photo_order"].append(photo_id)
                self.on_select_name(); self.photo_tree.selection_set(photo_id); self.photo_tree.focus(photo_id); self.photo_tree.see(photo_id)
    def rename_photo(self):
        name, sel = self.get_selected_name(), self.photo_tree.selection();
        if not (name and sel): return
        photo_id = sel[0]; photos = self.data[name].get("photos", {})
        if photo_id not in photos: return
        old_pname, old_path = photos[photo_id]; new_pname = simpledialog.askstring("Rename Photo", "Enter new photo name:", initialvalue=old_pname, parent=self)
        if new_pname and new_pname.strip() and new_pname.strip() != old_pname:
            new_pname = new_pname.strip()
            if not self._validate_photo_name(new_pname): return
            new_path = save_image_as_png(old_path, name, new_pname, photo_id) if old_path else ""
            if new_path and old_path and new_path != old_path:
                try: os.remove(old_path)
                except OSError: pass
            photos[photo_id] = (new_pname, new_path); self.on_select_name(); self.photo_tree.selection_set(photo_id)
    def add_name(self):
        name = simpledialog.askstring("Add Name", "Enter a new name:", parent=self)
        if name and name.strip():
            name = name.strip();
            if name in self.data: messagebox.showerror("Error", f"Name '{name}' already exists.", parent=self); return
            self.data[name] = {"photos": {}, "photo_order": []}; self.name_order.append(name); self.update_name_search()
            if name in self.filtered_name_order: idx = self.filtered_name_order.index(name); self.name_list.selection_clear(0, tk.END); self.name_list.selection_set(idx); self.name_list.activate(idx); self.name_list.see(idx)
    def rename_name(self):
        name = self.get_selected_name();
        if not name: return
        new_name = simpledialog.askstring("Rename Name", "Enter new name:", initialvalue=name, parent=self)
        if new_name and new_name.strip() and new_name.strip() != name:
            new_name = new_name.strip()
            if new_name in self.data: messagebox.showerror("Error", f"Name '{new_name}' already exists.", parent=self); return
            idx = self.name_order.index(name); self.data[new_name] = self.data.pop(name); self.name_order[idx] = new_name; self.update_name_search()
    def delete_name(self):
        name = self.get_selected_name();
        if not name or not messagebox.askyesno("Delete Name", f"Delete '{name}' and all its photos?", parent=self, icon='warning'): return
        photos = self.data.get(name, {}).get("photos", {})
        for _, ppath in photos.values():
            if ppath and os.path.exists(ppath):
                try: os.remove(ppath)
                except OSError as e: print(f"Could not delete {ppath}: {e}")
        del self.data[name]; self.name_order.remove(name); self.update_name_search()
    def move_name(self, direction):
        name = self.get_selected_name();
        if not name or (self.name_search_var.get().strip() and self.name_search_var.get().strip() != "search names..."): return
        idx = self.name_order.index(name); new_idx = idx + direction
        if 0 <= new_idx < len(self.name_order):
            self.name_order.insert(new_idx, self.name_order.pop(idx)); self.refresh_name_list()
            self.name_list.selection_set(new_idx); self.name_list.activate(new_idx); self.name_list.see(new_idx)
    def delete_photo(self):
        name, sel = self.get_selected_name(), self.photo_tree.selection();
        if not (name and sel): return
        photo_id = sel[0]; photos, photo_order = self.data[name].get("photos", {}), self.data[name].get("photo_order", [])
        if photo_id not in photos or not messagebox.askyesno("Delete Photo", f"Delete photo '{photos[photo_id][0]}' for '{name}'?", parent=self, icon='warning'): return
        ppath = photos[photo_id][1]
        if ppath and os.path.exists(ppath):
            try: os.remove(ppath)
            except OSError: pass
        del photos[photo_id]; photo_order.remove(photo_id); self.on_select_name()
    def move_photo(self, direction):
        name, sel = self.get_selected_name(), self.photo_tree.selection();
        if not (name and sel): return
        photo_id = sel[0]; photo_order = self.data[name].get("photo_order", [])
        if photo_id not in photo_order: return
        idx = photo_order.index(photo_id); new_idx = idx + direction
        if 0 <= new_idx < len(photo_order):
            photo_order.insert(new_idx, photo_order.pop(idx)); self.on_select_name()
            self.photo_tree.selection_set(photo_id); self.photo_tree.focus(photo_id); self.photo_tree.see(photo_id)
    def get_selected_name(self): sel = self.name_list.curselection(); return self.name_list.get(sel[0]) if sel else None
    def test_match(self):
        name, sel = self.get_selected_name(), self.photo_tree.selection()
        if not (name and sel): messagebox.showwarning("Test Error", "Please select a photo to test.", parent=self); return
        photo_id = sel[0]; _, template_path = self.data[name]['photos'][photo_id]
        if not template_path or not os.path.exists(template_path): messagebox.showerror("Test Error", "Photo file path is missing or invalid.", parent=self); return
        try:
            self.app.settings_tab.apply_changes(); global settings; settings = self.app.settings
            score = compare_photos(ImageGrab.grab(), template_path); threshold = float(settings.get("photo_match_threshold", 0.85))
            messagebox.showinfo("Match Test Result", f"Comparison Score: {score:.4f}\nThreshold: {threshold}\n\nResult: {'MATCH' if score >= threshold else 'NO MATCH'}", parent=self)
        except Exception as e: messagebox.showerror("Match Test Error", f"Could not perform match test: {e}", parent=self)
    def show_name_context_menu(self, event):
        if not self.name_list.curselection(): self.name_list.selection_set(self.name_list.nearest(event.y))
        if not self.name_list.curselection(): return
        menu = Menu(self.name_list, tearoff=0)
        menu.add_command(label="Rename Name", command=self.rename_name); menu.add_command(label="Delete Name", command=self.delete_name)
        menu.add_separator(); menu.add_command(label="Move Up", command=lambda: self.move_name(-1)); menu.add_command(label="Move Down", command=lambda: self.move_name(1))
        menu.post(event.x_root, event.y_root)
    def show_photo_context_menu(self, event):
        selection_id = self.photo_tree.identify_row(event.y)
        if not selection_id: return
        self.photo_tree.selection_set(selection_id)
        menu = Menu(self.photo_tree, tearoff=0)
        menu.add_command(label="Rename Photo", command=self.rename_photo); menu.add_command(label="Delete Photo", command=self.delete_photo)
        menu.add_separator(); menu.add_command(label="Move Up", command=lambda: self.move_photo(-1)); menu.add_command(label="Move Down", command=lambda: self.move_photo(1))
        menu.add_separator(); menu.add_command(label="Test Match vs. Screen", command=self.test_match)
        menu.post(event.x_root, event.y_root)

class BotControlTab(bstrap.Frame):
    def __init__(self, parent, start_callback, stop_callback):
        super().__init__(parent, padding=20); self.start_callback, self.stop_callback = start_callback, stop_callback
        self.columnconfigure(0, weight=1); self.rowconfigure(1, weight=1)
        control_frame = bstrap.Frame(self); control_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.start_button = bstrap.Button(control_frame, text="Start Bot", command=self.start_callback, bootstyle="success", width=15); self.start_button.pack(side="left", padx=5)
        self.stop_button = bstrap.Button(control_frame, text="Stop Bot", command=self.stop_callback, bootstyle="danger", width=15, state="disabled"); self.stop_button.pack(side="left", padx=5)
        self.status_label = bstrap.Label(control_frame, text="Status: Stopped", font="-weight bold", bootstyle="secondary"); self.status_label.pack(side="left", padx=20)
        log_frame = bstrap.LabelFrame(self, text="Live Bot Log", padding=5); log_frame.grid(row=1, column=0, sticky="nsew")
        self.log_text = ScrolledText(log_frame, wrap=tk.WORD, state="disabled", autohide=True); self.log_text.pack(fill="both", expand=True)
        style = bstrap.Style.get_instance()
        self.log_text.tag_config("SUCCESS", foreground=style.colors.success); self.log_text.tag_config("ERROR", foreground=style.colors.danger); self.log_text.tag_config("FATAL_ERROR", foreground=style.colors.danger, font="-weight bold"); self.log_text.tag_config("WARNING", foreground=style.colors.warning); self.log_text.tag_config("INFO", foreground=style.colors.info); self.log_text.tag_config("ACTION", foreground=style.colors.primary); self.log_text.tag_config("SCAN", foreground=style.colors.secondary); self.log_text.tag_config("STATUS", foreground=style.colors.fg, font="-weight bold")
    def add_log(self, message):
        self.log_text.text['state'] = 'normal'
        tag_map = {"[SUCCESS]": "SUCCESS", "[ERROR]": "ERROR", "[FATAL_ERROR]": "FATAL_ERROR", "[WARNING]": "WARNING", "[INFO]": "INFO", "[ACTION]": "ACTION", "[SCAN]": "SCAN", "[STATUS]": "STATUS", "============== [STATUS]": "STATUS"}
        tag_to_apply = next((tag for prefix, tag in tag_map.items() if message.startswith(prefix)), None)
        self.log_text.insert(tk.END, message + '\n', tag_to_apply if tag_to_apply else ()); self.log_text.see(tk.END); self.log_text.text['state'] = 'disabled'

class MainApp(bstrap.Window):
    def __init__(self):
        settings_data, names_dict, name_order_list = load_app_data(); self.settings = settings_data
        initial_theme = self.settings.get("theme", "darkly")
        try: super().__init__(themename=initial_theme)
        except tk.TclError: super().__init__(themename="darkly"); self.settings["theme"] = "darkly"; initial_theme = "darkly"
        self.title("Automation & Data Manager"); self.geometry("1200x800"); self.minsize(1000, 700)
        self.protocol("WM_DELETE_WINDOW", self.on_closing); self.bot_threads, self.log_queue = [], queue.Queue()
        main_frame = bstrap.Frame(self, padding=10); main_frame.pack(fill="both", expand=True)
        self.notebook = bstrap.Notebook(main_frame); self.notebook.pack(fill="both", expand=True, pady=(0, 10))
        self.bot_control_tab = BotControlTab(self.notebook, self.start_bot, self.stop_bot)
        self.settings_tab = SettingsTab(self.notebook, self.settings)
        self.names_tab = NamesPhotosTab(self.notebook, self, names_dict, name_order_list)
        self.notebook.add(self.bot_control_tab, text="Bot Control"); self.notebook.add(self.settings_tab, text="General Settings"); self.notebook.add(self.names_tab, text="Names & Photos")
        button_frame = bstrap.Frame(main_frame); button_frame.pack(fill="x", side="bottom")
        theme_frame = bstrap.Frame(button_frame); theme_frame.pack(side="left", padx=5); bstrap.Label(theme_frame, text="Theme:").pack(side="left")
        self.theme_var = tk.StringVar(value=initial_theme)
        self.theme_chooser = ttk.Combobox(master=theme_frame, textvariable=self.theme_var, values=self.style.theme_names(), state="readonly")
        self.theme_chooser.pack(side="left", padx=5); self.theme_chooser.bind("<<ComboboxSelected>>", self.change_theme)
        save_button = bstrap.Button(button_frame, text="Save All Data", command=self.save_all_data_with_feedback, bootstyle="primary"); save_button.pack(side="right")
        self.after(100, self.process_log_queue)
    def save_all_data(self): self.settings_tab.apply_changes(); save_app_data(self.settings, self.names_tab.data, self.names_tab.name_order); self.names_tab.on_select_name()
    def save_all_data_with_feedback(self):
        try: self.save_all_data(); messagebox.showinfo("Success", "All application data has been saved successfully.")
        except Exception as e: messagebox.showerror("Save Error", f"An error occurred while saving all data: {e}")
    def start_bot(self):
        try: self.save_all_data()
        except Exception as e: messagebox.showerror("Save Error", f"Could not save settings before starting: {e}"); return
        load_bot_data_from_gui_file()
        missing_configs = [item for item, path in [("Tesseract executable path", settings.get("TESSERACT_PATH")), ("AHK Path", settings.get("AHK_PATH")), ("AHK Capture Script", settings.get("AHK_SCRIPT")), ("AHK Run Away Script", settings.get("AHK_RUNAWAY_SCRIPT")), ("Items Header Image", settings.get("ITEMS_HEADER_PATH")), ("Ace Disc Image", settings.get("ACE_DISC_PATH")), ("Use Button Image", settings.get("USE_IMAGE_PATH")), ("No Button Image", settings.get("NO_BUTTON_IMAGE_PATH"))] if not path or not os.path.exists(path)]
        if missing_configs: messagebox.showerror("Missing Configuration", "The following required configurations are missing or invalid:\n\n" + "\n".join(f"  • {item}" for item in missing_configs) + "\n\nPlease configure them in the General Settings tab and save."); return
        pytesseract.pytesseract.tesseract_cmd = settings.get("TESSERACT_PATH")
        self.bot_control_tab.status_label.config(text="Status: Loading..."); self.bot_control_tab.add_log("[STATUS] --- BOT STARTING ---")

        exit_program.clear(); scan_active = False
        self.stdout_original = sys.stdout; sys.stdout = self.QueueWriter(self.log_queue)
        self.bot_threads = [threading.Thread(target=scan_loop, daemon=True), threading.Thread(target=keybind_listener, args=(self,), daemon=True)]
        for t in self.bot_threads: t.start()
        self.bot_control_tab.start_button.configure(state="disabled"); self.bot_control_tab.stop_button.configure(state="normal")
        self.bot_control_tab.status_label.configure(text="Status: Running (Paused)", bootstyle="warning")
        self.bot_control_tab.add_log(f"[INFO] Bot is running. Press '{settings.get('pause_hotkey', 'F9')}' to start/pause scanning.")
    def stop_bot(self):
        if not self.bot_threads: return
        self.bot_control_tab.add_log("[STATUS] --- BOT STOPPING ---"); self.bot_control_tab.status_label.config(text="Status: Stopping...")
        global exit_program, scan_active
        exit_program.set(); scan_active = False
        if hasattr(self, 'stdout_original'): sys.stdout = self.stdout_original
        self.bot_threads = []
        self.bot_control_tab.start_button.configure(state="normal"); self.bot_control_tab.stop_button.configure(state="disabled")
        self.bot_control_tab.status_label.configure(text="Status: Stopped", bootstyle="secondary"); self.bot_control_tab.add_log("[STATUS] Bot stopped.")
    def process_log_queue(self):
        try:
            while True: self.bot_control_tab.add_log(self.log_queue.get_nowait().strip())
        except queue.Empty: pass
        finally: self.after(100, self.process_log_queue)
    def on_closing(self):
        if self.bot_threads:
            if messagebox.askyesno("Exit", "The bot is running. Are you sure you want to exit?\nUnsaved data will be lost."): self.stop_bot(); self.destroy()
        else:
            try: self.save_all_data()
            except Exception as e: print(f"Error saving on close: {e}")
            finally: self.destroy()
    def emergency_shutdown(self):
        print("\n" + "="*50); print("!! F12 FAILSAFE TRIGGERED - SHUTTING DOWN IMMEDIATELY !!"); print("="*50)
        global exit_program, scan_active
        exit_program.set(); scan_active = False
        self.destroy()
    def change_theme(self, event=None):
        new_theme = self.theme_var.get(); self.style.theme_use(new_theme); self.settings["theme"] = new_theme
        try: self.save_all_data()
        except Exception as e: messagebox.showerror("Theme Save Error", f"Could not save new theme setting: {e}", parent=self)
    class QueueWriter:
        def __init__(self, q): self.queue = q
        def write(self, msg):
            if msg.strip(): self.queue.put(msg)
        def flush(self): pass

# ===================================================================================
# --- Main Execution ---
# ===================================================================================

if __name__ == "__main__":
    app = MainApp()
    app.mainloop()