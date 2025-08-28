# filepath: /home/djiang/jiang_ws/coding_ws/tree_health_analysis/app.py
import streamlit as st
from openai import AzureOpenAI #, RateLimitError
from PIL import Image
import base64
import os
import json
# from azure.identity import DefaultAzureCredential, get_bearer_token_provider
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import io
import pydeck as pdk

# --- 1. AZURE OPENAI CLIENT INITIALIZATION ---
try:
    # credential = DefaultAzureCredential()
    # token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
    # client = AzureOpenAI(
    #     api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    #     azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT_SWEDEN_CENTRAL"),
    #     azure_ad_token_provider=token_provider,
    # )
    client = AzureOpenAI(
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT_SWEDEN_CENTRAL"), 
        api_key=os.getenv("AZURE_OPENAI_API_KEY_SWEDEN_CENTRAL"),  
        api_version=os.getenv("AZURE_OPENAI_API_VERSION")
      )
    if not os.getenv("AZURE_OPENAI_ENDPOINT_SWEDEN_CENTRAL"):
        st.error("AZURE_OPENAI_ENDPOINT_SWEDEN_CENTRAL environment variable is not set.")
        st.stop()
except Exception as e:
    st.error(f"Failed to initialize Azure OpenAI client with Entra ID: {e}")
    st.info("Please ensure you are logged in via 'az login' and have the 'Cognitive Services OpenAI User' role.")
    st.stop()

# --- 2. MULTI-LANGUAGE SUPPORT ---
translations = {
    "English": {
        "title": "🌳 Tree Health Dashboard",
        "select_lang": "Select Language",
        "select_model": "Select AI Model",
        "clear_button": "Clear & Start Over",
        "upload_prompt": "📤 Drag & drop or click to upload tree images",
        "analyze_button": "Analyze Images",
        "health_grade": "Health Grade",
        "tree_type": "Tree Type",
        "approx_age": "Approx. Age",
        "location": "Photographed Location", # Origin / Location
        "native_origins": "Native Origins",
        "details_expander": "View Details & Chat",
        "observations": "Observations",
        "rehab_advice": "Rehabilitation Advice",
        "chat_prompt": "Ask a follow-up question...",
        "spinner_text": "Analyzing image {i} of {n}... 🌿",
        "clear_toast": "✅ Reset complete. Ready for new images.",
        "legend_header": "Health Grade Legend",
        "summary_table_header": "Batch Analysis Summary",
        "map_header": "Geographic Distribution of Trees",
        "debug_expander": "Debug Info",
        "map_fail_header": "Locations Not Found on Map",
        "map_fail_info": "The following locations were too general to be plotted:",
        "summary_filename": "Filename",
        "map_legend_header": "Map Legend",
        "map_legend_location": "Photographed Location",
        "map_legend_origin": "Native Origin"
    },
    "Deutsch": {
        "title": "🌳 Baumgesundheits-Dashboard",
        "select_lang": "Sprache auswählen",
        "select_model": "KI-Modell auswählen",
        "clear_button": "Löschen & Neustarten",
        "upload_prompt": "📤 Bilder per Drag & Drop oder Klick hochladen",
        "analyze_button": "Bilder analysieren",
        "health_grade": "Gesundheitsgrad",
        "tree_type": "Baumart",
        "approx_age": "Ungefähres Alter",
        "location": "Fotografierter Standort", # Herkunft / Standort
        "native_origins": "Heimische Herkunft",
        "details_expander": "Details & Chat anzeigen",
        "observations": "Beobachtungen",
        "rehab_advice": "Rehabilitationsratschläge",
        "chat_prompt": "Stellen Sie eine Folgefrage...",
        "spinner_text": "Analysiere Bild {i} von {n}... 🌿",
        "clear_toast": "✅ Zurücksetzen abgeschlossen. Bereit für neue Bilder.",
        "legend_header": "Legende der Gesundheitsgrade",
        "summary_table_header": "Zusammenfassung der Stapelanalyse",
        "map_header": "Geografische Verteilung der Bäume",
        "debug_expander": "Debug-Informationen",
        "map_fail_header": "Standorte, die nicht auf der Karte gefunden wurden",
        "map_fail_info": "Die folgenden Standorte waren zu allgemein, um dargestellt zu werden:",
        "summary_filename": "Dateiname",
        "map_legend_header": "Kartenlegende",
        "map_legend_location": "Fotografierter Standort",
        "map_legend_origin": "Heimische Herkunft"
    },
    "中文": {
        "title": "🌳 树木健康仪表板",
        "select_lang": "选择语言",
        "select_model": "选择AI模型",
        "clear_button": "清除并重新开始",
        "upload_prompt": "📤 拖拽或点击上传树木图片",
        "analyze_button": "分析图片",
        "health_grade": "健康等级",
        "tree_type": "树木种类",
        "approx_age": "大约年龄",
        "location": "拍摄地 / 位置",
        "native_origins": "主要原产地",
        "details_expander": "查看详情与对话",
        "observations": "观察结果",
        "rehab_advice": "复健建议",
        "chat_prompt": "提出后续问题...",
        "spinner_text": "正在分析第 {i} 张图片，共 {n} 张... 🌿",
        "clear_toast": "✅ 重置完成，请上传新图片。",
        "legend_header": "健康等级图例",
        "summary_table_header": "批量分析总览",
        "map_header": "树木地理位置分布",
        "debug_expander": "调试信息",
        "map_fail_header": "地图上未找到的位置",
        "map_fail_info": "以下位置因过于宽泛而无法标示：",
        "summary_filename": "文件名",
        "map_legend_header": "地图图例",
        "map_legend_location": "拍摄位置",
        "map_legend_origin": "原生栖息地"
    }
}

# --- 3. HELPER & VISUALIZATION FUNCTIONS ---
def get_text(lang, key):
    return translations.get(lang, translations["English"]).get(key)

def encode_image(image_bytes, resize_to=None):
    img = Image.open(io.BytesIO(image_bytes))
    if resize_to:
        img.thumbnail(resize_to)
    buffered = io.BytesIO()
    img_format = 'PNG' if img.mode == 'RGBA' else 'JPEG'
    img.save(buffered, format=img_format)
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def get_grade_details(grade):
    """Maps a health grade to a color, value, and description."""
    grade_map = {
        "A": {"color": "#28a745", "value": 100, "desc": "Excellent", "icon": "🌿"},
        "B": {"color": "#90EE90", "value": 80, "desc": "Good", "icon": "🌳"},
        "C": {"color": "#ffc107", "value": 60, "desc": "Fair", "icon": "⚠️"},
        "D": {"color": "#fd7e14", "value": 40, "desc": "Poor", "icon": "❗️"},
        "E": {"color": "#dc3545", "value": 20, "desc": "Critical", "icon": "🆘"},
        "F": {"color": "#6c757d", "value": 0, "desc": "Failed / Dead", "icon": "💀"},
    }
    return grade_map.get(str(grade).upper(), {"color": "#6c757d", "value": 0, "desc": "Unknown", "icon": "❓"})

def create_progress_circle(progress, color, size=120):
    stroke_width = 10
    radius = (size / 2) - stroke_width
    circumference = 2 * 3.14159 * radius
    stroke_dashoffset = circumference * (1 - progress / 100)
    svg = f"""<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" style="transform: rotate(-90deg);"><circle cx="{size/2}" cy="{size/2}" r="{radius}" fill="none" stroke="#e6e6e6" stroke-width="{stroke_width}" /><circle cx="{size/2}" cy="{size/2}" r="{radius}" fill="none" stroke="{color}" stroke-width="{stroke_width}" stroke-dasharray="{circumference}" stroke-dashoffset="{stroke_dashoffset}" stroke-linecap="round" /></svg>"""
    return svg

def clear_state(lang):
    """Resets the session state and increments the uploader key to clear it."""
    st.session_state.batch_results = []
    st.session_state.chat_histories = {}
    st.session_state.uploader_key += 1
    st.toast(get_text(lang, "clear_toast"))

@st.cache_resource
def get_geocoder():
    return RateLimiter(Nominatim(user_agent="tree_health_app").geocode, min_delay_seconds=1)

def get_lat_lon(location_str):
    if not location_str:
        return None, None
    
    # Expanded list of terms to treat as invalid locations
    unknown_terms = ['n/a', 'unknown', 'unspecified', 'uncertain', 'not specified']
    if any(term in location_str.lower() for term in unknown_terms):
        return None, None

    try:
        geocode = get_geocoder()
        location = geocode(location_str)
        if location:
            return location.latitude, location.longitude
    except Exception:
        return None, None
    return None, None

def image_to_html_thumbnail(img_bytes):
    b64_img = encode_image(img_bytes, resize_to=(50, 50))
    return f'<img src="data:image/png;base64,{b64_img}" width="50">'

def display_result_card(container, result, idx, lang):
    with container:
        st.image(result["image"], use_container_width=True, caption=f"Tree {idx+1}")
        
        if result["analysis"]:
            res = result["analysis"]
            grade = res.get("health_grade", "N/A")
            grade_details = get_grade_details(grade)
            
            viz_col1, viz_col2 = st.columns([1, 2])
            with viz_col1:
                st.image(create_progress_circle(grade_details["value"], grade_details["color"]), use_container_width=True)
            with viz_col2:
                st.metric(label=get_text(lang, "health_grade"), value=f"Grade {grade}")
                st.markdown(f"**{grade_details['icon']} {grade_details['desc']}**")

            st.markdown(f"""
            - **{get_text(lang, 'tree_type')}:** {res.get('tree_type', 'N/A')}
            - **{get_text(lang, 'approx_age')}:** {res.get('approximate_age', 'N/A')}
            - **{get_text(lang, 'location')}:** {res.get('location', 'N/A')}
            - **{get_text(lang, 'native_origins')}:** {', '.join(res.get('native_origins', [])) or 'N/A'}
            """)

            with st.expander(get_text(lang, "details_expander")):
                st.markdown(f"**{get_text(lang, 'observations')}:**")
                st.write(res.get("detailed_observations", "No details provided."))
                
                if res.get("is_diseased", False) or grade in ["C", "D", "E", "F"]:
                    st.markdown(f"**{get_text(lang, 'rehab_advice')}:**")
                    st.warning(res.get("rehabilitation_advice", "No advice available."))
                
                st.write("---")
                if idx not in st.session_state.chat_histories:
                    st.session_state.chat_histories[idx] = []

                for message in st.session_state.chat_histories[idx]:
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"])

                if prompt := st.chat_input(get_text(lang, "chat_prompt"), key=f"chat_{idx}"):
                    st.session_state.chat_histories[idx].append({"role": "user", "content": prompt})
                    with st.chat_message("user"):
                        st.markdown(prompt)

                    with st.chat_message("assistant"):
                        with st.spinner("Thinking..."):
                            context = f"The user is asking a follow-up question about a specific tree. The initial analysis for this tree was: {json.dumps(res)}."
                            messages_for_api = [{"role": "system", "content": context}] + st.session_state.chat_histories[idx]
                            
                            try:
                                chat_response = client.chat.completions.create(model=st.session_state.selected_model, messages=messages_for_api, max_completion_tokens=500)
                                response_text = chat_response.choices[0].message.content
                                st.markdown(response_text)
                                st.session_state.chat_histories[idx].append({"role": "assistant", "content": response_text})
                            except Exception as e:
                                st.error(f"An error occurred: {e}")
        else:
            st.error(f"Analysis Failed: {result['error']}")
            with st.expander(get_text(lang, "debug_expander")):
                st.code(result['raw_text'])

# --- 4. MAIN APPLICATION LOGIC ---
st.set_page_config(page_title="Tree Health Dashboard", layout="wide")

# Initialize session state
if 'batch_results' not in st.session_state:
    st.session_state.batch_results = []
if 'chat_histories' not in st.session_state:
    st.session_state.chat_histories = {}
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0
if 'selected_model' not in st.session_state:
    st.session_state.selected_model = "gpt-4.1"

# --- SIDEBAR ---
lang = st.sidebar.selectbox(get_text("English", "select_lang"), options=["English", "Deutsch", "中文"])
st.session_state.selected_model = st.sidebar.selectbox(get_text(lang, "select_model"), options=["gpt-4.1", "gpt-4o"])
st.sidebar.button(get_text(lang, "clear_button"), on_click=clear_state, args=(lang,), use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.subheader(get_text(lang, "legend_header"))
for grade in ["A", "B", "C", "D", "E", "F"]:
    details = get_grade_details(grade)
    st.sidebar.markdown(f"<span style='color:{details['color']};'>**{grade}**: {details['icon']} {details['desc']}</span>", unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.subheader(get_text(lang, "map_legend_header"))
st.sidebar.markdown(f"<span style='font-size: 18px; color: rgb(200, 30, 0);'>●</span> {get_text(lang, 'map_legend_location')}", unsafe_allow_html=True)
st.sidebar.markdown(f"<span style='font-size: 18px; color: rgb(30, 200, 0);'>●</span> {get_text(lang, 'map_legend_origin')}", unsafe_allow_html=True)


# --- MAIN PAGE ---
st.title(get_text(lang, "title"))

uploaded_files = st.file_uploader(
    get_text(lang, "upload_prompt"),
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True,
    key=f"file_uploader_{st.session_state.uploader_key}"
)

if uploaded_files and st.button(get_text(lang, "analyze_button")):
    st.session_state.batch_results = []
    st.session_state.chat_histories = {}
    
    num_columns = 3
    grid = st.columns(num_columns)
    
    for i, uploaded_file in enumerate(uploaded_files):
        placeholder = grid[i % num_columns].container(border=True)
        
        with placeholder:
            with st.spinner(get_text(lang, "spinner_text").format(i=i+1, n=len(uploaded_files))):
                img_bytes = uploaded_file.getvalue()
                base64_image = encode_image(img_bytes)
                
                system_prompt = """
                
                You are a professional botanist and tree pathologist. 
                Analyze the user-submitted tree image and provide a clear health assessment. 
                Please check specifically for the following indicators, but not limited to them:
                1. Deadwood and loose branches → risk of falling branches
                2. Fungal fruiting bodies → signs of white rot, brown rot, or soft rot
                3. Diseased or weak fork (branch junction) → increased risk of breakage
                4. Loose or peeling bark → possible internal stem decay
                5. Cavities or broken branches → structural instability
                If none of these indicators are present, state that the tree appears healthy. 
                If no tree is detected in the image, skip the analysis and return exactly: 'No tree'.
                
                Your response MUST be a single JSON object.
                The JSON structure is:
                {
                  "tree_type": "The common name and scientific name of the tree species, if identifiable.",
                  "approximate_age": "An estimated age of the tree in years (e.g., '10-15 years', 'Mature').",
                  "location": "The likely city and country where the photo was taken (e.g., 'Bonn, Germany'). If unknown, state 'Unknown'.",
                  "native_origins": "A list of up to three primary native countries or regions for this tree species. Example: ['Japan', 'Korea', 'China']. If the species is a hybrid or its origin is unknown, provide an empty list [].",
                  "health_status": "A brief summary (e.g., 'Healthy', 'Showing signs of stress', 'Diseased').",
                  "health_grade": "A single letter grade from A to F (A=Excellent, B=Good, C=Fair, D=Poor, E=Critical, F=Dead).",
                  "is_diseased": true or false,
                  "disease_identification": "If is_diseased is true, name the potential disease(s) or pest(s). Otherwise, 'None'.",
                  "detailed_observations": "A paragraph describing what you see in the image (leaf color, bark condition, trunk damage, etc.).",
                  "rehabilitation_advice": "If is_diseased is true or health_grade is C or lower, provide a detailed, actionable rehabilitation plan. Otherwise, provide simple maintenance tips."
                }
                Do not add any text or formatting outside of this JSON object.
                """
                result_text = ""
                try:
                    response = client.chat.completions.create(
                        model=st.session_state.selected_model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": [{"type": "text", "text": f"Analyze this tree. Respond in {lang}."}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}]}
                        ],
                        max_completion_tokens=1500, temperature=0.5
                    )
                    result_text = response.choices[0].message.content
                    analysis_data = json.loads(result_text)
                    result_payload = {"image": img_bytes, "analysis": analysis_data, "error": None, "raw_text": None, "filename": uploaded_file.name}
                except Exception as e:
                    error_text = getattr(e, 'message', str(e))
                    raw_output = result_text if result_text else "No response from model."
                    result_payload = {"image": img_bytes, "analysis": None, "error": error_text, "raw_text": raw_output, "filename": uploaded_file.name}
                
                st.session_state.batch_results.append(result_payload)
        
        # After spinner is done, display the final card in the same placeholder
        display_result_card(placeholder, result_payload, i, lang)

if st.session_state.batch_results:
    st.write("---")
    st.subheader(get_text(lang, "summary_table_header"))
    
    summary_data = []
    location_points = []
    origin_points = []
    failed_locations = []

    for idx, result in enumerate(st.session_state.batch_results):
        if result["analysis"]:
            res = result["analysis"]
            
            # Process photographed location
            loc_str = res.get('location', 'N/A')
            lat, lon = get_lat_lon(loc_str)
            if lat and lon:
                location_points.append({
                    "lat": lat, "lon": lon, 
                    "tooltip": f"<b>Photographed Location</b><br>{loc_str}",
                    "location_text": loc_str
                })
            elif loc_str.lower() not in ['n/a', 'unknown']:
                failed_locations.append(loc_str)

            # Process native origins
            native_origins = res.get('native_origins', [])
            for origin_loc in native_origins:
                origin_lat, origin_lon = get_lat_lon(origin_loc)
                if origin_lat and origin_lon:
                    origin_points.append({
                        "lat": origin_lat, "lon": origin_lon,
                        "tooltip": f"<b>Native Origin: {res.get('tree_type')}</b><br>{origin_loc}"
                    })

            summary_data.append({
                get_text(lang, "summary_filename"): result.get("filename", "N/A"),
                "Thumbnail": image_to_html_thumbnail(result['image']),
                get_text(lang, "health_grade"): res.get('health_grade', 'N/A'),
                get_text(lang, "tree_type"): res.get('tree_type', 'N/A'),
                get_text(lang, "location"): loc_str,
                get_text(lang, "native_origins"): ', '.join(native_origins) or 'N/A',
            })
        else:
             summary_data.append({
                get_text(lang, "summary_filename"): result.get("filename", "N/A"), 
                "Thumbnail": image_to_html_thumbnail(result['image']), 
                get_text(lang, "health_grade"): "Error", 
                get_text(lang, "tree_type"): "Error", 
                get_text(lang, "location"): "Error",
                get_text(lang, "native_origins"): "Error"
            })

    if summary_data:
        df = pd.DataFrame(summary_data)
        st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)

    st.subheader(get_text(lang, "map_header"))
    map_layers = []
    if location_points:
        loc_df = pd.DataFrame(location_points)
        map_layers.append(pdk.Layer(
            'ScatterplotLayer', data=loc_df, get_position='[lon, lat]',
            get_color='[200, 30, 0, 160]', get_radius=50000, pickable=True
        ))
        map_layers.append(pdk.Layer(
            'TextLayer', data=loc_df, get_position='[lon, lat]', get_text='location_text',
            get_size=15, get_color='[255, 255, 255, 200]', get_angle=0,
            get_text_anchor='"middle"', get_alignment_baseline='"bottom"'
        ))

    if origin_points:
        origin_df = pd.DataFrame(origin_points)
        map_layers.append(pdk.Layer(
            'ScatterplotLayer', data=origin_df, get_position='[lon, lat]',
            get_color='[30, 200, 0, 160]', get_radius=30000, pickable=True # Green, smaller radius
        ))

    if map_layers:
        initial_view_state = pdk.ViewState(latitude=30, longitude=0, zoom=1, pitch=0)
        st.pydeck_chart(pdk.Deck(
            map_style='https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
            initial_view_state=initial_view_state,
            layers=map_layers,
            tooltip={"html": "{tooltip}", "style": {"color": "white"}}
        ))
    
    if failed_locations:
        st.warning(get_text(lang, "map_fail_header"))
        st.info(f"{get_text(lang, 'map_fail_info')} {', '.join(set(failed_locations))}")
    elif not map_layers:
         st.info("No valid location data was found in the analysis results to display on the map.")
