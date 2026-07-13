import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import pandas as pd
import time
from urllib.parse import urlparse

# --- Page Setup & Modern Styling ---
st.set_page_config(
    page_title="SchemaPulse | Structured Data Auditor",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS Injector for Premium Look & Feel
st.markdown("""
    <style>
        /* Main metric layout enhancements */
        [data-testid="stMetricValue"] {
            font-size: 2.2rem !important;
            font-weight: 700 !important;
        }
        /* Custom styled containers */
        .status-box {
            padding: 1.5rem;
            border-radius: 0.5rem;
            background-color: #f8f9fa;
            border-left: 5px solid #6c757d;
            margin-bottom: 1rem;
        }
        /* Hide default Streamlit decoration lines if desired */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- Header & Brand Title ---
st.markdown("<h1 style='text-align: left; margin-bottom:0;'>⚡ SchemaPulse</h1>", unsafe_allow_html=True)
st.markdown("<p style='font-size:1.1rem; color:#6c757d; margin-top:0;'>Automated SEO Structured Data Auditing for Home & Core Service Pages</p>", unsafe_allow_html=True)
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
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    clean_base = base_url.rstrip('/') + '/'
    index_files = ["sitemap.xml", "sitemap_index.xml"]
    discovered_sitemaps = []
    
    for index_file in index_files:
        index_url = f"{clean_base}{index_file}"
        try:
            response = requests.get(index_url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'xml')
                loc_tags = soup.find_all('loc')
                for tag in loc_tags:
                    sitemap_loc = tag.text.strip().lower()
                    if "page" in sitemap_loc or "astra-portfolio" in sitemap_loc:
                        discovered_sitemaps.append(tag.text.strip())
        except Exception:
            continue
            
    if not discovered_sitemaps:
        discovered_sitemaps = [
            f"{clean_base}page-sitemap.xml",
            f"{clean_base}astra-portfolio-sitemap.xml",
            f"{clean_base}astra-portfolio-sitemap1.xml"
        ]
    return list(set(discovered_sitemaps))

def extract_urls_from_sitemaps(base_url, discovered_sitemaps):
    urls = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    clean_base = base_url.rstrip('/') + '/'
    urls.append(clean_base)

    for sitemap_url in discovered_sitemaps:
        try:
            response = requests.get(sitemap_url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'xml')
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
    return sorted(list(set(urls)))

def check_schema(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return "⚠️ Error", f"Status Error ({response.status_code})"
        
        soup = BeautifulSoup(response.text, 'html.parser')
        schema_tags = soup.find_all('script', type='application/ld+json')
        if not schema_tags:
            return "❌ Missing", "No JSON-LD Detected"
        
        schema_types = []
        for tag in schema_tags:
            try:
                data = json.loads(tag.string)
                if isinstance(data, dict):
                    if '@type' in data: schema_types.append(data['@type'])
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and '@type' in item: schema_types.append(item['@type'])
            except: pass
                
        if schema_types:
            return "✅ Valid Schema", ", ".join(list(set(schema_types)))
        return "❌ Missing", "No Schema Data Present"
    except Exception:
        return "⚠️ Error", "Connection Timeout/Failed"

# --- Sidebar Controls Layout ---
st.sidebar.markdown("### 🛠️ Crawler Control Panel")
raw_website_input = st.sidebar.text_input("Target Domain Path", placeholder="example.com")
run_button = st.sidebar.button("🚀 Start Deep Scan", type="primary", use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.markdown("#### 🚫 System Filter Constraints")
with st.sidebar.expander("View Active Exclusions List"):
    st.write(IGNORE_KEYWORDS)

# --- Main Dashboard Execution Flow ---
if run_button:
    if not raw_website_input:
        st.error("❗ Please provide a target domain extension before executing the scanner pipeline.")
    else:
        target_website = normalize_url(raw_website_input)
        
        # Discovery Steps UI Box
        with st.status("🛠️ Initiating Mapping Engines & Link Filtering...", expanded=True) as status_box:
            st.write("🕵️ Discovering applicable index structures...")
            sitemaps_to_run = discover_sitemaps(target_website)
            st.write(f"📂 Selected sitemaps for tracking: `{[s.split('/')[-1] for s in sitemaps_to_run]}`")
            
            st.write("📥 Fetching active routes & stripping system noise...")
            urls_to_check = extract_urls_from_sitemaps(target_website, sitemaps_to_run)
            status_box.update(label="Target Pipeline Complete!", state="complete", expanded=False)
        
        if not urls_to_check:
            st.error("❌ Process Halting: No URLs remain after filtering against exclusions constraints.")
        else:
            # Progress Tracking Cards
            progress_bar = st.progress(0)
            status_ticker = st.empty()
            results_data = []
            
            for index, url in enumerate(urls_to_check):
                status_ticker.markdown(f"**Scanning Node ({index + 1}/{len(urls_to_check)}):** `{url}`")
                status, info = check_schema(url)
                
                results_data.append({
                    "Target URL Endpoint": url,
                    "Verification Status": status,
                    "Detected Types / Metadata": info
                })
                progress_bar.progress((index + 1) / len(urls_to_check))
                time.sleep(0.05)
                
            status_ticker.empty()
            progress_bar.empty()
            
            # --- Interactive Analytics Block ---
            df = pd.DataFrame(results_data)
            total_count = len(df)
            valid_count = len(df[df["Verification Status"] == "✅ Valid Schema"])
            missing_count = len(df[df["Verification Status"] == "❌ Missing"])
            error_count = total_count - (valid_count + missing_count)
            
            st.markdown("### 📈 Verification Performance")
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            m_col1.metric("Audited Routes", total_count)
            m_col2.metric("Schema Configured", valid_count, help="JSON-LD code detected")
            m_col3.metric("Unstructured Pages", missing_count, delta=f"-{missing_count}" if missing_count > 0 else None, delta_color="inverse")
            m_col4.metric("Crawling Errors", error_count, delta=f"{error_count} flagged" if error_count > 0 else None, delta_color="off")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Tabbed View Components
            tab1, tab2 = st.tabs(["📋 Inspection Data Stream", "📦 Data Export Panel"])
            
            with tab1:
                st.subheader("Data Overview Table")
                st.dataframe(
                    df, 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={
                        "Verification Status": st.column_config.SelectColumn(
                            "Verification Status",
                            width="medium"
                        ),
                        "Target URL Endpoint": st.column_config.LinkColumn("Target URL Endpoint")
                    }
                )
                
            with tab2:
                st.subheader("Download Artifacts")
                st.markdown("Download the full execution audit log to a CSV spreadsheet.")
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Data Sheet (.csv)",
                    data=csv,
                    file_name="schemapulse_audit_log.csv",
                    mime="text/csv",
                    type="secondary"
                )
