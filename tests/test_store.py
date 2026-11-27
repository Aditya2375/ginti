import pytest

from app.store import BadNickname, Store


@pytest.fixture
def st():
    return Store(":memory:")


def test_learner_get_or_create_and_nickname_rules(st):
    a = st.learner("Asha", "hi")
    assert st.learner("asha", "hi")["id"] == a["id"]
    assert st.learner("Asha", "en")["lang"] == "en"
    for bad in ["", "   ", "x" * 25, "a<b>", "a;drop", "=cmd"]:
        with pytest.raises(BadNickname):
            st.learner(bad, "hi")
    assert st.learner("आशा", "hi")["nickname"] == "आशा"
    with pytest.raises(ValueError):
        st.learner("Ok", "fr")


def test_record_moves_box_and_level(st):
    l = st.learner("Ravi", "en")["id"]
    for i in range(5):
        r = st.record(l, "add", f"1+{i}", 1 + i, 1 + i, True, 1200, "voice")
    assert r["level"] == 2 and r["leveled_up"]
    assert st.progress(l, "add")["served"] == 5
    st.record(l, "add", "9+9", 18, 17, False, 3000, "typed")
    assert st.boxes(l)["9+9"]["box"] == 0
    sk = st.record(l, "add", "2+2", 4, None, False, None, "voice", skipped=True)
    assert sk["level"] == 2 and not sk["leveled_down"]


def test_teacher_summary_and_export(st):
    l = st.learner("Mina", "hi")["id"]
    for _ in range(3):
        st.record(l, "mul", "7x8", 56, 54, False, 4000, "voice")
    st.record(l, "mul", "2x3", 6, 6, True, 900, "voice")
    st.record(l, "mul", "6x6", 36, None, False, None, "voice", skipped=True)
    s = st.teacher_summary()[0]
    assert s["nickname"] == "Mina" and s["attempts"] == 5 and s["correct"] == 1
    assert s["weak_facts"][0] == {"fact": "7x8", "tries": 3, "misses": 3}
    assert all(w["fact"] != "6x6" for w in s["weak_facts"])
    assert s["median_ms_correct"] == 900
    assert len(st.export_rows()) == 5


def test_delete_learner_removes_everything(st):
    l = st.learner("Temp", "en")["id"]
    st.record(l, "add", "1+1", 2, 2, True, 500, "voice")
    assert st.delete_learner("Temp") and not st.delete_learner("Temp")
    assert st.export_rows() == [] and st.boxes(l) == {}


def test_no_audio_or_personal_columns(st):
    cols = {r[1] for t in ("learners", "attempts", "progress", "boxes")
            for r in st._db.execute(f"PRAGMA table_info({t})")}
    assert not cols & {"audio", "email", "phone", "surname", "address", "wav", "pcm"}
