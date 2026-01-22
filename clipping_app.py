import streamlit as st
import feedparser
import requests
import time
from datetime import datetime
import re

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gerador de Clipping", page_icon="📰", layout="wide")

st.title("📰 Gerador de Clipping - SISEMA & Geral")
st.markdown("Busca automática de notícias (últimas 24h) formatada para o padrão oficial.")

# --- FUNÇÕES DE SUPORTE ---

def encurtar_link(url_longa):
    """Encurta links usando is.gd para economizar caracteres no Zap"""
    try:
        # O Google News usa redirecionamentos. O is.gd resolve bem.
        api_url = f"https://is.gd/create.php?format=simple&url={url_longa}"
        response = requests.get(api_url, timeout=5)
        if response.status_code == 200 and "is.gd" in response.text:
            return response.text.strip()
    except:
        pass
    return url_longa

def categorizar_veiculo(nome_veiculo):
    """Tenta adivinhar a categoria do veículo baseado no nome"""
    nome = nome_veiculo.lower()
    
    if "youtube" in nome or "canal" in nome or "tv" in nome:
        return "YOUTUBE"
    elif any(x in nome for x in ["jornal", "estado", "folha", "tempo", "tribuna", "diário", "gazeta", "hoje em dia"]):
        return "JORNAIS"
    elif "revista" in nome:
        return "REVISTAS"
    else:
        return "PORTAIS" # Padrão para blogs, sites de notícias, G1, UOL, etc.

def buscar_noticias_google(termos):
    noticias = []
    urls_vistas = set()
    
    for termo in termos:
        # Busca no Google News RSS (Brasil, pt-BR, últimas 24h 'when:1d')
        termo_url = termo.replace(" ", "+")
        rss_url = f"https://news.google.com/rss/search?q={termo_url}+when:1d&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        
        feed = feedparser.parse(rss_url)
        
        for entry in feed.entries:
            titulo = entry.title
            link = entry.link
            veiculo = entry.source.title if 'source' in entry else "Fonte Desconhecida"
            
            # Limpa o título (Remove o " - Nome do Jornal" que o Google adiciona no fim)
            if " - " in titulo:
                partes = titulo.rsplit(" - ", 1)
                titulo_limpo = partes[0]
                # Às vezes o veículo vem no título, atualizamos se estiver genérico
                if veiculo == "Fonte Desconhecida" and len(partes) > 1:
                    veiculo = partes[1]
            else:
                titulo_limpo = titulo

            # Evita duplicatas (mesma matéria aparecendo em buscas diferentes)
            chave = titulo_limpo.lower()
            if chave not in urls_vistas:
                urls_vistas.add(chave)
                
                categoria = categorizar_veiculo(veiculo)
                
                noticias.append({
                    "titulo": titulo_limpo,
                    "link": link,
                    "veiculo": veiculo,
                    "categoria": categoria
                })
                
    return noticias

# --- INTERFACE ---

col1, col2 = st.columns(2)
with col1:
    if st.button("🚀 Iniciar Busca e Formatação", type="primary"):
        with st.spinner("Varrendo a internet... Isso pode levar alguns segundos..."):
            
            # 1. BUSCA - SISEMA (Órgãos Específicos)
            termos_sisema = [
                '"Semad" Minas Gerais', 
                '"IEF" Minas Gerais', 
                '"Feam" Minas Gerais', 
                '"Igam" Minas Gerais',
                '"Secretaria de Meio Ambiente" Minas Gerais',
                '"Sistema Estadual de Meio Ambiente"'
            ]
            raw_sisema = buscar_noticias_google(termos_sisema)
            
            # 2. BUSCA - GERAL (Temas Ambientais)
            # Focamos em Minas Gerais para relevância, mas você pode tirar o "Minas Gerais" para pegar Brasil todo
            termos_geral = [
                '"Meio Ambiente" Minas Gerais',
                '"Desmatamento" Minas Gerais',
                '"Recursos Hídricos" Minas Gerais',
                '"Mineração" Meio Ambiente Minas',
                '"Sustentabilidade" Minas Gerais',
                '"Mudanças Climáticas" Minas Gerais'
            ]
            raw_geral = buscar_noticias_google(termos_geral)
            
            # --- PROCESSAMENTO E ENCURTAMENTO ---
            # Barra de progresso para o encurtamento (que é a parte lenta)
            total_links = len(raw_sisema) + len(raw_geral)
            progresso = st.progress(0)
            contador = 0
            
            status_text = st.empty()
            
            # Função interna para organizar os dados
            def processar_lista(lista_crua):
                nonlocal contador
                organizado = {"JORNAIS": [], "PORTAIS": [], "REVISTAS": [], "YOUTUBE": []}
                
                for item in lista_crua:
                    contador += 1
                    status_text.text(f"Encurtando link {contador}/{total_links}: {item['veiculo']}")
                    progresso.progress(contador / (total_links + 1) if total_links > 0 else 0)
                    
                    item['link_curto'] = encurtar_link(item['link'])
                    
                    if item['categoria'] in organizado:
                        organizado[item['categoria']].append(item)
                    else:
                        organizado["PORTAIS"].append(item) # Fallback
                return organizado

            dados_sisema = processar_lista(raw_sisema)
            dados_geral = processar_lista(raw_geral)
            
            progresso.empty()
            status_text.empty()
            
            # --- MONTAGEM DO TEXTO FINAL (Padrão WhatsApp) ---
            data_hoje = datetime.now().strftime("%d.%m.%Y")
            
            # Cabeçalho
            texto_zap = f"*Clipping Meio Ambiente: {data_hoje}*\n\n"
            
            # --- SEÇÃO 1: SISEMA ---
            if any(dados_sisema.values()):
                texto_zap += "*MATÉRIAS QUE CITAM O SISEMA*\n\n"
                
                for cat in ["JORNAIS", "PORTAIS", "REVISTAS", "YOUTUBE"]:
                    if dados_sisema[cat]:
                        texto_zap += f"*{cat}*\n\n"
                        for noticia in dados_sisema[cat]:
                            texto_zap += f"*{noticia['veiculo']}*\n"
                            texto_zap += f"{noticia['titulo']}\n"
                            texto_zap += f"{noticia['link_curto']}\n\n"

            # --- SEÇÃO 2: GERAL ---
            if any(dados_geral.values()):
                texto_zap += "*OUTRAS MATÉRIAS RELEVANTES*\n\n"
                
                for cat in ["JORNAIS", "PORTAIS", "REVISTAS", "YOUTUBE"]:
                    if dados_geral[cat]:
                        texto_zap += f"*{cat}*\n\n"
                        for noticia in dados_geral[cat]:
                            texto_zap += f"*{noticia['veiculo']}*\n"
                            texto_zap += f"{noticia['titulo']}\n"
                            texto_zap += f"{noticia['link_curto']}\n\n"
            
            # Rodapé Obrigatório
            rodape = "_Clipping direcionado exclusivamente para servidores, sendo proibida a divulgação para outras pessoas_"
            texto_zap += f"{rodape}"

            # --- EXIBIÇÃO ---
            st.success("Clipping gerado com sucesso!")
            
            st.subheader("Resultado Formatado (WhatsApp)")
            st.code(texto_zap, language="markdown")
            st.caption("Copie o texto acima e cole no WhatsApp. Os negritos e itálicos já estão configurados.")

with col2:
    st.info("ℹ️ Este sistema busca notícias no Google News (últimas 24h), categoriza automaticamente em Jornais/Portais e aplica a formatação padrão do Sisema.")
