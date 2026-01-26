import streamlit as st
import feedparser
import requests
from datetime import datetime, timedelta, timezone, time as dt_time

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Clipping Alerts", page_icon="🔗", layout="wide")
st.title("🔗 Formatador de Google Alerts")
st.markdown("Transforma seus RSS do Google Alerts em uma lista única e limpa (08:30 às 08:30).")

# ==============================================================================
# ÁREA DE CONFIGURAÇÃO DOS LINKS (COLE SEUS LINKS DO GOOGLE ALERTS AQUI)
# ==============================================================================

# Lista 1: Links dos Alertas do SISEMA (Semad, IEF, Feam, Igam...)
# Cole cada link RSS entre aspas, separado por vírgula.
URLS_ALERTS_SISEMA = [
    "https://www.google.com.br/alerts/feeds/06474796398566785113/8556040124559167503",
    "https://www.google.com.br/alerts/feeds/06474796398566785113/3256954388664724591",
    "https://www.google.com.br/alerts/feeds/06474796398566785113/8177748629976302199",
    "https://www.google.com.br/alerts/feeds/06474796398566785113/779453071302735537"
]

# Lista 2: Links dos Alertas GERAIS (Relevantes, Curiosidades...)
URLS_ALERTS_GERAL = [
    "https://www.google.com.br/alerts/feeds/06474796398566785113/13915059247713257237"
]

# ==============================================================================

def resolver_link_final(url_google):
    """Transforma o link redirecionado do Google no link real do site"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        # O Google Alerts usa links do tipo google.com/url?q=...
        # Precisamos extrair o 'q' ou seguir o redirect.
        if "url?q=" in url_google:
            # Tentativa rápida de extração via texto (mais rápido que requisição)
            inicio = url_google.find("url?q=") + 6
            fim = url_google.find("&ct=")
            if fim != -1:
                return url_google[inicio:fim]
        
        # Se não der certo extrair, faz a requisição
        r = requests.head(url_google, allow_redirects=True, timeout=5, headers=headers)
        if r.status_code == 200: return r.url
        r = requests.get(url_google, allow_redirects=True, timeout=5, headers=headers)
        return r.url
    except:
        return url_google

def limpar_nome_veiculo(nome_cru, titulo_materia):
    # Tenta pegar do título (Padrão: Título - Veículo)
    if " - " in titulo_materia:
        possivel_nome = titulo_materia.rsplit(" - ", 1)[1].strip()
        if len(possivel_nome) < 40: nome_cru = possivel_nome

    nome = nome_cru.replace("www.", "").replace(".com.br", "").replace(".com", "").replace(".gov", "")
    nome = nome.replace("-", " ").replace("_", " ")
    
    mapa = {
        "gazetadevarginha": "Gazeta de Varginha", "diariodoaco": "Diário do Aço",
        "em": "Estado de Minas", "otempo": "O Tempo", "hojeemdia": "Hoje em Dia",
        "folha": "Folha de S.Paulo", "agenciaminas": "Agência Minas",
        "g1": "Portal G1", "uol": "Portal UOL", "r7": "Portal R7", "youtube": "YouTube",
        "oeco": "O Eco", "conexaoplaneta": "Conexão Planeta"
    }
    
    nome_lower = nome.lower()
    for k, v in mapa.items():
        if k in nome_lower: return v
    return nome.title()

def converter_para_brt(struct_time_utc):
    dt_utc = datetime(*struct_time_utc[:6], tzinfo=timezone.utc)
    return (dt_utc - timedelta(hours=3)).replace(tzinfo=None)

def processar_feeds(lista_urls, data_referencia):
    # Define a janela 08:30 (Ontem) até 08:30 (Hoje)
    fim_janela = datetime.combine(data_referencia, dt_time(8, 30))
    inicio_janela = fim_janela - timedelta(days=1)
    
    resultados = {}
    links_vistos = set()
    
    progresso_total = len(lista_urls)
    barra = st.progress(0)
    msg = st.empty()
    
    for i, url in enumerate(lista_urls):
        if "COLE_O_LINK" in url: continue # Pula placeholders vazios
        
        msg.text(f"Lendo Alerta {i+1}...")
        barra.progress((i)/progresso_total)
        
        feed = feedparser.parse(url)
        
        for entry in feed.entries:
            # 1. Filtro de Horário
            if hasattr(entry, 'published_parsed'):
                try:
                    pub_dt = converter_para_brt(entry.published_parsed)
                    if not (inicio_janela <= pub_dt <= fim_janela):
                        continue
                except: continue
            
            # 2. Dados
            titulo = entry.title
            
            # Limpeza HTML que às vezes vem no título do Alerts
            titulo = titulo.replace("<b>", "").replace("</b>", "").replace("&quot;", '"')
            
            # Limpeza Veículo
            if " - " in titulo: 
                titulo_limpo = titulo.rsplit(" - ", 1)[0]
            else: 
                titulo_limpo = titulo
            
            # Deduplicação
            chave = titulo_limpo.lower()
            if chave not in links_vistos:
                links_vistos.add(chave)
                
                v_raw = entry.source.title if 'source' in entry else "Fonte Desconhecida"
                veiculo = limpar_nome_veiculo(v_raw, entry.title)
                link_real = resolver_link_final(entry.link)
                
                if veiculo not in resultados: resultados[veiculo] = []
                resultados[veiculo].append({'titulo': titulo_limpo, 'link': link_real})
    
    barra.empty()
    msg.empty()
    return resultados

# --- INTERFACE ---

st.info("Este sistema processa os links RSS do seu Google Alerts, filtra pelo horário (08:30 a 08:30) e formata a lista.")
data = st.date_input("Data de Referência:", format="DD/MM/YYYY")

if st.button("🚀 Processar Alertas", type="primary"):
    
    # Validação simples
    if "COLE_O_LINK" in URLS_ALERTS_SISEMA[0]:
        st.error("⚠️ Você precisa colar os links RSS do Google Alerts no código (arquivo .py) antes de rodar!")
    else:
        d_sisema = processar_feeds(URLS_ALERTS_SISEMA, data)
        d_geral = processar_feeds(URLS_ALERTS_GERAL, data)
        
        # --- MONTAGEM DO TEXTO ---
        ontem = data - timedelta(days=1)
        txt = f"CLIPPING DIÁRIO - {data.strftime('%d/%m/%Y')}\n"
        txt += f"Janela: {ontem.strftime('%d/%m')} (08:30) a {data.strftime('%d/%m')} (08:30)\n\n"
        
        def fmt(dados, tit):
            t = f"=== {tit} ===\n"
            if not dados: return t + "Nenhuma matéria encontrada neste período.\n\n"
            for v in sorted(dados.keys()):
                t += f"{v}\n"
                for n in dados[v]:
                    t += f"{n['titulo']}\n{n['link']}\n"
                t += "\n"
            return t + "\n"

        txt += fmt(d_sisema, "MATÉRIAS QUE CITAM O SISEMA")
        txt += "----------------------------------------\n\n"
        txt += fmt(d_geral, "MATÉRIAS AMBIENTAIS RELEVANTES")
        
        st.success("Lista Gerada com a precisão do Google Alerts!")
        st.text_area("Copie aqui:", txt, height=600)
        
        # Área de conferência
        st.markdown("---")
        c1, c2 = st.columns(2)
        def conf(dados, tit):
            st.markdown(f"##### {tit}")
            if not dados: st.caption("Vazio")
            for v in sorted(dados.keys()):
                st.markdown(f"**{v}**")
                for n in dados[v]: st.markdown(f"• [{n['titulo']}]({n['link']})")
        
        with c1: conf(d_sisema, "SISEMA")
        with c2: conf(d_geral, "GERAL")
