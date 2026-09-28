from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import os

from censor import find_blocked, mask
from database import get_conn, init_db
from meal import router as meal_router


# ── 관리자 ───────────────────────────────────────────────
# 관리자는 남의 포스트잇도 뗄 수 있다.
# 열쇠는 코드에 박아 두면 화면 소스만 봐도 들통나므로 파일/환경변수에서 읽는다.
# admin_key.txt 를 만들어 아무 문장이나 한 줄 적어 두면 그게 열쇠가 된다.
def _load_admin_key():
    key = os.environ.get("MEMO_ADMIN_KEY", "").strip()
    if key:
        return key
    try:
        with open("admin_key.txt", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


ADMIN_KEY = _load_admin_key()


def _is_admin(token):
    """관리자 열쇠가 맞는지 본다. 열쇠를 안 정해 뒀으면 아무도 관리자가 아니다."""
    return bool(ADMIN_KEY) and token == ADMIN_KEY


app = FastAPI(title="우리 학교 API")

init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(meal_router)


class MemoIn(BaseModel):
    title: str
    content: str
    # 브라우저가 만들어 보내는 "내 것" 표시. 이게 맞아야 뗄 수 있다
    owner_token: str | None = None


def _censor(title: str, content: str):
    """막을 말이 있으면 400 으로 돌려보내고, 가벼운 건 ** 로 덮어서 준다."""
    hits = find_blocked(title) + find_blocked(content)
    if hits:
        raise HTTPException(status_code=400, detail="그런 말은 붙일 수 없습니다")
    return mask(title), mask(content)


@app.post("/memos", status_code=201)
def create_memo(memo: MemoIn):
    title, content = _censor(memo.title, memo.content)
    now = datetime.now().isoformat()

    conn = get_conn()
    cursor = conn.execute(
        "INSERT INTO memos (title, content, created_at, owner_token) VALUES (?, ?, ?, ?)",
        (title, content, now, memo.owner_token),
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    return {
        "id": new_id,
        "title": title,
        "content": content,
        "created_at": now,
        "likes": 0,
    }


def _public(row):
    """화면에 내보낼 메모. owner_token 은 남한테 보이면 안 되니 뺀다."""
    memo = dict(row)
    memo.pop("owner_token", None)
    return memo


@app.get("/memos")
def read_memos(keyword: str = None):
    conn = get_conn()

    if keyword:
        rows = conn.execute(
            "SELECT * FROM memos WHERE title LIKE ? ORDER BY id DESC",
            (f"%{keyword}%",),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM memos ORDER BY id DESC"
        ).fetchall()

    conn.close()
    return [_public(row) for row in rows]


@app.get("/memos/{memo_id}")
def read_memo(memo_id: int):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM memos WHERE id = ?", (memo_id,)
    ).fetchone()
    conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="그런 메모 없습니다")

    return _public(row)


@app.post("/memos/{memo_id}/like")
def like_memo(memo_id: int):
    return _change_likes(memo_id, +1)


@app.delete("/memos/{memo_id}/like")
def unlike_memo(memo_id: int):
    return _change_likes(memo_id, -1)


def _change_likes(memo_id: int, amount: int):
    """좋아요를 amount 만큼 더한다. 0 밑으로는 안 내려가게 막는다."""
    conn = get_conn()
    cursor = conn.execute(
        "UPDATE memos SET likes = MAX(0, likes + ?) WHERE id = ?",
        (amount, memo_id),
    )
    conn.commit()

    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="그런 메모 없습니다")

    row = conn.execute(
        "SELECT likes FROM memos WHERE id = ?", (memo_id,)
    ).fetchone()
    conn.close()

    return {"id": memo_id, "likes": row["likes"]}


@app.put("/memos/{memo_id}")
def update_memo(memo_id: int, new_data: MemoIn):
    title, content = _censor(new_data.title, new_data.content)

    conn = get_conn()
    row = conn.execute(
        "SELECT owner_token FROM memos WHERE id = ?", (memo_id,)
    ).fetchone()

    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="그런 메모 없습니다")

    # 떼기와 같은 규칙: 내가 붙인 것만 고칠 수 있다
    # 관리자는 누구 것이든 고칠 수 있다
    if not _is_admin(new_data.owner_token) and (
        not row["owner_token"] or row["owner_token"] != new_data.owner_token
    ):
        conn.close()
        raise HTTPException(status_code=403, detail="내가 붙인 포스트잇만 고칠 수 있습니다")

    conn.execute(
        "UPDATE memos SET title = ?, content = ? WHERE id = ?",
        (title, content, memo_id),
    )
    conn.commit()
    conn.close()

    return {"id": memo_id, "title": title, "content": content}


@app.delete("/memos/{memo_id}")
def delete_memo(memo_id: int, owner_token: str = None):
    conn = get_conn()
    row = conn.execute(
        "SELECT owner_token FROM memos WHERE id = ?", (memo_id,)
    ).fetchone()

    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="그런 메모 없습니다")

    # 주인 표시가 없거나(옛날 메모) 토큰이 다르면 못 뗀다.
    # 화면에서 떼기 버튼을 숨기는 것만으로는 막을 수 없어서 서버에서 한 번 더 확인한다
    # 관리자는 누구 것이든 뗄 수 있다
    if not _is_admin(owner_token) and (
        not row["owner_token"] or row["owner_token"] != owner_token
    ):
        conn.close()
        raise HTTPException(status_code=403, detail="내가 붙인 포스트잇만 뗄 수 있습니다")

    conn.execute("DELETE FROM memos WHERE id = ?", (memo_id,))
    conn.commit()
    conn.close()

    return {"ok": True, "deleted_id": memo_id}


@app.get("/admin/check")
def admin_check(token: str = None):
    """내가 관리자인지 알려준다. 열쇠 자체는 돌려주지 않는다."""
    return {"admin": _is_admin(token)}


# 이 줄은 항상 맨 아래! 위의 주소들을 먼저 찾고, 없으면 static 을 내려준다
app.mount("/", StaticFiles(directory="static", html=True), name="static")
