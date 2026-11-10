# 導入方法

```sh
npx skills add soyomogi/skills
```

## シンボリックリンク

このリポジトリのルートで実行する。

### 追加

```sh
for target in "$HOME/.agents/skills" "$HOME/.claude/skills"; do
  mkdir -p "$target"
  for skill in "$PWD"/skills/*/; do
    skill="${skill%/}"
    ln -s "$skill" "$target/${skill##*/}"
  done
done
```

### 削除

```sh
for target in "$HOME/.agents/skills" "$HOME/.claude/skills"; do
  for skill in "$PWD"/skills/*/; do
    skill="${skill%/}"
    link="$target/${skill##*/}"
    if [ -L "$link" ] && [ "$(readlink "$link")" = "$skill" ]; then
      unlink "$link"
    fi
  done
done
```
