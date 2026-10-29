-- Qual o ticket médio de cada estado?
-- Grão: uma UF, depois de mudar de item para pedido e de pedido para UF.
-- Ticket médio: receita de cada pedido válido, depois média por pedido.
WITH receita_por_pedido AS (
    -- Grão: um pedido válido com itens; receita exclui frete.
    SELECT
        p.pedido_id,
        p.cliente_id,
        sum(i.preco) AS receita
    FROM refined.pedidos AS p
    JOIN refined.itens_pedido AS i ON i.pedido_id = p.pedido_id
    WHERE p.status NOT IN ('canceled', 'unavailable')
    GROUP BY p.pedido_id, p.cliente_id
),
ticket_por_uf AS (
    -- Grão: uma UF, com uma observação por pedido.
    SELECT
        c.uf,
        count(*) AS pedidos,
        round(avg(r.receita), 2) AS ticket_medio
    FROM receita_por_pedido AS r
    JOIN refined.clientes AS c ON c.cliente_id = r.cliente_id
    GROUP BY c.uf
)
SELECT
    uf,
    pedidos,
    ticket_medio
FROM ticket_por_uf
ORDER BY uf
