import httpx

from scripts.jarvis_voice_client import run_pipeline


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def request(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        return self.responses.pop(0)


def response(status=200, *, json_data=None, content=b"RIFF", content_type="application/json"):
    if json_data is not None:
        return httpx.Response(status, json=json_data, headers={"content-type": content_type})
    return httpx.Response(status, content=content, headers={"content-type": content_type})


def test_text_pipeline_skips_stt_and_forwards_conversation():
    fake = FakeClient([response(json_data={"reply": "부산은 맑아요."}), response(content=b"RIFFWAV", content_type="audio/wav")])
    played = []
    reply = run_pipeline(server="http://core", text="오늘 부산 날씨 어때", audio=None, conversation_id="c1", client=fake, player=played.append, play=True)
    assert reply == "부산은 맑아요."
    assert len(fake.requests) == 2
    assert fake.requests[0][1].endswith("/api/chat")
    assert fake.requests[0][2]["json"]["conversation_id"] == "c1"
    assert played == [b"RIFFWAV"]


def test_file_pipeline_stops_on_no_speech():
    fake = FakeClient([response(json_data={"speech_detected": False, "text": ""})])
    assert run_pipeline(server="http://core", text=None, audio=b"wav", conversation_id="c1", client=fake) is None
    assert len(fake.requests) == 1
    assert fake.requests[0][1].endswith("/api/stt/transcribe")


def test_file_pipeline_posts_stt_then_chat_then_tts_and_can_save(tmp_path):
    fake = FakeClient([
        response(json_data={"speech_detected": True, "text": "자비스 부산 날씨", "language": "ko"}),
        response(json_data={"reply": "확인해볼게요."}),
        response(content=b"RIFFWAV", content_type="audio/wav"),
    ])
    output = tmp_path / "reply.wav"
    run_pipeline(server="http://core", text=None, audio=b"audio", conversation_id="voice", client=fake, save_output=str(output))
    assert [request[1] for request in fake.requests] == [
        "http://core/api/stt/transcribe", "http://core/api/chat", "http://core/api/tts/synthesize"
    ]
    assert fake.requests[1][2]["json"] == {"message": "자비스 부산 날씨", "conversation_id": "voice"}
    assert output.read_bytes() == b"RIFFWAV"


def test_stage_failure_does_not_call_downstream():
    fake = FakeClient([response(503, json_data={"detail": "unavailable"})])
    try:
        run_pipeline(server="http://core", text=None, audio=b"audio", conversation_id="c1", client=fake)
    except RuntimeError as exc:
        assert "HTTP 503" in str(exc)
    else:
        raise AssertionError("expected stage failure")
    assert len(fake.requests) == 1
