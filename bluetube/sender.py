"""Functions for send a publication to specified local or remote destination."""


import os
import shutil
from bluetube.bluetoothclient import BluetoothClient
from bluetube.cli.events import Error
from bluetube.model import Publication, PublicationStatus

ACCESS_MODE = 0o744
senders = {}


def send(pub: Publication, configs) -> Publication:
    """Send files to a destination specified in configs."""

    # send via bluetooth
    device_id = configs.get('bluetooth_device_id')
    if device_id:
        sent = _send_bt(device_id, [pub.local_path])
        if sent:
            pub.local_path.unlink()
            pub.local_path = None
            pub.status = PublicationStatus.sent
            return pub

    # move to local directory
    local_path = configs.get('local_path')
    if local_path:
        try:
            os.makedirs(local_path,
                        ACCESS_MODE,
                        exist_ok=True)
        except PermissionError as e:
            # notify(Error(e))  #TODO fix
            pass
        _move_to_local_path(local_path, pub.local_path)
        pub.local_path.unlink()
        pub.local_path = None
        pub.status = PublicationStatus.sent
        return pub

    return pub

def _send_bt(device_id, links):
    '''sent all files defined by the links
    to the device defined by device_id'''
    # TODO under construction
    sent = []
    sender = _get_sender(device_id)
    if sender and sender.found and sender.connect():
        sent += sender.send(links)
        sender.disconnect()
    return sent


def _get_sender(self, device_id):
    '''return a sender from the cache for a device ID if possible
    or create a new one'''
    if device_id in self.senders:
        return self.senders[device_id]
    else:
        sender = BluetoothClient(device_id, self.temp_dir)
        if not sender.found:
            self.notify(Error('device not found'))  # TODO fix self
            return None
        else:
            self.senders[device_id] = sender
            return sender


def _move_to_local_path(local_path, pub_local_path):
    '''move files defined by links to the local path'''

    # self._debug(f'copying {pub_local_path} to {local_path}')
    try:
        shutil.move(pub_local_path, local_path)
    except shutil.SameFileError as e:
        # self.notify(Error(e))  # TODO: fix
        pass
