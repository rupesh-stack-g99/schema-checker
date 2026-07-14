import streamlit as st
import requests
import cloudscraper
from bs4 import BeautifulSoup
import extruct
import json
import re
import pandas as pd
import time
from urllib.parse import urlparse

# --- Page Setup & Modern Styling ---
st.set_page_config(
    page_title="SchemaPulse | Deep Schema Extractor",
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
            border-left: 5px solid #17a2b8;
            margin-bottom: 1rem;
        }
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

st.markdown("<h1 style='text-align: left; margin-bottom:0;'>⚡ SchemaPulse</h1>", unsafe_allow_html=True)
st.markdown("<p style='font-size:1.1rem; color:#6c757d; margin-top:0;'>Anti-Bot Resilient Multi-Format Structured Data Auditor</p>", unsafe_allow_html=True)
st.markdown("---")

# --- Ignore Rules ---
IGNORE_KEYWORDS = [
    "wp-content", "terms", "condition", "privacy", "policy", "policies",        
    "shop", "specials", "payment-plans", "our-services", "/html-sitemap/",
    "contact", "about", "review", "gallery", "awards", "before-after",    
    "blog", "video", "thank-you"        
]
IGNORE_EXTENSIONS = (".svg", ".webp", ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".ico")

# --- Helper Functions ---
def normalize_url(url_input):
    url_str = url_input.strip()
    if not url_str: return ""
    if not url_str.startswith(('http://', 'https://')):
        url_str = 'https://' + url_str
    parsed = urlparse(url_str)
    base = f"{parsed.scheme}://{parsed.netloc}"
    return base.rstrip('/') + '/'

def discover_sitemaps(base_url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    clean_base = base_url.rstrip('/') + '/'
    index_files = ["sitemap.xml", "sitemap_index.xml"]
    discovered_sitemaps = []
    
    scraper = cloudscraper.create_scraper()
    for index_file in index_files:
        index_url = f"{clean_base}{index_file}"
        try:
            response = scraper.get(index_url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'xml')
                for tag in soup.find_all('loc'):
                    sitemap_loc = tag.text.strip().lower()
                    if "page" in sitemap_loc or "sitemap" in sitemap_loc:
                        discovered_sitemaps.append(tag.text.strip())
        except Exception:
            continue
            
    if not discovered_sitemaps:
        discovered_sitemaps = [f"{clean_base}page-sitemap.xml", f"{clean_base}sitemap.xml"]
    return list(set(discovered_sitemaps))

def extract_urls_from_sitemaps(base_url, discovered_sitemaps):
    urls = []
    scraper = cloudscraper.create_scraper()
    clean_base = base_url.rstrip('/') + '/'
    urls.append(clean_base)

    for sitemap_url in discovered_sitemaps:
        try:
            response = scraper.get(sitemap_url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'xml')
                for tag in soup.find_all('loc'):
                    if tag.text:
                        url = tag.text.strip()
                        url_lower = url.lower()
                        if url_lower.endswith(IGNORE_EXTENSIONS) or any(k in url_lower for k in IGNORE_KEYWORDS):
                            if url.rstrip('/') != clean_base.rstrip('/'):
                                continue
                        urls.append(url)
        except Exception:
            pass
    return sorted(list(set(urls)))

# --- Helper Parser: Infinitely Deep JSON Schema Hunter ---
def recursive_find_types(data):
    """
    Recursively scans JSON dictionaries and lists to extract *every* single schema type, 
    no matter how deeply nested it is inside arrays, graphs, or nested layouts.
    """
    types = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k in ('@type', 'type') and isinstance(v, str):
                types.append(v.split('/')[-1]) # Extracts 'LocalBusiness' from 'https://schema.org/LocalBusiness'
            elif isinstance(v, (dict, list)):
                types.extend(recursive_find_types(v))
    elif isinstance(data, list):
        for item in data:
            types.extend(recursive_find_types(item))
    return types

def clean_and_parse_json(raw_json_str):
    """
    Cleans up broken JSON string syntax (like inline comments or trailing commas) 
    that causes standard Python JSON parsers to crash.
    """
    # Remove JS double slash comments
    cleaned = re.sub(r'//.*', '', raw_json_str)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    
    # Remove trailing commas before closing braces/brackets
    cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None

# --- Main Schema Inspection Engine ---
def check_schema_robustly(url):
    """
    Downloads page using Cloudscraper, tests for protection screens, 
    and performs a multi-strategy audit.
    """
    scraper = cloudscraper.create_scraper()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5'
    }
    
    try:
        response = scraper.get(url, headers=headers, timeout=15)
        
        # Explicit check if page is actually blocked or serving an anti-bot challenge
        html_lower = response.text.lower()
        if "captcha-delivery" in html_lower or "cloudflare" in html_lower and "enable javascript" in html_lower:
            return "⚠️ Protected", "Blocked by Anti-Bot Screen (Cloudflare/Sucuri)"
            
        if response.status_code != 200:
            return "⚠️ Error", f"Status Error ({response.status_code})"
        
        detected_types = []
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Strategy A: Directly find and parse ALL script tag contents (Deep Hunter)
        json_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_scripts:
            if script.string:
                parsed_json = clean_and_parse_json(script.string.strip())
                if parsed_json:
                    detected_types.extend(recursive_find_types(parsed_json))
                    
        # Strategy B: Fallback to Extruct (Catches inline Microdata & RDFa formats)
        try:
            extruct_data = extruct.extract(response.text, base_url=url, syntaxes=['json-ld', 'microdata'])
            # Extract JSON-LD via Extruct
            for block in extruct_data.get('json-ld', []):
                detected_types.extend(recursive_find_types(block))
            # Extract Microdata via Extruct
            for block in extruct_data.get('microdata', []):
                if isinstance(block, dict) and 'type' in block:
                    raw_type = block['type']
                    if isinstance(raw_type, str):
                        detected_types.append(raw_type.split('/')[-1])
        except Exception:
            pass # Strategy A is already running, continue if Extruct errors out on messy tags
            
        # Deduplicate results
        detected_types = list(set([t for t in detected_types if t]))
        
        if detected_types:
            return "✅ Valid Schema", ", ".join(detected_types)
            
        return "❌ Missing", "No Schema Found (Checked JSON-LD & Microdata)"
        
    except requests.exceptions.Timeout:
        return "⚠️ Error", "Connection Timeout"
    except Exception as e:
        return "⚠️ Error", f"Failed to Fetch ({str(e)})"

# --- Sidebar Controls ---
st.sidebar.markdown("### 🛠️ Crawler Control Panel")
raw_website_input = st.sidebar.text_input("Target Domain Path", placeholder="example.com")
run_button = st.sidebar.button("🚀 Start Deep Scan", type="primary", use_container_width=True)

# --- Main App Execution ---
if run_button:
    if not raw_website_input:
        st.error("❗ Please provide a target domain extension before executing.")
    else:
        target_website = normalize_url(raw_website_input)
        
        with st.status("🛠️ Mapping Sitemap Routes & Bypassing Anti-Bot Walls...", expanded=True) as status_box:
            st.write("🕵️ Discovering active sitemaps...")
            sitemaps_to_run = discover_sitemaps(target_website)
            
            st.write("📥 Loading pages and ignoring system noise...")
            urls_to_check = extract_urls_from_sitemaps(target_website, sitemaps_to_run)
            status_box.update(label="Scanning Target Pipeline Configured!", state="complete", expanded=False)
        
        if not urls_to_check:
            st.error("❌ Process Halting: No URLs found.")
        else:
            progress_bar = st.progress(0)
            status_ticker = st.empty()
            results_data = []
            
            for index, url in enumerate(urls_to_check):
                status_ticker.markdown(f"**Inspecting Node ({index + 1}/{len(urls_to_check)}):** `{url}`")
                status, info = check_schema_robustly(url)
                
                results_data.append({
                    "Target URL Endpoint": url,
                    "Verification Status": status,
                    "Detected Types / Metadata": info
                })
                progress_bar.progress((index + 1) / len(urls_to_check))
                time.sleep(0.1) # Natural pause to prevent server rate-limiting
                
            status_ticker.empty()
            progress_bar.empty()
            
            # --- Interactive Analytics ---
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
            m_col4.metric("Error/Protected Pages", error_count, delta=f"{error_count} flagged" if error_count > 0 else None, delta_color="off")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Tabbed View Components
            tab1, tab2 = st.tabs(["📋 Inspection Data Stream", "📦 Data Export Panel"])
            
            with tab1:
                st.subheader("Data Overview Table")
                
                if not df.empty:
                    # Clean output values to render lists cleanly inside Streamlit's dataframe
                    df["Detected Types / Metadata"] = df["Detected Types / Metadata"].apply(
                        lambda x: [t.strip() for t in x.split(",")] if x and "No" not in x and "Connection" not in x and "Blocked" not in x else [x]
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
                    file_name="schemapulse_scan_results.csv",
                    mime="text/csv",
                    type="secondary"
                )
