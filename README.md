# ⚡ **Seismic Faucet Script**
Welcome to the Seismic Faucet Script – a powerful, multi-threaded tool that automates Seismic token claims using 2Captcha and proxies.
> 🛠️ Easy to set up, blazing fast, and highly customizable.

# 🌟 **Features**
+ 🚀 Multi-threaded execution (high throughput)
+ 🤖 Automatic captcha solving using 2Captcha
+ 🌐 Optional proxy support for enhanced anonymity
+ 🧾 Log results to success/fail files
+ 🪄 Retry mechanism to increase claim success rate
+ 📊 Real-time logging with colorful CLI output
_______________________
# **🧰 Installation Guide**

1. Clone the repository
```
git clone https://github.com/Quincy-seun/Sesimic-Network-Auto-Faucet.git 
cd Sesimic-Network-Auto-Faucet
```
2. Install dependencies
```
pip install -r requirements.txt
```
3. Configure the script
* Open ```faucet.py```
* Edit the following in lines 17 - 25:
```
THREADS = 1                     # Number of parallel threads
REQUEST_DELAY = 5               # Seconds between wallet processing
JITTER = 0.5                    # Random delay variation (+/- seconds)
MAX_ATTEMPTS = 3                # Max attempts per wallet
CAPTCHA_TIMEOUT = 420           # Increase timeout for captcha solving (seconds)
USE_PROXIES = True              # Set to False if you don't want to use proxies

# API Configuration
TWO_CAPTCHA_API_KEY = "YOUR_2CAPTCHA_KEY_HERE"
```
4. Run the script
```
python faucet.py
```
________________
# 📁 Required Files
Ensure the following files are present in faucet directory:
+ ```wallets.txt``` - 💼 List wallet addresses line by line
+ ```proxies.txt``` - 🌐 List proxies in format: ```http://user:pass@ip:port```
_________________
# 🧪 How It Works
1. Reads wallet addresses and proxies from respective files
2. Solves hcaptcha via 2captcha
3. Sends claim request to Seismic faucet
4. Logs results with retry mechanism
_______________
# Need Help?
Send a message on [Telegram](https://t.me/ruby_lanshi)
