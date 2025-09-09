from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Train a behavior cloning model")
    ap.add_argument("--dataset", required=True, help="path to npz with 'obs' and 'actions'")
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--learning-rate", type=float, default=1e-3)
    ap.add_argument("--save-path", default="bc_model.pt")
    return ap.parse_args()


def build_model(num_actions: int) -> nn.Module:
    return nn.Sequential(
        nn.Conv2d(3, 16, kernel_size=3, stride=2),
        nn.ReLU(),
        nn.Conv2d(16, 32, kernel_size=3, stride=2),
        nn.ReLU(),
        nn.Flatten(),
        nn.Linear(32 * 20 * 20, 128),  # assumes 84x84 input
        nn.ReLU(),
        nn.Linear(128, num_actions),
    )


def main() -> None:
    args = parse_args()
    data = np.load(args.dataset)
    obs = torch.from_numpy(data["obs"]).float() / 255.0
    obs = obs.permute(0, 3, 1, 2)  # NHWC -> NCHW
    actions = torch.from_numpy(data["actions"]).long()
    dataset = TensorDataset(obs, actions)
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True)

    num_actions = int(actions.max().item() + 1)
    model = build_model(num_actions)
    opt = optim.Adam(model.parameters(), lr=args.learning_rate)
    loss_fn = nn.CrossEntropyLoss()

    model.train()
    for _ in range(args.epochs):
        for x, y in loader:
            opt.zero_grad()
            logits = model(x)
            loss = loss_fn(logits, y)
            loss.backward()
            opt.step()

    Path(args.save_path).parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), args.save_path)


if __name__ == "__main__":  # pragma: no cover - script entry point
    main()
