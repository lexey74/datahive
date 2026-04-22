import pytest
from unittest.mock import patch

from src.modules.youtube_grabber_v2 import ImprovedCookieManager
from src.modules.youtube_video_downloader import (
    YouTubeVideoDownloader,
    YouTubeVideoResult,
)
from src.modules.youtube_shorts_downloader import YouTubeShortsDownloader
from src.modules.downloader_base import DownloadSettings, YouTubeContentType


class TestYouTubeDownloaders:
    @pytest.fixture
    def settings(self, tmp_path):
        return DownloadSettings(youtube_cookies_dir=tmp_path / "cookies")

    @pytest.fixture
    def video_downloader(self, settings):
        with patch(
            "src.modules.youtube_downloader_base.ProductionYouTubeGrabber"
        ) as mock_grabber:
            downloader = YouTubeVideoDownloader(settings)
            downloader.grabber = mock_grabber.return_value
            return downloader

    @pytest.fixture
    def shorts_downloader(self, settings):
        with patch(
            "src.modules.youtube_downloader_base.ProductionYouTubeGrabber"
        ) as mock_grabber:
            downloader = YouTubeShortsDownloader(settings)
            downloader.grabber = mock_grabber.return_value
            return downloader

    def test_can_handle_video(self, video_downloader):
        assert video_downloader.can_handle(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )
        assert video_downloader.can_handle("https://youtu.be/dQw4w9WgXcQ")
        assert not video_downloader.can_handle(
            "https://www.youtube.com/shorts/dQw4w9WgXcQ"
        )

    def test_can_handle_shorts(self, shorts_downloader):
        assert shorts_downloader.can_handle(
            "https://www.youtube.com/shorts/dQw4w9WgXcQ"
        )
        assert not shorts_downloader.can_handle(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )

    def test_loads_youtube_cookies_from_directory_with_real_filename(self, tmp_path):
        cookies_dir = tmp_path / "cookies"
        cookies_dir.mkdir()
        youtube_cookie = cookies_dir / "www.youtube.com_cookies.txt"
        youtube_cookie.write_text("youtube", encoding="utf-8")
        instagram_cookie = cookies_dir / "instagram_cookies.txt"
        instagram_cookie.write_text("instagram", encoding="utf-8")

        settings = DownloadSettings(youtube_cookies_dir=cookies_dir)

        with patch(
            "src.modules.youtube_downloader_base.ProductionYouTubeGrabber"
        ) as mock_grabber:
            YouTubeVideoDownloader(settings)

        cookie_manager = mock_grabber.call_args.kwargs["cookie_manager"]
        assert isinstance(cookie_manager, ImprovedCookieManager)
        assert youtube_cookie.name in cookie_manager.stats
        assert instagram_cookie.name not in cookie_manager.stats

    def test_merges_direct_cookie_with_directory_pool(self, tmp_path):
        cookies_dir = tmp_path / "cookies"
        cookies_dir.mkdir()
        directory_cookie = cookies_dir / "www.youtube.com_cookies.txt"
        directory_cookie.write_text("youtube-dir", encoding="utf-8")
        direct_cookie = tmp_path / "yt_cookies.txt"
        direct_cookie.write_text("youtube-direct", encoding="utf-8")

        settings = DownloadSettings(
            youtube_cookies=direct_cookie,
            youtube_cookies_dir=cookies_dir,
        )

        with patch(
            "src.modules.youtube_downloader_base.ProductionYouTubeGrabber"
        ) as mock_grabber:
            YouTubeVideoDownloader(settings)

        cookie_manager = mock_grabber.call_args.kwargs["cookie_manager"]
        assert isinstance(cookie_manager, ImprovedCookieManager)
        assert directory_cookie.name in cookie_manager.stats
        assert direct_cookie.name in cookie_manager.stats

    @patch("src.modules.downloader_base.BaseDownloader.create_folder")
    @patch("src.modules.downloader_base.BaseDownloader.save_description")
    def test_download_video_success(
        self, mock_save_desc, mock_create_folder, video_downloader, tmp_path
    ):
        # Mock create folder to return a valid path
        mock_create_folder.return_value = (
            tmp_path / "downloads/youtube_channel_VideoID_Title"
        )
        mock_save_desc.return_value = tmp_path / "description.md"

        # Mock grabber methods
        video_downloader.grabber.get_metadata.return_value = {
            "title": "Test Video",
            "channel": "Test Channel",
            "view_count": 1000,
            "like_count": 100,
            "duration": 600,
            "upload_date": "2024-01-01",
            "description": "Test Description",
        }

        # Mock download_video returning a path
        video_path = mock_create_folder.return_value / "video.mp4"
        video_downloader.grabber.download_video.return_value = video_path

        # Mock subtitles
        video_downloader.grabber.download_subtitles.return_value = []
        video_downloader.grabber.get_comments.return_value = []

        result = video_downloader.download(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )

        assert isinstance(result, YouTubeVideoResult)
        assert result.content_type == YouTubeContentType.VIDEO
        assert result.channel == "Test Channel"
        assert result.views == 1000

        # Verify grabber calls
        video_downloader.grabber.get_metadata.assert_called_once()
        video_downloader.grabber.download_video.assert_called_once()

    @patch("src.modules.downloader_base.BaseDownloader.create_folder")
    @patch("src.modules.downloader_base.BaseDownloader.save_description")
    def test_download_shorts_success(
        self, mock_save_desc, mock_create_folder, shorts_downloader, tmp_path
    ):
        # Mock create folder
        mock_create_folder.return_value = (
            tmp_path / "downloads/youtube_shorts_channel_ShortID_Title"
        )
        mock_save_desc.return_value = tmp_path / "description.md"

        # Mock grabber methods
        shorts_downloader.grabber.get_metadata.return_value = {
            "title": "Test Short",
            "channel": "Test Channel",
            "view_count": 5000,
            "like_count": 500,
            "duration": 59,
            "upload_date": "2024-01-01",
            "description": "Short Description",
        }

        video_path = mock_create_folder.return_value / "short.mp4"
        shorts_downloader.grabber.download_video.return_value = video_path
        shorts_downloader.grabber.get_comments.return_value = []

        result = shorts_downloader.download(
            "https://www.youtube.com/shorts/dQw4w9WgXcQ"
        )

        assert isinstance(result, YouTubeVideoResult)
        assert result.content_type == YouTubeContentType.SHORT
        assert result.channel == "Test Channel"

        # Verify calls
        shorts_downloader.grabber.get_metadata.assert_called_once()
        shorts_downloader.grabber.download_video.assert_called_once()
