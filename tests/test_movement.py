import pytest

from agent.movement import MovementController
from agent.wasd import KeyHold


def make_tgt(x1, x2, W=100, H=100):
    return {"bbox": (x1, 0, x2, H)}


def test_move_forward_right_diagonal():
    keys = KeyHold(dry=True)
    mc = MovementController(keys, desired_w=0.3, deadzone=0.05)
    tgt = make_tgt(60, 80)
    bw = mc.move(tgt, None, (100, 100))
    assert bw == pytest.approx(0.2)
    assert keys.down == {"w", "d"}
    keys.stop()


def test_move_backward_left_diagonal():
    keys = KeyHold(dry=True)
    mc = MovementController(keys, desired_w=0.3, deadzone=0.05)
    tgt = make_tgt(10, 50)
    bw = mc.move(tgt, None, (100, 100))
    assert bw == pytest.approx(0.4)
    assert keys.down == {"s", "a"}
    keys.stop()
