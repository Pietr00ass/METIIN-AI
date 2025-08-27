import torch
import torch.nn as nn
import torchvision.models as models


class KbdPolicy(nn.Module):
    def __init__(self):
        super().__init__()
        base = models.resnet18(weights=None)
        base.fc = nn.Identity()
        self.backbone = base
        self.head = nn.Sequential(
            nn.Linear(512, 256), nn.ReLU(), nn.Linear(256, 4), nn.Sigmoid()
        )

    def forward(self, x):
        f = self.backbone(x)
        return self.head(f)  # W,A,S,D w [0,1]
