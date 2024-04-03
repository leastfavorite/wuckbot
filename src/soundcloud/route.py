import asyncio
from dataclasses import dataclass
from typing import Callable, Optional, TYPE_CHECKING
from .datatypes import User, Track  # Playlist
from ..validator import Serializable

if TYPE_CHECKING:
    from .client import Client

NotRequired = object()
Required = object()

@dataclass
class Route:
    sc: 'Client'
    verb: str
    endpoint: str
    params: Optional[dict[str, str]] = None
    json: Optional[Serializable] = None
    parse: Optional[Callable] = None

    # coroutine or callable

    BASE_URL = "https://api-v2.soundcloud.com"

    @classmethod
    def _parse_args(cls, arg_dict, **kwargs):
        out = {}

        if isinstance(arg_dict, list):
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

            print(k, type(v))
            if isinstance(v, dict):
                out[k] = cls._parse_args(v, **kwargs)
            elif isinstance(v, str):
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


def routes(client):
    return {
        "resolve": Route(client, "get", "/resolve", params=["url"]),

        "track_upload_policy": Route(
            client, "post", "/uploads/track-upload-policy",
            json=["filename", "filesize"]),

        "track_transcoding": Route(
            client, "post", "/uploads/{uid}/track-transcoding"),

        "track_permalink_availability": Route(
            client, "get", "/track_permalink_availability",
            params=["permalink"],
            parse=lambda _, **x: x.get(
                "track_permalink_available", False)),

        "upload_track": Route(client, "post", "/tracks", json={"track": {
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
            client, "put", "/tracks/soundcloud:tracks:{s_id}",
            json={"track": {
                "description": Required,
                "downloadable": True,
                "permalink": Required,
                "sharing": "private",
                "tag_list": Required,
                "title": Required,
                "monetization": NotRequired
            }}, parse=Track),

        "delete_track": Route(client, "delete",
                              "/tracks/soundcloud:tracks:{s_id}"),

        "me": Route(client, "get", "/me", parse=User),

        "fetch_track": Route(client, "get",
                             "/tracks/soundcloud:tracks:{s_id}",
                             params={"secret_token": NotRequired},
                             parse=Track),

        "fetch_user": Route(client, "get",
                            "/users/soundcloud:users:{s_id}",
                            parse=User)
    }
