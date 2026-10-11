"""Word frequency by hashing tokens.

Time: O(n) in the number of characters, plus O(u log u) to rank unique words.
Space: O(u) for the hash map.
The text limit is 100,000 characters. Ranking is count descending, then word
ascending, so ties are deterministic.
"""

import re
from typing import Any

_TOKEN = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?")


def word_frequencies(text: str, top_n: int) -> dict[str, Any]:
    counts: dict[str, int] = {}
    total = 0
    for match in _TOKEN.finditer(text):
        word = match.group(0).lower()
        counts[word] = counts.get(word, 0) + 1
        total += 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    chosen = ranked[:top_n]
    return {
        "algorithm": "token_hash_count",
        "token_count": total,
        "unique_count": len(counts),
        "top_n": top_n,
        "frequencies": [{"word": word, "count": count} for word, count in chosen],
    }
