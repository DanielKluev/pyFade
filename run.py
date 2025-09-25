"""
Script to run the application.

Usage:
  --sample_id <id> - Show only the specified sample ID.
"""
import sys, os, argparse

from py_fade.app import pyFadeApp

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the pyFade application.")
    parser.add_argument("--config", type=str, help="Path to configuration file.", default=None)
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    parser.add_argument("--sample_id", type=str, help="Sample ID to load in GUI.", default=None)
    args = parser.parse_args()

    if args.debug:
        print("[!] Debug mode is enabled.")
        pyFadeApp.setup_logging(is_debug=True)
    else:
        pyFadeApp.setup_logging(is_debug=False)

    pyfade_app = pyFadeApp(config_path=args.config, is_debug=args.debug)
    sys.exit(pyfade_app.run_gui(sample_id=args.sample_id))