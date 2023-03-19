from bluetube.cli import EventListener
from bluetube.cli.events import Event


class EventPublisher(object):
    '''An event publisher.'''

    def __init__(self) -> None:
        self._subscribers = []

    def subscribe(self, listener: EventListener) -> None:
        '''Subscripe a listener.'''
        self._subscribers.append(listener)

    def notify(self, event: Event) -> None:
        '''Notify all subscribers about an event.'''
        for s in self._subscribers:
            s.update(event)
