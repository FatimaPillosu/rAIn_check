"""Dev launcher: running `python run_dev.py` (rather than `python -m uvicorn ...`) makes
Python add this file's own directory to sys.path[0] regardless of the process's current
working directory, so `app.main` resolves correctly no matter where the launcher starts
the process from. (run.bat, for the packaged prototype, does the equivalent via a `cd`.)
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8501, reload=False)
