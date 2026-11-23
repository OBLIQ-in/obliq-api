import sys

import pytest

from scripts import canary


@pytest.mark.parametrize(
    ("reference", "extracted", "expected"),
    [
        ("a b\nc", "abc", 0.0),
        ("abc", "axc", 1 / 3),  # substitution
        ("abc", "ac", 1 / 3),  # deletion
        ("abc", "abxc", 1 / 3),  # insertion
        ("abc", "abcabcdef", 2.0),
        ("", "", 0.0),
        ("", "x", 1.0),
    ],
)
def test_character_error_rate(reference, extracted, expected):
    assert canary.calculate_cer(reference, extracted) == pytest.approx(expected)


def test_actual_regression_exceeds_the_scheduled_canary_threshold():
    truth = "abcdefghijklmnopqrstuvwxyz"
    # One missing character in 26 is 3.85%, above the workflow's 3% SLA.
    assert canary.calculate_cer(truth, truth[:-1]) > 0.03


@pytest.mark.parametrize("contents", [None, "", " \n\t"])
def test_missing_or_empty_ground_truth_fails_before_submitting(
    contents, tmp_path, monkeypatch, capsys
):
    fixture = tmp_path / "sample.pdf"
    fixture.write_bytes(b"%PDF-1.4\nSynthetic fixture")
    truth = tmp_path / "truth.txt"
    if contents is not None:
        truth.write_text(contents, encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["canary", "--fixture", str(fixture), "--truth", str(truth)])
    monkeypatch.setattr(canary.httpx, "Client", lambda **kwargs: pytest.fail("unexpected HTTP"))
    assert canary.main() == 1
    assert str(truth) in capsys.readouterr().err


@pytest.mark.parametrize(("drop_last", "exit_code"), [(False, 0), (True, 1)])
def test_canary_enforces_accuracy_gate(drop_last, exit_code, tmp_path, monkeypatch):
    fixture = tmp_path / "sample.pdf"
    fixture.write_bytes(b"%PDF-1.4\nSynthetic fixture")
    reference = "abcdefghijklmnopqrstuvwxyz"
    truth = tmp_path / "truth.txt"
    truth.write_text(reference, encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "canary",
            "--no-warmup",
            "--fixture",
            str(fixture),
            "--truth",
            str(truth),
            "--max-cer",
            "0.03",
        ],
    )
    monkeypatch.delenv("ALERT_WEBHOOK_URL", raising=False)

    def handle(request):
        if request.url.path == "/v1/jobs":
            return canary.httpx.Response(202, json={"id": "sample-job"})
        if request.url.path == "/v1/jobs/sample-job":
            return canary.httpx.Response(200, json={"status": "succeeded"})
        assert request.url.path == "/v1/jobs/sample-job/result"
        text = reference[:-1] if drop_last else reference
        return canary.httpx.Response(
            200, json={"pages": [{"text": text}], "processing_time_ms": 10}
        )

    client_cls = canary.httpx.Client
    monkeypatch.setattr(
        canary.httpx,
        "Client",
        lambda **kwargs: client_cls(transport=canary.httpx.MockTransport(handle), **kwargs),
    )
    assert canary.main() == exit_code
