import os

os.environ["APP_VARIANT"] = "family"

from app import main


if __name__ == "__main__":
    main()
