# Skills

## リポジトリ内で使う

Codex は `.agents/skills/` の相対 symlink を通じて `skills/` の自作スキルを読む。外部依存は [APM](https://github.com/microsoft/apm) で展開する。展開するコミットは `apm.lock.yaml` に記録している。

```sh
apm install --target codex --frozen
```

Windows で相対 symlink を使う場合は、開発者モードを有効にして `git clone -c core.symlinks=true` で取得する。

## グローバルに配布する

dotfiles を使う場合は、[dotfiles のセットアップ手順](https://github.com/soyomogi/dotfiles#skillshare-%E3%81%AE%E8%A8%AD%E5%AE%9A%E3%81%A8%E5%90%8C%E6%9C%9F)に従う。[skillshare](https://github.com/runkids/skillshare) を単独で設定する場合は、このリポジトリのルートで実行する。初期化済みなら最初の行を省く。旧手順で `_apm` を登録している場合は、先に `skillshare unlink _apm -g` を実行する。

```sh
skillshare init --targets claude,universal --mode copy --no-copy --no-git --no-skill
skillshare link "$PWD/skills" --name soyomogi --enable -g
skillshare target claude --mode copy --target-naming standard -g
skillshare target universal --mode copy --target-naming standard -g
sh scripts/install-external-skills.sh
```

自作スキルを追加・削除したら、対応する `.agents/skills/` の symlink も更新する。グローバルのコピーは `skillshare sync -g` で更新し、extras を使う場合は続けて `skillshare sync extras -g` を実行する。

外部スキルの更新には、リポジトリ内では `apm update --target codex`、グローバルでは `skillshare update --all -g` を使う。

## テスト

スキルを変更したら、対応する [テストシナリオ](test-skills/) で動作を確認する。anti-slop の実行手順は [RUN.md](test-skills/anti-slop/RUN.md) を参照。

テストには架空の入力と期待する振る舞いを記載する。生成結果、実行ログ、採点記録は一時ディレクトリに置き、Git で管理するのはシナリオと手順に限る。
