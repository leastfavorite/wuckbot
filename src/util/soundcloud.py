# i am going to use regex to parse HTML :)
# yayyyy....
import re
import aiohttp
import asyncio
from typing import Optional
from urllib.parse import urlparse

from util.json import JsonSerializable


class Http:
    API = "https://api-v2.soundcloud.com/"

    def __init__(self, oauth_token):
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()
        self.client_id = None
        self.oauth_token = oauth_token

    async def close(self):
        await self.session.close()

    @property
    def req_kwargs(self):
        return {
        }

    async def refresh_client_id(self):
        async with self.session.get("https://soundcloud.com/") as resp:

            if resp.status != 200:
                return None

            urls = []
            async for line in resp.content:
                # find cdn js files
                match = re.search(
                    r'src="(https://a-v2.sndcdn.com/assets/.*\.js)',
                    line.decode("utf8"))
                if match is not None:
                    urls.append(match.group(1))

            # finds a client id from javascript.
            # uses some really ugly scrape-y regex
            async def _find_client_id(url):
                async with self.session.get(url) as inner_resp:
                    if inner_resp.status != 200:
                        return None
                    content = await inner_resp.content.read()
                    content = content.decode("utf8")
                    match = re.search(r'"client_id=(\w+)"', content)
                    if match is not None:
                        return match.group(1)
                    else:
                        match = re.search(r'client_id:"(\w+)"', content)
                        if match is not None:
                            return match.group(1)

            ids = await asyncio.gather(*(_find_client_id(url) for url in urls))
            ids = [id_ for id_ in ids if id_ is not None]
            if len(ids) == 0:
                raise RuntimeError("Could not find client_id")
            if any(id_ != ids[0] for id_ in ids):
                raise RuntimeError("Got false-positive client ids? Uh oh")
            self.client_id = ids[0]

    async def api_call(self, verb, url,
                       headers={}, params={},
                       as_json=True, retry=True,
                       **kwargs):
        if self.client_id is None:
            await self.refresh_client_id()

        default_headers = {
            "Accept": "application/json",
            "Authorization": f"OAuth {self.oauth_token}"
        }
        default_params = {
            "client_id": self.client_id
        }
        kwargs["headers"] = {**default_headers, **headers}
        kwargs["params"] = {**default_params, **params}

        url = self.API + url

        async with getattr(self.session, verb)(url, **kwargs) as resp:
            if not retry:
                # error out if we fail here and don't want to retry
                resp.raise_for_status()

            if resp.ok:
                if as_json:
                    return await resp.json()
                else:
                    return await resp.read()

        # if we fail with retry, reparse stale parameters
        await self.refresh_client_id()

        # try again
        async with getattr(self.session, verb)(url, **kwargs) as resp:
            resp.raise_for_status()
            if as_json:
                return await resp.json()
            else:
                return await resp.read()

    async def post(self, *args, **kwargs):
        return await self.api_call("post", *args, **kwargs)

    async def get(self, *args, **kwargs):
        return await self.api_call("get", *args, **kwargs)

    async def upload_track(self, song_url, *, title,
                           description="", tags="", pro=False):

        # get "filename" from parsing the song url
        filename = urlparse(song_url).path.split("/")[-1]
        print(filename)

        # request the url to get its content length (and later its data)
        async with self.session.get(song_url) as song_resp:
            song_resp.raise_for_status()

            # get the length
            length = int(song_resp.headers["Content-Length"])

            # post the track upload policy.
            # this gives an aws link to PUT to to upload the song
            policy = await self.post("uploads/track-upload-policy",
                                     json={
                                         "filename": filename,
                                         "filesize": length
                                     })
            uid = policy["uid"]

            async with self.session.put(
                policy["url"],
                headers=policy["headers"],
                data=song_resp.content
            ) as bucket_resp:
                bucket_resp.raise_for_status()

        # then, queue transcoding:
        await self.post(f"uploads/{uid}/track-transcoding", data=b'')

        # song is uploaded. we can now put the metadata in.
        # first, we find a slug:
        slug_base = title.lower().replace(" ", "-")

        # filter out invalid characters
        slug_base = "".join(
            filter(lambda x: re.search(r'[a-z0-9_-]', x), slug_base))

        for i in range(10):
            # try slug_base, then slug_base-1, slug_base-2...
            slug = f"{slug_base}-{i}" if i > 0 else slug_base

            # call tp availability and extract tp available from the response
            slug_available = (await self.get(
                "track_permalink_availability",
                params={"permalink": slug}
            )).get("track_permalink_available", False)

            if slug_available:
                break
        else:
            raise ValueError("Somehow this slug has been uploaded 10 times")

        # now, finally, we can upload:
        form = self.track_form(
            title=title,
            slug=slug,
            description=description,
            tags=tags,
            filename=filename,
            uid=uid)

        return await self.post("tracks", json=form)

    async def edit_track(self, s_id: int,
                         title: str = None,
                         description: str = None,
                         tags: str = None,
                         pro: bool = False):
        track_info = await self.get(
            f"tracks/soundcloud:tracks:{s_id}")

        form = self.track_form(
            title=title or track_info["title"],
            slug=track_info["permalink"],
            description=description or track_info["description"],
            tags=tags or track_info["tag_list"],
            pro=pro
        )

        track_info = await self.api_call(
            "put",
            f"tracks/soundcloud:tracks:{s_id}",
            json=form)

        return track_info


    def track_form(self, title: str, slug: str,
                   description: str = "", tags: str = "",
                   filename: str = None, uid: str = None,
                   pro: bool = False):
        ret = {
            "track": {
                # "api_streamable": True,
                # "commentable": True,
                "description": description,
                "downloadable": True,
                # "embeddable": True,
                # "feedable": False,
                # "genre": "",
                # "isrc_generate": False,
                # "license": "all-rights-reserved",
                "permalink": slug,
                # "reveal_comments": True,
                # "reveal_stats": True,
                "sharing": "private",
                "tag_list": tags,
                "title": title,
                # "geo_blockings": [],
                # "snippet_presets": {"start_seconds": 0, "end_seconds": 3},  # e
                # "publisher_metadata": {
                #     "artist": None,
                #     "album_title": None,
                #     "contains_music": True,  # present in edit
                #     "publisher": None,
                #     "iswc": None,
                #     "upc_or_ean": None,
                #     "isrc": None,  # present in edit
                #     "p_line": None,
                #     "c_line": None,
                #     "explicit": None,
                #     "writer_composer": None,
                #     "release_title": None
                # },
                # "restrictions": [],
                # "rightsholders": [],
                # "caption": "", # shows in create, not in edit
                # "tracklist": {
                #     "segments": []
                # },
                # "track_format": "single-track",
                # "scheduled_public_date": None,
                # "scheduled_timezone": None
            }
        }
        if filename is not None:
            ret["track"]["original_filename"] = filename
        if uid is not None:
            ret["track"]["uid"] = uid

        if pro:
            ret["track"]["monetization"] = {
                "start_timestamp": None,
                "start_timezone": None,
                "end_timestamp": None,
                "end_timezone": None,
                "territories": [],
                "excluded_territories": [],
                "worldwide": False
            }

        return ret



class Playlist:
    pass


class Track:
    pass


class Session:
    def __init__(self, http: Http, slug: str, pro: bool):
        self._http = http
        self.slug = slug
        self.pro = pro

    async def close(self):
        await self._http.close()

    @classmethod
    async def create(cls, oauth_token: str):
        http = Http(oauth_token)
        me = await http.get("me")

        slug = me["permalink"]
        pro = me["badges"]["pro"] or me["badges"]["pro_unlimited"]

        return cls(http, slug, pro)

    async def upload_track(self, url: str, *, title: str,
                           description: str = "", tags: str = "") -> Track:
        resp = await self._http.upload_track(
            url, title=title, description=description, tags=tags,
            pro=self.pro)

        return await Track.create(s_id=resp["id"], sc=self)

    async def fetch_track(self, url: str) -> Optional[Track]:
        async with self._http.session.get(url) as resp:
            async for line in resp.content:
                pattern = r'<link rel="alternate" href="ios-app://.+:(\d+)">'
                match = re.search(pattern, line.decode().strip())
                if match:
                    s_id = int(match.group(1))
                    return await Track.create(s_id=s_id, sc=self)

    async def fetch_playlist(self, url: str) -> Optional[Playlist]:
        pass


class Track(JsonSerializable):
    MANIFEST = {
        "s_id": int
    }

    async def on_init(self, sc: Session, **_):
        self._session = sc
        track_info = await sc._http.get(
            f"tracks/soundcloud:tracks:{self.s_id}")
        self.title = track_info["title"],
        self.url = track_info["permalink_url"]

    def __repr__(self):
        return f"Track<{self.title}>"

    async def edit(self,
                   title: str = None,
                   description: str = None,
                   tags: str = None):
        resp = await self._session._http.edit_track(
            s_id=self.s_id,
            title=title,
            description=description,
            tags=tags,
            pro=self._session.pro
        )

        self.title = resp["title"]
        self.url = resp["permalink_url"]

    async def delete(self):
        await self._session._http.api_call(
            "delete", f"tracks/soundcloud:tracks:{self.s_id}")


class Playlist(JsonSerializable):
    MANIFEST = {
        "s_id": int
    }

    async def on_init(self, sc: Session, **_):
        # get songs
        self.songs: list[Track] = []  # TODO
        self._session = sc

    @classmethod
    async def from_url(cls, url: str):
        pass

    async def add(self, track: Track):
        pass

    async def remove(self, track: Track):
        pass

    async def edit(self, name: str = "", description: str = ""):
        pass

    def __contains__(self):
        pass
