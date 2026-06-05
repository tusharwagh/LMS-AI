import uvicorn

from lms.api.app import create_app

app = create_app()


def main() -> None:
    uvicorn.run(
        "lms.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        app_dir="src",
    )


if __name__ == "__main__":
    main()
