# Coloque este arquivo em  .github/workflows/coleta-pncp.yml  no repositório.
# Roda sozinho no GitHub (grátis), sem depender de nenhum computador pessoal.
name: Coleta PNCP e conversão dos PCAs
on:
  schedule:
    - cron: "30 10 * * *"   # 07:30 em Brasília (10:30 UTC)
    - cron: "0 16 * * *"    # 13:00 em Brasília (16:00 UTC)
  workflow_dispatch: {}      # botão "Run workflow" para rodar na hora
  push:
    paths: ["pca_2026.csv", "pca_2027.csv"]   # reconverte quando um PCA novo for enviado
permissions:
  contents: write
jobs:
  coleta:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - name: Converter PCAs e coletar PNCP
        run: python coleta/pncp_coleta.py
      - name: Salvar resultado no repositório
        run: |
          git config user.name "coleta-automatica"
          git config user.email "coleta@users.noreply.github.com"
          git add coleta/pncp_ff.csv coleta/atualizacao.json coleta/pca_*_utf8.csv coleta/pncp_log.txt
          git diff --staged --quiet || git commit -m "Atualização automática $(date -u +%F)"
          git push
