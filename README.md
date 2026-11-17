# Skills

個人用のエージェントスキル集。

自作スキルとその依存関係は [APM](https://github.com/microsoft/apm) で管理する。
グローバルへの配布は [skillshare](https://github.com/runkids/skillshare) の merge モードを使う。

初回セットアップ（リポジトリのルートで実行）:

```sh
brew install apm skillshare
apm install --target codex
skillshare init --targets claude,universal --mode merge --no-copy --no-git --no-skill
skillshare link "$PWD/.agents/skills" --name _apm --enable -g
skillshare disable _apm/herdr -g
skillshare disable _apm/obsidian-cli -g
skillshare disable _apm/obsidian-markdown -g
skillshare target claude --target-naming standard -g
skillshare target universal --target-naming standard -g
sh scripts/install-external-skills.sh
skillshare status -g
```

既存の skillshare 環境では初期化せず、現在の設定を確認してから取り込む。
同期元の既定値は `~/.config/skillshare/skills/`。
`_apm` はこのリポジトリのローカル展開先へのリンクで、自作スキルを配布する。
Herdr・Obsidian は GitHub から skillshare に直接導入し、APM 展開分の同名 3 スキルだけを
skillshare の `.skillignore` で除外する。スキル本体の依存定義は維持する。
`standard` はスキル名に `_apm__` を付けずに配布するための設定。

自作スキルの編集・追加・削除後は、`skills/` の原本から再展開して同期する:

```sh
apm install --target codex
skillshare sync -g
```

APM 側の依存更新は `apm update --target codex`、skillshare で直接導入した
外部スキルの更新は `skillshare update --all -g` を使い、その後 `skillshare sync -g` を実行する。
APM のグローバルインストール（`-g`）は使わない。
Codex の組み込みスキルとサービス連携プラグインは別途管理する。


## テスト

開発用のシナリオと実行手順は [`test-skills/`](test-skills/) に置く。skillを変更したときは、必要に応じて対応するテストも更新し、振る舞いを確認する。anti-slopの実行手順は [`test-skills/anti-slop/RUN.md`](test-skills/anti-slop/RUN.md) を参照する。

テストには架空の入力と期待する振る舞いを記載し、個人情報や実際の会話・案件情報を含めない。生成結果・実行ログ・採点記録は一時ディレクトリで扱い、コミットしない。`test-skills/` はskillの配布対象に含めない。
