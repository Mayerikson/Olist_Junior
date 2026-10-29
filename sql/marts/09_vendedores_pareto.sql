-- Que fração dos vendedores concentra 80% da receita?
-- Grão: um vendedor com venda de pedido válido.
WITH receita_por_vendedor AS (
    -- Grão: um vendedor; receita válida é o preço dos itens, sem frete.
    SELECT
        i.vendedor_id,
        v.uf,
        sum(i.preco) AS receita
    FROM refined.itens_pedido AS i
    JOIN refined.pedidos AS p ON p.pedido_id = i.pedido_id
    JOIN refined.vendedores AS v ON v.vendedor_id = i.vendedor_id
    WHERE p.status NOT IN ('canceled', 'unavailable')
    GROUP BY i.vendedor_id, v.uf
),
pareto AS (
    -- Grão: um vendedor, ordenado com desempate para acumulado reproduzível.
    SELECT
        vendedor_id,
        uf,
        receita,
        row_number() OVER (
            ORDER BY receita DESC, vendedor_id
        ) AS posicao,
        round(
            100.0
            * sum(receita) OVER (
                ORDER BY receita DESC, vendedor_id
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            )
            / sum(receita) OVER (),
            2
        ) AS pct_acumulado
    FROM receita_por_vendedor
)
SELECT
    vendedor_id,
    uf,
    receita,
    posicao,
    pct_acumulado
FROM pareto
ORDER BY posicao
