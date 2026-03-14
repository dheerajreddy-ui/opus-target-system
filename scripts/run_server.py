#!/usr/bin/env python3
"""
Launch the opus-target-system server.

Usage:
    python scripts/run_server.py
    python scripts/run_server.py --port 9090
    python scripts/run_server.py --no-reload
"""

import argparse

import uvicorn
from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch opus-target-system server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", type=int, default=8080, help="Port number")
    parser.add_argument(
        "--no-reload",
        action="store_true",
        help="Disable auto-reload (use in production).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1).",
    )
    args = parser.parse_args()

    uvicorn.run(
        "src.bluestack.app:app",
        host=args.host,
        port=args.port,
        reload=not args.no_reload,
        workers=args.workers,
    )


if __name__ == "__main__":
    main()
