import streamlit as st
import math

# --- 1. 앱의 기본 설정 ---
st.set_page_config(page_title="세포 수 계산기 v14", layout="wide")
st.title("🔬 간단한 세포 수 계산기 v14")
st.write("실험 값을 입력하면, 필요한 새 배지와 총 접시 수를 계산합니다.")

st.divider() # 구분선

# --- 2. 입력 섹션 (Sidebar) ---
st.sidebar.header("[1단계] 세포 계수 정보")

num_squares_counted = st.sidebar.number_input(
    "1. 계수한 칸의 수", 
    min_value=1, max_value=9, value=4, step=1
)

live_cell_counts = [] # 살아있는 세포 수를 저장할 리스트
dead_cell_counts = [] # 죽은 세포 수를 저장할 리스트
st.sidebar.write("2. 각 칸의 세포 수를 입력하세요:")

for i in range(int(num_squares_counted)):
    col1, col2 = st.sidebar.columns(2)
    
    # ▼▼▼ [수정] value=50, step=1 (정수), format 제거 ▼▼▼
    live_count = col1.number_input(
        f"   칸 {i+1} (Live)", 
        min_value=0, value=50, step=1,
        key=f"live_count_{i}" 
    )
    # ▼▼▼ [수정] value=0, step=1 (정수), format 제거 ▼▼▼
    dead_count = col2.number_input(
        f"   칸 {i+1} (Dead)", 
        min_value=0, value=0, step=1,
        key=f"dead_count_{i}" 
    )
    live_cell_counts.append(live_count)
    dead_cell_counts.append(dead_count)

dilution = st.sidebar.number_input(
    "3. 카운팅 시 희석 배수", 
    min_value=1.0, value=2.0, step=0.1
)

total_stock_vol = st.sidebar.number_input(
    "4. 세포 현탁액 총 부피 (mL)", 
    min_value=0.0, value=5.0, step=0.1
)


st.sidebar.header("[2단계] 목표 조건 입력") 
default_target_cells = 5.0e5 

use_default = st.sidebar.radio(
    f"5. 목표 세포 수 (기본값: {default_target_cells:.2e}개)",
    ("기본값 사용", "직접 입력"), 
    index=0 
)

if use_default == "직접 입력":
    target_cells = st.sidebar.number_input(
        "   -> 원하는 총 세포 수를 입력하세요", 
        min_value=0.0, value=1000000.0, step=1000.0, format="%.0f"
    )
else:
    target_cells = default_target_cells

st.sidebar.header("[3단계] 분주용 현탁액 조건 입력") 
pipette_volume = st.sidebar.number_input(
    "6. 세포를 심을 부피 (mL)", 
    min_value=0.1, value=2.0, step=0.1
)

# --- 3. 계산 실행 버튼 ---
if st.sidebar.button("✨ 계산 실행하기 ✨", type="primary"):

    # --- 계산 로직 ---
    try:
        if num_squares_counted <= 0:
            st.error("!오류: '계수한 칸의 수'는 0보다 커야 합니다.")
        else:
            total_live_cells_counted = sum(live_cell_counts)
            total_dead_cells_counted = sum(dead_cell_counts)
            total_all_cells_counted = total_live_cells_counted + total_dead_cells_counted

            # (정수로 입력받아도 계산은 float으로 안전하게 수행됩니다)
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
                st.header("🔬 계산 결과")
                
                st.subheader("[1] 현재 세포 상태")
                col1, col2, col3 = st.columns(3)
                col1.metric("세포 현탁액 (Live) 농도", f"{cells_per_ml:.2e} cells/mL")
                col2.metric("보유한 총 (Live) 세포 수", f"{total_live_cells_in_tube:.2e} 개")
                col3.metric("보유한 현탁액 총 부피", f"{total_stock_vol:.2f} mL")
                
                st.info(
                    f"**세포 생존률 분석 (Counted)**\n\n"
                    # ▼▼▼ [수정] 정수(int)로 표기되도록 .1f 제거 ▼▼▼
                    f"- **총 세포 수:** {total_all_cells_counted} 개\n"
                    f"- **살아있는 세포 수:** {total_live_cells_counted} 개\n"
                    f"- **죽은 세포 수:** {total_dead_cells_counted} 개\n"
                    f"- **세포 생존률 (Viability):** {viability:.2f} %",
                    icon="🔬"
                )
                
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
                        st.error(
                            f"⚠️ [제조 불가] 경고!\n"
                            f"현탁액 농도({cells_per_ml:.2e})가 분주용 현탁액 목표 농도({concentration_working:.2e})보다 낮습니다.\n"
                            f"(목표 세포 수를 줄이거나, 주입 부피를 늘려주세요.)"
                        )
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

    except Exception as e:
        st.error(f"계산 중 오류가 발생했습니다: {e}")

else:
    st.info("왼쪽 사이드바에서 값을 입력하고 '계산 실행하기' 버튼을 눌러주세요.")
    #streamlit run cell_calculator2.py