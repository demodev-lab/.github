# GitHub Workflows - Slack 알림 시스템

이 레포지토리는 GitHub Actions와 Slack을 연동한 알림 워크플로우를 제공합니다.

## 📁 디렉토리 구조

```
.github/
├── workflows/          # 실제 실행되는 reusable workflow
│   ├── notify-slack-deploy.yml      # 배포 알림 (성공/실패)
│   ├── notify-slack-pr-open.yml     # PR 생성 알림
│   └── notify-slack-merge.yml       # PR 머지 알림
│
└── example/            # 사용 예시 (복사해서 사용)
    ├── notify-slack-deploy.yml      # 배포 알림 사용 예시
    ├── notify-slack-pr-open.yml     # PR 생성 알림 사용 예시
    └── notify-slack-merge.yml       # PR 머지 알림 사용 예시
```

## 🚀 빠른 시작

### 1. Secrets 설정

Repository Settings > Secrets and variables > Actions에서 다음 값을 설정하세요:

| Secret | 설명 | 예시 |
|--------|------|------|
| `SLACK_BOT_TOKEN` | Slack Bot OAuth Token | `xoxb-1234567890-...` |
| `SLACK_CHANNEL_ID` | 알림 채널 ID | `C01ABCD2EFG` |

### 2. 워크플로우 선택 및 적용

| 알림 종류 | 사용 방법 |
|----------|----------|
| 📢 배포 알림 | 기존 배포 워크플로우에 job 추가 |
| 📝 PR 생성 알림 | example 파일을 workflows로 복사 |
| ✅ PR 머지 알림 | example 파일을 workflows로 복사 |

---

## 📢 배포 알림 (notify-slack-deploy)

배포 성공/실패 시 Slack으로 알림을 보냅니다.

### 표시 정보
- 레포지토리명
- 커밋 (SHA 7자리)
- 브랜치
- 실행자
- 로그 링크 (실패 시)

### 사용 방법

**기존 배포 워크플로우에 아래 내용을 추가하세요:**

```yaml
  # 배포 성공 시 알림
  notify-success:
    needs: deploy  # ⚠️ 실제 배포 job 이름으로 변경
    if: success()
    uses: demodev-lab/.github/.github/workflows/notify-slack-deploy.yml@main
    with:
      status: 'success'
    secrets:
      SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
      SLACK_CHANNEL_ID: ${{ secrets.SLACK_CHANNEL_ID }}

  # 배포 실패 시 알림
  notify-failure:
    needs: deploy  # ⚠️ 실제 배포 job 이름으로 변경
    if: failure()
    uses: demodev-lab/.github/.github/workflows/notify-slack-deploy.yml@main
    with:
      status: 'failure'
    secrets:
      SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
      SLACK_CHANNEL_ID: ${{ secrets.SLACK_CHANNEL_ID }}
```

> 📄 자세한 내용은 [.github/example/notify-slack-deploy.yml](.github/example/notify-slack-deploy.yml) 참고

---

## 📝 PR 생성 알림 (notify-slack-pr-open)

새로운 PR이 생성되면 Slack으로 알림을 보냅니다.

### 표시 정보
- 레포지토리명
- 번호
- 브랜치 (source → target)
- 작성자
- PR 보기 (제목)

### 사용 방법

**`.github/workflows/` 폴더에 새 파일을 생성하세요:**

```yaml
name: PR Notification

on:
  pull_request:
    types: [opened, reopened, ready_for_review]

jobs:
  slack-pr-open-notification:
    if: github.event.pull_request.draft == false
    uses: demodev-lab/.github/.github/workflows/notify-slack-pr-open.yml@main
    secrets:
      SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
      SLACK_CHANNEL_ID: ${{ secrets.SLACK_CHANNEL_ID }}
```

### 트리거 옵션

| 타입 | 설명 |
|------|------|
| `opened` | PR 생성 시 |
| `reopened` | PR 재오픈 시 |
| `ready_for_review` | Draft → Ready 변경 시 |

> ⚠️ `if: github.event.pull_request.draft == false` 조건으로 Draft PR은 알림이 가지 않습니다.

> 📄 자세한 내용은 [.github/example/notify-slack-pr-open.yml](.github/example/notify-slack-pr-open.yml) 참고

---

## ✅ PR 머지 알림 (notify-slack-merge)

PR이 머지되면 Slack으로 알림을 보냅니다.

### 표시 정보
- 레포지토리명
- 작성자
- 브랜치 (source → target)
- 머지한 사람

### 사용 방법

**`.github/workflows/` 폴더에 새 파일을 생성하세요:**

```yaml
name: Merge Notification

on:
  pull_request:
    types: [closed]

jobs:
  slack-merge-notification:
    if: github.event.pull_request.merged == true
    uses: demodev-lab/.github/.github/workflows/notify-slack-merge.yml@main
    secrets:
      SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
      SLACK_CHANNEL_ID: ${{ secrets.SLACK_CHANNEL_ID }}
```

> ⚠️ `if: github.event.pull_request.merged == true` 조건이 있어야 머지 없이 닫힌 PR은 알림이 가지 않습니다.

> 📄 자세한 내용은 [.github/example/notify-slack-merge.yml](.github/example/notify-slack-merge.yml) 참고

---

## 🔧 Slack 설정 가이드

### Slack App 생성
1. [Slack API](https://api.slack.com/apps)에서 새 앱 생성
2. **OAuth & Permissions** 메뉴에서 Bot Token Scopes 추가:
   - `chat:write`
   - `chat:write.public` (봇이 초대되지 않은 공개 채널에 메시지 전송 시)
3. **Install to Workspace** 클릭
4. **Bot User OAuth Token** 복사 → `SLACK_BOT_TOKEN`

### 채널 ID 확인
1. Slack에서 채널 우클릭 > **채널 세부정보 보기**
2. 하단의 채널 ID 복사 (C로 시작하는 11자리)

---

## 📋 워크플로우 사용 방식

### 중앙 레포 사용 (권장)
```yaml
uses: demodev-lab/.github/.github/workflows/notify-slack-deploy.yml@main
```
- 중앙에서 관리, 업데이트 자동 반영
- 여러 레포에서 동일한 워크플로우 사용 가능

### 로컬 사용
```yaml
uses: ./.github/workflows/notify-slack-deploy.yml
```
- workflows 폴더에 파일 복사 필요
- 레포별 커스터마이징 가능
