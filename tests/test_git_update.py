import subprocess
import sys

import pytest

from utils import git_update


def test_update_repository_success(monkeypatch, tmp_path):
    calls = {}

    def fake_check_call(cmd, cwd):
        calls['cmd'] = cmd
        calls['cwd'] = cwd

    monkeypatch.setattr(git_update.subprocess, 'check_call', fake_check_call)
    messages = []
    monkeypatch.setattr(git_update, '_notify', lambda msg: messages.append(msg))

    repo = tmp_path
    result = git_update.update_repository(repo)

    assert result is True
    assert calls['cmd'] == ['git', 'pull', '--ff-only']
    assert calls['cwd'] == repo
    assert messages == ['Repository is up to date.']


def test_update_repository_failure(monkeypatch, tmp_path):
    def fake_check_call(cmd, cwd):
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(git_update.subprocess, 'check_call', fake_check_call)
    messages = []
    monkeypatch.setattr(git_update, '_notify', lambda msg: messages.append(msg))

    result = git_update.update_repository(tmp_path)

    assert result is False
    assert messages == ['Failed to update repository.']


def test_notify_prints_when_pyside_missing(capsys, monkeypatch):
    monkeypatch.setitem(sys.modules, 'PySide6', None)
    git_update._notify('hello')
    assert 'hello' in capsys.readouterr().out

