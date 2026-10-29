# Pipeline de dados Olist

Pipeline local de dados do e-commerce brasileiro da Olist. Ele transforma os
arquivos CSV compactados em tabelas DuckDB e disponibiliza indicadores em um
painel Streamlit e em um relatório HTML.

## Dados: origem e licença

O projeto usa o **Brazilian E-Commerce Public Dataset by Olist**, publicado pela
Olist no Kaggle. O conjunto contém pedidos realizados entre 2016 e 2018, com
informações de itens, pagamentos, clientes, vendedores, produtos, entregas e
avaliações. Os dados foram anonimizados pelo publicador.

- [Página oficial do dataset no Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
- [Licença CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)
- [Informações e licença incluída com os dados](dados/README.md) · [LICENSE](dados/LICENSE)

A licença dos dados exige atribuição, proíbe uso comercial e requer que
adaptações sejam compartilhadas sob a mesma licença. A licença acima se refere
ao dataset; ela não define, por si só, a licença do código deste projeto.

Os nove arquivos `.csv.gz` devem estar em `raw/`, com os nomes originais abaixo.
Eles podem ser lidos compactados, sem descompactação. Não edite nem salve esses
arquivos em outra ferramenta: a camada `raw` preserva os valores de origem.

| Arquivo | Uma linha representa |
|---|---|
| `olist_orders_dataset.csv.gz` | Um pedido (`order_id`), com cliente, estado e datas do ciclo do pedido. |
| `olist_order_items_dataset.csv.gz` | Um item de um pedido (`order_id`, `order_item_id`), com produto, vendedor, preço e frete. |
| `olist_order_payments_dataset.csv.gz` | Uma parcela/registro de pagamento de um pedido (`order_id`, `payment_sequential`), com tipo, parcelas e valor. |
| `olist_order_reviews_dataset.csv.gz` | Uma avaliação associada a um pedido (`review_id`, `order_id`), com nota, comentários e datas. |
| `olist_customers_dataset.csv.gz` | Um cadastro de cliente (`customer_id`), com identificador da pessoa, CEP, cidade e UF. A mesma pessoa pode aparecer em mais de um cadastro. |
| `olist_sellers_dataset.csv.gz` | Um vendedor (`seller_id`), com CEP, cidade e UF. |
| `olist_products_dataset.csv.gz` | Um produto (`product_id`), com categoria, dimensões, peso e atributos descritivos. |
| `product_category_name_translation.csv.gz` | Uma categoria original, com seu nome traduzido para inglês. |
| `olist_geolocation_dataset.csv.gz` | Uma observação de geolocalização de CEP, com prefixo, cidade, UF e coordenadas. Um prefixo pode ter mais de uma observação. |

## Camadas do pipeline

O banco `olist.duckdb`, criado na raiz do projeto, contém três schemas. Cada
etapa lê a camada anterior e recria suas próprias tabelas para que a execução
possa ser repetida.

### 1. `raw` — ingestão sem transformação

`pipeline.ingestao` lê os nove CSVs gzip com UTF-8 e grava os dados no DuckDB
como texto, preservando linhas, colunas e valores. Campos vazios viram `NULL`;
não há deduplicação, correção ou conversão de tipos nesta etapa.

As tabelas resultantes são `pedidos`, `itens_pedido`, `pagamentos`,
`avaliacoes`, `clientes`, `vendedores`, `produtos`, `traducao_categorias` e
`geolocalizacao`. Cada tabela mantém o grão do arquivo de origem descrito
acima.

### 2. `refined` — nomes e tipos adequados para consulta

`pipeline.transformacao` cria oito tabelas refinadas. Colunas são renomeadas
para português; datas passam a `TIMESTAMP` ou `DATE`, valores monetários a
`DECIMAL` e contagens/dimensões numéricas a tipos inteiros. Identificadores
continuam texto para preservar valores como CEPs com zeros à esquerda.

Duplicatas exatamente iguais são removidas. Chaves repetidas com conteúdo
diferente e valores que não podem ser convertidos interrompem a execução.
Valores nulos e anomalias de negócio são mantidos, sem escolher regras de
negócio nesta camada.

| Tabela refined | Grão de uma linha | Chave declarada |
|---|---|---|
| `pedidos` | Um pedido, com cliente, status e datas. | `pedido_id` |
| `itens_pedido` | Um item de um pedido, com produto, vendedor, preço e frete. | (`pedido_id`, `item_seq`) |
| `pagamentos` | Um registro de pagamento de um pedido. | (`pedido_id`, `pagamento_seq`) |
| `clientes` | Um cadastro de cliente e sua localização. | `cliente_id` |
| `vendedores` | Um vendedor e sua localização. | `vendedor_id` |
| `produtos` | Um produto e seus atributos. | `produto_id` |
| `traducao_categorias` | Uma categoria e sua tradução. | `categoria` |
| `avaliacoes` | Uma avaliação associada a um pedido. | (`avaliacao_id`, `pedido_id`) |

`geolocalizacao` permanece apenas em `raw`: nenhuma consulta de mart deste
projeto a consome.

### 3. `marts` — indicadores de negócio

`pipeline.marts` executa, em ordem de nome, cada arquivo de `sql/marts/` e
materializa uma tabela com o mesmo nome sem o prefixo numérico. Abaixo estão
o grão e a regra principal de cada mart:

| Mart | Uma linha representa | Indicadores e regras |
|---|---|---|
| `vendas_mensais` | Um mês de compra. | Pedidos distintos e receita dos itens (`preco`) dos pedidos que não estão cancelados nem indisponíveis. Frete não compõe a receita. |
| `top_categorias` | Uma categoria de produto. | Pedidos distintos, itens e receita válida por categoria; pedidos podem aparecer em mais de uma categoria. |
| `entrega_no_prazo` | A operação inteira, uma linha. | Quantidade entregue, no prazo e atrasada, e percentual no prazo. Inclui quem chegou no próprio dia previsto, mesmo que a hora seja posterior; só considera pedidos entregues com data. |
| `nota_por_categoria` | Uma categoria com pelo menos 100 pedidos avaliados. | Nota média e posição da pior nota. Cada pedido conta uma vez por categoria e sua nota é a média das avaliações daquele pedido. |
| `recompra` | Uma quantidade de pedidos válidos por cliente-pessoa. | Número de clientes e sua participação percentual em cada faixa de pedidos. A pessoa é identificada por `cliente_unico_id`. |
| `ticket_medio_por_estado` | Uma UF de cliente. | Número de pedidos e média da receita de itens por pedido válido; frete não entra no ticket. |
| `mix_pagamento` | Um tipo de pagamento. | Pagamentos, pedidos distintos, valor e participação no valor pago. O valor inclui frete; um pedido pode aparecer em mais de um tipo. |
| `nota_por_prazo` | Uma situação de entrega entre pedidos avaliados (`no_prazo` ou `atrasado`). | Pedidos avaliados, nota média e percentual de notas baixas (nota até 2). Cada pedido avaliado conta uma vez. |
| `vendedores_pareto` | Um vendedor com receita de pedidos válidos. | Receita de itens sem frete, posição por receita e percentual acumulado, com desempate por identificador do vendedor. |
| `tempo_entrega_por_estado` | Uma UF de cliente. | Pedidos entregues com data, dias médios e mediana de compra até entrega. |
| `kpis` | A operação inteira, uma linha. | Ticket médio e mediano por pedido válido; peso do frete sobre receita mais frete; percentual de pedidos cancelados sobre todos os pedidos; dias médios e medianos até entrega; nota média das avaliações. |
| `clientes_por_uf` | Uma UF de cadastro de cliente. | Pessoas distintas por UF (`cliente_unico_id`). A soma entre UFs pode exceder pessoas únicas se uma pessoa estiver cadastrada em mais de uma UF. |

Os sete cartões do painel são: ticket médio (`kpis.ticket_medio`), cancelados
(`kpis.pct_cancelados`), peso do frete (`kpis.pct_frete`), recompra
(complemento da faixa de um pedido em `recompra`), entregas no prazo
(`entrega_no_prazo.pct_no_prazo`), dias até entregar (`kpis.dias_entrega`) e
nota média (`kpis.nota_media`). Os demais marts alimentam os gráficos
mensais, por categoria, pagamento, UF e concentração de vendedores.

## Requisitos

- Python 3.13
- [uv](https://docs.astral.sh/uv/)
- Arquivos do dataset em `raw/`, com os nomes listados acima

## Executar do zero

Clone o repositório e entre na pasta do projeto:

```powershell
git clone --recurse-submodules https://github.com/Mayerikson/Olist_Junior.git
cd Olist_Junior
```

Se os CSVs não estiverem presentes em `raw/`, baixe-os da [página do dataset
no Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) e
coloque os nove arquivos `.csv.gz` com os nomes da tabela acima. Em seguida,
no terminal a partir da raiz do projeto:

```powershell
# Instala as dependências registradas no projeto e no uv.lock.
uv sync

# 1. CSVs gzip -> schema raw.
uv run python -m pipeline.ingestao

# 2. raw -> schema refined.
uv run python -m pipeline.transformacao

# 3. SQLs -> schema marts.
uv run python -m pipeline.marts

# 4. Abre o dashboard no navegador.
uv run streamlit run app.py
```

O dashboard apresenta os cartões e gráficos para os marts materializados. O
filtro de período recorta apenas o gráfico de faturamento mensal; os cartões e
os outros gráficos representam o período completo.

Para gerar uma versão estática em HTML, em outro terminal ou depois de parar o
dashboard:

```powershell
uv run python relatorio.py
```

O arquivo `relatorio.html` é criado na raiz do projeto e pode ser aberto no
navegador. Ele não consulta o banco depois da geração; o rodapé informa quando
o arquivo foi criado.

### Executar a interface do DuckDB (opcional)

```powershell
uv run python ui.py
```

A interface fica disponível em `http://localhost:4213`. Pressione `Ctrl+C`
para encerrá-la. Feche essa interface antes de executar etapas que escrevam no
DuckDB, pois sua conexão mantém o arquivo aberto.

## Testes

Os testes usam bancos e dados inventados em diretórios temporários. Não
dependem de `olist.duckdb` nem leem CSVs de `raw/`.

```powershell
uv run pytest --cov
```

A configuração mede coverage de `pipeline/`, `painel.py` e `relatorio.py`;
`app.py` é validado visualmente no dashboard, e `ui.py` é apenas a interface
do DuckDB.

## Uso de inteligência artificial

Ferramentas de IA foram usadas como apoio durante o desenvolvimento e na
preparação da documentação e dos testes. As regras de negócio e os critérios
do pipeline vêm das especificações do projeto e dos SQLs em `sql/marts/`.
As alterações assistidas foram revisadas e verificadas com os testes locais;
a IA não é fonte dos dados nem substitui a validação do pipeline.

O material didático deste README e da documentação em `dados/` segue a
licença CC BY-NC-SA 4.0 indicada para manter compatibilidade com os termos de
compartilhamento do material do curso.
