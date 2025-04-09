import requests
from colorama import init, Fore, Style
from datetime import datetime
import threading
import pytz
import time
import random
from tzlocal import get_localzone
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.parse
import json

# Initialize colorama
init(autoreset=True)

# ================== CONFIGURATION ==================
THREADS = 1                     # Number of parallel threads
REQUEST_DELAY = 5               # Seconds between wallet processing
JITTER = 0.5                    # Random delay variation (+/- seconds)
MAX_ATTEMPTS = 3                # Max attempts per wallet
CAPTCHA_TIMEOUT = 420           # Increase timeout for captcha solving (seconds)

# API Configuration
TWO_CAPTCHA_API_KEY = "YOUR_2CAPTCHA_KEY_HERE"
HCAPTCHA_SITEKEY = "0a76a396-7bf6-477e-947c-c77e66a8222e"
FAUCET_URL = "https://faucet-2.seismicdev.net/"
API_ENDPOINT = "https://faucet-2.seismicdev.net/api/claim"

# File Configuration
WALLETS_FILE = "wallets.txt"
PROXIES_FILE = "proxies.txt"
SUCCESS_FILE = "success.txt"
FAIL_FILE = "fail.txt"
LOG_FILE = "logs.txt"

# Request Headers
headers = {
    "Accept": "*/*",
    "Content-Type": "application/json",
    "Origin": FAUCET_URL,
    "Referer": FAUCET_URL,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
}

# ================== INITIALIZATION ==================
# Check 2captcha balance
try:
    balance_url = f"https://2captcha.com/res.php?key={TWO_CAPTCHA_API_KEY}&action=getbalance"
    balance_response = requests.get(balance_url)
    if balance_response.text.startswith('ERROR'):
        print(f"{Fore.RED}✗ 2Captcha API error: {balance_response.text}{Style.RESET_ALL}")
        exit(1)
    else:
        print(f"{Fore.GREEN}✓ 2Captcha API connected. Balance: ${balance_response.text}{Style.RESET_ALL}")
except Exception as e:
    print(f"{Fore.RED}✗ Failed to check 2Captcha balance: {str(e)}{Style.RESET_ALL}")
    exit(1)

# Load proxies
try:
    with open(PROXIES_FILE, "r") as f:
        proxies_list = [line.strip() for line in f if line.strip()]
    print(f"{Fore.GREEN}✓ Loaded {len(proxies_list)} proxies{Style.RESET_ALL}")
except Exception as e:
    print(f"{Fore.YELLOW}⚠ No proxies loaded: {str(e)}{Style.RESET_ALL}")
    proxies_list = []

# ================== UTILITIES ==================
def now_local():
    return datetime.now(get_localzone()).strftime("%H:%M:%S %d/%m/%Y")

def write_to_log_file(message):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(message + "\n")
    except Exception as e:
        print(f"Failed to write log: {e}")

def log_info(msg, idx=None):
    prefix = f"[{now_local()}]" + (f" [{idx}]" if idx else "")
    full_msg = f"{prefix} {msg}"
    print(Fore.CYAN + full_msg + Style.RESET_ALL)
    write_to_log_file(full_msg)

def log_success(msg, idx=None):
    prefix = f"[{now_local()}]" + (f" [{idx}]" if idx else "")
    full_msg = f"{prefix} {msg}"
    print(Fore.GREEN + full_msg + Style.RESET_ALL)
    write_to_log_file(full_msg)

def log_fail(msg, idx=None):
    prefix = f"[{now_local()}]" + (f" [{idx}]" if idx else "")
    full_msg = f"{prefix} {msg}"
    print(Fore.RED + full_msg + Style.RESET_ALL)
    write_to_log_file(full_msg)

# ================== CORE FUNCTIONS ==================
def solve_hcaptcha(idx=None):
    try:
        params = {
            'key': TWO_CAPTCHA_API_KEY,
            'method': 'hcaptcha',
            'sitekey': HCAPTCHA_SITEKEY,
            'pageurl': FAUCET_URL,
            'invisible': 1,
            'json': 1
        }

        # Removed noisy logging:
        # log_info(f"Submitting captcha with params: {params}", idx=idx)

        response = requests.get('https://2captcha.com/in.php', params=params)
        result = response.json()

        if result.get('status') != 1:
            log_fail(f"Failed to submit captcha: {result.get('request')}", idx=idx)
            return None

        captcha_id = result.get('request')
        log_info(f"Captcha submitted, waiting for solution (ID: {captcha_id})", idx=idx)

        # Wait for the captcha to be solved
        wait_time = 0
        result_params = {
            'key': TWO_CAPTCHA_API_KEY,
            'action': 'get',
            'id': captcha_id,
            'json': 1
        }

        while wait_time < CAPTCHA_TIMEOUT:
            time.sleep(5)
            wait_time += 5

            result_response = requests.get('https://2captcha.com/res.php', params=result_params)
            result = result_response.json()

            if result.get('request') == 'CAPCHA_NOT_READY':
                print(f"[{idx}] ⏳ Waiting for captcha... {wait_time}s", end='\r')
                continue

            print()  # move to next line after success or failure

            if result.get('status') == 1:
                captcha_solution = result.get('request')
                log_success("Captcha solved successfully", idx=idx)
                return captcha_solution

            log_fail(f"Failed to get captcha solution: {result.get('request')}", idx=idx)
            return None

        log_fail("Timed out waiting for captcha solution", idx=idx)
        return None

    except Exception as e:
        log_fail(f"CAPTCHA solve error: {str(e)}", idx=idx)
        return None

def seismic_claim(wallet, hcaptcha_token, proxy, idx=None):
    request_headers = headers.copy()
    request_headers["h-captcha-response"] = hcaptcha_token

    payload = {"address": wallet}
    proxies = {"http": proxy, "https": proxy} if proxy else None

    try:
        log_info(f"Sending claim request to {API_ENDPOINT}", idx=idx)
        response = requests.post(
            API_ENDPOINT,
            json=payload,
            headers=request_headers,
            proxies=proxies,
            timeout=30
        )

        if response.status_code == 429:
            try:
                error_data = response.json()
                log_fail(f"HTTP 429 - Rate limited: {error_data}", idx=idx)
            except Exception:
                log_fail("HTTP 429 - Rate limited (no JSON body)", idx=idx)
            return response  # Let the caller decide what to do next

        if response.status_code != 200:
            log_fail(f"HTTP {response.status_code} - {response.text}", idx=idx)
            return None

        return response.json()

    except Exception as e:
        log_fail(f"API request failed: {str(e)}", idx=idx)
        return None

# ================== PROXY MANAGEMENT ==================
proxy_index = 0
PROXY_LOCK = threading.Lock()

def get_next_proxy():
    global proxy_index
    with PROXY_LOCK:
        if not proxies_list:
            return None
        proxy = proxies_list[proxy_index % len(proxies_list)]
        proxy_index += 1
        return proxy

# ================== RATE LIMITING ==================
LAST_REQUEST_TIME = 0
TIME_LOCK = threading.Lock()

def enforce_rate_limit(idx=None):
    global LAST_REQUEST_TIME
    
    with TIME_LOCK:
        current_time = time.time()
        elapsed = current_time - LAST_REQUEST_TIME
        remaining_delay = max(0, REQUEST_DELAY - elapsed + random.uniform(-JITTER, JITTER))
        
        if remaining_delay > 0:
            log_info(f"Rate limit delay: {remaining_delay:.1f}s", idx=idx)
            time.sleep(remaining_delay)
        
        LAST_REQUEST_TIME = time.time()

# ================== WALLET PROCESSING ==================
def process_wallet(wallet, index, stop_event):
    if stop_event.is_set():
        log_info("Stop signal received", idx=index)
        return

    enforce_rate_limit(idx=index)
    log_info(f"Processing wallet: {wallet}", idx=index)

    for attempt in range(MAX_ATTEMPTS):
        if stop_event.is_set():
            return

        proxy = get_next_proxy()
        log_info(f"Attempt {attempt+1}/{MAX_ATTEMPTS} using proxy: {proxy}", idx=index)

        # Solve CAPTCHA
        captcha_token = solve_hcaptcha(idx=index)
        if not captcha_token:
            time.sleep(1)
            continue

        # Make claim request
        response = seismic_claim(wallet, captcha_token, proxy, idx=index)

        if isinstance(response, dict):
            log_info(f"API response: {response}", idx=index)

            # Check if TX hash is present in msg even without 'success'
            tx_msg = response.get("msg", "")
            if "Txhash:" in tx_msg:
                log_success(f"Success! {tx_msg}", idx=index)
                with open(SUCCESS_FILE, "a") as f:
                    f.write(f"{wallet}  # {tx_msg}\n")
                return  # Wallet successfully processed

            if response.get("success"):
                log_success(f"Success! TX: {response.get('txHash', 'N/A')}", idx=index)
                with open(SUCCESS_FILE, "a") as f:
                    f.write(f"{wallet}\n")
                return  # Wallet successfully processed

            else:
                error_msg = response.get("message", response.get("msg", "Unknown error"))
                if "try again later" in error_msg.lower() or "rate limit" in error_msg.lower():
                    log_fail(f"Rate limited: {error_msg}", idx=index)
                    with open(FAIL_FILE, "a") as f:
                        f.write(f"{wallet} # Rate limited - try again later\n")
                    return  # Skip this wallet

        elif hasattr(response, 'status_code') and response.status_code == 429:
            log_fail(f"Rate limited (HTTP 429)", idx=index)
            with open(FAIL_FILE, "a") as f:
                f.write(f"{wallet} # Rate limited (HTTP 429) - try again later\n")
            return  # Skip this wallet

        log_fail(f"Attempt {attempt+1} failed", idx=index)
        time.sleep(1)

    # If all attempts failed
    with open(FAIL_FILE, "a") as f:
        f.write(f"{wallet}\n")

# ================== MAIN EXECUTION ==================
def main(stop_event):
    log_info("Starting Seismic faucet claim process")
    
    try:
        with open(WALLETS_FILE, "r") as f:
            wallets = [line.strip() for line in f if line.strip()]
    except Exception as e:
        log_fail(f"Failed to load wallets: {str(e)}")
        return
    
    if not wallets:
        log_fail("No wallets found in wallets.txt")
        return
    
    log_info(f"Loaded {len(wallets)} wallets to process")
    
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = {
            executor.submit(process_wallet, wallet, idx+1, stop_event): wallet
            for idx, wallet in enumerate(wallets)
        }
        
        try:
            for future in as_completed(futures):
                future.result()
        except KeyboardInterrupt:
            stop_event.set()
            log_info("Keyboard interrupt detected - shutting down")
            executor.shutdown(wait=False)
            raise

if __name__ == "__main__":
    while True:
        stop_event = threading.Event()
        try:
            main(stop_event)
        except KeyboardInterrupt:
            log_info("Program terminated by user")
            break
        except Exception as e:
            log_fail(f"Fatal error: {str(e)}")
        
        log_info("Waiting 90 minutes before restarting...")
        for i in range(90, 0, -1):
            print(f"⏳ Restarting in {i} minute(s)...", end='\r')
            time.sleep(60)
        print()  # Clean line break after countdown
