from __future__ import annotations

import torch
import torch.nn as nn
import torchvision.models as models


class ClickPolicy(nn.Module):
    """Predicts click location and probability from an RGB screenshot.

    The network expects a batch of images with shape ``(B, 3, H, W)`` and
    values in the ``[0, 1]`` range.  It returns a tuple containing:

    * ``point`` – tensor of shape ``(B, 2)`` with normalized ``x`` and ``y``
      coordinates in ``[0, 1]``.
    * ``click`` – tensor of shape ``(B, 1)`` with click probability in
      ``[0, 1]``.
    """

    def __init__(
        self,
        weights: models.ResNet18_Weights | None = None,
    ) -> None:
        """Initialize the policy.

        Args:
            weights: Optional torchvision weights used to initialize the
                ResNet18 backbone.
        """

        super().__init__()
        base = models.resnet18(weights=weights)
        base.fc = nn.Identity()
        self.backbone = base
        self.head_point = nn.Sequential(
            nn.Linear(512, 256), nn.ReLU(), nn.Linear(256, 2), nn.Sigmoid()
        )
        self.head_click = nn.Sequential(
            nn.Linear(512, 128), nn.ReLU(), nn.Linear(128, 1), nn.Sigmoid()
        )

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Run a forward pass.

        Args:
            x: Batch of images with shape ``(B, 3, H, W)`` and values in
                ``[0, 1]``.

        Returns:
            A tuple ``(point, click)`` where ``point`` has shape ``(B, 2)`` and
            ``click`` has shape ``(B, 1)``. Both outputs are in the ``[0, 1]``
            range.
        """

        f = self.backbone(x)
        point = self.head_point(f)  # (B,2) w [0,1]
        click = self.head_click(f)  # (B,1) w [0,1]
        return point, click
