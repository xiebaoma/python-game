"""Campus Cyber Guard - application entry point."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="校园网络防线 - Pygame 塔防小游戏")
    parser.add_argument("--demo", action="store_true", help="启动自动演示模式")
    parser.add_argument("--record-demo", type=Path, help="无窗口录制自动演示 MP4")
    parser.add_argument("--duration", type=float, default=52.0, help="演示录制时长（秒）")
    parser.add_argument("--fps", type=int, default=25, help="演示视频帧率")
    parser.add_argument("--screenshot-dir", type=Path, help="保存演示关键帧截图")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.record_demo:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    from cyber_guard.game import CyberGuardGame

    game = CyberGuardGame(headless=bool(args.record_demo), demo=args.demo or bool(args.record_demo))
    if args.record_demo:
        game.record_demo(args.record_demo, args.duration, args.fps, args.screenshot_dir)
    else:
        game.run()


if __name__ == "__main__":
    main()
