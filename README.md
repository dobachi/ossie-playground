# ossie-playground

[Apache Ossie](https://ossie.apache.org/)（旧 Open Semantic Interchange）の
仕様と実装のあいだで、実際に何が起きるのかを確かめるための検証環境。

ブログ記事の動作確認に使ったものを、そのまま再現できる形で公開している。

## 📄 調査レポート（Web 版）

**<https://dobachi.github.io/ossie-playground/>**

このリポジトリの `report/`（Quarto ブック）を公開したもの。仕様の一次読解・
動作確認・ガバナンス・エコシステムの現状を、出典と再現手順つきでまとめている。
`main` への push で自動ビルド・公開される（`.github/workflows/publish.yml`）。

全文を1つにまとめた **PDF 版**もサイトのサイドバーからダウンロードできる
（<https://dobachi.github.io/ossie-playground/apache-ossie-report-2026-07-21.pdf>）。
ファイル名・表紙・各ページのフッタに版（発行日）が入る。→ [レポートの版](#レポートの版)

## 何を確かめられるか

2026年7月時点の Apache Ossie は、リリース版 `0.1.1` と開発版 `0.2.0.dev0` に
分かれており、**それぞれ揃っているものが違う**。

| | 0.1.1 | 0.2.0.dev0 |
| --- | --- | --- |
| 位置づけ | 唯一のリリース版（2025-12-11） | 未リリース。本番依存を禁ずる旨の明記あり |
| 公式サンプル | なし | 2本 |
| リポジトリ同梱のコンバータ8本 | 対象外 | 全部こちら |
| 出荷版 dbt Core 1.12 | 受理 | 拒否 |

この環境では2つの経路を検証する。

- **トラックA（0.1.1）** — 手書きの準拠文書 → 公式バリデータ → dbt 取り込み → `dbt run`
- **トラックB（0.2.0.dev0）** — 公式コンバータで dbt から生成 → 公式バリデータ → dbt 取り込み

主な観測結果:

- 公式コンバータの出力が、**同一コミットの公式バリデータで落ちる**
- `dbt → OSI → dbt` の往復が、**別々の層の3つの要因が重なって**成立しない（本検証構成での観測）
- 公式バリデータが拒否する文書（検証した追加キー）を dbt が**警告なしで受理**する
- 数値カラムと文字列カラムが取り込み時に**同じ categorical になる**
- 集約関数 `SUM` / `COUNT` が写像の過程で**脱落する**

## 調査レポート

検証の背景と結果をまとめたレポートを `report/` に置いている（Quarto）。
公開版は <https://dobachi.github.io/ossie-playground/>。

ローカルで見る場合:

```bash
cd report && quarto preview   # ローカルで閲覧
cd report && quarto render    # _site/ へ HTML と PDF を出力
```

PDF は `_quarto.yml` の `format: pdf` で組んでいる。lualatex + luatexja を使い、
日本語フォントは Noto CJK を名指ししているため、ローカルで PDF まで出すには
TeX Live（luatexja を含む）と `fonts-noto-cjk` が要る。HTML だけなら
`quarto render --to html` で足りる。

本文の各主張は、一次情報の脚注と、このリポジトリの再現データ
（`docs/results/`, `make verify`）で裏づけている。

### レポートの版

レポートには日付形式の版を付けている。リポジトリ直下の `VERSION` が正で、
PDF のファイル名（`apache-ossie-report-<版>.pdf`）・表紙の日付・全ページの
フッタがこの値から作られる。手元に落とした PDF がいつ時点のものか、
ファイル名だけで分かるようにするため。

版は「レポートを発行した日」で、調査基準日（2026-07-19）とは別物。

版を上げるときは:

```bash
vi VERSION                 # 新しい日付（YYYY-MM-DD）に書き換える
scripts/set-version.sh     # report/_quarto.yml の3箇所へ反映する
git add VERSION report/_quarto.yml
```

`VERSION` と `report/_quarto.yml` がずれたまま push すると、CI の
`scripts/set-version.sh --check` が公開前に止める。

## 使い方

必要なのは **docker だけ**。Python も dbt もコンテナ内にある。

```bash
make spec     # 仕様リポジトリを固定コミットで取得（ここだけネットワークを使う）
make verify   # トラックA・Bを実行
```

個別に実行する場合:

```bash
make verify-a   # トラックA のみ
make verify-b   # トラックB のみ（先に verify-a が必要）
make shell      # コンテナ内でシェルを開く
```

検証結果は `docs/results/*.json` に出る。

## 再現性について

- 仕様リポジトリは**コミットを固定**している（`Makefile` の `OSSIE_COMMIT`）。
  上流が変われば結果も変わりうるため、固定を外す場合は結果も取り直すこと
- 検証コンテナは `network_mode: none` で動く。
  実行中に外部の状態へ依存しないことを担保するため
- `spec/python`（`apache-ossie`）と `spec/converters/dbt`（`ossie_dbt`）は
  **PyPI に公開されていない**ため、リポジトリからソース導入している

## 構成

```
docker/          コンテナ定義と依存
compose.yaml     network_mode: none で実行
Makefile         入口
scripts/         検証スクリプト
  lib_ossie.py       共通処理（バリデータの展開など）
  verify_track_a.py  トラックA
  verify_track_b.py  トラックB
track-a/
  dbt-project/   検証用の最小 dbt プロジェクト（DuckDB）
  osi/           手書きの 0.1.1 準拠文書
track-b/
  generated/     公式コンバータの生成物（実行時に作られる）
spec/            仕様リポジトリ（make spec で取得。git 管理外）
docs/results/    検証結果の JSON
```

## 注意

**バリデータの挙動がバージョンで違う。** `0.1.1` タグの `validate.py` には
`--schema` オプションがなく、`__file__.parent.parent / "core-spec"` を
決め打ちで読む。`scripts/lib_ossie.py` はその構造を再現している。

## 出典

- 仕様: https://github.com/apache/ossie
- 検証時の固定コミット: `07be0176e48af67f0b46e0957a87a154586abf38`
- 比較タグ: `osi-0.1.1-rc1`
- 検証日: 2026-07-19

## ライセンス

Apache License 2.0
