"""Connection Manager"""
import asyncio
import xml.etree.ElementTree as ET
from typing import Dict
from async_upnp_client.client import UpnpStateVariable
from async_upnp_client.const import ServiceInfo

from async_upnp_client.server import UpnpServerService, callable_action
from async_upnp_client.server import create_template_var, create_state_var, create_event_var
from async_upnp_client.exceptions import UpnpActionError, UpnpActionErrorCode

# pylint: disable=too-many-arguments
# pylint: disable=invalid-name
# pylint: disable=unused-argument)

class ConnectionManagerService(UpnpServerService):
    """DLNA Connection Manager."""
    SERVICE_DEFINITION = ServiceInfo(
        service_id="urn:upnp-org:serviceId:ConnectionManager",
        service_type="urn:schemas-upnp-org:service:ConnectionManager:2",
        control_url="/upnp/control/ConnectionManager",
        event_sub_url="/upnp/event/ConnectionManager",
        scpd_url="/ConnectionManager.xml",
        xml=ET.Element("server_service"),
    )
    STATE_VARIABLE_DEFINITIONS = {
        "SourceProtocolInfo": create_event_var("string"),
        "SinkProtocolInfo": create_event_var("string"),
        "CurrentConnectionIDs": create_event_var("string"),
        "A_ARG_TYPE_ConnectionStatus": create_template_var("string"),
        "A_ARG_TYPE_ConnectionManager": create_template_var("string"),
        "A_ARG_TYPE_Direction": create_template_var("string"),
        "A_ARG_TYPE_ProtocolInfo": create_template_var("string"),
        "A_ARG_TYPE_ConnectionID": create_template_var("i4"),
        "A_ARG_TYPE_AVTransportID": create_template_var("i4"),
        "A_ARG_TYPE_ResID": create_template_var("i4"),
    }
    @callable_action(
        name="GetProtocolInfo",
        in_args={},
        out_args={
            "Source": "SourceProtocolInfo",
            "Sink": "SinkProtocolInfo",
        },
    )
    async def get_protocol_info(self) -> Dict[str, UpnpStateVariable]:
        return {
            "Source": self.state_variable('SourceProtocolInfo'),
            "Sink": self.state_variable('SinkProtocolInfo'),
            }
    @callable_action(
        name="GetCurrentConnectionIDs",
        in_args={},
        out_args={
            "ConnectionIDs": "CurrentConnectionIDs",
        },
    )
    async def get_current_connection_ids(self) -> Dict[str, UpnpStateVariable]:
        return {
            "ConnectionIDs": self.state_variable('CurrentConnectionIDs'),
            }
    @callable_action(
        name="GetCurrentConnectionInfo",
        in_args={
            'ConnectionID': 'A_ARG_TYPE_ConnectionID'
            },
        out_args={
            "ResID": "A_ARG_TYPE_ResID",
            "AVTransportID": "A_ARG_TYPE_AVTransportID",
            "ProtocolInfo": "A_ARG_TYPE_ProtocolInfo",
            "PeerConnectionManager": "A_ARG_TYPE_ConnectionManager",
        },
    )
    async def get_current_connection_info(self, ConnectionID: int) -> Dict[str, UpnpStateVariable]:
        return {
            "ResID": self.template_var("A_ARG_TYPE_ResID", ""),
            "AVTransportID": self.template_var("A_ARG_TYPE_AVTransportID", ""),
            "ProtocolInfo": self.template_var("A_ARG_TYPE_ProtocolInfo", ""),
            "PeerConnectionManager": self.template_var("A_ARG_TYPE_ConnectionManager", ""),
            }
