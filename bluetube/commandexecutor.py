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

import os
import subprocess


class CommandExecutor(object):
    '''This class run the commands in the shell'''

    def __init__(self, verbose):
        self._verbose = verbose

    def call(self, args, cwd=None,
             suppress_stdout=False, suppress_stderr=False):
        if cwd is None:
            cwd = os.getcwd()
        call_env = os.environ
        return_code = 0
        stdout, stderr = None, None
        try:
            if self._verbose:
                print('RUN: {}'.format([a for a in args]))
            if suppress_stdout:
                stdout = open(os.devnull, 'wb')
            if suppress_stderr:
                stderr = open(os.devnull, 'wb')
            return_code = subprocess.call(args,
                                          env=call_env,
                                          stdout=stdout,
                                          stderr=stderr,
                                          cwd=cwd)
        except OSError as e:
            return_code = e.errno
            print(e.strerror)
        if self._verbose:
            print('Return code: {}'.format(return_code))
        return return_code

    def does_command_exist(self, name, dashes=2):
        '''call a command with the given name
        and expects that it has option --version'''
        return not self.call((name, '{}version'.format(dashes * '-')),
                             suppress_stdout=True,
                             suppress_stderr=True)
