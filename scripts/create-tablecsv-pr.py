#!/usr/bin/env python3
"""
Google Sheets → GitHub 브랜치 푸시 스크립트
- 구글 시트 탭에서 CSV 추출 후 변경된 것만 fork 브랜치에 업로드
- PR은 GitHub에서 직접 열기 (Compare & pull request 버튼)

Usage: python3 create-tablecsv-pr.py
"""

import urllib.request
import urllib.parse
import json
import csv
import io
import base64
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Config 로드
CONFIG_FILE = Path(__file__).parent.parent / "config" / "tablecsv.json"
config = json.loads(CONFIG_FILE.read_text())

GITHUB_TOKEN   = config["github_token"]
UPSTREAM_REPO  = config["upstream_repo"]
FORK_OWNER     = config["fork_owner"]
FORK_REPO      = f"{FORK_OWNER}/lib9c"
BASE_BRANCH    = config["base_branch"]
SPREADSHEET_ID = config["spreadsheet_id"]
CSV_PATH       = config["csv_path"]

# 구글 시트에 존재하는 탭 목록 (repo에 매핑되는 것만)
ALL_TABS = [
    "CollectionSheet", "CrystalEquipmentGrindingSheet", "ItemRequirementSheet",
    "EnhancementCostSheetV3", "MaterialItemSheet", "EquipmentItemSheet",
    "EquipmentItemRecipeSheet", "EquipmentItemSubRecipeSheetV2", "EquipmentItemOptionSheet",
    "InfiniteTowerScheduleSheet", "InfiniteTowerFloorSheet", "InfiniteTowerFloorWaveSheet",
    "InfiniteTowerConditionSheet", "StakeRegularRewardSheet_V10", "SynthesizeSheet",
    "RuneSheet", "RuneListSheet", "RuneOptionSheet", "RuneCostSheet",
    "SynthesizeWeightSheet", "PatrolRewardSheet"
]


def gh_request(method, path, data=None):
    url = f"https://api.github.com{path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "User-Agent": "openclaw-agent",
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        raise Exception(f"GitHub {method} {path} → {e.code}: {err}")


def fetch_sheet_csv(tab_name):
    url = (
        f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"
        f"/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(tab_name)}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=30)
    return resp.read().decode("utf-8", errors="replace")


def clean_csv(raw_csv):
    """빈 trailing 컬럼/행 제거"""
    reader = csv.reader(io.StringIO(raw_csv))
    rows = list(reader)
    if not rows:
        return ""
    max_col = max((i for i, h in enumerate(rows[0]) if h.strip()), default=0)
    cleaned = [row[:max_col + 1] for row in rows if any(c.strip() for c in row[:max_col + 1])]
    out = io.StringIO()
    csv.writer(out, lineterminator='\r\n').writerows(cleaned)
    return out.getvalue()


def get_upstream_file_sha(file_path):
    try:
        result = gh_request("GET", f"/repos/{UPSTREAM_REPO}/contents/{file_path}?ref={BASE_BRANCH}")
        return result["sha"], result.get("content", "")
    except:
        return None, ""


def main():
    now = datetime.now(timezone.utc)
    branch_name = f"update/tablecsv-{now.strftime('%Y%m%d-%H%M')}"

    print(f"🔍 변경된 CSV 탐지 중...")

    # 1. 변경된 탭 찾기
    changed = []
    for tab in ALL_TABS:
        try:
            gs_raw = fetch_sheet_csv(tab)
            gs_csv = clean_csv(gs_raw)
            file_path = f"{CSV_PATH}/{tab}.csv"
            sha, gh_content_b64 = get_upstream_file_sha(file_path)
            if sha:
                gh_csv = base64.b64decode(gh_content_b64.replace('\n', '')).decode('utf-8', errors='replace')
            else:
                gh_csv = ""
            if gs_csv.strip() != gh_csv.strip():
                changed.append((tab, gs_csv, sha))
                print(f"  📝 {tab}.csv — 변경됨")
            else:
                print(f"  ✅ {tab}.csv — 동일")
        except Exception as e:
            print(f"  ⚠️  {tab}.csv — 스킵 ({e})")

    if not changed:
        print("\n변경된 CSV 없음. 브랜치 생성 불필요.")
        return

    print(f"\n총 {len(changed)}개 변경 감지 → 브랜치 생성 시작")

    # 2. upstream development 최신 SHA
    ref = gh_request("GET", f"/repos/{UPSTREAM_REPO}/git/ref/heads/{BASE_BRANCH}")
    base_sha = ref["object"]["sha"]

    # 3. fork development 동기화
    try:
        gh_request("POST", f"/repos/{FORK_REPO}/merge-upstream", {"branch": BASE_BRANCH})
        print(f"✅ Fork development 동기화")
    except Exception as e:
        print(f"⚠️  동기화 스킵: {e}")

    # 4. 새 브랜치 생성
    gh_request("POST", f"/repos/{FORK_REPO}/git/refs", {
        "ref": f"refs/heads/{branch_name}",
        "sha": base_sha
    })
    print(f"🌿 브랜치 생성: {branch_name}")

    # 5. 변경된 CSV 업로드
    uploaded = []
    failed = []
    for tab, content, sha in changed:
        file_path = f"{CSV_PATH}/{tab}.csv"
        try:
            encoded = base64.b64encode(content.encode("utf-8")).decode()
            payload = {
                "message": f"Update {tab}.csv from Google Sheets",
                "content": encoded,
                "branch": branch_name,
            }
            if sha:
                payload["sha"] = sha
            gh_request("PUT", f"/repos/{FORK_REPO}/contents/{file_path}", payload)
            print(f"  ✅ {tab}.csv 업로드 완료")
            uploaded.append(tab)
        except Exception as e:
            print(f"  ❌ {tab}.csv 실패: {e}")
            failed.append(tab)

    # 6. 결과 출력
    pr_title = urllib.parse.quote(f"[TableCSV] Update from Google Sheets ({now.strftime('%Y-%m-%d')})")
    compare_url = (
        f"https://github.com/{UPSTREAM_REPO}/compare/{BASE_BRANCH}...{FORK_OWNER}:{branch_name}"
        f"?expand=1&title={pr_title}"
    )

    print(f"\n{'='*60}")
    print(f"✅ 완료! {len(uploaded)}개 업로드 / {len(failed)}개 실패")
    print(f"\n📌 아래 링크에서 PR 열어주세요:")
    print(f"{compare_url}")
    print(f"{'='*60}")

    return compare_url


if __name__ == "__main__":
    main()
