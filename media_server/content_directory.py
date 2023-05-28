"""Content Directory"""
import asyncio
import logging

from typing import Dict, Optional, Callable, Any, AsyncIterable, cast
from collections import defaultdict
import xml.etree.ElementTree as ET

from async_upnp_client.client import UpnpStateVariable, UpnpDevice, UpnpEventableStateVariable
from async_upnp_client.const import ServiceInfo

from async_upnp_client.server import UpnpServerService, callable_action
from async_upnp_client.server import create_template_var, create_state_var, create_event_var
from async_upnp_client.exceptions import UpnpActionError, UpnpActionErrorCode
from .items import BaseItem, DirectoryItem
from .namespace import get_ns

# pylint: disable=too-many-arguments
# pylint: disable=invalid-name
# pylint: disable=unused-argument)
FEATURE_STR = """<?xml version="1.0" encoding="UTF-8"?>
<Features
 xmlns="urn:schemas-upnp-org:av:avs"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 xsi:schemaLocation="
 urn:schemas-upnp-org:av:avs
 http://www.upnp.org/schemas/av/avs-v1-20060531.xsd">
</Features>"""

class ContentDirectoryService(UpnpServerService):
    """DLNA Content Directory."""
    SCANNER: Optional[Callable[[BaseItem, UpnpDevice], AsyncIterable[BaseItem]]] = None
    SERVICE_DEFINITION = ServiceInfo(
        service_id="urn:upnp-org:serviceId:ContentDirectory",
        service_type="urn:schemas-upnp-org:service:ContentDirectory:2",
        control_url="/upnp/control/ContentDirectory",
        event_sub_url="/upnp/event/ContentDirectory",
        scpd_url="/ContentDirectory.xml",
        xml=ET.Element("server_service"),
    )

    STATE_VARIABLE_DEFINITIONS = {
        "SearchCapabilities": create_state_var("string"),
        "SortCapabilities": create_state_var("string"),
        "SystemUpdateID": create_event_var("ui4", default="0"),
        "ContainerUpdateIDs": create_event_var("string"),
        "FeatureList": create_state_var("string", default=FEATURE_STR),
        "A_ARG_TYPE_BrowseFlag": create_template_var("string", allowed=["BrowseMetadata", "BrowseDirectChildren"]),
        "A_ARG_TYPE_Filter": create_template_var("string"),
        "A_ARG_TYPE_ObjectID": create_template_var("string"),
        "A_ARG_TYPE_Count": create_template_var("ui4"),
        "A_ARG_TYPE_Index": create_template_var("ui4"),
        "A_ARG_TYPE_SortCriteria": create_template_var("string"),
        ###
        "A_ARG_TYPE_Result": create_template_var("string"),
        "A_ARG_TYPE_UpdateID": create_template_var("ui4"),
    }

    @callable_action(
        name="Browse",
        in_args={
            "BrowseFlag": "A_ARG_TYPE_BrowseFlag",
            "Filter": "A_ARG_TYPE_Filter",
            "ObjectID": "A_ARG_TYPE_ObjectID",
            "RequestedCount": "A_ARG_TYPE_Count",
            "SortCriteria": "A_ARG_TYPE_SortCriteria",
            "StartingIndex": "A_ARG_TYPE_Index",
            },
        out_args={
            "Result": "A_ARG_TYPE_Result",
            "NumberReturned": "A_ARG_TYPE_Count",
            "TotalMatches": "A_ARG_TYPE_Count",
            "UpdateID": "A_ARG_TYPE_UpdateID",
        },
    )
    async def browse(self, BrowseFlag: str, Filter: str, ObjectID: str, StartingIndex: int,
                     RequestedCount: int, SortCriteria: str) -> Dict[str, UpnpStateVariable]:
        """Browse media."""
        await self._scan_task
        try:
            objectid = int(ObjectID)
            parent = self._item_map[objectid]
            assert isinstance(parent, DirectoryItem)
            root =  ET.Element("DIDL-Lite", get_ns('dc', 'upnp', 'DIDL-Lite'))
            for child in sorted(parent.children, key=lambda x: x.name):
                root.append(await child.xml())
            xml = ET.tostring(root).decode()
            if isinstance(parent, DirectoryItem):
                update_id = parent.update_id
            else:
                update_id = self.state_variable('SystemUpdateID').value
        except Exception as _e:
            raise UpnpActionError(
                error_code=UpnpActionErrorCode.INVALID_ACTION, error_desc=str(_e)
            ) from _e
        return {
            "Result": self.template_var("A_ARG_TYPE_Result", xml),
            "NumberReturned": self.template_var("A_ARG_TYPE_Count", len(parent.children)),
            "TotalMatches": self.template_var("A_ARG_TYPE_Count", len(parent.children)),
            "UpdateID": self.template_var("A_ARG_TYPE_UpdateID", update_id),
        }

    @callable_action(
        name="GetSearchCapabilities",
        in_args={},
        out_args={
            "SearchCaps": "SearchCapabilities",
        },
    )
    async def GetSearchCapabilities(self) -> Dict[str, UpnpStateVariable]:
        """Browse media."""
        return {
            "SearchCaps": self.state_variable("SearchCapabilities"),
        }

    @callable_action(
        name="GetSortCapabilities",
        in_args={},
        out_args={
            "SortCaps": "SortCapabilities",
        },
    )
    async def GetSortCapabilities(self) -> Dict[str, UpnpStateVariable]:
        """Browse media."""
        return {
            "SortCaps": self.state_variable("SortCapabilities"),
        }
    @callable_action(
        name="GetFeatureList",
        in_args={},
        out_args={
            "FeatureList": "FeatureList",
        },
    )
    async def GetFeatureList(self) -> Dict[str, UpnpStateVariable]:
        """Browse media."""
        return {
            "FeatureList": self.state_variable("FeatureList"),
        }
    @callable_action(
        name="GetSystemUpdateID",
        in_args={},
        out_args={
            "Id": "SystemUpdateID",
        },
    )
    async def get_system_update_id(self) -> Dict[str, UpnpStateVariable]:
        """Browse media."""
        return {
            "Id": self.state_variable("SystemUpdateID"),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize"""
        super().__init__(*args, **kwargs)
        self._root_item = DirectoryItem(None, None)
        self._item_map: Dict[int, BaseItem] = {0: self._root_item, self._root_item.object_id: self._root_item}
        self._scan_task = asyncio.create_task(self._start_scan())

    async def _start_scan(self) -> None:
        if not self.SCANNER:
            return
        updates: Dict[int, int] = defaultdict(int)
        system_update_id = self.state_variable('SystemUpdateID')
        container_update_ids = cast(UpnpEventableStateVariable, self.state_variable('ContainerUpdateIDs'))
        async for item in self.SCANNER(self._root_item, self.device):  # pylint: disable=not-callable
            if container_update_ids.event_triggered.is_set():
                updates.clear()
                container_update_ids.event_triggered.clear()
            self._item_map[item.object_id] = item
            updates[item.parent.object_id] = item.parent.update_id
            container_update_ids.value = self.build_container_update_ids(updates)
            system_update_id.value += 1  # type: ignore [operator]
        logging.debug("Done scanning")

    def get_item(self, object_id: int) -> Optional[BaseItem]:
        """Get item from object_id."""
        return self._item_map.get(object_id)

    @staticmethod
    def build_container_update_ids(updates: dict[int, int]) -> Any:
        """Create CSV value for ContainerUpdateIDs"""
        return ",".join([f"{_id},{_val}" for _id, _val in updates.items()])
