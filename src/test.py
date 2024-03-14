class RegistryMeta(type):
    _registry = set()
    def __new__(mcs, name, bases, dct):
        new_type = super().__new__(mcs, name, bases, dct)
        print(dct)
        if len(bases) > 0:
            mcs._registry.add(new_type)
        return new_type

class Registered(metaclass=RegistryMeta):
    pass

class A(Registered):
    def __init__(self, b):
        self.b = b

    def balls(self): pass

print(RegistryMeta._registry)
