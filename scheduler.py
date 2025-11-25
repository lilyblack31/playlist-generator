#!/usr/bin/env python3
import heapq
from collections import deque


def _schedule_with_gap(tracks, min_gap=3, seed=None):
    """
    Deterministic scheduler using a max-heap + cooldown queue.

    tracks: list of dicts: [{"name": str, "count": int}, ...]
    min_gap: minimum number of *other* songs between two occurrences
             of the same song (global constraint).

    Returns: list of song labels in a spaced-out order.
    Raises: ValueError only if it is mathematically impossible.
    """
    # Build a simple count map
    counts = {}
    for t in tracks:
        name = t["name"]
        count = t["count"]
        if count > 0:
            counts[name] = counts.get(name, 0) + count

    if not counts:
        return []

    total = sum(counts.values())

    # Trivial case: no gap constraint
    if min_gap <= 0:
        result = []
        for name, c in counts.items():
            result.extend([name] * c)
        return result

    # Max-heap of (-count, name)
    heap = [(-c, name) for name, c in counts.items()]
    heapq.heapify(heap)

    # Cooldown queue: each entry is (ready_step, -remaining_count, name)
    cooldown = deque()
    result = []
    step = 0

    while heap or cooldown:
        # Bring back any songs whose cooldown is finished
        while cooldown and cooldown[0][0] <= step:
            _, negc, nm = cooldown.popleft()
            heapq.heappush(heap, (negc, nm))

        if not heap:
            # Nothing we can place now, but songs still waiting -> impossible
            if len(result) != total:
                raise ValueError(
                    f"Cannot schedule playlist with min_gap={min_gap} given these counts."
                )
            else:
                break  # should not happen normally

        negc, name = heapq.heappop(heap)
        count_left = -negc

        # Place this song
        result.append(name)
        step += 1
        count_left -= 1

        if count_left > 0:
            # It can be used again after min_gap other songs:
            cooldown.append((step + min_gap, -count_left, name))

    if len(result) != total:
        raise ValueError(
            f"Cannot schedule playlist with min_gap={min_gap} given these counts."
        )

    # Safety check: verify min_gap constraint actually holds
    if min_gap > 0:
        last_pos = {}
        for i, song in enumerate(result):
            if song in last_pos:
                if i - last_pos[song] - 1 < min_gap:
                    raise AssertionError(
                        f"Internal error: song '{song}' repeated too soon at positions "
                        f"{last_pos[song]} and {i}"
                    )
            last_pos[song] = i

    return result


def generate_round_robin(tracks, preferred_gap=3, min_allowed_gap=2, seed=None):
    """
    Public generator with fallback:

    - Tries to schedule with preferred_gap (e.g., 3).
    - If impossible, automatically falls back to smaller gaps
      down to min_allowed_gap (e.g., 2).
    - Uses a deterministic scheduler; failure really means "mathematically impossible".
    - When impossible, the ValueError message includes guidance
      about which song is the bottleneck and how to fix counts.
    """
    # Precompute counts once
    counts = {}
    for t in tracks:
        name = t["name"]
        count = t["count"]
        if count > 0:
            counts[name] = counts.get(name, 0) + count

    if not counts:
        return []

    total = sum(counts.values())
    max_song, max_count = max(counts.items(), key=lambda kv: kv[1])

    gap = preferred_gap
    last_error = None

    while gap >= min_allowed_gap:
        # Quick feasibility check: others ≥ gap * (max_count - 1)
        if gap > 0 and max_count > 1:
            others = total - max_count
            required_others = gap * (max_count - 1)
            if others < required_others:
                # This gap is mathematically impossible
                max_feasible = 1 + others // gap
                needed_extra = required_others - others
                msg = (
                    f"Counts impossible with min_gap={gap}: song '{max_song}' appears "
                    f"{max_count} times. With {others} other song occurrences, "
                    f"it can appear at most {max_feasible} times, or you must add at least "
                    f"{needed_extra} more occurrences of other songs."
                )
                print(f"[!] {msg}")
                last_error = ValueError(msg)
                gap -= 1
                continue

        try:
            print(f"[*] Trying to schedule with min_gap={gap}...")
            result = _schedule_with_gap(tracks, min_gap=gap, seed=seed)
            print(f"[*] Success with min_gap={gap}.")
            return result
        except ValueError as e:
            print(f"[!] Failed with min_gap={gap}: {e}")
            last_error = e
            gap -= 1

    # If we reach here, even min_allowed_gap was impossible
    raise ValueError(
        "Cannot schedule playlist with any gap >= "
        f"{min_allowed_gap}. Last error: {last_error}"
    )
