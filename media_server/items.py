"""Item types for ContentDirectory"""

# pylint: disable=too-few-public-methods
import asyncio
import os
import mimetypes
import xml.etree.ElementTree as ET
from datetime import datetime
from .namespace import get_ns

def get_url(item, mediatype):
    """Get full URL of item"""
    return f"{BaseItem.base_url}/content/{item.object_id}/{mediatype}"

def set_base_url(url):
    """Set the current URI as a static class variable for easy access"""
    BaseItem.base_url = url

class BaseItem:
    """Base item definition"""
    base_url = None
    next_id = 1000

    def __init__(self, parent, path, itemtype='item'):
        if parent:
            parent.add_child(self)
        self._parent = parent
        self._path = path
        if path:
            stat = os.stat(path)
            self._date = datetime.fromtimestamp(int(stat.st_mtime))
            self._size = stat.st_size
        else:
            self._date = datetime.fromtimestamp(0)
            self._size = 0
        self._type = itemtype
        self._cover = None
        self._id = BaseItem.next_id
        BaseItem.next_id += 1

    @property
    def object_id(self):
        """Object ID"""
        return self._id

    @property
    def parent(self):
        """Parent BaseItem"""
        return self._parent

    @property
    def name(self):
        """Item name"""
        return os.path.basename(self._path)

    async def get_path(self):
        """Item full path"""
        return self._path

    @property
    def size(self):
        """Item size"""
        return self._size

    async def xml(self):
        """Return XML describing item"""
        root = ET.Element(self._type, {'id': f'{self._id}', 'restricted': '0'})
        if self._parent:
            root.attrib['parentID'] = f'{self._parent.object_id}'
        ET.SubElement(root, 'dc:title').text = self.name
        ET.SubElement(root, 'dc:date').text = self._date.isoformat()
        if self._cover:
            # Cover art can be added as either
            #    <upnp:albumArtURI>
            #    or
            #    <res protocolInfo="http-get:*:image/jpeg:DLNA.ORG_PN=JPEG_TN;DLNA.ORG_OP=01;DLNA.ORG_CI=0">
            #    (or both)
            cover = ET.SubElement(root, 'upnp:albumArtURI', {'dlna:profileID': 'JPEG_TN'})
            cover.attrib.update(get_ns('dlna'))
            cover.text = get_url(self, "cover")
        return root

    def add_child(self, item):
        """Add a child item"""
        raise ValueError("Item doesn't support children")

class DirectoryItem(BaseItem):
    """Directory item"""
    def __init__(self, parent, path):
        super().__init__(parent, path, 'container')
        self._children = []
        self._update_id = 0

    def add_child(self, item):
        """Add a child item"""
        self._children.append(item)
        self._update_id += 1

    @property
    def children(self):
        """Return child objects"""
        return self._children.copy()

    async def xml(self):
        """Container description
        <container id=\"1001\" parentID=\"1000\" restricted=\"0\" childCount=\"33\">
          <dc:title>DIR_NAME</dc:title>
          <upnp:class>object.container</upnp:class>
          <dc:date>1999-09-19T04:12:00+02:00</dc:date>
          <upnp:albumArtURI
              xmlns:dlna=\"urn:schemas-dlna-org:metadata-1-0\"
              dlna:profileID=\"JPEG_TN\"
          >http://.../1001?cover.jpg</upnp:albumArtURI>
        </container>
        """
        root = await super().xml()
        root.attrib['childCount'] = f'{len(self._children)}'
        ET.SubElement(root, 'upnp:class').text = 'object.container'
        return root

    @property
    def update_id(self):
        """Get he number of times this item has changed"""
        return self._update_id

class AudioItem(BaseItem):
    """Audio  item"""
    def __init__(self, parent, path):
        super().__init__(parent, path)
        self._mimetype, _ = mimetypes.guess_type(path, strict=False)

    @property
    def mime_type(self):
        """Mime type"""
        return self._mimetype

    async def xml(self):
        """
        <item id=\"1030.flac\" parentID=\"1001\" restricted=\"0\">
          <dc:title>01. Sgt. Pepper's Lonely Hearts Club Band (Remix).flac</dc:title>
          <upnp:class>object.item.audioItem</upnp:class>
          <dc:date>2022-07-20T05:44:08</dc:date>
          <upnp:albumArtURI
           xmlns:dlna=\"urn:schemas-dlna-org:metadata-1-0\"
           dlna:profileID=\"JPEG_TN\"
          >http://{URL}/1030.flac?cover.jpg</upnp:albumArtURI>
          <res protocolInfo=\"http-get:*:audio/flac:*\" size=\"13866930\">
              http://{URL}/1030.flac
          </res>
          <res protocolInfo=\"internal:192.168.1.2:audio/flac:*\" size=\"13866930\">
              file://{PATH}
          </res>
        </item>
        """
        root = await super().xml()
        ET.SubElement(root, 'upnp:class').text = 'object.item.audioItem'
        protocol_info = f'http-get:*:{self._mimetype}:*'
        media = ET.SubElement(root, 'res', {'protocolInfo': protocol_info, 'size': f"{self._size}"})
        media.text = get_url(self, 'media')
        return root

class TranscodeItem(AudioItem):
    """Video item that will be transcoded on playback"""
    def __init__(self, parent, path, audio_extractor):
        super().__init__(parent, path)
        self._audio_extractor = audio_extractor
        self._probe = asyncio.create_task(audio_extractor.probe(path))
        self._mimetype = None
        self._audioext = None
        self._size = None

    async def get_path(self):
        """Get full-path to item"""
        path = await self._audio_extractor.get_path(self._path)
        if self._size is None:
            self._size = os.stat(path).st_size
        if self._mimetype is None:
            self._mimetype = self._mimetype, _ = mimetypes.guess_type(path)
        return path

    @property
    def size(self):
        """Item size"""
        if self._size is None:
            return 0
        return self._size

    @property
    def name(self):
        """Item name"""
        if self._audioext:
            return os.path.basename(self._path).rsplit('.', 1)[0] + f'.{self._audioext}'
        return super().name

    async def xml(self):
        """Create XML for item"""
        if self._probe:
            self._audioext = await self._probe
            self._probe = None
            self._mimetype, _ = mimetypes.guess_type(f"media_file.{self._audioext}", strict=False)
        return await super().xml()
