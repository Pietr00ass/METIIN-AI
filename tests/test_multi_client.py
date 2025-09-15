import sys
import types
from pathlib import Path


def test_client_rotation(monkeypatch):
    # Ensure repository root is on sys.path
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))

    # Stub optional dependencies used by window capture
    monkeypatch.setitem(sys.modules, "mss", types.SimpleNamespace(mss=lambda: None))
    monkeypatch.setitem(
        sys.modules, "pygetwindow", types.SimpleNamespace(getAllWindows=lambda: [])
    )

    # Provide lightweight stub for the 'agent' package to avoid heavy imports
    agent_pkg = types.ModuleType("agent")
    agent_pkg.__path__ = [str(root / "agent")]
    agent_pkg.AgentConfig = object
    sys.modules.setdefault("agent", agent_pkg)

    from agent.multi_client import ClientManager

    steps = []

    class DummyWindow:
        def __init__(self, name):
            self.name = name

    class DummyStrategy:
        def __init__(self, cfg=None, window_capture=None):
            self.win = window_capture

        def step(self):
            steps.append(self.win.name)

        def stop(self):
            pass

    windows = [DummyWindow("A"), DummyWindow("B"), DummyWindow("C")]
    mgr = ClientManager(windows)
    mgr.run_cycle(DummyStrategy, per_client_sec=0)

    assert steps == ["A", "B", "C"]
