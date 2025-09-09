from __future__ import annotations

import argparse
import logging
import shutil
from datetime import datetime
from pathlib import Path

import psutil

from agent_rl import Metin2Env

try:  # pragma: no cover - optional dependency for tests
    from stable_baselines3 import A2C, DQN, PPO
    from stable_baselines3.common.env_util import make_vec_env
    from stable_baselines3.common.vec_env import VecTransposeImage
    from stable_baselines3.common.callbacks import EvalCallback
except Exception:  # pragma: no cover - allow importing without sb3 installed
    A2C = DQN = PPO = make_vec_env = VecTransposeImage = EvalCallback = None  # type: ignore


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
        help=(
            "Replay buffer capacity (transitions). Memory usage scales roughly as "
            "buffer_size × bytes_per_transition; default 10000 with 84×84×3 "
            "frames requires about 420 MB and will be reduced if RAM is insufficient."
        ),
    )
    ap.add_argument(
        "--frame-shape",
        type=int,
        nargs=2,
        metavar=("H", "W"),
        default=(84, 84),
        help="Resize captured frames to this height and width.",
    )
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--exploration-initial-eps", type=float, default=1.0)
    ap.add_argument("--exploration-final-eps", type=float, default=0.05)
    ap.add_argument("--exploration-fraction", type=float, default=0.1)
    ap.add_argument("--gamma", type=float, default=0.99)
    ap.add_argument("--target-update-interval", type=int, default=1000)
    ap.add_argument("--tensorboard-log", default="runs/rl", help="log dir")
    ap.add_argument("--save-name", default="metin2_rl_agent")
    ap.add_argument("--eval-freq", type=int, default=10000, help="Evaluation frequency")
    ap.add_argument("--kill-reward", type=float, default=1.0)
    ap.add_argument("--damage-penalty", type=float, default=1.0)
    ap.add_argument("--time-penalty", type=float, default=0.01)
    ap.add_argument("--num-envs", type=int, default=1, help="number of parallel environments")

    args = ap.parse_args()
    h, w = args.frame_shape
    frame_pixels = h * w * 3
    bytes_per_transition = frame_pixels * 4 * 2  # obs and next_obs as float32
    required = args.buffer_size * bytes_per_transition
    available = psutil.virtual_memory().available
    if required > available:
        max_transitions = available // bytes_per_transition
        if max_transitions <= 0:
            ap.error(
                f"buffer_size × bytes_per_transition requires {required / (1024 ** 2):.1f} MB, "
                f"but only {available / (1024 ** 2):.1f} MB is available",
            )
        logging.warning(
            "Reducing buffer_size from %d to %d due to limited RAM",
            args.buffer_size,
            max_transitions,
        )
        args.buffer_size = int(max_transitions)
    args.frame_shape = (h, w)
    return args


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = parse_args()

    algo_cls = ALGORITHMS.get(args.algo)
    if algo_cls is None:
        raise RuntimeError("stable_baselines3 is required for this script")

    try:  # pragma: no cover - optional dependency for tests
        import torch  # type: ignore

        if not hasattr(torch, "utils"):
            raise ImportError
        from torch.utils.tensorboard import SummaryWriter  # type: ignore  # noqa: F401

        tb_available = shutil.which("tensorboard") is not None
    except Exception:  # pragma: no cover - allow running without tensorboard
        logging.warning("TensorBoard is not installed; proceeding without logging.")
        tb_available = False

    run_dir = Path(args.tensorboard_log) / f"{args.algo}_{datetime.now():%Y%m%d_%H%M%S}"
    run_dir.mkdir(parents=True, exist_ok=True)

    def _make_env() -> Metin2Env:
        try:
            return Metin2Env(
                frame_shape=(*args.frame_shape, 3),
                kill_reward=getattr(args, "kill_reward", 1.0),
                damage_penalty=getattr(args, "damage_penalty", 1.0),
                time_penalty=getattr(args, "time_penalty", 0.01),
            )
        except TypeError:  # pragma: no cover - fallback for test stubs
            return Metin2Env(frame_shape=(*args.frame_shape, 3))

    try:
        env = make_vec_env(_make_env, n_envs=args.num_envs)
        env = VecTransposeImage(env)
    except Exception:  # pragma: no cover - fallback when vec env wrappers are unavailable
        env = _make_env()

    eval_env = None
    eval_callback = None
    eval_freq = getattr(args, "eval_freq", 10000)
    if EvalCallback is not None:
        try:
            def _make_eval_env() -> Metin2Env:
                try:
                    return Metin2Env(
                        frame_shape=(*args.frame_shape, 3),
                        kill_reward=getattr(args, "kill_reward", 1.0),
                        damage_penalty=getattr(args, "damage_penalty", 1.0),
                        time_penalty=getattr(args, "time_penalty", 0.01),
                    )
                except TypeError:  # pragma: no cover - fallback for test stubs
                    return Metin2Env(frame_shape=(*args.frame_shape, 3))

            try:
                eval_env = make_vec_env(_make_eval_env, n_envs=1)
                eval_env = VecTransposeImage(eval_env)
            except Exception:  # pragma: no cover - fallback when vec env wrappers are unavailable
                eval_env = _make_eval_env()

            eval_callback = EvalCallback(
                eval_env,
                best_model_save_path=str(run_dir / "best_model"),
                log_path=str(run_dir / "logs"),
                eval_freq=eval_freq,
            )
        except Exception:  # pragma: no cover - allow running without eval callback
            if eval_env is not None:
                eval_env.close()
            eval_env = None
            eval_callback = None

    kwargs = dict(
        learning_rate=args.learning_rate,
        tensorboard_log=str(run_dir) if tb_available else None,
    )
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
    try:
        learn_kwargs = {"total_timesteps": args.total_timesteps}
        if eval_callback is not None:
            learn_kwargs["callback"] = eval_callback
        model.learn(**learn_kwargs)
        model_path = run_dir / args.save_name
        model.save(str(model_path))
        logging.info("Model saved to %s", model_path)
    finally:
        # Guarantee cleanup even if training fails
        env.close()
        if eval_env is not None:
            eval_env.close()


if __name__ == "__main__":
    main()
