# 📋 Table Tools 사용 가이드

게임 데이터 시트 관리를 위한 두 가지 자동화 도구입니다.

---

## 🔧 도구 소개

| 도구 | 설명 |
|------|------|
| **sheet merge** | 브랜치(작업) 시트의 내용을 근본 데이터 시트에 반영 |
| **table pr** | 근본 데이터 시트의 CSV를 GitHub에 푸시하고 PR 링크 생성 |

### 일반적인 작업 흐름

```
브랜치 시트 작업
      ↓
sheet merge → 근본 시트에 반영 + 버전 업데이트
      ↓
table pr → GitHub에 CSV 푸시 → PR 오픈
```

---

## 📦 설치 및 디렉토리 구조

### 스크립트 다운로드

```bash
git clone https://github.com/jaeho0103/table-pr-agent-scripts.git
cd table-pr-agent-scripts
```

### 디렉토리 구조

```
table-pr-agent-scripts/
├── scripts/
│   └── create-tablecsv-pr.py   ← table pr 실행 스크립트
├── config/
│   ├── tablecsv.json            ← 실제 설정 파일 (gitignore 처리됨)
│   └── tablecsv.example.json   ← 설정 파일 양식
└── README.md
```

> ⚠️ **모든 명령은 `table-pr-agent-scripts/` 루트 디렉토리에서 실행하세요.**
> `scripts/` 또는 `config/` 폴더 안에서 실행하면 경로 오류가 발생합니다.

---

## 1. sheet merge

### 무엇을 하나요?
브랜치(작업용) 구글 시트의 각 탭 데이터를 근본 데이터 시트의 해당 서브문서에 자동으로 반영합니다.
반영 후 근본 시트 `기본` 탭의 E열(업데이트 버전)도 자동으로 갱신됩니다.

### 버전 정보 위치
브랜치 시트의 **`개요` 탭 C1 셀**에 버전이 기재되어 있어야 합니다. (예: `v200420`)

### 사용 방법
아래 URL을 브라우저에서 열면 실행됩니다. **별도 설치나 스크립트 실행 없이 URL 접속만으로 동작합니다.**

```
https://script.google.com/macros/s/AKfycbyxzhCZBFDf3tjRpzVXPnvZdsSR-3I3oQVuXXA_1yBqekHaSI-Ho_WfdiicbR4FxpgI7A/exec?sheetId=브랜치시트ID
```

**브랜치 시트 ID 찾는 방법:**
구글 시트 URL에서 `/d/` 뒤, `/edit` 앞의 값입니다.
```
https://docs.google.com/spreadsheets/d/[여기가 ID]/edit
```

### 결과 확인
실행 후 JSON 결과가 출력됩니다:
```json
{
  "success": true,
  "message": "완료",
  "data": {
    "version": "v200420",       ← 반영된 버전
    "updated": ["SheetA", ...], ← 성공적으로 반영된 탭 목록
    "skipped": ["개요", ...],   ← 건너뛴 탭 (관리용 탭, 매핑 없음 등)
    "errors": []                ← 오류 목록
  }
}
```

### skipped 항목 판단 기준
| 표시 | 의미 | 조치 |
|------|------|------|
| `개요`, `테스트환경 셋팅`, `상시 업무` 등 | 정상 — CSV 아닌 관리용 탭 | 없음 |
| `[TEST]` 접미사 있는 탭 | 정상 — 테스트 전용 탭, 배포 대상 아님 | 없음 |
| `[HEIMDALL]` 접미사 있는 탭 | 정상 — Heimdall 전용 CSV, 근본 시트 백업 대상 아님 | 없음 |
| `(서브문서에 탭 없음)` | 근본 시트 서브문서에 해당 탭이 없음 | 수동 확인 필요 |
| 탭 이름만 있고 괄호 없음 | 근본 시트 `기본` 탭 D열에 링크 없음 | 링크 추가 필요 |

> **참고**: `[HEIMDALL]` 탭은 Heimdall 체인 전용 데이터로, 별도 관리됩니다. 근본 시트의 백업 구조에 포함되지 않으므로 skipped되는 것이 정상입니다.

### 신규 시트 추가 시
근본 시트 `기본` 탭에 아래 내용을 추가해야 합니다:
1. **C열**: CSV 이름 입력
2. **D열**: 해당 CSV가 속한 서브문서 링크를 **하이퍼링크**로 입력 (같은 폴더 그룹이면 폴더 첫 행에만 추가해도 됨)

---

## 2. table pr

### 무엇을 하나요?
근본 데이터 시트의 지정된 탭들을 CSV로 변환해 GitHub 브랜치에 푸시합니다.
이후 PR 링크를 클릭해서 직접 PR을 열면 됩니다.

### 사전 준비 (최초 1회)

**1. 스크립트 다운로드**
위 [설치 및 디렉토리 구조](#-설치-및-디렉토리-구조) 섹션을 참고하세요.

**2. `planetarium/lib9c` Fork 생성**
GitHub에서 [planetarium/lib9c](https://github.com/planetarium/lib9c)에 접속한 뒤, 우측 상단 **Fork** 버튼을 눌러 본인 계정에 fork합니다.
fork 주소 예시: `https://github.com/본인GitHub아이디/lib9c`

> ⚠️ fork가 없으면 스크립트가 브랜치를 푸시할 곳이 없어 실패합니다.

**3. Python 패키지 설치**
```bash
pip3 install requests gspread
# 또는
python3 -m pip install requests gspread
```

**4. config 파일 작성**
`config/tablecsv.example.json`을 복사해 `config/tablecsv.json`을 만들고 내용을 채웁니다:
```bash
cp config/tablecsv.example.json config/tablecsv.json
```

```json
{
  "github_token": "github_pat_xxxx",
  "upstream_repo": "planetarium/lib9c",
  "fork_owner": "본인GitHub아이디",
  "base_branch": "development",
  "spreadsheet_id": "근본시트ID",
  "csv_path": "Lib9c/TableCSV"
}
```

> ⚠️ `config/tablecsv.json`은 절대 GitHub에 올리지 마세요. `.gitignore`에 이미 등록되어 있습니다.

**5. GitHub 토큰 권한 확인**
토큰은 본인 fork 레포(`fork_owner/lib9c`)에 **Contents: Read & Write** 권한이 있어야 합니다.

### 사용 방법

```bash
# 저장된 시트 기준으로 실행 (config의 spreadsheet_id 사용)
python3 scripts/create-tablecsv-pr.py

# 다른 시트 URL을 지정해서 실행
python3 scripts/create-tablecsv-pr.py "https://docs.google.com/spreadsheets/d/시트ID/..."
```

> **참고**: 다른 시트 URL을 인수로 전달하면, 해당 시트 ID가 `config/tablecsv.json`의 `spreadsheet_id`에 **자동으로 저장**됩니다. 이후 인수 없이 실행하면 새로 저장된 시트가 기본값으로 사용됩니다.

### 실행 순서
1. 구글 시트에서 탭 CSV 다운로드
2. `planetarium/lib9c:development` 기준 변경된 파일만 감지
3. `본인아이디/lib9c` fork의 development 브랜치 동기화
4. `update/tablecsv-YYYYMMDD-HHMM` 브랜치 생성 후 CSV 업로드
5. PR 오픈 링크 출력

### 결과 예시
```
✅ 21개 파일 업로드 완료 (브랜치: update/tablecsv-20260401-1030)

PR 오픈 링크:
https://github.com/planetarium/lib9c/compare/development...본인아이디:update/tablecsv-20260401-1030?expand=1
```

링크를 클릭하면 GitHub에서 PR을 직접 열 수 있습니다.

---

## ❓ 자주 묻는 문제

**Q. sheet merge 실행했는데 아무것도 updated가 없어요**
→ 브랜치 시트 탭 이름이 근본 시트 C열의 CSV명과 정확히 일치하는지 확인하세요.

**Q. 서브문서에 탭 없음이 뜨는데 탭이 분명 있어요**
→ 탭 이름에 공백이나 대소문자 차이가 있을 수 있습니다. 정확히 비교해보세요.

**Q. [HEIMDALL] 탭이 전부 skipped인데 정상인가요?**
→ 네, 정상입니다. Heimdall 탭은 근본 시트 백업 구조에 포함되지 않아 의도적으로 건너뜁니다.

**Q. table pr에서 변경된 파일이 0개예요**
→ 시트 내용이 현재 GitHub development 브랜치와 동일한 경우입니다. 실제로 수정된 내용이 있는지 확인하세요.

**Q. GitHub 푸시가 403 오류로 실패해요**
→ `config/tablecsv.json`의 `github_token`이 만료되었거나 권한이 부족합니다. 토큰을 재발급하세요.

**Q. "No module named 'requests'" 오류가 나요**
→ `pip3 install requests gspread` 명령으로 패키지를 설치하세요. `pip`가 아닌 `pip3`를 사용해야 합니다.

**Q. 스크립트 실행 시 "config not found" 또는 경로 오류가 나요**
→ `table-pr-agent-scripts/` 루트 디렉토리에서 실행하고 있는지 확인하세요. `scripts/` 폴더 안에서 실행하면 경로 오류가 발생합니다.
