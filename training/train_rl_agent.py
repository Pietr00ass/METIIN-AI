from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path

from agent_rl import Metin2Env

try:  # pragma: no cover - optional dependency for tests
    from stable_baselines3 import A2C, DQN, PPO
except Exception:  # pragma: no cover - allow importing without sb3 installed
    A2C = DQN = PPO = None  # type: ignore


ALGORITHMS = {
    "dqn": DQN,
    "ppo": PPO,
    "a2c": A2C,
}


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Train an RL agent in Metin2")
    ap.add_argument("--algo", choices=ALGORITHMS.keys(), default="dqn")
    ap.add_argument("--total-timesteps", type=int, default=10000, help="liczba kroków")
    ap.add_argument("--learning-rate", type=float, default=1e-3)
    ap.add_argument(
        "--buffer-size",
        type=int,
        default=10000,
        help=
        "Replay buffer capacity (transitions). Memory usage scales roughly as "
        "buffer_size × frame_pixels bytes; default 10000 with 84×84×3 frames "
        "uses about 210 MB.",
    )
    ap.add_argument(
        "--frame-shape",
        type=int,
        nargs=2,
        metavar=("H", "W"),
        default=(84, 84),
        help="Resize captured frames to this height and width.",
    )
    ap.add_argument(
        "--memory-limit",
        type=int,
        default=512,
        help="Maximum allowed replay buffer memory in MB.",
    )
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--exploration-initial-eps", type=float, default=1.0)
    ap.add_argument("--exploration-final-eps", type=float, default=0.05)
    ap.add_argument("--exploration-fraction", type=float, default=0.1)
    ap.add_argument("--gamma", type=float, default=0.99)
    ap.add_argument("--target-update-interval", type=int, default=1000)
    ap.add_argument("--tensorboard-log", default="runs/rl", help="log dir")
    ap.add_argument("--save-name", default="metin2_rl_agent")

    args = ap.parse_args()
    h, w = args.frame_shape
    frame_pixels = h * w * 3
    required = args.buffer_size * frame_pixels
    if required > args.memory_limit * 1024 * 1024:
        ap.error(
            f"buffer_size × frame_pixels requires {required / (1024 * 1024):.1f} MB, "
            f"exceeding --memory-limit {args.memory_limit} MB",
        )
    args.frame_shape = (h, w)
    return args


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = parse_args()

    algo_cls = ALGORITHMS.get(args.algo)
    if algo_cls is None:
        raise RuntimeError("stable_baselines3 is required for this script")

    run_dir = Path(args.tensorboard_log) / f"{args.algo}_{datetime.now():%Y%m%d_%H%M%S}"
    run_dir.mkdir(parents=True, exist_ok=True)

    env = Metin2Env(frame_shape=(*args.frame_shape, 3))

    kwargs = dict(learning_rate=args.learning_rate, tensorboard_log=str(run_dir))
    if args.algo == "dqn":
        kwargs.update(
            buffer_size=args.buffer_size,
            batch_size=args.batch_size,
            exploration_initial_eps=args.exploration_initial_eps,
            exploration_final_eps=args.exploration_final_eps,
            exploration_fraction=args.exploration_fraction,
            gamma=args.gamma,
            target_update_interval=args.target_update_interval,
        )

    model = algo_cls("CnnPolicy", env, **kwargs)
    logging.info("Starting training for %s steps", args.total_timesteps)
    model.learn(total_timesteps=args.total_timesteps)
    model_path = run_dir / args.save_name
    model.save(str(model_path))
    env.close()
    logging.info("Model saved to %s", model_path)


if __name__ == "__main__":
    main()
