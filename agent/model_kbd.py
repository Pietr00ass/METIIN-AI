from __future__ import annotations

import torch
import torch.nn as nn
import torchvision.models as models


class KbdPolicy(nn.Module):
    """Predicts keyboard actions from an RGB screenshot.

    The model expects input tensors of shape ``(B, 3, H, W)`` with values in
    ``[0, 1]`` and outputs four probabilities corresponding to the ``W``, ``A``,
    ``S`` and ``D`` keys.
    """

    def __init__(
        self,
        weights: models.ResNet18_Weights | None = None,
    ) -> None:
        """Initialize the policy.

        Args:
            weights: Optional torchvision weights for the ResNet18 backbone.
        """

        super().__init__()
        base = models.resnet18(weights=weights)
        base.fc = nn.Identity()
        self.backbone = base
        self.head = nn.Sequential(
            nn.Linear(512, 256), nn.ReLU(), nn.Linear(256, 4), nn.Sigmoid()
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Run a forward pass.

        Args:
            x: Batch of images with shape ``(B, 3, H, W)`` and values in
                ``[0, 1]``.

        Returns:
            Tensor of shape ``(B, 4)`` with probabilities for ``W``, ``A``,
            ``S`` and ``D`` keys in the ``[0, 1]`` range.
        """

        f = self.backbone(x)
        return self.head(f)  # W,A,S,D w [0,1]
