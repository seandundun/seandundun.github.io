import os
import json
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

# ============================================================
# 基础配置（请修改下面两项后再启动）
# ============================================================
# 密钥：随便写一长串字母数字混合的随机字符串，不要泄露
SECRET_KEY = "请改成你自己的一长串随机字符串，比如abc123xyz789混合"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7  # 登录有效期7天

# 管理员账号密码：密码是bcrypt哈希值，不是明文
# 生成方法：运行 python -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt']).hash('你的密码'))"
ADMIN_USERS = {
    "admin": {
        "username": "admin",
        "hashed_password": "$2b$12$xjJGyzTkafRJTxZSw6HstetBj1zi/0eJI2HalLsoAaL36gIRo1F3G"
    }
}

# 数据文件目录（保持默认即可）
DATA_DIR = "./data"
BOOK_JSON_PATH = os.path.join(DATA_DIR, "book.json")
CHAPTERS_DIR = os.path.join(DATA_DIR, "chapters")
ACCUMULATION_JSON_PATH = os.path.join(DATA_DIR, "accumulation.json")

# 确保目录和基础文件存在
os.makedirs(CHAPTERS_DIR, exist_ok=True)
if not os.path.exists(BOOK_JSON_PATH):
    default_book = {
        "title": "你的小说书名",
        "author": "作者名",
        "cover": "./assets/cover.jpg",
        "description": "小说简介",
        "chapters": [{"id": 1, "title": "第一章 初入山林"}]
    }
    with open(BOOK_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(default_book, f, ensure_ascii=False, indent=2)
if not os.path.exists(os.path.join(CHAPTERS_DIR, "1.json")):
    default_chapter = {
        "title": "第一章 初入山林",
        "content": [{"type": "text", "text": "这是第一章的正文内容。"}]
    }
    with open(os.path.join(CHAPTERS_DIR, "1.json"), "w", encoding="utf-8") as f:
        json.dump(default_chapter, f, ensure_ascii=False, indent=2)
if not os.path.exists(ACCUMULATION_JSON_PATH):
    with open(ACCUMULATION_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump({"items": []}, f, ensure_ascii=False, indent=2)

# ============================================================
# 鉴权工具
# ============================================================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/admin/login")

app = FastAPI()

# 跨域配置（本地开发用，上线可收紧）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """生成密码哈希，用于填入上面的配置"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=7)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的登录凭证",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None or username not in ADMIN_USERS:
            raise credentials_exception
        return ADMIN_USERS[username]
    except JWTError:
        raise credentials_exception

# ============================================================
# 数据读写工具函数
# ============================================================
# --- 小说相关 ---
def read_book_data():
    with open(BOOK_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def write_book_data(data):
    with open(BOOK_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def read_chapter(chapter_id: int):
    path = os.path.join(CHAPTERS_DIR, f"{chapter_id}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="章节不存在")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_chapter(chapter_id: int, data):
    path = os.path.join(CHAPTERS_DIR, f"{chapter_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def delete_chapter_file(chapter_id: int):
    path = os.path.join(CHAPTERS_DIR, f"{chapter_id}.json")
    if os.path.exists(path):
        os.remove(path)

# --- 语文积累相关 ---
def read_accumulation():
    with open(ACCUMULATION_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def write_accumulation(data):
    with open(ACCUMULATION_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ============================================================
# 请求体模型
# ============================================================
class BookUpdate(BaseModel):
    title: str
    author: str
    cover: str
    description: str
    chapters: list

class ChapterUpdate(BaseModel):
    title: str
    content: list

class AccumulationItem(BaseModel):
    id: Optional[int] = None
    content: str
    source: str
    author: str
    source_url: str = ""
    tags: list[str]
    date: str

# ============================================================
# 公开接口（前台页面调用，无需登录）
# ============================================================
# --- 小说 ---
@app.get("/api/book")
def get_book():
    """获取书籍信息和章节列表"""
    return read_book_data()

@app.get("/api/chapter/{chapter_id}")
def get_chapter(chapter_id: int):
    """获取单章内容"""
    return read_chapter(chapter_id)

# --- 语文积累 ---
@app.get("/api/accumulation")
def get_accumulation(tag: str = None):
    """获取语文积累列表，可按标签筛选"""
    data = read_accumulation()
    items = data["items"]
    if tag:
        items = [item for item in items if tag in item.get("tags", [])]
    # 按日期倒序排列
    items.sort(key=lambda x: x.get("date", ""), reverse=True)
    return {"items": items}

@app.get("/api/accumulation/tags")
def get_accumulation_tags():
    """获取所有标签列表"""
    data = read_accumulation()
    tags = set()
    for item in data["items"]:
        for t in item.get("tags", []):
            tags.add(t)
    return {"tags": sorted(list(tags))}

# ============================================================
# 管理员接口（需要登录鉴权）
# ============================================================
# --- 登录 ---
@app.post("/api/admin/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """管理员登录，返回访问令牌"""
    user = ADMIN_USERS.get(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# --- 小说管理 ---
@app.put("/api/admin/book")
def update_book(book_data: BookUpdate, current_user = Depends(get_current_user)):
    """更新书籍基础信息和章节列表"""
    write_book_data(book_data.dict())
    return {"status": "success"}

# @app.put("/api/admin/chapter/{chapter_id}")
# def update_chapter(chapter_id: int, chapter_data: ChapterUpdate, current_user = Depends(get_current_user)):
#     """更新单章内容"""
#     write_chapter(chapter_id, chapter_data.dict())
#     return {"status": "success"}

@app.put("/api/admin/chapter/{chapter_id}")
def update_chapter(chapter_id: int, chapter_data: ChapterUpdate, current_user = Depends(get_current_user)):
    """更新单章内容，并同步更新 book.json 中的章节标题"""
    # 1. 写入章节内容文件
    write_chapter(chapter_id, chapter_data.dict())
    
    # 2. 同步更新 book.json 里的章节标题
    book = read_book_data()
    for chap in book["chapters"]:
        if chap["id"] == chapter_id:
            chap["title"] = chapter_data.title
            break
    write_book_data(book)
    
    return {"status": "success"}


@app.post("/api/admin/chapter")
def add_chapter(current_user = Depends(get_current_user)):
    """新增章节，自动分配ID"""
    book = read_book_data()
    if book["chapters"]:
        new_id = max(c["id"] for c in book["chapters"]) + 1
    else:
        new_id = 1
    
    new_chapter = {"id": new_id, "title": f"第{new_id}章 新章节"}
    book["chapters"].append(new_chapter)
    write_book_data(book)
    
    default_content = {
        "title": new_chapter["title"],
        "content": [{"type": "text", "text": "在这里写正文..."}]
    }
    write_chapter(new_id, default_content)
    
    return {"id": new_id, "title": new_chapter["title"]}

@app.delete("/api/admin/chapter/{chapter_id}")
def delete_chapter(chapter_id: int, current_user = Depends(get_current_user)):
    """删除章节"""
    book = read_book_data()
    if len(book["chapters"]) <= 1:
        raise HTTPException(status_code=400, detail="至少保留一章")
    
    book["chapters"] = [c for c in book["chapters"] if c["id"] != chapter_id]
    write_book_data(book)
    delete_chapter_file(chapter_id)
    return {"status": "success"}

# --- 语文积累管理 ---
@app.post("/api/admin/accumulation")
def add_accumulation(item: AccumulationItem, current_user = Depends(get_current_user)):
    """新增一条摘抄"""
    data = read_accumulation()
    if data["items"]:
        new_id = max(i["id"] for i in data["items"]) + 1
    else:
        new_id = 1
    item_dict = item.dict()
    item_dict["id"] = new_id
    data["items"].append(item_dict)
    write_accumulation(data)
    return item_dict

@app.put("/api/admin/accumulation/{item_id}")
def update_accumulation(item_id: int, item: AccumulationItem, current_user = Depends(get_current_user)):
    """编辑一条摘抄"""
    data = read_accumulation()
    for idx, i in enumerate(data["items"]):
        if i["id"] == item_id:
            item_dict = item.dict()
            item_dict["id"] = item_id
            data["items"][idx] = item_dict
            write_accumulation(data)
            return {"status": "success"}
    raise HTTPException(status_code=404, detail="记录不存在")

@app.delete("/api/admin/accumulation/{item_id}")
def delete_accumulation(item_id: int, current_user = Depends(get_current_user)):
    """删除一条摘抄"""
    data = read_accumulation()
    data["items"] = [i for i in data["items"] if i["id"] != item_id]
    write_accumulation(data)
    return {"status": "success"}

# ============================================================
# 托管静态页面（前台+后台）
# 注意：必须放在所有接口后面，否则会覆盖接口路由
# ============================================================
app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
