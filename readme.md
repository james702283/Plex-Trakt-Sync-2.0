# Plex-Trakt Sync v2.0: The Definitive Modern Sync Dashboard

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg) ![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg) ![Framework](https://img.shields.io/badge/framework-Flask-green.svg)

**Plex-Trakt Sync v2.0** is a sophisticated, self-hosted web application that completely redefines how you synchronize your media watch history between your personal Plex Media Server and your Trakt.tv account. Built from the ground up to overcome the critical limitations of prior "golden standard" solutions, this version delivers a **modern, professional, and feature-packed experience** that makes synchronization **accessible and powerful for all users**, not just advanced coders.

Where others settled for rudimentary terminal scripts, Plex-Trakt Sync v2.0 introduces a **sleek, intuitive UI** combined with a **much stronger and unique feature set**, all while maintaining a **smaller operational footprint**. It stands as a testament to pushing boundaries, bringing features never before available in a single, cohesive application.

---

![Plex-Trakt Sync Dashboard](Assets-demo.gif)

---

## Key Features & Enhancements

Plex-Trakt Sync v2.0 delivers an unparalleled synchronization experience with its comprehensive set of features and significant enhancements:

*   **Polished & Responsive Web Interface:**
    *   A clean, modern UI built with Flask and Tailwind CSS provides a professional and intuitive dashboard for all operations.
    *   **Revitalized Settings Modal:** The "Settings" modal is fully responsive, allowing users to **load, modify, and persistently save all configuration options** (including API keys, sync direction, interval, and feature checkboxes) reliably to `config.json`.
*   **Advanced Authentication & Control:**
    *   **Seamless, Secure Authentication:** Utilizes the latest OAuth2 Device and PIN flows for both Trakt and Plex, ensuring **secure, fully functional, and easy authorization** without ever needing to manually expose passwords. This includes **reliable initiation, token acquisition, and persistent credential saving**, resolving past unresponsiveness.
    *   **Manual & Automated Syncing:** Run a sync on-demand with a single click or set a schedule for automated, hands-off synchronization. The "Interval (hours)" input on the main dashboard offers **dynamic and persistent control** over automated sync schedules.
    *   **Granular Library Selection:** From the settings, users can **easily fetch and select specific Plex libraries** for synchronization, providing granular control over synced content.
    *   **Intuitive Sync Control:** Dedicated "Run Sync Now" and "Stop Sync" buttons offer **immediate and responsive control** over active sync processes, with clear visual feedback (e.g., "Syncing..." state).

*   **Comprehensive Live Sync Monitoring:**
    *   **Real-time Live Log Stream:** The "Live Progress" tab now offers a **complete, real-time log stream from the backend**, displaying all INFO, WARN, ERROR, and FATAL messages for immediate operational insight.
    *   **Dynamic `tqdm` Progress Bar Mirroring (Directory Opus Aesthetic):** This is a groundbreaking feature. The detailed `tqdm` progress bar, showing **scanning percentages, current/total items, the current library name, precise items/second transfer rates, and elapsed/remaining time, is accurately mirrored from the terminal directly into the UI's live log panel.** This provides a visually rich, **"file transfer" like experience** for real-time progress monitoring.
    *   **Dynamic Status Panel:** The main "Live Status" panel **dynamically updates in real-time** to reflect the current sync status (Idle/Syncing) and the specific library being scanned, staying perfectly in sync with the detailed log below.
    *   **Dual Log Output:** Enjoy the flexibility of simultaneously monitoring detailed sync progress in both your terminal and the web UI.

*   **Accurate Data & Visual Histories:**
    *   **Precision "Items Scanned" Counter:** The "Items Synced" field in the "Sync History" tab has been **accurately relabeled to "Items Scanned." This count now precisely reflects the total number of movies and individual episodes processed during a scan**, providing a clear and reliable measure of the sync's scope for each run, a fundamental fix that resolved previous inaccuracies.
    *   **Timezone-Aware Watched History:** When syncing watched history from Plex to Trakt, the application now **correctly identifies your server's local timezone and converts Plex's watch timestamps to UTC before sending them to Trakt.** This ensures all watched times displayed on Trakt.tv (and within the Trakt History tab) are perfectly accurate to your local viewing time, resolving previous discrepancies.
    *   **Dedicated & Live Plex "In Progress" Tab:** A new "In Progress" tab now **directly fetches and displays your Plex server's live "Continue Watching" (On Deck) items in real-time.** This provides an immediate and dynamic overview of your current Plex activity.
        *   **Robust Poster Loading:** Features **accurate poster retrieval from The Movie Database (TMDb)** for both movies and **TV show episodes**. The system intelligently handles cases where episode-specific IDs might be missing from Plex by **falling back to extracting GUIDs from the parent TV show**, ensuring posters always load reliably.
        *   **Resilient Display:** The tab's backend logic is **robust against items with incomplete or malformed metadata** in Plex's "On Deck" list, preventing crashes and ensuring a stable and informative display.
    *   **Definitive Trakt Visual History:** The "Trakt History" tab provides the ultimate confirmation of a successful sync. It efficiently fetches and renders a fluid, chronological list of your entire watch history from Trakt.tv, complete with poster art sourced from TMDb, perfectly mirroring your official Trakt profile.

*   **Backend Stability & Performance:**
    *   **Optimized Sync Speed:** The core Plex to Trakt scanning process now runs at its **maximum possible speed**, with all prior artificial `time.sleep` delays during library scanning completely removed. This ensures efficient processing for even the largest media libraries.
    *   **Robust API Resilience:** The application is built to be exceptionally resilient. Its **industry-leading `@retry` decorator implementation** is consistently applied to all API interactions, automatically handling network errors and Trakt API rate limits with intelligent exponential backoff.
    *   **Centralized State Management (`state.py`):** Key application state variables and threading locks are **centralized in a dedicated `state.py` file**, significantly improving code organization, readability, and preventing complex multi-threading issues and race conditions.
    *   **Robust Plugin Architecture:** All sync plugins are designed for modularity and correctly import and access shared state variables, guaranteeing the smooth and crash-free operation of all enabled sync features.
    *   **Predictable Scheduler Behavior:** The automatic sync scheduler accurately schedules the first run for the full configured interval (e.g., 6 hours after launch or settings save), preventing unexpected immediate syncs upon application startup.

## Technical Architecture

This application employs a sophisticated, multi-layered architecture designed for stability, scalability, and a seamless user experience, pushing beyond traditional limitations.

*   **Backend:** A robust **Flask** web server, served by the production-ready **Waitress** WSGI, efficiently handles all API requests and complex business logic. It provides a lightweight yet powerful foundation.
*   **Frontend:** A dynamic, single-page application powered exclusively by **vanilla JavaScript** for high performance and styled with **Tailwind CSS** for a modern, responsive, and sleek design.
*   **Plex Integration:** Utilizes the `PlexAPI` library for stable and reliable communication with the user's Plex Media Server, including fetching "On Deck" items, library details, and managing watch states.
*   **Trakt Integration (A Hybrid & Optimized Approach):**
    *   **Sync Logic:** The core synchronization engine leverages the `pytrakt` library, applying meticulously tested and optimized logic for matching and submitting watched history.
    *   **History & Progress Display:** To overcome `pytrakt`'s rate-limiting and data structure inconsistencies for efficient UI display, custom **direct, authenticated API calls using the `requests` library** are made to Trakt's `sync/history` and `sync/playback` endpoints with `extended=full` data. This hybrid approach ensures the UI remains exceptionally fast, reliable, and provides comprehensive, accurate data without impacting core sync operations.
*   **Metadata:** Rich poster art and metadata are consistently fetched from **The Movie Database (TMDb)** API, ensuring high-quality visuals across the dashboard without influencing Trakt API rate limits.
*   **Real-time Progress Capture:** A custom `TqdmToLog` class intercepts and processes the output of `tqdm` progress bars, transforming raw terminal output into structured data that is streamed to the UI, enabling the dynamic live progress display.
*   **Centralized State Management:** A dedicated `state.py` module centralizes all global application state variables, threading locks, and critical counters (like `ITEMS_PROCESSED_COUNT`), ensuring robust, thread-safe, and highly maintainable management of real-time sync progress and logs.
*   **Data Persistence:**
    *   `config.json`: Securely stores all user settings, API credentials, and authorization tokens, automatically updated via the UI.
    *   `sync_history.json`: Maintains a chronological log of the last 50 sync runs, including duration and accurately tracked "items scanned," for transparent activity tracking and debugging.

## Overcoming the "Impossible" Challenge

A central challenge of this project was delivering a rich, interactive experience and fetching a user's complete, chronological Trakt watch history and live Plex "Continue Watching" lists—tasks frequently deemed "impossible" or too complex for a self-hosted dashboard. This project rises to that challenge:

1.  **Robust ID Matching:** The application meticulously handles complex ID matching across Plex, Trakt, and TMDb to ensure accurate synchronization and metadata display.
2.  **Optimized API Interactions:** The `pytrakt` library is leveraged for its core sync strengths, while direct `requests` calls are employed where greater efficiency and data richness are required for the UI, bypassing common library limitations and rate-limit headaches.
3.  **Real-time UI Mirroring:** The innovative integration of `tqdm` output redirection with custom logging precisely mirrors backend scanning progress directly into the web UI, providing a level of transparency and interactivity rarely seen.
4.  **Accurate Metric Tracking:** Fundamental to its reliability, the application features a precisely engineered system for tracking "items scanned," providing true, verifiable metrics of each sync operation's scope.

This hybrid, custom-engineered approach is the key to the application's unique success, providing features and a level of detail and control previously unavailable in this category of software.

## Installation & Setup

1.  **Clone the Repository:**
    ```bash
    git clone [your-repo-url]
    cd [your-repo-name]
    ```

2.  **Set up a Python Virtual Environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install Dependencies:**
    *   Ensure your `requirements.txt` file is up-to-date. It should include:
        ```text
        Flask==3.1.1
        PlexAPI==4.17.0
        requests==2.32.4
        trakt==3.4.0
        waitress==3.0.2
        APScheduler==3.10.4
        tzlocal==5.2
        tqdm==4.66.1
        ```
    *   Then, install using:
        ```bash
        pip install -r requirements.txt
        ```

4.  **Run the Application:**
    ```bash
    python app.py
    ```
    The application will automatically open a new tab in your web browser at `http://localhost:8080`.

## Usage

1.  **First-Time Setup:**
    *   On first launch, the **Settings** modal will appear.
    *   Fill in your **Plex Server URL** and your **Trakt Client ID & Secret**.
    *   Click **Authorize Plex** and follow the on-screen instructions to link your Plex account. Your Plex Token will be filled in automatically.
    *   Click **Authorize Trakt** and follow the on-screen instructions to link your Trakt account.
    *   Click **Save Settings**.
    *   In Settings, select the Plex libraries you wish to sync.
    *   Click **Save Settings** again.

2.  **Running a Sync:**
    *   Click the **Run Sync Now** button on the main dashboard.
    *   Monitor the detailed output and progress in the **Live Progress** tab.

3.  **Viewing History:**
    *   The **Sync History** tab shows a log of past sync runs, including duration and the number of items scanned.
    *   The **Trakt History** tab provides a rich, visual confirmation of your current watched history on Trakt. It will automatically refresh after a sync is completed.
    *   The **In Progress** tab gives a live overview of what you're currently watching on Plex.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.