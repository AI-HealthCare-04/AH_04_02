import os
import sys
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

# routers/가 프로젝트 루트 하위에 있으므로, 직접 실행 시에도 루트 모듈을 찾을 수 있도록 보장
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env")

from ocr_interface import get_ocr_provider  # noqa: E402

router = APIRouter(prefix="/ocr", tags=["OCR"])

_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}
_MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post(
    "",
    summary="처방전 이미지 OCR",
    description="이미지를 업로드하면 CLOVA OCR로 텍스트를 추출하고 복약 정보를 구조화해 반환합니다.",
)
async def run_ocr(file: UploadFile = File(..., description="처방전 이미지 (jpg/png/bmp/tiff)")):
    # 1. 확장자 검증
    _, ext = os.path.splitext(file.filename or "")
    if ext.lower() not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식: '{ext}'. 허용: {sorted(_ALLOWED_EXTENSIONS)}",
        )

    # 2. 파일 크기 검증
    content = await file.read()
    if len(content) > _MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="파일 크기가 10 MB를 초과합니다.")

    # 3. 임시 파일로 저장 (ClovaOCRProvider.extract()는 파일 경로를 받음)
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext.lower()) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        provider = get_ocr_provider("clova")
        result = provider.extract(tmp_path)
    except RuntimeError as exc:
        # CLOVA 키 미설정 등 설정 오류
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"OCR 처리 중 오류 발생: {exc}") from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return result.to_dict()
