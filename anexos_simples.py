# anexos_simples.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Literal

Anexo = Literal["I", "II", "III", "IV", "V"]

# Faixas de receita do Simples (limites anuais – RBT12)
FAIXAS = [
    (1, 0.00,        180_000.00),
    (2, 180_000.01,  360_000.00),
    (3, 360_000.01,  720_000.00),
    (4, 720_000.01, 1_800_000.00),
    (5, 1_800_000.01, 3_600_000.00),
    (6, 3_600_000.01, 4_800_000.00),
]

# Alíquotas NOMINAIS por Anexo/Faixa (percentuais em decimal)
ALIQUOTAS_NOMINAIS: Dict[Anexo, Dict[int, float]] = {
    "I":   {1: 0.040, 2: 0.073, 3: 0.095, 4: 0.107, 5: 0.143, 6: 0.190},
    "II":  {1: 0.045, 2: 0.078, 3: 0.100, 4: 0.112, 5: 0.147, 6: 0.300},
    "III": {1: 0.060, 2: 0.112, 3: 0.135, 4: 0.160, 5: 0.210, 6: 0.330},
    "IV":  {1: 0.045, 2: 0.090, 3: 0.102, 4: 0.140, 5: 0.220, 6: 0.330},
    "V":   {1: 0.155, 2: 0.180, 3: 0.195, 4: 0.205, 5: 0.230, 6: 0.305},
}

# (Opcional) Tabelas de Parcela a Deduzir para calcular ALÍQUOTA EFETIVA depois
# PODEMOS PREENCHER MAIS TARDE (quando você quiser ativar a efetiva)
PARCELA_DEDUZIR: Dict[Anexo, Dict[int, float]] = {
    # "I":   {1: 0.0, 2: 5_940.00, 3: 13_860.00, 4: 22_500.00, 5: 87_300.00, 6: 378_000.00},
    # "II":  {...},
    # "III": {1: 0.0, 2: 9_360.00, 3: 17_640.00, 4: 35_640.00, 5: 125_640.00, 6: 648_000.00},
    # "IV":  {...},
    # "V":   {...},
}

@dataclass
class CNAEInfo:
    cnae: str
    descricao: str
    anexos: List[Anexo]
    fator_r: bool
    natureza: Literal["servicos", "comercio", "industria"]  # pode usar só "servicos"/"comercio" no seu JSON

def carregar_tabela_cnae(obj: List[dict]) -> Dict[str, CNAEInfo]:
    """
    Recebe a lista (JSON já carregado) e indexa por código CNAE.
    """
    tabela: Dict[str, CNAEInfo] = {}
    for item in obj:
        tabela[item["cnae"]] = CNAEInfo(
            cnae=item["cnae"],
            descricao=item.get("descricao", ""),
            anexos=item.get("anexos", []),
            fator_r=bool(item.get("fator_r", False)),
            natureza=item.get("natureza", "servicos"),  # default "servicos"
        )
    return tabela

def faixa_por_rbt12(rbt12: float) -> int:
    for faixa, ini, fim in FAIXAS:
        if ini <= rbt12 <= fim:
            return faixa
    raise ValueError("RBT12 fora do limite do Simples (0 a 4,8 milhões).")

def resolver_anexo_por_cnae(
    cnae: str,
    rbt12: float,
    folha_12m: Optional[float],
    tabela_cnae: Dict[str, CNAEInfo],
    anexo_forcado: Optional[Anexo] = None,
) -> Anexo:
    """
    - Se anexo_forcado for informado, respeita.
    - Senão, usa a linha do CNAE:
        * Se houver apenas 1 anexo, usa ele.
        * Se vier ["III","V"] e fator_r=True, aplica Fator R (>= 28% -> III; < 28% -> V).
        * Se vier ["IV"], é sempre IV.
        * Se comércio/indústria vierem com I/II fixos, usa direto.
    """
    if anexo_forcado:
        return anexo_forcado

    info = tabela_cnae.get(cnae)
    if not info:
        raise KeyError(f"CNAE {cnae} não encontrado na tabela.")

    # Caso com um único anexo
    if len(info.anexos) == 1:
        return info.anexos[0]

    # Caso III/V com Fator R
    if set(info.anexos) == {"III", "V"} and info.fator_r:
        if folha_12m is None or rbt12 <= 0:
            # Se não veio folha, por segurança, assuma V (mais conservador) — ou levante erro se preferir
            return "V"
        fator_r = (folha_12m / rbt12)
        return "III" if fator_r >= 0.28 else "V"

    # Se vierem anexos múltiplos diferentes dos casos acima, por padrão escolha o primeiro
    # (ou levante um erro para análise manual)
    return info.anexos[0]

def aliquota_nominal_por_anexo(anexo: Anexo, rbt12: float) -> Tuple[int, float]:
    """
    Retorna (faixa, aliquota_nominal_decimal) com base no anexo e no RBT12.
    """
    faixa = faixa_por_rbt12(rbt12)
    try:
        aliq = ALIQUOTAS_NOMINAIS[anexo][faixa]
    except KeyError:
        raise KeyError(f"Alíquota não encontrada para Anexo {anexo}, faixa {faixa}.")
    return faixa, aliq

# (Opcional) Quando quiser ativar a alíquota efetiva com PD:
# def aliquota_efetiva(anexo: Anexo, rbt12: float) -> Tuple[int, float, float]:
#     faixa = faixa_por_rbt12(rbt12)
#     aliq_nom = ALIQUOTAS_NOMINAIS[anexo][faixa]
#     pd = PARCELA_DEDUZIR[anexo][faixa]
#     aliq_eff = ((rbt12 * aliq_nom) - pd) / rbt12
#     return faixa, aliq_nom, aliq_eff

def obter_aliquota_por_cnae(
    cnae: str,
    rbt12: float,
    folha_12m: Optional[float],
    tabela_cnae: Dict[str, CNAEInfo],
    anexo_forcado: Optional[Anexo] = None,
) -> Dict[str, object]:
    """
    Função de alto nível: resolve anexo pelo CNAE e entrega a alíquota nominal correta.
    """
    anexo = resolver_anexo_por_cnae(cnae, rbt12, folha_12m, tabela_cnae, anexo_forcado)
    faixa, aliq_nom = aliquota_nominal_por_anexo(anexo, rbt12)
    return {
        "anexo": anexo,
        "faixa": faixa,
        "aliquota_nominal": aliq_nom,        # decimal (ex.: 0.112 = 11,2%)
        "aliquota_nominal_pct": aliq_nom * 100,  # em %
        "rbt12": rbt12,
        "faturamento_mensal_medio": rbt12 / 12.0,
    }

# ------------------ EXEMPLO DE USO ------------------
if __name__ == "__main__":
    import json
    # Carregue seu JSON (cole o arquivo como cnae_anexos.json na raiz)
    with open("cnae_anexos.json", "r", encoding="utf-8") as f:
        dados = json.load(f)
    tabela = carregar_tabela_cnae(dados)

    # Exemplo 1: CNAE com III/V por fator R (62.01-5-01)
    rbt12 = 600_000.0
    folha = 200_000.0  # fator R ≈ 33% => Anexo III
    res = obter_aliquota_por_cnae("62.01-5-01", rbt12, folha, tabela)
    print("Exemplo 1:", res)

    # Exemplo 2: comércio fixo no Anexo I (47.51-2-01)
    rbt12 = 500_000.0
    res2 = obter_aliquota_por_cnae("47.51-2-01", rbt12, None, tabela)
    print("Exemplo 2:", res2)

    # Exemplo 3: engenharia (71.12-0-00) mapeado para V e com fator R aplicável (no seu JSON está V + fator_r True)
    rbt12 = 1_200_000.0
    folha = 100_000.0  # fator R ≈ 8% => Anexo V
    res3 = obter_aliquota_por_cnae("71.12-0-00", rbt12, folha, tabela)
    print("Exemplo 3:", res3)
