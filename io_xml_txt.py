#!/usr/bin/env python3
import os
import plistlib
from datetime import datetime

from pid_utils import build_song_label, get_label_with_optional_pid


# ---------- Filename & TXT helpers ----------

def sanitize_filename(name: str) -> str:
    bad_chars = '<>:"/\\|?*'
    for ch in bad_chars:
        name = name.replace(ch, "_")
    return name.strip()


def write_playlist_file(playlist_name, ordered_songs, output_path=None, note="Generated"):
    if output_path is None:
        filename = sanitize_filename(playlist_name) + ".txt"
        output_path = os.path.abspath(filename)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# Playlist: {playlist_name}\n")
        f.write(f"# {note} by apple-music-pl-generator.py\n")
        f.write(f"# Timestamp: {datetime.now().isoformat(timespec='seconds')}\n\n")
        for song in ordered_songs:
            f.write(song + "\n")

    print(f"\n✅ Playlist file written to: {output_path}")
    return output_path


def read_txt_playlist_file(path):
    songs = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            songs.append(line)
    return songs


# ---------- XML parsing (Apple Music / iTunes playlist export) ----------

def parse_xml_playlist(path):
    """
    Parse an Apple Music / iTunes XML playlist export.
    Returns: (playlist_name, [song_label, ...])
    Each song_label is:
      - '[pid=HEX] Title – Artist' if a Persistent ID is available
      - 'Title – Artist' otherwise
    """
    with open(path, "rb") as f:
        data = plistlib.load(f)

    tracks_dict = data.get("Tracks", {})
    playlists = data.get("Playlists", [])

    if not playlists:
        raise ValueError("No playlists found in XML file.")

    if len(playlists) == 1:
        chosen = playlists[0]
    else:
        print("\nMultiple playlists found in this XML:")
        for idx, pl in enumerate(playlists, start=1):
            print(f"[{idx}] {pl.get('Name', 'Unnamed Playlist')}")
        while True:
            try:
                choice = int(input("Choose a playlist index: ").strip())
                if 1 <= choice <= len(playlists):
                    chosen = playlists[choice - 1]
                    break
                else:
                    print("Invalid index.")
            except ValueError:
                print("Please enter a valid integer.")

    playlist_name = chosen.get("Name", "Unnamed Playlist")
    items = chosen.get("Playlist Items", [])

    ordered_songs = []

    for item in items:
        track_id = item.get("Track ID")
        if track_id is None:
            continue

        track = tracks_dict.get(str(track_id)) or tracks_dict.get(track_id)
        if not track:
            continue

        name = track.get("Name", "Unknown Title")
        artist = track.get("Artist")
        pid = track.get("Persistent ID")

        if artist:
            core_label = f"{name} – {artist}"
        else:
            core_label = name

        if pid:
            label = build_song_label(core_label, pid)
        else:
            label = core_label

        ordered_songs.append(label)

    if not ordered_songs:
        raise ValueError("No playlist items found in XML.")

    return playlist_name, ordered_songs


# ---------- URL cleanup integrated helper ----------

def _backup_file(path: str) -> str:
    dir_name, base = os.path.split(path)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_name = f"{base}.bak-{ts}"
    backup_path = os.path.join(dir_name, backup_name)
    with open(path, "r", encoding="utf-8") as src, open(backup_path, "w", encoding="utf-8") as dst:
        for line in src:
            dst.write(line)
    return backup_path


def _process_url_line_interactive(raw: str) -> str:
    """
    Interactive fixer for one line that involves a URL.

    Cases:
      - [url=...] Label
      - bare URL line

    Returns a new label that contains NO URL and uses the standard
    [pid=HEX] Title – Artist or Title – Artist format.
    """
    line = raw.rstrip("\n")
    s = line.strip()

    # Case: [url=...] prefix
    if s.startswith("[url="):
        closing = s.find("]")
        if closing != -1:
            url_part = s[5:closing]
            rest = s[closing + 1:].lstrip()
            print("\nFound [url=...] label:")
            print(f"  Original line: {line}")
            print(f"  URL part     : {url_part!r}")

            if rest:
                print(f"  Label part   : {rest!r}")
                new_label = get_label_with_optional_pid(rest)
                print(f"  -> Replacing with: {new_label!r}")
                return new_label
            else:
                print("  No label text after [url=...].")
                while True:
                    new_core = input(
                        "  Enter label for this song (Title – Artist, no URL): "
                    ).strip()
                    if not new_core:
                        print("  Please provide a non-empty label.")
                        continue
                    if "://" in new_core:
                        print("  URLs are not supported here. Please enter just Title – Artist.")
                        continue
                    break
                new_label = get_label_with_optional_pid(new_core)
                print(f"  -> Replacing with: {new_label!r}")
                return new_label

        print(f"\nWARNING: Malformed [url=...] line, leaving as-is:\n  {line}")
        return line

    # Case: bare URL
    if "://" in s:
        print("\nFound bare URL-only line:")
        print(f"  {line}")
        while True:
            new_core = input(
                "  Enter label for this song (Title – Artist, no URL): "
            ).strip()
            if not new_core:
                print("  Please provide a non-empty label.")
                continue
            if "://" in new_core:
                print("  URLs are not supported here. Please enter just Title – Artist.")
                continue
            break
        new_label = get_label_with_optional_pid(new_core)
        print(f"  -> Replacing with: {new_label!r}")
        return new_label

    # Shouldn't happen; caller only calls on URL-ish lines
    return line


def fix_playlist_urls(txt_path: str) -> None:
    """
    Scan txt_path for any URL-based lines and fix them interactively.

    - [url=...] Label -> canonical label via get_label_with_optional_pid(Label)
    - bare URL lines  -> prompt for Title – Artist, then PID helper

    If no URLs are found, does nothing.
    If URLs are found, creates a timestamped backup before rewriting.
    """
    try:
        with open(txt_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        print(f"❌ TXT file not found when trying to clean URLs: {txt_path}")
        return

    has_urls = any(
        (("://" in ln and not ln.lstrip().startswith("#")) or ln.lstrip().startswith("[url="))
        for ln in lines
    )
    if not has_urls:
        # Quietly do nothing if there are no URLs
        return

    print(f"\n🔍 URL-style labels detected in {txt_path}.")
    print("    This tool no longer uses URLs directly; they will be converted to proper labels.")
    backup_path = _backup_file(txt_path)
    print(f"📦 Backup of original file created at:\n  {backup_path}")

    new_lines = []
    for line in lines:
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line.rstrip("\n"))
            continue

        if stripped.startswith("[url=") or "://" in stripped:
            new_lines.append(_process_url_line_interactive(line))
        else:
            new_lines.append(line.rstrip("\n"))

    with open(txt_path, "w", encoding="utf-8") as f:
        for ln in new_lines:
            f.write(ln + "\n")

    print(f"✅ URL cleanup complete for: {txt_path}")
    print("   All songs are now stored as [pid=HEX] Title – Artist or Title – Artist only.")
