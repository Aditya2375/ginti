"""Spoken numbers in Hindi (Devanagari and Roman) and English.

Everything here is plain tables and string handling. It turns what the
recogniser heard (or what a child typed) into an integer, and turns an
integer into words that a speech synthesiser can read out.

Hindi number words from 1 to 99 are mostly irregular, so they are in a
written-out table instead of a rule.
"""

from __future__ import annotations

import re

HI_WORDS = (
    "शून्य एक दो तीन चार पाँच छह सात आठ नौ "
    "दस ग्यारह बारह तेरह चौदह पंद्रह सोलह सत्रह अठारह उन्नीस "
    "बीस इक्कीस बाईस तेईस चौबीस पच्चीस छब्बीस सत्ताईस अट्ठाईस उनतीस "
    "तीस इकतीस बत्तीस तैंतीस चौंतीस पैंतीस छत्तीस सैंतीस अड़तीस उनतालीस "
    "चालीस इकतालीस बयालीस तैंतालीस चौवालीस पैंतालीस छियालीस सैंतालीस अड़तालीस उनचास "
    "पचास इक्यावन बावन तिरपन चौवन पचपन छप्पन सत्तावन अट्ठावन उनसठ "
    "साठ इकसठ बासठ तिरसठ चौंसठ पैंसठ छियासठ सड़सठ अड़सठ उनहत्तर "
    "सत्तर इकहत्तर बहत्तर तिहत्तर चौहत्तर पचहत्तर छिहत्तर सतहत्तर अठहत्तर उनासी "
    "अस्सी इक्यासी बयासी तिरासी चौरासी पचासी छियासी सत्तासी अट्ठासी नवासी "
    "नब्बे इक्यानवे बानवे तिरानवे चौरानवे पचानवे छियानवे सत्तानवे अट्ठानवे निन्यानवे"
).split()

HI_HUNDRED = "सौ"
HI_THOUSAND = "हज़ार"

# Other spellings a recogniser or a keyboard produces for the same word.
HI_ALIASES = {
    "पांच": 5, "छः": 6, "छ": 6, "छे": 6, "पन्द्रह": 15, "अठ्ठाईस": 28,
    "अठाईस": 28, "चौबिस": 24, "चवालीस": 44, "तिरेपन": 53, "इक्याबन": 51,
    "तिरेसठ": 63, "छयासठ": 66, "अट्ठारह": 18, "अठ्ठारह": 18, "हजार": 1000,
    "तिरपन": 53, "सतहत्तर": 77, "इक्यावन": 51,
}
assert len(HI_WORDS) == 100

HI_VALUE: dict[str, int] = {w: i for i, w in enumerate(HI_WORDS)}
HI_VALUE.update(HI_ALIASES)
HI_VALUE[HI_HUNDRED] = 100
HI_VALUE[HI_THOUSAND] = 1000

# Roman spellings of the same words, as people type Hindi on a phone.
HI_ROMAN = (
    "shunya ek do teen char paanch chhe saat aath nau "
    "das gyarah barah terah chaudah pandrah solah satrah atharah unnis "
    "bees ikkis baais teis chaubis pachchis chhabbis sattais atthais untis "
    "tees iktis battis taintis chauntis paintis chhattis saintis adtis untalis "
    "chalis iktalis bayalis taintalis chauvalis paintalis chhiyalis saintalis adtalis unchas "
    "pachas ikyavan baavan tirpan chauvan pachpan chhappan sattavan atthavan unsath "
    "saath iksath baasath tirsath chausath painsath chhiyasath sadsath adsath unhattar "
    "sattar ikhattar bahattar tihattar chauhattar pachhattar chhihattar satattar athattar unasi "
    "assi ikyasi bayasi tirasi chaurasi pachasi chhiyasi sattasi atthasi navasi "
    "nabbe ikyanave baanave tiranave chauranave pachanave chhiyanave sattanave atthanave ninyanave"
).split()
assert len(HI_ROMAN) == 100

EN_UNITS = (
    "zero one two three four five six seven eight nine ten eleven twelve "
    "thirteen fourteen fifteen sixteen seventeen eighteen nineteen"
).split()
EN_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
EN_VALUE: dict[str, int] = {w: i for i, w in enumerate(EN_UNITS)}
EN_VALUE.update({w: i * 10 for i, w in enumerate(EN_TENS) if w != "_"})
EN_VALUE.update({"fourty": 40, "hundred": 100, "thousand": 1000})

MAX_VALUE = 9999


def _roman_key(word: str) -> str:
    """Fold the usual Roman spelling differences so 'paanch' and 'panch' meet."""
    w = re.sub(r"[^a-z]", "", word.lower())
    w = w.replace("w", "v").replace("ph", "f")
    for a, b in (("aa", "a"), ("ee", "i"), ("ii", "i"), ("oo", "u"), ("uu", "u")):
        w = w.replace(a, b)
    return re.sub(r"([bcdfgjklmnpqrstvxyz])\1+", r"\1", w)


ROMAN_VALUE: dict[str, int] = {}
for _i, _w in enumerate(HI_ROMAN):
    ROMAN_VALUE[_roman_key(_w)] = _i
ROMAN_VALUE.update({_roman_key("sau"): 100, _roman_key("hazar"): 1000,
                    _roman_key("hazaar"): 1000, _roman_key("shunay"): 0,
                    _roman_key("zero"): 0})


def to_hindi(n: int) -> str:
    """Words for 0..9999 in Devanagari, for a synthesiser to read."""
    _check(n)
    parts: list[str] = []
    if n >= 1000:
        parts += [HI_WORDS[n // 1000], HI_THOUSAND]
        n %= 1000
    if n >= 100:
        parts += [HI_WORDS[n // 100], HI_HUNDRED]
        n %= 100
    if n or not parts:
        parts.append(HI_WORDS[n])
    return " ".join(parts)


def to_english(n: int) -> str:
    """Words for 0..9999 in English."""
    _check(n)
    parts: list[str] = []
    if n >= 1000:
        parts += [EN_UNITS[n // 1000], "thousand"]
        n %= 1000
    if n >= 100:
        parts += [EN_UNITS[n // 100], "hundred"]
        n %= 100
        if n:
            parts.append("and")
    if n >= 20:
        parts.append(EN_TENS[n // 10])
        if n % 10:
            parts.append(EN_UNITS[n % 10])
    elif n or not parts:
        parts.append(EN_UNITS[n])
    return " ".join(parts)


def _check(n: int) -> None:
    if not isinstance(n, int) or isinstance(n, bool) or n < 0 or n > MAX_VALUE:
        raise ValueError(f"number out of range 0..{MAX_VALUE}: {n!r}")


def _token_value(tok: str, lang: str) -> int | None:
    """Look a word up in the tables, the preferred language first."""
    order = {"hi": (HI_VALUE, EN_VALUE, ROMAN_VALUE), "en": (EN_VALUE, ROMAN_VALUE, HI_VALUE)}[lang]
    for table in order:
        key = _roman_key(tok) if table is ROMAN_VALUE else tok
        if key in table:
            return table[key]
    return None


def parse_number(text: str, lang: str = "hi") -> int | None:
    """Read a spoken or typed number. Returns None if it is not a clean number.

    Accepts Devanagari, Roman Hindi, English words and plain digits. Anything
    that does not parse cleanly ("twenty twenty", "seven eight") is rejected
    rather than guessed at: a wrong guess would mark a child wrong for a right
    answer, or right for a wrong one.
    """
    if lang not in ("hi", "en"):
        raise ValueError("lang must be 'hi' or 'en'")
    text = text.strip().lower()
    if text[:1] in ("-", "+"):
        return None
    tokens = [t for t in re.split(r"[\s,\-]+", text) if t and t != "and"]
    if not tokens:
        return None
    if len(tokens) == 1 and tokens[0].isascii() and tokens[0].isdigit():
        n = int(tokens[0]) if len(tokens[0]) <= 4 else MAX_VALUE + 1
        return n if n <= MAX_VALUE else None
    total = 0          # thousands already closed
    group = 0          # hundreds so far in the current thousand
    pending: int | None = None   # a 0..99 word waiting to be used
    have_thousand = False
    for tok in tokens:
        v = _token_value(tok, lang)
        if v is None:
            return None
        if v < 100:
            if pending is None:
                pending = v
            elif pending >= 20 and pending % 10 == 0 and 1 <= v <= 9:
                pending += v                       # English "twenty" "five"
            else:
                return None
        elif v == 100:
            if pending is None:
                if group:
                    return None
                multiplier = 1
            else:
                multiplier = pending
            if group or multiplier < 1 or multiplier > 99:
                return None
            group = multiplier * 100
            pending = None
        else:                                       # thousand
            multiplier = group + (pending or 0) or 1
            if have_thousand or multiplier > 9:
                return None
            total += multiplier * 1000
            have_thousand = True
            group = 0
            pending = None
    result = total + group + (pending or 0)
    return result if 0 <= result <= MAX_VALUE else None
