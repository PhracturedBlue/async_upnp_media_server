"""Transcode engine"""
import os
import re
import hashlib
import logging
import time
import asyncio
import sqlite3
# pylint: disable=broad-except

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FFPROBE = os.path.join(BASE_DIR, "ffprobe")
FFMPEG = os.path.join(BASE_DIR, "ffmpeg")

class AudioExtractor:
    """Transcoder"""

    def __init__(self, db_file, cache_dir, max_size):
        self._semaphore = asyncio.Semaphore(10)
        self._cache_dir = cache_dir
        self._max_cache_size = max_size
        self._db = sqlite3.connect(db_file)
        self._cur =self._db.cursor()
        self._cleanup = asyncio.create_task(self.run_cleanup())
        self._running = {}
        os.makedirs(cache_dir, exist_ok=True)
        self._cur.execute("CREATE TABLE IF NOT EXISTS media ("
            "path TEXT PRIMARY KEY,"
            "mediatype TEXT,"
            "cache TEXT"
            ")")
    def get_item(self, path):
        """Get mediatype and path for extracted audio"""
        for row in self._cur.execute("SELECT mediatype, cache FROM media WHERE path = ?", (path,)):
            return row
        return None, None

    async def get_path(self, path):
        """Get path to audio file.  Create if needed"""
        audio_type, cache_path = self.get_item(path)
        if path in self._running:
            try:
                await self._running[path].wait()
                del self._running[path]
            except Exception:
                pass
        if not cache_path or not os.path.exists(cache_path):
            cache_path = await self.extract_audio(path, audio_type)
        os.utime(cache_path)  # keep on top of the LRU list
        return cache_path

    async def extract_audio(self, path, audio_type):
        """Extract audio-stream from video file"""
        if self._cleanup:
            if self._cleanup.done():
                await self._cleanup
                self._cleanup = None
        if not self._cleanup:
            self._cleanup = asyncio.create_task(self.run_cleanup())

        cache_file = self._get_cache_file(path, audio_type)
        self._running[path] = asyncio.Event()
        try:
            tmpname = os.path.join(self._cache_dir, "tmp." + os.path.basename(cache_file))
            if os.path.exists(tmpname):
                os.unlink(tmpname)
            proc = await asyncio.create_subprocess_exec(FFMPEG, "-i", path, "-vn", "-c:a", "copy", tmpname)
            await proc.wait()
            if os.path.exists(tmpname):
                os.rename(tmpname, cache_file)
                self._cur.execute("UPDATE media SET cache = ? WHERE path = ?", (cache_file, path))
                self._db.commit()
                self._running[path].set()
                return cache_file
        except Exception as _e:
            logging.error("Failed to extract audio for %s: %s", path, _e)
        return None

    async def run_cleanup(self):
        """Cleanup LRU files in cache dir"""
        paths = sorted(os.scandir(self._cache_dir), key=lambda x: x.stat().st_mtime)
        while sum(_.stat().st_size for _ in paths) > self._max_cache_size:
            item = paths.pop()
            if item.stat().st_mtime > time.time() - 600:
                break
            os.unlink(item.path)

    async def probe(self, path):
        """Probe Video file to get audio format"""
        audio_type, _ = self.get_item(path)
        if audio_type:
            return audio_type
        async with self._semaphore:
            try:
                proc = await asyncio.create_subprocess_exec(FFPROBE, path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                _stdout_data, stderr_data = await proc.communicate()
                await proc.wait()
            except Exception as _e:
                logging.error("Failed to run ffprobe %s: %s", path, _e)
        if proc.returncode != 0:
            logging.error("Failed to run ffprobe %s: %s", path, stderr_data)
            return
        _match = re.search(r'Stream #.*: Audio: (\S+)', stderr_data.decode(), re.MULTILINE)
        if _match:
            audio_type = _match.group(1)
            self._cur.execute("INSERT OR REPLACE INTO media (mediatype, path) VALUES (?, ?)", (audio_type, path))
            self._db.commit()
        return audio_type

    def _get_cache_file(self, path, audio_type):
        return os.path.join(self._cache_dir,
            os.path.basename(path) + "." + hashlib.sha256(os.path.dirname(path).encode()).hexdigest()[:8] + "." + audio_type)
