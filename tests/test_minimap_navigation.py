import os
import sys
import types
import importlib.util

import numpy as np

# Repository root
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Create namespace package for 'agent'
agent_pkg = types.ModuleType("agent")
agent_pkg.__path__ = [os.path.join(repo_root, "agent")]
sys.modules["agent"] = agent_pkg

# Load GameState module
spec = importlib.util.spec_from_file_location("agent.game_state", os.path.join(repo_root, "agent", "game_state.py"))
game_state = importlib.util.module_from_spec(spec)
sys.modules["agent.game_state"] = game_state
spec.loader.exec_module(game_state)
agent_pkg.game_state = game_state
GameState = game_state.GameState

# Provide stub game_controller
gc_mod = types.ModuleType("agent.game_controller")
gc_mod.controller = types.SimpleNamespace(state=GameState())
sys.modules["agent.game_controller"] = gc_mod
agent_pkg.game_controller = gc_mod

gc = gc_mod

# Load minimap module
spec = importlib.util.spec_from_file_location("agent.minimap", os.path.join(repo_root, "agent", "minimap.py"))
minimap = importlib.util.module_from_spec(spec)
sys.modules["agent.minimap"] = minimap
spec.loader.exec_module(minimap)
agent_pkg.minimap = minimap


def test_extract_and_navigate_updates_state():
    grid = np.array([
        [0, 0, 0],
        [1, 1, 0],
        [2, 0, 0],
    ], dtype=np.uint8)

    pos = minimap.extract_player_pos(grid)
    assert pos == (0, 2)
    assert gc.controller.state.player_pos == (0, 2)

    path = minimap.navigate_to((2, 0))
    assert path == [(0, 2), (1, 2), (2, 2), (2, 1), (2, 0)]
    assert gc.controller.state.player_pos == (2, 0)
