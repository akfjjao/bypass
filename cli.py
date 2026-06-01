import argparse
import asyncio
import sys
import time

# Reconfigure stdout/stderr to support UTF-8 emojis on Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

import config
from bypass_engine import BypassEngine

def main():
    parser = argparse.ArgumentParser(description="LuminaBypass Command-Line Interface")
    parser.add_argument("--url", required=True, help="Shortened URL to bypass")
    parser.add_argument("--headful", action="store_true", help="Launch browser in visible headful mode")
    args = parser.parse_args()

    print("=" * 60)
    print("🌟 LuminaBypass CLI Core Active 🌟")
    print("=" * 60)

    engine = BypassEngine(headless=not args.headful)
    
    # Progress callback log printer
    async def progress_print(message: str, status: str):
        symbol = "[INFO]"
        if status == "start": symbol = "[START]"
        elif status == "success": symbol = "[SUCCESS]"
        elif status == "warning": symbol = "[WARNING]"
        elif status == "error": symbol = "[ERROR]"
        print(f"{symbol} {message}")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(engine.bypass(args.url, progress_callback=progress_print))
    except KeyboardInterrupt:
        print("\n[INFO] Bypass sequence terminated by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] CLI Driver encountered failure: {e}")
        sys.exit(1)
    finally:
        loop.close()

    print("=" * 60)
    if result.get("success"):
        print("🌟 BYPASS SUCCESSFUL!")
        print(f"🔗 Bypassed Link : {result['bypassed_url']}")
        print(f"⏱  Time Taken   : {result['time_taken']:.2f}s")
        print(f"🛡  Strategy     : {result['strategy']}")
        print(f"👣 Hops Count    : {len(result['hops'])}")
        print("\nHops Path List:")
        for idx, hop in enumerate(result['hops']):
            print(f"  {idx + 1}. {hop}")
    else:
        print("❌ BYPASS FAILED!")
        print(f"⚠️ Error Detail  : {result.get('error')}")
    print("=" * 60)

if __name__ == "__main__":
    main()
