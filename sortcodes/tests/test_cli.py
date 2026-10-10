import csv

import pytest

from conftest import FIX_INSTITUTIONS, FIX_SORT_CODES
from sortcode_lookup import main

HEADER = "sort_code,match,candidates,context,added"


@pytest.fixture
def q(tmp_path):
    return tmp_path / "to_verify.csv"


def run(args, q):
    return main(args + ["--sort-codes", str(FIX_SORT_CODES),
                        "--institutions", str(FIX_INSTITUTIONS), "--queue", str(q)])


def rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def test_single_code_prints_bank(q, capsys):
    assert run(["60-01-73"], q) == 0
    assert "NatWest" in capsys.readouterr().out


def test_invalid_single_code(q):
    assert run(["12345"], q) == 2


def test_unknown_queued_once(q):
    run(["990000"], q)
    run(["990000"], q)
    r = rows(q)
    assert len(r) == 1 and r[0]["sort_code"] == "990000" and r[0]["match"] == "unknown"


def test_queue_created_with_header(q):
    assert not q.exists()
    run(["990000"], q)
    assert q.read_text(encoding="utf-8").splitlines()[0] == HEADER


def test_ambiguous_queued_with_candidates(q):
    run(["309500"], q)
    assert rows(q)[0]["candidates"] == "Lloyds;TSB"


def test_context_recorded(q):
    run(["990000", "--context", "1234567"], q)
    assert rows(q)[0]["context"] == "1234567"


@pytest.fixture
def csv_run(tmp_path, q):
    src = tmp_path / "in.csv"
    src.write_text("church,sort_code\nA,04-00-04\nB,\nC,not a code\nD,60-01-73\nE,99-00-00\n",
                   encoding="utf-8")
    out = tmp_path / "out.csv"
    rc = run(["--csv", str(src), "--column", "sort_code", "--out", str(out),
              "--context-column", "church"], q)
    return rc, rows(out)


def test_csv_mode_keeps_leading_zero_and_survives_bad_rows(csv_run):
    rc, out = csv_run
    assert rc == 0 and len(out) == 5
    a, b, c, d, _ = out
    assert a["sort_code"] == "04-00-04"
    assert (a["sc_normalised"], a["sc_bank"]) == ("040004", "Monzo")
    assert b["sc_match"] == "invalid" and c["sc_match"] == "invalid"
    assert d["sc_bank"] == "NatWest"


def test_csv_row_with_extra_field_does_not_crash(tmp_path, q):
    src = tmp_path / "in.csv"
    src.write_text("church,sort_code\nA,60-01-73\nB,04-00-04,stray\n", encoding="utf-8")
    out = tmp_path / "out.csv"
    assert run(["--csv", str(src), "--column", "sort_code", "--out", str(out)], q) == 0
    assert [r["sc_bank"] for r in rows(out)] == ["NatWest", "Monzo"]


def test_queue_saved_by_excel_with_bom(q):
    q.write_text("﻿" + HEADER + "\n990000,unknown,,,2026-10-10\n", encoding="utf-8")
    assert run(["990000"], q) == 0
    assert run(["980000"], q) == 0
    assert [r["sort_code"] for r in rows(q)] == ["990000", "980000"]


def test_wrong_column_is_an_error(tmp_path, q):
    src = tmp_path / "in.csv"
    src.write_text("church,sort_code\nA,60-01-73\n", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        run(["--csv", str(src), "--column", "sortcode", "--out", str(tmp_path / "o.csv")], q)
    assert e.value.code != 0


def test_csv_mode_writes_queue_once(tmp_path, q, monkeypatch):
    import sortcode_lookup
    calls = []
    real = sortcode_lookup.queue_unresolved
    monkeypatch.setattr(sortcode_lookup, "queue_unresolved",
                        lambda *a, **k: calls.append(1) or real(*a, **k))
    src = tmp_path / "in.csv"
    src.write_text("church,sort_code\n" + "".join(f"c{i},99-00-{i:02d}\n" for i in range(30)),
                   encoding="utf-8")
    run(["--csv", str(src), "--column", "sort_code", "--out", str(tmp_path / "o.csv"),
         "--context-column", "church"], q)
    assert len(calls) == 1
    queued = rows(q)
    assert len(queued) == 30 and queued[5]["context"] == "c5"


def test_known_codes_not_queued(csv_run, q):
    queued = {r["sort_code"]: r for r in rows(q)}
    assert set(queued) == {"990000"}
    assert queued["990000"]["context"] == "E"
