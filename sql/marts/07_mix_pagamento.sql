-- Quanto do valor pago corresponde a cada tipo de pagamento?
-- Grão: um tipo de pagamento.
-- Valor pago inclui frete; receita é somente sum(preco) dos itens, sem frete.
-- A soma de pedidos entre tipos pode exceder o total: um pedido pode usar
-- mais de um tipo de pagamento e aparece uma vez em cada tipo usado.
WITH pagamentos_validos AS (
    -- Grão: um pagamento de um pedido válido (pedido_id, pagamento_seq).
    SELECT
        pg.pedido_id,
        pg.tipo,
        pg.valor
    FROM refined.pagamentos AS pg
    JOIN refined.pedidos AS p ON p.pedido_id = pg.pedido_id
    WHERE p.status NOT IN ('canceled', 'unavailable')
),
por_tipo AS (
    -- Grão: um tipo de pagamento.
    SELECT
        tipo,
        count(*) AS pagamentos,
        count(DISTINCT pedido_id) AS pedidos,
        sum(valor) AS valor
    FROM pagamentos_validos
    GROUP BY tipo
)
SELECT
    tipo,
    pagamentos,
    pedidos,
    valor,
    round(100.0 * valor / sum(valor) OVER (), 1) AS pct_valor
FROM por_tipo
ORDER BY tipo
