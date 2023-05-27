"""Media Server Device"""
import asyncio
import logging
import re
import xml.etree.ElementTree as ET

from time import time
from functools import partial
from http import HTTPStatus

from aiohttp import web
from async_generator import async_generator, yield_

from async_upnp_client.client import UpnpRequester
from async_upnp_client.const import DeviceInfo
from async_upnp_client.server import UpnpServer, UpnpServerDevice
from .items import set_base_url
from .content_directory import ContentDirectoryService
from .connection_manager import ConnectionManagerService
from .scan_paths import scan_paths

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

    def __init__(self, requester: UpnpRequester, base_uri: str, boot_id: int, config_id: int) -> None:
        """Initialize."""
        super().__init__(
            requester=requester,
            base_uri=base_uri,
            boot_id=boot_id,
            config_id=config_id,
        )
        # route decorator doesn't support instance-methods natively
        # so convert static-method call to instance method call here
        self.ROUTES =[web.RouteDef(route.method, route.path, partial(route.handler, self), route.kwargs) for route in self._routes]
        self._content_dir = next(svc for svc in self.services.values() if isinstance(svc, ContentDirectoryService))

    @_routes.get("/content/{object_id:\d+}/{media_type}")
    async def handle_media(self, request: web.Request) -> web.Response:
        object_id = int(request.match_info['object_id'])
        media_type = request.match_info['media_type']
        item = self._content_dir.get_item(object_id)
        if not item:
            raise web.HTTPNotFound
            
        @async_generator
        async def generate(chunk_size=2**16):  # Default to 64k chunks
            with open(_path, 'rb') as f:
                f.seek(start)
                for data in iter(partial(f.read, chunk_size), b''):
                    await yield_(data)

        _path = item.path
        part, start, end = self.get_range(request.headers)
        mime_type = item.mime_type
        end = item.size if end is None else end
        size = str(end-start)

        headers = {'Content-Length': size, 'Content-Type': mime_type, 'Accept-Ranges': 'bytes',
                   # DLNA.ORG_OP = Time range capable / Byte range capable
                   'Contentfeatures.dlna.org': 'DLNA.ORG_OP=01'  # TV will try to read entire file without this
                   }
        if part:
            headers['Content-Range'] = f'bytes {start}-{end-1}/{size}'
        response = web.Response(body=generate(), status=HTTPStatus.PARTIAL_CONTENT if part else HTTPStatus.OK, headers=headers)#, direct_passthrough=True)
        return response

    @staticmethod
    def get_range(headers):
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

async def async_main(server):
    """Async entrypoint."""
    await server.async_start()
    while True:
        await asyncio.sleep(3600)

def main():
    """Entrypoint"""
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger("async_upnp_client.traffic").setLevel(logging.WARNING)
    boot_id = int(time())
    config_id = 1
    set_base_url(f"http://{SOURCE[0]}:{HTTP_PORT}")

    ContentDirectoryService.SCANNER = partial(scan_paths, ["/mnt/music/FLAC/"])
    server = UpnpServer(MediaServerDevice, SOURCE, http_port=HTTP_PORT, boot_id=boot_id, config_id=config_id)
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(async_main(server))
    except KeyboardInterrupt:
        print("KeyboardInterrupt")
    loop.run_until_complete(server.async_stop())
