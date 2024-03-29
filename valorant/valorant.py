"""
Classes and methods related to Valorant API calls
"""
import base64
import json
import socket

import requests
import urllib3

from valorant.classes import Auth
from valorant.constants import URLS, API, Region, regions

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Valorant:
    def __init__(self, username: str, password: str) -> None:
        self.session = requests.Session()
        self.auth = Auth(self.session, username, password)

        build = requests.get("https://valorant-api.com/v1/version").json()["data"]["riotClientBuild"]
        self.session.headers.update({
            "User-Agent": f"RiotClient/{build} riot-status (Windows;10;;Professional, x64)",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "application/json, text/plain, */*"
        })

        self.auth.set_auth_cookies()

        self.region = self.get_region()
        self.pd_server = f"https://pd.{self.region.region}.a.pvp.net"
        self.glz_server = f"https://glz-{self.region.region}-1.{self.region.shard}.a.pvp.net"
        self.user_info = self.get_user_info()

    @property
    def client_platform(self) -> bytes:
        return base64.b64encode(json.dumps({
            "platformType": "PC",
            "platformOS": "Windows",
            "platformOSVersion": "10.0.19042.1.256.64bit",
            "platformChipset": "Unknown"
        }).encode("utf-8"))

    @property
    def client_version(self) -> str:
        """
        Get the latest client version
        :return: str
        """
        return requests.get(
            "https://valorant-api.com/v1/version",
            timeout=30
        ).json()["data"]["riotClientVersion"]

    def get_user_info(self) -> dict:
        return self.session.post(
            URLS.USERINFO_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.auth.get_access_token()}"
            },
            json={}
        ).json()

    def get_border_level(self, player_id: str | None = None) -> dict:
        if player_id is None:
            player_id = self.user_info["sub"]

        last_match_id = self.get_match_history(player_id, amount=1)["History"][0]["MatchID"]

        players = self.get_match_details(last_match_id)["players"]
        player = list(filter(lambda player_data: player_data["subject"] == player_id, players))[0]

        preferred_border = player.get("preferredLevelBorder", "ebc736cd-4b6a-137b-e2b0-1486e31312c9")
        return requests.get(f"https://valorant-api.com/v1/levelborders/{preferred_border}").json()["data"]

    def get_region(self) -> Region:
        a = self.session.put(
            "https://riot-geo.pas.si.riotgames.com/pas/v1/product/valorant",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.auth.get_access_token()}"
            },
            json={
                "id_token": self.auth.get_id_token()
            }
        ).json()
        return regions[a["affinities"]["live"]]

    def get_content(self) -> dict:
        return self.session.get(
            f"{self.pd_server}{API.CONTENT}",
            headers={
                "X-Riot-ClientPlatform": f"{self.client_platform}",
                "X-Riot-ClientVersion": f"{self.client_version}",
                "X-Riot-Entitlements-JWT": f"{self.auth.get_entitlement_token()}",
                "Authorization": f"Bearer {self.auth.get_access_token()}"
            }
        ).json()

    def get_account_xp(self) -> dict:
        return self.session.get(
            f"{self.pd_server}{API.ACCOUNT_XP}/{self.user_info['sub']}",
            headers={
                "X-Riot-Entitlements-JWT": self.auth.get_entitlement_token(),
                "Authorization": f"Bearer {self.auth.get_access_token()}"
            }
        ).json()

    def get_loadout(self) -> dict:
        return self.session.get(
            f"{self.pd_server}{API.PERSONALIZATION}/{self.user_info['sub']}/playerloadout",
            headers={
                "X-Riot-Entitlements-JWT": self.auth.get_entitlement_token(),
                "Authorization": f"Bearer {self.auth.get_access_token()}"
            }
        ).json()

    def set_loadout(self, loadout: dict) -> None:
        # TODO: Make a class for loadout to make this easier
        self.session.put(
            f"{self.pd_server}{API.PERSONALIZATION}/{self.user_info['sub']}/playerloadout",
            headers={
                "X-Riot-Entitlements-JWT": self.auth.get_entitlement_token(),
                "Authorization": f"Bearer {self.auth.get_access_token()}"
            },
            json=loadout
        )

    def get_player_mmr(self, player_id: str | None = None) -> dict:
        if player_id is None:
            player_id = self.user_info["sub"]

        return self.session.get(
            f"{self.pd_server}{API.MMR}/{player_id}",
            headers={
                "X-Riot-ClientPlatform": self.client_platform,
                "X-Riot-ClientVersion": self.client_version,
                "X-Riot-Entitlements-JWT": self.auth.get_entitlement_token(),
                "Authorization": f"Bearer {self.auth.get_access_token()}"
            }
        ).json()

    def get_match_history(self, player_id: str | None = None, offset: int | None = 0, amount: int | None = 20) -> dict:
        # TODO: add queue parameter when ids are known
        if player_id is None:
            player_id = self.user_info["sub"]

        return self.session.get(
            f"{self.pd_server}{API.HISTORY}/{player_id}?startIndex={offset}&endIndex={amount}",
            headers={
                "X-Riot-Entitlements-JWT": self.auth.get_entitlement_token(),
                "Authorization": f"Bearer {self.auth.get_access_token()}"
            }
        ).json()

    def get_match_details(self, match_id: str) -> dict:
        return self.session.get(
            f"{self.pd_server}{API.MATCHES}/{match_id}",
            headers={
                "X-Riot-Entitlements-JWT": self.auth.get_entitlement_token(),
                "Authorization": f"Bearer {self.auth.get_access_token()}"
            }
        ).json()

    def get_leaderboard(self, season_id: str, start: int = 0, amount: int = 510, username: str | None = None) -> dict:
        return self.session.get(
            f"{self.pd_server}{API.LEADERBOARD}/{season_id}?startIndex={start}&size={amount}" + f"&query={username}" if username else "",
            headers={
                "X-Riot-ClientVersion": self.client_version,
                "X-Riot-Entitlements-JWT": self.auth.get_entitlement_token(),
                "Authorization": f"Bearer {self.auth.get_access_token()}"
            }
        ).json()

    def get_penalties(self) -> dict:
        return self.session.get(
            f"{self.pd_server}{API.PENALTIES}",
            headers={
                "X-Riot-ClientPlatform": self.client_platform,
                "X-Riot-Entitlements-JWT": self.auth.get_entitlement_token(),
                "Authorization": f"Bearer {self.auth.get_access_token()}"
            }
        ).json()

    def get_config(self) -> dict:
        return self.session.get(
            f"{self.pd_server}{API.CONFIG}/{self.region.region}",
            headers={
                "X-Riot-Entitlements-JWT": self.auth.get_entitlement_token(),
                "Authorization": f"Bearer {self.auth.get_access_token()}"
            }
        ).json()

    def get_prices(self) -> dict:
        return self.session.get(
            f"{self.pd_server}{API.PRICES}",
            headers={
                "X-Riot-Entitlements-JWT": self.auth.get_entitlement_token(),
                "Authorization": f"Bearer {self.auth.get_access_token()}"
            }
        ).json()

    def get_store(self) -> dict:
        return requests.get(
            f"{self.pd_server}{API.STORE}/{self.user_info['sub']}",
            headers={
                "Authorization": f"Bearer {self.auth.get_access_token()}",
                "X-Riot-Entitlements-JWT": self.auth.get_entitlement_token(),
                "X-Riot-ClientPlatform": self.client_platform,
                "X-Riot-ClientVersion": self.client_version,
                "Content-Type": "application/json"
            }
        ).json()

    def get_wallet(self) -> dict:
        return self.session.get(
            f"{self.pd_server}{API.WALLET}/{self.user_info['sub']}",
            headers={
                "X-Riot-Entitlements-JWT": self.auth.get_entitlement_token(),
                "Authorization": f"Bearer {self.auth.get_access_token()}"
            }
        ).json()

    def get_items(self, item_type: str) -> dict:
        return self.session.get(
            f"{self.pd_server}{API.OWNED}/{self.user_info['sub']}/{item_type}",
            headers={
                "X-Riot-Entitlements-JWT": self.auth.get_entitlement_token(),
                "Authorization": f"Bearer {self.auth.get_access_token()}"
            }

        ).json()

    def get_pregame_id(self, player_id: str | None = None) -> dict:
        if player_id is None:
            player_id = self.user_info['sub']

        return self.session.get(
            f"{self.glz_server}{API.PREGAME_PLAYER}/{player_id}",
            headers={
                "X-Riot-Entitlements-JWT": self.auth.get_entitlement_token(),
                "Authorization": f"Bearer {self.auth.get_access_token()}"
            }
        ).json()

    def get_pregame_match(self, pregame_match_id: str | None = None) -> dict:
        if pregame_match_id is None:
            pregame_match_id = self.get_pregame_id()["MatchID"]

        return self.session.get(
            f"{self.glz_server}{API.PREGAME_MATCH}/{pregame_match_id}",
            headers={
                "X-Riot-Entitlements-JWT": self.auth.get_entitlement_token(),
                "Authorization": f"Bearer {self.auth.get_access_token()}"
            }
        ).json()

    def get_pregame_loadout(self, pregame_match_id: str | None = None) -> dict:
        if pregame_match_id is None:
            pregame_match_id = self.get_pregame_id()["MatchID"]

        return self.session.get(
            f"{self.glz_server}{API.PREGAME_MATCH}/{pregame_match_id}/loadouts",
            headers={
                "X-Riot-Entitlements-JWT": self.auth.get_entitlement_token(),
                "Authorization": f"Bearer {self.auth.get_access_token()}"
            }
        ).json()

    def select_agent(self, agent_id: str, pregame_match_id: str | None = None) -> dict:
        if pregame_match_id is None:
            pregame_match_id = self.get_pregame_id()

        return self.session.post(
            f"{self.glz_server}{API.MATCHES}/{pregame_match_id}/select/{agent_id}",
            headers={
                "X-Riot-Entitlements-JWT": self.auth.get_entitlement_token(),
                "Authorization": f"Bearer {self.auth.get_access_token()}"
            }
        ).json()

    def lock_agent(self, agent_id: str, pregame_match_id: str | None = None) -> dict:
        if pregame_match_id is None:
            pregame_match_id = self.get_pregame_id()

        return self.session.post(
            f"{self.glz_server}{API.MATCHES}/{pregame_match_id}/lock/{agent_id}",
            headers={
                "X-Riot-Entitlements-JWT": self.auth.get_entitlement_token(),
                "Authorization": f"Bearer {self.auth.get_access_token()}"
            }
        ).json()

    def quit_pregame(self, pregame_match_id: str | None = None) -> dict:
        if pregame_match_id is None:
            pregame_match_id = self.get_pregame_id()

        return self.session.post(
            f"{self.glz_server}{API.MATCHES}/{pregame_match_id}/quit",
            headers={
                "X-Riot-Entitlements-JWT": self.auth.get_entitlement_token(),
                "Authorization": f"Bearer {self.auth.get_access_token()}"
            }
        ).json()

    def get_current_game_player(self, player_id: str | None = None) -> dict:
        if player_id is None:
            player_id = self.user_info["sub"]

        print(f"{self.glz_server}{API.CURRENT_GAME_PLAYER}/{player_id}")
        return self.session.get(
            f"{self.glz_server}{API.CURRENT_GAME_PLAYER}/{player_id}",
            headers={
                "X-Riot-Entitlements-JWT": self.auth.get_entitlement_token(),
                "Authorization": f"Bearer {self.auth.get_access_token()}"
            }
        ).json()

    def get_current_game_match(self, current_match_id: str | None = None) -> dict:
        if current_match_id is None:
            current_match_id = self.get_pregame_id()["MatchID"]

        return self.session.get(
            f"{self.glz_server}{API.CURRENT_GAME_MATCH}/{current_match_id}",
            headers={
                "X-Riot-Entitlements-JWT": self.auth.get_entitlement_token(),
                "Authorization": f"Bearer {self.auth.get_access_token()}"
            }
        ).json()

    def get_current_game_loadout(self, current_match_id: str | None = None) -> dict:
        if current_match_id is None:
            current_match_id = self.get_pregame_id()["MatchID"]

        return self.session.get(
            f"{self.glz_server}{API.CURRENT_GAME_MATCH}/{current_match_id}/loadouts",
            headers={
                "X-Riot-Entitlements-JWT": self.auth.get_entitlement_token(),
                "Authorization": f"Bearer {self.auth.get_access_token()}"
            }
        ).json()

    def get_item_upgrades(self) -> dict:
        return self.session.get(
            f"{self.pd_server}{API.ITEM_UPGRADES}",
            headers={
                "X-Riot-Entitlements-JWT": self.auth.get_entitlement_token(),
                "Authorization": f"Bearer {self.auth.get_access_token()}"
            }
        ).json()

    def get_contracts(self, player_id: str | None = None) -> dict:
        if player_id is None:
            player_id = self.user_info["sub"]

        return self.session.get(
            f"{self.pd_server}{API.CONTRACTS}/{player_id}",
            headers={
                "X-Riot-ClientVersion": self.client_version,
                "X-Riot-Entitlements-JWT": self.auth.get_entitlement_token(),
                "Authorization": f"Bearer {self.auth.get_access_token()}"
            }
        ).json()

    def get_xmpp_socket(self) -> socket.socket:
        pass
