import re
import time
import asyncio
import logging
from urllib.parse import urlparse
import requests
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LuminaBypassEngine")

# Known ad domains and shortener landing pages to block or detect
AD_DOMAINS = [
    "admaven.com", "adpaypost.com", "onclickads.net", "popads.net", 
    "popcash.net", "exoclick.com", "adsterra.com", "juicyads.com",
    "clktag.com", "adk2x.com", "ad-maven.com", "adplaypost.com",
    "shortlink", "linkvertise", "shrinkme", "gplinks"
]

def is_ad_domain(url: str) -> bool:
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    # Also catch subdomains or direct matches
    return any(ad in domain for ad in AD_DOMAINS)

class BypassEngine:
    def __init__(self, headless: bool = True):
        self.headless = headless

    async def bypass(self, url: str, progress_callback=None) -> dict:
        """
        Main bypass driver. Runs multiple strategies:
        1. Fast HTTP Tracker
        2. Dynamic Playwright headless browser with ad/popup block rules
        """
        async def report(msg: str, status: str = "info"):
            if progress_callback:
                try:
                    await progress_callback(msg, status)
                except Exception as cb_err:
                    logger.error(f"Callback error: {cb_err}")
            logger.info(f"[{status.upper()}] {msg}")

        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        start_time = time.time()
        await report(f"Starting bypass sequence for URL: {url}", "start")

        # -------------------------------------------------------------
        # Strategy 1: Direct HTTP redirection tracker
        # -------------------------------------------------------------
        await report("Strategy 1: Initiating fast HTTP redirection tracker...", "info")
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            }
            # Follow redirects with a short timeout
            response = requests.get(url, headers=headers, timeout=5, allow_redirects=True)
            final_url = response.url
            if final_url != url and not is_ad_domain(final_url):
                elapsed = time.time() - start_time
                await report(f"Bypassed successfully via HTTP Tracker in {elapsed:.2f}s!", "success")
                return {
                    "success": True,
                    "strategy": "HTTP Tracker",
                    "original_url": url,
                    "bypassed_url": final_url,
                    "hops": [h.url for h in response.history] + [final_url],
                    "time_taken": elapsed
                }
            else:
                await report("Strategy 1 resolved to an ad/same domain. Moving to Strategy 2...", "info")
        except Exception as e:
            await report(f"Strategy 1 skipped (network/timeout): {str(e)}. Proceeding...", "warning")

        # -------------------------------------------------------------
        # Strategy 2: Playwright headless browser (dynamic JS & Admaven bypass)
        # -------------------------------------------------------------
        await report("Strategy 2: Preparing Playwright headless browser context...", "info")
        
        try:
            async with async_playwright() as p:
                await report("Spinning up headless Chromium instance...", "info")
                browser = await p.chromium.launch(
                    headless=self.headless,
                    args=[
                        "--disable-gpu",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-web-security",
                        "--disable-features=IsolateOrigins,site-per-process"
                    ]
                )
                
                # Setup context with desktop agent and standard configuration
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 720},
                    java_script_enabled=True
                )
                
                # Block ads, CSS, and popups dynamically using route interceptors
                await context.route("**/*", lambda route: self._handle_route(route, report))
                
                page = await context.new_page()
                
                # Setup popup closure handler
                context.on("page", lambda p: self._handle_popup(p, report))
                
                hops = [url]
                
                # Log frame navigation redirects
                page.on("framenavigated", lambda frame: self._log_navigation(frame, hops, report))
                
                await report("Opening page and loading shortened URL...", "info")
                
                try:
                    # Navigate and wait for HTML content commit
                    await page.goto(url, wait_until="commit", timeout=15000)
                except Exception as e:
                    await report(f"Page load warning (continuing bypass): {str(e)}", "warning")
                
                await report("Simulating user focus & waiting for dynamic script execution...", "info")
                
                final_url = None
                max_checks = 8
                for check in range(max_checks):
                    current_url = page.url
                    await report(f"Tracking location [Hop {check+1}]: {current_url}", "info")
                    
                    if current_url != url and not is_ad_domain(current_url) and current_url != "about:blank":
                        final_url = current_url
                        break
                    
                    # Wait 1.5s per interval to let countdowns/scripts redirect
                    await asyncio.sleep(1.5)
                
                if not final_url:
                    final_url = page.url
                
                await browser.close()
                
                elapsed = time.time() - start_time
                if final_url and final_url != url and not is_ad_domain(final_url):
                    await report(f"Bypassed successfully via Headless Browser in {elapsed:.2f}s!", "success")
                    return {
                        "success": True,
                        "strategy": "Playwright Browser",
                        "original_url": url,
                        "bypassed_url": final_url,
                        "hops": hops,
                        "time_taken": elapsed
                    }
                else:
                    await report("Headless browser could not escape ad/shortener domain limits.", "error")
                    return {
                        "success": False,
                        "error": "Failed to bypass ad-redirection gate.",
                        "original_url": url,
                        "bypassed_url": final_url,
                        "hops": hops,
                        "time_taken": elapsed
                    }
                    
        except Exception as e:
            elapsed = time.time() - start_time
            await report(f"Playwright automation encountered an error: {str(e)}", "error")
            return {
                "success": False,
                "error": str(e),
                "original_url": url,
                "bypassed_url": None,
                "hops": [],
                "time_taken": elapsed
            }

    async def _handle_route(self, route, report_func):
        """Blocks scripts, stylesheet assets, and tracker analytics requests to maximize speed."""
        request = route.request
        url = request.url
        resource_type = request.resource_type
        
        # Block media assets (images, stylesheets, fonts) that don't participate in redirection
        if resource_type in ["image", "media", "font", "stylesheet"]:
            await route.abort()
            return

        # Block requests directed to ad providers or containing ad footprints
        url_lower = url.lower()
        if any(ad in url_lower for ad in AD_DOMAINS) or any(keyword in url_lower for keyword in ["/ads/", "google-analytics", "doubleclick", "popunder", "analytics"]):
            await route.abort()
            return
            
        await route.continue_()

    def _handle_popup(self, popup_page, report_func):
        """Catches and closes newly opened popup tabs instantly."""
        asyncio.create_task(self._close_popup_async(popup_page))

    async def _close_popup_async(self, popup_page):
        try:
            await popup_page.wait_for_load_state()
            await popup_page.close()
        except:
            pass

    def _log_navigation(self, frame, hops, report_func):
        if frame == frame.page.main_frame:
            url = frame.url
            if url not in hops and url != "about:blank":
                hops.append(url)
