"""
AI Worker 진입점
현재는 임시 스켈레톤입니다. Redis Stream 기반 실제 추론 로직은
이후 스프린트에서 구현됩니다 (roadmap.md 2주차: 파이프라인 1차 연결).
"""
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_worker")


async def main() -> None:
    logger.info("AI Worker 시작 — 대기 중 (구현 예정)")
    while True:
        # TODO: Redis Stream XREAD로 작업 수신 → 실제 추론 처리
        await asyncio.sleep(10)
        logger.info("AI Worker 대기 중...")


if __name__ == "__main__":
    asyncio.run(main())
