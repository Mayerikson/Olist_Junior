-- Quanto tempo os pedidos levam da compra até a entrega em cada UF?
-- Grão: uma UF de cliente, com os pedidos entregues do mart 03.
WITH entrega_por_pedido AS (
    -- Grão: um pedido entregue com data de entrega.
    SELECT
        p.pedido_id,
        c.uf,
        date_diff('day', p.data_compra, p.data_entrega) AS dias
    FROM refined.pedidos AS p
    JOIN refined.clientes AS c ON c.cliente_id = p.cliente_id
    WHERE p.status = 'delivered'
      AND p.data_entrega IS NOT NULL
),
tempo_por_uf AS (
    -- Grão: uma UF, resumida por média e mediana dos dias por pedido.
    SELECT
        uf,
        count(*) AS entregues,
        round(avg(dias), 1) AS dias_medio,
        median(dias) AS dias_mediana
    FROM entrega_por_pedido
    GROUP BY uf
)
SELECT
    uf,
    entregues,
    dias_medio,
    dias_mediana
FROM tempo_por_uf
ORDER BY uf
