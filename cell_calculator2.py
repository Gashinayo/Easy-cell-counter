import streamlit as st
import math
from datetime import datetime
import gspread 
import json 
import base64 
from google.oauth2.service_account import Credentials 
import pandas as pd # ⬅️ [신규] Pandas 라이브러리

# --- 1. 앱의 기본 설정 ---
st.set_page_config(page_title="세포 수 계산기 v28 (로그 조회)", layout="wide")
st.title("🔬 간단한 세포 수 계산기 v28")
st.write("계산기 탭에서 일지를 기록하고, 로그 조회 탭에서 데이터를 확인하세요.")

# --- 2. Google Sheets 인증 및 데이터 로드 (v28 핵심) ---

# --- 시트 정보 (전역 변수) ---
# ❗️❗️❗️ 이 부분은 연구원님의 시트 정보와 일치해야 합니다 ❗️❗️❗️
SHEET_FILE_NAME = "Cell Culture Log" # ⬅️ (v27에서 설정한 파일 이름)
SHEET_TAB_NAME = "Log"               # ⬅️ (v27에서 설정한 탭 이름)

# (1) 인증된 '클라이언트' 생성 (10분간 캐시)
@st.cache_resource(ttl=600)
def get_gspread_client():
    try:
        scope = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        # v26 방식 (Base64)으로 Secrets 로드
        base64_string = st.secrets["gcp_json_base64"]
        json_string = base64.b64decode(base64_string).decode("utf-8")
        creds_dict = json.loads(json_string) 
        
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        return client, None
    except Exception as e:
        return None, f"Google 인증 실패: {e}"

# (2) 데이터 로드 (1분간 캐시)
@st.cache_data(ttl=60)
def load_data(_client): # _client 인자는 캐시를 트리거하기 위해 받음
    try:
        sh = _client.open(SHEET_FILE_NAME)
        sheet = sh.worksheet(SHEET_TAB_NAME)
        data = sheet.get_all_records() # 데이터를 딕셔너리 리스트로 가져옴
        df = pd.DataFrame(data) # Pandas DataFrame으로 변환
        return df, None
    except Exception as e:
        return pd.DataFrame(), f"Google Sheets 데이터 로드 실패: {e}"

# --- 3. 앱 실행 ---

# (A) 클라이언트 인증
client, auth_error_msg = get_gspread_client()

if auth_error_msg:
    st.error(auth_error_msg)
    st.warning("Secrets 설정, API 권한, 봇 초대, 파일/탭 이름을 다시 확인하세요.")
    st.stop() # 인증 실패 시 앱 중지

# (B) 탭 생성
tab1, tab2 = st.tabs(["🔬 계산기", "📊 로그 조회"])


# --- 4. 탭 1: 계산기 (v27 코드 이동) ---
with tab1:
    # (v27의 사이드바 코드는 그대로 사용)
    st.sidebar.header("[1단계] 세포 계수 정보")
    num_squares_counted = st.sidebar.number_input("1. 계수한 칸의 수", min_value=1, max_value=9, value=4, step=1)
    live_cell_counts = [] 
    dead_cell_counts = [] 
    st.sidebar.write("2. 각 칸의 세포 수를 입력하세요:")
    for i in range(int(num_squares_counted)):
        col1, col2 = st.sidebar.columns(2)
        live_count = col1.number_input(f"   칸 {i+1} (Live)", min_value=0, value=50, step=1, key=f"calc_live_count_{i}")
        dead_count = col2.number_input(f"   칸 {i+1} (Dead)", min_value=0, value=0, step=1, key=f"calc_dead_count_{i}")
        live_cell_counts.append(live_count)
        dead_cell_counts.append(dead_count)
    dilution = st.sidebar.number_input("3. 카운팅 시 희석 배수", min_value=1.0, value=2.0, step=0.1)
    total_stock_vol = st.sidebar.number_input("4. 세포 현탁액 총 부피 (mL)", min_value=0.0, value=5.0, step=0.1)
    st.sidebar.header("[2단계] 목표 조건 입력") 
    default_target_cells = 5.0e5 
    use_default = st.sidebar.radio(f"5. 목표 세포 수 (기본값: {default_target_cells:.2e}개)", ("기본값 사용", "직접 입력"), index=0)
    if use_default == "직접 입력":
        target_cells = st.sidebar.number_input("   -> 원하는 총 세포 수를 입력하세요", min_value=0.0, value=1000000.0, step=1000.0, format="%.0f")
    else:
        target_cells = default_target_cells
    st.sidebar.header("[3단계] 분주용 현탁액 조건 입력") 
    pipette_volume = st.sidebar.number_input("6. 세포를 심을 부피 (mL)", min_value=0.1, value=2.0, step=0.1)
    st.sidebar.header("[4단계] 일지 정보 입력")
    num_operators = st.sidebar.number_input("총 작업자 수:", min_value=1, value=1, step=1)
    
    # (v27의 계산 함수)
    def perform_calculation():
        try:
            if num_squares_counted <= 0: st.error("!오류: '계수한 칸의 수'는 0보다 커야 합니다."); return False
            total_live_cells_counted = sum(live_cell_counts)
            total_dead_cells_counted = sum(dead_cell_counts)
            total_all_cells_counted = total_live_cells_counted + total_dead_cells_counted
            avg_live_count = float(total_live_cells_counted) / float(num_squares_counted)
            if total_all_cells_counted > 0: viability = (float(total_live_cells_counted) / float(total_all_cells_counted)) * 100
            else: viability = 0.0 
            cells_per_ml = avg_live_count * dilution * 10000
            total_live_cells_in_tube = cells_per_ml * total_stock_vol
            if cells_per_ml == 0: st.error("!오류: 1단계에서 계산된 '살아있는' 세포 농도가 0입니다."); return False
            required_volume = target_cells / cells_per_ml
            available_dishes = int(total_live_cells_in_tube // target_cells)
            if pipette_volume <= 0: st.error("!오류: '심을 부피'는 0보다 커야 합니다."); return False
            concentration_working = target_cells / pipette_volume
            if cells_per_ml < concentration_working: st.error(f"⚠️ [제조 불가] 경고! 현탁액 농도({cells_per_ml:.2e})가 ..."); return False
            total_working_volume = total_live_cells_in_tube / concentration_working
            media_to_add = total_working_volume - total_stock_vol
            total_dishes_final = math.floor(total_working_volume / pipette_volume)
            
            # (계산 성공 시) 결과값을 st.session_state에 저장
            st.session_state.results = {
                "cells_per_ml": cells_per_ml, "total_live_cells_in_tube": total_live_cells_in_tube,
                "total_stock_vol": total_stock_vol, "total_all_cells_counted": total_all_cells_counted,
                "total_live_cells_counted": total_live_cells_counted, "total_dead_cells_counted": total_dead_cells_counted,
                "viability": viability, "required_volume": required_volume, "available_dishes": available_dishes,
                "target_cells": target_cells, "pipette_volume": pipette_volume, "concentration_working": concentration_working,
                "total_working_volume": total_working_volume, "media_to_add": media_to_add,
                "total_dishes_final": total_dishes_final
            }
            return True # 계산 성공
        except Exception as e:
            st.error(f"계산 중 오류가 발생했습니다: {e}"); return False

    # (v27의 계산 버튼 로직)
    if st.sidebar.button("✨ 계산 실행하기 ✨", type="primary"):
        if perform_calculation():
            st.session_state.calculation_done = True
        else:
            st.session_state.calculation_done = False
            if "results" in st.session_state: del st.session_state.results

    # (v27의 결과 및 일지 기록 폼)
    if st.session_state.get("calculation_done", False) and "results" in st.session_state:
        results = st.session_state.results
        
        st.header("🔬 계산 결과")
        st.subheader("[1] 현재 세포 상태")
        col1, col2, col3 = st.columns(3)
        col1.metric("세포 현탁액 (Live) 농도", f"{results['cells_per_ml']:.2e} cells/mL")
        col2.metric("보유한 총 (Live) 세포 수", f"{results['total_live_cells_in_tube']:.2e} 개")
        col3.metric("보유한 현탁액 총 부피", f"{results['total_stock_vol']:.2f} mL")
        st.info(f"**세포 생존률 분석 (Counted)**\n\n- **총 세포 수:** {results['total_all_cells_counted']} 개\n- **살아있는 세포 수:** {results['total_live_cells_counted']} 개\n- **죽은 세포 수:** {results['total_dead_cells_counted']} 개\n- **세포 생존률 (Viability):** {results['viability']:.2f} %", icon="🔬")
        st.divider()
        st.subheader(f"[2] 현탁액 기준 ({results['target_cells']:.2e}개/접시)")
        col1, col2 = st.columns(2)
        col1.metric("'접시 1개' 필요 현탁액 부피", f"{results['required_volume']:.3f} mL")
        col2.metric("'총 준비 가능 배양접시 수'", f"{results['available_dishes']} 개")
        st.divider()
        st.subheader("[3] 자동 분주용 현탁액 제조 (현탁액 모두 사용)")
        st.success("✅ **[분주용 현탁액 제조법]**")
        recipe_text = f"""
1. '세포 현탁액' {results['total_stock_vol']:.3f} mL (전체)에
2. '새 배지' {results['media_to_add']:.3f} mL를 더합니다.
------------------------------------------------
   총 {results['total_working_volume']:.3f} mL의 '분주용 현탁액'이 완성됩니다.
   (분주용 현탁액 농도: {results['concentration_working']:.2e} cells/mL)
        """
        st.code(recipe_text, language="text")
        st.success(f"➡️ **이 분주용 현탁액을 {results['pipette_volume']:.1f} mL씩 분주하면, 총 {results['total_dishes_final']}개의 배양접시를 만들 수 있습니다.**")

        st.divider()
        st.subheader("✍️ 이 작업을 배양 일지에 기록합니다")

        with st.form(key="log_form"):
            st.write("**일지 정보 입력**") 
            cell_name = st.text_input("세포 이름 (Cell Line ID):")
            passage_num = st.number_input("계대 배수 (Passage No.):", min_value=0, step=1)
            st.write("---") 
            operators_list = [] 
            st.write(f"**작업자 (총 {int(num_operators)}명) 정보**")
            for i in range(int(num_operators)):
                operator_name = st.text_input(f"작업자 {i+1} 이름:", key=f"form_operator_name_{i}")
                operators_list.append(operator_name)
            st.write("---")
            notes = st.text_area("특이사항 (Notes):")
            
            submit_button = st.form_submit_button(label="일지 저장하기", type="primary")

            if submit_button:
                try:
                    # (글로벌 client 사용)
                    sh = client.open(SHEET_FILE_NAME)
                    sheet = sh.worksheet(SHEET_TAB_NAME)
                    
                    log_data_list = [
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        cell_name, int(passage_num),
                        ", ".join(operators_list), 
                        notes, f"{results['viability']:.2f}",
                        int(results['total_live_cells_counted']), int(results['total_dead_cells_counted']),
                        f"{results['cells_per_ml']:.2e}", f"{results['total_live_cells_in_tube']:.2e}",
                        float(results['total_stock_vol']), f"{results['target_cells']:.2e}",
                        float(results['pipette_volume']), f"{results['media_to_add']:.3f}",
                        f"{results['total_working_volume']:.3f}", int(results['total_dishes_final'])
                    ]
                    
                    sheet.append_row(log_data_list)
                    st.success(f"✅ 일지 저장 완료! (Cell: {cell_name}, P:{passage_num})")
                    st.info("로그 조회 탭을 확인하세요 (새로고침 필요).")
                    
                    # (캐시 클리어 및 상태 초기화)
                    st.cache_data.clear() 
                    st.cache_resource.clear() # 인증 캐시도 클리어 (필수는 아님)
                    st.session_state.calculation_done = False
                    del st.session_state.results
                
                except Exception as e:
                    st.error(f"Google Sheet 저장 실패: {e}")
    else:
        st.info("왼쪽 사이드바에서 값을 입력하고 '계산 실행하기' 버튼을 눌러주세요.")


# --- 5. 탭 2: 로그 조회 (신규) ---
with tab2:
    st.header("📊 배양 일지 로그 조회")
    
    # (B) 데이터 로드 (위에서 이미 로드됨)
    df, data_error_msg = load_data(client) # 캐시된 데이터 사용

    # (C) 새로고침 버튼
    if st.button("새로고침 (Refresh Data)"):
        st.cache_data.clear() # 데이터 캐시 지우기
        st.cache_resource.clear() # 인증 캐시 지우기
        st.rerun() # 앱 재실행

    if data_error_msg:
        st.error(data_error_msg)
    elif df.empty:
        st.warning("아직 저장된 로그가 없습니다. '계산기' 탭에서 일지를 저장하세요.")
    else:
        # --- (D) 데이터 전처리 ---
        df_display = df.copy()
        try:
            # 시트에 데이터가 없어도 오류 나지 않도록
            if 'Timestamp' in df_display.columns:
                df_display['Timestamp'] = pd.to_datetime(df_display['Timestamp'])
            if 'Viability_Percent' in df_display.columns:
                df_display['Viability_Percent'] = pd.to_numeric(df_display['Viability_Percent'], errors='coerce')
            if 'Passage_No' in df_display.columns:
                df_display['Passage_No'] = pd.to_numeric(df_display['Passage_No'], errors='coerce')
        except Exception as e:
            st.warning(f"데이터 타입 변환 중 오류: {e} (일부 필터가 작동하지 않을 수 있습니다)")

        # --- (E) 필터 ---
        st.subheader("필터")
        
        # 1. 세포 이름 필터
        if 'Cell_Name' in df_display.columns:
            all_cell_names = df_display['Cell_Name'].dropna().unique()
            selected_cells = st.multiselect(
                "세포 이름 (Cell Name) 필터:",
                options=all_cell_names,
                default=list(all_cell_names) # 기본값: 모두 선택
            )
        else:
            st.info("'Cell_Name' 컬럼이 시트에 없습니다. (헤더 확인)")
            selected_cells = []

        # 2. 날짜 범위 필터
        if 'Timestamp' in df_display.columns and not df_display['Timestamp'].isnull().all():
            min_date = df_display['Timestamp'].min().date()
            max_date = df_display['Timestamp'].max().date()
            selected_date_range = st.date_input(
                "날짜 범위 (Date Range) 필터:",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
                format="YYYY-MM-DD"
            )
        else:
            st.info("'Timestamp' 컬럼이 없거나 비어있습니다.")
            selected_date_range = None

        # --- (F) 필터 로직 ---
        df_filtered = df_display.copy()
        if 'Cell_Name' in df_filtered.columns and selected_cells:
            df_filtered = df_filtered[df_filtered['Cell_Name'].isin(selected_cells)]
        
        if 'Timestamp' in df_filtered.columns and selected_date_range and len(selected_date_range) == 2:
            start_date = pd.to_datetime(selected_date_range[0])
            end_date = pd.to_datetime(selected_date_range[1]).replace(hour=23, minute=59, second=59)
            df_filtered = df_filtered[
                (df_filtered['Timestamp'] >= start_date) & 
                (df_filtered['Timestamp'] <= end_date)
            ]

        # --- (G) 데이터 표시 ---
        st.subheader(f"필터링된 로그 ({len(df_filtered)} / {len(df_display)} 건)")
        # (v27에서 저장한 순서대로 컬럼을 재정렬하여 보여주면 깔끔함)
        columns_order = [
            "Timestamp", "Cell_Name", "Passage_No", "Operators", "Viability_Percent", 
            "Total_Dishes_Made", "Counted_Total_Live", "Counted_Total_Dead", 
            "Stock_Concentration_cells_ml", "Total_Live_Cells_in_Tube", "Stock_Volume_ml",
            "Target_Cells_per_Dish", "Seeding_Volume_per_Dish_ml", 
            "Media_to_Add_ml", "Total_Final_Volume_ml", "Notes"
        ]
        # 시트에 있는 컬럼만 골라서 순서 정렬
        display_cols = [col for col in columns_order if col in df_filtered.columns]
        st.dataframe(df_filtered[display_cols])
        
        st.divider()

        # --- (H) 시각화 ---
        st.subheader("Viability (생존률) 추이")
        if (not df_filtered.empty and 
            'Viability_Percent' in df_filtered.columns and 
            'Timestamp' in df_filtered.columns and 
            'Cell_Name' in df_filtered.columns):
            
            try:
                # (Viability가 숫자가 아닌 경우 제외)
                chart_df = df_filtered.dropna(subset=['Viability_Percent', 'Timestamp', 'Cell_Name'])
                
                chart_data = chart_df.pivot_table(
                    index='Timestamp', 
                    columns='Cell_Name', 
                    values='Viability_Percent',
                    aggfunc='mean' # 같은 날짜/세포가 여러 개일 경우 평균
                )
                st.line_chart(chart_data)
            except Exception as e:
                st.warning(f"차트 생성 중 오류: {e}")
                st.info("데이터가 차트 생성에 적합한지 확인하세요 (예: Timestamp, Viability_Percent).")
        else:
            st.info("차트를 그릴 데이터가 부족합니다. (Timestamp, Cell_Name, Viability_Percent 컬럼 필요)")
