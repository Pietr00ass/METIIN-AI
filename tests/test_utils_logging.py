import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import utils.git_update as git_update
import utils.requirements_check as req_check


def test_update_repository_logs(monkeypatch, caplog, tmp_path):
    def fake_check_call(cmd, cwd=None):
        return 0

    monkeypatch.setattr(git_update.subprocess, "check_call", fake_check_call)
    caplog.set_level(logging.INFO)
    assert git_update.update_repository(repo_dir=tmp_path)
    assert "Checking for updates from GitHub..." in caplog.text
    assert "Repository is up to date." in caplog.text


def test_check_requirements_logs(monkeypatch, caplog, tmp_path):
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("nonexistent-package==0\n")

    monkeypatch.setattr(req_check, "update_requirements", lambda reqs: False)
    caplog.set_level(logging.INFO)

    result = req_check.check_requirements(req_file)
    assert result is False
    log_text = caplog.text
    assert "Unmet dependencies detected:" in log_text
    assert "Attempting to install missing dependencies..." in log_text
    assert "Automatic installation failed." in log_text

