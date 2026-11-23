# Aplicao-Simplificada-de-Comercio-Eletronico
Aplicação WEB de comércio eletrônico simplificada utilizando Python e Flask, hospedada em uma instância AWS EC2, capaz de gerenciar clientes, produtos, carrinhos, pedidos e pagamentos.

## Como rodar

```bash
pip install -r requirements.txt
python app.py            # site em http://localhost:5000
```

Variáveis de ambiente opcionais: `SECRET_KEY` (chave da sessão; defina em produção), `DB_PATH` (caminho do banco, padrão `loja_online.db`) e `FLASK_DEBUG=1` (modo debug).

## API REST

Todas as rotas ficam sob `/api` e respondem em JSON. A autenticação usa a mesma sessão do site: faça login em `POST /api/auth/login` e reaproveite o cookie nas próximas chamadas.

| Método | Rota | Descrição | Login |
|---|---|---|---|
| GET | `/api/produtos?busca=texto` | Lista produtos (busca opcional por nome) | — |
| GET | `/api/produtos/{id}` | Detalhes de um produto | — |
| POST | `/api/auth/registrar` | Cadastra cliente `{nome, email, senha, telefone?}` | — |
| POST | `/api/auth/login` | Inicia sessão `{email, senha}` | — |
| POST | `/api/auth/logout` | Encerra a sessão | — |
| GET | `/api/auth/me` | Dados do cliente logado | ✔ |
| GET | `/api/carrinho` | Itens e total do carrinho | ✔ |
| POST | `/api/carrinho/itens` | Adiciona `{produto_id, quantidade?}` | ✔ |
| PATCH | `/api/carrinho/itens/{produto_id}` | Altera `{quantidade}` | ✔ |
| DELETE | `/api/carrinho/itens/{produto_id}` | Remove o item | ✔ |
| POST | `/api/pedidos` | Finaliza a compra `{tipo_pagamento?: cartao \| pix \| boleto}` | ✔ |
| GET | `/api/pedidos` | Pedidos do cliente logado | ✔ |
| GET | `/api/pedidos/{id}` | Detalhes de um pedido | ✔ |

Códigos de status usados: `200`, `201` (criado), `204` (sem conteúdo), `400` (dados inválidos), `401` (não autenticado), `404` (não encontrado), `409` (conflito: email já cadastrado ou estoque insuficiente). Erros vêm no formato `{"erro": "mensagem"}`.

A finalização do pedido grava `pedidos`, `itens_pedido` e `pagamentos` e dá baixa no estoque em uma única transação: se algum item ficar sem estoque, nada é gravado.

### Exemplo com curl

```bash
curl -c cookies.txt -X POST localhost:5000/api/auth/login \
     -H "Content-Type: application/json" -d '{"email":"teste@email.com","senha":"654321"}'
curl -b cookies.txt -X POST localhost:5000/api/carrinho/itens \
     -H "Content-Type: application/json" -d '{"produto_id": 2, "quantidade": 1}'
curl -b cookies.txt -X POST localhost:5000/api/pedidos \
     -H "Content-Type: application/json" -d '{"tipo_pagamento":"pix"}'
```

## Testes

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Os testes usam um banco SQLite temporário e não alteram `loja_online.db`.
