import os

os.environ["APP_VARIANT"] = "office"
os.environ.setdefault("STREAMLIT_SERVER_FILE_WATCHER_TYPE", "none")

from app import main


if __name__ == "__main__":
    main()
