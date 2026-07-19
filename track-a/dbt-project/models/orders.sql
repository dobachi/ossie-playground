-- 検証用の最小データセット。
-- V3(型情報)のため、数値・文字列・日時をそれぞれ持たせている。
select * from (values
    (1, 'shipped',   100.50, date '2026-01-01'),
    (2, 'pending',   250.00, date '2026-01-02'),
    (3, 'shipped',    75.25, date '2026-01-03'),
    (4, 'cancelled', 500.00, date '2026-01-04')
) as t(order_id, status, amount, ordered_at)
