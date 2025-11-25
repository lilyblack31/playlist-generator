#!/usr/bin/env python3
"""
PID / label helper utilities shared by the playlist generator and AppleScript bridge.
"""

PID_PREFIX = "[pid="
URL_PREFIX = "[url="


def label_has_pid(label: str) -> bool:
    """Return True if the label starts with a [pid=...] prefix (ignoring leading spaces)."""
    return label.lstrip().startswith(PID_PREFIX)


def extract_pid(label_or_pid: str):
    """
    Try to pull a PID out of:
      - '[pid=ABC123...] Title – Artist'
      - '[pid=ABC123...]'
      - 'pid=ABC123...'
      - 'ABC123...' (plain hex)
    Returns the PID string (no [pid=] wrapper) or None.
    """
    s = label_or_pid.strip()
    if not s:
        return None

    # Full label like "[pid=ABC123...] Title – Artist"
    if s.startswith(PID_PREFIX):
        closing = s.find("]")
        if closing != -1:
            return s[len(PID_PREFIX):closing].strip()

    # Just "pid=ABC123..." or "PID=..."
    if s.lower().startswith("pid="):
        return s[4:].strip()

    # Heuristic: 16-char hex (the usual Music persistent ID)
    hex_candidate = s.replace(" ", "")
    if len(hex_candidate) == 16 and all(c in "0123456789ABCDEFabcdef" for c in hex_candidate):
        return hex_candidate.upper()

    return None


def strip_pid(label: str) -> str:
    """
    Remove a leading [pid=...] prefix if present and return just the core label text.
    Also strips leading [url=...] if present (treat URL as metadata only).
    """
    s = label.lstrip()

    # Strip [pid=...]
    if s.startswith(PID_PREFIX):
        closing = s.find("]")
        if closing != -1:
            s = s[closing + 1:].lstrip()

    # Strip [url=...] if present
    if s.startswith(URL_PREFIX):
        closing2 = s.find("]")
        if closing2 != -1:
            s = s[closing2 + 1:].lstrip()

    return s.strip()


def build_song_label(core_label: str, pid) -> str:
    """
    Combine a core label with an optional PID into the canonical text format.
    """
    core_label = core_label.strip()
    if not pid:
        return core_label

    pid_clean = extract_pid(str(pid)) or str(pid).strip()
    return f"[pid={pid_clean}] {core_label}"


def display_label(label: str) -> str:
    """
    For menus: strip the PID (and URL) so you see only 'Title – Artist' or the bare label.
    """
    return strip_pid(label)


def get_label_with_optional_pid(raw_label: str) -> str:
    """
    Unified helper:
      * If raw_label already has [pid=...], keeps it.
      * Otherwise:
          - Refuses URL inputs (anything containing '://').
          - Asks: "Do you have a PID for this song?"
          - If yes, read PID and wrap as [pid=PID] core_label
          - If no, just use the core_label.
    """
    label = raw_label.strip()

    # If the user already typed/pasted a [pid=...] label, just keep it.
    if label_has_pid(label):
        return label

    # Disallow URLs as labels
    if "://" in label:
        print("  URLs are not supported as labels in this tool.")
        print("  Please enter in the form: 'Title – Artist' or '[pid=HEX] Title – Artist'.")
        new_raw = input("  Enter label without URL: ").strip()
        return get_label_with_optional_pid(new_raw)

    core_label = strip_pid(label)  # usually same as label here

    have_pid = input("  Do you have a PID for this song? [y/N]: ").strip().lower()
    pid_value = None
    if have_pid == "y":
        pid_input = input("  Enter PID (paste [pid=...] label or just the hex): ").strip()
        pid_value = extract_pid(pid_input) or pid_input

    return build_song_label(core_label, pid_value)


def attach_pid_to_existing_label(label: str) -> str:
    """
    Used by menu option P) to attach or overwrite a PID for an existing song label.
    """
    print(f"\nCurrent song label: {display_label(label)}")
    existing_pid = extract_pid(label)
    if existing_pid:
        print(f"  Existing PID: {existing_pid}")
        overwrite = input("  Overwrite existing PID? [y/N]: ").strip().lower()
        if overwrite != "y":
            print("  Keeping existing PID.")
            return label

    pid_input = input("  Enter PID for this song: ").strip()
    pid_value = extract_pid(pid_input) or pid_input

    core_label = strip_pid(label)
    new_label = build_song_label(core_label, pid_value)
    print(f"  Updated label: {display_label(new_label)}  (PID attached)")
    return new_label
