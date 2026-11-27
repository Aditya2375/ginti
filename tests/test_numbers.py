import pytest

from app.numbers import HI_ROMAN, HI_WORDS, ROMAN_VALUE, _roman_key, parse_number, to_english, to_hindi


@pytest.mark.parametrize("lang,fn", [("hi", to_hindi), ("en", to_english)])
def test_every_number_round_trips(lang, fn):
    for n in range(0, 10000):
        assert parse_number(fn(n), lang) == n, (lang, n, fn(n))


def test_hindi_words_are_all_different():
    assert len(set(HI_WORDS)) == 100


def test_roman_spellings_do_not_collide():
    keys = [_roman_key(w) for w in HI_ROMAN]
    assert len(set(keys)) == 100
    for i, w in enumerate(HI_ROMAN):
        assert ROMAN_VALUE[_roman_key(w)] == i


@pytest.mark.parametrize("text,lang,want", [
    ("pachpan", "hi", 55), ("paachpan", "hi", 55), ("PACHPAN", "hi", 55),
    ("saat", "hi", 7), ("saath", "hi", 60), ("sat", "hi", 7), ("paanch sau", "hi", 500),
    ("पच्चीस", "hi", 25), ("पांच", "hi", 5), ("छः", "hi", 6), ("एक सौ पाँच", "hi", 105), ("सौ", "hi", 100),
    ("पच्चीस सौ", "hi", 2500), ("दो हजार", "hi", 2000),
    ("twenty five", "en", 25), ("twenty-five", "en", 25), ("one hundred and five", "en", 105),
    ("a", "en", None),
    ("55", "hi", 55), ("0", "en", 0), ("9999", "en", 9999),
])
def test_parse_known(text, lang, want):
    assert parse_number(text, lang) == want


@pytest.mark.parametrize("text", [
    "", "   ", "seven eight", "twenty twenty", "ten five", "hundred hundred", "one hundred one hundred",
    "thousand thousand", "दो तीन", "सात आठ नौ", "12345", "-5", "five dollars", "[unk]", "ten thousand",
    "ninety nine thousand", "एक सौ दो सौ",
])
def test_parse_rejects_what_is_not_a_clean_number(text):
    assert parse_number(text, "hi") is None
    assert parse_number(text, "en") is None


def test_out_of_range_words():
    for n in (-1, 10000, True):
        with pytest.raises(ValueError):
            to_hindi(n)
    with pytest.raises(ValueError):
        parse_number("5", "fr")
