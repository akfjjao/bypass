import subprocess
import time
import asyncio
import sys
import requests

# Reconfigure stdout/stderr to support UTF-8 emojis on Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass  # Fallback for older Python versions

import config
from bypass_engine import BypassEngine

def run_test():
    print("=" * 60)
    print("[TEST] Starting Automated LuminaBypass Integration Test...")
    print("=" * 60)

    # 1. Start Mock Server as a background process
    print("Step 1: Launching local Mock Shortener Server on port 9000...")
    mock_server_path = config.BASE_DIR / "mock_shortener.py"
    server_process = subprocess.Popen(
        [sys.executable, str(mock_server_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for mock server to bind and respond
    time.sleep(2.5)
    
    try:
        # Check if server is running
        resp = requests.get("http://127.0.0.1:9000/simulate-ad?dest=https://github.com", timeout=3)
        if resp.status_code == 200:
            print("[SUCCESS] Mock Shortener Server responded successfully on http://127.0.0.1:9000")
        else:
            raise RuntimeError(f"Mock server returned status {resp.status_code}")
    except Exception as e:
        print(f"[ERROR] Could not start Mock Server: {e}")
        server_process.terminate()
        sys.exit(1)

    # 2. Instantiate and run Bypass Engine
    print("\nStep 2: Launching Playwright Chromium sandbox and resolving mock link...")
    engine = BypassEngine(headless=True)
    
    target_url = "http://127.0.0.1:9000/simulate-ad?dest=https://github.com"
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        start_t = time.time()
        result = loop.run_until_complete(engine.bypass(target_url))
        elapsed = time.time() - start_t
        print(f"Bypass sequence completed in {elapsed:.2f} seconds.")
    except Exception as e:
        print(f"[ERROR] Core engine exception: {e}")
        result = {"success": False, "error": str(e)}
    finally:
        loop.close()
        
    # 3. Shutdown Mock Server
    print("\nStep 3: Shutting down local Mock Shortener Server...")
    server_process.terminate()
    server_process.wait()
    print("Mock Server shut down.")

    # 4. Evaluate results
    print("\nStep 4: Evaluating results...")
    print("-" * 60)
    print(f"Bypassed Success : {result.get('success')}")
    print(f"Original Link    : {result.get('original_url')}")
    print(f"Resolved Link    : {result.get('bypassed_url')}")
    print(f"Strategy Used    : {result.get('strategy')}")
    print(f"Hops Count       : {len(result.get('hops', []))}")
    print("-" * 60)

    # Strip trailing slashes to avoid domain comparisons mismatch
    resolved_link = result.get('bypassed_url', '').rstrip('/')
    expected_link = "https://github.com"

    if result.get("success") and resolved_link == expected_link:
        print("\n[SUCCESS] INTEGRATION TEST PASSED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("\n[FAILED] INTEGRATION TEST FAILED!")
        print(f"Reason: Resolved URL did not match the expected destination. Expected: '{expected_link}', Got: '{resolved_link}'")
        sys.exit(1)

if __name__ == "__main__":
    run_test()
