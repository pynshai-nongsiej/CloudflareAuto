"""Link loader — reads ouo.io links from a text file and provides random selection."""

import random
from pathlib import Path
from typing import List, Optional


def load_links(filepath: str) -> List[str]:
    """Load non-empty ouo.io links from a text file, one per line.

    Args:
        filepath: Absolute or relative path to the links file.

    Returns:
        List of cleaned URL strings.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If no valid links are found.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Links file not found: {filepath}")

    links: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            url = line.strip()
            if url and url.startswith("http"):
                links.append(url)

    if not links:
        raise ValueError(f"No valid links found in {filepath}")

    return links


def pick_random_link(links: List[str], exclude: Optional[str] = None) -> str:
    """Pick a random link from the list, optionally excluding the last-used one.

    Args:
        links: Pool of all available links.
        exclude: URL to avoid picking consecutively (reduces repetition).

    Returns:
        A randomly chosen URL.
    """
    if len(links) == 1:
        return links[0]

    pool = [u for u in links if u != exclude] if exclude else links
    if not pool:
        pool = links  # fallback if exclude filtered everything

    return random.choice(pool)


def shuffle_links(links: List[str]) -> List[str]:
    """Return a shuffled copy of the links list."""
    shuffled = links.copy()
    random.shuffle(shuffled)
    return shuffled
