# Filma24 Kodi Video Add-on (`plugin.video.filma24`)

A production-ready Kodi video add-on for scraping and streaming movies and TV shows from [filma24.stream](https://filma24.stream) with subtitles and multi-server resolution.

Compatible with **Kodi 20 (Nexus)**, **Kodi 21 (Omega)**, and **Kodi 22 (Piers)** on Python 3.

---

## Features

- **Movies & TV Series**: Browse latest releases, seasons, and episodes with automatic pagination.
- **Categories & Genres**: Direct access to 14 curated genres (Action, Comedy, Horror, Romance, Thriller, Dubbed Albanian, Turkish Series, and more).
- **Interactive Search with History**:
  - Native on-screen keyboard search.
  - Remembers recent searches for quick TV remote access.
  - Context menu to delete individual search entries or clear history.
- **High-Speed Parallel Scraper**:
  - Uses `concurrent.futures.ThreadPoolExecutor` to scrape external server tabs and DooPlay AJAX endpoints in parallel.
  - Multi-host support for Vidmoly, VOE, Streamtape, Doodstream, Mixdrop, Filemoon, and more.
- **Playback Reliability**:
  - Context-aware host labels (e.g., `Me Titra SRV1 (Vidmoly)`, `Me Titra SRV2 (VOE)`).
  - Smart retry fallback dialog if a selected server is down.
  - Optional `auto_select_server` setting for hands-free instant playback.
  - Direct `.m3u8` and `.mp4` stream playback with CDN header spoofing.
- **ISP Censorship / DNS Bypass**:
  - Built-in Google DNS-over-HTTPS (DoH) resolver to seamlessly bypass ISP DNS poisoning and blocks.
- **Modern Metadata Support**:
  - Built natively with Kodi's modern `InfoTagVideo` API (eliminates Kodi 20+ deprecation warnings).
  - Displays IMDb ratings, synopsis plots, release years, and poster/fanart artwork.
- **Context Menu Integration**:
  - Quick access to add-on settings and directory refresh from any view.

---

## Installation

### Option 1: Install from Release ZIP (Recommended)
1. Download the latest `plugin.video.filma24-x.x.x.zip` from the [Releases](https://github.com/korabcenaj/plugin.video.filma24/releases) page.
2. In Kodi, navigate to **Settings** > **System** > **Add-ons**.
3. Enable **Unknown sources**.
4. Go back to **Add-ons** > **Install from zip file**.
5. Select the downloaded ZIP file and click **OK**.

### Option 2: Clone or Install via Git
Clone this repository directly into your Kodi addons folder:

- **Linux / Flatpak**:
  ```bash
  git clone https://github.com/korabcenaj/plugin.video.filma24.git ~/.var/app/tv.kodi.Kodi/data/addons/plugin.video.filma24
  ```
- **Linux (Native)**:
  ```bash
  git clone https://github.com/korabcenaj/plugin.video.filma24.git ~/.kodi/addons/plugin.video.filma24
  ```
- **Windows**:
  ```bash
  git clone https://github.com/korabcenaj/plugin.video.filma24.git "%APPDATA%\Kodi\addons\plugin.video.filma24"
  ```
- **Android**:
  ```
  /Android/data/org.xbmc.kodi/files/.kodi/addons/plugin.video.filma24
  ```

---

## Dependencies

The add-on relies on standard Kodi Python 3 runtime modules:
- `xbmc.python` (>= 3.0.0)
- `script.module.requests` (>= 2.25.1)
- `script.module.beautifulsoup4` (>= 4.9.3)
- `script.module.resolveurl` (>= 5.1.0) *(Recommended for cyberlocker stream resolution)*

> **Note**: If `script.module.resolveurl` is not installed on your system, install Gujal00's ResolveURL repository from [https://github.com/Gujal00/smrzips](https://github.com/Gujal00/smrzips).

---

## Configuration Settings

Access settings via **Add-on Settings** or directly from the main menu:

| Setting | Default | Description |
|---|---|---|
| `base_url` | `https://filma24.stream` | Target website mirror or alternate domain |
| `user_agent` | Modern Chrome Desktop UA | Browser User-Agent header for HTTP requests |
| `timeout` | `15` | Network request timeout in seconds |
| `ssl_verify` | `false` | Verify SSL certificates (disable for mirrors with invalid certificates) |
| `use_doh` | `true` | Dynamic Google DNS-over-HTTPS bypass for ISP blockades |
| `auto_select_server` | `false` | Automatically resolve and play first available stream |

---

## Building the Package

To create an installable ZIP archive:
```bash
python3 build_zip.py
```
This generates `plugin.video.filma24-1.0.0.zip` ready for distribution.

---

## Disclaimer

This add-on does not host, store, or distribute any media content. It is an open-source scraper that indexes and resolves hyperlinks publicly accessible on the web. The author is not affiliated with or responsible for any content provided by third-party hosting services.
