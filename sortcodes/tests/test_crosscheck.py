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


class FakeResp:
    def __init__(self, status, body, ctype="application/json"):
        self.status_code, self._body, self.headers = status, body, {"content-type": ctype}

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


def test_fetch_masks_url_encoded_key(monkeypatch):
    key = "SECRETKEY+/="
    monkeypatch.setattr(crosscheck.requests, "get",
                        lambda *a, **k: FakeResp(401, {"message": "Invalid key SECRETKEY%2B%2F%3D"}))
    with pytest.raises(RuntimeError) as e:
        crosscheck.fetch_bank("600173", key)
    assert "SECRETKEY" not in str(e.value)


def test_fetch_null_message(monkeypatch):
    monkeypatch.setattr(crosscheck.requests, "get", lambda *a, **k: FakeResp(403, {"message": None}))
    with pytest.raises(RuntimeError, match="HTTP 403"):
        crosscheck.fetch_bank("600173", "k")


def test_fetch_non_json_200(monkeypatch):
    monkeypatch.setattr(crosscheck.requests, "get",
                        lambda *a, **k: FakeResp(200, ValueError("not json"), "text/html"))
    with pytest.raises(RuntimeError, match="not JSON"):
        crosscheck.fetch_bank("600173", "k")
