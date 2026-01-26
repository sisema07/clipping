import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from dateutil import parser
import re

# ===============================
# CONFIGURAÇÕES GERAIS
# ===============================

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

# ===============================
# FUNÇÕES AUXILIARES
# ===============================

def noticia_relevante(titulo):
    titulo = titulo.lower()
    return not any(palavra in titulo for palavra in PALAVRAS_EXCLUIDAS)

def cita_orgao_mg(texto):
    texto = texto.lower()
    return any(orgao.lower() in texto for orgao in ORGAOS_MG)

def dentro_do_intervalo(data_noticia, inicio, fim):
    return inicio <= data_noticia <= fim

# ===============================
# BUSCA DE NOTÍCIAS
# ===============================

def buscar_noticias(data_selecionada):
    inicio = datetime.combine(data_selecionada - timedelta(days=1), datetime.strptime("08:30", "%H:%M").time())
    fim = datetime.combine(data_selecionada, datetime.strptime("08:30", "%H:%M").time())

    noticias_orgao = []
    noticias_gerais = []

    for veiculo, url in FONTES.items():
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")

            links = soup.find_all("a", href=True)

            for link in links:
                titulo = link.get_text(strip=True)
                href = link["href"]

                if not titulo or len(titulo) < 30:
                    continue

                if not noticia_relevante(titulo):
                    continue

                if not href.startswith("http"):
                    continue

                texto_completo = titulo.lower()

                data_publicacao = datetime.now()  # fallback

                if not dentro_do_intervalo(data_publicacao, inicio, fim):
                    continue

                noticia = {
                    "veiculo": veiculo,
                    "titulo": titulo,
                    "link": href
                }

                if cita_orgao_mg(texto_completo):
                    noticias_orgao.append(noticia)
                else:
                    noticias_gerais.append(noticia)

        except Exception as e:
            st.warning(f"Erro ao buscar em {veiculo}: {e}")

    return noticias_orgao, noticias_gerais

# ===============================
# INTERFACE STREAMLIT
# ===============================

st.set_page_config(page_title="Clipping Ambiental MG", layout="wide")

st.title("🌱 Clipping Ambiental – Minas Gerais")

st.markdown(
    """
    Buscador de matérias ambientais com foco em **Minas Gerais**  
    Período considerado: **08:30 do dia anterior até 08:30 do dia selecionado**
    """
)

data_escolhida = st.date_input("📅 Selecione a data das publicações")

if st.button("🔎 Buscar notícias"):
    with st.spinner("Buscando matérias ambientais relevantes..."):
        orgaos, gerais = buscar_noticias(data_escolhida)

    st.subheader("🏛️ Matérias que citam órgãos ambientais de Minas Gerais")

    if orgaos:
        for n in orgaos:
            st.markdown(f"**{n['veiculo']}**")
            st.markdown(n["titulo"])
            st.markdown(n["link"])
            st.markdown("---")
    else:
        st.info("Nenhuma matéria com citação direta a órgãos ambientais encontrada.")

    st.subheader("🌍 Outras matérias ambientais relevantes")

    if gerais:
        for n in gerais:
            st.markdown(f"**{n['veiculo']}**")
            st.markdown(n["titulo"])
            st.markdown(n["link"])
            st.markdown("---")
    else:
        st.info("Nenhuma outra matéria ambiental relevante encontrada.")
