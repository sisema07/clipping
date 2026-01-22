import streamlit as st
import feedparser
import requests
import time
from datetime import datetime, timedelta
import re

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gerador de Clipping", page_icon="📰", layout="wide")

st.title("📰 Gerador de Clipping - SISEMA & Geral")
st.markdown("Monitoramento inteligente com filtro de relevância (apenas para notícias gerais) e limpeza de fontes.")

# --- FUNÇÕES DE SUPORTE ---

def encurtar_link(url_longa):
    """Encurta links para o WhatsApp"""
    try:
        api_url = f"https://is.gd/create.php?format=simple&url={url_longa}"
        response = requests.get(api_url, timeout=5)
        if response.status_code == 200 and "is.gd" in response.text:
            return response.text.strip()
    except:
        pass
    return url_longa

def limpar_nome_veiculo(nome_cru, titulo_materia):
    """
    Transforma 'ofator.com.br' em 'O Fator' e remove sujeira.
    """
    if " - " in titulo_materia:
        possivel_nome = titulo_materia.rsplit(" - ", 1)[1].strip()
        if len(possivel_nome) < 30:
            nome_cru = possivel_nome

    nome = nome_cru.replace("www.", "").replace(".com.br", "").replace(".com", "").replace(".org", "").replace(".gov", "")
    nome = nome.replace("-", " ").replace("_", " ")
    
    nome_lower = nome.lower()
    if "youtube" in nome_lower: return "YouTube"
    if "g1" in nome_lower: return "Portal G1"
    if "uol" in nome_lower: return "Portal UOL"
    if "em.com" in nome_lower or "estado de minas" in nome_lower: return "Jornal Estado de Minas"
    if "otempo" in nome_lower: return "Jornal O Tempo"
    if "folha" in nome_lower: return "Folha de S.Paulo"
    if "ofator" in nome_lower: return "Portal O Fator"
    
    return nome.title()

def categorizar_veiculo(nome_veiculo):
    nome = nome_veiculo.lower()
    if "youtube" in nome or "tv" in nome or "canal" in nome: return "YOUTUBE"
    if any(x in nome for x in ["jornal", "estado", "folha", "tempo", "tribuna", "diário", "gazeta", "hoje em dia"]): return "JORNAIS"
    if "revista" in nome: return "REVISTAS"
    return "PORTAIS"

def eh_relevante(titulo):
    """
    Filtro 'Anti-Ruído' para notícias GERAIS.
    Bloqueia concursos e editais genéricos.
    """
    titulo_lower = titulo.lower()
    palavras_bloqueadas = [
        "concurso", "edital", "vaga", "inscrição", "processo seletivo", 
        "estágio", "gabarito", "prova", "classificação", "convocação",
        "resultado final", "homologação", "vestibular", "enem", "curso gratuito",
        "workshop", "palestra"
    ]
    
    for palavra in palavras_bloqueadas:
        if palavra in titulo_lower:
            return False
    return True

def buscar_noticias_google(termos, data_especifica=None, aplicar_filtro=True):
    """
    O parâmetro 'aplicar_filtro' define se vamos ignorar editais/concursos ou não.
    """
    noticias = []
    urls_vistas = set()
    
    for termo in termos:
        termo_url = termo.replace(" ", "+")
        
        if data_especifica:
            data_formatada = data_especifica.strftime("%Y-%m-%d")
            data_seguinte = (data_especifica + timedelta(days=1)).strftime("%Y-%m-%d")
            query_time = f"after:{data_formatada}+before:{data_seguinte}"
        else:
            query_time = "when:1d"
            
        rss_url = f"https://news.google.com/rss/search?q={termo_url}+{query_time}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        
        feed = feedparser.parse(rss_url)
        
        for entry in feed.entries:
            titulo_completo = entry.title
            link = entry.link
            
            if " - " in titulo_completo:
                titulo_limpo = titulo_completo.rsplit(" - ", 1)[0]
            else:
                titulo_limpo = titulo_completo

            # --- AQUI ESTÁ A CORREÇÃO ---
            # Só aplicamos o filtro se for solicitado (Geral).
            # Se for SISEMA (aplicar_filtro=False), passa tudo.
            if aplicar_filtro and not eh_relevante(titulo_limpo):
                continue

            chave = titulo_limpo.lower()
            if chave not in urls_vistas:
                urls_vistas.add(chave)
                
                veiculo_sujo = entry.source.title if 'source' in entry else "Fonte Desconhecida"
                veiculo_limpo = limpar_nome_veiculo(veiculo_sujo, titulo_completo)
                
                categoria = categorizar_veiculo(veiculo_limpo)
                
                noticias.append({
                    "titulo": titulo_limpo,
                    "link_original": link,
                    "link_curto": link, 
                    "veiculo": veiculo_limpo,
                    "categoria": categoria
                })
                
    return noticias

# --- INTERFACE ---

modo_busca = st.radio("Período da Busca:", ["Últimas 24 horas", "Data Específica"], horizontal=True)

data_escolhida = None
if modo_busca == "Data Específica":
    data_escolhida = st.date_input("Selecione a data:", format="DD/MM/YYYY")

if st.button("🚀 Iniciar Busca", type="primary"):
    with st.spinner("Minerando notícias..."):
        
        # 1. BUSCA SISEMA (SEM FILTRO)
        # Traz tudo: editais, concursos, notícias, polêmicas.
        termos_sisema = [
            '"Semad" Minas Gerais', '"IEF" Minas Gerais', 
            '"Feam" Minas Gerais', '"Igam" Minas Gerais',
            '"Secretaria de Meio Ambiente" Minas Gerais',
            '"Sistema Estadual de Meio Ambiente"'
        ]
        # aplicar_filtro=False -> GARANTE QUE NÃO BLOQUEIA NADA DO SISEMA
        raw_sisema = buscar_noticias_google(termos_sisema, data_escolhida, aplicar_filtro=False)
        
        # 2. BUSCA GERAL (COM FILTRO)
        # Bloqueia lixo: concursos de prefeitura, editais de escola, etc.
        termos_geral = [
            '"Crime Ambiental" Minas Gerais',
            '"Desmatamento" Minas Gerais',
            '"Incêndio" parque Minas Gerais',
            '"Poluição" rio Minas Gerais',
            '"Barragem" risco Minas Gerais',
            '"Multa ambiental" Minas Gerais',
            '"Licenciamento ambiental" Minas Gerais',
            '"Mudanças Climáticas" governo Minas',
            '"Crise hídrica" Minas Gerais'
        ]
        # aplicar_filtro=True -> GARANTE LIMPEZA NO GERAL
        raw_geral = buscar_noticias_google(termos_geral, data_escolhida, aplicar_filtro=True)
        
        total_links = len(raw_sisema) + len(raw_geral)
        progresso = st.progress(0)
        status = st.empty()
        
        estado = {'contador': 0}
        
        def processar_listas(lista_crua):
            organizado = {"JORNAIS": [], "PORTAIS": [], "REVISTAS": [], "YOUTUBE": []}
            for item in lista_crua:
                estado['contador'] += 1
                status.text(f"Processando {estado['contador']}/{total_links}: {item['veiculo']}")
                progresso.progress(estado['contador'] / (total_links + 1) if total_links > 0 else 0)
                
                item['link_curto'] = encurtar_link(item['link_original'])
                
                if item['categoria'] in organizado:
                    organizado[item['categoria']].append(item)
                else:
                    organizado["PORTAIS"].append(item)
            return organizado

        dados_sisema = processar_listas(raw_sisema)
        dados_geral = processar_listas(raw_geral)
        
        progresso.empty()
        status.empty()
        
        if data_escolhida:
            data_texto = data_escolhida.strftime("%d.%m.%Y")
        else:
            data_texto = datetime.now().strftime("%d.%m.%Y")

        # --- GERAÇÃO WHATSAPP ---
        texto_zap = f"*Clipping Meio Ambiente: {data_texto}*\n\n"
        
        def montar_secao_zap(titulo_secao, dados):
            txt = ""
            if any(dados.values()):
                txt += f"*{titulo_secao}*\n\n"
                for cat in ["JORNAIS", "PORTAIS", "REVISTAS", "YOUTUBE"]:
                    if dados[cat]:
                        txt += f"*{cat}*\n\n"
                        for n in dados[cat]:
                            txt += f"*{n['veiculo']}*\n" 
                            txt += f"{n['titulo']}\n"
                            txt += f"{n['link_curto']}\n\n"
            return txt

        texto_zap += montar_secao_zap("MATÉRIAS QUE CITAM O SISEMA", dados_sisema)
        texto_zap += montar_secao_zap("OUTRAS MATÉRIAS RELEVANTES", dados_geral)
        texto_zap += "_Clipping direcionado exclusivamente para servidores, sendo proibida a divulgação para outras pessoas_"

        # --- GERAÇÃO HTML ---
        texto_html = f"<p><strong><u>Clipping Meio Ambiente: {data_texto}</u></strong></p>\n<p> </p>\n"
        
        def montar_secao_html(titulo_secao, dados):
            html = ""
            if any(dados.values()):
                html += f"<p><span style=\"text-decoration: underline;\"><strong>{titulo_secao}</strong></span></p>\n<p> </p>\n"
                for cat in ["JORNAIS", "PORTAIS", "REVISTAS", "YOUTUBE"]:
                    if dados[cat]:
                        html += f"<p><span style=\"text-decoration: underline;\"><strong>{cat}</strong></span></p>\n<p> </p>\n"
                        for i, n in enumerate(dados[cat]):
                            html += f"<p><strong>{n['veiculo']}</strong></p>\n"
                            html += f"<p><a href=\"{n['link_original']}\">{n['titulo']}</a></p>\n"
                            if i < len(dados[cat]) - 1:
                                html += "<p> </p>\n"
                        html += "<p> </p>\n"
            return html

        texto_html += montar_secao_html("MATÉRIAS QUE CITAM O SISEMA", dados_sisema)
        texto_html += montar_secao_html("OUTRAS MATÉRIAS RELEVANTES", dados_geral)
        texto_html += "<p><em><strong>Clipping direcionado exclusivamente para servidores, sendo proibida a divulgação para outras pessoas</strong></em></p>"

        # --- EXIBIÇÃO ---
        st.success(f"Busca finalizada! {len(raw_sisema)} matérias Sisema e {len(raw_geral)} gerais.")
        
        tab1, tab2 = st.tabs(["📱 WhatsApp (Links Curtos)", "💻 HTML (Links Originais)"])
        
        with tab1:
            st.code(texto_zap, language="markdown")
            st.caption("Ideal para copiar e colar no grupo.")
            
        with tab2:
            st.code(texto_html, language="html")
            st.caption("Ideal para colar na ferramenta de e-mail ou site.")
