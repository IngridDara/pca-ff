#!/usr/bin/env python3
# Coleta no PNCP as contratações da Fundação Florestal (a partir de 01/01/2026 até hoje)
# e grava pncp_ff.csv NA MESMA PASTA deste script. Também converte pca_2026.csv e pca_2027.csv (pasta acima)
# para UTF-8 (pca_AAAA_utf8.csv) e registra as datas em atualizacao.json. A plataforma do PCA lê esses arquivos.
# Uso: python3 pncp_coleta.py           -> converte os PCAs e coleta o PNCP
#      python3 pncp_coleta.py --so-pca  -> só converte os PCAs (rápido)
import csv, json, os, sys, time, tempfile, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

PASTA = Path(__file__).resolve().parent
SAIDA = PASTA / "pncp_ff.csv"
LOG = PASTA / "pncp_log.txt"
META = PASTA / "atualizacao.json"
PASTA_PCA = PASTA.parent
BASE = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
CNPJ = "56089790000188"          # SIMA: a Fundação Florestal aparece como unidade compradora
INICIO = "20260101"
MODALIDADES = {1: "Leilão eletrônico", 2: "Diálogo competitivo", 3: "Concurso", 4: "Concorrência eletrônica",
               5: "Concorrência presencial", 6: "Pregão eletrônico", 7: "Pregão presencial", 8: "Dispensa",
               9: "Inexigibilidade", 12: "Credenciamento"}
BRT = timezone(timedelta(hours=-3))

def log(msg):
    linha = f"{datetime.now(BRT):%Y-%m-%d %H:%M:%S} {msg}"
    print(linha)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(linha + "\n")

def buscar(url, tentativas=3):
    for t in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code in (400, 404, 422):
                return e.code, ""
            time.sleep(3 * (t + 1))
        except Exception as e:
            time.sleep(3 * (t + 1))
    return None, ""

def ler_meta():
    try:
        return json.loads(META.read_text(encoding="utf-8"))
    except Exception:
        return {}

def gravar_meta(**kv):
    m = ler_meta()
    m.update(kv)
    tmp = META.with_suffix(".tmp")
    tmp.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, META)

def converter_pcas():
    """Converte pca_2026.csv / pca_2027.csv (Windows-1252) para UTF-8, sem perder acentos."""
    for ano in (2026, 2027):
        origem = PASTA_PCA / f"pca_{ano}.csv"
        destino = PASTA / f"pca_{ano}_utf8.csv"
        if not origem.exists():
            continue
        bruto = origem.read_bytes()
        try:
            texto = bruto.decode("utf-8")
        except UnicodeDecodeError:
            texto = bruto.decode("cp1252", errors="replace")
        texto = texto.lstrip("\ufeff")
        if destino.exists() and destino.read_text(encoding="utf-8") == texto:
            continue
        tmp = destino.with_suffix(".tmp")
        tmp.write_text(texto, encoding="utf-8")
        os.replace(tmp, destino)
        mt = datetime.fromtimestamp(origem.stat().st_mtime, BRT).isoformat(timespec="seconds")
        gravar_meta(**{f"pca{ano}": mt})
        log(f"PCA {ano} convertido para UTF-8 (arquivo de {mt}).")

def main():
    converter_pcas()
    if "--so-pca" in sys.argv:
        return 0
    hoje = datetime.now(BRT).strftime("%Y%m%d")
    vistos, linhas, falhas = set(), [], 0
    for mod, nome in MODALIDADES.items():
        pag = 1
        while True:
            qs = urllib.parse.urlencode({"dataInicial": INICIO, "dataFinal": hoje,
                "codigoModalidadeContratacao": mod, "cnpj": CNPJ, "pagina": pag, "tamanhoPagina": 50})
            status, corpo = buscar(BASE + "?" + qs)
            if status is None:
                falhas += 1
                log(f"ERRO de rede em {nome}, página {pag}")
                break
            if not corpo.strip():
                break
            j = json.loads(corpo)
            for c in j.get("data", []):
                u = c.get("unidadeOrgao") or {}
                if "FLORESTAL" not in (u.get("nomeUnidade") or "").upper():
                    continue
                cid = c.get("numeroControlePNCP")
                if cid in vistos:
                    continue
                vistos.add(cid)
                linhas.append([cid, nome, c.get("numeroCompra"), c.get("anoCompra"),
                    " ".join((c.get("objetoCompra") or "").split()),
                    c.get("valorTotalEstimado"), c.get("valorTotalHomologado"),
                    (c.get("dataPublicacaoPncp") or "")[:10], c.get("situacaoCompraNome")])
            if pag >= (j.get("totalPaginas") or 1):
                break
            pag += 1
            time.sleep(0.4)
    if falhas or not linhas:
        log(f"Coleta incompleta ({falhas} falhas, {len(linhas)} linhas): arquivo anterior mantido.")
        return 1
    agora = datetime.now(BRT).isoformat(timespec="seconds")
    fd, tmp = tempfile.mkstemp(dir=PASTA, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";", lineterminator="\n")
        w.writerow(["controle", "modalidade", "numero", "ano", "objeto", "valor_estimado",
                    "valor_homologado", "publicacao", "situacao", "coletado_em"])
        for l in sorted(linhas, key=lambda x: x[7] or ""):
            w.writerow(["" if v is None else v for v in l] + [agora])
    os.replace(tmp, SAIDA)
    gravar_meta(pncp=agora)
    log(f"OK: {len(linhas)} contratações gravadas em {SAIDA.name}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
