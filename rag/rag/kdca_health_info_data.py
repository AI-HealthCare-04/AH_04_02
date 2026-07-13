import json
from pathlib import Path

from rag.schemas import KdcaHealthInfoSection

DEFAULT_KDCA_HEALTH_INFO_PATH = Path(__file__).resolve().parent.parent / "data" / "kdca_healthinfo_content.jsonl"


def load_kdca_health_info_sections(path: Path | None = None) -> list[KdcaHealthInfoSection]:
    """`data/kdca_healthinfo_content.jsonl`(질병관리청 국가건강정보포털 Open API 수집분)을
    섹션 단위로 펼쳐서 읽어옵니다. 한 줄 = 건강정보 항목 1건(cntntsSn), sections 배열에
    여러 섹션(개요정의/증상/치료 등)이 들어있습니다.
    """
    path = path or DEFAULT_KDCA_HEALTH_INFO_PATH
    sections: list[KdcaHealthInfoSection] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            article = json.loads(line)
            for i, section in enumerate(article.get("sections", [])):
                sections.append(
                    KdcaHealthInfoSection(
                        cntnts_sn=article["cntntsSn"],
                        title=article["title"],
                        section_name=section["name"],
                        section_sn=section["cl_sn"],
                        index=i,
                        html=section["html"],
                        updated_at=article.get("updated_at", ""),
                        source=article.get("source", "질병관리청 국가건강정보포털"),
                        source_url=article.get("source_url", ""),
                    )
                )
    return sections
