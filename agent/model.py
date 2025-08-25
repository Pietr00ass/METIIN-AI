import torch, torch.nn as nn
import torchvision.models as models

class ClickPolicy(nn.Module):
    def __init__(self):
        super().__init__()
        base = models.resnet18(weights=None)
        base.fc = nn.Identity()
        self.backbone = base
        self.head_point = nn.Sequential(nn.Linear(512, 256), nn.ReLU(), nn.Linear(256, 2), nn.Sigmoid())
        self.head_click = nn.Sequential(nn.Linear(512, 128), nn.ReLU(), nn.Linear(128, 1), nn.Sigmoid())
    def forward(self, x):
        f = self.backbone(x)
        point = self.head_point(f)  # (B,2) w [0,1]
        click = self.head_click(f)  # (B,1) w [0,1]
        return point, click
