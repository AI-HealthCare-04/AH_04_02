from pathlib import Path

from rag.kdca_health_info_data import load_kdca_health_info_sections

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "kdca_healthinfo_sample.jsonl"


def test_load_kdca_health_info_sections_flattens_all_sections():
    sections = load_kdca_health_info_sections(FIXTURE_PATH)

    # 1번째 기사 3섹션 + 2번째 기사 1섹션
    assert len(sections) == 4
    assert {s.cntnts_sn for s in sections} == {"6544", "5423"}


def test_load_kdca_health_info_sections_preserves_order_and_index():
    sections = load_kdca_health_info_sections(FIXTURE_PATH)
    edema_sections = [s for s in sections if s.cntnts_sn == "6544"]

    assert [s.index for s in edema_sections] == [0, 1, 2]
    assert edema_sections[0].section_name == "개요정의"
    # 같은 section_sn(161)이 이미지/텍스트로 반복되는 케이스 — index로만 구분 가능
    assert edema_sections[1].section_sn == edema_sections[2].section_sn == "161"


def test_load_kdca_health_info_sections_field_mapping():
    sections = load_kdca_health_info_sections(FIXTURE_PATH)
    cold = next(s for s in sections if s.cntnts_sn == "5423")

    assert cold.title == "감기"
    assert cold.section_name == "개요정의"
    assert cold.updated_at == "2026-05-12 13:24"
    assert cold.source == "질병관리청 국가건강정보포털"
    assert "감기는 바이러스" in cold.html
