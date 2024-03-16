# i am going to use regex to parse HTML :)
# yayyyy....
import re
import aiohttp
class SoundcloudClient:
    def __init__(self):
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()
        self.client_id: str = None

    async def get_client_id(self):
        print("hi :D")
        async with self.session.get("https://soundcloud.com/") as resp:
            print(resp.status)
            async for line in resp.content:
                match = re.search(
                    r'src="(https://a-v2.sndcdn.com/assets/*.js)', line)
                if match is not None:
                    print(match.group(1))

    async def close(self):
        await self.session.close()
