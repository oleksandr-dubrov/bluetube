import os
import socket
import sys
import time

import bluetooth
from PyOBEX import headers, requests, responses
from PyOBEX.client import Client

from bluetube.cli.cli import Error, Warn

'''
    This file is part of Bluetube.

    Bluetube is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Bluetube is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with Bluetube.  If not, see <https://www.gnu.org/licenses/>.
'''


class BluetoothClient(Client):
    '''Sends files to the given device'''

    SOCKETTIMEOUT = 120.0

    def __init__(self, event_listener, device_id, bluetube_dir):
        self.found = self._find_device(device_id)
        self._event_listener = event_listener
        if self.found:
            print(f'Checking connection to "{self.name}" on "{self.host}"')
            # Client is old style class, so don't use super
            Client.__init__(self, self.host, self.port)
            self.bluetube_dir = bluetube_dir
            self.in_progress = False
        else:
            self._event_listener.update(
                Error(f'Device {device_id} is not found.'))

    def _find_device(self, device_id):
        service_matches = bluetooth.find_service(address=device_id)
        if len(service_matches) == 0:
            self._event_listener.update(Error("Couldn't find the service."))
            return False

        for s in service_matches:
            if s['name'] == 'OBEX Object Push':
                first_match = s
                break

        self.name = bluetooth.lookup_name(device_id)
        self.host = first_match["host"]
        self.port = first_match["port"]
        return True

    def _callback(self, resp, filename):
        if resp:
            if self.in_progress:
                sys.stdout.write('.')
            else:
                if len(filename) > 45:
                    filename = filename[:42] + '...'
                sys.stdout.write(f'[sending] "{filename}" to {self.name}...')
                self.in_progress = True
            sys.stdout.flush()

    def _put(self, name, file_data, header_list=()):
        '''Modify the method from the base class
        to allow getting data from the file stream.'''

        header_list = [
            headers.Name(name),
            headers.Length(os.path.getsize(file_data))
            ] + list(header_list)

        max_length = self.remote_info.max_packet_length
        request = requests.Put()

        response = self._send_headers(request, header_list, max_length)
        yield response

        if not isinstance(response, responses.Continue):
            return

        optimum_size = max_length - 3 - 3

        i = 0
        size = os.path.getsize(file_data)
        while i < size:

            data = self.file_data_stream.read(optimum_size)
            i += len(data)
            if i < size:
                request = requests.Put()
                request.add_header(headers.Body(data, False), max_length)
                self.socket.sendall(request.encode())

                response = self.response_handler.decode(self.socket)
                yield response

                if not isinstance(response, responses.Continue):
                    return
            else:
                request = requests.Put_Final()
                request.add_header(headers.End_Of_Body(data, False),
                                   max_length)
                self.socket.sendall(request.encode())

                response = self.response_handler.decode(self.socket)
                yield response

                if not isinstance(response, responses.Success):
                    return

    def send(self, filenames):
        '''Sends files to the bluetooth device.
        Returns file names that has been sent.'''
        assert self.found, 'Device is not found. Create a new Bluetooth.'
        sent = []
        for fm in filenames:
            full_path = os.path.join(self.bluetube_dir, fm)
            self.file_data_stream = open(full_path, 'rb')
            try:
                base_fm = os.path.basename(fm)
                resp = self.put(base_fm,
                                full_path,
                                callback=lambda resp: self._callback(resp,
                                                                     base_fm))
                assert not resp, "No response expected (a callback is used)."
                print('\n{} sent.'.format(base_fm))
                sent.append(full_path)
            except socket.error as e:
                self._event_listener.update(Error(str(e)))
                self._event_listener.update(Error(f"{base_fm} didn't send"))
                print('Trying to reconnect...')
                self.socket.shutdown(socket.SHUT_RDWR)
                self.socket.close()
                del self.socket
                time.sleep(10.0)
                if not self.connect():
                    break
                else:
                    sent += self.send([fm, ])
            except KeyboardInterrupt:
                msg = f'Sending of {base_fm} stopped ' +\
                    'because of KeyboardInterrupt'
                self._event_listener.update(Error(msg))
            finally:
                self.in_progress = False
                self.file_data_stream.close()
        return sent

    def connect(self):
        status = False
        try:
            Client.connect(self)
            self.socket.settimeout(BluetoothClient.SOCKETTIMEOUT)
            status = True
        except socket.error as e:
            self._event_listener.update(Error(str(e)))
            self._event_listener.update(Warn('Some files will not be sent.'))
        return status

    def disconnect(self):
        try:
            Client.disconnect(self)
            #  print(resp)
        except (socket.error, socket.timeout) as e:
            self._event_listener.update(Error(str(e)))
            self._event_listener.update(Warn('Wait a minute.'))
            time.sleep(60.0)
