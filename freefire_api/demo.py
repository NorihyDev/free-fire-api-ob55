import json
from importlib.resources import files

from freefire_api.errors import APIError

DEMO_UID = "1234567890"


class DemoClient:
    """Synthetic data for exercising REST requests; never represented as live game data."""

    def __init__(self):
        self.accounts = {"IND": None}

    def fixture(self, name: str) -> dict:
        return json.loads(files("freefire_api.fixtures").joinpath(name + ".json").read_text())

    async def profile(self, uid: str, region: str, gallery: bool = False) -> dict:
        if uid != DEMO_UID or region != "IND":
            raise APIError(404, "PLAYER_NOT_FOUND", "Demo player is 1234567890 in IND.")
        return self.fixture("profile")

    async def stats(self, uid: str, region: str, mode: str, match_type: str) -> dict:
        await self.profile(uid, region)
        return self.fixture(mode + "_stats")

    async def search(self, keyword: str, region: str) -> dict:
        basic = self.fixture("profile")["basicinfo"]
        return {"infos": [basic] if region == "IND" and keyword.casefold() in "demoplayer" else []}
