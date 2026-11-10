---
name: obsidian-notes
description: 自分の Obsidian ノートの運用規則。Obsidian ノートを作成・編集するときに必ず使う。
---

# Obsidian Notes

## ノート

- 指定がなければ `template/general_note` のテンプレートを使う。
- 不要な見出しを追加しない。
- フロントマターの `updated` はプラグインが自動更新するため編集しない。

## AI の作業ログ

- `ai-log` セクションに記録する。
- 各行に Zettelkasten 形式のタイムスタンプを付け、Markdown の箇条書きで記録する。
- 追記は [scripts/append_ai_log.py](scripts/append_ai_log.py) を介して行い、順序を保つ。呼び方は `--help` で確認する。
- 指示がない限り過去の `ai-log` を改変しない。
- 人間は読まない前提とし、自然言語である必要はない。

## タスクノート

`tags` に `task` を含むノートをタスクノートとして扱う。フロントマターは以下の意味で記録する。

- `status`: 完了した事実を表す20文字以内のラベル。
- `next_action`: 人間向けの次のアクションを20文字以内で記録。
- `next_action_detail`: AI が次のセッションで実行する最初の具体的手順。
