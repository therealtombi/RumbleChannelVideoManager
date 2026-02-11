# RumbleChannelVideoManager (Pro) v1.9 🗂️

**RumbleChannelVideoManager** is a powerful automation tool designed to help content creators effortlessly organize their video library. It automatically scans your uploaded videos and moves them to specific channels based on your custom rules (Title Keywords + Category), ensuring your content is always in the right place without manual sorting.

![App Screenshot](https://via.placeholder.com/800x450?text=Rumble+Channel+Video+Manager+v1.9)

## 🚀 Key Features (v1.9)

* **Smart Video Sorting:** Create rules to move videos based on Title Keywords and Category matches.
* **Mass Tagging Support:** Automatically apply a standardized set of tags to videos while moving them.
* **Swarm Processing:** Launch up to 20 concurrent worker threads to scan and update hundreds of videos in minutes.
* **Auto-Heal Driver Technology:** The app detects Chrome version mismatches and automatically downloads the correct driver to prevent crashes.
* **Intelligent Start:** Choose which page to start scanning from (e.g., skip Page 1 to keep new videos on the main feed).
* **Modern Dark UI:** A sleek, CustomTkinter interface with smooth scaling (Ctrl+Scroll) and a responsive layout.
* **Dry Run Mode:** Test your rules safely. The app will log exactly what *would* happen without actually changing your videos.

## 🛠️ Prerequisites

1.  **Operating System:** Windows 10 or 11.
2.  **Browser:** **Google Chrome** is recommended. (Brave, Opera, and Vivaldi are supported via auto-detection).

## 📦 Installation

### Option A: Standalone Executable (Recommended)
* Download `RumbleChannelVideoManager.exe`.
* **Important:** Place the `icon.ico` file in the same folder as the `.exe`.
* Double-click to launch. No Python installation required.

### Option B: Running from Source
1.  Install Python 3.10+.
2.  Install dependencies:
    ```bash
    pip install customtkinter selenium undetected-chromedriver beautifulsoup4
    ```
3.  Run the script:
    ```bash
    python rumble_manager.py
    ```

## ▶️ User Guide

### Phase 1: Authentication
1.  Click **"Open Browser to Login"**. A Chrome window will appear.
2.  Log in to your Rumble account securely.
3.  **Wait:** The app will detect your login, save your session cookies, and automatically fetch your list of Channels.
4.  Once the window closes and the log says "Login Success," you are ready.

### Phase 2: Create Rules
1.  **Title Contains:** Enter a keyword (e.g., `Gaming`).
2.  **Category Is:** (Optional) Enter a category (e.g., `Gaming`).
3.  **Target Channel:** Select the destination channel from the dropdown.
4.  **Set Tags:** (Optional) Enter tags to apply (e.g., `gameplay, ps5, review`).
5.  Click **"Add Rule"**.
    * *Tip: Use the "Edit Selected" button to modify existing rules quickly.*

### Phase 3: Execution Settings
1.  **Worker Threads:** Set to `4` for casual use, or `10-20` for high-speed batch processing.
2.  **Start Page:** Set to `2` if you want to skip the first page of videos (keeping recent uploads on your main channel).
3.  **Dry Run:** Check this box to test your rules first. Uncheck it when you are ready to make real changes.
4.  **Headless:** Keep this checked to run browsers invisibly in the background.

### Phase 4: Launch Swarm
1.  Click **"LAUNCH SWARM"**.
2.  The app will spawn worker threads to scan your video pages.
3.  Monitor the **Application Logs** panel to see matches found and actions taken.
    * `[W1] Updating: Channel -> Gaming Channel, Tags -> game, fun...`
    * `[W2] -> Already correct. Skipping.`

## 🔧 Troubleshooting

### **"Session not created" / Driver Error**
The app includes **Auto-Heal**. If your Chrome updates, the app will catch the error, determine the correct version, downgrade the driver automatically, and retry. You generally do not need to do anything.

### **Videos Not Moving?**
* Check the **Logs**: Ensure "Dry Run" is **UNCHECKED**.
* Verify Rules: Rules are case-insensitive, but ensure your target channel matches exactly (or select it from the dropdown).

### **App Crashing on Start?**
Ensure the `icon.ico` file is present in the same folder as the `.exe`.

## 📄 License
MIT License.
