from typing import Union, Optional
from urllib.parse import urlparse

import aiohttp
import re

from .route import routes
from .datatypes import Track, User, Playlist, MONETIZATION_ARGS

class Client:
    def __init__(self, oauth_token: str):
        self.http = aiohttp.ClientSession()
        self.oauth_token = oauth_token
        self.client_id = None
        self.routes = routes(self)

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

        self.me = await self.routes["me"].run()

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
                           tags: str) -> Track:
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
            monetization=MONETIZATION_ARGS if self.me.pro else None
        )

        # re-fetch, since not all info is available
        return await self.fetch_track(result["id"], result["secret_token"])

    async def fetch_track(
            self, s_id: int, secret_token: Optional[str] = None) -> Track:
        return await self.routes["fetch_track"].run(
            s_id=s_id, secret_token=secret_token)

    async def fetch_playlist(self, s_id: int, secret_token: Optional[str] = None) -> Playlist:
        raise NotImplementedError("fetch_playlist")

    async def fetch_user(self, s_id: int) -> User:
        return await self.routes["fetch_user"].run(s_id=s_id)
        raise NotImplementedError("fetch_user")
