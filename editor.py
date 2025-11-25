#!/usr/bin/env python3
import questionary

from pid_utils import (
    extract_pid,
    display_label,
    get_label_with_optional_pid,
    attach_pid_to_existing_label,
)


def show_song_counts(counter):
    print("\nCurrent songs in playlist:")
    if not counter:
        print("(no songs)")
        print()
        return

    for idx, (song, cnt) in enumerate(counter.items(), start=1):
        label = display_label(song)
        pid = extract_pid(song)
        if pid:
            print(f"[{idx}] {label} -> {cnt} (PID: {pid})")
        else:
            print(f"[{idx}] {label} -> {cnt}")
    print()


def choose_song_from_counter(counter, prompt="Select a song:"):
    """
    Use an arrow-key menu to select a song from the Counter.
    Returns the song label (key in the Counter), or None if cancelled.
    """
    items = list(counter.items())
    if not items:
        print("No songs available.")
        return None

    choices = []
    for song, cnt in items:
        title = f"{display_label(song)}  (x{cnt})"
        choices.append(questionary.Choice(title=title, value=song))

    selected = questionary.select(
        prompt,
        choices=choices,
        qmark="🎵",
    ).ask()

    return selected  # song label, or None if cancelled


def choose_edit_action():
    return questionary.select(
        "What would you like to do?",
        choices=[
            questionary.Choice("Add songs", value="A"),
            questionary.Choice("Substitute songs", value="S"),
            questionary.Choice("Change counts for an existing song", value="C"),
            questionary.Choice("Attach PID to an existing song", value="P"),
            questionary.Choice("Update playlist description", value="D"),
            questionary.Choice("Done editing", value="Q"),
        ],
        qmark="📝",
    ).ask()



def edit_playlist_counts(counter):
    """
    Interactive loop to:
      - Add songs (with optional PID)
      - Substitute songs (with optional PID)
      - Change counts for an existing song
      - Attach PID to an existing label
    Returns updated Counter.
    """
    while True:
        show_song_counts(counter)
        choice = choose_edit_action()

        if choice == "Q":
            return counter

        if choice == "A":
            try:
                m = int(input("How many new unique songs do you want to add? ").strip())
            except ValueError:
                print("Please enter a valid integer.")
                continue

            for i in range(1, m + 1):
                print(f"\nNew Song {i}:")
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
                counter[label] += count

        elif choice == "S":
            if not counter:
                print("No songs to substitute.")
                continue

            old_song = choose_song_from_counter(counter, "Select the song to substitute:")
            if old_song is None:
                continue

            old_count = counter[old_song]
            print(f"\nSelected: {display_label(old_song)} (currently {old_count} times)")

            raw_new = questionary.text(
                "Enter the replacement song label (Title – Artist or [pid=...] Title – Artist):"
            ).ask()
            if not raw_new:
                print("  (blank, cancelled)")
                continue

            new_song = get_label_with_optional_pid(raw_new)

            mode = questionary.select(
                "Change which occurrences?",
                choices=[
                    questionary.Choice("All occurrences", value="A"),
                    questionary.Choice("A specific number of occurrences", value="N"),
                ],
                qmark="🔁",
            ).ask()

            if mode == "A":
                num_to_change = old_count
            else:
                while True:
                    try:
                        num_to_change = int(input("How many occurrences to change? ").strip())
                        if num_to_change <= 0:
                            print("Please enter a positive integer.")
                            continue
                        if num_to_change > old_count:
                            print(f"You only have {old_count} occurrences of that song.")
                            continue
                        break
                    except ValueError:
                        print("Please enter a valid integer.")

            # Apply changes
            counter[old_song] -= num_to_change
            if counter[old_song] <= 0:
                del counter[old_song]
            counter[new_song] += num_to_change

            print(
                f"\nUpdated counts: changed {num_to_change} of "
                f"'{display_label(old_song)}' to '{display_label(new_song)}'."
            )

            # Optional: ask about remaining occurrences
            if mode != "A" and old_song in counter:
                remaining = counter[old_song]
                ans = questionary.confirm(
                    f"There are still {remaining} occurrences of "
                    f"'{display_label(old_song)}'. Change all remaining to "
                    f"'{display_label(new_song)}' as well?",
                    default=False,
                ).ask()
                if ans:
                    counter[new_song] += remaining
                    del counter[old_song]
                    print(f"All remaining occurrences changed to '{display_label(new_song)}'.")

        elif choice == "C":
            if not counter:
                print("No songs to change counts for.")
                continue

            song = choose_song_from_counter(counter, "Select the song whose count you want to change:")
            if song is None:
                continue

            old_count = counter[song]
            print(f"\nSelected: {display_label(song)} (currently {old_count} times)")

            while True:
                try:
                    new_count = int(input("Enter the NEW total count for this song (0 to remove): ").strip())
                    break
                except ValueError:
                    print("Please enter a valid integer.")

            if new_count <= 0:
                del counter[song]
                print(f"Removed '{display_label(song)}' from playlist.")
            else:
                counter[song] = new_count
                print(f"Updated '{display_label(song)}' count to {new_count}.")

        elif choice == "P":
            if not counter:
                print("No songs to attach PIDs to.")
                continue

            song = choose_song_from_counter(counter, "Select the song to attach/overwrite PID for:")
            if song is None:
                continue

            count = counter[song]
            new_label = attach_pid_to_existing_label(song)

            if new_label != song:
                del counter[song]
                counter[new_label] += count
        
        elif choice == "D":
            # Use questionary.text for nicer input
            new_desc = questionary.text(
                "Enter new playlist description:"
            ).ask()

            # Store this description somewhere accessible
            global PLAYLIST_DESCRIPTION
            PLAYLIST_DESCRIPTION = new_desc or ""

            print(f"Description updated to:\n  {PLAYLIST_DESCRIPTION}")

        else:
            # Shouldn't happen with questionary, but keep a guard
            print("Unknown option; please try again.")
            continue
