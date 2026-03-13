# table-pr-agent-scripts

Google Sheets CSV → GitHub PR 자동화 에이전트 스크립트

## 기능

- 구글 시트의 탭을 읽어 CSV로 변환
- GitHub 레포의 기존 CSV와 비교해 변경된 파일만 감지
- Fork 브랜치에 변경된 CSV 업로드
- PR 오픈 링크 제공

## 사용법

```
table pr
table pr https://docs.google.com/spreadsheets/d/...
```

## 설정

`config/tablecsv.json` 생성 (예시: `config/tablecsv.example.json` 참고):

```json
{
  "github_token": "your_github_pat_here",
  "upstream_repo": "planetarium/lib9c",
  "fork_owner": "your_github_username",
  "base_branch": "development",
  "spreadsheet_id": "your_google_spreadsheet_id",
  "csv_path": "Lib9c/TableCSV"
}
```

## 스크립트

- `scripts/create-tablecsv-pr.py` — 메인 스크립트
- `scripts/bnkr-gunpla-monitor.py` — 반다이남코코리아몰 건프라 신상품 모니터링
