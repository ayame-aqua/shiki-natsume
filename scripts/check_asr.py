"""手动核对 ASR 后端：把仓库的转写链路跑在样例音频上，结果写 UTF-8 文件避免控制台编码干扰。

用法：
  python scripts/check_asr.py <音频文件> [更多音频文件...]
  python scripts/check_asr.py --model fun-asr-nano example/zh.mp3
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.speech.asr import build_asr  # noqa: E402
from src.speech.constants import DEFAULT_ASR_MODEL  # noqa: E402

OUTPUT_PATH = Path("data/asr_check.txt")
MIME_BY_SUFFIX = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".webm": "audio/webm"}


async def _run(model_name: str, paths: list[Path]) -> list[str]:
    asr = build_asr(model_name)
    lines = [f"model={model_name}"]
    for path in paths:
        mime = MIME_BY_SUFFIX.get(path.suffix.lower(), "audio/wav")
        text = await asr.transcribe(path.read_bytes(), mime)
        lines.append(f"{path.name} -> {text}")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="核对本仓库 ASR 转写")
    parser.add_argument(
        "--model",
        default=DEFAULT_ASR_MODEL,
        help=f"asr_model 名，默认 {DEFAULT_ASR_MODEL}",
    )
    parser.add_argument("audios", nargs="+", help="音频文件")
    args = parser.parse_args()
    paths = [Path(item) for item in args.audios]
    lines = asyncio.run(_run(args.model, paths))
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
