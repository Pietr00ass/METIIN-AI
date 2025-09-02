from importlib.metadata import PackageNotFoundError
from packaging.requirements import Requirement
import sys

import pytest

from utils import requirements_check as rq


@pytest.fixture
def sample_requirements(tmp_path):
    req_file = tmp_path / 'requirements.txt'
    req_file.write_text('missing_pkg==1.0\n')
    return req_file


def test_check_requirements_installs_missing(monkeypatch, sample_requirements):
    calls = []

    def fake_version(name):
        calls.append(name)
        if len(calls) == 1:
            raise PackageNotFoundError
        return '1.0'

    monkeypatch.setattr(rq.metadata, 'version', fake_version)
    updated = []

    def fake_update(reqs):
        updated.append(list(reqs))
        return True

    monkeypatch.setattr(rq, 'update_requirements', fake_update)

    assert rq.check_requirements(sample_requirements) is True
    assert len(updated) == 1
    assert str(updated[0][0]) == 'missing_pkg==1.0'


def test_check_requirements_install_failure(monkeypatch, sample_requirements):
    def fake_version(name):
        raise PackageNotFoundError

    monkeypatch.setattr(rq.metadata, 'version', fake_version)
    monkeypatch.setattr(rq, 'update_requirements', lambda reqs: False)

    assert rq.check_requirements(sample_requirements) is False


def test_update_requirements_with_list(monkeypatch):
    called = {}

    def fake_check_call(cmd):
        called['cmd'] = cmd

    monkeypatch.setattr(rq.subprocess, 'check_call', fake_check_call)
    req = Requirement('demo>=1.0')
    assert rq.update_requirements([req]) is True
    assert 'demo>=1.0' in called['cmd']


def test_update_requirements_missing_file(tmp_path):
    missing = tmp_path / 'req.txt'
    assert rq.update_requirements(requirements=None, requirements_file=missing) is False

