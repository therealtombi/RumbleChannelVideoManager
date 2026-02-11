import sys
import os
import re

# --- HOTFIX FOR PYTHON 3.12+ REMOVAL OF DISTUTILS ---
if sys.version_info >= (3, 12):
    try:
        import setuptools
    except ImportError:
        pass
# ----------------------------------------------------

import customtkinter as ctk
from tkinter import ttk, messagebox
import threading
import queue
import time
import pickle
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import StaleElementReferenceException, ElementClickInterceptedException, \
    WebDriverException, SessionNotCreatedException

# --- CONFIGURATION ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# --- FILES ---
COOKIES_FILE = "rumble_cookies.pkl"
CHANNELS_FILE = "rumble_channels.pkl"
RULES_FILE = "rumble_rules.pkl"
SETTINGS_FILE = "rumble_settings.pkl"
ICON_FILE = "icon.ico"


# --- BROWSER DETECTION HELPER ---
def find_browsers():
    found = {"Auto-Detect": ""}
    prog_files = os.environ.get("PROGRAMFILES", "C:\\Program Files")
    prog_files_x86 = os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")
    local_app_data = os.environ.get("LOCALAPPDATA", "C:\\Users\\Default\\AppData\\Local")

    candidates = {
        "Google Chrome": [
            os.path.join(prog_files, "Google\\Chrome\\Application\\chrome.exe"),
            os.path.join(prog_files_x86, "Google\\Chrome\\Application\\chrome.exe")
        ],
        "Brave Browser": [
            os.path.join(prog_files, "BraveSoftware\\Brave-Browser\\Application\\brave.exe"),
            os.path.join(prog_files_x86, "BraveSoftware\\Brave-Browser\\Application\\brave.exe"),
            os.path.join(local_app_data, "BraveSoftware\\Brave-Browser\\Application\\brave.exe")
        ],
        "Vivaldi": [
            os.path.join(local_app_data, "Vivaldi\\Application\\vivaldi.exe")
        ],
        "Opera": [
            os.path.join(local_app_data, "Programs\\Opera\\launcher.exe"),
            os.path.join(prog_files, "Opera\\launcher.exe")
        ],
        "Opera GX": [
            os.path.join(local_app_data, "Programs\\Opera GX\\launcher.exe")
        ]
    }

    for name, paths in candidates.items():
        for path in paths:
            if os.path.exists(path):
                found[name] = path
                break
    return found


class RumbleManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- Window Setup ---
        self.title("Rumble Manager - v1.9 Skip Pages")
        self.geometry("1250x850")

        if os.path.exists(ICON_FILE):
            try:
                self.iconbitmap(ICON_FILE)
            except:
                pass

        # --- Logic State ---
        self.is_running = False
        self.rules = []
        self.page_queue = queue.Queue()
        self.drivers = []
        self.threads = []
        self.log_lock = threading.Lock()
        self.detected_browsers = find_browsers()

        # --- Variables ---
        self.browser_var = ctk.StringVar(value="Auto-Detect")
        self.manual_path_var = ctk.StringVar()
        self.thread_var = ctk.StringVar(value="4")
        self.start_page_var = ctk.StringVar(value="2")  # DEFAULT TO PAGE 2
        self.dry_run_var = ctk.BooleanVar(value=True)
        self.headless_var = ctk.BooleanVar(value=True)
        self.theme_var = ctk.StringVar(value="Dark")

        # --- Init ---
        self._setup_scaling()
        self._init_ui()
        self._load_rules()
        self._load_cached_channels()
        self._load_settings()

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # --- SMOOTH SCALING LOGIC ---
    def _setup_scaling(self):
        self.current_scale = 1.0
        self.target_scale = 1.0
        self._zoom_job = None

        self.bind("<Control-MouseWheel>", self.on_mousewheel_zoom)
        self.bind("<Control-plus>", lambda e: self.schedule_zoom(0.1))
        self.bind("<Control-equal>", lambda e: self.schedule_zoom(0.1))
        self.bind("<Control-minus>", lambda e: self.schedule_zoom(-0.1))

    def on_mousewheel_zoom(self, event):
        if event.delta > 0:
            self.schedule_zoom(0.1)
        else:
            self.schedule_zoom(-0.1)

    def schedule_zoom(self, amount):
        self.target_scale += amount
        if self.target_scale < 0.5: self.target_scale = 0.5
        if self.target_scale > 2.0: self.target_scale = 2.0
        if self._zoom_job: self.after_cancel(self._zoom_job)
        self._zoom_job = self.after(150, self.apply_zoom)

    def apply_zoom(self):
        if self.current_scale != self.target_scale:
            self.current_scale = self.target_scale
            ctk.set_widget_scaling(self.current_scale)
            ctk.set_window_scaling(self.current_scale)

    # --- UI INIT ---
    def _init_ui(self):
        # ================= TOP BAR =================
        top_frame = ctk.CTkFrame(self)
        top_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(top_frame, text="Rumble Manager", font=("Roboto", 20, "bold")).pack(side="left", padx=20)

        self.btn_login = ctk.CTkButton(top_frame, text="Open Browser to Login", command=self.perform_login, width=200)
        self.btn_login.pack(side="left", padx=10)

        self.switch_theme = ctk.CTkSwitch(top_frame, text="Dark Mode", command=self.toggle_theme,
                                          variable=self.theme_var, onvalue="Dark", offvalue="Light")
        self.switch_theme.pack(side="right", padx=20)

        # ================= BROWSER SETTINGS =================
        browser_frame = ctk.CTkFrame(self)
        browser_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(browser_frame, text="Browser Engine:", font=("Roboto", 12, "bold")).pack(side="left", padx=10)

        self.cb_browser = ctk.CTkComboBox(browser_frame, variable=self.browser_var,
                                          values=list(self.detected_browsers.keys()), width=200)
        self.cb_browser.pack(side="left", padx=5)

        ctk.CTkLabel(browser_frame, text="Or Manual Path:").pack(side="left", padx=(20, 5))
        self.entry_manual = ctk.CTkEntry(browser_frame, textvariable=self.manual_path_var, width=300,
                                         placeholder_text="C:\\Path\\To\\browser.exe")
        self.entry_manual.pack(side="left", padx=5)

        ctk.CTkButton(browser_frame, text="Browse", width=80, command=self.browse_exe).pack(side="left", padx=5)

        # ================= RULES SECTION =================
        rule_main_frame = ctk.CTkFrame(self)
        rule_main_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(rule_main_frame, text="Rules Configuration", font=("Roboto", 14, "bold")).pack(anchor="w", padx=10,
                                                                                                    pady=5)

        # Input Row
        input_frame = ctk.CTkFrame(rule_main_frame, fg_color="transparent")
        input_frame.pack(fill="x", padx=5, pady=5)

        # Col 1: Title
        ctk.CTkLabel(input_frame, text="Title Contains:").pack(side="left", padx=5)
        self.entry_title_kw = ctk.CTkEntry(input_frame, width=140)
        self.entry_title_kw.pack(side="left", padx=5)

        # Col 2: Category
        ctk.CTkLabel(input_frame, text="Category Is:").pack(side="left", padx=5)
        self.entry_cat_kw = ctk.CTkEntry(input_frame, width=140)
        self.entry_cat_kw.pack(side="left", padx=5)

        # Col 3: Channel
        ctk.CTkLabel(input_frame, text="Target Channel:").pack(side="left", padx=5)
        self.entry_target_channel = ctk.CTkComboBox(input_frame, width=200, values=["User Profile"])
        self.entry_target_channel.pack(side="left", padx=5)

        # Col 4: Tags
        ctk.CTkLabel(input_frame, text="Set Tags:").pack(side="left", padx=5)
        self.entry_tags = ctk.CTkEntry(input_frame, width=180, placeholder_text="Tag1, Tag2, Tag3")
        self.entry_tags.pack(side="left", padx=5)

        ctk.CTkButton(input_frame, text="Add Rule", command=self.add_rule, fg_color="green", width=80).pack(side="left",
                                                                                                            padx=10)

        # Treeview
        tree_frame = ctk.CTkFrame(rule_main_frame)
        tree_frame.pack(fill="x", padx=10, pady=10)

        cols = ("Title", "Category", "Target", "Tags")
        self.rule_list = ttk.Treeview(tree_frame, columns=cols, show="headings", height=6)
        self.rule_list.heading("Title", text="Title Keyword")
        self.rule_list.heading("Category", text="Category Keyword")
        self.rule_list.heading("Target", text="Target Channel")
        self.rule_list.heading("Tags", text="Tags to Apply")

        self.rule_list.column("Title", width=200)
        self.rule_list.column("Category", width=150)
        self.rule_list.column("Target", width=250)
        self.rule_list.column("Tags", width=300)

        self.rule_list.pack(side="left", fill="x", expand=True)

        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.rule_list.yview)
        sb.pack(side="right", fill="y")
        self.rule_list.configure(yscrollcommand=sb.set)

        # Button Row
        btn_row = ctk.CTkFrame(rule_main_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=5)

        ctk.CTkButton(btn_row, text="Edit Selected", command=self.edit_rule, fg_color="orange", width=150).pack(
            side="right", padx=5)
        ctk.CTkButton(btn_row, text="Delete Selected", command=self.delete_rule, fg_color="red", width=150).pack(
            side="right", padx=5)

        self.apply_treeview_theme("Dark")

        # ================= EXECUTION CONTROL =================
        exec_frame = ctk.CTkFrame(self)
        exec_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(exec_frame, text="Execution Settings", font=("Roboto", 14, "bold")).pack(anchor="w", padx=10,
                                                                                              pady=5)

        ctrl_frame = ctk.CTkFrame(exec_frame, fg_color="transparent")
        ctrl_frame.pack(fill="x", padx=10, pady=5)

        # THREADS
        ctk.CTkLabel(ctrl_frame, text="Worker Threads:").pack(side="left", padx=5)
        self.slider_threads = ctk.CTkSlider(ctrl_frame, from_=1, to=20, number_of_steps=19, width=150,
                                            command=self.update_thread_label)
        self.slider_threads.set(4)
        self.slider_threads.pack(side="left", padx=5)
        self.lbl_threads = ctk.CTkLabel(ctrl_frame, text="4")
        self.lbl_threads.pack(side="left", padx=5)

        # NEW: START PAGE
        ctk.CTkLabel(ctrl_frame, text="Start Page:").pack(side="left", padx=(20, 5))
        self.entry_start_page = ctk.CTkEntry(ctrl_frame, textvariable=self.start_page_var, width=50)
        self.entry_start_page.pack(side="left", padx=5)

        # SWITCHES
        self.sw_dry = ctk.CTkSwitch(ctrl_frame, text="Dry Run", variable=self.dry_run_var)
        self.sw_dry.pack(side="left", padx=20)

        self.sw_head = ctk.CTkSwitch(ctrl_frame, text="Headless", variable=self.headless_var)
        self.sw_head.pack(side="left", padx=20)

        # BUTTONS
        self.btn_stop = ctk.CTkButton(ctrl_frame, text="STOP", command=self.stop_processing, fg_color="red", width=80,
                                      state="disabled")
        self.btn_stop.pack(side="right", padx=10)

        self.btn_start = ctk.CTkButton(ctrl_frame, text="LAUNCH SWARM", command=self.start_swarm, fg_color="green",
                                       font=("Roboto", 12, "bold"), height=40)
        self.btn_start.pack(side="right", padx=10)

        # ================= LOGS =================
        log_frame = ctk.CTkFrame(self)
        log_frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(log_frame, text="Application Logs").pack(anchor="w", padx=5, pady=2)
        self.log_area = ctk.CTkTextbox(log_frame, font=("Consolas", 12))
        self.log_area.pack(fill="both", expand=True, padx=5, pady=5)
        self.log_area.configure(state="disabled")

    # --- THEME LOGIC ---
    def toggle_theme(self):
        mode = self.theme_var.get()
        ctk.set_appearance_mode(mode)
        self.apply_treeview_theme(mode)

    def apply_treeview_theme(self, mode):
        style = ttk.Style()
        if mode == "Dark":
            style.theme_use("default")
            style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b",
                            borderwidth=0)
            style.map('Treeview', background=[('selected', '#1f538d')])
            style.configure("Treeview.Heading", background="#3a3a3a", foreground="white", relief="flat")
            style.map("Treeview.Heading", background=[('active', '#565b5e')])
        else:
            style.theme_use("default")
            style.configure("Treeview", background="white", foreground="black", fieldbackground="white", borderwidth=0)
            style.map('Treeview', background=[('selected', '#3a7ebf')])
            style.configure("Treeview.Heading", background="#e1e1e1", foreground="black", relief="flat")
            style.map("Treeview.Heading", background=[('active', '#d0d0d0')])

    def update_thread_label(self, value):
        self.lbl_threads.configure(text=str(int(value)))

    def browse_exe(self):
        f = ctk.filedialog.askopenfilename(filetypes=[("Executables", "*.exe")])
        if f: self.manual_path_var.set(f)

    def log(self, message):
        with self.log_lock:
            self.log_area.configure(state="normal")
            self.log_area.insert("end", f"{message}\n")
            self.log_area.see("end")
            self.log_area.configure(state="disabled")
            print(message)

            # --- SETTINGS I/O ---

    def _save_settings(self):
        data = {
            "browser": self.browser_var.get(),
            "manual_path": self.manual_path_var.get(),
            "threads": self.slider_threads.get(),
            "dry": self.dry_run_var.get(),
            "head": self.headless_var.get(),
            "start_page": self.start_page_var.get()
        }
        try:
            pickle.dump(data, open(SETTINGS_FILE, "wb"))
        except:
            pass

    def _load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                data = pickle.load(open(SETTINGS_FILE, "rb"))
                self.browser_var.set(data.get("browser", "Auto-Detect"))
                self.manual_path_var.set(data.get("manual_path", ""))
                self.slider_threads.set(data.get("threads", 4))
                self.update_thread_label(data.get("threads", 4))
                self.dry_run_var.set(data.get("dry", True))
                self.headless_var.set(data.get("head", True))
                self.start_page_var.set(data.get("start_page", "2"))
            except:
                pass

    # --- DRIVER FACTORY (AUTO-HEAL) ---
    def get_driver(self, headless=False, force_version=None):
        options = uc.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-popup-blocking")
        if headless:
            options.add_argument("--blink-settings=imagesEnabled=false")

        binary_path = ""
        manual = self.manual_path_var.get()
        if manual and os.path.exists(manual):
            binary_path = manual
        else:
            choice = self.browser_var.get()
            if choice in self.detected_browsers:
                binary_path = self.detected_browsers[choice]

        if binary_path:
            options.binary_location = binary_path

        try:
            if force_version:
                self.log(f"Attempting driver launch (Version {force_version})...")
                driver = uc.Chrome(options=options, version_main=force_version)
            else:
                driver = uc.Chrome(options=options)
            return driver

        except SessionNotCreatedException as e:
            msg = str(e)
            if "This version of ChromeDriver only supports Chrome version" in msg:
                self.log("Driver Version Mismatch Detected.")
                match = re.search(r"Current browser version is (\d+)", msg)
                if match:
                    detected_version = int(match.group(1))
                    self.log(f"Detected Browser Version: {detected_version}. Downgrading driver...")
                    return self.get_driver(headless, force_version=detected_version)
            raise e

    def load_cookies(self, driver):
        if os.path.exists(COOKIES_FILE):
            driver.get("https://rumble.com/404")
            try:
                with open(COOKIES_FILE, "rb") as f:
                    cookies = pickle.load(f)
                    for c in cookies:
                        try:
                            driver.add_cookie(c)
                        except:
                            pass
            except:
                pass

    # --- LOGIN ---
    def perform_login(self):
        self._save_settings()
        threading.Thread(target=self._login_process, daemon=True).start()

    def _login_process(self):
        self.log("Launching login browser...")
        try:
            driver = self.get_driver(headless=False)
            driver.get("https://rumble.com/login.php")
            self.log("Please log in. Waiting 60s...")
            start = time.time()
            while time.time() - start < 60:
                if driver.get_cookie("u_s") or "rumble.com/account" in driver.current_url:
                    self.log("Login Success! Saving cookies...")
                    time.sleep(2)
                    pickle.dump(driver.get_cookies(), open(COOKIES_FILE, "wb"))
                    self._fetch_channels_internal(driver)
                    break
                time.sleep(1)
            driver.quit()
        except Exception as e:
            self.log(f"Login failed/closed: {e}")

    def _fetch_channels_internal(self, driver):
        self.log("Fetching channels...")
        try:
            driver.get("https://rumble.com/account/content")
            triggers = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".my-videos-nav .open-menu")))
            if triggers:
                driver.execute_script("arguments[0].click();", triggers[0])
                time.sleep(0.5)
                edit_btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".dd-menu[style*='block'] #edit")))
                driver.execute_script("arguments[0].click();", edit_btn)
                WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, "video-form")))
                driver.execute_script("arguments[0].click();",
                                      driver.find_element(By.CSS_SELECTOR, "li[data-tab='settings']"))
                time.sleep(1)
                select = Select(driver.find_element(By.ID, "channelId"))
                chans = [o.text for o in select.options]
                pickle.dump(chans, open(CHANNELS_FILE, "wb"))
                self.after(0, lambda: self.update_channel_dropdown(chans))
                self.log(f"Saved {len(chans)} channels.")
        except Exception as e:
            self.log(f"Fetch error: {e}")

    def _load_cached_channels(self):
        if os.path.exists(CHANNELS_FILE):
            try:
                chans = pickle.load(open(CHANNELS_FILE, "rb"))
                self.update_channel_dropdown(chans)
            except:
                pass

    def update_channel_dropdown(self, channels):
        self.entry_target_channel.configure(values=channels)
        if channels: self.entry_target_channel.set(channels[0])

    # --- RULES ---
    def _load_rules(self):
        if os.path.exists(RULES_FILE):
            try:
                self.rules = pickle.load(open(RULES_FILE, "rb"))
                for r in self.rules:
                    title = r.get('title', '')
                    cat = r.get('cat', '')
                    target = r.get('target', '')
                    tags = r.get('tags', '')
                    self.rule_list.insert("", "end", values=(title, cat, target, tags))
            except:
                pass

    def _save_rules(self):
        pickle.dump(self.rules, open(RULES_FILE, "wb"))

    def add_rule(self):
        t = self.entry_title_kw.get().strip()
        c = self.entry_cat_kw.get().strip()
        tg = self.entry_target_channel.get()
        tags = self.entry_tags.get().strip()

        if not tg: return
        self.rules.append({"title": t, "cat": c, "target": tg, "tags": tags})
        self.rule_list.insert("", "end", values=(t, c, tg, tags))
        self._save_rules()

    def edit_rule(self):
        sel = self.rule_list.selection()
        if not sel: return
        item = self.rule_list.item(sel[0])
        values = item['values']

        self.entry_title_kw.delete(0, "end")
        self.entry_title_kw.insert(0, values[0])
        self.entry_cat_kw.delete(0, "end")
        self.entry_cat_kw.insert(0, values[1])
        self.entry_target_channel.set(values[2])
        self.entry_tags.delete(0, "end")
        tag_val = values[3] if len(values) > 3 else ""
        self.entry_tags.insert(0, tag_val)

        self.delete_rule()

    def delete_rule(self):
        sel = self.rule_list.selection()
        if sel:
            idx = self.rule_list.index(sel[0])
            self.rule_list.delete(sel[0])
            del self.rules[idx]
            self._save_rules()

    # --- SWARM LOGIC ---
    def start_swarm(self):
        if not os.path.exists(COOKIES_FILE):
            messagebox.showerror("Error", "Login first.")
            return
        if not self.rules:
            messagebox.showerror("Error", "No rules.")
            return
        if self.is_running: return

        self._save_settings()
        self.is_running = True
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")

        # Get Start Page
        try:
            start_pg = int(self.start_page_var.get())
            if start_pg < 1: start_pg = 1
        except:
            start_pg = 1

        with self.page_queue.mutex:
            self.page_queue.queue.clear()

        # Queue pages starting from user selection
        for i in range(start_pg, start_pg + 150):
            self.page_queue.put(i)

        threading.Thread(target=self.init_workers, daemon=True).start()

    def init_workers(self):
        headless = self.headless_var.get()
        dry_run = self.dry_run_var.get()
        num_workers = int(self.slider_threads.get())

        self.log(f"Initializing {num_workers} workers...")

        for i in range(num_workers):
            if not self.is_running: break
            try:
                d = self.get_driver(headless=headless)
                self.load_cookies(d)
                self.drivers.append(d)
                self.log(f"  Worker {i + 1} Ready.")
                time.sleep(1)
            except Exception as e:
                self.log(f"  Worker {i + 1} Failed: {e}")

        self.log("All workers ready. Swarm active.")

        for i, driver in enumerate(self.drivers):
            t = threading.Thread(target=self.worker_task, args=(i + 1, driver, dry_run), daemon=True)
            self.threads.append(t)
            t.start()

    def worker_task(self, worker_id, driver, dry_run):
        while self.is_running:
            try:
                page_num = self.page_queue.get(timeout=1)
            except queue.Empty:
                break

            try:
                self.log(f"[W{worker_id}] Processing Page {page_num}...")
                driver.get(f"https://rumble.com/account/content?&pg={page_num}")

                try:
                    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".my-videos-nav")))
                except:
                    self.log(f"[W{worker_id}] Page {page_num} empty. Stopping this worker.")
                    with self.page_queue.mutex:
                        self.page_queue.queue.clear()
                    break

                soup = BeautifulSoup(driver.page_source, 'html.parser')
                navs = soup.select(".my-videos-nav")
                to_process = []

                for idx, nav in enumerate(navs):
                    row_text = ""
                    article_container = nav.find_parent("article")
                    if not article_container: article_container = nav.find_parent("div", class_="media-by-user")

                    if article_container:
                        title_el = article_container.select_one(".video-title")
                        if title_el:
                            row_text = title_el.get_text(strip=True)
                        else:
                            row_text = article_container.get_text(" ", strip=True)
                    else:
                        row_text = "Unknown"

                    match = None
                    for r in self.rules:
                        title_kw = r.get('title', '').strip()
                        cat_kw = r.get('cat', '').strip()
                        if title_kw:
                            if title_kw.lower() in row_text.lower():
                                match = r
                                break
                        elif not title_kw and cat_kw:
                            match = r
                            break

                    if match:
                        self.log(f"[W{worker_id}] [+] Match Found: {row_text[:30]}...")
                        to_process.append(idx)

                if to_process:
                    self.process_matches_on_page(worker_id, driver, to_process, dry_run)

            except Exception as e:
                self.log(f"[W{worker_id}] Error Pg {page_num}: {e}")

        self.log(f"[W{worker_id}] Finished.")

    def process_matches_on_page(self, worker_id, driver, indices, dry_run):
        for vid_idx in indices:
            if not self.is_running: break
            success = False
            for attempt in range(3):
                try:
                    driver.refresh()
                    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".my-videos-nav")))
                    triggers = driver.find_elements(By.CSS_SELECTOR, ".my-videos-nav .open-menu")
                    if vid_idx >= len(triggers): break
                    trigger = triggers[vid_idx]
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", trigger)
                    time.sleep(0.3)
                    driver.execute_script("arguments[0].click();", trigger)
                    edit_btn = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, ".dd-menu[style*='block'] #edit")))
                    time.sleep(0.2)
                    driver.execute_script("arguments[0].click();", edit_btn)
                    WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.ID, "video-form")))
                    success = True
                    break
                except (StaleElementReferenceException, ElementClickInterceptedException, WebDriverException):
                    time.sleep(1)
                except Exception:
                    break

            if not success: continue

            try:
                # 1. Grab Details from DETAILS tab (default)
                try:
                    details_tab = driver.find_element(By.CSS_SELECTOR, "li[data-tab='details']")
                    if "active" not in details_tab.get_attribute("class"):
                        driver.execute_script("arguments[0].click();", details_tab)
                        time.sleep(0.2)
                except:
                    pass

                title_val = driver.find_element(By.ID, "title").get_attribute("value")
                tags_input = driver.find_element(By.ID, "tags")
                current_tags = tags_input.get_attribute("value")

                cat_select = Select(driver.find_element(By.ID, "siteChannelId"))
                current_cat = cat_select.first_selected_option.text

                # 2. Switch to Settings to get Channel
                settings_tab = driver.find_element(By.CSS_SELECTOR, "li[data-tab='settings']")
                driver.execute_script("arguments[0].click();", settings_tab)
                time.sleep(0.5)

                chan_select = Select(driver.find_element(By.ID, "channelId"))
                current_chan = chan_select.first_selected_option.text

                # 3. Find Rule Match
                target_rule = None
                for r in self.rules:
                    t_kw = r.get('title', '').strip().lower()
                    c_kw = r.get('cat', '').strip().lower()
                    if t_kw and not c_kw:
                        if t_kw in title_val.lower(): target_rule = r; break
                    elif t_kw and c_kw:
                        if t_kw in title_val.lower() and c_kw in current_cat.lower(): target_rule = r; break
                    elif not t_kw and c_kw:
                        if c_kw in current_cat.lower(): target_rule = r; break

                if not target_rule: continue

                # 4. Calculate Changes
                target_chan_name = target_rule['target'].strip()
                target_tags_val = target_rule.get('tags', '').strip()

                needs_chan_update = False
                needs_tag_update = False

                # Check Channel (Case Insensitive Fuzzy)
                if target_chan_name and target_chan_name.lower() not in current_chan.strip().lower():
                    needs_chan_update = True

                # Check Tags
                if target_tags_val and target_tags_val != current_tags.strip():
                    needs_tag_update = True

                if needs_chan_update or needs_tag_update:
                    log_items = []
                    if needs_chan_update: log_items.append(f"Channel -> {target_chan_name}")
                    if needs_tag_update: log_items.append(f"Tags -> {target_tags_val[:15]}...")
                    self.log(f"[W{worker_id}] Updating: {', '.join(log_items)}")

                    if not dry_run:
                        # Apply Channel (We are on Settings Tab)
                        if needs_chan_update:
                            try:
                                chan_select.select_by_visible_text(target_chan_name)
                            except:
                                found = False
                                for opt in chan_select.options:
                                    if target_chan_name.lower() in opt.text.lower():
                                        chan_select.select_by_visible_text(opt.text)
                                        found = True
                                        break
                                if not found:
                                    self.log(f"[W{worker_id}] Warn: Target channel '{target_chan_name}' not found.")

                        # Apply Tags (Switch back to Details)
                        if needs_tag_update:
                            driver.execute_script("arguments[0].click();", details_tab)
                            time.sleep(0.5)
                            tags_input = driver.find_element(By.ID, "tags")
                            tags_input.clear()
                            tags_input.send_keys(target_tags_val)

                        # Save
                        save_btn = driver.find_element(By.CSS_SELECTOR, ".overlay-dialog .buttons [id='0']")
                        driver.execute_script("arguments[0].click();", save_btn)
                        time.sleep(1.5)
                        self.log(f"[W{worker_id}] -> Saved.")
                    else:
                        self.log(f"[W{worker_id}] -> Dry Run: Changes Skipped.")
                else:
                    self.log(f"[W{worker_id}] -> Already correct.")

            except Exception as e:
                self.log(f"[W{worker_id}] Edit Glitch: {str(e).splitlines()[0]}")

    def stop_processing(self):
        self.is_running = False
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.log("Stopping swarm...")

    def on_close(self):
        self.is_running = False
        self.log("Closing drivers...")
        for d in self.drivers:
            try:
                d.quit()
            except:
                pass
        self.destroy()


if __name__ == "__main__":
    app = RumbleManagerApp()
    app.mainloop()