import httpx
from datetime import datetime
from fastapi import APIRouter, HTTPException


router = APIRouter()


NEIS_KEY = "6b68aa6e36854bb0aa8b8a030ec58485"
BASE_URL = "https://open.neis.go.kr/hub/mealServiceDietInfo"


OFFICE_CODE = "C10"        # 부산광역시교육청
SCHOOL_CODE = "7150532"    # 각자 학교 코드




@router.get("/meal")
def get_meal(date: str = None):
    if date is None:
        date = datetime.now().strftime("%Y%m%d")


    params = {
        "KEY": NEIS_KEY,
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": OFFICE_CODE,
        "SD_SCHUL_CODE": SCHOOL_CODE,
        "MLSV_YMD": date,
    }


    res = httpx.get(BASE_URL, params=params, timeout=10)
    data = res.json()


    if "mealServiceDietInfo" not in data:
        raise HTTPException(status_code=404, detail="급식 정보가 없습니다")


    rows = data["mealServiceDietInfo"][1]["row"]


    result = []
    for row in rows:
        menu_text = row["DDISH_NM"]
        menu_list = [m.strip() for m in menu_text.split("<br/>")]
        result.append({
            "date": row["MLSV_YMD"],
            "type": row["MMEAL_SC_NM"],   # 조식/중식/석식
            "menu": menu_list,
            "calorie": row.get("CAL_INFO"),
        })


    return result