"""Тест retention-чистки run_logs: удаляем старше cutoff, свежие оставляем."""

import datetime as dt

from inmemory import InMemoryRunLog


def _log(repo, created_at):
    repo.write_run_logs([{
        "created_at": created_at, "module": "pii", "input_text": "",
        "output": "{}", "duration_ms": 1.0, "meta": None,
    }])


def test_delete_run_logs_before_removes_only_old():
    repo = InMemoryRunLog()
    now = dt.datetime.utcnow()
    _log(repo, now - dt.timedelta(days=40))   # старый
    _log(repo, now - dt.timedelta(days=31))   # старый
    _log(repo, now - dt.timedelta(days=5))    # свежий
    _log(repo, now)                           # свежий

    cutoff = now - dt.timedelta(days=30)
    deleted = repo.delete_run_logs_before(cutoff)

    assert deleted == 2
    remaining = repo.query_run_logs(limit=100)
    assert len(remaining) == 2
    assert all(r.created_at >= cutoff for r in remaining)


def test_delete_run_logs_before_noop_when_all_fresh():
    repo = InMemoryRunLog()
    now = dt.datetime.utcnow()
    _log(repo, now)
    assert repo.delete_run_logs_before(now - dt.timedelta(days=30)) == 0
    assert len(repo.query_run_logs(limit=100)) == 1
