"""Connection Manager"""
import xml.etree.ElementTree as ET
from typing import Dict
from async_upnp_client.client import UpnpStateVariable
from async_upnp_client.const import ServiceInfo

from async_upnp_client.server import UpnpServerService, callable_action
from async_upnp_client.server import create_template_var, create_event_var

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
        "SourceProtocolInfo": create_event_var("string",
            default=','.join([f'http-get:*:audio/{_}:*' for _ in ('mpeg', 'ac3', 'aac', 'ogg', 'eac3')])),
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
        """Get supported protocols"""
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
        """Get current connections"""
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
        """Get current conntion information"""
        return {
            "ResID": self.template_var("A_ARG_TYPE_ResID", ""),
            "AVTransportID": self.template_var("A_ARG_TYPE_AVTransportID", ""),
            "ProtocolInfo": self.template_var("A_ARG_TYPE_ProtocolInfo", ""),
            "PeerConnectionManager": self.template_var("A_ARG_TYPE_ConnectionManager", ""),
            }
    @callable_action(
        name="PrepareForConnection",
        in_args={
            'RemoteProtocolInfo': 'A_ARG_TYPE_ProtocolInfo',
            'PeerConnectionManager': 'A_ARG_TYPE_ConnectionManager',
            'PeerConnectionID': 'A_ARG_TYPE_ConnectionID',
            'Direction': 'A_ARG_TYPE_Direction',
            },
        out_args={
            'ConnectionID': 'A_ARG_TYPE_ConnectionID',
            'AVTransportID': 'A_ARG_TYPE_AVTransportID',
            'ResID': 'A_ARG_TYPE_ResID',
        },
    )
    async def prepare_for_connection(self,
            RemoteProtocolInfo: str, PeerConnectionManager: str,
            PeerConnectionID: int, Direction: str) -> Dict[str, UpnpStateVariable]:
        """Get current conntion information"""
        return {
            'ConnectionID': self.template_var('A_ARG_TYPE_ConnectionID', 1),
            'AVTransportID': self.template_var('A_ARG_TYPE_AVTransportID', 1),
            'ResID': self.template_var('A_ARG_TYPE_ResID', 1),
            }
    @callable_action(
        name="ConnectionCompleted",
        in_args={
            'ConnectionID': 'A_ARG_TYPE_ConnectionID',
        },
        out_args = {},
    )
    async def connection_completed(self, ConnectionID: int) -> Dict[str, UpnpStateVariable]:
        """Get current conntion information"""
        return {}
