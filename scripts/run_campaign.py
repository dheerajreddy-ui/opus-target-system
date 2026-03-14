#!/usr/bin/env python3
"""
Run red team campaign against opus-target-system.

Usage:
    # Single defense level
    python scripts/run_campaign.py --level 2 --duration 120

    # Sweep all levels
    python scripts/run_campaign.py --sweep --duration 60

    # Custom levels
    python scripts/run_campaign.py --sweep --levels 0,2,4 --duration 90

    # With custom target URL
    python scripts/run_campaign.py --sweep --target-url http://staging:8080
"""

import argparse
import logging
import sys
from pathlib import Path

# Ensure the project root is importable
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.campaign_runner import CampaignRunner


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run red team campaign against opus-target-system"
    )
    parser.add_argument(
        "--level",
        type=int,
        default=0,
        help="Defense level to test (0-4). Ignored if --sweep is set.",
    )
    parser.add_argument(
        "--sweep",
        action="store_true",
        help="Sweep across all defense levels.",
    )
    parser.add_argument(
        "--levels",
        type=str,
        default="0,1,2,3,4",
        help="Comma-separated defense levels for sweep mode (default: 0,1,2,3,4).",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duration per level in seconds (default: 60).",
    )
    parser.add_argument(
        "--target-url",
        type=str,
        default="http://localhost:8080",
        help="Base URL of the target system (default: http://localhost:8080).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="results/",
        help="Output directory for reports (default: results/).",
    )
    parser.add_argument(
        "--start-server",
        action="store_true",
        help="Automatically start and stop the target server.",
    )
    parser.add_argument(
        "--payloads",
        type=str,
        default=None,
        help="Path to a JSON file containing custom attack payloads.",
    )
    parser.add_argument(
        "--phased",
        action="store_true",
        help="Run phased campaign (recon → injection → exfiltration → kill chain).",
    )
    parser.add_argument(
        "--benign-only",
        action="store_true",
        help="Run benign-only queries to measure false positive rate.",
    )
    parser.add_argument(
        "--phases",
        type=str,
        default="recon,injection,exfiltration,kill_chain",
        help="Comma-separated phases for --phased mode.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging.",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Load custom payloads if provided
    payloads = None
    if args.payloads:
        import json
        payloads_path = Path(args.payloads)
        if not payloads_path.exists():
            print(f"Error: payloads file not found: {payloads_path}", file=sys.stderr)
            sys.exit(1)
        with open(payloads_path) as f:
            payloads = json.load(f)

    # Build runner
    runner = CampaignRunner(
        target_url=args.target_url,
        project_root=PROJECT_ROOT,
        output_dir=args.output,
    )

    try:
        # Optionally start the server
        if args.start_server:
            runner._start_server()

        if args.phased:
            phases = [p.strip() for p in args.phases.split(",")]
            results = runner.run_phased(
                level=args.level,
                phases=phases,
                duration_seconds=args.duration,
            )
        elif args.benign_only:
            results = runner.run_benign_only(
                level=args.level,
                duration_seconds=args.duration,
            )
        elif args.sweep:
            levels = [int(x.strip()) for x in args.levels.split(",")]
            results = runner.run_sweep(
                levels=levels,
                duration_per_level=args.duration,
                attack_payloads=payloads,
            )
        else:
            results = runner.run_single_level(
                level=args.level,
                duration_seconds=args.duration,
                attack_payloads=payloads,
            )
            # Write reports for single-level runs too
            runner._write_reports()

        # Print summary
        total = len(results)
        breaches = sum(1 for r in results if r["verdict"]["is_breach"])
        print(f"\nCampaign complete: {total} attacks, {breaches} breaches")
        print(f"Reports written to: {Path(args.output).resolve()}")

    except KeyboardInterrupt:
        print("\nCampaign interrupted by user.")
    finally:
        if args.start_server:
            runner._stop_server()


if __name__ == "__main__":
    main()
