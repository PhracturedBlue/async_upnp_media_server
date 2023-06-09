"""Media Server Device"""
# Many parts of this are based upon https://github.com/shaolo1/VideoServer

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
import argparse

from time import time
from functools import partial
from http import HTTPStatus
from typing import cast, Callable, Type, Tuple, Optional, Union
from aiohttp import web
from multidict import CIMultiDictProxy

from async_generator import async_generator, yield_  # type: ignore [import]

from async_upnp_client.client import UpnpRequester
from async_upnp_client.const import DeviceInfo
from async_upnp_client.server import UpnpServer, UpnpServerDevice
from .items import set_base_url, AudioItem
from .content_directory import ContentDirectoryService
from .connection_manager import ConnectionManagerService
from .scan_paths import scan_paths
from .audio_extract import AudioExtractor

SOURCE = ("192.168.1.85", 0)  # Your IP here!
HTTP_PORT = 8000

class MediaServerDevice(UpnpServerDevice):
    """Media Server Device."""

    DEVICE_DEFINITION = DeviceInfo(
        device_type="urn:schemas-upnp-org:device:MediaServer:2",
        friendly_name="Media Server v1",
        manufacturer="Steven",
        manufacturer_url=None,
        model_name="MediaServer v1",
        model_url=None,
        udn="uuid:1cd38bfe-3c10-403e-a97f-2bc5c1652b9a",
        upc=None,
        model_description="Media Server",
        model_number="v0.0.1",
        serial_number="0000001",
        presentation_url=None,
        url="/device.xml",
        icons=[],
        xml=ET.Element("server_device"),
    )
    EMBEDDED_DEVICES = []
    SERVICES = [ConnectionManagerService, ContentDirectoryService]
    _routes = web.RouteTableDef()

    def __init__(self, audio_extractor_cls: Callable[[], None], requester: UpnpRequester,
                 base_uri: str, boot_id: int, config_id: int) -> None:
        """Initialize."""
        # pylint: disable=(too-many-arguments)
        super().__init__(
            requester=requester,
            base_uri=base_uri,
            boot_id=boot_id,
            config_id=config_id,
        )
        set_base_url(base_uri)
        # route decorator doesn't support instance-methods natively
        # so convert static-method call to instance method call here
        self.ROUTES = [  # pylint: disable=invalid-name
            web.RouteDef(route.method, route.path, partial(route.handler, self), route.kwargs)  # type: ignore [attr-defined]
            for route in self._routes]
        self._content_dir = next(svc for svc in self.services.values() if isinstance(svc, ContentDirectoryService))
        self.audio_extractor = audio_extractor_cls()

    @_routes.get(r"/content/{object_id:\d+}/{media_type}")   # type: ignore [arg-type]
    async def handle_media(self, request: web.Request) -> Union[web.Response, web.FileResponse]:
        """URL handler for streaming media"""
        object_id = int(request.match_info['object_id'])
        media_type = request.match_info['media_type']
        item = self._content_dir.get_item(object_id)
        if not item:
            raise web.HTTPNotFound
        if not isinstance(item, AudioItem):
            logging.error("Tried to query  %s media item: %s", item.__class__.__name__, item.name)
            raise web.HTTPNotFound
        if request.method == 'HEAD':
            raise web.HTTPOk()
        if media_type == 'cover':
            if item.cover:
                return web.FileResponse(item.cover)
            raise web.HTTPNotFound

        _path = await item.get_path()

        @async_generator
        async def generate(chunk_size: int=2**16) -> None:
            # Default to 64k chunks
            with open(_path, 'rb') as _f:
                _f.seek(start)
                for data in iter(partial(_f.read, chunk_size), b''):
                    await yield_(data)

        if not _path:
            raise web.HTTPNotFound
        part, start, end = self.get_range(request.headers)
        mime_type = item.mime_type
        end = item.size if end is None else end
        size = str(end-start)
        if not mime_type:
            raise web.HTTPNotFound

        headers: dict[str, str] = {'Content-Length': size, 'Content-Type': mime_type, 'Accept-Ranges': 'bytes',
                   # DLNA.ORG_OP = Time range capable / Byte range capable
                   'Contentfeatures.dlna.org': 'DLNA.ORG_OP=01'  # TV will try to read entire file without this
                   }
        if part:
            headers['Content-Range'] = f'bytes {start}-{end-1}/{size}'
        print(headers)
        logging.info("Playing: %s", item.name)
        response = web.Response(
            body=generate(),
            status=HTTPStatus.PARTIAL_CONTENT if part else HTTPStatus.OK, headers=headers)
        return response

    @staticmethod
    def get_range(headers: CIMultiDictProxy[str]) -> Tuple[bool, int, Optional[int]]:
        """Get requested byte range from headers"""
        byte_range = headers.get('Range', headers.get('range'))
        match = None if not byte_range else re.match(r'bytes=(?P<start>\d+)-(?P<end>\d+)?', byte_range)
        if not match:
            return False, 0, None
        start = match.group('start')
        end = match.group('end')
        start = int(start)
        if end is not None:
            end = int(end)
        return True, start, end

async def async_main(server: UpnpServer) -> None:
    """Async entrypoint."""
    await server.async_start()
    while True:
        await asyncio.sleep(3600)

def main() -> None:
    """Entrypoint"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--media", required=True, nargs='+', help="Media paths to serve")
    parser.add_argument("--host", required=True, help="Host IP address to listen on")
    parser.add_argument("--port", type=int, default = 8000, help="Port to listen on")
    parser.add_argument("--dbfile", default="cache.sqlite", help="Database file for caching audio-extractor")
    parser.add_argument("--cache_dir", default="/tmp/audio_cache", help="Directory for audio-extractor to chache files")
    parser.add_argument("--max-cache-size", type=int, default=1_000_000_000, help="Maximum cache size for auido-extractor")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    logging.getLogger("async_upnp_client.traffic").setLevel(logging.WARNING)

    boot_id = int(time())
    config_id = 1
    audio_extractor_partial = partial(AudioExtractor, args.dbfile, args.cache_dir, args.max_cache_size)
    msd_partial = cast(Type[UpnpServerDevice], partial(MediaServerDevice, audio_extractor_partial))
    ContentDirectoryService.SCANNER = partial(scan_paths, args.media)
    server = UpnpServer(msd_partial, (args.host, 0), http_port=args.port, boot_id=boot_id, config_id=config_id)

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(async_main(server))
    except KeyboardInterrupt:
        print("KeyboardInterrupt")
    loop.run_until_complete(server.async_stop())
