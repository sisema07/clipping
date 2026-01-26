import streamlit as st
import feedparser
import requests
from datetime import datetime, timedelta, timezone, time as dt_time
import re

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Clipping Diário", page_icon="✂️", layout="wide")

st.title("✂️ Clipping Diário")
st.markdown("Monitoramento 08:30 às 08:30 | Exclusivo MG | Sites Prioritários")

# --- LISTAS DE CONTROLE ---

# Fontes Obrigatórias (O robô vai varrer estes domínios especificamente)
FONTES_OBRIGATORIAS = [
    "em.com.br",                # Estado de Minas
    "otempo.com.br",            # O Tempo
    "hojeemdia.com.br",         # Hoje em Dia
    "g1.globo.com/mg",          # G1 Minas (Ajustado para focar em MG)
    "g1.globo.com/meio-ambiente", # G1 Meio Ambiente
    "oeco.org.br",              # O Eco
    "agenciabrasil.ebc.com.br/meio-ambiente", # Agência Brasil
    "conexaoplaneta.com.br"     # Conexão Planeta
]

# Termos de Bloqueio (Ruídos)
TERMOS_BLOQUEIO_GERAL = [
    "PREVISÃO DO TEMPO", "VAI CHOVER", "CHUVA EM", "TEMPO EM", "CLIMA EM", "SOL COM NUVENS", "METEOROLOGIA",
    "CONCURSO", "EDITAL", "VAGA", "INSCRIÇÃO", "PROCESSO SELETIVO", "GABARITO",
    "PALESTRA", "WORKSHOP", "SEMINÁRIO", "AULA", "ALUNOS", "ESCOLA", "REUNIÃO",
    "COMUNICADO", "CURSO", "FORMATURA", "VESTIBULAR", "ENEM", "ESTÁGIO"
]

# --- FUNÇÕES DE SUPORTE ---

def resolver_link_final(url_google):
    """Descobre o link original"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.head(url_google, allow_redirects=True, timeout=5, headers=headers)
        if response.status_code == 200:
            return response.url
        else:
            response = requests.get(url_google, allow_redirects=True, timeout=5, headers=headers)
            return response.url
    except:
        return url_google

def limpar_nome_veiculo(nome_cru, titulo_materia):
    """Padroniza o nome do veículo"""
    if " - " in titulo_materia:
        possivel_nome = titulo_materia.rsplit(" - ", 1)[1].strip()
        if len(possivel_nome) < 40:
            nome_cru = possivel_nome

    nome = nome_cru.replace("www.", "").replace(".com.br", "").replace(".com", "").replace(".org", "").replace(".gov", "")
    nome = nome.replace("-", " ").replace("_", " ")
    
    mapa_correcao = {
        "gazetadevarginha": "Gazeta de Varginha",
        "diariodoaco": "Diário do Aço",
        "em": "Estado de Minas",
        "otempo": "O Tempo",
        "hojeemdia": "Hoje em Dia",
        "tribunademinas": "Tribuna de Minas",
        "folha": "Folha de S.Paulo",
        "agenciaminas": "Agência Minas",
        "almg": "Assembleia Legislativa (ALMG)",
        "g1": "Portal G1",
        "uol": "Portal UOL",
        "r7": "Portal R7",
        "youtube": "YouTube",
        "oeco": "O Eco",
        "conexaoplaneta": "Conexão Planeta",
        "agenciabrasil": "Agência Brasil"
    }
    
    nome_lower = nome.lower()
    for chave, valor in mapa_correcao.items():
        if chave in nome_lower:
            return valor
            
    return nome.title()

def verificar_relevancia_geral(titulo):
    """Filtra ruídos"""
    titulo_upper = titulo.upper()
    for bloqueio in TERMOS_BLOQUEIO_GERAL:
        if bloqueio in titulo_upper:
            return False
    return True

def converter_para_brt(struct_time_utc):
    dt_utc = datetime(*struct_time_utc[:6], tzinfo=timezone.utc)
    dt_brt = dt_utc - timedelta(hours=3)
    return dt_brt.replace(tzinfo=None)

# --- FUNÇÃO MESTRA DE BUSCA ---
def executar_busca_inteligente(termos_lista, fontes_especificas, data_referencia, tipo_filtro, container_status, barra_progresso, progresso_atual, total_etapas):
    
    fim_janela = datetime.combine(data_referencia, dt_time(8, 30))
    inicio_janela = fim_janela - timedelta(days=1)
    
    noticias_temp = [] # Lista temporária para processamento
    
    # 1. BUSCA GERAL (Varredura na Web)
    for termo in termos_lista:
        progresso_atual += 1
        container_status.text(f"Varrendo Web: {termo}...")
        barra_progresso.progress(progresso_atual / total_etapas)
        
        termo_url = termo.replace(" ", "+")
        q_after = (data_referencia - timedelta(days=2)).strftime("%Y-%m-%d")
        q_before = (data_referencia + timedelta(days=1)).strftime("%Y-%m-%d")
        
        rss_url = f"https://news.google.com/rss/search?q={termo_url}+after:{q_after}+before:{q_before}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        noticias_temp.append(rss_url)

    # 2. BUSCA DIRECIONADA (Sites Obrigatórios)
    # Cria uma "Super Query" (Termo1 OR Termo2) site:site.com
    # Isso economiza tempo e foca no site específico
    
    # Prepara os termos para a query combinada (remove aspas para simplificar a concatenação OR)
    termos_limpos = []
    for t in termos_lista:
        # Extrai a palavra chave principal para o OR (ex: "Semad" "Minas" -> Semad)
        # Pega a primeira palavra entre aspas ou a primeira palavra
        match = re.search(r'"([^"]+)"', t)
        if match:
            termos_limpos.append(match.group(1))
        else:
            termos_limpos.append(t.split()[0])
            
    # Cria string (Termo1 OR Termo2 OR Termo3)
    query_or = "(" + " OR ".join([f'"{x}"' for x in termos_limpos]) + ")"
    
    for site in fontes_especificas:
        progresso_atual += 1
        container_status.text(f"Varrendo Site Específico: {site}...")
        barra_progresso.progress(progresso_atual / total_etapas)
        
        # Query: (Semad OR IEF ...) site:em.com.br
        query_site = f"{query_or} site:{site}"
        query_url = query_site.replace(" ", "+")
        
        q_after = (data_referencia - timedelta(days=2)).strftime("%Y-%m-%d")
        q_before = (data_referencia + timedelta(days=1)).strftime("%Y-%m-%d")
        
        rss_url = f"https://news.google.com/rss/search?q={query_url}+after:{q_after}+before:{q_before}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        noticias_temp.append(rss_url)

    # --- PROCESSAMENTO DOS FEEDS ---
    resultados_agrupados = {}
    urls_processadas = set() # Para evitar duplicatas entre Busca Geral e Busca Específica

    for url_feed in noticias_temp:
        feed = feedparser.parse(url_feed)
        
        for entry in feed.entries:
            # Filtro Horário
            if hasattr(entry, 'published_parsed'):
                try:
                    pub_dt_brt = converter_para_brt(entry.published_parsed)
                    if not (inicio_janela <= pub_dt_brt <= fim_janela):
                        continue
                except:
                    continue

            titulo_completo = entry.title
            link_google = entry.link
            
            if " - " in titulo_completo:
                titulo_limpo = titulo_completo.rsplit(" - ", 1)[0]
            else:
                titulo_limpo = titulo_completo

            # Filtro de Relevância
            if tipo_filtro == "GERAL":
                if not verificar_relevancia_geral(titulo_limpo):
                    continue
            
            # Deduplicação (chave = título minúsculo)
            chave = titulo_limpo.lower()
            if chave not in urls_processadas:
                urls_processadas.add(chave)
                
                veiculo_sujo = entry.source.title if 'source' in entry else "Fonte Desconhecida"
                veiculo_limpo = limpar_nome_veiculo(veiculo_sujo, titulo_completo)
                
                # Resolve Link
                link_real = resolver_link_final(link_google)
                
                if veiculo_limpo not in resultados_agrupados:
                    resultados_agrupados[veiculo_limpo] = []
                
                resultados_agrupados[veiculo_limpo].append({
                    "titulo": titulo_limpo,
                    "link": link_real
                })
                
    return resultados_agrupados, progresso_atual

# --- INTERFACE ---

st.info("O sistema buscará notícias entre 08:30 de ontem e 08:30 de hoje (data selecionada).")
data_escolhida = st.date_input("Selecione a Data de Referência:", format="DD/MM/YYYY")

if st.button("🚀 Gerar Clipping (Web + Sites Prioritários)", type="primary"):
    
    container_status = st.empty()
    barra = st.progress(0)
    
    # Definição dos Termos
    exclusoes = "-Bahia -BA -Mato -MT -Acre -AC -Tocantins -TO -Amazonas -AM -Pará -PA"
    
    termos_sisema = [
        f'"Semad" "Minas Gerais" {exclusoes}', 
        f'"Sisema" "Minas Gerais" {exclusoes}',
        f'"Sistema Estadual de Meio Ambiente" "Minas Gerais" {exclusoes}',
        f'"Secretaria de Estado de Meio Ambiente" "Minas Gerais" {exclusoes}',
        f'"IEF" "Minas Gerais" {exclusoes}', 
        f'"Instituto Estadual de Florestas" "Minas Gerais" {exclusoes}',
        f'"Feam" "Minas Gerais" {exclusoes}', 
        f'"Fundação Estadual do Meio Ambiente" "Minas Gerais" {exclusoes}',
        f'"Igam" "Minas Gerais" {exclusoes}',
        f'"Instituto Mineiro de Gestão das Águas" "Minas Gerais" {exclusoes}'
    ]
    
    termos_geral = [
        '"Acidente ambiental" Minas Gerais',
        '"Rompimento" barragem Minas Gerais',
        '"Vazamento" rejeito Minas Gerais',
        '"Onça" Minas Gerais',  
        '"Lobo guará" Minas Gerais',
        '"Resgate" animal Minas Gerais',
        '"Multa ambiental" Minas Gerais',
        '"Crime ambiental" Minas Gerais',
        '"Desmatamento ilegal" Minas Gerais',
        '"Poluição rio" Minas Gerais',
        '"Mortandade peixes" Minas Gerais',
        '"Espécie rara" Minas Gerais',
        '"Nova espécie" Minas Gerais',
        '"Incêndio" parque estadual Minas',
        '"Operação" meio ambiente Minas Gerais'
    ]
    
    # Cálculo para barra de progresso
    # Etapas = (Termos Sisema + Sites Sisema) + (Termos Geral + Sites Geral)
    total_etapas = len(termos_sisema) + len(FONTES_OBRIGATORIAS) + len(termos_geral) + len(FONTES_OBRIGATORIAS)
    prog_atual = 0
    
    # 1. EXECUÇÃO SISEMA
    dados_sisema, prog_atual = executar_busca_inteligente(
        termos_sisema, FONTES_OBRIGATORIAS, data_escolhida, "SISEMA", 
        container_status, barra, prog_atual, total_etapas
    )
    
    # 2. EXECUÇÃO GERAL
    dados_geral, prog_atual = executar_busca_inteligente(
        termos_geral, FONTES_OBRIGATORIAS, data_escolhida, "GERAL", 
        container_status, barra, prog_atual, total_etapas
    )
    
    barra.empty()
    container_status.empty()
    
    # --- VISUALIZAÇÃO ---
    st.success("Busca finalizada!")
    
    dt_ontem = data_escolhida - timedelta(days=1)
    
    texto_copia = f"CLIPPING DIÁRIO - {data_escolhida.strftime('%d/%m/%Y')}\n"
    texto_copia += f"Período: {dt_ontem.strftime('%d/%m')} (08:30) a {data_escolhida.strftime('%d/%m')} (08:30)\n\n"
    
    def formatar_texto(dados, titulo_bloco):
        t = ""
        if dados:
            t += f"=== {titulo_bloco} ===\n" 
            for veiculo in sorted(dados.keys()):
                t += f"{veiculo}\n"
                for n in dados[veiculo]:
                    t += f"{n['titulo']}\n"
                    t += f"{n['link']}\n" 
                t += "\n" 
        else:
            t += f"=== {titulo_bloco} ===\nNenhuma matéria encontrada.\n"
        t += "\n" 
        return t

    texto_copia += formatar_texto(dados_sisema, "MATÉRIAS QUE CITAM O SISEMA")
    texto_copia += "----------------------------------------\n\n"
    texto_copia += formatar_texto(dados_geral, "MATÉRIAS AMBIENTAIS RELEVANTES")

    st.subheader("📋 Texto para Cópia")
    st.text_area("Copie aqui:", value=texto_copia, height=500)
    
    st.markdown("---")
    st.subheader("🔍 Área de Conferência")
    
    def exibir_compacto(dados, titulo_bloco):
        st.markdown(f"##### {titulo_bloco}")
        if not dados:
            st.caption("Nada encontrado.")
            return

        for veiculo in sorted(dados.keys()):
            st.markdown(f"**{veiculo}**")
            for n in dados[veiculo]:
                st.markdown(f"• [{n['titulo']}]({n['link']})") 
            st.write("") 

    col1, col2 = st.columns(2)
    with col1:
        exibir_compacto(dados_sisema, "SISEMA")
    with col2:
        exibir_compacto(dados_geral, "RELEVANTES/CURIOSIDADES")
