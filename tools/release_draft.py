import argparse
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import quote


REPOSITORY = "chzhonge/stock-bot"
REPO_ROOT = Path(__file__).resolve().parents[1]


def run(*command):
    result = subprocess.run(
        command, cwd=REPO_ROOT, capture_output=True, encoding="utf-8",
        errors="replace", check=True,
    )
    return result.stdout.strip()


def github_ref(ref):
    endpoint = f"repos/{REPOSITORY}/git/matching-refs/{quote(ref)}"
    matches = json.loads(run("gh", "api", "--hostname", "github.com", endpoint))
    for match in matches:
        if match["ref"] == f"refs/{ref}":
            return match["object"]["sha"]
    return None


def main():
    parser = argparse.ArgumentParser(description="建立 stock-bot 的 GitHub Release 草稿")
    parser.add_argument("version", help="正式版本號，例如 1.0.0 或 v1.0.0")
    parser.add_argument("--summary", required=True, help="標題用的單行版本重點")
    parser.add_argument("--notes-file", type=Path, required=True, help="UTF-8 Markdown 發行說明")
    args = parser.parse_args()

    version = args.version.removeprefix("v")
    if not re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*)){2}", version):
        parser.error("版本號必須是 1.0.0 或 v1.0.0 這類正式版本")
    tag = f"v{version}"
    if len(tag) > 128:
        parser.error("版本標籤不得超過 Docker 的 128 字元限制")

    summary = args.summary.strip()
    if len(summary.splitlines()) != 1:
        parser.error("版本重點必須是非空白的單行文字")

    try:
        notes_file = args.notes_file.expanduser().resolve(strict=True)
        if not notes_file.read_text(encoding="utf-8-sig").strip():
            parser.error("發行說明不能空白")

        branch = run("git", "symbolic-ref", "--short", "HEAD")
        commit = run("git", "rev-parse", "HEAD")
        run("gh", "auth", "status", "--hostname", "github.com")
        if github_ref(f"heads/{branch}") != commit:
            parser.error(f"本機 HEAD 必須和 GitHub 上的 {REPOSITORY}:{branch} 一致")
        if github_ref(f"tags/{tag}") is not None:
            parser.error(f"GitHub 上已存在 {tag}，請使用新的版本號")
        existing_release = run(
            "gh", "api", "--hostname", "github.com", "--paginate",
            f"repos/{REPOSITORY}/releases",
            "--jq", f'.[] | select(.tag_name == "{tag}") | .id',
        )
        if existing_release:
            parser.error(f"GitHub 上已存在 {tag} 的 Release，請到 GitHub 查看")

        draft_url = run(
            "gh", "release", "create", tag,
            "--repo", f"github.com/{REPOSITORY}",
            "--target", commit,
            "--title", f"stock-bot {tag} - {summary}",
            "--notes-file", str(notes_file),
            "--draft",
        )
    except subprocess.CalledProcessError as error:
        parser.exit(1, f"{error.stderr.strip() or error}\n")
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")

    print(draft_url)


if __name__ == "__main__":
    main()
