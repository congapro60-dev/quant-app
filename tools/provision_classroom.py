"""Operator-only provisioning; uses gcloud login, never exports an Admin key.

Generated credentials are written outside the public checkout and not printed.
Run: python tools/provision_classroom.py --teacher-code GV-001
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import firebase_classroom as fc


def command(*args):
    return subprocess.run(args, capture_output=True, encoding="utf-8", check=True).stdout.strip()


def operator_token():
    account = command("gcloud.cmd", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)")
    if account != "congapro60@gmail.com":
        raise SystemExit("Wrong operator account; sign in as the approved project owner. No account was switched.")
    return command("gcloud.cmd", "auth", "print-access-token", "--quiet")


def config_from_cli():
    apps = json.loads(command("firebase.cmd", "apps:list", "--project", fc.PROJECT_ID, "--json", "--non-interactive"))["result"]
    web = next(a for a in apps if a.get("platform") == "WEB" or ":web:" in a.get("appId", ""))
    sdk = json.loads(command("firebase.cmd", "apps:sdkconfig", "WEB", web["appId"],
                             "--project", fc.PROJECT_ID, "--json", "--non-interactive"))["result"]["sdkConfig"]
    if isinstance(sdk, str):
        sdk = json.loads(sdk)
    return {"project_id": fc.PROJECT_ID, "api_key": sdk["apiKey"]}


def write_private(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def provision_teacher(config, code, output):
    target = output / f"teacher-{code}.json"
    if target.exists():
        return json.loads(target.read_text(encoding="utf-8"))
    client = fc.FirebaseClassroom(config)
    password = secrets.token_urlsafe(24)
    data = client._auth("signUp", {"email": fc.account_email("teacher", "", code),
                                  "password": password, "returnSecureToken": True})
    # Persist before privileged role write so a retry can recover safely.
    result = {"teacher_code": code, "password": password, "uid": data["localId"]}
    write_private(target, result)
    return result


def enable_teacher(teacher):
    fc._json_request(
        f"https://firestore.googleapis.com/v1/projects/{fc.PROJECT_ID}/databases/(default)/documents/teachers/{teacher['uid']}",
        {"fields": {"enabled": {"booleanValue": True}}}, token=operator_token(), method="PATCH",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--teacher-code", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path.home() / ".quant-app-classroom")
    args = parser.parse_args()
    operator_token()  # Verify approved active account before creating any account or document.
    output = args.output_dir.resolve()
    if output.is_relative_to(ROOT):
        raise SystemExit("Output must be outside the public checkout")
    code = fc.cp._id(args.teacher_code, "teacher_code").upper()
    config_file = output / "config.json"
    config = json.loads(config_file.read_text()) if config_file.exists() else config_from_cli()
    if not config_file.exists():
        write_private(config_file, config)
    teacher = provision_teacher(config, code, output)
    enable_teacher(teacher)
    # Public client config goes into Streamlit Secrets, not Git.
    secrets_file = output / "streamlit-classroom.toml"
    if not secrets_file.exists():
        secrets_file.parent.mkdir(parents=True, exist_ok=True)
        with os.fdopen(os.open(secrets_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as file:
            file.write('[classroom_firebase]\nenabled = true\nproject_id = ' + json.dumps(config["project_id"]) + '\napi_key = ' + json.dumps(config["api_key"]) + '\n')
    print(f"Teacher {code} provisioned. Private handoff files: {output}")


if __name__ == "__main__":
    try:
        main()
    except (subprocess.CalledProcessError, fc.ClassroomConnectionError, KeyError):
        raise SystemExit("Provisioning failed; no credentials were printed. Check CLI access/configuration.")
