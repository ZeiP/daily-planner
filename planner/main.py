"""Daily Planner CLI entry point.

Usage:
    python -m planner                  # Generate today's planner and upload
    python -m planner --no-upload      # Generate PDF only
    python -m planner --date 2026-02-16
    python -m planner --register-remarkable
"""

import argparse
import logging
import sys
from datetime import date, datetime
from pathlib import Path

from planner.config import load_config
from planner.sources.base import PlannerData
from planner.sources.caldav_source import CalDavSource
from planner.sources.tracks_source import TracksSource
from planner.pdf_generator import PlannerPDFGenerator
from planner import remarkable

logger = logging.getLogger("planner")


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="daily-planner",
        description="Generate a daily planner PDF from CalDAV and Tracks, upload to reMarkable.",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Target date in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Generate PDF only, do not upload to reMarkable",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output PDF path (default: ./planner-YYYY-MM-DD.pdf)",
    )
    parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help="Path to config.json (default: ./config.json)",
    )
    parser.add_argument(
        "--register-remarkable",
        action="store_true",
        help="Run one-time reMarkable device registration",
    )
    parser.add_argument(
        "--skip-caldav",
        action="store_true",
        help="Skip CalDAV calendar fetching",
    )
    parser.add_argument(
        "--skip-tracks",
        action="store_true",
        help="Skip Tracks todo fetching",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose/debug logging",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()
    setup_logging(verbose=args.verbose)

    # Handle remarkable registration
    if args.register_remarkable:
        success = remarkable.register_device()
        sys.exit(0 if success else 1)

    # Load config
    config = load_config(args.config)

    # Determine target date
    if args.date:
        try:
            target_date = date.fromisoformat(args.date)
        except ValueError:
            logger.error("Invalid date format: %s (expected YYYY-MM-DD)", args.date)
            sys.exit(1)
    else:
        target_date = date.today()

    logger.info("Generating planner for %s", target_date.isoformat())

    # Collect data from all sources
    data = PlannerData(target_date=target_date)

    # CalDAV events
    if not args.skip_caldav:
        try:
            caldav_source = CalDavSource(config.caldav, timezone=config.planner.timezone)
            caldav_source.fetch(target_date, data)
            logger.info("Fetched %d calendar events", len(data.events))
        except Exception as e:
            logger.error("CalDAV fetch failed: %s", e)
            if args.verbose:
                import traceback
                traceback.print_exc()

    # Tracks todos
    if not args.skip_tracks:
        try:
            tracks_source = TracksSource(config.tracks)
            tracks_source.fetch(target_date, data)
            logger.info("Fetched %d todos", len(data.todos))
        except Exception as e:
            logger.error("Tracks fetch failed: %s", e)
            if args.verbose:
                import traceback
                traceback.print_exc()

    # Generate PDF
    output_path = args.output or f"planner-{target_date.isoformat()}.pdf"
    generator = PlannerPDFGenerator(
        day_start_hour=config.planner.day_start_hour,
        day_end_hour=config.planner.day_end_hour,
    )
    pdf_path = generator.generate(data, output_path)
    logger.info("PDF saved to: %s", pdf_path)

    # Upload to reMarkable
    if not args.no_upload:
        if not remarkable.is_available():
            logger.warning(
                "rmapi tool not found, skipping upload. "
                "See README_REMARKABLE.md for installation instructions."
            )
        else:
            doc_name = f"{target_date.isoformat()} Daily Planner"
            success = remarkable.upload_pdf(
                pdf_path,
                folder_name=config.remarkable.folder,
                document_name=doc_name,
            )
            if not success:
                sys.exit(1)
    else:
        logger.info("Upload skipped (--no-upload)")

    logger.info("Done!")


if __name__ == "__main__":
    main()
