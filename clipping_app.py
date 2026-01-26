import streamlit as st
import feedparser
from datetime import datetime, timedelta
import re

# =========================
# CONFIGURAÇÕES
# =========================

ORGAOS_MG = [
    "SISEMA",
    "Sistema Estadual de Meio Ambiente e Recursos Hídricos",
    "SEMAD MG",
    "Secretaria de Estado de Meio Ambiente e Desenvolvimento Sustentável de Minas Gerais",
    "FEAM",
    "Fundação Estadual do Meio Ambiente",
    "IEF",
    "Instituto Estadual de Florestas",
    "IGAM",
    "Instituto Mineiro de Gestão das Águas",
    "Secretaria de Meio Ambiente de Minas Gerais"
]

PALAVRAS_EXCLUIDAS = [
    "concurso",
    "previsão do tempo",
    "temperatura",
    "clima hoje",
    "meteorologia"
]

FONTES = {
    "Portal O Tempo": "https://www.otempo.com.br/busca?q=meio%20ambiente",
    "Portal G1": "https://g1.globo.com/meio-ambiente/",
    "Portal Estado de Minas": "https://www.em.com.br/busca/meio%20ambiente/",
    "Portal Hoje Em Dia": "https://www.hojeemdia.com.br/?term=meio+ambiente",
    "Portal O Eco": "https://oeco.org.br/category/noticias/,
    "Portal Agência Brasil": "https://agenciabrasil.ebc.com.br/meio-ambiente",
    "Portal Conexão Planeta": "https://conexaoplaneta.com.br/?s=meio+ambiente,
    "Portal Sou Ecológico": "https://www.souecologico.com.br/sou-ecologico/meio-ambiente/",
    "Portal BHAZ": "https://bhaz.com.br/?s=meio+ambiente"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

RSS_FEEDS = {
    "Portal O Tempo": "https://www.otempo.com.br/rss",
    "Estado de Minas": "https://www.em.com.br/rss",
    "G1 Minas": "https://g1.globo.com/rss/g1/mg/"
}

# =========================
# FUNÇÕES
# =========================

def titulo_relevante(titulo):
    titulo = titulo.lower()
    return not any(p in titulo for p in PALAVRAS_EXCLUIDAS)

def cita_orgao_mg(texto):
    texto = texto.lower()
    return any(o.lower() in texto for o in ORGAOS_MG)

def dentro_janela(data_pub, data_escolhida):
    inicio = datetime.combine(
        data_escolhida - timedelta(days=1),
        datetime.strptime("08:30", "%H:%M").time()
    )
    fim = datetime.combine(
        data_escolhida,
        datetime.strptime("08:30", "%H:%M").time()
    )
    return inicio <= data_pub <= fim

def buscar_noticias(data_escolhida):
    orgaos = []
    gerais = []

    for veiculo, feed_url in RSS_FEEDS.items():
        feed = feedparser.parse(feed_url)

        for entry in feed.entries:
            titulo = entry.title
            link = entry.link

            if not titulo_relevante(titulo):
                continue

            resumo = entry.get("summary", "")
            texto = f"{titulo} {resumo}"

            try:
                data_pub = datetime(*entry.published_parsed[:6])
            except:
                continue

            if not dentro_janela(data_pub, data_escolhida):
                continue

            noticia = {
                "veiculo": veiculo,
                "titulo": titulo,
                "link": link
            }

            if cita_orgao_mg(texto):
                orgaos.append(noticia)
            else:
                if "meio ambiente" in texto.lower() or "ambiental" in texto.lower():
                    gerais.append(noticia)

    return orgaos, gerais

# =========================
# INTERFACE STREAMLIT
# =========================

st.set_page_config(
    page_title="Clipping Ambiental MG",
    page_icon="🌱",
    layout="wide"
)

st.title("🌱 Clipping Ambiental – Minas Gerais")
st.caption("Janela de coleta: 08:30 do dia anterior até 08:30 do dia selecionado")

data_escolhida = st.date_input("📅 Selecione a data")

if st.button("🔎 Buscar matérias"):
    with st.spinner("Coletando notícias ambientais..."):
        orgaos, gerais = buscar_noticias(data_escolhida)

    st.subheader("🏛️ Matérias com citação a órgãos ambientais de MG")

    if orgaos:
        for n in orgaos:
            st.markdown(f"**{n['veiculo']}**")
            st.markdown(n["titulo"])
            st.markdown(n["link"])
            st.markdown("---")
    else:
        st.info("Nenhuma matéria com citação direta a órgãos ambientais de MG.")

    st.subheader("🌍 Outras matérias ambientais relevantes")

    if gerais:
        for n in gerais:
            st.markdown(f"**{n['veiculo']}**")
            st.markdown(n["titulo"])
            st.markdown(n["link"])
            st.markdown("---")
    else:
        st.info("Nenhuma outra matéria ambiental relevante encontrada.")
