from datetime import datetime


def info(message: str):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[INFO {now}] {message}")


def success(message: str):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[DONE {now}] {message}")


def error(message: str):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[ERROR {now}] {message}")