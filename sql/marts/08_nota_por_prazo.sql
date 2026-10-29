-- Atrasos estão associados a notas piores?
-- Grão: uma situação de entrega entre pedidos avaliados.
WITH nota_por_pedido AS (
    -- Grão: um pedido, com a média de suas avaliações.
    SELECT
        pedido_id,
        avg(nota) AS nota
    FROM refined.avaliacoes
    GROUP BY pedido_id
),
entrega_por_pedido AS (
    -- Grão: um pedido entregue com data de entrega, como no mart 03.
    SELECT
        pedido_id,
        CASE
            WHEN data_entrega::DATE <= data_entrega_prevista THEN 'no_prazo'
            ELSE 'atrasado'
        END AS situacao
    FROM refined.pedidos
    WHERE status = 'delivered'
      AND data_entrega IS NOT NULL
),
nota_por_situacao AS (
    -- Grão: um pedido avaliado; cada pedido entra uma única vez.
    SELECT
        e.situacao,
        n.pedido_id,
        n.nota
    FROM entrega_por_pedido AS e
    JOIN nota_por_pedido AS n ON n.pedido_id = e.pedido_id
)
SELECT
    situacao,
    count(*) AS pedidos_avaliados,
    round(avg(nota), 2) AS nota_media,
    round(
        100.0 * count(*) FILTER (WHERE nota <= 2) / count(*),
        1
    ) AS pct_nota_baixa
FROM nota_por_situacao
GROUP BY situacao
ORDER BY situacao
