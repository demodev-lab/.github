#!/usr/bin/env python3
"""
주간 PR 리포트
- Organization 전체 PR 생성 수 + 리뷰 코멘트 수
- 레포별 / 사람별 breakdown
- 기간: 지난 금요일 16:00 KST ~ 이번 금요일 16:00 KST
"""

import json
import os
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone

GRAPHQL_URL = "https://api.github.com/graphql"
KST = timezone(timedelta(hours=9))
REPORT_HOUR = 16  # 매주 금요일 16시 발행


def graphql(query, variables=None):
    """GitHub GraphQL API 호출"""
    token = os.environ["GH_TOKEN"]
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        GRAPHQL_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    if "errors" in data:
        print(f"GraphQL errors: {json.dumps(data['errors'], indent=2)}", file=sys.stderr)
        sys.exit(1)
    return data["data"]


def get_report_range():
    """지난 금요일 16:00 KST ~ 이번 금요일 16:00 KST"""
    now_kst = datetime.now(KST)
    # 이번 금요일 16시 (오늘이 금요일이면 오늘)
    days_until_friday = (4 - now_kst.weekday()) % 7
    this_friday = now_kst.replace(hour=REPORT_HOUR, minute=0, second=0, microsecond=0) + timedelta(days=days_until_friday)
    # 지난 금요일 16시
    last_friday = this_friday - timedelta(days=7)
    return last_friday, this_friday


def to_github_date(dt):
    """GitHub Search API용 ISO 8601 형식"""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def search_prs_created(org, since, until):
    """이번 주 생성된 PR 조회"""
    query = """
    query($q: String!, $cursor: String) {
      search(query: $q, type: ISSUE, first: 100, after: $cursor) {
        issueCount
        pageInfo { hasNextPage endCursor }
        nodes {
          ... on PullRequest {
            number
            author { login }
            repository { name }
          }
        }
      }
    }
    """
    search_q = f"org:{org} type:pr created:{to_github_date(since)}..{to_github_date(until)}"
    return _paginate_search(query, search_q)


def search_prs_with_reviews(org, since, until):
    """이번 주 업데이트된 PR에서 리뷰 코멘트 조회"""
    query = """
    query($q: String!, $cursor: String) {
      search(query: $q, type: ISSUE, first: 100, after: $cursor) {
        issueCount
        pageInfo { hasNextPage endCursor }
        nodes {
          ... on PullRequest {
            number
            repository { name }
            reviews(last: 100) {
              nodes {
                author { login }
                createdAt
                comments { totalCount }
              }
            }
          }
        }
      }
    }
    """
    search_q = f"org:{org} type:pr updated:{to_github_date(since)}..{to_github_date(until)}"
    return _paginate_search(query, search_q)


def _paginate_search(query, search_q):
    """Search API 페이지네이션"""
    cursor = None
    results = []
    while True:
        data = graphql(query, {"q": search_q, "cursor": cursor})
        search = data["search"]
        results.extend([n for n in search["nodes"] if n])
        if not search["pageInfo"]["hasNextPage"]:
            break
        cursor = search["pageInfo"]["endCursor"]
        if len(results) >= 1000:
            print("Warning: 검색 결과 1000개 초과, 일부 누락 가능", file=sys.stderr)
            break
    return results


def aggregate(created_prs, updated_prs, since, until):
    """통계 집계"""
    pr_by_repo = defaultdict(int)
    pr_by_person = defaultdict(int)
    comments_by_repo = defaultdict(int)
    comments_by_person = defaultdict(int)

    # PR 생성 통계
    for pr in created_prs:
        repo = pr["repository"]["name"]
        author = pr["author"]["login"] if pr.get("author") else "ghost"
        pr_by_repo[repo] += 1
        pr_by_person[author] += 1

    # 리뷰 코멘트 통계 (이번 주 기간 내에 작성된 리뷰만)
    since_str = to_github_date(since)
    until_str = to_github_date(until)
    for pr in updated_prs:
        repo = pr["repository"]["name"]
        for review in pr.get("reviews", {}).get("nodes", []):
            created_at = review.get("createdAt", "")
            if not (since_str <= created_at <= until_str):
                continue
            reviewer = review["author"]["login"] if review.get("author") else "ghost"
            count = review["comments"]["totalCount"]
            comments_by_repo[repo] += count
            comments_by_person[reviewer] += count

    desc = lambda d: dict(sorted(d.items(), key=lambda x: -x[1]))
    return {
        "total_prs": sum(pr_by_repo.values()),
        "total_comments": sum(comments_by_repo.values()),
        "pr_by_repo": desc(pr_by_repo),
        "pr_by_person": desc(pr_by_person),
        "comments_by_repo": desc(comments_by_repo),
        "comments_by_person": desc(comments_by_person),
    }


def ranking(data, unit="건", limit=10):
    """순위 텍스트 포맷"""
    items = list(data.items())[:limit]
    if not items:
        return "활동 없음"
    return "\n".join(f"{i}. {name}: {count}{unit}" for i, (name, count) in enumerate(items, 1))


def send_slack(stats, since, until):
    """Slack Bot Token으로 메시지 전송"""
    token = os.environ["SLACK_BOT_TOKEN"]
    channel = os.environ["SLACK_CHANNEL_ID"]

    since_str = since.astimezone(KST).strftime("%m/%d %H:%M")
    until_str = until.astimezone(KST).strftime("%m/%d %H:%M")

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "📊 주간 PR 리포트", "emoji": True},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*총 PR:*\n{stats['total_prs']}건"},
                {"type": "mrkdwn", "text": f"*총 리뷰 코멘트:*\n{stats['total_comments']}건"},
            ],
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*📁 레포별 PR*\n```\n{ranking(stats['pr_by_repo'])}```",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*👤 사람별 PR*\n```\n{ranking(stats['pr_by_person'])}```",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*📁 레포별 리뷰 코멘트*\n```\n{ranking(stats['comments_by_repo'])}```",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*👤 사람별 리뷰 코멘트*\n```\n{ranking(stats['comments_by_person'])}```",
            },
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"📅 {since_str} ~ {until_str}"}],
        },
    ]

    payload = json.dumps({
        "channel": channel,
        "attachments": [{"color": "#6C5CE7", "blocks": blocks}],
    }).encode()

    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )

    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
    if not result.get("ok"):
        print(f"Slack error: {result.get('error')}", file=sys.stderr)
        sys.exit(1)
    print("Slack 전송 완료!")


def main():
    org = os.environ.get("ORG_NAME")
    if not org:
        print("Error: ORG_NAME 환경변수 필요", file=sys.stderr)
        sys.exit(1)

    since, until = get_report_range()
    since_fmt = since.astimezone(KST).strftime("%Y-%m-%d %H:%M")
    until_fmt = until.astimezone(KST).strftime("%Y-%m-%d %H:%M")
    print(f"📊 {org} 주간 PR 리포트 ({since_fmt} ~ {until_fmt})")

    created_prs = search_prs_created(org, since, until)
    print(f"  생성된 PR: {len(created_prs)}건")

    updated_prs = search_prs_with_reviews(org, since, until)
    print(f"  리뷰 활동 PR: {len(updated_prs)}건")

    stats = aggregate(created_prs, updated_prs, since, until)
    print(f"  합계: PR {stats['total_prs']}건, 리뷰 코멘트 {stats['total_comments']}건")

    send_slack(stats, since, until)


if __name__ == "__main__":
    main()
