import streamlit as st
import math
from datetime import datetime
import gspread 
from oauth2client.service_account import ServiceAccountCredentials
import json 
import base64 # ⬅️ [신규] Base64 라이브러리 추가

# --- 1. 앱의 기본 설정 ---
st.set_page_config(page_title="세포 수 계산기 v22 (G-Sheets)", layout="wide")
st.title("🔬 간단한 세포 수 계산기 v22 (G-Sheets 연동)")
st.write("실험 값을 입력하면, 필요한 새 배지와 총 접시 수를 계산합니다.")

st.divider() # 구분선

# --- 2. 입력 섹션 (Sidebar) ---
# (v19~21과 동일하므로 생략)
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


# ▼▼▼ [수정됨] v22: 구글 시트 연동 (Base64 방식) ▼▼▼

# 1. 구글 시트 API 접근 권한 범위 설정
scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']

try:
    # (배포용 코드) Secrets에서 'gcp_json_base64'라는 '한 줄 텍스트'를 읽어옴
    base64_string = st.secrets["gcp_json_base64"]
    # Base64 텍스트를 디코딩하여 원래의 JSON 문자열로 복원
    json_string = base64.b64decode(base64_string).decode("utf-8")
    # 문자열을 딕셔너리로 변환
    creds_dict = json.loads(json_string) 
    # 딕셔너리를 사용해 인증
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

except KeyError:
    # (로컬 테스트용 코드)
    st.warning("로컬 테스트 모드로 실행 중입니다. ('gcreds.json' 파일 사용)")
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name('gcreds.json', scope)
    except FileNotFoundError:
        st.error("로컬 테스트를 위해 'gcreds.json' 파일을 폴더에 추가하세요.")
        st.stop()
    except Exception as e_local:
        st.error(f"로컬 'gcreds.json' 파일 로드 실패: {e_local}")
        st.stop()
except Exception as e_cloud:
    # (배포용 코드) Base64 디코딩/json.loads 실패 등 (Secrets 포맷이 잘못된 경우)
    st.error(f"Google API 인증 정보 로드 실패 (Secrets 포맷 확인): {e_cloud}")
    st.stop()

# 인증된 클라이언트 생성
client = gspread.authorize(creds)

# ❗️❗️❗️ 이 부분은 연구원님의 시트 제목으로 꼭 수정해주세요 ❗️❗️❗️
SHEET_FILE_NAME = "Cell Culture Log" 

try:
    sheet = client.open(SHEET_FILE_NAME).sheet1
except gspread.exceptions.SpreadsheetNotFound:
    st.error(f"시트 파일 '{SHEET_FILE_NAME}'을(를) 찾을 수 없습니다. (이름/봇 초대 확인)")
    st.stop()
except Exception as e:
    st.error(f"시트 파일 열기 실패: {e}")
    st.stop()

# ▲▲▲ [수정됨] v22: 구글 시트 설정 끝 ▲▲▲


# --- 3. 계산 실행 버튼 ---
if st.sidebar.button("✨ 계산 실행하기 ✨", type="primary"):

    # --- 계산 로직 ---
    # (v21과 동일하므로 생략...)
    try:
        if num_squares_counted <= 0:
            st.error("!오류: '계수한 칸의 수'는 0보다 커야 합니다.")
        else:
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
            else:
                required_volume = target_cells / cells_per_ml
                available_dishes = int(total_live_cells_in_tube // target_cells)

                # --- 4. 결과 출력 (메인 화면) ---
                # (v21과 동일하므로 생략...)
                st.header("🔬 계산 결과")
                st.subheader("[1] 현재 세포 상태")
                col1, col2, col3 = st.columns(3)
                col1.metric("세포 현탁액 (Live) 농도", f"{cells_per_ml:.2e} cells/mL")
                col2.metric("보유한 총 (Live) 세포 수", f"{total_live_cells_in_tube:.2e} 개")
                col3.metric("보유한 현탁액 총 부피", f"{total_stock_vol:.2f} mL")
                st.info(f"**세포 생존률 분석 (Counted)**\n\n- **총 세포 수:** {total_all_cells_counted} 개\n- **살아있는 세포 수:** {total_live_cells_counted} 개\n- **죽은 세포 수:** {total_dead_cells_counted} 개\n- **세포 생존률 (Viability):** {viability:.2f} %", icon="🔬")
                st.divider()
                st.subheader(f"[2] 현탁액 기준 ({target_cells:.2e}개/접시)")
                col1, col2 = st.columns(2)
                col1.metric("'접시 1개' 필요 현탁액 부피", f"{required_volume:.3f} mL")
                col2.metric("'총 준비 가능 배양접시 수'", f"{available_dishes} 개")
                st.divider()
                st.subheader("[3] 자동 분주용 현탁액 제조 (현탁액 모두 사용)")

                if pipette_volume <= 0:
                    st.error("!오류: '심을 부피'는 0보다 커야 합니다.")
                else:
                    concentration_working = target_cells / pipette_volume
                    
                    if cells_per_ml < concentration_working:
                        st.error(f"⚠️ [제조 불가] 경고!\n현탁액 농도({cells_per_ml:.2e})가 분주용 현탁액 목표 농도({concentration_working:.2e})보다 낮습니다.\n(목표 세포 수를 줄이거나, 주입 부피를 늘려주세요.)")
                    else:
                        total_working_volume = total_live_cells_in_tube / concentration_working
                        media_to_add = total_working_volume - total_stock_vol
                        total_dishes_final = math.floor(total_working_volume / pipette_volume)
                        
                        st.success("✅ **[분주용 현탁액 제조법]**")
                        recipe_text = f"""
1. '세포 현탁액' {total_stock_vol:.3f} mL (전체)에
2. '새 배지' {media_to_add:.3f} mL를 더합니다.
------------------------------------------------
   총 {total_working_volume:.3f} mL의 '분주용 현탁액'이 완성됩니다.
   (분주용 현탁액 농도: {concentration_working:.2e} cells/mL)
                        """
                        st.code(recipe_text, language="text")
                        st.success(f"➡️ **이 분주용 현탁액을 {pipette_volume:.1f} mL씩 분주하면, 총 {total_dishes_final}개의 배양접시를 만들 수 있습니다.**")

                        # --- 일지 기록 폼 ---
                        # (v21과 동일하므로 생략...)
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
                            submit_button = st.form_submit_button(label="일지 저장하기", type="primary")

                        if submit_button:
                            # --- 저장 로직 ---
                            # (v21과 동일하므로 생략...)
                            log_data_list = [
                                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                cell_name, int(passage_num),
                                ", ".join(operators_list), # 작업자 리스트를 텍스트 한 줄로 변환
                                notes, f"{viability:.2f}",
                                int(total_live_cells_counted), int(total_dead_cells_counted),
                                f"{cells_per_ml:.2e}", f"{total_live_cells_in_tube:.2e}",
                                float(total_stock_vol), f"{target_cells:.2e}",
                                float(pipette_volume), f"{media_to_add:.3f}",
                                f"{total_working_volume:.3f}", int(total_dishes_final)
                            ]
                            try:
                                sheet.append_row(log_data_list)
                                st.success(f"✅ 일지 저장 완료! (Cell: {cell_name}, P:{passage_num})")
                                st.info("Google Sheet에 데이터가 성공적으로 기록되었습니다.")
                            except Exception as e:
                                st.error(f"Google Sheet 저장 실패: {e}")
                                st.warning("아래 JSON 데이터를 수동으로 복사하세요:")
                                st.json(log_data_list) # 실패 시 데이터라도 보여줌

    except Exception as e:
        st.error(f"계산 중 오류가 발생했습니다: {e}")

else:
    st.info("왼쪽 사이드바에서 값을 입력하고 '계산 실행하기' 버튼을 눌러주세요.")
