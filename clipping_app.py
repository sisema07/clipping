import streamlit as st
import feedparser
import requests
from datetime import datetime, timedelta, timezone, time as dt_time
import re

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Clipping Diário", page_icon="✂️", layout="wide")

st.title("✂️ Clipping Diário")
st.markdown("Monitoramento 08:30 às 08:30")

# --- LISTAS DE AUDITORIA (PENTE FINO) ---

# 1. SISEMA: A matéria SÓ entra se tiver um desses termos no Título ou no Resumo
TERMOS_VALIDACAO_SISEMA = [
    "SISEMA", "SEMAD", "IEF", "FEAM", "IGAM",
    "SISTEMA ESTADUAL DE MEIO AMBIENTE",
    "SECRETARIA DE ESTADO DE MEIO AMBIENTE",
    "INSTITUTO ESTADUAL DE FLORESTAS",
    "FUNDAÇÃO ESTADUAL DO MEIO AMBIENTE",
    "INSTITUTO MINEIRO DE GESTÃO DAS ÁGUAS"
]

# 2. GERAL: A matéria SÓ entra se tiver contexto ambiental (evita curiosidades aleatórias)
CONTEXTO_AMBIENTAL = [
    "MEIO AMBIENTE", "AMBIENTAL", "NATUREZA", "ECOLÓGIC", "SUSTENTÁ",
    "FAUNA", "FLORA", "ANIMAL", "BICHO", "ONÇA", "LOBO", "PEIXE", "RESGATE",
    "RIO", "ÁGUA", "BARRAGEM", "NASCENTE", "CHUVA", "SECA", "HIDRIC",
    "MATA", "FLORESTA", "PARQUE", "UNIDADE DE CONSERVAÇÃO", "APP",
    "POLUIÇÃO", "LIXO", "RESÍDUO", "MINERAÇÃO", "DESMATAMENTO", "QUEIMADA", "INCÊNDIO",
    "CRIME", "MULTA", "INFRAÇÃO", "CLIMA", "AQUECIMENTO"
]

# 3. BLOQUEIO (Remove lixo óbvio)
TERMOS_BLOQUEIO = [
    "PREVISÃO DO TEMPO", "VAI CHOVER", "TEMPO EM", "CLIMA EM", "SOL COM NUVENS",
    "CONCURSO", "EDITAL", "VAGA", "INSCRIÇÃO", "PROCESSO SELETIVO", "GABARITO",
    "PALESTRA", "WORKSHOP", "SEMINÁRIO", "AULA", "ALUNOS", "ESCOLA", "REUNIÃO",
    "COMUNICADO", "CURSO", "FORMATURA", "VESTIBULAR", "ENEM", "ESTÁGIO"
]

# --- SITES OBRIGATÓRIOS ---
FONTES_OBRIGATORIAS = [
    "em.com.br", "otempo.com.br", "hojeemdia.com.br", 
    "g1.globo.com/mg", "g1.globo.com/meio-ambiente", 
    "oeco.org.br", "agenciabrasil.ebc.com.br/meio-ambiente", "conexaoplaneta.com.br"
]

# --- FUNÇÕES DE SUPORTE ---

def resolver_link_final(url_google):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        # Tenta HEAD primeiro (mais rápido)
        r = requests.head(url_google, allow_redirects=True, timeout=5, headers=headers)
        if r.status_code == 200: return r.url
        # Se falhar, GET
        r = requests.get(url_google, allow_redirects=True, timeout=5, headers=headers)
        return r.url
    except:
        return url_google

def limpar_nome_veiculo(nome_cru, titulo_materia):
    if " - " in titulo_materia:
        possivel_nome = titulo_materia.rsplit(" - ", 1)[1].strip()
        if len(possivel_nome) < 40: nome_cru = possivel_nome

    nome = nome_cru.replace("www.", "").replace(".com.br", "").replace(".com", "").replace(".org", "").replace(".gov", "")
    nome = nome.replace("-", " ").replace("_", " ")
    
    mapa = {
        "gazetadevarginha": "Gazeta de Varginha", "diariodoaco": "Diário do Aço",
        "em": "Estado de Minas", "otempo": "O Tempo", "hojeemdia": "Hoje em Dia",
        "tribunademinas": "Tribuna de Minas", "folha": "Folha de S.Paulo",
        "agenciaminas": "Agência Minas", "almg": "Assembleia Legislativa",
        "g1": "Portal G1", "uol": "Portal UOL", "r7": "Portal R7", "youtube": "YouTube",
        "oeco": "O Eco", "conexaoplaneta": "Conexão Planeta", "agenciabrasil": "Agência Brasil"
    }
    
    nome_lower = nome.lower()
    for k, v in mapa.items():
        if k in nome_lower: return v
    return nome.title()

def converter_para_brt(struct_time_utc):
    dt_utc = datetime(*struct_time_utc[:6], tzinfo=timezone.utc)
    return (dt_utc - timedelta(hours=3)).replace(tzinfo=None)

# --- FUNÇÕES DE AUDITORIA (PENTE FINO) ---

def auditoria_sisema(texto_completo):
    """Retorna True apenas se encontrar SIGLAS EXATAS no texto (Título + Resumo)"""
    texto_upper = texto_completo.upper()
    for termo in TERMOS_VALIDACAO_SISEMA:
        # Usa regex word boundary (\b) para evitar falsos positivos (ex: achar IEF dentro de RIEFA)
        # Mas para siglas simples, busca direta é mais segura contra pontuação
        if termo in texto_upper:
            return True
    return False

def auditoria_geral(texto_completo):
    """
    1. Bloqueia termos proibidos (concurso, previsão do tempo).
    2. Obriga ter contexto ambiental (rio, mata, bicho).
    """
    texto_upper = texto_completo.upper()
    
    # 1. Bloqueio
    for ruim in TERMOS_BLOQUEIO:
        if ruim in texto_upper: return False
        
    # 2. Contexto Obrigatório
    tem_contexto = False
    for bom in CONTEXTO_AMBIENTAL:
        if bom in texto_upper:
            tem_contexto = True
            break
            
    return tem_contexto

# --- MOTOR DE BUSCA ---

def executar_busca_auditada(termos_lista, fontes_especificas, data_referencia, tipo_filtro, container_status, barra, prog_atual, total_etapas):
    
    fim_janela = datetime.combine(data_referencia, dt_time(8, 30))
    inicio_janela = fim_janela - timedelta(days=1)
    
    # URLs para varrer
    lista_urls = []
    
    # 1. Google Geral
    for termo in termos_lista:
        prog_atual += 1
        container_status.text(f"Varrendo Web: {termo}...")
        barra.progress(prog_atual / total_etapas)
        
        termo_url = termo.replace(" ", "+")
        q_after = (data_referencia - timedelta(days=2)).strftime("%Y-%m-%d")
        q_before = (data_referencia + timedelta(days=1)).strftime("%Y-%m-%d")
        lista_urls.append(f"https://news.google.com/rss/search?q={termo_url}+after:{q_after}+before:{q_before}&hl=pt-BR&gl=BR&ceid=BR:pt-419")

    # 2. Sites Específicos (Busca Combinada)
    termos_limpos = []
    for t in termos_lista:
        match = re.search(r'"([^"]+)"', t)
        termos_limpos.append(match.group(1) if match else t.split()[0])
    
    query_or = "(" + " OR ".join([f'"{x}"' for x in termos_limpos]) + ")"
    
    for site in fontes_especificas:
        prog_atual += 1
        container_status.text(f"Varrendo Site: {site}...")
        barra.progress(prog_atual / total_etapas)
        
        query_site = f"{query_or} site:{site}"
        q_url = query_site.replace(" ", "+")
        q_after = (data_referencia - timedelta(days=2)).strftime("%Y-%m-%d")
        q_before = (data_referencia + timedelta(days=1)).strftime("%Y-%m-%d")
        lista_urls.append(f"https://news.google.com/rss/search?q={q_url}+after:{q_after}+before:{q_before}&hl=pt-BR&gl=BR&ceid=BR:pt-419")

    # --- PROCESSAMENTO ---
    resultados = {}
    duplicatas = set()

    for url in lista_urls:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            
            # Filtro Horário
            if hasattr(entry, 'published_parsed'):
                try:
                    pub_dt = converter_para_brt(entry.published_parsed)
                    if not (inicio_janela <= pub_dt <= fim_janela): continue
                except: continue

            # Preparação dos dados
            titulo = entry.title
            resumo = entry.summary if 'summary' in entry else ""
            texto_para_auditoria = f"{titulo} {resumo}"
            
            # Limpeza Título
            if " - " in titulo: titulo = titulo.rsplit(" - ", 1)[0]
            
            # --- A AUDITORIA ACONTECE AQUI ---
            passou_na_auditoria = False
            
            if tipo_filtro == "SISEMA":
                # Verifica se as siglas estão no Título OU no Resumo
                if auditoria_sisema(texto_para_auditoria):
                    passou_na_auditoria = True
            
            elif tipo_filtro == "GERAL":
                # Verifica bloqueios E contexto ambiental
                if auditoria_geral(texto_para_auditoria):
                    passou_na_auditoria = True
            
            if passou_na_auditoria:
                chave = titulo.lower()
                if chave not in duplicatas:
                    duplicatas.add(chave)
                    
                    v_raw = entry.source.title if 'source' in entry else "Fonte Desconhecida"
                    veiculo = limpar_nome_veiculo(v_raw, entry.title)
                    link = resolver_link_final(entry.link)
                    
                    if veiculo not in resultados: resultados[veiculo] = []
                    resultados[veiculo].append({'titulo': titulo, 'link': link})

    return resultados, prog_atual

# --- INTERFACE ---

st.info("Busca entre 08:30 de ontem e 08:30 da data selecionada.")
data = st.date_input("Data de Referência:", format="DD/MM/YYYY")

if st.button("🚀 Gerar Clipping Auditado", type="primary"):
    status = st.empty()
    bar = st.progress(0)
    
    # Termos
    excl = "-Bahia -BA -Mato -MT -Acre -AC -Tocantins -TO -Amazonas -AM -Pará -PA"
    t_sisema = [
        f'"Semad" "Minas Gerais" {excl}', f'"IEF" "Minas Gerais" {excl}', 
        f'"Feam" "Minas Gerais" {excl}', f'"Igam" "Minas Gerais" {excl}',
        f'"Sisema" "Minas Gerais" {excl}', f'"Sistema Estadual de Meio Ambiente" {excl}',
        f'"Secretaria de Estado de Meio Ambiente" {excl}'
    ]
    
    t_geral = [
        '"Acidente ambiental" Minas', '"Rompimento" Minas', '"Onça" Minas', 
        '"Lobo guará" Minas', '"Resgate animal" Minas', '"Multa ambiental" Minas',
        '"Crime ambiental" Minas', '"Desmatamento" Minas', '"Poluição" Minas',
        '"Espécie rara" Minas', '"Incêndio" parque Minas', '"Operação" ambiental Minas',
        '"Morte peixes" Minas', '"Capivara" Minas', '"Tamanduá" Minas'
    ]
    
    total = len(t_sisema) + len(FONTES_OBRIGATORIAS) + len(t_geral) + len(FONTES_OBRIGATORIAS)
    prog = 0
    
    d_sisema, prog = executar_busca_auditada(t_sisema, FONTES_OBRIGATORIAS, data, "SISEMA", status, bar, prog, total)
    d_geral, prog = executar_busca_auditada(t_geral, FONTES_OBRIGATORIAS, data, "GERAL", status, bar, prog, total)
    
    bar.empty()
    status.empty()
    
    # Texto
    ontem = data - timedelta(days=1)
    txt = f"CLIPPING DIÁRIO - {data.strftime('%d/%m/%Y')}\n"
    txt += f"Janela: {ontem.strftime('%d/%m')} (08:30) a {data.strftime('%d/%m')} (08:30)\n\n"
    
    def fmt(dados, tit):
        t = f"=== {tit} ===\n"
        if not dados: return t + "Nenhuma matéria encontrada.\n\n"
        for v in sorted(dados.keys()):
            t += f"{v}\n"
            for n in dados[v]:
                t += f"{n['titulo']}\n{n['link']}\n"
            t += "\n"
        return t + "\n"

    txt += fmt(d_sisema, "MATÉRIAS QUE CITAM O SISEMA")
    txt += "----------------------------------------\n\n"
    txt += fmt(d_geral, "RELEVANTES/CURIOSIDADES AMBIENTAIS")
    
    st.subheader("📋 Texto Final")
    st.text_area("Copie aqui:", txt, height=600)
    
    # Conferência
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    def conf(dados, tit):
        st.markdown(f"##### {tit}")
        if not dados: st.caption("Vazio"); return
        for v in sorted(dados.keys()):
            st.markdown(f"**{v}**")
            for n in dados[v]: st.markdown(f"• [{n['titulo']}]({n['link']})")
            
    with col1: conf(d_sisema, "SISEMA")
    with col2: conf(d_geral, "GERAL")
