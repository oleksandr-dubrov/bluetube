from bluetube.cli.cli import CLI
from bluetube.cli.events import Event, Success


class Outputer(CLI):
    '''Print information to CLI'''

    def __init__(self):
        super().__init__()

    def update(self, event: Event):
        '''Update the output based on the event.'''
        self._handlers[type(event).__name__](event)

    def _success(self, event: Success):
        '''inform about success'''
        if event.msg == 'feed updated':
            self._sound()
            return
        return super()._success(event)

    def _sound(self):
        '''inform the user by beep'''
        print('\a')
