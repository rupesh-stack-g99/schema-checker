import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import pandas as pd
import time

# --- Page Setup & Styling ---
st.set_page_config(
    page_title="SEO Schema Verifier",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 Site-Wide Schema Checker Automation")
st.markdown("Enter your domain below. The app will pull all URLs from your target sitemaps and clean them based on your strict ignore rules.")

# --- The Strict Ignore Rules (Based on your requirements) ---
IGNORE_KEYWORDS = [
    "wp-content",
    "terms",
    "condition",
    "services",        # Strips out main service listing page if requested
    "privacy",
    "policy",
    "/portfolio/",
    "/html-sitemap/",
    "contact",         # Catches contact, contact-us, contact-us/
    "about",           # Catches about, about-us, about-us/
    "review",          # Catches review, reviews, customer-reviews
    "gallery"          # Catches gallery, photo-gallery
]

# Asset extensions to ignore completely
IGNORE_EXTENSIONS = (".svg", ".webp", ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".ico")

# --- Functions ---
def extract_urls_from_sitemaps(base_url, sitemap_list):
    urls = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    clean_base = base_url.rstrip('/') + '/'
    # Always keep the primary homepage
    urls.append(clean_base)

    for sitemap in sitemap_list:
        sitemap_url = f"{clean_base}{sitemap.lstrip('/')}"
        try:
            response = requests.get(sitemap_url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'xml')
                loc_tags = soup.find_all('loc')
                for tag in loc_tags:
                    if tag.text:
                        url = tag.text.strip()
                        url_lower = url.lower()
                        
                        # 1. Skip if it's a file (pdf, webp, svg, etc)
                        if url_lower.endswith(IGNORE_EXTENSIONS):
                            continue
                            
                        # 2. Skip if it matches any of your manual ignore terms
                        if any(keyword in url_lower for keyword in IGNORE_KEYWORDS):
                            # Ensure we don't accidentally ignore the homepage root if a keyword triggers it
                            if url.rstrip('/') != clean_base.rstrip('/'):
                                continue
                        
                        urls.append(url)
            else:
                st.sidebar.warning(f"Could not reach sitemap: {sitemap}")
        except Exception as e:
            st.sidebar.error(f"Error fetching {sitemap}: {e}")
            
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
target_website = st.sidebar.text_input("Website Domain:", placeholder="https://yourwebsite.com")

sitemaps_to_check = [
    "page-sitemap.xml",
    "astra-portfolio-sitemap.xml"
]

# --- Main App Logic ---
if st.sidebar.button("🚀 Run Automation", type="primary"):
    if not target_website:
        st.error("Please enter a valid website URL first!")
    else:
        with st.spinner("📥 Extracting and filtering URLs based on your ignore list..."):
            urls_to_check = extract_urls_from_sitemaps(target_website, sitemaps_to_check)
        
        if not urls_to_check:
            st.error("No URLs remaining after applying filters.")
        else:
            st.success(f"🎯 Filter applied! Found {len(urls_to_check)} pages to analyze.")
            
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
                st.metric("Total Filtered Pages", len(df))
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
