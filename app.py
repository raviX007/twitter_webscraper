from flask import Flask, render_template, request, jsonify
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from pymongo import MongoClient
from datetime import datetime
from urllib.parse import quote_plus
import requests
import time
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

mongo_password = os.getenv('MONGO_PASSWORD')
encoded_password = quote_plus(mongo_password)
client = MongoClient(f"mongodb+srv://{os.getenv('MONGO_USER')}:{encoded_password}@{os.getenv('MONGO_CLUSTER')}")
db = client["twitter_trends"]
collection = db["trending_topics"]

def create_driver():
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def handle_security_challenge(driver):
    try:
        security_input = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//input[@type='email']"))
        )
        if security_input:
            security_input.send_keys(os.getenv('TWITTER_EMAIL'))
            security_input.send_keys(Keys.RETURN)
            time.sleep(3)
            return True
    except:
        return False
    return False

def scrape_trending_topics():
    driver = create_driver()
    
    try:
        driver.get("https://twitter.com/login")
        time.sleep(2)

        email_field = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//input[@name='text']"))
        )
        email_field.send_keys(os.getenv('TWITTER_USERNAME'))
        email_field.send_keys(Keys.RETURN)

        if handle_security_challenge(driver):
            print("Handled security challenge")

        password_field = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//input[@name='password']"))
        )
        password_field.send_keys(os.getenv('TWITTER_PASSWORD'))
        password_field.send_keys(Keys.RETURN)

        time.sleep(8)

        max_retries = 3
        for attempt in range(max_retries):
            try:
                driver.get("https://x.com/explore/tabs/trending")
                trending_topics = WebDriverWait(driver, 30).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[data-testid='trend']"))
                )
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                time.sleep(5)

        top_trends = []
        for topic in trending_topics[:15]:
            try:
                trend_text = topic.find_element(By.CSS_SELECTOR, "span.r-18u37iz span").text
                if trend_text and not trend_text.startswith(tuple(str(i) for i in range(10))):
                    top_trends.append(trend_text)
            except Exception as e:
                print(f"Error extracting trend: {str(e)}")
                continue

        ip_address = requests.get("https://api.ipify.org", timeout=5).text

        record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ip_address": ip_address,
            "trends": top_trends
        }
        collection.insert_one(record)

        return top_trends, ip_address

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return [], str(e)

    finally:
        driver.quit()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/run_script", methods=["POST"])
def run_script():
    trends, ip_address = scrape_trending_topics()
    if trends:
        return jsonify({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ip_address": ip_address,
            "trends": trends
        })
    else:
        return jsonify({"error": ip_address})

if __name__ == "__main__":
    app.run(debug=True)