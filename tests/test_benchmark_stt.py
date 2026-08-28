from scripts.benchmark_stt import character_error_rate, parse_bool


def test_parse_bool_accepts_common_values():
    assert parse_bool("true") is True
    assert parse_bool("OFF") is False


def test_character_error_rate_normalizes_whitespace():
    assert character_error_rate(" 자비스 오늘 ", "자비스오늘") == 0.0
    assert character_error_rate("자비스", "자비스 오늘") > 0
