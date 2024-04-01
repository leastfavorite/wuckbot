from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .datatypes import State, Secrets

def state() -> 'State':
    from .datatypes import State
    return State()

def secrets() -> 'Secrets':
    from .datatypes import Secrets
    return Secrets()
