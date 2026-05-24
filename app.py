import streamlit as st
import pandas as pd
import numpy as np
from google import genai
from google.genai import types
from supabase import create_client, Client

# 0. 페이지 설정 및 디자인
st.set_page_config(
    page_title="노인 무임승차 시간 제한 정책 수립 시스템",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 1. 시크릿 및 클라이언트 초기화
@st.cache_resource
def init_clients():
    try:
        gemini_key = st.secrets["GEMINI_API_KEY"]
        supabase_url = st.secrets["SUPABASE_URL"]
        supabase_key = st.secrets["SUPABASE_KEY"]
        
        ai_client = genai.Client(api_key=gemini_key)
        supabase_client = create_client(supabase_url, supabase_key)
        return ai_client, supabase_client
    except Exception as e:
        st.error(f"시크릿 로드 또는 클라이언트 초기화 실패 (일부 기능이 제한될 수 있습니다): {e}")
        return None, None

ai_client, supabase_client = init_clients()

# 2. 데이터 자동 로드 로직 (로컬/서버 내의 CSV를 우선 탐색)
@st.cache_data
def load_data_auto(file_pointer, default_path):
    if file_pointer is not None:
        return pd.read_csv(file_pointer)
    try:
        return pd.read_csv(default_path)
    except FileNotFoundError:
        return None

st.sidebar.title("🛠️ 데이터 소스 관리")
st.sidebar.info("💡 CSV 파일이 자동으로 감지되어 즉시 작동합니다. 데이터 갱신 시에만 아래에 업로드하세요.")

uploaded_senior = st.sidebar.file_uploader("노인이용.csv 변경", type=["csv"])
uploaded_congestion = st.sidebar.file_uploader("시간별혼잡도.csv 변경", type=["csv"])
uploaded_infra = st.sidebar.file_uploader("역세권.csv 변경", type=["csv"])

df_senior = load_data_auto(uploaded_senior, "노인이용.csv")
df_congestion = load_data_auto(uploaded_congestion, "시간별혼잡도.csv")
df_infra = load_data_auto(uploaded_infra, "역세권.csv")

# 메인 타이틀 (노인 무임승차 시간 제한 정책 방향성 수립)
st.title("🚇 고령층 무임승차 시간 제한 정책 수립을 위한 교통 혼잡도 분석 시스템")
st.markdown("""
본 시스템은 지하철 재정 적자 해소 및 출퇴근 시간대 혼잡도 완화를 위해 **고령층 무임승차 제한 시간 대역을 과학적으로 도출**하는 것을 목적으로 합니다. 
역별 유동인구 패턴을 대화형 차트로 분석하여 가장 실효성 있는 요금 규제 타이밍을 제안합니다.
""")

if df_senior is None or df_congestion is None or df_infra is None:
    st.error("❌ 데이터를 불러올 수 없습니다. 레포지토리에 [노인이용.csv, 시간별혼잡도.csv, 역세권.csv] 파일이 존재하거나 사이드바에 업로드되었는지 확인해 주세요.")
    st.stop()

# --- 탭 구성 ---
tab1, tab2, tab3 = st.tabs([
    "⏱️ Tab 1: 역별 무임승차 제한 권고 시간 도출", 
    "🔍 Tab 2: 인프라 유형별 제한 정책 필터링", 
    "📈 Tab 3: 역세권 특성별 혼잡도 분석 및 AI 정책 리포트"
])

# 공통 시간축 정의
hours_common = [f"{i}시" for i in range(6, 25)]

# ==========================================
# Tab 1: 역별 무임승차 제한 권고 시간 도출 (한글 깨짐 해결)
# ==========================================
with tab1:
    st.header("⏱️ 고령층 유동인구 vs 전체 열차 혼잡도 격차 분석")
    st.caption("💡 대화형 라인 차트: 우측 상단의 확장 버튼을 누르거나 그래프 위에 마우스를 가져다대면 한글 깨짐 없이 깨끗하게 시간대별 수치(명, %)가 표출됩니다.")
    
    # 공통 역 목록 추출
    available_stations = sorted(list(set(df_senior['역명'].unique()) & set(df_congestion['출발역'].unique())))
    
    col1, col2 = st.columns([1, 3])
    with col1:
        selected_station = st.selectbox("🎯 분석 및 규제 적용 대상역 선택", available_stations)
    
    # 데이터 필터링 및 병합 연산
    stat_senior = df_senior[df_senior['역명'] == selected_station]
    stat_congest = df_congestion[df_congestion['출발역'] == selected_station]
    
    if not stat_senior.empty and not stat_congest.empty:
        # 노인 인구수 합계 산출
        senior_total = stat_senior[stat_senior['승하차'] == '승차'][hours_common].sum().values + \
                       stat_senior[stat_senior['승하차'] == '하차'][hours_common].sum().values
        # 해당 역의 시간대별 평균 열차 혼잡도 산출
        congest_mean = stat_congest[hours_common].mean().values
        
        # 🌟 한글 깨짐 방지를 위해 컬럼명과 인덱스를 완전 명시하여 DataFrame 생성 🌟
        chart_df = pd.DataFrame({
            "고령층 유동인구(명)": senior_total,
            "열차 혼잡도(%)": congest_mean
        }, index=hours_common)
        
        st.subheader(f"📊 [{selected_station}역] 시간대별 트렌드 지표 비교 (마우스 호버 지원)")
        
        # 내장 라인 차트로 안전하게 한글 표기 및 호버링 활성화
        st.line_chart(chart_df, height=380, use_container_width=True)
        
        # 정책 규제 조건 자동 분석 (열차 혼잡도 기준선 35% 이상인 타깃 추출)
        congest_threshold = 35.0  
        restrict_candidates = []
        
        for h in hours_common:
            c_val = chart_df.loc[h, "열차 혼잡도(%)"]
            s_val = chart_df.loc[h, "고령층 유동인구(명)"]
            if c_val >= congest_threshold:
                restrict_candidates.append(f"**{h}** (혼잡도: {c_val:.1f}%, 고령층: {int(s_val)}명)")
        
        if restrict_candidates:
            st.warning(f"🚨 **[{selected_station}역 무임승차 제한 권고 고지]**\n\n본 역은 아래 시간대에 일반 직장인 및 학생들의 출퇴근 혼잡과 고령층 이동 동선이 겹쳐 대형 안전사고 및 혼잡 지연 위험이 수반됩니다. **해당 피크 시간대 무임승차 혜택 일시 제한 및 일반 요금 부과 정책 도입**의 타깃 구역으로 권고합니다.\n\n" + " \n/ ".join(restrict_candidates))
        else:
            st.success("✅ 본 역은 출퇴근 시간대에도 전체 열차 혼잡도가 안정적이므로, 현행 교통 복지(무임승차) 제도를 유연하게 유지해도 안전합니다.")

# ==========================================
# Tab 2: 인프라 유형별 제한 정책 필터링
# ==========================================
with tab2:
    st.header("🔍 특정 유입 유발 시설별 규제 영향도 파악")
    st.caption("규제 예외 대상을 구별하기 위해 특정 인프라 키워드를 검색하고 고령층의 누적 이용 패턴을 확인합니다.")
    
    df_senior['총이용량'] = df_senior[hours_common].sum(axis=1)
    search_keyword = st.text_input("💡 규제 완화 혹은 예외 검토 시설 키워드 입력 (예: 공원, 병원, 복지관)", "병원")
    
    if search_keyword:
        filtered_infra = df_infra[df_infra['역주변'].str.contains(search_keyword, na=False, case=False)]
        unique_stations = filtered_infra['역명'].unique()
        
        senior_policy_sum = df_senior[df_senior['역명'].isin(unique_stations)].groupby('역명')['총이용량'].sum().reset_index()
        senior_policy_sum = senior_policy_sum.sort_values(by='총이용량', ascending=False)
        
        st.markdown(f"### 📑 '{search_keyword}' 인접 역사의 고령층 총이용량 정책 순위")
        
        col_f1, col_f2 = st.columns([2, 1])
        with col_f1:
            st.dataframe(senior_policy_sum.rename(columns={'총이용량': '고령층 총 유동량(명)'}), use_container_width=True, hide_index=True)
        with col_f2:
            st.info(f"""
            📌 **정책 가이드**
            - '{search_keyword}' 유관 역사는 서울 시내 총 **{len(unique_stations)}개** 지점입니다.
            - 의료나 생계형 인프라 인근 지역은 무임승차 전면 박탈보다는, **출근 피크 타임(07:30~09:00)만 집중 제한**하는 유연한 시간제 유료화 방안안 수립이 합당합니다.
            """)
            
            csv_data = senior_policy_sum.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 규제 검토 대상 리스트 다운로드 (CSV)",
                data=csv_data,
                file_name=f"무임승차_정책검토_{search_keyword}.csv",
                mime="text/csv"
            )

# ==========================================
# Tab 3: 역세권 특성별 혼잡도 분석 및 AI 리포트
# ==========================================
with tab3:
    st.header("📈 역세권 특성 분류별 혼잡 트렌드 및 AI 실효성 진단")
    st.caption("유형별 혼잡 한계점을 식별하고, Gemini 2.5 Flash 모델이 국회 및 지자체 제출용 입법 제안서를 즉각 요약 작성합니다.")
    
    col_b1, col_b2 = st.columns([1, 1])
    
    with col_b1:
        st.subheader("🏢 역세권 클러스터별 평균 혼잡도 시각화")
        
        def categorize_policy_zone(text):
            if any(k in str(text) for k in ['병원', '의원', '복지관', '실버']): return '의료복지 밀집지역 (선별 제한)'
            if any(k in str(text) for k in ['시장', '백화점', '마트']): return '상업 소비지역 (낮시간 유도)'
            if any(k in str(text) for k in ['학교', '대학', '초등']): return '학생 주거지역 (출퇴근 강한 제한)'
            return '일반 행정지역'
            
        df_infra['역세권유형'] = df_infra['역주변'].apply(categorize_policy_zone)
        station_zone_map = df_infra.groupby('역명')['역세권유형'].first().to_dict()
        
        df_congest_policy = df_congestion.copy()
        df_congest_policy['역세권유형'] = df_congest_policy['출발역'].map(station_zone_map).fillna('일반 행정지역')
        
        hours_full = [f"{i}시" for i in range(6, 25)]
        zone_profile = df_congest_policy.groupby('역세권유형')[hours_full].mean().T
        
        st.line_chart(zone_profile)
        st.caption("💡 각 곡선에 마우스를 대면 유형별 수치가 깔끔하게 팝업됩니다. 출퇴근 시간 혼잡 유발 구역의 우선 규제 순위를 도출하는 척도입니다.")
        
    with col_b2:
        st.subheader("🤖 Gemini 2.5 Flash 실시간 정책 분석 리포터")
        ai_policy_station = st.selectbox("🔮 의무 제한 시뮬레이션 역사 선택", available_stations, key="ai_policy_select")
        
        if st.button("⚖️ 무임승차 제한 실효성 AI 리포트 생성"):
            if ai_client is None:
                st.error("Gemini API Key 연동 상태를 확인해 주세요.")
            else:
                with st.spinner("AI가 해당 역의 혼잡 데이터를 기반으로 최적의 요금 규제 시간대를 연산 중입니다..."):
                    
                    target_infra_list = df_infra[df_infra['역명'] == ai_policy_station]['역주변'].tolist()[:6]
                    target_congest_dict = df_congestion[df_congestion['출발역'] == ai_policy_station][hours_common].mean().to_dict()
                    
                    prompt = f"""
                    대한민국 서울시 지하철의 고령층 무임승차 제도를 개편하려고 합니다. [{ai_policy_station}역]의 실제 데이터를 바탕으로 '무임승차 시간 제한 정책' 보고서를 작성해 주세요.
                    
                    - 역세권 환경 인프라: {', '.join(map(str, target_infra_list))}
                    - 시간대별 평균 열차 혼잡도: {target_congest_dict}
                    
                    위 데이터를 분석하고, Google Search 기능을 활용하여 현재 논의되고 있는 대한민국의 지하철 무임승차 연령 상향 및 시간제 제한(출퇴근 시간 제외) 트렌드를 참고하세요. 
                    이 역의 출퇴근 혼잡을 완화하기 위해 어떤 시간대에 무임승차를 제한해야 하는지, 그리고 반발을 줄이기 위한 대안은 무엇인지 **고령층 안전 대책 및 교통 복지 개선 방안에 대한 명확한 3줄 요약 리포트**로 작성해 주세요. 
                    전문적이고 객관적인 공문서 어조(~합니다)로 작성해 주세요.
                    """
                    
                    try:
                        response = ai_client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                system_instruction="너는 국토교통부와 서울시 지하철 공사의 교통 수요 관리 및 요금 정책을 설계하는 수석 행정관이자 데이터 과학자야.",
                                temperature=0.2,
                                tools=[types.Tool(google_search=types.GoogleSearch())]
                            )
                        )
                        
                        st.markdown("#### 📋 고령층 이용 제한 시간대 제안 및 대책 리포트")
                        st.info(response.text)
                        
                        if supabase_client:
                            try:
                                supabase_client.table('subway_policy_logs').insert({
                                    "station_name": ai_policy_station,
                                    "restricted_hours": "데이터 기반 출퇴근 피크 타임 제한 권고",
                                    "ai_policy_report": response.text
                                }).execute()
                            except Exception:
                                pass
                                
                    except Exception as e:
                        st.error(f"AI 정책 생성 중 에러가 발생했습니다: {e}")
