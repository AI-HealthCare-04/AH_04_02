# -*- coding: utf-8 -*-
"""
파싱 규칙 초안 (Day1)
CLOVA/Tesseract가 뽑아낸 raw_text에서 약품명/용량/복용법/진단명을 구조화한다.
정확도는 나중에(Day6 OCR 정확도 측정 단계) 다듬고, 오늘은 최소 동작 버전만 만든다.
"""

import re

# 용량 패턴: 숫자 + mg/g/ml/정/캡슐
DOSAGE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(mg|g|ml|정|캡슐)")

# 복용법 패턴: "1일 N회", "하루 N번" 등
FREQUENCY_PATTERN = re.compile(r"(1일|하루)\s*(\d+)\s*(회|번)")

# TODO: Day2 이후 실제 샘플 10장으로 검증하며 아래 사전을 계속 보강
DRUG_CLASS_DICTIONARY = {
    "아스피린": "항혈소판제",
    "로자탄": "ARB(안지오텐신수용체차단제)",
    "메트포르민": "당뇨병용제(비구아니드)",
    "암로디핀": "칼슘채널차단제",
}


def extract_dosage(text: str) -> str:
    m = DOSAGE_PATTERN.search(text)
    return f"{m.group(1)}{m.group(2)}" if m else ""


def extract_frequency(text: str) -> str:
    m = FREQUENCY_PATTERN.search(text)
    return f"{m.group(1)} {m.group(2)}{m.group(3)}" if m else ""


def lookup_drug_class(drug_name: str) -> str:
    return DRUG_CLASS_DICTIONARY.get(drug_name, "")


def parse_line(line: str) -> dict:
    """처방전 한 줄(약품명 + 용량 + 복용법)을 파싱. 진단명은 별도 라인에서 처리."""
    return {
        "dosage": extract_dosage(line),
        "frequency": extract_frequency(line),
    }


if __name__ == "__main__":
    sample = "아스피린 100mg 1일 1회"
    print(parse_line(sample))
    print(lookup_drug_class("아스피린"))
