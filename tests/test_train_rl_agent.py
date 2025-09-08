import os
import sys
import types
import pytest

# Ensure repository root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Stub out optional dependencies used during import
sys.modules.setdefault("mss", types.SimpleNamespace(mss=lambda: types.SimpleNamespace(close=lambda: None)))
sys.modules.setdefault("pygetwindow", types.SimpleNamespace(getAllWindows=lambda: []))

from training import train_rl_agent


def test_env_closed_on_training_exception(monkeypatch, tmp_path):
    env_holder = {}

    class DummyEnv:
        def __init__(self, frame_shape):
            self.closed = False

        def close(self):
            self.closed = True

    def fake_env(frame_shape):
        env = DummyEnv(frame_shape)
        env_holder["env"] = env
        return env

    class DummyModel:
        def __init__(self, policy, env, **kwargs):
            self.env = env

        def learn(self, total_timesteps):  # pragma: no cover - raising intentionally
            raise RuntimeError("boom")

        def save(self, path):
            pass

    args = types.SimpleNamespace(
        algo="dqn",
        total_timesteps=1,
        learning_rate=0.001,
        buffer_size=1,
        frame_shape=(1, 1),
        batch_size=1,
        exploration_initial_eps=1.0,
        exploration_final_eps=0.05,
        exploration_fraction=0.1,
        gamma=0.99,
        target_update_interval=1,
        tensorboard_log=str(tmp_path),
        save_name="test_model",
    )

    monkeypatch.setattr(train_rl_agent, "parse_args", lambda: args)
    monkeypatch.setattr(train_rl_agent, "Metin2Env", fake_env)
    monkeypatch.setitem(train_rl_agent.ALGORITHMS, "dqn", DummyModel)

    with pytest.raises(RuntimeError):
        train_rl_agent.main()

    assert env_holder["env"].closed is True
