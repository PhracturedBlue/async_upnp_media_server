"""Create BaseItems for file paths"""
import os
import logging
import mimetypes
from typing import List, Dict

from .items import BaseItem, DirectoryItem, TranscodeItem, AudioItem

async def scan_paths(paths: List[str], root_item):
    """Async generator to generate BaseItems"""
    for path in paths:
        dir_cache:Dict[str, BaseItem] = {}
        if path.endswith('/') and path != '/':
            path = path[:-1]
        for root, sub_dirs, files in os.walk(path):
            if not files and not sub_dirs:
                continue
            if root == path:
                parent = root_item
            else:
                parent = dir_cache[os.path.dirname(root)]
            item: BaseItem = DirectoryItem(parent, root)
            dir_cache[root] = item
            yield item
            for file in files:
                full_path = os.path.join(root, file)
                mime_type, _ = mimetypes.guess_type(file, strict=False)
                if not mime_type:
                    continue
                if mime_type.startswith('video/'):
                    child = TranscodeItem(item, full_path)
                elif mime_type.startswith("audio/"):
                    child = AudioItem(item, full_path)
                else:
                    continue
                logging.debug(f"Adding {item}: {full_path}")
                yield child
