import os

os.environ["APP_VARIANT"] = "public"

from app import main


if __name__ == "__main__":
    main()
