#!/usr/bin/env python3
import os
import questionary
import editor
from collections import Counter
from datetime import datetime, timezone
from scheduler import generate_round_robin
from pid_utils import get_label_with_optional_pid
from io_xml_txt import (
    parse_xml_playlist,
    write_playlist_file,
    read_txt_playlist_file,
    sanitize_filename,
    fix_playlist_urls,
)
from apple_music_bridge import (
    maybe_apply_to_apple_music,
    update_playlist_description,
    get_playlist_description,
)
from colors import (
    FG_GREEN,
    FG_YELLOW,
    FG_RED,
    FG_CYAN,
    FG_MAGENTA,
    FG_GRAY,
    BOLD,
    RESET,
    color,
)


# ---------- Helper: choose base playlist (TXT list + new) ----------

def choose_base_playlist_name():
    """
    Show a list of TXT playlists in the current directory with an arrow-key menu.
    Also allow entering a completely new playlist name.
    Returns the base name WITHOUT .txt extension.
    """
    txt_files = sorted(
        [f for f in os.listdir(".") if f.lower().endswith(".txt")]
    )

    if not txt_files:
        # No existing TXT files → just ask for a new name
        base = questionary.text(
            "Enter playlist base name (without extension):"
        ).ask()
        return (base or "").strip()

    choices = [
        questionary.Choice(title=f, value=f[:-4])  # strip .txt
        for f in txt_files
    ]
    choices.append(
        questionary.Choice(
            title="➕ Create a NEW playlist…",
            value="__NEW__"
        )
    )

    answer = questionary.select(
        "Select a TXT playlist, or choose 'Create a NEW playlist…':",
        choices=choices,
        qmark="🎵",
        instruction="Use ↑/↓ to move, Enter to select",
    ).ask()

    if answer is None:
        # User hit Ctrl+C / Esc
        return ""

    if answer == "__NEW__":
        base = questionary.text(
            "Enter NEW playlist base name (without extension):"
        ).ask()
        return (base or "").strip()

    # answer is an existing base name (without .txt)
    return answer


# ---------- Helper: description handling ----------

def handle_playlist_description_update(playlist_name: str) -> None:
    """
    1) Fetch current description from Apple Music.
    2) Use editor.PLAYLIST_DESCRIPTION if set, otherwise:
         - If current desc is empty, offer a default template.
         - If current desc exists and no custom desc, do nothing unless user explicitly wants change.
    3) Show current vs new, and confirm before applying update.
    """
    # Try to read current description from Apple Music
    current = get_playlist_description(playlist_name).strip()
    if current.startswith("ERROR:"):
        print(f"⚠️ Could not read current playlist description: {current}")
        return

    # Custom description from the editor (D option)
    pending = getattr(editor, "PLAYLIST_DESCRIPTION", "").strip()

    if pending:
        new_desc = pending
    else:
        # No custom pending description
        if current:
            # There is already a description in Apple Music; leave it alone by default.
            print("\nCurrent playlist description in Apple Music:")
            print(f"  {current}")
            change = questionary.confirm(
                "A description already exists. Do you want to replace it?",
                default=False,
            ).ask()
            if not change:
                return

            # If they *do* want to change it, prompt for a new one (no default template forced)
            new_desc = questionary.text(
                "Enter new playlist description (leave blank to cancel):"
            ).ask() or ""
            if not new_desc.strip():
                print("No new description entered. Keeping existing description.")
                return
        else:
            # No description in Apple Music + no pending custom → propose default template
            default_desc = f"{playlist_name} – {datetime.now(timezone.utc).strftime('%b %d')}"
            use_default = questionary.confirm(
                "This playlist currently has no description.\n"
                f"Apply a default description?\n  \"{default_desc}\"",
                default=True,
            ).ask()
            if not use_default:
                return
            new_desc = default_desc

    # At this point we have a new_desc to apply.
    print("\n--- Playlist Description Preview ---")
    if current:
        print("Current description:")
        print(f"  {current}")
    else:
        print("Current description: (none)")

    print("\nNew description to apply:")
    print(f"  {new_desc}")

    confirm = questionary.confirm(
        "Update playlist description to the above?",
        default=True,
    ).ask()
    if not confirm:
        print("Description update cancelled.")
        return

    result = update_playlist_description(playlist_name, new_desc)
    print(f"Playlist description update result: {result}")


# ---------- Helper: apply TXT -> Apple Music (+ description) ----------

def apply_to_apple_music_with_description(playlist_name: str, txt_path: str) -> None:
    """
    1) Clean any URL-style labels from TXT (interactive if needed).
    2) Call maybe_apply_to_apple_music to push the tracks.
    3) Then handle playlist description update (current vs new + optional default).
    """
    # Ensure TXT is URL-free and in canonical label format
    fix_playlist_urls(txt_path)

    # This function usually prompts Y/N and does the clear+rebuild
    maybe_apply_to_apple_music(playlist_name, txt_path)

    # Handle playlist description (show current, optionally apply new/default)
    handle_playlist_description_update(playlist_name)


# ---------- Unified "work on playlist" flow (XML preferred) ----------

def resolve_xml_path(base):
    """
    Ask user if they have XML, and if so, resolve its path.
    Returns:
      None if user says no XML
      absolute path to XML file if yes/provided
    """
    ans = input(
        "Do you have an Apple Music XML export to use as base? "
        "(Y/n or enter XML file path): "
    ).strip()

    if ans == "" or ans.lower() in ("y", "yes"):
        # Try default <base>.xml or ask for it
        default_xml = os.path.abspath(base + ".xml")
        if os.path.isfile(default_xml):
            use_default = input(
                f"Found default XML '{default_xml}'. Use this? [Y/n]: "
            ).strip().lower()
            if use_default in ("", "y", "yes"):
                return default_xml

        # Ask user for a path
        path = input("Enter XML file path: ").strip()
        if not path:
            return None
        xml_path = os.path.abspath(path)
        if os.path.isfile(xml_path):
            return xml_path
        else:
            print(color("❌ XML file not found. Continuing without XML.", FG_RED, BOLD))
            return None

    elif ans.lower() in ("n", "no"):
        return None
    else:
        # Treat ans as a possible path
        xml_path = os.path.abspath(ans)
        if os.path.isfile(xml_path):
            return xml_path
        else:
            print(color("❌ XML file not found. Continuing without XML.", FG_RED, BOLD))
            return None


def new_playlist_flow(default_name=None):
    print(color("\n--- New Playlist (from scratch) ---", FG_MAGENTA, BOLD))
    while True:
        try:
            n = int(input("Number of unique songs: ").strip())
            if n <= 0:
                print("Please enter a positive integer.")
                continue
            break
        except ValueError:
            print("Please enter a valid integer.")

    tracks = []
    for i in range(1, n + 1):
        print(f"\nSong {i}:")
        raw_label = questionary.text(
            "  Enter song label (Title – Artist or [pid=...] Title – Artist):"
        ).ask()
        if not raw_label:
            print("  (blank, skipped)")
            continue
        label = get_label_with_optional_pid(raw_label)
        while True:
            try:
                count = int(input("  How many times? ").strip())
                if count <= 0:
                    print("  Please enter a positive integer.")
                    continue
                break
            except ValueError:
                print("  Please enter a valid integer.")
        tracks.append({"name": label, "count": count})

    if default_name:
        use_default = questionary.confirm(
            f"Use playlist name '{default_name}'?",
            default=True,
        ).ask()
        if use_default:
            playlist_name = default_name
        else:
            playlist_name = questionary.text("Playlist name:").ask() or default_name
    else:
        playlist_name = questionary.text("\nPlaylist name:").ask() or ""

    if not playlist_name:
        print(color("❌ No playlist name given.", FG_RED, BOLD))
        return

    print("\nGenerating round-robin order...")
    ordered = generate_round_robin(tracks)
    txt_path = write_playlist_file(playlist_name, ordered)

    # Apply to Apple Music (with URL cleanup + description handling)
    apply_to_apple_music_with_description(playlist_name, txt_path)


def work_on_playlist_flow():
    """
    Ask for a base playlist name and:
      - Ask user about XML and use it if provided
      - Else use <name>.txt if present
      - Else notify user and switch to creation mode
    """
    print(color("\n--- Work on a Playlist (XML if provided, else TXT, else create new) ---", FG_MAGENTA, BOLD))
    base = choose_base_playlist_name()
    if not base:
        print(color("❌ No name given.", FG_RED, BOLD))
        return

    txt_path = os.path.abspath(base + ".txt")

    # Ask about XML
    xml_path = resolve_xml_path(base)

    if xml_path:
        # Use XML as base
        print(f"\nUsing XML export: {xml_path}")
        try:
            xml_playlist_name, ordered_songs = parse_xml_playlist(xml_path)
        except Exception as e:
            print(color(f"❌ Failed to parse XML: {e}", FG_RED, BOLD))
            return

        print(f"\nImported playlist from XML as: {xml_playlist_name}")
        use_xml_name = questionary.confirm(
            f"Use XML playlist name '{xml_playlist_name}' for the TXT file?",
            default=True,
        ).ask()

        if use_xml_name:
            playlist_name = xml_playlist_name
        else:
            playlist_name = questionary.text(
                "Enter playlist name to use for TXT:"
            ).ask() or xml_playlist_name

        counter = Counter(ordered_songs)
        editor.edit_playlist_counts(counter)

        tracks = [{"name": name, "count": count} for name, count in counter.items()]
        ordered = generate_round_robin(tracks)
        txt_path = write_playlist_file(playlist_name, ordered, output_path=txt_path)

        # Apply to Apple Music (with URL cleanup + description handling)
        apply_to_apple_music_with_description(playlist_name, txt_path)

    else:
        # No XML → try TXT
        if os.path.isfile(txt_path):
            print(f"\nUsing TXT file: {txt_path}")
            songs = read_txt_playlist_file(txt_path)
            if not songs:
                print(color("❌ No songs found in TXT file (non-comment lines).", FG_RED, BOLD))
                return

            playlist_name = base
            counter = Counter(songs)
            editor.edit_playlist_counts(counter)

            tracks = [{"name": name, "count": count} for name, count in counter.items()]
            ordered = generate_round_robin(tracks)
            txt_path = write_playlist_file(playlist_name, ordered, output_path=txt_path)

            # Apply to Apple Music (with URL cleanup + description handling)
            apply_to_apple_music_with_description(playlist_name, txt_path)
        else:
            # Neither XML nor TXT found → switch to creation
            print(color("⚠️ Neither XML nor TXT found for that name.", FG_YELLOW, BOLD))
            print(color("Switching to creation mode for a new playlist.", FG_YELLOW, BOLD))
            new_playlist_flow(default_name=base)


def sync_txt_from_xml_flow():
    """
    Take an XML export and rewrite a TXT file to match it exactly.
    This is useful if you manually changed the Apple Music playlist
    and want the TXT master to reflect that (names/order/counts).
    """
    print(color("\n--- Sync TXT from XML (preserve Apple Music order) ---", FG_MAGENTA, BOLD))
    path = input("Enter XML file path: ").strip()
    if not path:
        print(color("❌ No path given.", FG_RED, BOLD))
        return

    xml_path = os.path.abspath(path)
    if not os.path.isfile(xml_path):
        print(color("❌ XML file not found.", FG_RED, BOLD))
        return

    try:
        xml_playlist_name, ordered_songs = parse_xml_playlist(xml_path)
    except Exception as e:
        print(color(f"❌ Failed to parse XML: {e}", FG_RED, BOLD))
        return

    print(f"\nImported playlist from XML as: {xml_playlist_name}")
    use_xml_name = questionary.confirm(
        f"Use XML playlist name '{xml_playlist_name}' for TXT file name?",
        default=True,
    ).ask()

    if use_xml_name:
        playlist_name = xml_playlist_name
    else:
        playlist_name = questionary.text(
            "Enter playlist name / base name for TXT:"
        ).ask() or xml_playlist_name

    txt_path = os.path.abspath(sanitize_filename(playlist_name) + ".txt")
    # Write TXT preserving original order (no round-robin here)
    txt_path = write_playlist_file(
        playlist_name,
        ordered_songs,
        output_path=txt_path,
        note="Synced from Apple Music XML (original order preserved)"
    )

    # Apply to Apple Music (with URL cleanup + description handling)
    apply_to_apple_music_with_description(playlist_name, txt_path)
    print(color("✅ TXT has been synced to match the Apple Music playlist.", FG_GREEN, BOLD))


# ---------- Main menu ----------

def main_menu_choice():
    print("\n")
    return questionary.select(
        "Choose an option:",
        choices=[
            questionary.Choice(
                "Work on a playlist (XML if provided, else TXT, else create new)", value="1"
            ),
            questionary.Choice(
                "New playlist (from scratch, manual name)", value="2"
            ),
            questionary.Choice(
                "Sync TXT from XML only (no edits, preserve order)", value="3"
            ),
            questionary.Choice("Exit", value="0"),
        ],
        qmark="🎧",
    ).ask()


def main():
    print(color("\n Apple Music Playlist Tool ", FG_MAGENTA, BOLD)
      + color("(XML-aware, TXT master, AppleScript integration)", FG_CYAN))
    print(color("=" * 71, FG_MAGENTA))
    while True:
        choice = main_menu_choice()

        if choice == "1":
            work_on_playlist_flow()
        elif choice == "2":
            new_playlist_flow()
        elif choice == "3":
            sync_txt_from_xml_flow()
        elif choice == "0":
            print("Bye!")
            break
        else:
            # This shouldn't happen with questionary, but just in case
            print("Please choose 1, 2, 3, or 0.")


if __name__ == "__main__":
    main()
