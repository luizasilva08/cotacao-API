"""
Câmbio Certo (versão colorida, nativa) — usa somente Streamlit + biblioteca padrão do Python.
Dados: AwesomeAPI (https://docs.awesomeapi.com.br/api-de-moedas)

Execução:  streamlit run app.py
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone

import streamlit as st

try:
    from zoneinfo import ZoneInfo

    FUSO = ZoneInfo("America/Sao_Paulo")
except Exception:  # tzdata ausente (ex.: Windows sem o pacote)
    FUSO = None

# ----------------------------------------------------------------------------
# Configuração
# ----------------------------------------------------------------------------
APP_NOME = "Câmbio Certo"
API_BASE = "https://economia.awesomeapi.com.br/json"

st.set_page_config(page_title=f"{APP_NOME} · Cotações em tempo real", page_icon="💱", layout="wide")

# código: (nome, bandeira/ícone, símbolo, é cripto)
MOEDAS = {
    "USD": ("Dólar Americano", "🇺🇸", "US$", False),
    "EUR": ("Euro", "🇪🇺", "€", False),
    "GBP": ("Libra Esterlina", "🇬🇧", "£", False),
    "ARS": ("Peso Argentino", "🇦🇷", "AR$", False),
    "CAD": ("Dólar Canadense", "🇨🇦", "C$", False),
    "AUD": ("Dólar Australiano", "🇦🇺", "A$", False),
    "JPY": ("Iene Japonês", "🇯🇵", "¥", False),
    "CHF": ("Franco Suíço", "🇨🇭", "CHF", False),
    "CNY": ("Yuan Chinês", "🇨🇳", "CN¥", False),
    "BTC": ("Bitcoin", "₿", "₿", True),
    "ETH": ("Ethereum", "Ξ", "Ξ", True),
}
BRL = ("Real Brasileiro", "🇧🇷", "R$", False)

TICKER = ["USD", "EUR", "GBP", "ARS", "BTC", "ETH"]
ATALHOS = ["USD-BRL", "EUR-BRL", "GBP-BRL", "ARS-BRL", "BTC-BRL", "ETH-BRL"]
PERIODOS = [7, 15, 30, 90, 180]
PADRAO_PAR = re.compile(r"^[A-Z0-9]{2,6}-[A-Z0-9]{2,6}$")

# cor de cada moeda: (nome da cor no Markdown do Streamlit, cor hexadecimal para gráficos)
COR = {
    "USD": ("green", "#22A06B"), "EUR": ("blue", "#2F6FED"), "GBP": ("violet", "#8B5CF6"),
    "ARS": ("blue", "#38BDF8"), "CAD": ("red", "#EF4444"), "AUD": ("green", "#14B8A6"),
    "JPY": ("red", "#E11D48"), "CHF": ("gray", "#64748B"), "CNY": ("orange", "#F97316"),
    "BTC": ("orange", "#F7931A"), "ETH": ("violet", "#627EEA"), "BRL": ("green", "#16A34A"),
}


def cor_md(codigo: str) -> str:
    return COR.get(codigo, ("gray", "#64748B"))[0]


def cor_hex(codigo: str) -> str:
    return COR.get(codigo, ("gray", "#64748B"))[1]


# ----------------------------------------------------------------------------
# Formatação
# ----------------------------------------------------------------------------
def agora() -> datetime:
    return datetime.now(FUSO) if FUSO else datetime.now()


def numero(valor: float, casas: int = 2) -> str:
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def info_moeda(codigo: str):
    return BRL if codigo == "BRL" else MOEDAS.get(codigo, (codigo, "🌐", codigo, False))


def fmt_moeda(valor: float, codigo: str) -> str:
    _, _, simbolo, cripto = info_moeda(codigo)
    casas = 2 if abs(valor) >= 1 else (6 if cripto else 4)
    return f"{simbolo} {numero(valor, casas)}"


def fmt_pct(pct: float) -> str:
    return f"{pct:+.2f}%".replace(".", ",")


def badge_var(pct: float) -> str:
    """Selo colorido de variação: verde (alta), vermelho (queda) ou cinza (estável)."""
    if pct > 0.005:
        return f":green-badge[▲ {fmt_pct(pct)}]"
    if pct < -0.005:
        return f":red-badge[▼ {fmt_pct(pct)}]"
    return f":gray-badge[● {fmt_pct(pct)}]"


def txt_var(pct: float) -> str:
    """Texto colorido de variação para tabelas Markdown."""
    cor = "green" if pct > 0.005 else "red" if pct < -0.005 else "gray"
    return f":{cor}[**{fmt_pct(pct)}**]"


def md_tabela(cabecalhos: list[str], linhas: list[list]) -> str:
    topo = "| " + " | ".join(cabecalhos) + " |\n|" + "|".join(["---"] * len(cabecalhos)) + "|\n"
    corpo = "\n".join("| " + " | ".join(str(c) for c in linha) + " |" for linha in linhas)
    return topo + corpo


def fmt_data(texto: str) -> str:
    try:
        return datetime.strptime(texto, "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y às %H:%M:%S")
    except (ValueError, TypeError):
        return texto or "—"


def normalizar(texto: str) -> str:
    """Aceita 'usd-brl', 'USDBRL', 'usd brl' e 'eur' (assume -BRL)."""
    t = re.sub(r"[\s/_→>]+", "-", (texto or "").strip().upper()).strip("-")
    if "-" in t:
        return t
    if len(t) == 6:
        return f"{t[:3]}-{t[3:]}"
    if 2 <= len(t) <= 5:
        return f"{t}-BRL"
    return t


# ----------------------------------------------------------------------------
# Acesso à API (somente biblioteca padrão)
# ----------------------------------------------------------------------------
def http_json(url: str, timeout: int = 6):
    """Retorna (status_http, json) ou (None, None) em caso de falha de rede."""
    req = urllib.request.Request(url, headers={"User-Agent": "CambioCerto/1.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            bruto = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(bruto)
            except ValueError:
                return resp.status, None
    except urllib.error.HTTPError as erro:  # 404 e similares trazem corpo JSON
        try:
            return erro.code, json.loads(erro.read().decode("utf-8"))
        except (ValueError, OSError):
            return erro.code, None
    except (urllib.error.URLError, TimeoutError, OSError):
        return None, None


@st.cache_data(ttl=30, show_spinner=False)
def api_ultima(pares: tuple[str, ...]):
    url = f"{API_BASE}/last/{','.join(pares)}"
    for _ in range(2):
        status, corpo = http_json(url)
        if status is not None:
            return status, corpo
    return None, None


@st.cache_data(ttl=600, show_spinner=False)
def api_diaria(par: str, dias: int):
    """Série diária: dict com listas 'datas', 'valores', 'max' e 'min' (ou None)."""
    status, lista = http_json(f"{API_BASE}/daily/{par}/{dias}", timeout=8)
    if status != 200 or not isinstance(lista, list) or not lista:
        return None
    try:
        linhas = sorted(
            (
                datetime.fromtimestamp(int(i["timestamp"]), timezone.utc).replace(tzinfo=None),
                float(i["bid"]), float(i["high"]), float(i["low"]),
            )
            for i in lista
        )
    except (KeyError, ValueError, TypeError):
        return None
    return {
        "datas": [l[0] for l in linhas],
        "valores": [l[1] for l in linhas],
        "max": [l[2] for l in linhas],
        "min": [l[3] for l in linhas],
    }


def interpretar(par: str, d: dict) -> dict:
    return {
        "ok": True, "par": par, "base": d["code"], "cotada": d["codein"], "nome": d.get("name", par),
        "bid": float(d["bid"]), "ask": float(d["ask"]), "high": float(d["high"]), "low": float(d["low"]),
        "var": float(d["varBid"]), "pct": float(d["pctChange"]), "data": d.get("create_date", ""),
    }


def consultar(texto: str) -> dict:
    par = normalizar(texto)
    if not PADRAO_PAR.match(par):
        return {"ok": False, "tipo": "formato", "entrada": (texto or "").strip()}

    status, corpo = api_ultima((par,))
    if status is None:
        return {"ok": False, "tipo": "rede"}

    chave = par.replace("-", "")  # "USD-BRL" -> "USDBRL"
    if status == 200 and isinstance(corpo, dict) and chave in corpo:
        try:
            return interpretar(par, corpo[chave])
        except (KeyError, ValueError, TypeError):
            return {"ok": False, "tipo": "outro", "status": status}

    if isinstance(corpo, dict) and "message" in corpo:
        return {
            "ok": False, "tipo": "api", "par": par, "status": corpo.get("status", status),
            "codigo": corpo.get("code", "—"), "mensagem": corpo.get("message", "Par não encontrado."),
        }
    return {"ok": False, "tipo": "outro", "status": status}


# ----------------------------------------------------------------------------
# Estado da sessão
# ----------------------------------------------------------------------------
ss = st.session_state
ss.setdefault("resultado", None)
ss.setdefault("historico", [])
ss.setdefault("favoritos", [])
ss.setdefault("pendente", False)
ss.setdefault("conv_de", "USD")
ss.setdefault("conv_para", "BRL")
if "par_input" not in ss:
    ss.par_input = str(st.query_params.get("par", "USD-BRL"))[:14]  # link direto: ?par=EUR-BRL
    ss.pendente = True


def escolher_par(par: str) -> None:
    ss.par_input = par
    ss.pendente = True


def atualizar_agora(par: str) -> None:
    api_ultima.clear()
    api_diaria.clear()
    escolher_par(par)


def alternar_favorito(par: str) -> None:
    ss.favoritos.remove(par) if par in ss.favoritos else ss.favoritos.append(par)


def trocar_moedas() -> None:
    ss.conv_de, ss.conv_para = ss.conv_para, ss.conv_de


def registrar_historico(r: dict) -> None:
    ss.historico.append({
        "hora": agora().strftime("%H:%M:%S"), "par": r["par"],
        "valor": fmt_moeda(r["bid"], r["cotada"]), "pct": r["pct"], "base": r["base"],
    })
    ss.historico = ss.historico[-20:]


# ----------------------------------------------------------------------------
# Componentes
# ----------------------------------------------------------------------------
def topo() -> None:
    st.title(":rainbow[💱 Câmbio Certo]")
    st.markdown(f":green-badge[● Ao vivo] :blue-badge[Atualizado às {agora():%H:%M:%S}] :violet-badge[AwesomeAPI]")
    st.caption("Cotações de moedas e criptomoedas em tempo real.")

    status, corpo = api_ultima(tuple(f"{c}-BRL" for c in TICKER))
    for col, c in zip(st.columns(len(TICKER)), TICKER):
        _, bandeira, _, _ = MOEDAS[c]
        valor, delta, cor = "—", None, "off"
        if status == 200 and isinstance(corpo, dict) and f"{c}BRL" in corpo:
            try:
                d = corpo[f"{c}BRL"]
                valor, pct = fmt_moeda(float(d["bid"]), "BRL"), float(d["pctChange"])
                delta, cor = fmt_pct(pct), ("normal" if abs(pct) >= 0.005 else "off")
            except (KeyError, ValueError, TypeError):
                pass
        with col.container(border=True):
            st.metric(f":{cor_md(c)}[{bandeira} **{c}**]", valor, delta=delta, delta_color=cor)


def mostrar_erro(r: dict) -> None:
    tipo = r["tipo"]
    if tipo == "formato":
        st.error(
            f"**Formato inválido:** não foi possível interpretar “{r['entrada'] or '(vazio)'}”.\n\n"
            "- Use o padrão MOEDA-MOEDA, por exemplo: `USD-BRL`\n"
            "- Digite apenas a moeda (ex.: `EUR`) para cotar em reais"
        )
    elif tipo == "rede":
        st.error(
            "**Sem conexão com o serviço de cotações.**\n\n"
            "- Verifique sua conexão com a internet\n- Tente novamente em alguns instantes"
        )
    elif tipo == "api":
        st.error(
            "**Par de moedas não encontrado.** A API não retornou cotação para o par informado.\n\n"
            f"- **Status:** {r['status']}\n- **Código do erro:** {r['codigo']}\n- **Motivo:** {r['mensagem']}"
        )
    else:
        st.error(f"**Não foi possível concluir a consulta.** Resposta inesperada (HTTP {r.get('status')}).")


# ----------------------------------------------------------------------------
# Abas
# ----------------------------------------------------------------------------
def aba_cotacao() -> None:
    st.subheader("Consulte qualquer par de moedas", divider="blue")
    with st.form("form_consulta", border=False):
        c1, c2 = st.columns([4, 1.4], vertical_alignment="bottom")
        c1.text_input(
            "Par de moedas", key="par_input", placeholder="Ex.: USD-BRL, EUR, btc-brl",
            help="Formatos aceitos: USD-BRL · usd brl · USDBRL · EUR (assume BRL)",
        )
        enviado = c2.form_submit_button("Consultar cotação", type="primary")

    st.caption("Atalhos")
    ativo = normalizar(ss.par_input)
    for col, par in zip(st.columns(len(ATALHOS)), ATALHOS):
        bandeira = info_moeda(par.split("-")[0])[1]
        col.button(
            f"{bandeira} {par}", key=f"atalho_{par}", on_click=escolher_par, args=(par,),
            type="primary" if par == ativo else "secondary",  # atalho ativo em destaque colorido
        )

    if ss.favoritos:
        st.caption("⭐ Seus favoritos")
        for col, par in zip(st.columns(max(len(ss.favoritos), 6)), ss.favoritos):
            col.button(par, key=f"fav_{par}", on_click=escolher_par, args=(par,))

    if enviado or ss.pendente:
        ss.pendente = False
        with st.spinner("Consultando cotação..."):
            ss.resultado = consultar(ss.par_input)
        if ss.resultado["ok"]:
            registrar_historico(ss.resultado)
            st.query_params["par"] = ss.resultado["par"]

    r = ss.resultado
    if r is None:
        return
    if not r["ok"]:
        mostrar_erro(r)
        return

    cotada = r["cotada"]
    cor = cor_md(r["base"])
    with st.container(border=True):
        st.markdown(
            f":{cor}-badge[{info_moeda(r['base'])[1]} {r['base']} → {info_moeda(cotada)[1]} {cotada}] "
            f"{badge_var(r['pct'])}  \n:{cor}[**{r['nome']}**]"
        )
        st.metric(":blue[Valor atual]", fmt_moeda(r["bid"], cotada), delta=fmt_pct(r["pct"]))
        st.caption(f"Atualizado em {fmt_data(r['data'])}")

    m = st.columns(4)
    m[0].metric(":blue[Compra]", fmt_moeda(r["bid"], cotada))
    m[1].metric(":orange[Venda]", fmt_moeda(r["ask"], cotada))
    m[2].metric(":green[Máxima do dia]", fmt_moeda(r["high"], cotada))
    m[3].metric(":red[Mínima do dia]", fmt_moeda(r["low"], cotada))

    b1, b2, _ = st.columns([1.2, 1.2, 4])
    b1.button(
        "★ Nos favoritos" if r["par"] in ss.favoritos else "☆ Favoritar",
        key="btn_fav", on_click=alternar_favorito, args=(r["par"],),
    )
    b2.button("↻ Atualizar", key="btn_atualizar", on_click=atualizar_agora, args=(r["par"],))

    st.subheader("Evolução no período", divider="violet")
    dias = st.radio(
        "Período", PERIODOS, index=2, horizontal=True, key="periodo_cot",
        format_func=lambda d: f"{d} dias", label_visibility="collapsed",
    )
    serie = api_diaria(r["par"], dias)
    if serie is None:
        st.caption("Histórico indisponível para este par no momento.")
    else:
        v = serie["valores"]
        variacao = (v[-1] / v[0] - 1) * 100 if v[0] else 0.0
        # gráfico em área: verde quando o período fecha em alta, vermelho quando fecha em queda
        st.area_chart({"Data": serie["datas"], "Cotação": v}, x="Data", y="Cotação",
                      color="#16A34A" if variacao >= 0 else "#DC2626", height=300)
        s = st.columns(4)
        s[0].metric(":violet[Variação no período]", fmt_pct(variacao), delta=fmt_pct(variacao))
        s[1].metric(":blue[Média]", fmt_moeda(sum(v) / len(v), cotada))
        s[2].metric(":green[Máxima]", fmt_moeda(max(serie["max"]), cotada))
        s[3].metric(":red[Mínima]", fmt_moeda(min(serie["min"]), cotada))

    if ss.historico:
        with st.expander("🕘 Histórico de consultas desta sessão"):
            st.markdown(md_tabela(
                ["Hora", "Par", "Valor", "Variação"],
                [[h["hora"], f":{cor_md(h['base'])}[**{h['par']}**]", h["valor"], txt_var(h["pct"])]
                 for h in reversed(ss.historico[-8:])],
            ))


def aba_conversor() -> None:
    st.subheader("Conversor de moedas", divider="green")
    st.caption("Converta valores entre reais, moedas estrangeiras e criptomoedas pela cotação atual.")
    codigos = ["BRL"] + list(MOEDAS)
    rotulo = lambda c: f"{info_moeda(c)[1]} {c} · {info_moeda(c)[0]}"

    c1, c2, c3, c4 = st.columns([1.3, 2, 0.6, 2], vertical_alignment="bottom")
    valor = c1.number_input("Valor", min_value=0.0, value=100.0, step=10.0, format="%.2f", key="conv_valor")
    de = c2.selectbox("De", codigos, key="conv_de", format_func=rotulo)
    c3.button("⇄", key="btn_trocar", on_click=trocar_moedas, help="Inverter moedas")
    para = c4.selectbox("Para", codigos, key="conv_para", format_func=rotulo)

    if de == para:
        st.info("Selecione moedas diferentes para realizar a conversão.")
        return

    necessarias = tuple(sorted({f"{c}-BRL" for c in (de, para) if c != "BRL"}))
    status, corpo = api_ultima(necessarias)
    try:
        if status != 200 or not isinstance(corpo, dict):
            raise ValueError
        taxa_brl = {"BRL": 1.0}
        for par in necessarias:
            taxa_brl[par[:-4]] = float(corpo[par.replace("-", "")]["bid"])
        taxa = taxa_brl[de] / taxa_brl[para]
    except (ValueError, KeyError, TypeError, ZeroDivisionError):
        st.error("**Conversão indisponível.** Não foi possível obter as cotações agora. Tente novamente em instantes.")
        return

    with st.container(border=True):
        st.markdown(f":{cor_md(de)}[**{numero(valor, 2)} {de}**] equivalem a")
        st.markdown(f"## :{cor_md(para)}[{fmt_moeda(valor * taxa, para)}]")
        st.caption(f"1 {de} = {fmt_moeda(taxa, para)}  ·  1 {para} = {fmt_moeda(1 / taxa, de)}")
    st.caption("Cálculo feito a partir da cotação de compra de cada moeda em relação ao real.")


def aba_analise() -> None:
    st.subheader("Análise comparativa", divider="orange")
    st.caption("Compare a evolução de várias moedas no mesmo período (base 100 no primeiro dia).")
    c1, c2 = st.columns([3, 2])
    escolhidas = c1.multiselect(
        "Moedas", list(MOEDAS), default=["USD", "EUR"],
        format_func=lambda c: f"{c} · {MOEDAS[c][0]}", max_selections=6,
    )
    dias = c2.radio("Período", PERIODOS, index=2, horizontal=True, key="periodo_analise", format_func=lambda d: f"{d} dias")

    if not escolhidas:
        st.info("Selecione ao menos uma moeda para visualizar a comparação.")
        return

    series, resumo = {}, []
    for c in escolhidas:
        s = api_diaria(f"{c}-BRL", dias)
        if s is None:
            continue
        base = s["valores"][0]
        series[c] = {d.date(): v / base * 100 for d, v in zip(s["datas"], s["valores"])}
        atual = s["valores"][-1]
        resumo.append({
            "Moeda": f":{cor_md(c)}[**{c}**] · {MOEDAS[c][0]}", "Atual": fmt_moeda(atual, "BRL"),
            "Variação": txt_var((atual / base - 1) * 100),
            "Mínima": f":red[{fmt_moeda(min(s['min']), 'BRL')}]",
            "Máxima": f":green[{fmt_moeda(max(s['max']), 'BRL')}]",
            "_ord": atual / base,
        })

    if not series:
        st.error("**Histórico indisponível.** Não foi possível carregar a série histórica agora.")
        return

    datas = sorted({d for s in series.values() for d in s})
    dados = {"Data": datas}
    for c, s in series.items():
        dados[c] = [s.get(d) for d in datas]  # None = sem cotação no dia (ex.: fim de semana)
    st.line_chart(dados, x="Data", y=list(series), color=[cor_hex(c) for c in series], height=320)

    resumo.sort(key=lambda x: -x["_ord"])
    cabecalhos = ["Moeda", "Atual", "Variação", "Mínima", "Máxima"]
    st.markdown(md_tabela(cabecalhos, [[linha[k] for k in cabecalhos] for linha in resumo]))


def aba_sobre() -> None:
    st.subheader("Sobre o Câmbio Certo", divider="rainbow")
    st.caption("Ferramenta gratuita para consultar e acompanhar cotações de forma simples e confiável.")
    with st.expander("De onde vêm os dados?", expanded=True):
        st.write("As cotações são fornecidas pela AwesomeAPI, que consolida valores de mercado de moedas e criptomoedas em relação ao real.")
    with st.expander("Com que frequência as cotações são atualizadas?"):
        st.write("Os valores são renovados a cada 30 segundos. O botão “Atualizar” força uma nova consulta imediatamente.")
    with st.expander("Quais formatos de par são aceitos?"):
        st.write("Você pode digitar USD-BRL, usd brl, USDBRL ou apenas a sigla da moeda (por exemplo, EUR), caso em que a cotação é feita em reais.")
    with st.expander("Posso compartilhar uma cotação específica?"):
        st.write("Sim. Ao consultar um par, o endereço da página passa a incluir o parâmetro correspondente (por exemplo, ?par=EUR-BRL). Basta copiar e enviar o link.")
    with st.expander("Aviso importante"):
        st.write("Os valores têm caráter informativo e podem diferir dos praticados por bancos, corretoras e casas de câmbio. Não constituem recomendação de investimento.")


# ----------------------------------------------------------------------------
# Página
# ----------------------------------------------------------------------------
topo()
tab1, tab2, tab3, tab4 = st.tabs([":blue[💱 Cotação]", ":green[🔄 Conversor]", ":orange[📈 Análise]", ":violet[ℹ️ Sobre]"])
with tab1:
    aba_cotacao()
with tab2:
    aba_conversor()
with tab3:
    aba_analise()
with tab4:
    aba_sobre()

st.divider()
st.caption(f"© {agora().year} {APP_NOME} · Fonte dos dados: AwesomeAPI · Valores informativos, sem caráter de recomendação de investimento.")
