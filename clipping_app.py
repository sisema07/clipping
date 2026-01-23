import streamlit as st
import feedparser
import time
from datetime import datetime, timedelta, timezone, time as dt_time
import re

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Clipping Diário", page_icon="✂️", layout="wide")

st.title("✂️ Clipping Diário - Lista Limpa")
st.markdown("Busca exata: Das 08:30 do dia anterior às 08:30 do dia selecionado.")

# --- FUNÇÕES DE SUPORTE ---

def limpar_nome_veiculo(nome_cru, titulo_materia):
    """Padroniza nomes de veículos"""
    # Tenta pegar o nome limpo que geralmente vem após o hífen no título do Google
    if " - " in titulo_materia:
        possivel_nome = titulo_materia.rsplit(" - ", 1)[1].strip()
        if len(possivel_nome) < 40: # Tamanho seguro para evitar pegar títulos cortados
            nome_cru = possivel_nome

    # Limpeza básica de URL
    nome = nome_cru.replace("www.", "").replace(".com.br", "").replace(".com", "").replace(".org", "").replace(".gov", "")
    nome = nome.replace("-", " ").replace("_", " ")
    
    # Padronização de nomes comuns
    nome_lower = nome.lower()
    if "youtube" in nome_lower: return "YouTube"
    if "g1" in nome_lower: return "Portal G1"
    if "uol" in nome_lower: return "Portal UOL"
    if "em.com" in nome_lower or "estado de minas" in nome_lower: return "Jornal Estado de Minas"
    if "otempo" in nome_lower: return "Jornal O Tempo"
    if "folha" in nome_lower: return "Folha de S.Paulo"
    if "ofator" in nome_lower: return "Portal O Fator"
    if "agência minas" in nome_lower: return "Agência Minas"
    
    return nome.title()

def eh_relevante(titulo):
    """Filtro para remover editais e concursos da lista GERAL"""
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

def converter_para_brt(struct_time_utc):
    """
    Converte o horário do Google (UTC) para o horário do Brasil (UTC-3).
    Isso é essencial para o filtro das 08:30 funcionar.
    """
    # Cria um objeto datetime com fuso UTC
    dt_utc = datetime(*struct_time_utc[:6], tzinfo=timezone.utc)
    # Converte para BRT (UTC-3)
    dt_brt = dt_utc - timedelta(hours=3)
    # Retorna "naive" (sem info de fuso) para facilitar comparação simples
    return dt_brt.replace(tzinfo=None)

def buscar_e_filtrar(termos, data_referencia, aplicar_filtro_palavras=True):
    # 1. DEFINIÇÃO DA JANELA DE TEMPO (BRT)
    # Se a data escolhida for dia 17:
    # Inicio: Dia 16 às 08:30
    # Fim: Dia 17 às 08:30
    
    fim_janela = datetime.combine(data_referencia, dt_time(8, 30))
    inicio_janela = fim_janela - timedelta(days=1)
    
    noticias_agrupadas = {} 
    urls_vistas = set()
    
    for termo in termos:
        termo_url = termo.replace(" ", "+")
        
        # Pedimos ao Google um intervalo maior (2 dias antes e 1 depois) para garantir
        q_after = (data_referencia - timedelta(days=2)).strftime("%Y-%m-%d")
        q_before = (data_referencia + timedelta(days=1)).strftime("%Y-%m-%d")
        
        rss_url = f"https://news.google.com/rss/search?q={termo_url}+after:{q_after}+before:{q_before}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        
        feed = feedparser.parse(rss_url)
        
        for entry in feed.entries:
            if hasattr(entry, 'published_parsed'):
                try:
                    # Converte hora da notícia para horário do Brasil
                    pub_dt_brt = converter_para_brt(entry.published_parsed)
                    
                    # FILTRO RIGOROSO DE HORÁRIO
                    # Se a notícia for de 16h do dia da referência, ela será maior que o fim_janela (08:30) e será ignorada.
                    if not (inicio_janela <= pub_dt_brt <= fim_janela):
                        continue 
                        
                except:
                    continue 
            
            titulo_completo = entry.title
            link = entry.link
            
            # Limpeza do título
            if " - " in titulo_completo:
                titulo_limpo = titulo_completo.rsplit(" - ", 1)[0]
            else:
                titulo_limpo = titulo_completo

            # Filtro de palavras (apenas para Geral)
            if aplicar_filtro_palavras and not eh_relevante(titulo_limpo):
                continue

            # Evita duplicatas
            chave = titulo_limpo.lower()
            if chave not in urls_vistas:
                urls_vistas.add(chave)
                
                veiculo_sujo = entry.source.title if 'source' in entry else "Fonte Desconhecida"
                veiculo_limpo = limpar_nome_veiculo(veiculo_sujo, titulo_completo)
                
                if veiculo_limpo not in noticias_agrupadas:
                    noticias_agrupadas[veiculo_limpo] = []
                
                noticias_agrupadas[veiculo_limpo].append({
                    "titulo": titulo_limpo,
                    "link": link
                })
                
    return noticias_agrupadas

# --- INTERFACE ---

st.info("O sistema buscará notícias publicadas entre as 08:30 do dia anterior e as 08:30 da data selecionada abaixo.")
data_escolhida = st.date_input("Selecione a Data de Referência:", format="DD/MM/YYYY")

if st.button("🚀 Gerar Lista Limpa", type="primary"):
    with st.spinner("Filtrando notícias pelo horário exato..."):
        
        # 1. SISEMA - Termos Corrigidos para evitar prefeituras
        termos_sisema = [
            '"Semad" Minas Gerais', 
            '"IEF" Minas Gerais', 
            '"Feam" Minas Gerais', 
            '"Igam" Minas Gerais',
            # Adicionado "de Estado" para evitar Secretaria Municipal
            '"Secretaria de Estado de Meio Ambiente" Minas Gerais', 
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
        
        # --- MONTAGEM DO TEXTO (SEM FORMATAÇÃO WHATSAPP) ---
        dt_ontem = data_escolhida - timedelta(days=1)
        
        texto_final = f"CLIPPING AMBIENTAL - {data_escolhida.strftime('%d/%m/%Y')}\n"
        texto_final += f"Janela: {dt_ontem.strftime('%d/%m')} (08:30) até {data_escolhida.strftime('%d/%m')} (08:30)\n\n"
        
        def formatar_lista_limpa(titulo_bloco, dados):
            txt = ""
            if dados:
                txt += f"=== {titulo_bloco} ===\n\n"
                # Ordena Veículos
                for veiculo in sorted(dados.keys()):
                    txt += f"{veiculo}\n"
                    # Lista Matérias
                    for noticia in dados[veiculo]:
                        txt += f"{noticia['titulo']}\n"
                        txt += f"{noticia['link']}\n"
                    txt += "\n" # Espaço extra entre veículos
            return txt

        if dados_sisema:
            texto_final += formatar_lista_limpa("MATÉRIAS QUE CITAM O SISEMA", dados_sisema)
        else:
            texto_final += "=== MATÉRIAS QUE CITAM O SISEMA ===\nNenhuma matéria encontrada neste período.\n\n"

        texto_final += "----------------------------------------\n\n"
        
        if dados_geral:
            texto_final += formatar_lista_limpa("OUTRAS MATÉRIAS RELEVANTES", dados_geral)
        else:
            texto_final += "=== OUTRAS MATÉRIAS RELEVANTES ===\nNenhuma matéria encontrada neste período.\n"
        
        st.success("Lista gerada com sucesso!")
        st.text_area("Resultado (Copie e edite conforme necessário):", value=texto_final, height=700)
