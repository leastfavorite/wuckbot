from typing import Optional
import json

def get_watchdog(filename, default: Optional[dict] = None):

    def transform(item):
        if type(item) is list:
            return _WatchdogList(item)
        elif type(item) is dict:
            return _WatchdogDict(item)
        else:
            return item

    def on_change(): pass

    class _WatchdogContainer:
        def __setitem__(self, key, value):
            self.data[key] = transform(value)
            on_change()

        def __delitem__(self, key):
            del self.data[key]
            on_change()

        def __getitem__(self, key):
            return self.data[key]

        def __iter__(self):
            return self.data.__iter__()

        def __str__(self):
            return self.data.__str__()

        def __repr__(self):
            return self.data.__repr__()

        def __eq__(self, other):
            if isinstance(other, _WatchdogContainer):
                return self.data == other.data
            return self.data == other

    class _WatchdogList(_WatchdogContainer):
        def __init__(self, data: list):
            self.data = []
            for elem in data:
                self.data.append(transform(elem))

        def _standardize(self):
            ret = []
            for elem in self.data:
                if isinstance(elem, _WatchdogContainer):
                    ret.append(elem._standardize())
                else:
                    ret.append(elem)
            return ret

        def extend(self, l2):
            for i in l2:
                self.data.append(transform(l2))

        def append(self, value):
            self.data.append(transform(value))
            on_change()

        def pop(self, n):
            self.data.pop(n)
            on_change()

    class _WatchdogDict(_WatchdogContainer):
        def __getattribute__(self, key):
            try:
                return super().__getattribute__(key)
            except AttributeError:
                return self.__getitem__(key)

        def __setattr__(self, key, value):
            if key == "data":
                super().__setattr__(key, value)
            else:
                self.__setitem__(key, value)

        def __delattr__(self, key):
            if key == "data":
                super().__delattr__(key)
            else:
                self.__delitem__(key)

        def __init__(self, data: dict):
            self.data = dict()
            for k, v in data.items():
                self.data[k] = transform(v)

        def _standardize(self):
            ret = dict()
            for k, elem in self.data.items():
                if isinstance(elem, _WatchdogContainer):
                    ret[k] = elem._standardize()
                else:
                    ret[k] = elem
            return ret

        def items(self):
            return self.data.items()

        def get(self, key, default=None):
            return self.data.get(key, default)

    try:
        with open(filename, "r") as fp:
            data = json.load(fp)
            if type(data) is not dict:
                raise ValueError("JSON not parsed as dict.")
    except FileNotFoundError:
        print(f"Could not find file '{filename}'. Using default...")
        if default is None:
            data = {}
        else:
            data = default
        on_change()

    ret = _WatchdogDict(data)

    def on_change():
        with open(filename, "w") as fp:
            json.dump(ret._standardize(), fp, indent=2)

    return ret
