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
    initial_sidebar_state="collapsed" # Collapsed by default for a cleaner main screen
)

# Custom CSS for UI centering and styling
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
        
        /* Centering the main header text */
        .centered-header {
            text-align: center;
            margin-bottom: 0px;
        }
        .centered-subheader {
            text-align: center;
            font-size: 1.1rem;
            color: #6c757d;
            margin-top: 0px;
            margin-bottom: 15px;
        }
        .detailed-explanation {
            text-align: center !important;
            max-width: 900px;
            margin: 0 auto 30px auto;
            font-size: 1.25rem !important;
            font-weight: 400;
            line-height: 1.6;
            color: #b0b3b8;
        }
    </style>
""", unsafe_allow_html=True)

# Centered Headings
st.markdown("<h1 class='centered-header'>⚡ SchemaPulse</h1>", unsafe_allow_html=True)
st.markdown("<p class='centered-subheader'>Anti-Bot Resilient Multi-Format Structured Data Auditor</p>", unsafe_allow_html=True)

# Detailed H2 Explanation Section (Explicitly Center-Aligned)
st.markdown("<h2 class='detailed-explanation'>🔍 Auditing your live production environment to verify that structural schema architecture is correctly mapped and active across your homepage, service offerings, and core landing pages.</h2>", unsafe_allow_html=True)

# --- Center-Aligned Input Layout ---
# Creating columns to perfectly center the input box on the page
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    raw_website_input = st.text_input(
        "Target Domain Path", 
        placeholder="example.com", 
        label_visibility="collapsed"
    )
    # Centered primary action button
    run_button = st.button("🚀 Start Deep Scan", type="primary", use_container_width=True)

st.markdown("---")

# --- Ignore Rules (Updated: Removed contact, about, review, gallery) ---
IGNORE_KEYWORDS = [
    "wp-content", "terms", "condition", "privacy", "policy", "policies",        
    "shop", "specials", "payment-plans", "our-services", "/html-sitemap/",
    "awards", "before-after", "blog", "video", "thank-you"        
]
IGNORE_EXTENSIONS = (
    ".svg", ".webp", ".pdf", ".jpg", ".jpeg", ".png", 
    ".gif", ".ico", "locations.kml", ".kml"
)

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
    index_files = ["sitemap.xml", "sitemap_index.xml", "post-sitemap.xml"]
    discovered_sitemaps = []
    
    scraper = cloudscraper.create_scraper()
    for index_file in index_files:
        index_url = f"{clean_base}{index_file}"
        try:
            response = scraper.get(index_url, timeout=10)
            if response.status_code == 200:
                if index_file == "post-sitemap.xml":
                    discovered_sitemaps.append(index_url)
                    continue
                
                soup = BeautifulSoup(response.content, 'xml')
                for tag in soup.find_all('loc'):
                    sitemap_loc = tag.text.strip().lower()
                    if "page" in sitemap_loc or "sitemap" in sitemap_loc or "post" in sitemap_loc:
                        discovered_sitemaps.append(tag.text.strip())
        except Exception:
            continue
            
    if not discovered_sitemaps:
        discovered_sitemaps = [f"{clean_base}page-sitemap.xml", f"{clean_base}post-sitemap.xml", f"{clean_base}sitemap.xml"]
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
    types = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k in ('@type', 'type') and isinstance(v, str):
                types.append(v.split('/')[-1])
            elif isinstance(v, (dict, list)):
                types.extend(recursive_find_types(v))
    elif isinstance(data, list):
        for item in data:
            types.extend(recursive_find_types(item))
    return types

def clean_and_parse_json(raw_json_str):
    cleaned = re.sub(r'//.*', '', raw_json_str)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    
    cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None

# --- Main Schema Inspection Engine ---
def check_schema_robustly(url):
    scraper = cloudscraper.create_scraper()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5'
    }
    
    try:
        response = scraper.get(url, headers=headers, timeout=15)
        
        html_lower = response.text.lower()
        if "captcha-delivery" in html_lower or "cloudflare" in html_lower and "enable javascript" in html_lower:
            return "⚠️ Protected", "Blocked by Anti-Bot Screen (Cloudflare/Sucuri)"
            
        if response.status_code != 200:
            return "⚠️ Error", f"Status Error ({response.status_code})"
        
        detected_types = []
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Strategy A: Deep Parser
        json_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_scripts:
            if script.string:
                parsed_json = clean_and_parse_json(script.string.strip())
                if parsed_json:
                    detected_types.extend(recursive_find_types(parsed_json))
                    
        # Strategy B: Extruct
        try:
            extruct_data = extruct.extract(response.text, base_url=url, syntaxes=['json-ld', 'microdata'])
            for block in extruct_data.get('json-ld', []):
                detected_types.extend(recursive_find_types(block))
            for block in extruct_data.get('microdata', []):
                if isinstance(block, dict) and 'type' in block:
                    raw_type = block['type']
                    if isinstance(raw_type, str):
                        detected_types.append(raw_type.split('/')[-1])
        except Exception:
            pass
            
        detected_types = list(set([t for t in detected_types if t]))
        
        if detected_types:
            return "✅ Valid Schema", ", ".join(detected_types)
            
        return "❌ Missing", "No Schema Found (Checked JSON-LD & Microdata)"
        
    except requests.exceptions.Timeout:
        return "⚠️ Error", "Connection Timeout"
    except Exception as e:
        return "⚠️ Error", f"Failed to Fetch ({str(e)})"

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
                time.sleep(0.1)
                
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
            
            tab1, tab2 = st.tabs(["📋 Inspection Data Stream", "📦 Data Export Panel"])
            
            with tab1:
                st.subheader("Data Overview Table")
                
                st.dataframe(
                    df, 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={
                        "Target URL Endpoint": st.column_config.LinkColumn("Target URL Endpoint", width="large"),
                        "Verification Status": st.column_config.TextColumn("Verification Status", width="medium"),
                        "Detected Types / Metadata": st.column_config.TextColumn("Detected Types / Metadata", width="large")
                    }
                )
                
            with tab2:
                st.subheader("Download Artifacts")
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Data Sheet (.csv)",
                    data=csv,
                    file_name="schemapulse_scan_results.csv",
                    mime="text/csv",
                    type="secondary"
                )

# --- Bottom Collapsible Exclusions View (Closed by Default) ---
st.markdown("<br><br>", unsafe_allow_html=True)
with st.expander("⚙️ View Active URL Exclusion Rules (Closed by Default)"):
    st.markdown("To speed up auditing, the crawler automatically ignores non-contextual pages or complex non-HTML document objects.")
    col_ex1, col_ex2 = st.columns(2)
    with col_ex1:
        st.write("**Ignored Keywords:**")
        st.code(", ".join(IGNORE_KEYWORDS))
    with col_ex2:
        st.write("**Ignored Extensions & Document Assets:**")
        st.code(", ".join(IGNORE_EXTENSIONS))
