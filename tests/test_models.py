import torch
import torchvision.models as models
import pytest

from agent.model import ClickPolicy
from agent.model_kbd import KbdPolicy


@torch.inference_mode()
@pytest.mark.parametrize("weights", [None, models.ResNet18_Weights.IMAGENET1K_V1])
def test_click_policy_forward(weights):
    model = ClickPolicy(weights=weights)
    x = torch.rand(1, 3, 224, 224)
    point, click = model(x)
    assert point.shape == (1, 2)
    assert click.shape == (1, 1)


@torch.inference_mode()
@pytest.mark.parametrize("weights", [None, models.ResNet18_Weights.IMAGENET1K_V1])
def test_kbd_policy_forward(weights):
    model = KbdPolicy(weights=weights)
    x = torch.rand(1, 3, 224, 224)
    out = model(x)
    assert out.shape == (1, 4)
