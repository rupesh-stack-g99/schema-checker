import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import pandas as pd
import time
import re
import os
import subprocess
import sys
from urllib.parse import urlparse

# --- Automated Playwright Server Setup Override ---
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "playwright"])
    from playwright.sync_api import sync_playwright

try:
    with sync_playwright() as p:
        test_browser = p.chromium.launch(headless=True)
        test_browser.close()
except Exception:
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])

# --- Page Setup & Modern Styling ---
st.set_page_config(
    page_title="SchemaPulse | Structured Data Auditor",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
        [data-testid="stMetricValue"] {
            font-size: 2.2rem !important;
            font-weight: 700 !important;
        }
        .status-box {
            padding: 1.5rem;
            border-radius: 0.5rem;
            background-color: #f8f9fa;
            border-left: 5px solid #6c757d;
            margin-bottom: 1rem;
        }
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

st.markdown("<h1 style='text-align: left; margin-bottom:0;'>⚡ SchemaPulse</h1>", unsafe_allow_html=True)
st.markdown("<p style='font-size:1.1rem; color:#6c757d; margin-top:0;'>Automated Google-Equivalent Structured Data Auditing with JavaScript Rendering</p>", unsafe_allow_html=True)
st.markdown("---")

# --- Strict Ignore Rules ---
IGNORE_KEYWORDS = [
    "wp-content", "terms", "condition", "privacy", "policy", "policies",        
    "shop", "specials", "payment-plans", "our-services", "/html-sitemap/",
    "contact", "about", "review", "gallery", "awards", "before-after",    
    "blog", "video", "thank-you"        
]
IGNORE_EXTENSIONS = (".svg", ".webp", ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".ico")

# --- Logic Helper Functions ---
def normalize_url(url_input):
    url_str = url_input.strip()
    if not url_str: return ""
    if not url_str.startswith(('http://', 'https://')):
        url_str = 'https://' + url_str
    parsed = urlparse(url_str)
    base = f"{parsed.scheme}://{parsed.netloc}"
    return base.rstrip('/') + '/'

def discover_sitemaps(base_url):
    """
    Uses Rendered Playwright to fetch the domain root sitemaps, 
    bypassing static blocks that return empty lists.
    """
    clean_base = base_url.rstrip('/') + '/'
    index_files = ["sitemap.xml", "sitemap_index.xml"]
    discovered_sitemaps = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)")
        page = context.new_page()
        
        for index_file in index_files:
            index_url = f"{clean_base}{index_file}"
            try:
                response = page.goto(index_url, wait_until="commit", timeout=10000)
                if response and response.status == 200:
                    content = page.content()
                    soup = BeautifulSoup(content, 'html.parser')
                    loc_tags = soup.find_all('loc')
                    for tag in loc_tags:
                        sitemap_loc = tag.text.strip().lower()
                        if "page" in sitemap_loc or "astra-portfolio" in sitemap_loc or "sitemap" in sitemap_loc:
                            discovered_sitemaps.append(tag.text.strip())
            except Exception:
                continue
        browser.close()
            
    if not discovered_sitemaps:
        discovered_sitemaps = [
            f"{clean_base}page-sitemap.xml",
            f"{clean_base}astra-portfolio-sitemap.xml",
            f"{clean_base}sitemap.xml"
        ]
    return list(set(discovered_sitemaps))

def extract_urls_from_sitemaps(base_url, discovered_sitemaps):
    """Loads internal targets by scraping the linked sitemap tree endpoints via browser frames."""
    urls = []
    clean_base = base_url.rstrip('/') + '/'
    urls.append(clean_base)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)")
        page = context.new_page()
        
        for sitemap_url in discovered_sitemaps:
            try:
                response = page.goto(sitemap_url, wait_until="commit", timeout=10000)
                if response and response.status == 200:
                    soup = BeautifulSoup(page.content(), 'html.parser')
                    loc_tags = soup.find_all('loc')
                    for tag in loc_tags:
                        if tag.text:
                            url = tag.text.strip()
                            url_lower = url.lower()
                            if url_lower.endswith(IGNORE_EXTENSIONS) or any(k in url_lower for k in IGNORE_KEYWORDS):
                                if url.rstrip('/') != clean_base.rstrip('/'):
                                    continue
                            urls.append(url)
            except Exception:
                pass
        browser.close()
    return sorted(list(set(urls)))

def check_schema_google_rendered(url):
    schema_types = []
    has_scripts = False
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)")
        page = context.new_page()
        
        try:
            response = page.goto(url, wait_until="networkidle", timeout=15000)
            if not response or response.status != 200:
                status_code = response.status if response else "No Response"
                browser.close()
                return "⚠️ Error", f"Status Error ({status_code})"
                
            rendered_html = page.content()
            browser.close()
        except Exception:
            browser.close()
            return "⚠️ Error", "Connection Timeout/Failed"

    soup = BeautifulSoup(rendered_html, 'html.parser')
    
    # JSON-LD Verification
    schema_tags = soup.find_all('script', type='application/ld+json')
    if schema_tags:
        has_scripts = True
        for tag in schema_tags:
            if not tag.string:
                continue
            try:
                data = json.loads(tag.string)
                if isinstance(data, dict):
                    if '@type' in data: schema_types.append(data['@type'])
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and '@type' in item: schema_types.append(item['@type'])
            except json.JSONDecodeError:
                matches = re.findall(r'"@type"\s*:\s*"([^"]+)"', tag.string)
                if matches:
                    schema_types.extend(matches)

    # Inline Microdata Engine
    microdata_tags = soup.find_all(itemtype=True)
    if microdata_tags:
        for tag in microdata_tags:
            schema_url = tag['itemtype']
            type_name = schema_url.split('/')[-1].split('#')[-1]
            schema_types.append(f"{type_name} (Microdata)")

    if schema_types:
        return "✅ Valid Schema", ", ".join(list(set(schema_types)))
    if has_scripts:
        return "❌ Missing", "No Schema Data Present"
    return "❌ Missing", "No JSON-LD Detected"

# --- Sidebar Controls ---
st.sidebar.markdown("### 🛠️ Crawler Control Panel")
raw_website_input = st.sidebar.text_input("Target Domain Path", placeholder="example.com")
run_button = st.sidebar.button("🚀 Start Deep Scan", type="primary", use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.markdown("#### 🚫 System Filter Constraints")
with st.sidebar.expander("View Active Exclusions List"):
    st.write(IGNORE_KEYWORDS)

# --- Execution Flow ---
if run_button:
    if not raw_website_input:
        st.error("❗ Please provide a target domain extension before executing the scanner pipeline.")
    else:
        target_website = normalize_url(raw_website_input)
        
        with st.status("🛠️ Deep Scan: Extracting Google-Equivalent Renders...", expanded=True) as status_box:
            st.write("🕵️ Discovering sitemaps via virtual rendering...")
            sitemaps_to_run = discover_sitemaps(target_website)
            
            st.write("📥 Crawling sitemaps to fetch active page routes...")
            urls_to_check = extract_urls_from_sitemaps(target_website, sitemaps_to_run)
            status_box.update(label="Target Pipeline Maps Synced!", state="complete", expanded=False)
        
        if not urls_to_check:
            st.error("❌ Process Halting: No URLs found.")
        else:
            progress_bar = st.progress(0)
            status_ticker = st.empty()
            results_data = []
            
            for index, url in enumerate(urls_to_check):
                status_ticker.markdown(f"**Scanning Node ({index + 1}/{len(urls_to_check)}) [Render Mode]:** `{url}`")
                status, info = check_schema_google_rendered(url)
                
                results_data.append({
                    "Target URL Endpoint": url,
                    "Verification Status": status,
                    "Detected Types / Metadata": info
                })
                progress_bar.progress((index + 1) / len(urls_to_check))
                
            status_ticker.empty()
            progress_bar.empty()
            
            # --- Metrics Blocks ---
            df = pd.DataFrame(results_data)
            total_count = len(df)
            valid_count = len(df[df["Verification Status"] == "✅ Valid Schema"])
            missing_count = len(df[df["Verification Status"] == "❌ Missing"])
            error_count = total_count - (valid_count + missing_count)
            
            st.markdown("### 📈 Verification Performance")
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            m_col1.metric("Total Pages Checked", total_count)
            m_col2.metric("Schema Found Pages", valid_count)
            m_col3.metric("Missing Schema Pages", missing_count, delta=f"-{missing_count}" if missing_count > 0 else None, delta_color="inverse")
            m_col4.metric("Error Pages", error_count, delta=f"{error_count} flagged" if error_count > 0 else None, delta_color="off")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            tab1, tab2 = st.tabs(["📋 Inspection Data Stream", "📦 Data Export Panel"])
            
            with tab1:
                st.subheader("Data Overview Table")
                if not df.empty:
                    df["Detected Types / Metadata"] = df["Detected Types / Metadata"].apply(
                        lambda x: [t.strip() for t in x.split(",")] if x and "No" not in x and "Connection" not in x else []
                    )

                st.dataframe(
                    df, 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={
                        "Verification Status": st.column_config.TextColumn("Verification Status", width="medium"),
                        "Target URL Endpoint": st.column_config.LinkColumn("Target URL Endpoint"),
                        "Detected Types / Metadata": st.column_config.ListColumn("Detected Types / Metadata")
                    }
                )
                
            with tab2:
                st.subheader("Download Artifacts")
                csv_df = df.copy()
                csv_df["Detected Types / Metadata"] = csv_df["Detected Types / Metadata"].apply(lambda xl: ", ".join(xl) if isinstance(xl, list) else xl)
                
                csv = csv_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Data Sheet (.csv)",
                    data=csv,
                    file_name="schemapulse_audit_log.csv",
                    mime="text/csv",
                    type="secondary"
                )
