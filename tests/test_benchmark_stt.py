from scripts.benchmark_stt import benchmark_cpu_thread_values, build_model_kwargs, character_error_rate, default_compute_type, parse_bool


def test_benchmark_device_defaults_and_model_kwargs():
    assert default_compute_type("cpu") == "int8"
    assert default_compute_type("cuda") == "float16"
    cpu = build_model_kwargs("cpu", "int8", 6, None)
    assert cpu["device"] == "cpu" and cpu["compute_type"] == "int8" and cpu["cpu_threads"] == 6
    cuda = build_model_kwargs("cuda", "float16", 6, None)
    assert cuda["device"] == "cuda" and cuda["compute_type"] == "float16"
    assert "cpu_threads" not in cuda
    assert benchmark_cpu_thread_values("cpu", [2, 4, 6]) == [2, 4, 6]
    assert benchmark_cpu_thread_values("cuda", [2, 4, 6]) == [0]


def test_parse_bool_accepts_common_values():
    assert parse_bool("true") is True
    assert parse_bool("OFF") is False


def test_character_error_rate_normalizes_whitespace():
    assert character_error_rate(" 자비스 오늘 ", "자비스오늘") == 0.0
    assert character_error_rate("자비스", "자비스 오늘") > 0
