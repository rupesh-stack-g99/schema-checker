import streamlit as st
import requests
from bs4 import BeautifulSoup
import extruct
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

# Custom CSS for UI
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
st.markdown("<p style='font-size:1.1rem; color:#6c757d; margin-top:0;'>Multi-Format Structured Data Auditor (JSON-LD & Microdata)</p>", unsafe_allow_html=True)
st.markdown("---")

# --- Ignore Rules ---
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
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    clean_base = base_url.rstrip('/') + '/'
    urls.append(clean_base)

    for sitemap_url in discovered_sitemaps:
        try:
            response = requests.get(sitemap_url, headers=headers, timeout=10)
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

# --- Extruct Integration Core Logic ---
def check_schema_with_extruct(url):
    """
    Parses both JSON-LD and Microdata declarations using the extruct engine.
    """
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) SchemaPulse/1.0'}
    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code != 200:
            return "⚠️ Error", f"Status Error ({response.status_code})"
        
        # Base url is crucial for resolving relative schema structures
        data = extruct.extract(response.text, base_url=url, syntaxes=['json-ld', 'microdata'])
        
        detected_types = []
        
        # 1. Check JSON-LD Blocks
        for block in data.get('json-ld', []):
            if isinstance(block, dict):
                # Handle @graph patterns inside nested JSON-LD arrays
                if '@graph' in block:
                    for sub_block in block['@graph']:
                        if isinstance(sub_block, dict) and '@type' in sub_block:
                            detected_types.append(sub_block['@type'])
                elif '@type' in block:
                    detected_types.append(block['@type'])
                    
        # 2. Check Microdata (e.g., HTML markup with itemscope/itemtype)
        for block in data.get('microdata', []):
            if isinstance(block, dict) and 'type' in block:
                # Extruct types usually come back as full URLs like http://schema.org/LocalBusiness
                raw_type = block['type']
                if isinstance(raw_type, str):
                    type_name = raw_type.split('/')[-1]
                    detected_types.append(type_name)

        # Cleanup duplicate types
        detected_types = list(set(detected_types))
        
        if detected_types:
            return "✅ Valid Schema", ", ".join(detected_types)
            
        return "❌ Missing", "No Schema Found (Checked JSON-LD & Microdata)"
        
    except requests.exceptions.Timeout:
        return "⚠️ Error", "Connection Timeout"
    except Exception as e:
        return "⚠️ Error", "Parsing Failed"

# --- Sidebar ---
st.sidebar.markdown("### 🛠️ Crawler Control Panel")
raw_website_input = st.sidebar.text_input("Target Domain Path", placeholder="example.com")
run_button = st.sidebar.button("🚀 Start Deep Scan", type="primary", use_container_width=True)

# --- Main App Logic ---
if run_button:
    if not raw_website_input:
        st.error("❗ Please provide a target domain extension before executing.")
    else:
        target_website = normalize_url(raw_website_input)
        
        with st.status("🛠️ Mapping Sitemap Routes & Stripping Exclusions...", expanded=True) as status_box:
            st.write("🕵️ Discovering active sitemap indexing...")
            sitemaps_to_run = discover_sitemaps(target_website)
            
            st.write("📥 Loading pages and ignoring system files...")
            urls_to_check = extract_urls_from_sitemaps(target_website, sitemaps_to_run)
            status_box.update(label="Scanning Target Pipeline Configured!", state="complete", expanded=False)
        
        if not urls_to_check:
            st.error("❌ Process Halting: No URLs remain after filtering against exclusions.")
        else:
            progress_bar = st.progress(0)
            status_ticker = st.empty()
            results_data = []
            
            for index, url in enumerate(urls_to_check):
                status_ticker.markdown(f"**Inspecting Node ({index + 1}/{len(urls_to_check)}):** `{url}`")
                status, info = check_schema_with_extruct(url)
                
                results_data.append({
                    "Target URL Endpoint": url,
                    "Verification Status": status,
                    "Detected Types / Metadata": info
                })
                progress_bar.progress((index + 1) / len(urls_to_check))
                time.sleep(0.05)
                
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
            m_col2.metric("Schema Found Pages", valid_count, help="Valid structured JSON-LD or Microdata found")
            m_col3.metric("Missing Schema Pages", missing_count, delta=f"-{missing_count}" if missing_count > 0 else None, delta_color="inverse")
            m_col4.metric("Error Pages", error_count, delta=f"{error_count} flagged" if error_count > 0 else None, delta_color="off")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Tabbed View Components
            tab1, tab2 = st.tabs(["📋 Inspection Data Stream", "📦 Data Export Panel"])
            
            with tab1:
                st.subheader("Data Overview Table")
                
                if not df.empty:
                    # Parse text list back into dynamic table tags for a clean visualization layout
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
                    file_name="extruct_schema_audit.csv",
                    mime="text/csv",
                    type="secondary"
                )
