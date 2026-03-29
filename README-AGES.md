# 🚀 Executando o Projeto com Docker Compose

Este projeto pode ser executado localmente usando **Docker Compose**,
que sobe todos os serviços necessários:

-   API Flask
-   Banco de dados PostgreSQL
-   Prometheus (coleta de métricas)
-   Grafana (visualização de métricas)

------------------------------------------------------------------------

# 📦 Pré‑requisitos

Antes de começar, certifique-se de ter instalado:

-   Docker
-   Docker Compose

Verifique se estão instalados:

``` bash
docker --version
docker compose version
```

------------------------------------------------------------------------

# 📂 Estrutura Necessária do Projeto

Também é necessário possuir o repositório do banco de dados clonado
localmente, pois os scripts SQL são utilizados para inicializar o banco.

Exemplo de estrutura:

    nitra/
    ├── api
    │   ├── docker-compose.yml
    │   └── ...
    └── database
        ├── noharm-public.sql
        ├── noharm-create.sql
        ├── noharm-newuser.sql
        ├── noharm-triggers.sql
        └── noharm-insert.sql

Clone o repositório do banco:

``` bash
git clone https://github.com/noharm-ai/database.git
```

------------------------------------------------------------------------

# ⚙️ Configurando o Caminho do Banco

No arquivo `docker-compose.yml`, os scripts SQL são montados dentro do
container do PostgreSQL.

Exemplo:

``` yaml
db:
  image: postgres:16-alpine
  container_name: nitra_db
  environment:
    POSTGRES_DB: noharm
    POSTGRES_USER: postgres
    POSTGRES_HOST_AUTH_METHOD: trust
  volumes:
    - postgres_data:/var/lib/postgresql/data
    - /caminho/para/database:/sql
```

Substitua:

    /caminho/para/database

pelo caminho absoluto do diretório do banco de dados no seu computador.

Exemplo:

    /Users/willian/Documents/github/nitra/database

------------------------------------------------------------------------

# ▶️ Iniciando o Ambiente

Execute:

``` bash
docker compose -f docker-compose.nitra.yml up --build
```

Isso irá iniciar:

-   API Flask
-   PostgreSQL
-   Prometheus
-   Grafana
-   Inicialização do banco de dados

------------------------------------------------------------------------

# 🗄 Inicialização do Banco

O banco é inicializado automaticamente utilizando os scripts:

    noharm-public.sql
    noharm-create.sql
    noharm-newuser.sql
    noharm-triggers.sql
    noharm-insert.sql

Esses scripts criam:

-   schemas
-   tabelas
-   triggers
-   dados iniciais

------------------------------------------------------------------------

# 🌐 URLs dos Serviços

Após subir os containers, os serviços estarão disponíveis em:

  Serviço      URL
  ------------ -----------------------
  API Flask -   http://localhost:5000

  Prometheus  - http://localhost:9090

  Grafana  -    http://localhost:3000

------------------------------------------------------------------------

# 📊 Login do Grafana

Credenciais padrão:

    usuário: admin
    senha: admin

No primeiro acesso será solicitado alterar a senha.

------------------------------------------------------------------------

# 🔌 Conectando o Grafana ao Prometheus

Dentro do Grafana:

1.  Acesse **Connections → Data Sources**
2.  Clique em **Add data source**
3.  Escolha **Prometheus**
4.  Configure a URL:


```
    http://prometheus:9090
   ```

------------------------------------------------------------------------

# 🧪 Verificando Métricas

A API Flask expõe métricas do Prometheus em:

    http://localhost:5000/metrics

Para verificar se o Prometheus está coletando:

    http://localhost:9090/targets

------------------------------------------------------------------------

# 🛑 Parando o Ambiente

Para parar os serviços:

``` bash
docker compose -f docker-compose.nitra.yml down
```

Para remover volumes e recriar o banco:

``` bash
docker compose -f docker-compose.nitra.yml down -v
```

------------------------------------------------------------------------

# 🧹 Comandos Úteis

Ver logs:

``` bash
docker compose -f docker-compose.nitra.yml logs -f
```

Acessar o banco:

``` bash
docker exec -it nitra_db psql -U postgres -d noharm
```

------------------------------------------------------------------------

# 📈 Observabilidade

O projeto inclui um stack básico de observabilidade:

-   **Prometheus** → coleta de métricas
-   **Grafana** → dashboards e visualização
-   **Prometheus Flask Exporter** → métricas da API

Isso permite monitorar:

-   latência das requisições
-   quantidade de requests
-   taxa de erros
-   performance da aplicação
