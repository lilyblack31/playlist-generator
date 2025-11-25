# 🎵 Apple Music Playlist Generator & Sync Tool - Personal Project for b-cd.app daily streaming missions

**A fully automated, PID-aware playlist editor & builder for Apple Music — with round-robin scheduling, colorized CLI, XML import, TXT master files, and direct AppleScript syncing.**

This tool lets you:

* Create or edit playlists stored in TXT format
* Import playlist metadata from Apple Music XML exports (including Persistent IDs)
* Add, rename, substitute, and re-count songs
* Maintain **song identity using Persistent IDs (PIDs)**
* Automatically generate **evenly spaced playlists** with round-robin “min-gap” spacing
* Apply playlists directly to Apple Music using AppleScript (no Shortcuts needed!)
* Preserve or update playlist descriptions
* Enjoy a clean, colorized interactive CLI powered by `questionary` + ANSI colors

---

## ✨ Features

### 📘 1. TXT-based Master Format

Each playlist lives as a clean `.txt` file containing lines like:

```
[pid=ABC123DEF4567890] Yet To Come – BTS
[pid=...] Title – Artist
Title – Artist
```

This format survives:

* Editing
* Reordering
* Rebuilding your Apple Music playlists

### 🧠 2. PID-Aware Song Identification

Whenever possible, songs are stored and matched by:

**`[pid=HEX] Title – Artist`**

This ensures:

* No duplicate confusion
* No ambiguous title matching
* Exact linking to your Apple Music Library items

### 🔄 3. Round-Robin Spacing Engine

This scheduler guarantees that repeated tracks are spaced out so as to maintain good streaming practice:

* Preferred gap = 3
* Fallback gap = 2
* Never allows repeats with gap = 1
* Uses max-heap + cooldown algorithm for best correctness

If impossible, the tool **explains why** and suggests fixes.

### 🎨 4. Interactive Editing (Add, Substitute, Recount, Attach PID)

Use a menu-driven interface:

* **A)** Add songs
* **S)** Substitute existing songs
* **C)** Change counts
* **P)** Attach or overwrite PID
* **D)** Set playlist description
* **Q)** Finish editing

### 🎧 5. Direct Apple Music Integration (AppleScript)

After generating your TXT, you can directly apply it:

* Clear playlist or append
* Add tracks by PID
* If PID missing: fallback to Title–Artist match
* URL-based tracks are disallowed (avoids flaky behavior)
* Only songs *already in your Library* are added
* SILENT + background-safe — no autoplay required

### 📝 6. Playlist Description Support

* Reads the **existing description** from Music.app
* Lets you **replace, keep, or generate defaults**
* Default uses **UTC date**:
  *Example*:
  `bcd daily missions – Nov 25`

---

## 📁 Project Structure

```
playlist-generator/
│
├── apple-music-pl-generator.py     # Main UI + workflow
├── apple_music_bridge.py           # AppleScript integration
├── pid_utils.py                    # PID parsing + label building
├── editor.py                       # A/S/C/P/D editing menus
├── scheduler.py                    # Round-robin spacing algorithm
├── io_xml_txt.py                   # XML parsing, TXT read/write, URL cleanup
├── colors.py                       # ANSI color helpers
├── *.txt                           # Your playlist master files
└── *.xml                           # Apple Music XML exports (optional)
```

---

## 🚀 Usage

### 1. Activate your virtual environment (optional but recommended)

```bash
source .venv/bin/activate
```

### 2. Run the main script

```bash
python3 apple-music-pl-generator.py
```

### 3. Choose what you want to do

Use arrow keys + Enter:

* **Work on existing playlist (TXT)**
* **Create new playlist**
* **Sync TXT from XML**
* **Exit**

### 4. Edit your songs

Menus will guide you (Add, Substitute, Recount, Attach PID…).

### 5. Generate & apply

Once you write the TXT file, the tool will:

* Clean URL-like lines
* Ask if you want to push updates to Apple Music
* Handle playlist description updates
* Apply via AppleScript

---

## 🖥 Requirements

* macOS (because it relies on AppleScript + Music.app)
* Python 3.9+
* Basic package dependencies (`pip install package_name`):

  * `questionary`
  * `plistlib`
  * No external API keys required

---

## ⚠️ Limitations

Can be run on macOS only :( and will need you to allow Terminal or your Python interpreter to control Music.app (Automation permissions). 
To avoid unstable behavior, the tool **does not add Apple Music URLs** directly.
Tracks must already be in your **Library**, not just in a playlist you follow.

If a song is missing:

* Add it to your library
* Re-run the tool

---

## 🗺️ Possible To-Do's:

### 🔜 **1. Spotify Linking**

### 🔜 **2. Autocomplete Search on Add/Substitute**

### 🔜 **3. Smart PID Extractor**

### 🔜 **4. Backup & Versioning**

### 🔜 **5. Playlist Analytics**

---

Complementing BCD's Daily Streaming Missions to create similar playlist in Apple Music (albeit locally)
