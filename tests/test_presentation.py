from app.agent.presentation import parse_presentation_response


def test_valid_presentation_marker_is_extracted_without_second_llm_call():
    text, hint = parse_presentation_response(
        '좋은 소식이에요. <!--JARVIS_PRESENTATION {"emotion":"happy","intensity":0.6,"motion_intent":"positive"}-->'
    )
    assert text == "좋은 소식이에요."
    assert hint.emotion == "happy"
    assert hint.intensity == 0.6
    assert hint.motion_intent == "positive"


def test_missing_or_invalid_metadata_falls_back_to_neutral():
    text, hint = parse_presentation_response("그냥 답변입니다.")
    assert text == "그냥 답변입니다."
    assert hint.emotion == "neutral"
    assert parse_presentation_response("답변 <!--JARVIS_PRESENTATION {bad}-->")[1].emotion == "neutral"


def test_json_envelope_is_supported_and_invalid_values_are_safe():
    text, hint = parse_presentation_response(
        '{"reply":"분석 중입니다.","presentation_hint":{"emotion":"thinking","intensity":0.8,"motion_intent":"subtle"}}'
    )
    assert text == "분석 중입니다."
    assert hint.motion_intent == "subtle"
    _, fallback = parse_presentation_response('{"reply":"ok","presentation_hint":{"emotion":"unknown"}}')
    assert fallback.emotion == "neutral"
