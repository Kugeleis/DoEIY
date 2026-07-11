from fastapi import FastAPI

app = FastAPI(title="DoEIY - Design of Experiments")


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Hello from DoEIY FastAPI rewrite!"}
