import pytest

import crosscheck
from crosscheck import compare


@pytest.mark.parametrize("ours,theirs,verdict", [
    ({"bank": "Santander", "group": "Santander UK", "match": "range"}, "Santander UK plc", "brand"),
    ({"bank": "Royal Bank of Scotland", "group": "NatWest Group", "match": "range"}, "ROYAL BANK OF SCOT", "brand"),
    ({"bank": "NatWest", "group": "NatWest Group", "match": "range"}, "NATIONAL WESTMINSTER BANK PLC", "brand"),
    ({"bank": "Halifax", "group": "Bank of Scotland", "match": "range"}, "Bank of Scotland plc", "group"),
    ({"bank": "Halifax", "group": "Lloyds Banking Group", "match": "range"}, "Lloyds Bank plc", "mismatch"),
    ({"bank": None, "group": None, "match": "unknown"}, "Monzo Bank Ltd", "unresolved_ours"),
    ({"bank": "NatWest", "group": "NatWest Group", "match": "range"}, None, "no_answer"),
    ({"bank": None, "group": None, "match": "unknown"}, "", "no_answer"),
])
def test_compare(ours, theirs, verdict):
    assert compare(ours, theirs) == verdict


def test_missing_key(monkeypatch, capsys):
    monkeypatch.delenv("ESORTCODE_API_KEY", raising=False)
    monkeypatch.setattr(crosscheck, "find_dotenv", lambda *a, **k: "")
    assert crosscheck.main(["600173"]) == 1
    out = capsys.readouterr()
    assert "ESORTCODE_API_KEY not set" in out.out + out.err


def test_main_with_fake_fetch_writes_nothing(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ESORTCODE_API_KEY", "dummy-secret-key")
    monkeypatch.setattr(crosscheck, "find_dotenv", lambda *a, **k: "")
    monkeypatch.setattr(crosscheck, "time", type("T", (), {"sleep": staticmethod(lambda s: None)}))
    calls = []
    monkeypatch.setattr(crosscheck, "fetch_bank",
                        lambda code, key, account=None: calls.append((code, account)) or "NATIONAL WESTMINSTER BANK PLC")
    assert crosscheck.main(["60-70-80", "60-01-73:00216252", "not-a-code"]) == 0
    out = capsys.readouterr().out
    assert "brand" in out and "mismatch" in out and "invalid" in out
    assert "agreement" in out.lower()
    assert "dummy-secret-key" not in out
    assert calls == [("607080", None), ("600173", "00216252")]
    assert list(tmp_path.iterdir()) == []


def test_limit(monkeypatch, capsys):
    monkeypatch.setenv("ESORTCODE_API_KEY", "k")
    monkeypatch.setattr(crosscheck, "find_dotenv", lambda *a, **k: "")
    monkeypatch.setattr(crosscheck, "time", type("T", (), {"sleep": staticmethod(lambda s: None)}))
    calls = []
    monkeypatch.setattr(crosscheck, "fetch_bank", lambda c, k, account=None: calls.append(c) or None)
    crosscheck.main(["600173", "607080", "202741", "--limit", "2"])
    assert len(calls) == 2
