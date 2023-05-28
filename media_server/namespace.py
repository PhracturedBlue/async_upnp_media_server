"""Define common namespaces"""

NAMESPACES = {
    'xmlns:dc': 'http://purl.org/dc/elements/1.1/',
    'xmlns:dlna': 'urn:schemas-dlna-org:metadata-1-0',
    'xmlns:upnp': 'urn:schemas-upnp-org:metadata-1-0/upnp/',
    'DIDL-Lite': 'urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/',
}

def get_ns(*namespaces):
    """Helper to return pre-defined XML namespaces"""
    res = {}
    for ns_ in namespaces:
        if val := NAMESPACES.get(f'xmlns:{ns_}'):
            res[f'xmlns:{ns_}'] = val
        elif val:= NAMESPACES.get(ns_):
            res['xmlns'] = val
        else:
            raise KeyError(f'{ns_} is not a valid namespace')
    return res
