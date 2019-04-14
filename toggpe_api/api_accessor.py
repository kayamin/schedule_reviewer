import itertools
import os
from typing import List, Dict

import pandas as pd
import requests


class ApiAccessor:
    def __init__(self, agent: str, token: str):
        # api アクセスに必要なパラメータを初期化
        self.agent = agent
        self.token = token
        self.auth = (token, "api_token")
        self.reports_api_base = "https://toggl.com/reports/api/v2"
        self.toggl_api_base = "https://www.toggl.com/api/v8"

        # 記録を取得する際に必須な workspace_id を取得し，セットする
        r = requests.get(os.path.join(self.toggl_api_base, "workspaces"), auth=self.auth)
        self.workspace_id = r.json()[0]["id"]
        self.params = dict(user_agent=self.agent, workspace_id=self.workspace_id)

    """
    取得されるデータ形式
    [{'billable': None,
      'client': None,
      'cur': None,
      'description': 'togglレポート機能調査',
      'dur': 2066000,
      'end': '2019-04-09T20:32:46+09:00',
      'id': 1156429229,
      'is_billable': False,
      'pid': None,
      'project': None,
      'project_color': '0',
      'project_hex_color': None,
      'start': '2019-04-09T19:58:20+09:00',
      'tags': [],
      'task': None,
      'tid': None,
      'uid': 4161438,
      'updated': '2019-04-09T20:32:46+09:00',
      'use_stop': True,
      'user': '********'}, ]
    """

    def get_log(self, start_day: str, end_day: str) -> List[Dict]:
        params = self.params.copy()
        params["start"] = start_day
        params["end"] = end_day

        def _get_log(page: int):
            params["page"] = page
            r = requests.get(os.path.join(self.reports_api_base, "details"), auth=self.auth, params=params)
            if r.status_code != 200:
                raise ValueError(f"HttpRequests Failed {r.status_code} {r.json()}")

            return r.json()["data"]

        # start_day ~ end_day で作成された記録を取得する
        r = requests.get(os.path.join(self.reports_api_base, "detail"), auth=self.auth, params=params)
        if r.status_code != 200:
            raise ValueError(f"HttpRequests Failed {r.status_code} {r.json()}")

        total_page = r.json()['total_count'] // r.json()['per_page'] + 1

        data = list(itertools.chain.from_iterable([_get_log(page + 1) for page in range(total_page)]))

        return data

    def get_processed_log(self, start_day: str, end_day: str) -> pd.DataFrame:
        logs = self.get_log(start_day, end_day)

        return self.parse_logs(logs)

    """
    取得したログをパースして desc, dur, start, end 形式のデータフレームを作成する
    """

    def parse_logs(self, logs: List[Dict]) -> pd.DataFrame:
        data = pd.DataFrame(logs)[["id", "description", "dur", "start", "end"]]
        # 計測時間されたは ms 単位になっている
        data["dur"] //= 60 * 1000

        # チケット名と説明を分離
        ticket_descs = data["description"].apply(self.extract_ticket)
        data["ticket"] = [t[0] for t in ticket_descs]
        data["desc"] = [t[1] for t in ticket_descs]

        return data[["id", "ticket", "desc", "dur", "start", "end"]]

    """
    タスク名から，チケット名と説明を分離
    """

    @staticmethod
    def extract_ticket(description: str) -> List[str]:
        tokens = description.split()

        if len(tokens) == 1:
            return [tokens[0], ""]

        return [tokens[0], "".join(tokens[1:])]
