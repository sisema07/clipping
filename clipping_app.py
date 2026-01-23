import streamlit as st
import feedparser
import time
from datetime import datetime, timedelta, timezone
import re

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Clipping Diário", page_icon="✂️", layout="wide")

st.title("✂️ Clipping Diário - Lista Limpa")
st.markdown("Busca precisa por janela de horário (08:30 às 08:30).")

# --- FUNÇÕES DE SUPORTE ---

def limpar_nome_veiculo(nome_cru, titulo_materia):
    """Padroniza nomes de veículos"""
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

def eh_relevante(titulo):
    """Filtro para notícias gerais (remove editais/concursos)"""
    titulo_lower = titulo.lower()
    palavras_bloqueadas = [
        "concurso", "edital", "vaga", "inscrição", "processo seletivo", 
        "estágio", "gabarito", "prova", "classificação", "convocação",
        "resultado final", "homologação", "vestibular", "enem"
    ]
    for palavra in palavras_bloqueadas:
        if palavra in titulo_lower:
            return False
    return True

def buscar_e_filtrar(termos, data_referencia, aplicar_filtro_palavras=True):
    """
    Busca no Google e filtra manualmente pelo horário (08:30 D-1 até 08:30 D).
    """
    # 1. Definição da Janela de Tempo (Fuso Horário BRT é UTC-3)
    # 08:30 BRT = 11:30 UTC
    # Se a data referência é 21/01
    # Inicio: 20/01 às 11:30 UTC
    # Fim: 21/01 às 11:30 UTC
    
    # Criamos datas 'aware' (com fuso horário UTC) para comparar com o feed do Google
    offset_utc = timedelta(hours=3) # Diferença Brasil -> UTC
    
    # Data final (Dia escolhido às 08:30 BRT -> 11:30 UTC)
    dt_fim = datetime.combine(data_referencia, datetime.min.time()) + timedelta(hours=8, minutes=30) + offset_utc
    dt_fim = dt_fim.replace(tzinfo=timezone.utc)
    
    # Data inicial (Dia anterior às 08:30 BRT -> 11:30 UTC)
    dt_inicio = dt_fim - timedelta(days=1)
    
    noticias_agrupadas = {} # Dicionário: {'Nome Veículo': [{'titulo': x, 'link': y}]}
    urls_vistas = set()
    
    for termo in termos:
        termo_url = termo.replace(" ", "+")
        
        # Pedimos ao Google um intervalo um pouco maior para garantir que nada fique de fora
        # after:DiaAnterior before:DiaSeguinte
        q_after = (data_referencia - timedelta(days=2)).strftime("%Y-%m-%d")
        q_before = (data_referencia + timedelta(days=1)).strftime("%Y-%m-%d")
        
        rss_url = f"https://news.google.com/rss/search?q={termo_url}+after:{q_after}+before:{q_before}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        
        feed = feedparser.parse(rss_url)
        
        for entry in feed.entries:
            # Parse da data de publicação do RSS (struct_time -> datetime UTC)
            if hasattr(entry, 'published_parsed'):
                try:
                    pub_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    
                    # O GRANDE FILTRO DE HORÁRIO
                    if not (dt_inicio <= pub_dt <= dt_fim):
                        continue # Pula se estiver fora do horário das 08:30 as 08:30
                        
                except:
                    continue # Se não tiver data, ignora
            
            titulo_completo = entry.title
            link = entry.link
            
            if " - " in titulo_completo:
                titulo_limpo = titulo_completo.rsplit(" - ", 1)[0]
            else:
                titulo_limpo = titulo_completo

            if aplicar_filtro_palavras and not eh_relevante(titulo_limpo):
                continue

            chave = titulo_limpo.lower()
            if chave not in urls_vistas:
                urls_vistas.add(chave)
                
                veiculo_sujo = entry.source.title if 'source' in entry else "Fonte Desconhecida"
                veiculo_limpo = limpar_nome_veiculo(veiculo_sujo, titulo_completo)
                
                # Agrupamento por veículo
                if veiculo_limpo not in noticias_agrupadas:
                    noticias_agrupadas[veiculo_limpo] = []
                
                noticias_agrupadas[veiculo_limpo].append({
                    "titulo": titulo_limpo,
                    "link": link
                })
                
    return noticias_agrupadas

# --- INTERFACE ---

data_escolhida = st.date_input("Data do Clipping (Considera das 08:30 de ontem até as 08:30 desta data):", format="DD/MM/YYYY")

if st.button("🚀 Gerar Lista Limpa", type="primary"):
    with st.spinner("Buscando notícias e filtrando horário exato..."):
        
        # 1. SISEMA
        termos_sisema = [
            '"Semad" Minas Gerais', '"IEF" Minas Gerais', 
            '"Feam" Minas Gerais', '"Igam" Minas Gerais',
            '"Secretaria de Meio Ambiente" Minas Gerais',
            '"Sistema Estadual de Meio Ambiente"'
        ]
        dados_sisema = buscar_e_filtrar(termos_sisema, data_escolhida, aplicar_filtro_palavras=False)
        
        # 2. GERAL
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
        dados_geral = buscar_e_filtrar(termos_geral, data_escolhida, aplicar_filtro_palavras=True)
        
        # --- GERAÇÃO DO TEXTO ---
        # Data formatada para exibição
        dt_ontem = data_escolhida - timedelta(days=1)
        info_periodo = f"(De {dt_ontem.strftime('%d/%m')} às 08:30 até {data_escolhida.strftime('%d/%m')} às 08:30)"
        
        texto_final = ""
        
        def formatar_bloco(titulo_bloco, dados):
            txt = ""
            if dados:
                txt += f"{titulo_bloco}\n\n"
                # Ordena os veículos alfabeticamente
                for veiculo in sorted(dados.keys()):
                    txt += f"{veiculo}\n"
                    # Lista as matérias desse veículo
                    for noticia in dados[veiculo]:
                        txt += f"{noticia['titulo']}\n"
                        txt += f"{noticia['link']}\n"
                    txt += "\n" # Espaço entre veículos
            return txt

        texto_final += f"CLIPPING AMBIENTAL - {data_escolhida.strftime('%d/%m/%Y')}\n{info_periodo}\n\n"
        
        texto_final += formatar_bloco("MATÉRIAS QUE CITAM O SISEMA", dados_sisema)
        texto_final += "----------------------------------------\n\n"
        texto_final += formatar_bloco("OUTRAS MATÉRIAS RELEVANTES", dados_geral)
        
        st.success("Lista gerada!")
        st.text_area("Copie o conteúdo abaixo:", value=texto_final, height=600)
