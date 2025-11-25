#!/usr/bin/env python3
import heapq
from collections import deque
import random
import textwrap


# ---------- Basic count helpers ----------

def _count_map(tracks):
    """
    tracks: list of {"name": str, "count": int}
    Returns a dict {name: total_count} merging duplicates if needed.
    """
    counts = {}
    for t in tracks:
        name = t["name"]
        c = int(t["count"])
        if c > 0:
            counts[name] = counts.get(name, 0) + c
    return counts


# ---------- Feasibility analysis & explanation ----------

def analyze_gap_feasibility(tracks, gap):
    """
    Check if a given min_gap is mathematically possible
    for the given counts.

    Returns a dict with:
      - feasible: bool
      - gap, total, max_count, most_songs, others, required_others,
        extra_others_needed, max_feasible_for_max_song
    """
    counts = _count_map(tracks)
    if not counts:
        return {
            "feasible": True,
            "gap": gap,
            "total": 0,
            "max_count": 0,
            "most_songs": [],
            "others": 0,
            "required_others": 0,
            "extra_others_needed": 0,
            "max_feasible_for_max_song": 0,
        }

    total = sum(counts.values())
    max_count = max(counts.values())
    most_songs = [n for n, c in counts.items() if c == max_count]

    if gap <= 0:
        return {
            "feasible": True,
            "gap": gap,
            "total": total,
            "max_count": max_count,
            "most_songs": most_songs,
            "others": total - max_count,
            "required_others": 0,
            "extra_others_needed": 0,
            "max_feasible_for_max_song": max_count,
        }

    others = total - max_count
    required_others = gap * (max_count - 1)
    feasible = others >= required_others
    extra = max(0, required_others - others)
    max_feasible_for_max_song = 1 + others // gap if gap > 0 else max_count

    return {
        "feasible": feasible,
        "gap": gap,
        "total": total,
        "max_count": max_count,
        "most_songs": most_songs,
        "others": others,
        "required_others": required_others,
        "extra_others_needed": extra,
        "max_feasible_for_max_song": max_feasible_for_max_song,
    }


def explain_gap_issue(tracks, gap):
    """
    Produce a human-readable explanation string if a given gap is impossible.
    Returns None if it's actually feasible.
    """
    info = analyze_gap_feasibility(tracks, gap)
    if info["feasible"]:
        return None

    most = info["most_songs"]
    song_names = "', '".join(most)

    return textwrap.dedent(f"""
    With min_gap={info['gap']}, the current counts are mathematically impossible.

    • Most frequent song(s): '{song_names}' (each appears {info['max_count']} times)
    • Total song occurrences: {info['total']}
    • Other song occurrences (everything else combined): {info['others']}
    • To separate {info['max_count']} repeats with gap {info['gap']},
      you would need at least {info['required_others']} plays of *other* songs.

    Given your current counts, that means:
      - You can keep at most {info['max_feasible_for_max_song']} occurrences
        of the most frequent song(s), OR
      - You need to add at least {info['extra_others_needed']} more
        occurrences of other songs (new songs, or increasing counts of existing ones).

    Try reducing the counts of the most frequent song(s), or increasing the
    counts / adding more songs, then run the scheduler again.
    """).strip()


# ---------- Deterministic scheduler (always correct if feasible) ----------

def _schedule_with_gap(tracks, min_gap=3):
    """
    Deterministic scheduler using a max-heap + cooldown queue.

    tracks: list of {"name": str, "count": int}
    min_gap: minimum number of *other* songs between repeats.
    Returns: list of names in a valid order, or raises ValueError
             if it cannot satisfy the gap.
    """
    counts = _count_map(tracks)
    if not counts:
        return []

    total = sum(counts.values())

    if min_gap <= 0:
        result = []
        for name, c in counts.items():
            result.extend([name] * c)
        return result

    # Heap of (-count, name)
    heap = [(-c, name) for name, c in counts.items()]
    heapq.heapify(heap)

    # Cooldown queue: (ready_step, -count_remaining, name)
    cooldown = deque()
    result = []
    step = 0

    while heap or cooldown:
        # Return items whose cooldown has expired
        while cooldown and cooldown[0][0] <= step:
            _, negc, nm = cooldown.popleft()
            heapq.heappush(heap, (negc, nm))

        if not heap:
            # Nothing we can place, but some songs still pending
            if len(result) != total:
                raise ValueError("Cannot schedule with given gap; heap empty while songs remain.")
            break

        negc, name = heapq.heappop(heap)
        count_left = -negc

        result.append(name)
        step += 1
        count_left -= 1

        if count_left > 0:
            cooldown.append((step + min_gap, -count_left, name))

    if len(result) != total:
        raise ValueError("Cannot schedule with given gap; not all songs placed.")

    # Safety check
    if min_gap > 0:
        last_pos = {}
        for i, s in enumerate(result):
            if s in last_pos and i - last_pos[s] - 1 < min_gap:
                raise AssertionError("min_gap violated by internal scheduler")
            last_pos[s] = i

    return result


# ---------- Randomization layer (preserve gap) ----------

def _randomize_schedule_preserving_gap(order, min_gap, seed=None, passes=2):
    """
    Take a valid schedule `order` for a given min_gap, and introduce
    randomness by doing safe swaps that preserve the min_gap constraint.
    """
    if min_gap <= 0 or len(order) <= 2:
        return order[:]

    rng = random.Random(seed)
    n = len(order)
    res = order[:]

    def valid_all():
        last = {}
        for i, s in enumerate(res):
            if s in last and i - last[s] - 1 < min_gap:
                return False
            last[s] = i
        return True

    assert valid_all()

    num_swaps = passes * n
    for _ in range(num_swaps):
        i = rng.randrange(n)
        j = rng.randrange(n)
        if i == j:
            continue
        res[i], res[j] = res[j], res[i]
        if not valid_all():
            # revert if swap breaks gap constraint
            res[i], res[j] = res[j], res[i]

    return res


# ---------- Public API ----------

def generate_round_robin(
    tracks,
    preferred_gap=3,
    min_allowed_gap=2,
    randomize=False,
    seed=None,
):
    """
    Unified scheduler:

      - Tries min_gap = preferred_gap (e.g., 3).
      - If impossible, falls back down to min_allowed_gap (e.g., 2).
      - NEVER uses gap < min_allowed_gap (so you can forbid gap=1).

    If `randomize` is False:
      - Returns deterministic schedule from _schedule_with_gap.

    If `randomize` is True:
      - Uses the deterministic scheduler to get a valid baseline.
      - Then randomizes that baseline with safe swaps that preserve min_gap.

    Raises ValueError with a human-readable explanation if no gap >= min_allowed_gap
    is mathematically possible.
    """
    if preferred_gap < min_allowed_gap:
        preferred_gap, min_allowed_gap = min_allowed_gap, preferred_gap

    last_issue = None
    gap = preferred_gap

    while gap >= min_allowed_gap:
        info = analyze_gap_feasibility(tracks, gap)
        if not info["feasible"]:
            # We know this gap is mathematically impossible, move on
            last_issue = info
            gap -= 1
            continue

        try:
            print(f"[*] Trying to schedule with min_gap={gap}{' (with randomization)' if randomize else ''}...")
            base = _schedule_with_gap(tracks, min_gap=gap)
            print(f"[*] Success with min_gap={gap}.")
            if randomize:
                return _randomize_schedule_preserving_gap(base, gap, seed=seed)
            return base
        except ValueError as e:
            # extremely rare, but if deterministic scheduler fails, try a smaller gap
            print(f"[!] Internal scheduler failed at gap {gap}: {e}")
            last_issue = analyze_gap_feasibility(tracks, gap)
            gap -= 1

    if last_issue is None:
        raise ValueError("No tracks to schedule.")

    msg = explain_gap_issue(tracks, last_issue["gap"])
    raise ValueError(msg or "Cannot schedule playlist with given gaps.")
