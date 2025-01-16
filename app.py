import streamlit as st
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime
import requests
from pymongo import MongoClient
from urllib.parse import quote_plus

# Page config
st.set_page_config(
    page_title="Twitter Trends Tracker",
    page_icon="🐦",
    layout="wide"
)

# Custom CSS
st.markdown("""
    <style>
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
    }
    .trend-card {
        padding: 20px;
        border-radius: 10px;
        background-color: #f0f2f6;
        margin: 10px 0;
    }
    .metadata {
        color: #666;
        font-size: 0.8em;
    }
    </style>
""", unsafe_allow_html=True)

# Title and description
st.title("🐦 Twitter Trends Tracker")
st.markdown("Track real-time trending topics on Twitter with custom filtering options.")

# Sidebar for credentials and options
with st.sidebar:
    st.header("📝 Credentials")
    twitter_username = st.text_input("Twitter Username", type="default")
    twitter_email = st.text_input("Twitter Email", type="default")
    twitter_password = st.text_input("Twitter Password", type="password")
    
    st.header("⚙️ Configuration")
    num_trends = st.slider("Number of Trending Topics", min_value=5, max_value=15, value=10)
    show_browser = st.checkbox("Show Browser Window", value=True, 
                             help="If checked, you'll see the browser automation in action")
    
    # MongoDB credentials
    st.header("🗄️ MongoDB Settings (Optional)")
    mongo_user = st.text_input("MongoDB Username", type="default")
    mongo_password = st.text_input("MongoDB Password", type="password")
    mongo_cluster = st.text_input("MongoDB Cluster URL")

def create_driver(show_browser=True):
    options = Options()
    if not show_browser:
        options.add_argument("--headless")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Add window position to make it visible but not overlap with Streamlit
    options.add_argument("--window-position=1000,0")
    
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def handle_security_challenge(driver, email):
    try:
        security_input = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//input[@type='email']"))
        )
        if security_input:
            security_input.send_keys(email)
            security_input.send_keys(Keys.RETURN)
            time.sleep(3)
            return True
    except:
        return False
    return False

def scrape_trending_topics(username, email, password, num_topics, show_browser):
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        status_text.text("Initializing browser...")
        progress_bar.progress(10)
        
        driver = create_driver(show_browser)
        
        status_text.text("Logging into Twitter...")
        progress_bar.progress(20)
        
        driver.get("https://twitter.com/login")
        time.sleep(2)

        email_field = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//input[@name='text']"))
        )
        email_field.send_keys(username)
        email_field.send_keys(Keys.RETURN)

        progress_bar.progress(40)

        if handle_security_challenge(driver, email):
            status_text.text("Handling security challenge...")
            progress_bar.progress(50)

        password_field = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//input[@name='password']"))
        )
        password_field.send_keys(password)
        password_field.send_keys(Keys.RETURN)

        progress_bar.progress(60)
        status_text.text("Fetching trending topics...")

        time.sleep(8)
        driver.get("https://x.com/explore/tabs/trending")
        
        trending_topics = WebDriverWait(driver, 30).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[data-testid='trend']"))
        )

        progress_bar.progress(80)
        status_text.text("Processing results...")

        top_trends = []
        for topic in trending_topics[:num_topics]:
            try:
                trend_text = topic.find_element(By.CSS_SELECTOR, "span.r-18u37iz span").text
                if trend_text and not trend_text.startswith(tuple(str(i) for i in range(10))):
                    top_trends.append(trend_text)
            except:
                continue

        ip_address = requests.get("https://api.ipify.org", timeout=5).text

        # Save to MongoDB if credentials are provided
        if mongo_user and mongo_password and mongo_cluster:
            try:
                encoded_password = quote_plus(mongo_password)
                client = MongoClient(f"mongodb+srv://{mongo_user}:{encoded_password}@{mongo_cluster}")
                db = client["twitter_trends"]
                collection = db["trending_topics"]
                
                record = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "ip_address": ip_address,
                    "trends": top_trends
                }
                collection.insert_one(record)
                st.success("Successfully saved to MongoDB!")
            except Exception as e:
                st.warning(f"Failed to save to MongoDB: {str(e)}")

        progress_bar.progress(100)
        status_text.text("Complete!")
        time.sleep(1)
        status_text.empty()
        progress_bar.empty()

        return top_trends, ip_address

    except Exception as e:
        status_text.text(f"Error: {str(e)}")
        progress_bar.empty()
        return [], str(e)

    finally:
        driver.quit()

# Main content area
col1, col2 = st.columns([2, 1])

with col1:
    if st.button("🔍 Fetch Trending Topics", type="primary"):
        if not twitter_username or not twitter_email or not twitter_password:
            st.error("Please provide Twitter credentials in the sidebar!")
        else:
            with st.spinner("Fetching trending topics..."):
                trends, ip_address = scrape_trending_topics(
                    twitter_username,
                    twitter_email,
                    twitter_password,
                    num_trends,
                    show_browser
                )
                
                if trends:
                    st.success(f"Successfully fetched {len(trends)} trending topics!")
                    
                    # Display trends in cards
                    for i, trend in enumerate(trends, 1):
                        st.markdown(f"""
                            <div class="trend-card">
                                <h3>#{i} {trend}</h3>
                                <p class="metadata">Trending on Twitter</p>
                            </div>
                        """, unsafe_allow_html=True)
                    
                    # Display metadata
                    st.markdown("---")
                    st.markdown(f"""
                        <div class="metadata">
                            <p>🕒 Fetched at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                            <p>🌐 IP Address: {ip_address}</p>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.error(f"Failed to fetch trends. Error: {ip_address}")

with col2:
    st.markdown("""
        ### 📊 Statistics
        - Total trends requested: {}
        - Last update: {}
    """.format(
        num_trends,
        datetime.now().strftime("%H:%M:%S")
    ))
    
    # Add a refresh timer
    if st.checkbox("Enable auto-refresh"):
        refresh_interval = st.slider("Refresh interval (minutes)", 5, 60, 15)
        st.info(f"Next refresh in {refresh_interval} minutes")

if __name__ == "__main__":
    st.empty()