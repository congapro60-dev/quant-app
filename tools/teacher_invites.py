"""Chủ project tạo hoặc thu hồi mã mời giáo viên; dùng phiên gcloud, không xuất khoá quản trị.

Mỗi mã dùng được đúng một lần để đăng ký tài khoản giáo viên tự đăng ký. Mã ghi
ra tệp riêng NGOÀI repo công khai, không in ra màn hình.

Chạy:
    python tools/teacher_invites.py create --count 3 --note "GV trường X"
    python tools/teacher_invites.py revoke ABCDE-FGHIJ-KLMNO-PQRST
"""
import argparse
import datetime
import secrets
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import classroom_self as cself  # noqa: E402
import firebase_classroom as fc  # noqa: E402
from tools.provision_classroom import operator_token, write_private  # noqa: E402

_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
_BASE = (f"https://firestore.googleapis.com/v1/projects/{fc.PROJECT_ID}"
         "/databases/(default)/documents/teacher_invites")


def new_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(cself.INVITE_CODE_LEN))


def create(count: int, note: str, output: Path) -> Path:
    token = operator_token()
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    codes = []
    for _ in range(count):
        code = new_code()
        # currentDocument.exists=false: không bao giờ ghi đè một mã đang có.
        fc._json_request(
            f"{_BASE}?documentId={code}",
            {"fields": {"note": {"stringValue": note[:120]},
                        "created_at": {"timestampValue":
                                       datetime.datetime.now(datetime.timezone.utc)
                                       .strftime("%Y-%m-%dT%H:%M:%SZ")}}},
            token=token, method="POST",
        )
        codes.append(cself.format_invite_code(code))
    target = output / f"teacher-invites-{stamp}.json"
    write_private(target, {"note": note, "codes": codes,
                           "usage": "Mỗi mã dùng một lần ở form Đăng ký giáo viên."})
    return target


def revoke(code: str) -> None:
    code = cself.normalize_invite_code(code)
    fc._json_request(f"{_BASE}/{quote(code)}", token=operator_token(), method="DELETE")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    make = sub.add_parser("create")
    make.add_argument("--count", type=int, default=1)
    make.add_argument("--note", default="")
    make.add_argument("--output-dir", type=Path, default=Path.home() / ".quant-app-classroom")
    drop = sub.add_parser("revoke")
    drop.add_argument("code")
    args = parser.parse_args()

    if args.action == "create":
        if not 1 <= args.count <= 50:
            raise SystemExit("Mỗi lần tạo từ 1 đến 50 mã.")
        output = args.output_dir.resolve()
        if output.is_relative_to(ROOT):
            raise SystemExit("Thư mục lưu mã phải nằm ngoài repo công khai.")
        target = create(args.count, args.note, output)
        print(f"Đã tạo {args.count} mã mời. Mở tệp riêng để lấy mã: {target}")
    else:
        revoke(args.code)
        print("Đã thu hồi mã mời.")


if __name__ == "__main__":
    main()
