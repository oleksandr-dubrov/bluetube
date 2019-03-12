import os
import sys

import bluetooth  # @UnresolvedImport
import socket
import time
from PyOBEX.client import Client  # @UnresolvedImport
from PyOBEX import headers
from PyOBEX import requests
from PyOBEX import responses

from bcolors import Bcolors


class BluetoothClient(Client):
    '''Sends files to the given device'''

    SOCKETTIMEOUT = 120.0

    def __init__(self, device_id, bluetube_dir):
        self.found = self._find_device(device_id)
        if self.found:
            print("Checking connection to \"%s\" on %s" % (self.name, self.host))
            # Client is old style class, so don't use super
            Client.__init__(self, self.host, self.port)
            self.bluetube_dir = bluetube_dir
            self.in_progress = False
        else:
            Bcolors.error('Device {} is not found.'.format(device_id))

    def _find_device(self, device_id):
        service_matches = bluetooth.find_service(address = device_id)
        if len(service_matches) == 0:
            Bcolors.error("Couldn't find the service.")
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
                filename = filename.decode('utf-8')
                if len(filename) > 45:
                    filename = filename[:42] + '...'
                sys.stdout.write(u'Sending "{}" to {}...'.format(filename,
                                                                 self.name))
                self.in_progress = True
            sys.stdout.flush()

    def _put(self, name, file_data, header_list = ()):  # @UnusedVariable
        '''Modify the method from the base class
        to allow getting data from the file stream.'''

        header_list = [
            headers.Name(name),
            headers.Length(os.path.getsize(file_data))
            ]

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
                request.add_header(headers.End_Of_Body(data, False), max_length)
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
                resp = self.put(fm.decode('utf-8'),
                                full_path,
                                callback=lambda resp : self._callback(resp, fm))
                if resp:
                    pass  # print(resp)
                else:
                    print(u'\n{} sent.'.format(fm.decode('utf-8')))
                    sent.append(full_path)
            except socket.error as e:
                Bcolors.error(str(e))
                Bcolors.error(u'{} didn\'t send'.format(fm.decode('utf-8')))
                print('Trying to reconnect...')
                self.socket.shutdown(socket.SHUT_RDWR)
                self.socket.close()
                del self.socket
                time.sleep(10.0)
                if not self.connect():
                    break
                else:
                    self.send([fm, ])
            except KeyboardInterrupt:
                Bcolors.error(u'Sending of {} stopped because of KeyboardInterrupt'
                                .format(fm.decode('utf-8')))
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
            Bcolors.error(str(e))
            Bcolors.warn('Some files will not be sent.')
        return status

    def disconnect(self):
        try:
            Client.disconnect(self)
            #  print(resp)
        except socket.errno as e:
            Bcolors.error(str(e))
            Bcolors.warn('Wait a minute.')
            time.sleep(60.0)
