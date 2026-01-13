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


class RumbleManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Rumble Manager - Industrial Swarm")
        self.root.geometry("1100x800")

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
        # 1. Session
        top_frame = tk.LabelFrame(self.root, text="1. Session", padx=10, pady=10)
        top_frame.pack(fill="x", padx=10, pady=5)

        self.btn_login = tk.Button(top_frame, text="Open Browser to Login",
                                   command=self.perform_login, bg="#e1f5fe")
        self.btn_login.pack(side="left", padx=5)

        # 2. Rules
        rule_frame = tk.LabelFrame(self.root, text="2. Rules", padx=10, pady=10)
        rule_frame.pack(fill="x", padx=10, pady=5)

        input_frame = tk.Frame(rule_frame)
        input_frame.pack(fill="x", pady=5)

        tk.Label(input_frame, text="Title Contains:").pack(side="left")
        self.entry_title_kw = tk.Entry(input_frame, width=15)
        self.entry_title_kw.pack(side="left", padx=5)

        tk.Label(input_frame, text="Category Is:").pack(side="left")
        self.entry_cat_kw = tk.Entry(input_frame, width=15)
        self.entry_cat_kw.pack(side="left", padx=5)

        tk.Label(input_frame, text="Target Channel:").pack(side="left")
        self.entry_target_channel = ttk.Combobox(input_frame, width=25)
        self.entry_target_channel.pack(side="left", padx=5)

        tk.Button(input_frame, text="Add Rule", command=self.add_rule).pack(side="left", padx=10)

        self.rule_list = ttk.Treeview(rule_frame, columns=("Title", "Category", "Target"), show="headings", height=4)
        self.rule_list.heading("Title", text="Title Keyword")
        self.rule_list.heading("Category", text="Category Keyword")
        self.rule_list.heading("Target", text="Target Channel")
        self.rule_list.pack(fill="x", pady=5)

        tk.Button(rule_frame, text="Delete Selected", command=self.delete_rule).pack(anchor="e")

        # 3. Execution
        action_frame = tk.LabelFrame(self.root, text="3. Execution", padx=10, pady=10)
        action_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(action_frame, text="Threads:").pack(side="left", padx=(5, 2))
        self.spin_threads = tk.Spinbox(action_frame, from_=1, to=30, width=3)
        self.spin_threads.pack(side="left", padx=5)
        self.spin_threads.delete(0, "end")
        self.spin_threads.insert(0, 4)

        self.dry_run_var = tk.BooleanVar(value=True)
        tk.Checkbutton(action_frame, text="Dry Run", variable=self.dry_run_var).pack(side="left", padx=10)

        self.headless_var = tk.BooleanVar(value=True)
        tk.Checkbutton(action_frame, text="Run Headless", variable=self.headless_var).pack(side="left", padx=10)

        self.btn_run = tk.Button(action_frame, text="LAUNCH SWARM", command=self.start_swarm,
                                 bg="#c8e6c9", font=("Arial", 11, "bold"))
        self.btn_run.pack(side="right", padx=5)

        self.btn_stop = tk.Button(action_frame, text="STOP ALL", command=self.stop_processing,
                                  bg="#ffcdd2", font=("Arial", 10))
        self.btn_stop.pack(side="right", padx=5)

        # Logs
        log_frame = tk.LabelFrame(self.root, text="Logs", padx=10, pady=10)
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.log_area = scrolledtext.ScrolledText(log_frame, state='disabled', height=10)
        self.log_area.pack(fill="both", expand=True)

    def log(self, message):
        with self.log_lock:
            self.log_area.config(state='normal')
            self.log_area.insert(tk.END, f"{message}\n")
            self.log_area.see(tk.END)
            self.log_area.config(state='disabled')
            print(message)

    def zoom_ui(self, event):
        if event.delta > 0:
            self.font_size += 1
        else:
            self.font_size = max(6, self.font_size - 1)
        self.log_area.configure(font=("Arial", self.font_size))
        style = ttk.Style()
        style.configure("Treeview", font=("Arial", self.font_size), rowheight=int(self.font_size * 2.5))
        style.configure("Treeview.Heading", font=("Arial", self.font_size, "bold"))

    # --- DRIVER FACTORY ---
    def get_driver(self, headless=False):
        options = uc.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-popup-blocking")
        if headless:
            options.add_argument("--blink-settings=imagesEnabled=false")

        driver = uc.Chrome(options=options)
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
        driver = self.get_driver(headless=False)
        try:
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
        finally:
            driver.quit()

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
                        # Improved logic: Try to get H3 first, else get row text
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
                    # Always refresh before interaction in a swarm to clear gray overlays
                    driver.refresh()
                    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".my-videos-nav")))

                    triggers = driver.find_elements(By.CSS_SELECTOR, ".my-videos-nav .open-menu")
                    if vid_idx >= len(triggers): break

                    # 1. Open Menu
                    trigger = triggers[vid_idx]
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", trigger)
                    time.sleep(0.3)  # Throttle
                    driver.execute_script("arguments[0].click();", trigger)

                    # 2. Click Edit
                    edit_btn = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, ".dd-menu[style*='block'] #edit")))
                    time.sleep(0.2)  # Throttle
                    driver.execute_script("arguments[0].click();", edit_btn)

                    # 3. Wait for Modal
                    WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.ID, "video-form")))

                    success = True
                    break  # Success, move to editing
                except (StaleElementReferenceException, ElementClickInterceptedException, WebDriverException):
                    # self.log(f"[W{worker_id}] Click failed, retrying...")
                    time.sleep(1)
                except Exception as e:
                    # Suppress ugliness
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
                # Handle unexpected crashes inside edit modal gracefully
                err = str(e).split('\n')[0]
                self.log(f"[W{worker_id}] Edit Glitch: {err}")

    def stop_processing(self):
        self.is_running = False
        self.log("Stopping swarm...")

    def on_close(self):
        self.is_running = False
        for d in self.drivers:
            try:
                d.quit()
            except:
                pass
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = RumbleManagerApp(root)
    root.mainloop()