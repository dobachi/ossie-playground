.PHONY: help build spec shell verify-a verify-b verify clean distclean

# 検証対象として固定する仕様リポジトリのコミット。
# 差し替えるときは docs/ の検証結果も取り直すこと。
OSSIE_REPO := https://github.com/apache/ossie.git
OSSIE_COMMIT := 07be0176e48af67f0b46e0957a87a154586abf38
OSSIE_TAG_011 := osi-0.1.1-rc1

COMPOSE := docker compose
RUN := $(COMPOSE) run --rm --no-deps lab

help:
	@echo "Apache Ossie 動作確認環境"
	@echo ""
	@echo "  make build      コンテナイメージをビルド"
	@echo "  make spec       仕様リポジトリを固定コミットで取得 (要ネットワーク)"
	@echo "  make verify     トラックA・Bの検証をすべて実行"
	@echo "  make verify-a   トラックA (0.1.1) のみ"
	@echo "  make verify-b   トラックB (0.2.0.dev0) のみ"
	@echo "  make shell      コンテナ内でシェルを開く"
	@echo "  make clean      生成物を削除"
	@echo "  make distclean  spec/ とイメージも削除"
	@echo ""
	@echo "ホストに必要なものは docker のみ。Python も dbt もコンテナ内にある。"

build:
	$(COMPOSE) build

# 仕様リポジトリの取得だけはネットワークが要るため、
# network_mode: none の lab サービスとは別に一時コンテナで行う。
spec:
	@if [ -d spec/.git ]; then \
		echo "spec/ は取得済み。再取得するには make distclean"; \
	else \
		docker run --rm -v "$(PWD)":/w -w /w alpine/git:latest \
			clone --no-checkout $(OSSIE_REPO) spec; \
		docker run --rm -v "$(PWD)":/w -w /w/spec alpine/git:latest \
			checkout $(OSSIE_COMMIT); \
		docker run --rm -v "$(PWD)":/w -w /w/spec alpine/git:latest \
			fetch --depth 1 origin tag $(OSSIE_TAG_011); \
	fi
	@echo "固定コミット: $(OSSIE_COMMIT)"

shell: build
	$(RUN) bash

verify-a: build
	$(RUN) python -X pycache_prefix=/tmp scripts/verify_track_a.py

verify-b: build
	$(RUN) python -X pycache_prefix=/tmp scripts/verify_track_b.py

verify: verify-a verify-b

clean:
	rm -rf track-a/dbt-project/target track-a/dbt-project/logs \
	       track-a/dbt-project/*.duckdb track-b/generated docs/results

distclean: clean
	rm -rf spec
	-docker image rm ossie-playground:local
