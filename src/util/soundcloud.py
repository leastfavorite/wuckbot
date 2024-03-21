from typing import Union, Optional, Callable
from dataclasses import dataclass
import asyncio
import aiohttp
import re
from urllib.parse import urlparse
from util.json import JsonDb

MONETIZATION = {
    "start_timestamp": None,
    "start_timezone": None,
    "end_timestamp": None,
    "end_timezone": None,
    "territories": [],
    "excluded_territories": [],
    "worldwide": False
}


class SoundCloud:
    pass


class ScObject:
    def __init__(self, sc: SoundCloud, *,
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


class Track(TrackOrPlaylist):
    def __init__(self, *args, tag_list: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.tags = tag_list

    async def edit(self,
                   title: str = None,
                   description: str = None,
                   tags: str = None):

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
            monetization=MONETIZATION if self.sc.me.pro else None
        )

    async def delete(self):
        if not self.mine:
            return
        await self.sc.routes["delete_track"].run(s_id=self.s_id)

    async def update_artwork(self, artwork_url: str):
        pass


class Playlist(TrackOrPlaylist):
    def __init__(self, *args, tracks: list[dict], **kwargs):
        super().__init__(*args, **kwargs)
        self.tracks = [Track(**track) for track in tracks]

    async def add_track(self, track: Track):
        pass

    async def remove_track(self, track: Track):
        pass

    async def delete(self):
        pass


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


NotRequired = object()
Required = object()


@dataclass
class Route:
    sc: SoundCloud
    verb: str
    endpoint: str
    params: dict[str, str] = None
    json: list[str] = None
    parse: Callable = None

    # coroutine or callable

    BASE_URL = "https://api-v2.soundcloud.com"

    @classmethod
    def _parse_args(cls, arg_dict, **kwargs):
        out = {}

        if type(arg_dict) is list:
            arg_dict = {k: Required for k in arg_dict}

        for k, v in arg_dict.items():

            if v is Required:
                if k in kwargs:
                    out[k] = kwargs[k]
                else:
                    raise KeyError(f"Could not find {k}")
                continue

            if v is NotRequired:
                if k in kwargs and kwargs[k] is not None:
                    out[k] = kwargs[k]
                continue

            if type(v) is dict:
                out[k] = cls._parse_args(v, **kwargs)
            elif type(v) is str:
                out[k] = v.format(**kwargs)
            else:
                out[k] = v

        return out

    async def run(self, retry=True, **kwargs):
        endpoint = self.endpoint.format(**kwargs)

        params = dict(client_id=self.sc.client_id,
                      **self._parse_args(self.params or {}, **kwargs))
        json = None
        if self.json:
            json = self._parse_args(self.json, **kwargs)

        headers = {
            "Accept": "application/json",
            "Authorization": f"OAuth {self.sc.oauth_token}"
        }

        json = {} if json is None else {"json": json}
        async with self.sc.http.request(self.verb, self.BASE_URL + endpoint,
                                        params=params, headers=headers,
                                        **json) as resp:
            if not resp.ok:
                if retry:
                    # maybe something's gone stale?
                    await self.sc.refresh()
                    return await self.run(retry=False, **kwargs)
                else:
                    resp.raise_for_status()
                    return None

            result = await resp.json()

        if self.parse:
            result = self.parse(self.sc, **result)
            if asyncio.iscoroutine(result):
                return await result
        return result


class SoundCloud:
    def __init__(self, oauth_token: str):
        self.http = aiohttp.ClientSession()
        self.oauth_token = oauth_token
        self.client_id = None
        self.routes = {
            "resolve": Route(self, "get", "/resolve", params=["url"]),

            "track_upload_policy": Route(
                self, "post", "/uploads/track-upload-policy",
                json=["filename", "filesize"]),

            "track_transcoding": Route(
                self, "post", "/uploads/{uid}/track-transcoding"),

            "track_permalink_availability": Route(
                self, "get", "/track_permalink_availability",
                params=["permalink"],
                parse=lambda _, **x: x.get(
                    "track_permalink_available", False)),

            "upload_track": Route(self, "post", "/tracks", json={"track": {
                "description": Required,
                "downloadable": True,
                "permalink": Required,
                "sharing": "private",
                "tag_list": Required,
                "title": Required,
                "original_filename": NotRequired,
                "uid": NotRequired,
                "monetization": NotRequired
            }}),

            "edit_track": Route(
                self, "put", "/tracks/soundcloud:tracks:{s_id}",
                json={"track": {
                    "description": Required,
                    "downloadable": True,
                    "permalink": Required,
                    "sharing": "private",
                    "tag_list": Required,
                    "title": Required,
                    "monetization": NotRequired
                }}, parse=Track),

            "delete_track": Route(self, "delete",
                                  "/tracks/soundcloud:tracks:{s_id}"),

            "me": Route(self, "get", "/me", parse=User),

            "fetch_track": Route(self, "get",
                                 "/tracks/soundcloud:tracks:{s_id}",
                                 params={"secret_token": NotRequired},
                                 parse=Track)
        }

    async def close(self):
        await self.http.close()

    async def get_client_id(self):
        ASSET_RE = r'src="(https://a-v2.sndcdn.com/assets/.*\.js)'
        CLIENT_REGEXES = [r'"client_id=(\w+)"', r'client_id:"(\w+)"']

        async with self.http.get("https://soundcloud.com/") as resp:
            # find all assets/*.js files
            regex_gen = (re.search(ASSET_RE, line.decode())
                         async for line in resp.content)
            urls = (match.group(1) async for match in regex_gen
                    if match is not None)

            # try to find a client id in each one
            async for url in urls:
                async with self.http.get(url) as inner_resp:
                    if not inner_resp.ok:
                        continue

                    content = (await inner_resp.content.read()).decode()

                # hunt for client_id
                for regex in CLIENT_REGEXES:
                    if (match := re.search(regex, content)) is not None:
                        return match.group(1)

        return None

    # try to refresh all the "dynamic" elements of the soundcloud bot that
    # are needed to run.. the client_id and user account can change without
    # us knowing, and it might break stuff
    async def refresh(self):
        self.client_id = await self.get_client_id()
        if self.client_id is None:
            raise RuntimeError("Could not parse out a client id")

        self.me: User = await self.routes["me"].run()

    @classmethod
    async def create(cls, oauth_token: str):
        sc = cls(oauth_token)
        await sc.refresh()
        return sc

    async def resolve(self, url: str) -> Union[Track, User, Playlist, None]:

        try:
            resolved = await self.routes["resolve"].run(url=url)
        except aiohttp.ClientResponseError:
            return None

        kind = resolved["kind"]
        if kind == "user":
            return User(self, **resolved)
        elif kind == "playlist":
            return Playlist(self, **resolved)
        elif kind == "track":
            return Track(self, **resolved)
        else:
            return None

    async def find_permalink(self, title: str, tries=10) -> Optional[str]:
        slug = title.lower().replace(" ", "-")
        slug = re.sub(r'[^a-z0-9_-]', r'', slug)
        candidates = [slug, *(f"{slug}-{i}" for i in range(1, tries))]

        for candidate in candidates:
            if await self.routes["track_permalink_availability"].run(
                    permalink=candidate):
                return candidate
        raise RuntimeError(f"Track {title} has been uploaded {tries} times?")

    async def upload_track(self, file_url: str, *,
                           title: str,
                           description: str,
                           tags: str) -> Optional[Track]:
        async with self.http.get(file_url) as file_resp:
            file_resp.raise_for_status()

            filename = urlparse(file_url).path.split("/")[-1]
            filesize = int(file_resp.headers["Content-Length"])

            # get track policy
            policy = await self.routes["track_upload_policy"].run(
                filename=filename, filesize=filesize)
            uid = policy["uid"]

            # upload track to policy
            async with self.http.put(policy["url"],
                                     headers=policy["headers"],
                                     data=file_resp.content) as policy_resp:
                policy_resp.raise_for_status()

        # queue track transcoding
        await self.routes["track_transcoding"].run(uid=uid)

        # find a slug
        permalink = await self.find_permalink(title)

        # upload!! :D
        result = await self.routes["upload_track"].run(
            description=description,
            permalink=permalink,
            tag_list=tags,
            title=title,
            original_filename=filename,
            uid=uid,
            monetization=MONETIZATION if self.me.pro else None
        )

        # re-fetch, since not all info is available
        return await self.fetch_track(result["id"], result["secret_token"])

    async def fetch_track(
            self, s_id: int, secret_token: Optional[str] = None) -> Track:
        return await self.routes["fetch_track"].run(
            s_id=s_id, secret_token=secret_token)

    async def fetch_playlist(self, s_id: int) -> Playlist:
        pass

    async def fetch_user(self, s_id: int) -> User:
        pass


@JsonDb.serializer
def serialize(user: User) -> str:
    return str(user.s_id)


@JsonDb.deserializer
async def deserialize(s_id: str, sc: SoundCloud, **_) -> User:
    s_id = int(s_id)
    return await sc.fetch_user(s_id)


@JsonDb.serializer
def serialize(playlist: Playlist) -> str:
    if playlist.secret_token is None:
        return str(playlist.s_id)
    return f"{playlist.s_id}|{playlist.secret_token}"


@JsonDb.deserializer
async def deserialize(playlist: str, sc: SoundCloud, **_) -> Playlist:
    if "|" in playlist:
        s_id, token = playlist.split("|")
        return await sc.fetch_playlist(int(s_id), token)
    return await sc.fetch_track(int(playlist))


@JsonDb.serializer
def serialize(track: Track) -> str:
    if track.secret_token is None:
        return str(track.s_id)
    return f"{track.s_id}|{track.secret_token}"


@JsonDb.deserializer
async def deserialize(track: str, sc: SoundCloud, **_) -> Track:
    if "|" in track:
        s_id, token = track.split("|")
        return await sc.fetch_track(int(s_id), token)
    return await sc.fetch_track(int(track))
