"""Map UK section labels (3, 3A, 3ZA) to the locked model's (number, bis) integers, injectively."""


def suffix_value(s: str) -> int:
    """Bijective base 26: A=1 ... Z=26, AA=27 ... so every distinct suffix gets a distinct integer."""
    v = 0
    for ch in s:
        v = v * 26 + (ord(ch) - 64)
    return v
