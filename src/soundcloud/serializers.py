from dataclasses import dataclass
from typing import Optional, Union

from .client import Client
from .datatypes import User, Track, Playlist
from ..validator import Serializer, Serializable

from aiohttp import ClientResponseError

@dataclass
class UserSerializer(Serializer[User]):
    client: Client

    def supports(self, Target: type) -> bool:
        return issubclass(Target, User)

    async def serialize(self, obj: User, _) -> Optional[Serializable]:
        if isinstance(obj, User):
            return obj.s_id
        return None

    async def deserialize(self, obj: Serializable, _) -> Optional[User]:
        if not isinstance(obj, int):
            return None
        try:
            return await self.client.fetch_user(obj)
        except ClientResponseError:
            return None

@dataclass
class TrackOrPlaylistSerializer(Serializer[Union[Track, Playlist]]):
    client: Client

    def supports(self, Target: type) -> bool:
        return issubclass(Target, Playlist) or issubclass(Target, Track)

    async def serialize(self, obj: Union[Track, Playlist], _) -> Optional[Serializable]:
        if not isinstance(obj, Playlist) and not isinstance(obj, Track):
            return None
        if obj.secret_token:
            return f"{obj.s_id}|{obj.secret_token}"
        return f"{obj.s_id}"

    async def deserialize(self, obj: Serializable, Target: type) -> Optional[Union[Track, Playlist]]:
        if not isinstance(obj, str):
            return None

        s_id, token = obj, None
        if "|" in obj:
            s_id, token = obj.split("|")

        try:
            if issubclass(Target, Track):
                return await self.client.fetch_track(int(s_id), token)
            if issubclass(Target, Playlist):
                return await self.client.fetch_playlist(int(s_id), token)
            return None
        except ClientResponseError:
            return None

def serializers(client: Client):
    return [
        UserSerializer(client),
        TrackOrPlaylistSerializer(client)
    ]
