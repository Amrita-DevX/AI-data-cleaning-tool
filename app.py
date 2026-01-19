import streamlit as st
import pandas as pd
from groq import Groq
import json
import io
import plotly.express as px
import plotly.graph_objects as go
import os

# Page configuration
st.set_page_config(
    page_title="AI Data Cleaning Assistant",
    page_icon="🧹",
    layout="wide"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        color: #1f77b4;
    }
    .sub-header {
        text-align: center;
        color: #666;
        margin-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.markdown('<p class="main-header">🧹 AI Data Cleaning Assistant</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Upload CSV or Excel files and let AI clean your data - Powered by Groq</p>', unsafe_allow_html=True)

# Initialize Groq client
@st.cache_resource
def get_client():
    """Initialize Groq API client"""
    try:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            st.error("⚠️ GROQ_API_KEY not found. Please set it as an environment variable.")
            st.info("Get your free API key from: https://console.groq.com")
            return None
        return Groq(api_key=api_key)
    except Exception as e:
        st.error(f"Error initializing Groq client: {str(e)}")
        return None

client = get_client()

def analyze_data(df_sample):
    """Use Groq to analyze the data and identify issues"""
    if client is None:
        return None
    
    csv_string = df_sample.to_csv(index=False)
    
    try:
        # Create chat completion with Groq
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # Fast and free model
            messages=[{
                "role": "user",
                "content": f"""Analyze this CSV data sample and provide data cleaning recommendations. 
Return ONLY a valid JSON object with this exact structure (no markdown, no explanations):
{{
  "issues": ["list of specific issues found"],
  "recommendations": ["list of cleaning steps to take"],
  "summary": "brief summary of data quality",
  "severity": "high/medium/low"
}}

CSV Data Sample:
{csv_string}"""
            }],
            temperature=0.3,
            max_tokens=1500
        )
        
        response_text = response.choices[0].message.content
        
        # Parse JSON response
        try:
            # Remove markdown code blocks if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            response_text = response_text.strip()
            analysis = json.loads(response_text)
            return analysis
        except json.JSONDecodeError:
            # Fallback: try to find JSON in the response
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            if start != -1 and end > start:
                json_str = response_text[start:end]
                analysis = json.loads(json_str)
                return analysis
            else:
                st.error("Could not parse AI response. Please try again.")
                return None
                
    except Exception as e:
        st.error(f"Analysis error: {str(e)}")
        return None

def clean_data(df, issues):
    """Use Groq to clean the actual dataset"""
    if client is None:
        return None
    
    csv_string = df.to_csv(index=False)
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{
                "role": "user",
                "content": f"""Clean this CSV data based on these issues: {', '.join(issues)}

Apply these fixes intelligently:
1. Remove duplicate rows
2. Handle missing values (median for numbers, mode for categories, or remove if >50% missing)
3. Standardize formats (dates, text case, numbers)
4. Remove extra whitespace and special characters where inappropriate
5. Fix obvious data entry errors
6. Ensure consistent data types per column

IMPORTANT: Return ONLY the cleaned CSV data with headers. No explanations, no markdown formatting, just the raw CSV.

Original CSV Data:
{csv_string}"""
            }],
            temperature=0.2,
            max_tokens=4000
        )
        
        cleaned_csv = response.choices[0].message.content
        
        # Clean up response - remove markdown if present
        if "```csv" in cleaned_csv:
            cleaned_csv = cleaned_csv.split("```csv")[1].split("```")[0]
        elif "```" in cleaned_csv:
            lines = cleaned_csv.split('\n')
            cleaned_csv = '\n'.join([l for l in lines if not l.strip().startswith('```')])
        
        return cleaned_csv.strip()
        
    except Exception as e:
        st.error(f"Cleaning error: {str(e)}")
        return None

def create_data_quality_viz(df):
    """Create visualizations for data quality"""
    
    # 1. Missing values chart
    missing = df.isnull().sum()
    missing = missing[missing > 0].sort_values(ascending=False)
    
    if len(missing) > 0:
        fig_missing = px.bar(
            x=missing.values,
            y=missing.index,
            orientation='h',
            title="Missing Values by Column",
            labels={'x': 'Count', 'y': 'Column'},
            color=missing.values,
            color_continuous_scale='Reds'
        )
        fig_missing.update_layout(showlegend=False, height=300)
    else:
        fig_missing = None
    
    # 2. Data types distribution
    dtype_counts = df.dtypes.value_counts()
    fig_dtypes = px.pie(
        values=dtype_counts.values,
        names=dtype_counts.index.astype(str),
        title="Column Data Types Distribution",
        hole=0.4
    )
    fig_dtypes.update_layout(height=300)
    
    # 3. Numeric columns distribution (first numeric column)
    numeric_cols = df.select_dtypes(include=['number']).columns
    if len(numeric_cols) > 0:
        first_num_col = numeric_cols[0]
        fig_dist = px.histogram(
            df,
            x=first_num_col,
            title=f"Distribution of {first_num_col}",
            nbins=30
        )
        fig_dist.update_layout(height=300)
    else:
        fig_dist = None
    
    return fig_missing, fig_dtypes, fig_dist

def load_file(uploaded_file):
    """Load CSV or Excel file"""
    try:
        file_extension = uploaded_file.name.split('.')[-1].lower()
        
        if file_extension == 'csv':
            df = pd.read_csv(uploaded_file)
        elif file_extension in ['xlsx', 'xls']:
            df = pd.read_excel(uploaded_file)
        else:
            st.error("Unsupported file format. Please upload CSV or Excel file.")
            return None
        
        return df
    except Exception as e:
        st.error(f"Error loading file: {str(e)}")
        return None

# Main App
uploaded_file = st.file_uploader(
    "📁 Choose a file", 
    type=['csv', 'xlsx', 'xls'],
    help="Upload CSV or Excel files (up to 200MB)"
)

if uploaded_file is not None:
    df = load_file(uploaded_file)
    
    if df is not None:
        # Success message
        st.success(f"✅ File loaded: **{uploaded_file.name}**")
        
        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📊 Rows", f"{len(df):,}")
        with col2:
            st.metric("📋 Columns", len(df.columns))
        with col3:
            missing_total = df.isnull().sum().sum()
            missing_pct = (missing_total / (len(df) * len(df.columns)) * 100)
            st.metric("❌ Missing Values", f"{missing_total:,}", f"{missing_pct:.1f}%")
        with col4:
            duplicates = df.duplicated().sum()
            st.metric("🔄 Duplicates", f"{duplicates:,}")
        
        # Tabs for different views
        tab1, tab2, tab3 = st.tabs(["📊 Data Preview", "📈 Visualizations", "🔍 Analysis & Cleaning"])
        
        with tab1:
            st.subheader("Data Preview")
            st.dataframe(df.head(20), use_container_width=True)
            
            # Column info
            with st.expander("📋 Column Information"):
                col_info = pd.DataFrame({
                    'Column': df.columns,
                    'Type': df.dtypes.values,
                    'Non-Null': df.count().values,
                    'Null': df.isnull().sum().values,
                    'Unique': df.nunique().values
                })
                st.dataframe(col_info, use_container_width=True)
        
        with tab2:
            st.subheader("Data Quality Visualizations")
            
            fig_missing, fig_dtypes, fig_dist = create_data_quality_viz(df)
            
            col1, col2 = st.columns(2)
            with col1:
                if fig_missing:
                    st.plotly_chart(fig_missing, use_container_width=True)
                else:
                    st.info("✅ No missing values found!")
                
                st.plotly_chart(fig_dtypes, use_container_width=True)
            
            with col2:
                if fig_dist:
                    st.plotly_chart(fig_dist, use_container_width=True)
                
                # Correlation heatmap for numeric columns
                numeric_df = df.select_dtypes(include=['number'])
                if len(numeric_df.columns) > 1:
                    corr = numeric_df.corr()
                    fig_corr = px.imshow(
                        corr,
                        title="Correlation Matrix",
                        color_continuous_scale='RdBu',
                        aspect='auto'
                    )
                    st.plotly_chart(fig_corr, use_container_width=True)
        
        with tab3:
            st.subheader("AI-Powered Analysis")
            
            if client is None:
                st.warning("⚠️ Please set your GROQ_API_KEY to use AI features")
                st.code("export GROQ_API_KEY='your-key-here'  # Mac/Linux\nset GROQ_API_KEY=your-key-here  # Windows")
            else:
                if st.button("🔍 Analyze Data Quality", type="primary", use_container_width=True):
                    with st.spinner("🤖 AI is analyzing your data..."):
                        sample = df.head(100)
                        analysis = analyze_data(sample)
                        
                        if analysis:
                            st.session_state['analysis'] = analysis
                
                if 'analysis' in st.session_state:
                    analysis = st.session_state['analysis']
                    
                    # Severity indicator
                    severity = analysis.get('severity', 'medium')
                    severity_color = {
                        'high': '🔴',
                        'medium': '🟡', 
                        'low': '🟢'
                    }
                    
                    st.info(f"{severity_color.get(severity, '🟡')} **Data Quality:** {analysis['summary']}")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("### ⚠️ Issues Found")
                        for i, issue in enumerate(analysis['issues'], 1):
                            st.warning(f"**{i}.** {issue}")
                    
                    with col2:
                        st.markdown("### 💡 Recommendations")
                        for i, rec in enumerate(analysis['recommendations'], 1):
                            st.info(f"**{i}.** {rec}")
                    
                    st.markdown("---")
                    
                    if st.button("🧹 Clean Data Now", type="primary", use_container_width=True):
                        with st.spinner("🤖 AI is cleaning your data... This may take a moment..."):
                            cleaned_csv = clean_data(df, analysis['issues'])
                            
                            if cleaned_csv:
                                try:
                                    st.session_state['cleaned_data'] = cleaned_csv
                                    cleaned_df = pd.read_csv(io.StringIO(cleaned_csv))
                                    st.session_state['cleaned_df'] = cleaned_df
                                    st.success("✅ Data cleaned successfully!")
                                    st.balloons()
                                except Exception as e:
                                    st.error(f"Error parsing cleaned data: {str(e)}")
                    
                    if 'cleaned_df' in st.session_state:
                        st.markdown("---")
                        st.subheader("✨ Cleaned Data")
                        
                        cleaned_df = st.session_state['cleaned_df']
                        
                        # Comparison metrics
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Rows", f"{len(cleaned_df):,}", 
                                     delta=int(len(cleaned_df) - len(df)),
                                     delta_color="normal")
                        with col2:
                            st.metric("Columns", len(cleaned_df.columns))
                        with col3:
                            new_missing = cleaned_df.isnull().sum().sum()
                            st.metric("Missing Values", f"{new_missing:,}",
                                     delta=-int(missing_total - new_missing),
                                     delta_color="inverse")
                        with col4:
                            new_duplicates = cleaned_df.duplicated().sum()
                            st.metric("Duplicates", f"{new_duplicates:,}",
                                     delta=-int(duplicates - new_duplicates),
                                     delta_color="inverse")
                        
                        st.dataframe(cleaned_df.head(20), use_container_width=True)
                        
                        # Download button
                        st.download_button(
                            label="📥 Download Cleaned Data (CSV)",
                            data=st.session_state['cleaned_data'],
                            file_name=f"cleaned_{uploaded_file.name.rsplit('.', 1)[0]}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )

else:
    # Welcome screen
    st.markdown("""
    ### 🚀 Welcome to AI Data Cleaning Assistant!
    
    This tool uses **Groq AI** (powered by LLaMA 3.3) to automatically clean and improve your datasets.
    
    #### What it does:
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **Analysis:**
        - ✅ Identifies missing values
        - ✅ Detects duplicates
        - ✅ Finds formatting issues
        - ✅ Spots data type problems
        """)
    
    with col2:
        st.markdown("""
        **Cleaning:**
        - 🧹 Removes duplicates
        - 🧹 Handles missing data
        - 🧹 Standardizes formats
        - 🧹 Fixes inconsistencies
        """)
    
    st.markdown("---")
    st.info("👆 **Get Started:** Upload a CSV or Excel file above!")
    
    if client is None:
        st.warning("""
        **⚠️ API Key Required**
        
        To use AI features, you need a free Groq API key:
        1. Visit https://console.groq.com
        2. Sign up for a free account
        3. Generate an API key
        4. Set it as environment variable: `GROQ_API_KEY`
        """)

# Sidebar
with st.sidebar:
    st.header("ℹ️ About This Tool")
    
    st.markdown("""
    ### What is Groq?
    
    **Groq** is a lightning-fast AI inference platform that runs LLMs like LLaMA at incredible speeds.
    
    **Why Groq?**
    - ⚡ Super fast responses
    - 💰 Completely FREE
    - 🎯 High quality results
    - 🔓 No credit card needed
    """)
    
    st.markdown("---")
    
    st.markdown("""
    ### 🛠️ Tech Stack
    - **Python** - Programming language
    - **Streamlit** - Web framework
    - **Pandas** - Data manipulation
    - **Plotly** - Visualizations
    - **Groq API** - AI brain (LLaMA 3.3)
    """)
    
    st.markdown("---")
    
    st.markdown("""
    ### 📚 Quick Setup
    ```bash
    # Install packages
    pip install streamlit pandas groq plotly openpyxl
    
    # Get free API key
    # Visit: console.groq.com
    
    # Set API key (Windows)
    set GROQ_API_KEY=your-key-here
    
    # Set API key (Mac/Linux)
    export GROQ_API_KEY=your-key-here
    
    # Run app
    streamlit run app.py
    ```
    """)
    
    if client is None:
        st.error("⚠️ API Key Missing")
        st.markdown("""
        Get your free API key:
        1. Visit console.groq.com
        2. Sign up (no credit card!)
        3. Generate API key
        4. Set environment variable
        """)
    else:
        st.success("✅ API Key Configured")