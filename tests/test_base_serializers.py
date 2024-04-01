from unittest import IsolatedAsyncioTestCase
from random import randrange
import json

from src.validator.serializers.base import \
    IdentitySerializer, DatetimeSerializer, ListSerializer, TupleSerializer, \
    DictSerializer

from src.validator import base_serializers, Registrar

from datetime import datetime, UTC

# tests all the basic serializers
class TestBaseSerializers(IsolatedAsyncioTestCase):

    async def test_identity_serialization(self):
        s = IdentitySerializer()

        cases = [
            ("test", str),
            (42,     int),
            (50.0,   float),
            (True,   bool),
            (None,   type(None)),
            ("",     str),
            (0,      int),
            (False,  bool),
            ("hi!",  str)
        ]

        for obj, t in cases:
            self.assertTrue(s.supports(t))

            serialized = await s.serialize(obj, t)
            self.assertEqual(obj, serialized)

            # check that we don't throw
            json.dumps(serialized)

            deserialized = await s.deserialize(serialized, t)
            self.assertEqual(obj, deserialized)

    async def test_identity_failure(self):
        s = IdentitySerializer()

        cases = [
            ("test", int),
            (42,     float),
            (50.0,   bool),
            (True,   type(None)),
            (None,   str),
            ("True", bool),
            (0,      str),
            (False,  float),
            ("hi!",  type(None))
        ]

        for obj, t in cases:
            serialized = await s.serialize(obj, t)
            self.assertIs(serialized, None)

    async def test_datetime_serialization(self):
        s = DatetimeSerializer()

        timestamp = 1670389200
        dt = datetime.fromtimestamp(timestamp, UTC)
        serialized = await s.serialize(dt, datetime)
        self.assertEqual(timestamp, serialized)
        deserialized = await s.deserialize(serialized, datetime)
        self.assertEqual(dt, deserialized)

    async def test_registrar(self):
        r = Registrar()
        r.register(IdentitySerializer(), DatetimeSerializer())

        def dt():
            return datetime.fromtimestamp(randrange(946684800, 1704067200), UTC)

        cases = [
            ("test", str),
            (42,     int),
            (dt(),   datetime),
            (50.0,   float),
            (True,   bool),
            (dt(),   datetime),
            (None,   type(None)),
            ("",     str),
            (0,      int),
            (dt(),   datetime),
            (False,  bool),
            ("hi!",  str),
            (dt(),   datetime),
        ]

        for obj, t in cases:
            self.assertTrue(r.supports(t))

            serialized = await r.serialize(obj, t)

            # check that we don't throw
            json.dumps(serialized)

            deserialized = await r.deserialize(serialized, t)
            self.assertEqual(obj, deserialized)

    async def test_list_serialization(self):
        r = Registrar()
        r.register(IdentitySerializer(), DatetimeSerializer(), ListSerializer())

        def dt():
            return datetime.fromtimestamp(randrange(946684800, 1704067200), UTC)

        cases = [
            ([14, 5, 39, 1], list[int]),
            ([True, False, True, True], list[bool]),
            ([5.1, 7.2, 9.9, -1.0], list[float]),
            ([dt(), dt(), dt(), dt(), dt()], list[datetime])
        ]

        for obj, t in cases:
            self.assertTrue(r.supports(t))

            serialized = await r.serialize(obj, t)

            # check that we don't throw
            json.dumps(serialized)

            deserialized = await r.deserialize(serialized, t)
            self.assertEqual(obj, deserialized)

    async def test_list_filtering(self):
        r = Registrar()
        r.register(IdentitySerializer(), ListSerializer())

        obj = [5, 7, "hey", 13, None, 70, "what?"]
        t = list[int]

        self.assertTrue(r.supports(t))

        serialized = await r.serialize(obj, t)

        # check that we don't throw
        json.dumps(serialized)

        deserialized = await r.deserialize(serialized, t)
        self.assertEqual([5, 7, 13, 70], deserialized)

    async def test_tuple_serialization(self):
        r = Registrar()
        r.register(IdentitySerializer(), DatetimeSerializer(), TupleSerializer())

        def dt():
            return datetime.fromtimestamp(randrange(946684800, 1704067200), UTC)

        cases = [
            ((14, 5, 39, 1), tuple[int]),
            ((True, False, True, True), tuple[bool]),
            ((5.1, 7.2, 9.9, -1.0), tuple[float]),
            ((dt(), dt(), dt(), dt(), dt()), tuple[datetime])
        ]

        for obj, t in cases:
            self.assertTrue(r.supports(t))

            serialized = await r.serialize(obj, t)

            # check that we don't throw
            json.dumps(serialized)

            deserialized = await r.deserialize(serialized, t)
            self.assertEqual(obj, deserialized)

    async def test_tuple_nonfiltering(self):
        r = Registrar()
        r.register(IdentitySerializer(), TupleSerializer())

        obj = (5, 7, "hi", 13, None, 70, "what?")
        t = tuple[int]

        self.assertTrue(r.supports(t))

        serialized = await r.serialize(obj, t)

        # check that we don't throw
        json.dumps(serialized)

        deserialized = await r.deserialize(serialized, t)
        self.assertEqual((5, 7, None, 13, None, 70, None), deserialized)

    async def test_dict_serializer(self):
        r = Registrar()
        r.register(IdentitySerializer(), DictSerializer(), DatetimeSerializer())

        def dt():
            return datetime.fromtimestamp(randrange(946684800, 1704067200), UTC)

        cases = [
            ({"a": 1, "b": 2, "c": 3}, dict[str, int]),
            ({"a": dt(), "b": dt(), "c": dt()}, dict[str, datetime]),
            ({"a": True, "b": False, "c": True}, dict[str, bool])
        ]

        for obj, t in cases:
            self.assertTrue(r.supports(t))

            serialized = await r.serialize(obj, t)

            # check that we don't throw
            json.dumps(serialized)

            deserialized = await r.deserialize(serialized, t)
            self.assertEqual(obj, deserialized)

    async def test_dict_filtering(self):
        r = Registrar()
        r.register(IdentitySerializer(), DictSerializer())

        obj = {
            "a": 5, "b": 7, "c": "hey",
            "d": 13, "e": None, "f": 70, "g": "what?"
        }

        serialized = await r.serialize(obj, dict[str, int])

        # check that we don't throw
        json.dumps(serialized)

        deserialized = await r.deserialize(serialized, dict[str, int])
        self.assertEqual({"a": 5, "b": 7,  "d": 13, "f": 70}, deserialized)

    async def test_full_registrar(self):
        r = Registrar(*base_serializers())

        def dt():
            return datetime.fromtimestamp(randrange(946684800, 1704067200), UTC)

        cases = [
            ("test", str),
            (42,     int),
            (50.0,   float),
            (True,   bool),
            (None,   type(None)),
            (dt(), datetime),
            ([True, False, True], list[bool]),
            ({"a": 1, "b": 2, "c": 3}, dict[str, int]),
        ]

        for obj, t in cases:
            self.assertTrue(r.supports(t), f"{obj}: {t}")
            serialized = await r.serialize(obj, t)

            # check that we don't throw
            json.dumps(serialized)

            deserialized = await r.deserialize(serialized, t)
            self.assertEqual(deserialized, obj)

    async def test_nested_types(self):
        r = Registrar(*base_serializers())

        obj = {
            "a": [(1, 2), (3, 4)],
            "b": [(4, 3), (2, 1)]
        }

        t = dict[str, list[tuple[int]]]

        self.assertTrue(r.supports(t))
        serialized = await r.serialize(obj, t)

        # check that we don't throw
        json.dumps(serialized)

        deserialized = await r.deserialize(serialized, t)
        self.assertEqual(deserialized, obj)
