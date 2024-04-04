from typing import Optional, TYPE_CHECKING, AsyncIterator
from ..validator import Serializable

if TYPE_CHECKING:
    from .client import Client

MONETIZATION_ARGS: Serializable = {
    "start_timestamp": None,
    "start_timezone": None,
    "end_timestamp": None,
    "end_timezone": None,
    "territories": [],
    "excluded_territories": [],
    "worldwide": False
}

class ScObject:
    def __init__(self, sc: 'Client', *,
                 id: int, permalink_url: str, permalink: str, **_):
        self.sc = sc
        self.s_id = id
        self.url = permalink_url
        self.permalink = permalink

    def update(self, **kwargs):
        self.__init__(self.sc, **kwargs)

    def __eq__(self, o):
        return hasattr(o, "s_id") and self.s_id == o.s_id

    def __hash__(self):
        return self.s_id

    def __repr__(self):
        if hasattr(self, "title"):
            return f"{type(self).__qualname__}({self.title})"
        elif hasattr(self, "username"):
            return f"{type(self).__qualname__}({self.username})"
        return type(self).__qualname__


class TrackOrPlaylist(ScObject):
    def __init__(self, *args,
                 title: str, description: str, artwork_url: str,
                 secret_token: Optional[str],
                 user: dict, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = title
        self.description = description
        self.artwork_url = artwork_url
        self.secret_token = secret_token
        self.author = User(self.sc, **user)

    @property
    def mine(self):
        return self.author.s_id == self.sc.me.s_id

    @property
    def private(self):
        return self.secret_token is not None

class User(ScObject):
    def __init__(self, *args, avatar_url: str, username: str,
                 creator_subscriptions=None, badges=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.avatar_url = avatar_url
        self.username = username
        if badges:
            self.pro = badges["pro"] or badges["pro_unlimited"]
        elif creator_subscriptions:
            self.pro = creator_subscriptions[0]["product"]["id"] != "free"
        else:
            raise TypeError("Missing creator_subscriptions or badges")
        # TODO (possibly): check if we're following

    async def playlists(self) -> AsyncIterator['Playlist']:
        # parses the response from fetch_playlists
        async def fetch_playlists(offset):
            response = await self.sc.routes["fetch_playlists"].run(
                s_id=self.s_id,
                offset=offset)

            playlists = [
                Playlist(self.sc, **pl) for pl in response["collection"]]
            more = bool(response["next_href"])
            return playlists, more

        # iterates through pagination
        more = True
        offset = 0
        while more:
            playlists, more = await fetch_playlists(offset)
            for playlist in playlists:
                yield playlist
            offset += 10

class Track(TrackOrPlaylist):
    def __init__(self, *args, tag_list: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.tags = tag_list

    async def edit(self,
                   title: Optional[str] = None,
                   description: Optional[str] = None,
                   tags: Optional[str] = None):

        if description is None:
            description = self.description
        self.description = description

        if title is None:
            title = self.title
        self.title = title

        if tags is None:
            tags = self.tags
        self.tags = tags

        await self.sc.routes["edit_track"].run(
            s_id=self.s_id,
            description=description,
            permalink=self.permalink,
            tag_list=tags,
            title=title,
            monetization=MONETIZATION_ARGS if self.sc.me.pro else None
        )

    async def delete(self):
        if not self.mine:
            return
        await self.sc.routes["delete_track"].run(s_id=self.s_id)

    async def update_artwork(self, artwork_url: str):
        pass


class Playlist(TrackOrPlaylist):
    def __init__(self, sc: 'Client', *args, tracks: list[dict], **kwargs):
        super().__init__(sc, *args, **kwargs)
        self.track_ids = [track["id"] for track in tracks]

    def __contains__(self, other):
        return isinstance(other, Track) and other.s_id in self.track_ids

    async def tracks(self):
        CHUNK_SIZE = 20
        for i in range(0, len(self.track_ids), CHUNK_SIZE):
            track_id_chunk = self.track_ids[i:i+CHUNK_SIZE]
            tracks = await self.sc.routes["fetch_playlist_tracks"].run(
                ids=",".join(str(t) for t in track_id_chunk),
                playlistId=self.s_id,
                playlistSecretToken=self.secret_token
            )
            for track in tracks:
                yield Track(self.sc, **track)

    async def add_track(self, track: Track, top=False):
        if track.private and not track.mine:
            raise ValueError("Cannot add someone else's private track!")

        if track in self:
            return

        if top:
            self.track_ids.insert(0, track.s_id)
        else:
            self.track_ids.append(track.s_id)

        await self.sc.routes["edit_playlist"].run(
            s_id=self.s_id, tracks=self.track_ids)

    async def remove_track(self, track: Track):
        if track not in self:
            return

        self.track_ids.remove(track.s_id)
        await self.sc.routes["edit_playlist"].run(
            s_id=self.s_id, tracks=self.track_ids)

    # async def delete(self):
    #     pass
