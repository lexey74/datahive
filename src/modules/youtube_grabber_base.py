from typing import Protocol
from pathlib import Path


class YouTubeDownloadStrategy(Protocol):
    async def download_video(
        self,
        url: str,
        output_dir: Path,
        quality: str = "best",
    ) -> Path: ...
