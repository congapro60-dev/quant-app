"""Chạy test Firestore Rules trên emulator thật.

Vì sao cần công cụ này: emulator Firestore chạy trên Java và KHÔNG đọc được
``firestore.rules`` khi đường dẫn có dấu tiếng Việt (repo thật nằm trong
"phần mềm phân tích thị trường tài chính"). Khi đó emulator chết ngay lúc khởi
động; còn chạy pytest thường thì 3–4 test Rules tự bỏ qua, nên bộ test xanh
không chứng minh Rules đúng.

Công cụ chép ``firebase.json`` + ``firestore.rules`` sang thư mục tạm có đường
dẫn ASCII, khởi động emulator ở đó và chạy pytest trong repo.

Chạy: python tools/run_rules_tests.py   (cần Java và firebase CLI)
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _ascii_path(path: Path) -> str:
    """Đường dẫn ngắn 8.3 (ASCII) trên Windows; cmd ghi bằng UTF-8 đọc sai dấu."""

    if sys.platform != "win32":
        return str(path)
    import ctypes

    buffer = ctypes.create_unicode_buffer(1024)
    if ctypes.windll.kernel32.GetShortPathNameW(str(path), buffer, len(buffer)):
        return buffer.value
    return str(path)


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="quant_rules_", dir="C:/Users/Public"
                                 if sys.platform == "win32" else None))
    try:
        str(work).encode("ascii")
    except UnicodeEncodeError:
        raise SystemExit(f"Thư mục tạm {work} vẫn có ký tự không phải ASCII.")
    for name in ("firebase.json", "firestore.rules"):
        shutil.copy2(ROOT / name, work / name)
    runner = work / "run_tests.cmd"
    runner.write_text(
        "@echo off\n"
        f'cd /d "{_ascii_path(ROOT)}"\n'
        "set PYTHONIOENCODING=utf-8\n"
        f'"{sys.executable}" -m pytest -q -p no:cacheprovider -rs '
        "tests/test_firebase_rules_emulator.py\n",
        encoding="utf-8",
    )
    firebase = "firebase.cmd" if sys.platform == "win32" else "firebase"
    try:
        return subprocess.run(
            [firebase, "emulators:exec", "--only", "firestore,auth",
             "--project", "demo-quant-app", f'"{runner}"'],
            cwd=work,
        ).returncode
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
