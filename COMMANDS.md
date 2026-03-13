# COMMANDS.md - 커맨드 목록

사용자가 아래 커맨드를 입력하면 해당 작업을 즉시 실행한다.

---

## `table pr`

**설명**: 구글 시트의 CSV 데이터를 GitHub fork 브랜치에 푸시하고 PR 링크를 안내한다.

**사용법**:
- `table pr` → 마지막으로 사용한 시트(config 저장값) 기준으로 실행
- `table pr [구글시트URL]` → 해당 시트로 실행하고 config에 저장 (다음번 기본값이 됨)

**예시**:
```
table pr
table pr https://docs.google.com/spreadsheets/d/1ARhJYwOU9.../edit
```

**실행 방법**:
```bash
# 기본 시트
python3 /home/node/.openclaw/workspace/scripts/create-tablecsv-pr.py

# 시트 URL 지정
python3 /home/node/.openclaw/workspace/scripts/create-tablecsv-pr.py "https://docs.google.com/spreadsheets/d/..."
```

**동작 순서**:
1. 구글 시트 탭 전체 스캔 → CSV 변환
2. `planetarium/lib9c:development` 기준 변경된 파일만 감지
3. `jaeho0103/lib9c` fork development 동기화
4. `update/tablecsv-YYYYMMDD-HHMM` 브랜치 생성
5. 변경된 CSV 업로드
6. PR 오픈 링크 출력 → 사용자가 클릭해서 PR 생성

**설정 파일**: `config/tablecsv.json`
- GitHub 토큰, fork/upstream repo, 마지막 사용 스프레드시트 ID 저장

---

## `건프라 모니터 시작` / `건프라 모니터 중지`

**설명**: 반다이남코코리아몰 건프라 신상품 모니터링 cron을 활성화/비활성화한다.

- 모니터 cron ID: `2b7b5708-e7b5-41d4-808d-eef19977dc26`
- 리포트 cron ID: `d0cc92d8-023c-4eae-8e6b-896df52a9f60`
