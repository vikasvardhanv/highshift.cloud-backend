import asyncio
import os
import sys

from dotenv import load_dotenv

sys.path.append(os.getcwd())

from app.temporal.worker import run_temporal_worker  # noqa: E402


async def main():
    load_dotenv()
    if os.getenv("TEMPORAL_ENABLED", "false").lower() not in {"1", "true", "yes"}:
        raise RuntimeError("TEMPORAL_ENABLED is false. Set TEMPORAL_ENABLED=true before running worker.")
    await run_temporal_worker()


if __name__ == "__main__":
    asyncio.run(main())

