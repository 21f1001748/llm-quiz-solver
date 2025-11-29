# app/runner.py
import json
import re
import time
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
import httpx
from .handlers import solve_from_page_content

async def solve_task(email: str, secret: str, url: str, start_ts: float = None, timeout: int = 180):
    """
    Main task solver that uses Playwright to fetch page content and solve the quiz.
    
    Args:
        email: User email
        secret: Authentication secret
        url: Quiz URL to solve
        start_ts: Start timestamp for timeout tracking
        timeout: Maximum time allowed in seconds
    """
    start_ts = start_ts or time.time()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()
        
        try:
            # Navigate to the quiz page
            print(f"Navigating to {url}")
            await page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Wait a moment for any dynamic content
            await page.wait_for_timeout(1000)
            
            # Extract page content
            body_text = await page.inner_text('body')
            html = await page.content()
            
            # Try to extract any JSON data embedded in the page
            extracted_json = extract_json_from_text(body_text)
            
            # Solve the quiz using handlers
            answer_payload = await solve_from_page_content(
                email, secret, url, body_text, html, extracted_json
            )
            
            # Submit the answer if we have a submit URL
            submit_url = 'https://tds-llm-analysis.s-anand.net/submit'
            if answer_payload and 'submit_url' in answer_payload:
                submit_url = answer_payload.pop('submit_url')
                
                print(f"Submitting answer: {answer_payload.get('answer')} to {submit_url}")
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(submit_url, json=answer_payload)
                    
                    print(f"Submission status: {resp.status_code}")
                    
                    try:
                        resp_json = resp.json()
                        print(f"Submission response: {resp_json}")
                        
                        # Handle chained tasks (if response contains a new URL)
                        if isinstance(resp_json, dict) and resp_json.get('url'):
                            new_url = resp_json['url']
                            elapsed = time.time() - start_ts
                            
                            if elapsed < timeout:
                                remaining_time = timeout - elapsed
                                print(f"Chained task detected. Remaining time: {remaining_time:.1f}s")
                                await solve_task(email, secret, new_url, start_ts=start_ts, timeout=remaining_time)
                            else:
                                print("Insufficient time for chained task")
                    except json.JSONDecodeError:
                        print(f"Non-JSON response: {resp.text[:200]}")
            else:
                print("No submit URL found in answer payload")
                
        except PlaywrightTimeout:
            print(f"Playwright timeout while loading {url}")
        except Exception as e:
            print(f"Error in solve_task: {type(e).__name__}: {e}")
        finally:
            await browser.close()


def extract_json_from_text(text: str):
    """
    Extract the first valid JSON object from text.
    Useful for pages that embed data in script tags or text.
    """
    # Try to find JSON object pattern
    match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text)
    if not match:
        return None
    
    candidate = match.group(0)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        # Try to find a more complete JSON by expanding search
        match = re.search(r'\{[\s\S]*?\}', text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return None