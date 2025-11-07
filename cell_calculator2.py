import streamlit as st
import math
from datetime import datetime
import gspread 
import json 
import base64 
from google.oauth2.service_account import Credentials 

# --- 1. 앱의 기본 설정 ---
st.set_page_config(page_title="세포 수 계산기 v27 (G-Sheets)", layout="wide")
st.title("🔬 간단한 세포 수 계산기 v27 (G-Sheets 연동)")
st.write("실험 값을 입력하면, 필요한 새 배지와 총 접시 수를 계산합니다.")
st.divider() 

# --- 2. 입력 섹션 (Sidebar) ---
# (v26과 동일)
st.sidebar.header("[1단계] 세포 계수 정보")
num_squares_counted = st.sidebar.number_input("1. 계수한 칸의 수", min_value=1, max_value=9, value=4, step=1)
live_cell_counts = [] 
dead_cell_counts = [] 
st.sidebar.write("2. 각 칸의 세포 수를 입력하세요:")
for i in range(int(num_squares_counted)):
    col1, col2 = st.sidebar.columns(2)
    live_count = col1.number_input(f"   칸 {i+1} (Live)", min_value=0, value=50, step=1, key=f"live_count_{i}")
    dead_count = col2.number_input(f"   칸 {i+1} (Dead)", min_value=0, value=0, step=1, key=f"dead_count_{i}")
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


# --- 시트 정보 (전역 변수) ---
SHEET_FILE_NAME = "Cell Culture Log" # ⬅️ (이름 확인!)
SHEET_TAB_NAME = "Log" # ⬅️ (탭 이름 확인!)


# ▼▼▼ [수정됨] v27: 계산 로직을 '함수'로 분리 ▼▼▼
def perform_calculation():
    try:
        if num_squares_counted <= 0:
            st.error("!오류: '계수한 칸의 수'는 0보다 커야 합니다.")
            return False
        
        # (계산 로직은 v26과 동일)
        total_live_cells_counted = sum(live_cell_counts)
        total_dead_cells_counted = sum(dead_cell_counts)
        total_all_cells_counted = total_live_cells_counted + total_dead_cells_counted
        avg_live_count = float(total_live_cells_counted) / float(num_squares_counted)
        if total_all_cells_counted > 0:
            viability = (float(total_live_cells_counted) / float(total_all_cells_counted)) * 100
        else:
            viability = 0.0 
        cells_per_ml = avg_live_count * dilution * 10000
        total_live_cells_in_tube = cells_per_ml * total_stock_vol

        if cells_per_ml == 0:
            st.error("!오류: 1단계에서 계산된 '살아있는' 세포 농도가 0입니다. 계산을 중단합니다.")
            return False

        required_volume = target_cells / cells_per_ml
        available_dishes = int(total_live_cells_in_tube // target_cells)

        if pipette_volume <= 0:
            st.error("!오류: '심을 부피'는 0보다 커야 합니다.")
            return False

        concentration_working = target_cells / pipette_volume
        
        if cells_per_ml < concentration_working:
            st.error(f"⚠️ [제조 불가] 경고!\n현탁액 농도({cells_per_ml:.2e})가 ...")
            return False
        
        total_working_volume = total_live_cells_in_tube / concentration_working
        media_to_add = total_working_volume - total_stock_vol
        total_dishes_final = math.floor(total_working_volume / pipette_volume)
        
        # (계산 성공 시) 결과값을 st.session_state에 저장
        st.session_state.results = {
            "cells_per_ml": cells_per_ml,
            "total_live_cells_in_tube": total_live_cells_in_tube,
            "total_stock_vol": total_stock_vol,
            "total_all_cells_counted": total_all_cells_counted,
            "total_live_cells_counted": total_live_cells_counted,
            "total_dead_cells_counted": total_dead_cells_counted,
            "viability": viability,
            "required_volume": required_volume,
            "available_dishes": available_dishes,
            "target_cells": target_cells,
            "pipette_volume": pipette_volume,
            "concentration_working": concentration_working,
            "total_working_volume": total_working_volume,
            "media_to_add": media_to_add,
            "total_dishes_final": total_dishes_final
        }
        return True # 계산 성공

    except Exception as e:
        st.error(f"계산 중 오류가 발생했습니다: {e}")
        return False

# --- 3. 계산 실행 버튼 ---
if st.sidebar.button("✨ 계산 실행하기 ✨", type="primary"):
    # 계산을 실행하고, 성공 여부를 'calculation_done'에 저장
    if perform_calculation():
        st.session_state.calculation_done = True
    else:
        st.session_state.calculation_done = False

# --- 4. 결과 및 일지 기록 (Session State 기반) ---
# (계산 버튼을 누르거나, 일지 저장 버튼을 눌러도 이 블록은 유지됨)
if st.session_state.get("calculation_done", False):
    
    # 세션에 저장된 결과값 불러오기
    results = st.session_state.results
    
    # --- 4a. 결과 출력 (v26과 동일) ---
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

    # --- 4b. 일지 기록 폼 (v26과 동일) ---
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
            operator_name = st.text_input(f"작업자 {i+1} 이름:", key=f"operator_name_{i}")
            operators_list.append(operator_name)
        st.write("---")
        notes = st.text_area("특이사항 (Notes):")
        
        # ▼▼▼ [수정됨] v27: '일지 저장' 버튼 로직 ▼▼▼
        submit_button = st.form_submit_button(label="일지 저장하기", type="primary")

        if submit_button:
            # (버튼이 눌리면, 이 블록 안에서만 인증/저장을 시도)
            try:
                # 1. Scopes 정의
                scope = [
                    'https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive'
                ]
                
                # 2. Secrets에서 Base64 통-문자열 로드 (v26 방식)
                base64_string = st.secrets["gcp_json_base64"]
                json_string = base64.b64decode(base64_string).decode("utf-8")
                creds_dict = json.loads(json_string) 
                
                # 3. 최신 인증 (v26 방식)
                creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
                client = gspread.authorize(creds)
                
                # 4. 시트 열기
                sh = client.open(SHEET_FILE_NAME)
                sheet = sh.worksheet(SHEET_TAB_NAME)
                
                # 5. 저장할 데이터 생성 (v26과 동일)
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
                
                # 6. 시트에 쓰기
                sheet.append_row(log_data_list)
                st.success(f"✅ 일지 저장 완료! (Cell: {cell_name}, P:{passage_num})")
                st.info(f"Google Sheet '{SHEET_TAB_NAME}' 탭에 데이터가 성공적으로 기록되었습니다.")
            
            # ▼▼▼ [수정됨] v27: 이제 이 에러 메시지가 정상적으로 보여야 합니다 ▼▼▼
            except KeyError:
                st.error("⚠️ Google API 인증 정보(Secrets)가 설정되지 않았습니다. 'gcp_json_base64' 키를 확인하세요.")
            except gspread.exceptions.SpreadsheetNotFound:
                st.error(f"⚠️ 시트 파일 '{SHEET_FILE_NAME}'을(를) 찾을 수 없습니다. (이름/봇 초대 확인)")
            except gspread.exceptions.WorksheetNotFound:
                st.error(f"⚠️ 파일 '{SHEET_FILE_NAME}'에서 '{SHEET_TAB_NAME}' 탭을 찾을 수 없습니다! (탭 이름 확인)")
            except Exception as e:
                st.error(f"Google Sheets 연동 실패: {e}")
                st.warning("Secrets 설정, API 권한, 봇 초대, 파일/탭 이름을 다시 확인하세요.")
            # ▲▲▲ [수정됨] v27 끝 ▲▲▲

else:
    # (앱의 초기 화면)
    st.info("왼쪽 사이드바에서 값을 입력하고 '계산 실행하기' 버튼을 눌러주세요.")


