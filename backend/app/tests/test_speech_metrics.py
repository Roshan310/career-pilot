from app.schemas.interview import TranscriptSegment
from app.services import speech_metrics as sp


def seg(start_ms: float, end_ms: float, text: str = "words") -> TranscriptSegment:
    return TranscriptSegment(text=text, start_ms=start_ms, end_ms=end_ms)


def test_wpm_is_words_over_minutes():
    metrics = sp.compute_speech_metrics("one two three four", duration_seconds=30)
    assert metrics["word_count"] == 4
    assert metrics["wpm"] == 8.0  # 4 words in half a minute


def test_wpm_is_none_when_duration_is_zero():
    metrics = sp.compute_speech_metrics("one two", duration_seconds=0)
    assert metrics["word_count"] == 2
    assert metrics["wpm"] is None


def test_filler_count_matches_specs_list_including_phrases():
    transcript = "Um, I like, you know, sort of led the migration, uh, end to end."
    # um, like, you know, sort of, uh
    assert sp.count_fillers(transcript) == 5


def test_filler_matching_respects_word_boundaries():
    # "unlike" contains "like"; "umbrella" contains "um"; "knowledge" contains "know"
    assert sp.count_fillers("Unlike an umbrella, my knowledge grew.") == 0


def test_longest_pause_is_the_biggest_gap_between_segments():
    segments = [seg(0, 1000), seg(3000, 4000), seg(9000, 10000)]
    assert sp.longest_pause_ms(segments) == 5000.0


def test_longest_pause_ignores_time_before_the_first_segment():
    # 8s of thinking before speaking is not a pause mid-answer
    segments = [seg(8000, 9000), seg(9500, 10000)]
    assert sp.longest_pause_ms(segments) == 500.0


def test_longest_pause_is_none_without_usable_segments():
    assert sp.longest_pause_ms(None) is None
    assert sp.longest_pause_ms([]) is None
    assert sp.longest_pause_ms([seg(0, 1000)]) is None  # a single segment has no gap


def test_metrics_omit_pause_when_provider_gave_no_segments():
    # A provider that can't supply timings gets a null, never a fabricated number.
    metrics = sp.compute_speech_metrics("some answer here", duration_seconds=10)
    assert metrics["longest_pause_ms"] is None


def test_empty_or_whitespace_transcript_has_no_metrics():
    assert sp.compute_speech_metrics("", duration_seconds=5) is None
    assert sp.compute_speech_metrics("   ", duration_seconds=5) is None


def test_source_is_recorded_so_reports_survive_a_provider_swap():
    assert sp.compute_speech_metrics("hi there", 10)["source"] == "browser_speech"
    assert sp.compute_speech_metrics("hi there", 10, source="server_stt")["source"] == "server_stt"


def test_aggregate_totals_words_and_speaking_time():
    per_turn = [
        sp.compute_speech_metrics("one two three four", duration_seconds=60),
        sp.compute_speech_metrics(" ".join(["word"] * 200), duration_seconds=60),
    ]
    rollup = sp.aggregate_speech_metrics(per_turn)
    assert rollup["total_words"] == 204
    assert rollup["total_speaking_seconds"] == 120.0
    assert rollup["avg_wpm"] == 102.0
    assert rollup["turns_measured"] == 2


def test_aggregate_short_answer_does_not_dominate_avg_wpm():
    per_turn = [
        sp.compute_speech_metrics("one two", duration_seconds=1),  # 120 wpm over 1s
        sp.compute_speech_metrics(" ".join(["word"] * 60), duration_seconds=120),  # 30 wpm over 2min
    ]
    rollup = sp.aggregate_speech_metrics(per_turn)
    # mean of per-turn wpms would be 75; total-words-over-total-time is ~30.7
    assert rollup["avg_wpm"] < 35


def test_aggregate_rolls_up_fillers_and_worst_pause():
    per_turn = [
        sp.compute_speech_metrics("um yes", 10, [seg(0, 100), seg(600, 700)]),
        sp.compute_speech_metrics("uh no like", 10, [seg(0, 100), seg(3000, 3100)]),
    ]
    rollup = sp.aggregate_speech_metrics(per_turn)
    assert rollup["total_filler_count"] == 3
    assert rollup["longest_pause_ms"] == 2900.0


def test_aggregate_skips_unmeasured_turns_and_returns_none_when_all_are():
    measured = sp.compute_speech_metrics("a real answer", 10)
    assert sp.aggregate_speech_metrics([None, measured, None])["turns_measured"] == 1
    assert sp.aggregate_speech_metrics([None, None]) is None
    assert sp.aggregate_speech_metrics([]) is None


def test_vad_shaped_segments_measure_pauses_without_carrying_per_segment_text():
    """Server-side transcription returns one transcript for the whole answer, not
    text per utterance, so the recorded provider sends VAD speech bursts with the
    full text on the first segment and "" on the rest.

    That shape has to work: word_count and fillers come from `transcript`, which
    is a separate argument, and longest_pause_ms reads only the timings. This is
    the arrangement that finally makes the pause real rather than estimated —
    it's measured from the audio, not inferred from transcription lag.
    """
    metrics = sp.compute_speech_metrics(
        "I um rewrote the retry loop and shipped it on Friday",
        duration_seconds=12,
        segments=[seg(0, 2000, "I um rewrote the retry loop and shipped it on Friday"),
                  seg(5200, 8000, ""),
                  seg(8300, 12000, "")],
        source="server_stt",
    )

    assert metrics["word_count"] == 11  # from the transcript, not the segments
    assert metrics["filler_count"] == 1  # "um" still counted
    assert metrics["longest_pause_ms"] == 3200  # the real 2000→5200 silence
    assert metrics["source"] == "server_stt"
