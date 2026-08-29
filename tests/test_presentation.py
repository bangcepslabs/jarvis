from app.agent.presentation import parse_presentation_response, present_refusal_response


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


def test_explicit_capability_refusal_keeps_boundary_but_uses_casual_presentation():
    raw = "저는 그런 역할극이나 성적인 콘텐츠에는 참여하지 않아요. 다른 이야기나 도움이 필요한 작업이 있다면 말씀해 주세요."

    presented = present_refusal_response("그런 역할극 해줘", raw)

    assert presented == "거기부터는 너무 노골적이잖아 ㅋㅋ 그 정도까진 안 가."
    assert "말씀해" not in presented


def test_refusal_presenter_does_not_rewrite_normal_conversation():
    response = "그건 지금은 못 해."

    assert present_refusal_response("그거 해줘", response) == response


def test_refusal_presenter_does_not_change_tool_or_non_refusal_meaning():
    response = "서버 시간이 지금은 확인되지 않아. 다른 도움이 필요하면 말해 줘."

    assert present_refusal_response("서버 시간 알려줘", response) == response
