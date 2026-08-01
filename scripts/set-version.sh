#!/usr/bin/env bash
# レポートの版（VERSION の中身）を report/_quarto.yml に反映する。
#
# 版は日付（YYYY-MM-DD）で、レポートを発行した日を指す。調査基準日とは別物。
# 版が入るのは _quarto.yml の3箇所で、ここがずれると
#   - PDF のファイル名と表紙の日付が食い違う
#   - フッタの版だけ古いまま
# といった事故になるため、書き換えはこのスクリプトに寄せてある。
#
#   scripts/set-version.sh          VERSION の値を _quarto.yml に書き込む
#   scripts/set-version.sh --check  ずれていたら非ゼロで終わる（CI 用。書き換えない）
#
# 版を上げる手順:
#   1. VERSION を新しい日付に書き換える
#   2. scripts/set-version.sh を実行する
#   3. VERSION と report/_quarto.yml をまとめてコミットする
set -euo pipefail

cd "$(dirname "$0")/.."

CONFIG=report/_quarto.yml
CHECK=false
[[ "${1-}" == "--check" ]] && CHECK=true

VERSION="$(tr -d '[:space:]' <VERSION)"
if [[ ! "$VERSION" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
	echo "エラー: VERSION は YYYY-MM-DD で書く（実際の中身: '$VERSION'）" >&2
	exit 1
fi

# 日付を持つ行は他にもある（page-footer の調査日など）ので、版の行だけを狙って置き換える。
# 2スペース字下げの date: は book: 直下の1行だけ。
stamped="$(sed -E \
	-e "s/^(  date: )\"[0-9]{4}-[0-9]{2}-[0-9]{2}\"/\1\"$VERSION\"/" \
	-e "s/^(  output-file: \"apache-ossie-report)-[0-9]{4}-[0-9]{2}-[0-9]{2}\"/\1-$VERSION\"/" \
	-e "s/(\\\\ofoot\*\{\\\\footnotesize 版 )[0-9]{4}-[0-9]{2}-[0-9]{2}\}/\1$VERSION}/" \
	"$CONFIG")"

# 3箇所すべてが版を持っている状態を保つ。書式を変えて置換が空振りしたら気付けるようにする。
hits="$(grep -c -- "$VERSION" <<<"$stamped" || true)"
if [[ "$hits" -ne 3 ]]; then
	echo "エラー: $CONFIG 内で版を差し込む箇所が3つ見つからない（見つかったのは $hits 箇所）。" >&2
	echo "       date / output-file / \\ofoot の書式を変えたなら、このスクリプトも直すこと。" >&2
	exit 1
fi

if [[ "$CHECK" == true ]]; then
	if ! diff -q <(printf '%s\n' "$stamped") "$CONFIG" >/dev/null; then
		echo "エラー: $CONFIG の版が VERSION（$VERSION）と食い違っている。" >&2
		echo "       scripts/set-version.sh を実行して差分をコミットすること。" >&2
		diff -u "$CONFIG" <(printf '%s\n' "$stamped") || true
		exit 1
	fi
	echo "版は一致している: $VERSION"
	exit 0
fi

printf '%s\n' "$stamped" >"$CONFIG"
echo "版 $VERSION を $CONFIG に反映した。"
