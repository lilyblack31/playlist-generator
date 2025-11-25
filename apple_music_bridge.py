#!/usr/bin/env python3
import subprocess
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

# Bridge between Python and the Music.app (Apple Music) via AppleScript.
# NOTE: This version does NOT try to resolve or add Apple Music store URLs.
# It only works with:
#   - tracks already in your Library (via PID or Title–Artist search)
#   - TXT labels of the form:
#         [pid=HEX] Title – Artist
#         Title – Artist
#
# Any line that is *just* a URL (contains "://") will be skipped with a warning.
# Lines with "[url=...]" prefixes are treated as metadata only: we strip the
# prefix and just use the remaining label text for Title–Artist search.

APPLE_MUSIC_SCRIPT = """property pid_success : 0
property pid_fail : 0
property search_success : 0
property search_fail : 0
property skipped_lines : 0

on ensurePlaylistNamed(playlistName)
    tell application "Music"
        -- Only consider user playlists (playlists you own / can modify)
        set userPlaylists to every user playlist whose name is playlistName
        if (count of userPlaylists) > 0 then
            set targetPlaylist to item 1 of userPlaylists
        else
            set targetPlaylist to make new user playlist with properties {name:playlistName}
        end if
        return targetPlaylist
    end tell
end ensurePlaylistNamed

on clearPlaylist(playlistName)
    tell application "Music"
        set targetPlaylist to my ensurePlaylistNamed(playlistName)
        try
            delete every track of targetPlaylist
        on error errMsg number errNum
            log "WARNING: Error clearing playlist '" & playlistName & "': " & errMsg & " (" & errNum & ")"
        end try
    end tell
end clearPlaylist

on findTrackByPID(thePID)
    tell application "Music"
        try
            set theTracks to every track whose persistent ID is thePID
            if theTracks is {} then
                set pid_fail to pid_fail + 1
                log "WARNING: PID not found in library: " & thePID
                return missing value
            else
                set t to item 1 of theTracks
                set pid_success to pid_success + 1
                return t
            end if
        on error errMsg number errNum
            set pid_fail to pid_fail + 1
            log "WARNING: Error in findTrackByPID for PID " & thePID & ": " & errMsg & " (" & errNum & ")"
            return missing value
        end try
    end tell
end findTrackByPID

on addTrackToPlaylist(aTrack, playlistName)
    tell application "Music"
        set targetPlaylist to my ensurePlaylistNamed(playlistName)
        try
            duplicate aTrack to targetPlaylist
        on error errMsg number errNum
            log "WARNING: Error duplicating track to playlist '" & playlistName & "': " & errMsg & " (" & errNum & ")"
        end try
    end tell
end addTrackToPlaylist

on trimText(t)
    set theChars to {space, tab, return, linefeed}
    repeat while t is not "" and (t begins with space or t begins with tab or t begins with return or t begins with linefeed)
        set t to text 2 thru -1 of t
    end repeat
    repeat while t is not "" and (t ends with space or t ends with tab or t ends with return or t ends with linefeed)
        set t to text 1 thru -2 of t
    end repeat
    return t
end trimText

on searchAndAddTitleArtist(lineText, playlistName)
    set titlePart to lineText
    set artistPart to ""

    -- Try 'Title – Artist' (en dash)
    set AppleScript's text item delimiters to " – "
    if (count of text items of lineText) > 1 then
        set titlePart to text item 1 of lineText
        set artistPart to text item 2 of lineText
    else
        -- Fallback 'Title - Artist'
        set AppleScript's text item delimiters to " - "
        if (count of text items of lineText) > 1 then
            set titlePart to text item 1 of lineText
            set artistPart to text item 2 of lineText
        end if
    end if
    set AppleScript's text item delimiters to ""

    set titlePart to my trimText(titlePart)
    set artistPart to my trimText(artistPart)

    tell application "Music"
        set searchResults to (search library playlist 1 for titlePart only songs)
        if searchResults is {} then
            set search_fail to search_fail + 1
            log "WARNING: No search results for title '" & titlePart & "' (artist hint: '" & artistPart & "')"
            return
        end if

        set chosenTrack to missing value

        -- First pass: name contains title AND, if artistPart is present, artist contains artistPart
        repeat with t in searchResults
            set tName to ""
            set tArtist to ""
            try
                set tName to name of t as text
            end try
            try
                set tArtist to artist of t as text
            end try

            if tName is not "" then
                ignoring case
                    if tName contains titlePart then
                        if artistPart is "" then
                            set chosenTrack to t
                            exit repeat
                        else
                            if tArtist contains artistPart then
                                set chosenTrack to t
                                exit repeat
                            end if
                        end if
                    end if
                end ignoring
            end if
        end repeat

        -- Second pass: if still missing, try title-only strict match (name contains titlePart)
        if chosenTrack is missing value then
            repeat with t in searchResults
                set tName to ""
                try
                    set tName to name of t as text
                end try
                if tName is not "" then
                    ignoring case
                        if tName contains titlePart then
                            set chosenTrack to t
                            exit repeat
                        end if
                    end ignoring
                end if
            end repeat
        end if

        if chosenTrack is missing value then
            set search_fail to search_fail + 1
            log "WARNING: No suitable match for title '" & titlePart & "' (artist hint: '" & artistPart & "')"
            return
        end if

        set targetPlaylist to my ensurePlaylistNamed(playlistName)
        try
            duplicate chosenTrack to targetPlaylist
            set search_success to search_success + 1
        on error errMsg number errNum
            set search_fail to search_fail + 1
            log "WARNING: Error duplicating search result to playlist '" & playlistName & "': " & errMsg & " (" & errNum & ")"
        end try
    end tell
end searchAndAddTitleArtist

on addLineToPlaylist(lineText, playlistName)
    set lineText to lineText as text
    set playlistName to playlistName as text

    set lineText to my trimText(lineText)
    if lineText is "" then
        set skipped_lines to skipped_lines + 1
        return
    end if
    if lineText starts with "#" then
        set skipped_lines to skipped_lines + 1
        return
    end if

    -- 1) PID prefix: [pid=...]
    if lineText starts with "[pid=" then
        set closeBracket to offset of "]" in lineText
        if closeBracket > 6 then
            set thePID to text 6 thru (closeBracket - 1) of lineText
            set coreLabel to ""
            if (length of lineText) > (closeBracket + 1) then
                set coreLabel to text (closeBracket + 2) thru -1 of lineText -- skip "] "
            end if

            set theTrack to my findTrackByPID(thePID)
            if theTrack is not missing value then
                my addTrackToPlaylist(theTrack, playlistName)
                return
            end if

            -- PID lookup failed; fall back to coreLabel (if any)
            if coreLabel is not "" then
                set lineText to coreLabel
            else
                -- No label to fall back to
                set skipped_lines to skipped_lines + 1
                return
            end if
        else
            log "WARNING: Malformed PID prefix in line: " & lineText
            -- Fall through and treat as non-PID line
        end if
    end if

    -- 2) [url=...] prefix as metadata ONLY:
    --    We ignore the URL and just use the remaining label text.
    if lineText starts with "[url=" then
        set closeBracket2 to offset of "]" in lineText
        if closeBracket2 > 6 then
            if (length of lineText) > (closeBracket2 + 1) then
                set lineText to text (closeBracket2 + 2) thru -1 of lineText -- skip "] "
            else
                -- No text after [url=...]; nothing to search for
                set skipped_lines to skipped_lines + 1
                return
            end if
        end if
    end if

    -- 3) Bare URL-only lines are not supported; log + skip
    if lineText contains "://" then
        log "WARNING: URL-only line not supported. Please add this track to your Library and use a Title – Artist or PID label instead: " & lineText
        set skipped_lines to skipped_lines + 1
        return
    end if

    -- 4) Title – Artist fallback
    my searchAndAddTitleArtist(lineText, playlistName)
end addLineToPlaylist

on applyTxtFileToPlaylist(txtPath, playlistName, shouldClear)
    set txtPath to txtPath as text
    set playlistName to playlistName as text

    -- Reset counters for this run
    set pid_success to 0
    set pid_fail to 0
    set search_success to 0
    set search_fail to 0
    set skipped_lines to 0

    if shouldClear then
        my clearPlaylist(playlistName)
    else
        my ensurePlaylistNamed(playlistName)
    end if

    -- Read the TXT file contents
    set f to POSIX file txtPath
    try
        set fileContents to read f as «class utf8»
    on error
        set fileContents to read f
    end try

    -- Split into lines
    set AppleScript's text item delimiters to linefeed
    set theLines to paragraphs of fileContents
    set AppleScript's text item delimiters to ""

    repeat with lineText in theLines
        my addLineToPlaylist(lineText, playlistName)
    end repeat

    -- Summary log
    log "SUMMARY: PID success=" & pid_success & ", PID fail=" & pid_fail & ¬
        ", Search success=" & search_success & ", Search fail=" & search_fail & ¬
        ", Skipped lines=" & skipped_lines
end applyTxtFileToPlaylist

on run argv
    if (count of argv) is 0 then return
    set action to item 1 of argv

    if action is "applyFile" then
        if (count of argv) < 4 then return
        set txtPath to item 2 of argv
        set playlistName to item 3 of argv
        set clearFlag to item 4 of argv
        set shouldClear to (clearFlag is "1")
        my applyTxtFileToPlaylist(txtPath, playlistName, shouldClear)

    else if action is "addLine" then
        if (count of argv) < 3 then return
        set lineText to item 2 of argv
        set playlistName to item 3 of argv
        my addLineToPlaylist(lineText, playlistName)

    else if action is "clear" then
        if (count of argv) < 2 then return
        set playlistName to item 2 of argv
        my clearPlaylist(playlistName)
    end if
end run"""

def _run_osascript(args):
    """
    Low-level helper to run our AppleScript with arguments.
    Returns (returncode, stdout, stderr).
    """
    proc = subprocess.run(
        ["osascript", "-", *args],
        input=APPLE_MUSIC_SCRIPT,
        capture_output=True,
        text=True,
    )
    rc = proc.returncode
    out = proc.stdout.strip()
    err = proc.stderr.strip()
    return rc, out, err


def call_applescript_add_line(line_text: str, playlist_name: str) -> None:
    """
    Call AppleScript 'addLineToPlaylist' via the run handler (single line).
    Mostly for debugging; the batch flow is preferred.
    """
    rc, out, err = _run_osascript(["addLine", line_text, playlist_name])
    if err:
        print(f"[AppleScript log addLine]\n{err}")
    if out:
        print(f"[AppleScript output addLine]\n{out}")
    if rc != 0:
        print(f"[AppleScript error addLine] returncode={rc}")


def call_applescript_clear_playlist(playlist_name: str) -> None:
    """
    Call AppleScript 'clearPlaylist' to empty the target playlist (creating it if needed).
    """
    rc, out, err = _run_osascript(["clear", playlist_name])
    if err:
        print(f"[AppleScript log clear]\n{err}")
    if out:
        print(f"[AppleScript output clear]\n{out}")
    if rc != 0:
        print(f"[AppleScript error clear] returncode={rc}")


def apply_playlist_to_apple_music_from_txt(
    playlist_name: str,
    txt_path: str,
    clear_first: bool = True,
) -> None:
    """
    Read your final TXT playlist and apply it to Music.app.

    IMPORTANT:
      - This ONLY works for tracks that are already in your Apple Music Library.
      - The script uses:
          * [pid=HEX] prefixes to find exact tracks by persistent ID
          * Otherwise, a strict Title–Artist search of your library
      - Bare URL lines are skipped with a warning; no attempt is made to resolve
        Apple Music store URLs automatically. If you want a song, add it to
        your Library first (or give it a PID from an XML export / helper script).

    Parameters:
      playlist_name: name of the target user playlist in Music.app
      txt_path: path to the TXT file generated by the Python tool
      clear_first: if True, the target playlist is cleared before rebuilding
    """
    clear_flag = "1" if clear_first else "0"
    print(
        color("Applying TXT ", FG_CYAN)
        + color(f"'{txt_path}'", FG_MAGENTA)
        + color(" to Apple Music playlist ", FG_CYAN)
        + color(f"'{playlist_name}' ", FG_MAGENTA)
        + color(f"(clear_first={clear_first})...", FG_CYAN)
    )

    rc, out, err = _run_osascript(["applyFile", txt_path, playlist_name, clear_flag])

    # Show logs (warnings + summary)
    if err:
        print(color("[AppleScript log applyFile]", FG_YELLOW, BOLD))
        # err may already contain WARNING: lines; just print as-is but dim them slightly
        print(color(err, FG_YELLOW))

    if out:
        print(color("[AppleScript output applyFile]", FG_CYAN, BOLD))
        print(out)

    if rc != 0:
        print(color(f"[AppleScript error applyFile] returncode={rc}", FG_RED, BOLD))
    else:
        print(color("✅ Done applying playlist to Apple Music.", FG_GREEN, BOLD))

    # Add blank line to separate next menu cleanly
    print()


def maybe_apply_to_apple_music(playlist_name: str, txt_path: str) -> None:
    """
    Ask the user whether to apply the TXT playlist to Music.app now.
    Also reminds the user about the 'Library-only' requirement.
    """
    note = (
        "\nNOTE: This tool can only add tracks that are already in your Apple Music Library.\n"
        "      If a song is only available via an Apple Music URL and not in your Library,\n"
        "      it will be skipped. Use [pid=HEX] labels or Title – Artist for library tracks."
    )
    print(color(note, FG_YELLOW))

    ans = input(
        color(
            f"\nApply this TXT to Apple Music playlist '{playlist_name}' now? [y/N]: ",
            FG_CYAN,
            BOLD,
        )
    ).strip().lower()
    if ans != "y":
        print(color("  (Not applying to Music right now.)", FG_GRAY))
        print()
        return

    clear_choice = input(
        color("  Clear that playlist in Music before rebuilding? [Y/n]: ", FG_CYAN)
    ).strip().lower()
    clear_first = (clear_choice != "n")
    apply_playlist_to_apple_music_from_txt(playlist_name, txt_path, clear_first=clear_first)


def update_playlist_description(playlist_name, description):
    """
    Update the description metadata of a playlist in Apple Music.
    Only works for user-created playlists (not Smart Playlists).
    """
    script = '''
    on run {pName, pDesc}
        tell application "Music"
            try
                set targetPlaylist to playlist pName
                set description of targetPlaylist to pDesc
                return "OK"
            on error errMsg number errNum
                return "ERROR: " & errMsg & " (" & errNum & ")"
            end try
        end tell
    end run
    '''

    proc = subprocess.run(
        ["osascript", "-", playlist_name, description],
        input=script,
        text=True,
        capture_output=True,
    )
    result = proc.stdout.strip()
    return result


def get_playlist_description(playlist_name):
    """
    Read the current description of a playlist in Apple Music.
    Returns:
      - "" if there is no description
      - "ERROR: ..." if something went wrong
      - the description text otherwise
    """
    script = '''
    on run {pName}
        tell application "Music"
            try
                set targetPlaylist to playlist pName
                set descVal to description of targetPlaylist
                if descVal is missing value then
                    return ""
                else
                    return descVal
                end if
            on error errMsg number errNum
                return "ERROR: " & errMsg & " (" & errNum & ")"
            end try
        end tell
    end run
    '''

    proc = subprocess.run(
        ["osascript", "-", playlist_name],
        input=script,
        text=True,
        capture_output=True,
    )
    return proc.stdout.strip()
