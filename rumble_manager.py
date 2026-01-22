import sys
import os

# --- HOTFIX FOR PYTHON 3.12+ REMOVAL OF DISTUTILS ---
if sys.version_info >= (3, 12):
    try:
        import setuptools
    except ImportError:
        pass
# ----------------------------------------------------

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
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
    WebDriverException

# --- FILES ---
COOKIES_FILE = "rumble_cookies.pkl"
CHANNELS_FILE = "rumble_channels.pkl"
RULES_FILE = "rumble_rules.pkl"
ICON_FILE = "icon.ico"  # Place an .ico file in the same folder


class RumbleManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Rumble Channel Video Manager - v1.0 Release")
        self.root.geometry("1100x800")

        # --- 1. SET CUSTOM ICON ---
        if os.path.exists(ICON_FILE):
            try:
                self.root.iconbitmap(ICON_FILE)
            except Exception:
                pass  # Fallback to default if icon is corrupt/invalid

        # --- 2. APPLY MODERN THEME ---
        self.style = ttk.Style()
        self.style.theme_use("clam")  # 'clam' is generally cleaner than 'default' or 'winnative'

        # Customize Colors & Fonts
        bg_color = "#f0f0f0"
        self.root.configure(bg=bg_color)

        # Configure Frames
        self.style.configure("TLabelframe", background=bg_color, relief="solid", borderwidth=1)
        self.style.configure("TLabelframe.Label", background=bg_color, font=("Segoe UI", 10, "bold"), foreground="#333")

        # Configure Buttons
        # Green 'Action' Button
        self.style.configure("Green.TButton", font=("Segoe UI", 10, "bold"), background="#4CAF50", foreground="white",
                             borderwidth=0)
        self.style.map("Green.TButton", background=[("active", "#45a049")])

        # Red 'Stop' Button
        self.style.configure("Red.TButton", font=("Segoe UI", 10, "bold"), background="#f44336", foreground="white",
                             borderwidth=0)
        self.style.map("Red.TButton", background=[("active", "#d32f2f")])

        # Blue 'Login' Button
        self.style.configure("Blue.TButton", font=("Segoe UI", 9), background="#2196F3", foreground="white",
                             borderwidth=0)
        self.style.map("Blue.TButton", background=[("active", "#1976D2")])

        # Standard Button
        self.style.configure("TButton", font=("Segoe UI", 9))

        # --- APP STATE ---
        self.is_running = False
        self.rules = []
        self.font_size = 10
        self.page_queue = queue.Queue()
        self.drivers = []
        self.threads = []
        self.log_lock = threading.Lock()

        self._setup_ui()
        self._load_rules()
        self._load_cached_channels()

        self.root.bind("<Control-MouseWheel>", self.zoom_ui)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _setup_ui(self):
        # Using ttk.LabelFrame for better styling
        # Padding=(left, top, right, bottom)

        # --- 1. Session Section ---
        top_frame = ttk.LabelFrame(self.root, text=" 1. Session Management ", padding=(15, 10))
        top_frame.pack(fill="x", padx=15, pady=10)

        self.lbl_info = ttk.Label(top_frame, text="Log in to Rumble to enable automation.", font=("Segoe UI", 9))
        self.lbl_info.pack(side="left", padx=5)

        self.btn_login = ttk.Button(top_frame, text="Open Browser to Login", style="Blue.TButton",
                                    command=self.perform_login)
        self.btn_login.pack(side="right", padx=5)

        # --- 2. Rules Section ---
        rule_frame = ttk.LabelFrame(self.root, text=" 2. Rules Configuration ", padding=(15, 10))
        rule_frame.pack(fill="x", padx=15, pady=5)

        # Input Grid
        input_frame = ttk.Frame(rule_frame)
        input_frame.pack(fill="x", pady=5)

        ttk.Label(input_frame, text="Title Contains:").grid(row=0, column=0, padx=5, sticky="w")
        self.entry_title_kw = ttk.Entry(input_frame, width=20)
        self.entry_title_kw.grid(row=0, column=1, padx=5, sticky="w")

        ttk.Label(input_frame, text="Category Is:").grid(row=0, column=2, padx=5, sticky="w")
        self.entry_cat_kw = ttk.Entry(input_frame, width=20)
        self.entry_cat_kw.grid(row=0, column=3, padx=5, sticky="w")

        ttk.Label(input_frame, text="Target Channel:").grid(row=0, column=4, padx=5, sticky="w")
        self.entry_target_channel = ttk.Combobox(input_frame, width=25)
        self.entry_target_channel.grid(row=0, column=5, padx=5, sticky="w")

        ttk.Button(input_frame, text="Add Rule", command=self.add_rule).grid(row=0, column=6, padx=15, sticky="e")

        # Separator
        ttk.Separator(rule_frame, orient="horizontal").pack(fill="x", pady=10)

        # Treeview (Table)
        self.rule_list = ttk.Treeview(rule_frame, columns=("Title", "Category", "Target"), show="headings", height=5)
        self.rule_list.heading("Title", text="Title Keyword")
        self.rule_list.heading("Category", text="Category Keyword")
        self.rule_list.heading("Target", text="Target Channel")

        # Style the Treeview
        self.rule_list.column("Title", width=200)
        self.rule_list.column("Category", width=150)
        self.rule_list.column("Target", width=250)
        self.rule_list.pack(fill="x", pady=5)

        ttk.Button(rule_frame, text="Delete Selected Rule", command=self.delete_rule).pack(anchor="e", pady=5)

        # --- 3. Execution Section ---
        action_frame = ttk.LabelFrame(self.root, text=" 3. Execution Control ", padding=(15, 10))
        action_frame.pack(fill="x", padx=15, pady=5)

        # Thread Control
        thread_frame = ttk.Frame(action_frame)
        thread_frame.pack(side="left")
        ttk.Label(thread_frame, text="Workers (Threads):").pack(side="left", padx=(0, 5))
        self.spin_threads = ttk.Spinbox(thread_frame, from_=1, to=30, width=5)
        self.spin_threads.pack(side="left")
        self.spin_threads.set(4)

        # Checkboxes
        self.dry_run_var = tk.BooleanVar(value=True)
        self.chk_dry = ttk.Checkbutton(action_frame, text="Dry Run Mode (Safe)", variable=self.dry_run_var)
        self.chk_dry.pack(side="left", padx=20)

        self.headless_var = tk.BooleanVar(value=True)
        self.chk_head = ttk.Checkbutton(action_frame, text="Run in Background (Headless)", variable=self.headless_var)
        self.chk_head.pack(side="left", padx=5)

        # Main Buttons
        self.btn_stop = ttk.Button(action_frame, text="STOP ALL", style="Red.TButton", command=self.stop_processing)
        self.btn_stop.pack(side="right", padx=5)

        self.btn_run = ttk.Button(action_frame, text="LAUNCH SWARM", style="Green.TButton", command=self.start_swarm)
        self.btn_run.pack(side="right", padx=5)

        # --- 4. Logs Section ---
        log_frame = ttk.LabelFrame(self.root, text=" Application Logs (Ctrl+Scroll to Zoom) ", padding=(10, 10))
        log_frame.pack(fill="both", expand=True, padx=15, pady=10)

        self.log_area = scrolledtext.ScrolledText(log_frame, state='disabled', height=10, font=("Consolas", 10),
                                                  bg="#1e1e1e", fg="#00ff00", insertbackground="white")
        self.log_area.pack(fill="both", expand=True)

    def log(self, message):
        with self.log_lock:
            self.log_area.config(state='normal')
            self.log_area.insert(tk.END, f"{message}\n")
            self.log_area.see(tk.END)
            self.log_area.config(state='disabled')
            # Only print to console if running from python directly
            if not getattr(sys, 'frozen', False):
                print(message)

    def zoom_ui(self, event):
        if event.delta > 0:
            self.font_size += 1
        else:
            self.font_size = max(6, self.font_size - 1)
        self.log_area.configure(font=("Consolas", self.font_size))

        # Scale Treeview row height with font
        style = ttk.Style()
        style.configure("Treeview", font=("Segoe UI", self.font_size), rowheight=int(self.font_size * 2.5))
        style.configure("Treeview.Heading", font=("Segoe UI", self.font_size, "bold"))

    # --- DRIVER FACTORY (FIXED) ---
    def get_driver(self, headless=False):
        options = uc.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-popup-blocking")
        if headless:
            options.add_argument("--blink-settings=imagesEnabled=false")

        # --- FIX: Force Version 143 to match your installed Chrome ---
        driver = uc.Chrome(options=options, version_main=143)
        return driver

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
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".my-videos-nav .open-menu"))
            )
            if triggers:
                driver.execute_script("arguments[0].click();", triggers[0])
                time.sleep(0.5)
                edit_btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".dd-menu[style*='block'] #edit"))
                )
                driver.execute_script("arguments[0].click();", edit_btn)
                WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, "video-form")))
                driver.execute_script("arguments[0].click();",
                                      driver.find_element(By.CSS_SELECTOR, "li[data-tab='settings']"))
                time.sleep(1)
                select = Select(driver.find_element(By.ID, "channelId"))
                chans = [o.text for o in select.options]
                pickle.dump(chans, open(CHANNELS_FILE, "wb"))
                self.root.after(0, lambda: self.update_channel_dropdown(chans))
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
        self.entry_target_channel['values'] = channels

    # --- RULES ---
    def _load_rules(self):
        if os.path.exists(RULES_FILE):
            try:
                self.rules = pickle.load(open(RULES_FILE, "rb"))
                for r in self.rules:
                    self.rule_list.insert("", tk.END, values=(r['title'], r['cat'], r['target']))
            except:
                pass

    def _save_rules(self):
        pickle.dump(self.rules, open(RULES_FILE, "wb"))

    def add_rule(self):
        t, c, tg = self.entry_title_kw.get().strip(), self.entry_cat_kw.get().strip(), self.entry_target_channel.get().strip()
        if not tg: return
        self.rules.append({"title": t, "cat": c, "target": tg})
        self.rule_list.insert("", tk.END, values=(t, c, tg))
        self._save_rules()

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

        self.is_running = True
        with self.page_queue.mutex:
            self.page_queue.queue.clear()

        # Add 150 pages to the queue
        for i in range(1, 151):
            self.page_queue.put(i)

        threading.Thread(target=self.init_workers, daemon=True).start()

    def init_workers(self):
        headless = self.headless_var.get()
        dry_run = self.dry_run_var.get()

        try:
            num_workers = int(self.spin_threads.get())
        except:
            num_workers = 4

        self.log(f"Initializing {num_workers} workers... (This may take a moment)")

        for i in range(num_workers):
            if not self.is_running: break
            try:
                d = self.get_driver(headless=headless)
                self.load_cookies(d)
                self.drivers.append(d)
                self.log(f"  Worker {i + 1} Ready.")
                time.sleep(1)
            except Exception as e:
                self.log(f"  Worker {i + 1} Failed to start: {e}")

        self.log("All workers ready. Starting swarm.")

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
                    parent = nav.find_parent("div", class_="media-by-user") or nav.find_parent("tr") or nav.find_parent(
                        "div")

                    if parent:
                        title_el = parent.select_one("h3, .media-heading-name, .title")
                        if title_el:
                            row_text = title_el.get_text(strip=True)
                        else:
                            row_text = parent.get_text(" ", strip=True)

                    match = None
                    for r in self.rules:
                        t_ok = (not r['title']) or (r['title'].lower() in row_text.lower())
                        if t_ok:
                            match = r
                            break

                    if match:
                        log_title = row_text[:40] + "..." if len(row_text) > 40 else row_text
                        self.log(f"[W{worker_id}] [+] Match: {log_title}")
                        to_process.append(idx)

                if to_process:
                    self.process_matches_on_page(worker_id, driver, to_process, dry_run)

            except Exception as e:
                self.log(f"[W{worker_id}] Error on Pg {page_num}: {e}")

        self.log(f"[W{worker_id}] Finished.")

    def process_matches_on_page(self, worker_id, driver, indices, dry_run):
        for vid_idx in indices:
            if not self.is_running: break

            # --- RETRY & STABILITY LOOP ---
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
                except Exception as e:
                    break

            if not success:
                self.log(f"[W{worker_id}] Could not open video #{vid_idx + 1}. Skipping.")
                continue

            # --- EDITING LOGIC ---
            try:
                cat_select = Select(driver.find_element(By.ID, "siteChannelId"))
                current_cat = cat_select.first_selected_option.text

                driver.execute_script("arguments[0].click();",
                                      driver.find_element(By.CSS_SELECTOR, "li[data-tab='settings']"))
                time.sleep(0.5)

                chan_select = Select(driver.find_element(By.ID, "channelId"))
                current_chan = chan_select.first_selected_option.text
                title_val = driver.find_element(By.ID, "title").get_attribute("value")

                target = None
                for r in self.rules:
                    t_ok = (not r['title']) or (r['title'].lower() in title_val.lower())
                    c_ok = (not r['cat']) or (r['cat'].lower() in current_cat.lower())
                    if t_ok and c_ok:
                        target = r['target']
                        break

                if target and target != current_chan:
                    self.log(f"[W{worker_id}] -> Updating '{title_val[:20]}...' to {target}")
                    try:
                        chan_select.select_by_visible_text(target)
                        if not dry_run:
                            save_btn = driver.find_element(By.CSS_SELECTOR, ".overlay-dialog .buttons [id='0']")
                            driver.execute_script("arguments[0].click();", save_btn)
                            time.sleep(1.5)
                        else:
                            self.log(f"[W{worker_id}] -> Dry Run: Save Skipped")
                    except Exception as e:
                        self.log(f"[W{worker_id}] -> Select Error: {e}")

            except Exception as e:
                err = str(e).split('\n')[0]
                self.log(f"[W{worker_id}] Edit Glitch: {err}")

    def stop_processing(self):
        self.is_running = False
        self.log("Stopping swarm...")

    def on_close(self):
        self.is_running = False
        self.log("Closing drivers... (Please wait)")
        # Safe close to avoid WinError 6
        for d in self.drivers:
            try:
                d.quit()
            except OSError:
                pass  # Ignore handle invalid errors during forced exit
            except Exception:
                pass
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = RumbleManagerApp(root)
    root.mainloop()