from typing import TYPE_CHECKING

# this is a really, really dirty hack to avoid cyclic references.
# because the JsonFiles require non-string references to their
# types, they must import those types. but those types also depend on
# global state and configuration. to resolve this, we only import
# global state/configuration at runtime by proxying through these classes.

if TYPE_CHECKING:
    from .datatypes import State, Config, Tokens

def state() -> 'State':
    from .datatypes import State
    return State()

def config() -> 'Config':
    from .datatypes import Config
    return Config()

def tokens() -> 'Tokens':
    from .datatypes import Tokens
    return Tokens()
