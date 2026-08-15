"""Chụp ảnh giao diện thật bằng Playwright.

Chạy:
    .venv\\Scripts\\python tools\\capture_ui.py

Script tự khởi động Streamlit trên một cổng riêng, chụp cả hai lộ trình rồi
tắt tiến trình. Ảnh lưu vào thư mục ``anh_giao_dien``.
"""

from __future__ import annotations

import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "anh_giao_dien"
PORT = 8599
BASE = f"http://localhost:{PORT}"


def _port_open(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _wait_for_server(timeout: int = 90) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_open(PORT):
            return True
        time.sleep(1)
    return False


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Thiếu playwright. Cài: python -m pip install playwright"
              " && python -m playwright install chromium", file=sys.stderr)
        return 1

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    server = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py",
         "--server.headless=true", f"--server.port={PORT}",
         "--server.runOnSave=false"],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        if not _wait_for_server():
            print("Streamlit không khởi động kịp.", file=sys.stderr)
            return 1

        shots = 0
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1600, "height": 1100})

            page.goto(BASE, timeout=90_000)

            # Streamlit dựng dần; chờ đúng tiêu đề xuất hiện thay vì chờ mù.
            page.wait_for_selector("text=Quant App", timeout=90_000)
            page.wait_for_selector('[role="tab"]', timeout=90_000)
            page.wait_for_timeout(4000)

            page.screenshot(path=str(OUT_DIR / "01_man_hinh_dau.png"), full_page=True)
            shots += 1

            # Chụp từng khu vực theo đúng nhãn đang hiển thị.
            labels = page.get_by_role("tab").all_inner_texts()
            print("Khu vực thấy được:", labels[:6])

            for order, label in enumerate(labels[:5], start=2):
                safe = (label.lower()
                        .replace(" ", "_").replace("(", "").replace(")", ""))
                try:
                    page.get_by_role("tab", name=label, exact=True).first.click(timeout=10_000)
                    page.wait_for_timeout(3000)
                    page.screenshot(
                        path=str(OUT_DIR / f"{order:02d}_{safe}.png"), full_page=True
                    )
                    shots += 1
                except Exception as exc:  # noqa: BLE001 - chụp được bao nhiêu hay bấy nhiêu
                    print(f"Bỏ qua «{label}»: {str(exc)[:80]}")

            browser.close()

        print(f"Đã chụp {shots} ảnh vào: {OUT_DIR}")
        for path in sorted(OUT_DIR.glob("*.png")):
            print(f"  {path.name}  ({path.stat().st_size // 1024} KB)")
        return 0
    finally:
        server.terminate()
        try:
            server.wait(timeout=15)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    raise SystemExit(main())
