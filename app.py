import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import pandas as pd
import time
from urllib.parse import urlparse

# --- Page Setup & Styling ---
st.set_page_config(
    page_title="SEO Schema Verifier",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 Site-Wide Schema Checker Automation")
st.markdown("Enter your domain below. The app will automatically discover sitemaps matching `page` or `astra-portfolio` patterns and clean up matching target pages.")

# --- Corrected Ignore Rules ---
IGNORE_KEYWORDS = [
    "wp-content",
    "terms",
    "condition",
    "privacy",
    "policy",
    "/html-sitemap/",
    "contact",         
    "about",           
    "review",          
    "gallery",         
    "awards",          
    "before-after",    
    "blog",            
    "video",           
    "thank-you"        
]

IGNORE_EXTENSIONS = (".svg", ".webp", ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".ico")

# --- URL Normalizer ---
def normalize_url(url_input):
    """Ensures input domain has a protocol prefix and handles formatting variations smoothly."""
    url_str = url_input.strip()
    if not url_str:
        return ""
        
    # Prepend secure protocol if completely missing
    if not url_str.startswith(('http://', 'https://')):
        url_str = 'https://' + url_str
        
    parsed = urlparse(url_str)
    # Combine schema and network location framework
    base = f"{parsed.scheme}://{parsed.netloc}"
    return base.rstrip('/') + '/'

# --- Functions ---
def discover_sitemaps(base_url):
    """Finds any sitemaps matching 'page' or 'astra-portfolio' from the sitemap index."""
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
        st.sidebar.info(f"📥 Reading Sitemap: {sitemap_url.split('/')[-1]}")
        try:
            response = requests.get(sitemap_url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'xml')
                loc_tags = soup.find_all('loc')
                for tag in loc_tags:
                    if tag.text:
                        url = tag.text.strip()
                        url_lower = url.lower()
                        
                        if url_lower.endswith(IGNORE_EXTENSIONS):
                            continue
                            
                        if any(keyword in url_lower for keyword in IGNORE_KEYWORDS):
                            if url.rstrip('/') != clean_base.rstrip('/'):
                                continue
                        
                        urls.append(url)
        except Exception as e:
            st.sidebar.error(f"Error accessing sitemap contents: {e}")
            
    return sorted(list(set(urls)))

def check_schema(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return "⚠️ Error", f"Status Error ({response.status_code})", []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        schema_tags = soup.find_all('script', type='application/ld+json')
        
        if not schema_tags:
            return "❌ No Schema", "None", []
        
        schema_types = []
        for tag in schema_tags:
            try:
                data = json.loads(tag.string)
                if isinstance(data, dict):
                    if '@type' in data: schema_types.append(data['@type'])
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and '@type' in item: schema_types.append(item['@type'])
            except:
                continue
                
        if schema_types:
            return "✅ Yes", ", ".join(list(set(schema_types))), list(set(schema_types))
        else:
            return "❌ No Schema", "None", []
            
    except Exception:
        return "⚠️ Error", "Connection Failed", []

# --- Sidebar Inputs ---
st.sidebar.header("🛠️ Configuration")
raw_website_input = st.sidebar.text_input("Website Domain:", placeholder="example.com")

# --- Main App Logic ---
if st.sidebar.button("🚀 Run Automation", type="primary"):
    if not raw_website_input:
        st.error("Please enter a valid website URL first!")
    else:
        # Normalize target string input instantly
        target_website = normalize_url(raw_website_input)
        st.info(f"🔍 Normalizing target endpoint to: `{target_website}`")
        
        with st.spinner("🔍 Map Discovery: Finding relevant target sitemaps..."):
            sitemaps_to_run = discover_sitemaps(target_website)
            
        with st.spinner("📥 Extracting and filtering URLs based on your ignore list..."):
            urls_to_check = extract_urls_from_sitemaps(target_website, sitemaps_to_run)
        
        if not urls_to_check:
            st.error("No URLs remaining after applying structural filters.")
        else:
            st.success(f"🎯 Found {len(urls_to_check)} custom audited pages to analyze.")
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            results_data = []
            
            for index, url in enumerate(urls_to_check):
                status_text.text(f"Scanning ({index + 1}/{len(urls_to_check)}): {url}")
                status, detected_types, types_list = check_schema(url)
                
                results_data.append({
                    "URL": url,
                    "Schema Status": status,
                    "Detected Schema Types": detected_types
                })
                
                progress_bar.progress((index + 1) / len(urls_to_check))
                time.sleep(0.1)
            
            status_text.empty()
            progress_bar.empty()
            
            # Summary Dashboard
            df = pd.DataFrame(results_data)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Targeted Pages", len(df))
            with col2:
                st.metric("Schema Found", len(df[df["Schema Status"] == "✅ Yes"]))
            with col3:
                st.metric("Missing Schema", len(df[df["Schema Status"] != "✅ Yes"]))
            
            # Results Table
            st.subheader("📊 Automation Report")
            st.dataframe(df, use_container_width=True)
            
            # Export Options
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Clean CSV Report",
                data=csv,
                file_name="filtered_schema_report.csv",
                mime="text/csv",
            )
