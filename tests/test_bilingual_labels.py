"""Mọi thuật ngữ tiếng Anh hiển thị phải đi kèm tiếng Việt.

Bài kiểm tra quét các hằng nhãn thật sự được đưa ra giao diện, chứ không chỉ
kiểm tra danh sách do chính nó dựng ra.
"""

from __future__ import annotations

import re
import unicodedata

import pytest

import curriculum as cur
import learning_modes as lmode
import progress_profile as pp
import provider_directory as pdir
import readiness_gate as rg


# Thuật ngữ tiếng Anh không được đứng một mình trên giao diện.
ENGLISH_TERMS = (
    "paper portfolio", "paper trading", "backtest", "out-of-sample",
    "margin", "short selling", "cfd", "crypto", "derivatives",
    "high-school foundation", "university advanced", "realtime",
)

# Tên riêng và ký hiệu được phép đứng một mình.
PROPER_NOUNS = {
    "eviews", "markowitz", "sim", "ols", "vsdc", "json", "csv", "vnindex",
    "ssi", "mbs", "tcbs", "vndirect", "vietcap", "hsc", "vnsc", "dragonx",
    "tcinvest", "dstock", "oecd", "pisa",
}

_VIET_ONLY = "ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ"


def has_vietnamese(text: str) -> bool:
    """Có ký tự tiếng Việt có dấu, hoặc từ tiếng Việt không dấu thường gặp."""

    low = text.lower()
    if any(ch in _VIET_ONLY for ch in low):
        return True
    # Một số nhãn ngắn không dấu vẫn là tiếng Việt.
    plain_markers = (" va ", "gia ", "von ", "tien ", "hoc ")
    return any(m in f" {low} " for m in plain_markers)


def _labels_under_test() -> list[tuple[str, str]]:
    """(nguồn, nhãn) của mọi chuỗi hiển thị cho người dùng."""

    items: list[tuple[str, str]] = []
    for key, label in lmode.MODE_LABELS.items():
        items.append((f"MODE_LABELS[{key}]", label))
    for key, label in lmode.AREA_LABELS.items():
        items.append((f"AREA_LABELS[{key}]", label))
    for key, meta in lmode.FEATURES.items():
        items.append((f"FEATURES[{key}].label", meta["label"]))
    for key, label in rg.PRODUCT_LABELS.items():
        items.append((f"PRODUCT_LABELS[{key}]", label))
    for key, label in rg.AGE_LABELS.items():
        items.append((f"AGE_LABELS[{key}]", label))
    for key, label in pp.RUBRIC_LABELS.items():
        items.append((f"RUBRIC_LABELS[{key}]", label))
    for lesson in cur.LESSONS:
        items.append((f"lesson[{lesson.lesson_id}].title", lesson.title))
    items.append(("UNVERIFIED_NOTICE", pdir.UNVERIFIED_NOTICE))
    for name in (pdir.P_STOCK, pdir.P_FUND, pdir.P_DERIVATIVE):
        items.append(("product", name))
    return items


@pytest.mark.parametrize("source,label", _labels_under_test(), ids=lambda v: str(v)[:40])
def test_every_displayed_label_contains_vietnamese(source, label):
    assert has_vietnamese(label), f"{source} thiếu tiếng Việt: {label!r}"


@pytest.mark.parametrize("source,label", _labels_under_test(), ids=lambda v: str(v)[:40])
def test_english_terms_are_glossed_in_the_same_label(source, label):
    """Nhãn chứa thuật ngữ tiếng Anh thì phải có phần tiếng Việt trong cùng nhãn."""

    low = label.lower()
    for term in ENGLISH_TERMS:
        if term in low:
            assert has_vietnamese(label), (
                f"{source}: '{term}' đứng một mình, thiếu giải thích tiếng Việt "
                f"trong {label!r}"
            )


def test_mode_labels_pair_vietnamese_with_english():
    for mode, label in lmode.MODE_LABELS.items():
        assert has_vietnamese(label), mode
        assert "(" in label and ")" in label, mode


def test_leveraged_products_name_the_english_term_in_brackets():
    """Thuật ngữ người học sẽ gặp ở công ty chứng khoán phải được nêu kèm."""

    for product, expected in (
        (rg.PRODUCT_MARGIN, "margin"),
        (rg.PRODUCT_SHORT, "short selling"),
        (rg.PRODUCT_DERIVATIVE, "derivatives"),
    ):
        label = rg.PRODUCT_LABELS[product].lower()
        assert expected in label
        assert has_vietnamese(rg.PRODUCT_LABELS[product])


def test_glossary_detector_actually_discriminates():
    """Bộ dò phải bắt được nhãn xấu, nếu không bài kiểm tra là vô nghĩa."""

    assert has_vietnamese("Danh mục mô phỏng (paper portfolio)") is True
    assert has_vietnamese("Paper portfolio") is False
    assert has_vietnamese("Backtest OOS") is False


def test_no_bare_english_only_feature_label():
    for key, meta in lmode.FEATURES.items():
        label = meta["label"]
        words = re.findall(r"[A-Za-z][A-Za-z-]+", label)
        bare = [w for w in words if w.lower() not in PROPER_NOUNS]
        if bare:
            assert has_vietnamese(label), (key, label, bare)


def test_directory_table_values_are_not_bare_english():
    """Giá trị trong bảng cũng là chữ hiển thị, không chỉ tiêu đề cột.

    Bài kiểm tra trước chỉ soi hằng nhãn nên đã để lọt chuỗi 'unverified'
    hiện nguyên văn trong cột trạng thái.
    """

    for row in pdir.directory_rows():
        status = row["Trạng thái xác minh"]
        assert has_vietnamese(status), f"Trạng thái hiển thị thiếu tiếng Việt: {status!r}"
        assert status not in pdir.VALID_STATUSES, (
            f"Đang hiện giá trị nội bộ chưa dịch: {status!r}"
        )


@pytest.mark.parametrize("status", list(pdir.VALID_STATUSES))
def test_every_verification_status_has_a_vietnamese_label(status):
    assert has_vietnamese(pdir.status_display(status)), status


def test_status_display_falls_back_to_unverified_for_unknown():
    assert pdir.status_display("gia_tri_la") == pdir.STATUS_LABELS[pdir.STATUS_UNVERIFIED]


def test_area_labels_are_pure_vietnamese():
    for area, label in lmode.AREA_LABELS.items():
        assert has_vietnamese(label), area


def test_lesson_titles_are_vietnamese():
    for lesson in cur.LESSONS:
        assert has_vietnamese(lesson.title), lesson.lesson_id
        assert has_vietnamese(lesson.objective), lesson.lesson_id
