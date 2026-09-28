from fastapi import FastAPI
app=FastApi()
@app.get("/")
def hello():
    return{"message": "Hello, World"}

@app.get("/hello world")
def hello_world():
    return {"message": "안녕하세요", "from": "일과고"}