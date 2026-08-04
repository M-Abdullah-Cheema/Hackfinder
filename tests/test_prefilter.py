from core.prefilter import is_likely_opportunity, score_opportunity_text


def test_keeps_hackathon_post():
    text = (
        "Join GDG Islamabad Cloud Hackathon this Saturday! "
        "Register at https://forms.gle/example before the deadline."
    )
    assert is_likely_opportunity(text)
    assert score_opportunity_text(text) >= 2


def test_drops_short_noise():
    assert not is_likely_opportunity("hello world")


def test_keeps_workshop_signal():
    text = "Free AI workshop and networking session with speakers from AWS and Google."
    assert is_likely_opportunity(text)
