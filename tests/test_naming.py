from wowhelper.naming import fold, match_character, normalize, strip_realm

ROSTER = ["Ðaylen", "Mórli", "Nërdz", "Huschee", "Sgtbubbels", "Totó", "Lotuß"]


def test_strip_realm():
    assert strip_realm("Huschee-Blackhand") == "Huschee"
    assert strip_realm("Huschee") == "Huschee"


def test_exact_case_insensitive():
    hit, _ = match_character("huschee", ROSTER)
    assert hit == "Huschee"


def test_exact_with_special_chars():
    hit, _ = match_character("mórli", ROSTER)
    assert hit == "Mórli"


def test_folded_match_umlaut():
    hit, _ = match_character("Nerdz", ROSTER)
    assert hit == "Nërdz"


def test_folded_match_eth():
    hit, _ = match_character("Daylen", ROSTER)
    assert hit == "Ðaylen"


def test_folded_match_sharp_s():
    hit, _ = match_character("Lotuss", ROSTER)
    assert hit == "Lotuß"


def test_realm_suffix_in_query():
    hit, _ = match_character("Totó-Blackhand", ROSTER)
    assert hit == "Totó"


def test_no_match_gives_suggestions():
    hit, suggestions = match_character("Huschi", ROSTER)
    assert hit is None
    assert "Huschee" in suggestions


def test_fold_is_ascii_for_roster():
    for name in ROSTER:
        assert fold(name).isascii()


def test_normalize_nfc_equivalence():
    # 'ó' als vorkomponiertes Zeichen vs. 'o' + Kombinationszeichen
    assert normalize("Mórli") == normalize("Mórli")
