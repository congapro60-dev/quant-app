"""Firebase client REST transport: ID tokens obey Rules, never Admin SDK."""
from __future__ import annotations

import hashlib
import json
import secrets
import time
from dataclasses import dataclass, field
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import classroom_packages as cp
import classroom_submit as cs
import classroom_self as cself

PROJECT_ID = "quant-app-classroom-20261026"


class ClassroomConnectionError(RuntimeError):
    pass


def account_email(role, class_code, code):
    """Synthetic Auth identifier: no pupil email/name is collected."""
    role = "teacher" if role == "teacher" else "student"
    code = cp._id(code, "code").upper()
    class_code = cp._id(class_code, "class_code").upper() if role == "student" else ""
    digest = hashlib.sha256(f"{role}:{class_code}:{code}".encode()).hexdigest()
    return f"{role}-{digest}@quant-app.invalid"


def self_email(username):
    """Synthetic Auth identifier for self-registered accounts (no real email)."""
    return f"self-{cself.username_digest(username)}@quant-app.invalid"


def _json_request(url, data=None, *, token="", method=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data, allow_nan=False).encode() if data is not None else None
    try:
        with urlopen(Request(url, data=body, headers=headers, method=method), timeout=25) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise ClassroomConnectionError("Phản hồi Firebase quá lớn.")
            return json.loads(raw)
    except HTTPError as exc:
        # Never echo response bodies, URLs, tokens or passwords into the UI.
        message = {
            400: "Thông tin đăng nhập hoặc dữ liệu không hợp lệ.",
            401: "Phiên đã hết hạn. Đăng nhập lại.",
            403: "Không có quyền truy cập lớp hoặc bài nộp này.",
            404: "Chưa có lớp hoặc tài khoản được cấp.",
            409: "Mã đã tồn tại. Chọn mã khác; không ghi đè.",
            429: "Quá nhiều yêu cầu. Chờ một lát rồi thử lại.",
        }.get(exc.code, "Firebase tạm chưa phản hồi. Bản học cục bộ vẫn được giữ.")
        raise ClassroomConnectionError(message) from None
    except (URLError, OSError, ValueError):
        raise ClassroomConnectionError("Mất kết nối Firebase. Hãy giữ bản JSON và thử lại sau.") from None


def _value(value):
    if value is None:
        return {"nullValue": None}
    if isinstance(value, bool):
        return {"booleanValue": value}
    if isinstance(value, int):
        return {"integerValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, str):
        return {"stringValue": value}
    if isinstance(value, list):
        return {"arrayValue": {"values": [_value(v) for v in value]}}
    if isinstance(value, dict):
        return {"mapValue": {"fields": {k: _value(v) for k, v in value.items()}}}
    raise cs.SubmissionValidationError("Kiểu dữ liệu nộp bài không hợp lệ.")


def _plain(value):
    if "mapValue" in value:
        return {k: _plain(v) for k, v in value["mapValue"].get("fields", {}).items()}
    if "arrayValue" in value:
        return [_plain(v) for v in value["arrayValue"].get("values", [])]
    if "integerValue" in value:
        return int(value["integerValue"])
    return next(iter(value.values()), None)


def document_data(doc):
    return {key: _plain(value) for key, value in doc.get("fields", {}).items()}


@dataclass(repr=False)
class ClassroomSession:
    uid: str
    id_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    expires_at: float


class FirebaseClassroom:
    def __init__(self, config):
        if config.get("project_id") != PROJECT_ID or not config.get("api_key"):
            raise cs.SubmissionNotConfiguredError("Chưa cấu hình project nộp bài.")
        self.config = dict(config)
        self.base = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"

    def _auth(self, action, data):
        key = urlencode({"key": self.config["api_key"]})
        return _json_request(f"https://identitytoolkit.googleapis.com/v1/accounts:{action}?{key}", data)

    def login(self, role, class_code, code, password):
        if not isinstance(password, str) or len(password) < 12:
            raise ClassroomConnectionError("Dùng mật khẩu giáo viên hoặc chủ project đã cấp.")
        result = self._auth("signInWithPassword", {
            "email": account_email(role, class_code, code),
            "password": password, "returnSecureToken": True,
        })
        return ClassroomSession(result["localId"], result["idToken"], result["refreshToken"],
                                time.time() + int(result["expiresIn"]) - 60)

    def login_self(self, username, password):
        """Đăng nhập tài khoản tự đăng ký bằng tên đăng nhập + mật khẩu tự chọn."""
        username = cself.normalize_username(username)
        cself.validate_password(password)
        result = self._auth("signInWithPassword", {
            "email": self_email(username), "password": password, "returnSecureToken": True,
        })
        return ClassroomSession(result["localId"], result["idToken"], result["refreshToken"],
                                time.time() + int(result["expiresIn"]) - 60)

    def _register(self, username, password, doc_path, doc_data, timestamp_field):
        """Tạo tài khoản Auth rồi viết hồ sơ; hủy tài khoản mồ côi nếu viết hỏng."""
        username = cself.normalize_username(username)
        cself.validate_password(password)
        created = self._auth("signUp", {
            "email": self_email(username), "password": password, "returnSecureToken": True,
        })
        session = ClassroomSession(created["localId"], created["idToken"], created["refreshToken"],
                                   time.time() + int(created["expiresIn"]) - 60)
        try:
            self._write(session, doc_path.format(uid=session.uid), doc_data,
                        create=True, timestamp=True, timestamp_field=timestamp_field)
        except ClassroomConnectionError:
            # Remove only this just-created Auth account; never an existing user.
            try:
                self._auth("delete", {"idToken": created["idToken"]})
            except ClassroomConnectionError:
                pass
            raise
        return session

    def register_teacher(self, username, password, display_name):
        """GV tự tạo tài khoản; tên hiển thị public để HS chọn trong danh bạ."""
        return self._register(username, password, "teacher_directory/{uid}",
                              cself.teacher_directory_payload(display_name), "created_at")

    def register_student(self, username, password, display_name, block, class_name):
        """HS tự tạo tài khoản; chưa theo GV nào cho tới khi chọn."""
        return self._register(username, password, "student_state/{uid}",
                              cself.student_state_payload(display_name, block, class_name),
                              "updated_at")

    def self_profile(self, session):
        """Hồ sơ tự đăng ký: HS (student_state) trước, rồi GV (teacher_directory)."""
        for kind, path in (("student", f"student_state/{session.uid}"),
                           ("teacher", f"teacher_directory/{session.uid}")):
            try:
                return {"kind": kind, **self.get(session, path)}
            except ClassroomConnectionError:
                continue
        return {"kind": "none"}

    def list_teachers(self, session):
        """Danh bạ GV công khai (cần đăng nhập); trả [{uid, display_name}]."""
        docs, page_token = [], ""
        for _ in range(2):
            query = urlencode({"pageSize": 200, **({"pageToken": page_token} if page_token else {})})
            page = _json_request(f"{self.base}/teacher_directory?{query}", token=self._token(session))
            for doc in page.get("documents", []):
                uid = doc["name"].rsplit("/", 1)[-1]
                docs.append({"uid": uid, "display_name": document_data(doc).get("display_name", "")})
            page_token = page.get("nextPageToken", "")
            if not page_token:
                return docs
        raise ClassroomConnectionError("Danh bạ giáo viên quá dài. Hãy chờ chủ project mở rộng.")

    def join_teacher(self, session, teacher_uid):
        """Một commit nguyên tử: rút danh sách cũ (nếu có) + vào danh sách mới + cập nhật con trỏ."""
        if not isinstance(teacher_uid, str) or not teacher_uid:
            raise ClassroomConnectionError("Chọn giáo viên trước khi vào danh sách.")
        if teacher_uid == session.uid:
            raise ClassroomConnectionError("Không thể tự chọn chính mình làm giáo viên.")
        raw = self.get(session, f"student_state/{session.uid}")
        state = cself.student_state_payload(**{k: raw[k] for k in
                                               ("display_name", "block", "class_name")})
        current = raw.get("teacher_uid")
        writes = []
        if isinstance(current, str) and current and current != teacher_uid:
            writes.append(self._delete_write(f"rosters/{current}/members/{session.uid}"))
        writes.append(self._make_write(
            f"rosters/{teacher_uid}/members/{session.uid}",
            cself.roster_member_payload(state), create=True,
            timestamp=True, timestamp_field="joined_at"))
        writes.append(self._make_write(
            f"student_state/{session.uid}", {**state, "teacher_uid": teacher_uid},
            timestamp=True, timestamp_field="updated_at"))
        self._commit(session, writes)
        return teacher_uid

    def leave_teacher(self, session):
        """HS chủ động rút khỏi danh sách GV hiện tại; con trỏ về rỗng."""
        state = self.get(session, f"student_state/{session.uid}")
        current = state.get("teacher_uid")
        if not isinstance(current, str) or not current:
            raise ClassroomConnectionError("Em chưa vào danh sách giáo viên nào.")
        writes = [
            self._delete_write(f"rosters/{current}/members/{session.uid}"),
            self._make_write(
                f"student_state/{session.uid}",
                cself.student_state_payload(state.get("display_name"), state.get("block"),
                                            state.get("class_name"), None),
                timestamp=True, timestamp_field="updated_at"),
        ]
        self._commit(session, writes)

    def roster(self, session):
        """Danh sách HS đã tự chọn GV này; HS tự vào/rút, GV chỉ đọc và xóa."""
        docs, page_token = [], ""
        for _ in range(20):
            query = urlencode({"pageSize": 100, **({"pageToken": page_token} if page_token else {})})
            page = _json_request(f"{self.base}/rosters/{session.uid}/members?{query}",
                                 token=self._token(session))
            for doc in page.get("documents", []):
                uid = doc["name"].rsplit("/", 1)[-1]
                docs.append({"uid": uid, **document_data(doc)})
            page_token = page.get("nextPageToken", "")
            if not page_token:
                return cself.sort_roster(docs)
        raise ClassroomConnectionError("Danh sách có hơn 2.000 học sinh; hãy chia nhóm.")

    def remove_student(self, session, student_uid):
        """GV xóa HS khỏi danh sách của mình; hồ sơ HS và các nơi khác không đụng tới."""
        if not isinstance(student_uid, str) or not student_uid:
            raise ClassroomConnectionError("Chọn học sinh cần xóa.")
        self._commit(session, [self._delete_write(f"rosters/{session.uid}/members/{student_uid}")])

    def _token(self, session):
        if session.expires_at <= time.time():
            key = urlencode({"key": self.config["api_key"]})
            result = _json_request(f"https://securetoken.googleapis.com/v1/token?{key}", {
                "grant_type": "refresh_token", "refresh_token": session.refresh_token,
            })
            session.id_token = result["id_token"]
            session.refresh_token = result["refresh_token"]
            session.expires_at = time.time() + int(result["expires_in"]) - 60
        return session.id_token

    def get(self, session, path):
        data = document_data(_json_request(f"{self.base}/{path}", token=self._token(session)))
        if len(path.split('/')) == 4 and path.split('/')[2] == 'submissions':
            return self._hydrate(session, path, data)
        return data

    def _hydrate(self, session, path, data):
        if 'lesson_count' not in data:  # Earlier QA documents used a single summary document.
            return data
        rows, page_token = [], ''
        for _ in range(3):
            query = urlencode({'pageSize': 100, **({'pageToken': page_token} if page_token else {})})
            page = _json_request(f"{self.base}/{path}/lessons?{query}", token=self._token(session))
            rows.extend(document_data(d) for d in page.get('documents', []))
            page_token = page.get('nextPageToken', '')
            if not page_token:
                break
        rows = sorted((r for r in rows if r['index'] < data['lesson_count']), key=lambda r: r['index'])
        if page_token or [r['index'] for r in rows] != list(range(data['lesson_count'])):
            raise ClassroomConnectionError("Bài nộp chưa đủ dữ liệu mô-đun. Hãy nộp lại hoặc giữ bản JSON.")
        data['summary']['lesson_results'] = [r['lesson'] for r in rows]
        return data

    def _commit(self, session, writes):
        return _json_request(f"{self.base}:commit", {"writes": writes}, token=self._token(session))

    def _make_write(self, path, data, *, create=False, timestamp=False,
                    timestamp_field="received_at"):
        write = {"update": {"name": self.base.split("/v1/")[1] + "/" + path,
                            "fields": {k: _value(v) for k, v in data.items()}}}
        if create:
            write["currentDocument"] = {"exists": False}
        if timestamp:
            write["updateTransforms"] = [{"fieldPath": timestamp_field,
                                          "setToServerValue": "REQUEST_TIME"}]
        return write

    def _delete_write(self, path):
        return {"delete": self.base.split("/v1/")[1] + "/" + path}

    def _write(self, session, path, data, **options):
        return self._commit(session, [self._make_write(path, data, **options)])

    def is_teacher(self, session):
        return self.get(session, f"teachers/{session.uid}").get("enabled") is True

    def create_class(self, session, class_code):
        code = cp._id(class_code, "class_code").upper()
        self._write(session, f"classes/{code}", {"owner_uid": session.uid, "class_code": code}, create=True)
        return code

    def classes(self, session):
        result = _json_request(f"{self.base}:runQuery", {"structuredQuery": {
            "from": [{"collectionId": "classes"}],
            "where": {"fieldFilter": {"field": {"fieldPath": "owner_uid"},
                                       "op": "EQUAL", "value": {"stringValue": session.uid}}},
            "limit": 100,
        }}, token=self._token(session))
        return [document_data(row["document"]) for row in result if "document" in row]

    def issue_student(self, session, class_code, student_code):
        class_code = cp._id(class_code, "class_code").upper()
        student_code = cp._student_code(student_code).upper()
        if self.get(session, f"classes/{class_code}")["owner_uid"] != session.uid:
            raise ClassroomConnectionError("Bạn không sở hữu lớp này.")
        password = secrets.token_urlsafe(24)
        created = self._auth("signUp", {
            "email": account_email("student", class_code, student_code),
            "password": password, "returnSecureToken": True,
        })
        try:
            self._write(session, f"classes/{class_code}/students/{student_code}",
                        {"uid": created["localId"], "student_code": student_code}, create=True)
        except ClassroomConnectionError:
            # Account has no class permissions if membership creation fails.
            # Remove only this just-created Auth account; never an existing user.
            try:
                self._auth("delete", {"idToken": created["idToken"]})
            except ClassroomConnectionError:
                pass
            raise
        return {"class_code": class_code, "student_code": student_code, "password": password}

    def submit(self, session, submission):
        cs.validate_submission(submission)
        code = submission["class_code"]
        student_code = submission["student_code"]
        member = self.get(session, f"classes/{code}/students/{student_code}")
        if member["uid"] != session.uid:
            raise ClassroomConnectionError("Mã học sinh không thuộc phiên đăng nhập.")
        doc_id = hashlib.sha256(f"{submission['assignment_id']}:{student_code}".encode()).hexdigest()
        path = f"classes/{code}/submissions/{doc_id}"
        lessons = submission['lesson_results']
        header = {k: v for k, v in submission.items() if k != 'lesson_results'}
        # One atomic commit: no receipt can acknowledge a half-written course.
        writes = [self._make_write(path, {"owner_uid": session.uid, "summary": header,
                                         "lesson_count": len(lessons)}, timestamp=True)]
        writes.extend(self._make_write(f"{path}/lessons/{i}", {"index": i, "lesson": row})
                      for i, row in enumerate(lessons))
        result = self._commit(session, writes)
        stamp = result.get("commitTime")
        if not stamp or not result.get("writeResults"):
            raise ClassroomConnectionError("Chưa nhận xác nhận lưu. Hãy giữ JSON và kiểm tra lại.")
        return {"receipt_id": doc_id, "received_at": stamp, "class_code": code}

    def submissions(self, session, class_code):
        code = cp._id(class_code, "class_code").upper()
        docs, page_token = [], ""
        for _ in range(20):
            query = urlencode({"pageSize": 100, **({"pageToken": page_token} if page_token else {})})
            page = _json_request(f"{self.base}/classes/{code}/submissions?{query}", token=self._token(session))
            for doc in page.get("documents", []):
                path = doc['name'].split('/documents/', 1)[1]
                docs.append(self._hydrate(session, path, document_data(doc)))
            page_token = page.get("nextPageToken", "")
            if not page_token:
                return docs
        raise ClassroomConnectionError("Lớp có hơn 2.000 bài; hãy chia thành nhóm nhỏ hơn để xuất.")
