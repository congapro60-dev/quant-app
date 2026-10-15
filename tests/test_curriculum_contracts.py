import curriculum as cur


def test_compound_question_unit_matches_answer_precision():
    question = cur.get_lesson("m1_tien_ngan_sach").questions[0]
    assert "hai chữ số thập phân" in question.prompt
    assert question.check(23.15)
    assert not question.check(22.0)
