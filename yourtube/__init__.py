import uvicorn

__version__ = "1.0.0"


def main():
    uvicorn.run("yourtube.app:app", host="127.0.0.1", port=8866)


if __name__ == "__main__":
    main()
