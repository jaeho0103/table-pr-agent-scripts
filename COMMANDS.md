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

## `arena`

**설명**: 아레나 보상 공지용 PPTX (2슬라이드: Odin Championship + Heimdall Season)를 생성하고 파일로 전송한다.

**입력 형식** (게임에서 받는 데이터를 그대로 붙여넣기):
```
[오딘챔피언십번호] [오딘시작블록] [오딘종료블록] CHAMPIONSHIP [인터벌] [메달수] [오딘상금] 오딘 챔피언십
[헤임달시즌번호] [헤임달시작블록] [헤임달종료블록] SEASON [인터벌] [0] [헤임달상금] 헤임달
오딘현재블록: [블록번호]
헤임달현재블록: [블록번호]
```

**예시**:
```
21 17889224 18040423 CHAMPIONSHIP 10800 60 500000 오딘 챔피언십
21 9412781 9563980 SEASON 10800 0 400000 헤임달
오딘현재블록: 17862624
헤임달현재블록: 9365492
```

**동작**:
- 날짜 자동 계산 (현재 블록 기준, 8초/블록)
- 상금에 따라 보상 테이블 자동 재계산
- 2슬라이드 PPTX 생성 후 전송

**스크립트**: `scripts/create-arena-pptx.py`
**템플릿**: `assets/arena/template.pptx`

---

## `sheet merge [브랜치시트URL]`

**설명**: 브랜치 시트의 내용을 근본 시트(서브문서들)에 반영한다.
Apps Script 웹앱을 호출해 브랜치 시트 탭 → 해당 서브문서 탭으로 데이터를 덮어쓴다.

**사용법**:
- `sheet merge https://docs.google.com/spreadsheets/d/시트ID/...`

**동작 순서**:
1. 브랜치 시트 URL에서 sheetId 추출
2. Apps Script 웹앱 호출: `WEBAPP_URL?sheetId=...`
3. 결과(updated / skipped / errors) 출력

**설정**:
- 웹앱 URL: `https://script.google.com/macros/s/AKfycbyxzhCZBFDf3tjRpzVXPnvZdsSR-3I3oQVuXXA_1yBqekHaSI-Ho_WfdiicbR4FxpgI7A/exec`
- 근본 시트: `https://docs.google.com/spreadsheets/d/1IFRZ5bdwbIeDadq0HnpZwhLs3G6H5ZxSXwMbvq1erHE`

---

## `건프라 모니터 시작` / `건프라 모니터 중지`

**설명**: 반다이남코코리아몰 건프라 신상품 모니터링 cron을 활성화/비활성화한다.

- 모니터 cron ID: `2b7b5708-e7b5-41d4-808d-eef19977dc26`
- 리포트 cron ID: `d0cc92d8-023c-4eae-8e6b-896df52a9f60`
