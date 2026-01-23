import streamlit as st
import feedparser
import requests
from datetime import datetime, timedelta, timezone, time as dt_time
import re

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Clipping Diário", page_icon="✂️", layout="wide")

st.title("✂️ Clipping Diário - Link Real & MG")
st.markdown("Filtro: 08:30 às 08:30 | Exclusivo MG | Links Originais")

# --- FUNÇÕES DE SUPORTE ---

def resolver_link_final(url_google):
    """
    Tenta acessar o link do Google para descobrir qual é o link real (Original).
    """
    try:
        # User-Agent para parecer um navegador real e o site aceitar a conexão
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        # Faz uma requisição apenas para ver o cabeçalho (allow_redirects=True segue o link)
        response = requests.head(url_google, allow_redirects=True, timeout=5, headers=headers)
        
        # Se falhar no HEAD, tenta GET rápido
        if response.status_code != 200:
             response = requests.get(url_google, allow_redirects=True, timeout=5, headers=headers)
             
        return response.url
    except:
        # Se der erro ou demorar demais, devolve o link do Google mesmo (melhor que nada)
        return url_google

def limpar_nome_veiculo(nome_cru, titulo_materia):
    """Melhora a formatação dos nomes dos veículos"""
    
    # 1. Tenta pegar do título do Google (Geralmente é mais bonito: "Gazeta de Varginha")
    if " - " in titulo_materia:
        possivel_nome = titulo_materia.rsplit(" - ", 1)[1].strip()
        if len(possivel_nome) < 40:
            return possivel_nome # Retorna direto se achar no título

    # 2. Se não achar, tenta limpar a URL/Nome cru
    nome = nome_cru.replace("www.", "").replace(".com.br", "").replace(".com", "").replace(".org", "").replace(".gov", "")
    nome = nome.replace("-", " ").replace("_", " ")
    
    # Lista de Correções Manuais (Adicione aqui os que sempre aparecem feios)
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
        "youtube": "YouTube"
    }
    
    nome_lower = nome.lower()
    
    # Verifica se o nome está na lista de correções
    for chave, valor in mapa_correcao.items():
        if chave in nome_lower:
            return valor
            
    return nome.title()

def eh_relevante(titulo):
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
    dt_utc = datetime(*struct_time_utc[:6], tzinfo=timezone.utc)
    dt_brt = dt_utc - timedelta(hours=3)
    return dt_brt.replace(tzinfo=None)

def buscar_e_filtrar(termos, data_referencia, aplicar_filtro_palavras=True):
    fim_janela = datetime.combine(data_referencia, dt_time(8, 30))
    inicio_janela = fim_janela - timedelta(days=1)
    
    noticias_agrupadas = {} 
    urls_vistas = set()
    
    # Barra de progresso visual (pois resolver links demora)
    st.write("⏳ Processando fontes e resolvendo links originais...")
    barra = st.progress(0)
    
    for i, termo in enumerate(termos):
        barra.progress((i) / len(termos))
        
        termo_url = termo.replace(" ", "+")
        q_after = (data_referencia - timedelta(days=2)).strftime("%Y-%m-%d")
        q_before = (data_referencia + timedelta(days=1)).strftime("%Y-%m-%d")
        
        rss_url = f"https://news.google.com/rss/search?q={termo_url}+after:{q_after}+before:{q_before}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        
        feed = feedparser.parse(rss_url)
        
        for entry in feed.entries:
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

            if aplicar_filtro_palavras and not eh_relevante(titulo_limpo):
                continue

            chave = titulo_limpo.lower()
            if chave not in urls_vistas:
                urls_vistas.add(chave)
                
                veiculo_sujo = entry.source.title if 'source' in entry else "Fonte Desconhecida"
                veiculo_limpo = limpar_nome_veiculo(veiculo_sujo, titulo_completo)
                
                # --- AQUI ESTÁ A MÁGICA DO LINK REAL ---
                # Resolvemos o link original agora
                link_real = resolver_link_final(link_google)
                
                if veiculo_limpo not in noticias_agrupadas:
                    noticias_agrupadas[veiculo_limpo] = []
                
                noticias_agrupadas[veiculo_limpo].append({
                    "titulo": titulo_limpo,
                    "link": link_real # Agora salvamos o link resolvido
                })
    
    barra.empty()            
    return noticias_agrupadas

# --- INTERFACE ---

st.info("O sistema buscará notícias entre 08:30 de ontem e 08:30 de hoje (data selecionada).")
data_escolhida = st.date_input("Selecione a Data de Referência:", format="DD/MM/YYYY")

if st.button("🚀 Gerar Clipping com Links Reais", type="primary"):
    
    # 1. SISEMA - Estratégia de Termos Negativos (-)
    # Adicionamos -Bahia -BA -Mato -MT -Acre -Tocantins para excluir outras Semas
    exclusoes = "-Bahia -BA -Mato -MT -Acre -AC -Tocantins -TO -Amazonas -AM -Pará -PA"
    
    termos_sisema = [
        f'"Semad" "Minas Gerais" {exclusoes}', 
        f'"IEF" "Minas Gerais" {exclusoes}', 
        f'"Feam" "Minas Gerais" {exclusoes}', 
        f'"Igam" "Minas Gerais" {exclusoes}',
        f'"Secretaria de Estado de Meio Ambiente e Desenvolvimento Sustentável" {exclusoes}',
        f'"Sistema Estadual de Meio Ambiente" "Minas Gerais" {exclusoes}'
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
    
    # --- VISUALIZAÇÃO ---
    st.success("Busca finalizada!")
    
    # Preparação do Texto para Copiar
    dt_ontem = data_escolhida - timedelta(days=1)
    texto_copia = f"CLIPPING AMBIENTAL - {data_escolhida.strftime('%d/%m/%Y')}\n"
    texto_copia += f"Janela: {dt_ontem.strftime('%d/%m')} (08:30) até {data_escolhida.strftime('%d/%m')} (08:30)\n\n"
    
    def formatar_texto(dados, titulo_bloco):
        t = ""
        if dados:
            t += f"=== {titulo_bloco} ===\n\n"
            for veiculo in sorted(dados.keys()):
                t += f"{veiculo}\n"
                for n in dados[veiculo]:
                    t += f"{n['titulo']}\n"
                    t += f"{n['link']}\n"
                t += "\n"
        else:
            t += f"=== {titulo_bloco} ===\nNenhuma matéria encontrada.\n\n"
        return t

    texto_copia += formatar_texto(dados_sisema, "MATÉRIAS QUE CITAM O SISEMA")
    texto_copia += "----------------------------------------\n\n"
    texto_copia += formatar_texto(dados_geral, "OUTRAS MATÉRIAS RELEVANTES")

    # Exibe a caixa para copiar
    st.subheader("📋 Área de Cópia (Texto Puro)")
    st.text_area("Copie aqui:", value=texto_copia, height=400)
    
    # Exibe a Área de Conferência (Links Clicáveis)
    st.markdown("---")
    st.subheader("🔍 Área de Conferência (Links Clicáveis)")
    st.markdown("Use esta área para clicar e validar as notícias antes de copiar o texto acima.")
    
    def exibir_clicavel(dados, titulo_bloco):
        st.markdown(f"### {titulo_bloco}")
        if not dados:
            st.markdown("_Nenhuma matéria encontrada._")
            return

        for veiculo in sorted(dados.keys()):
            # Exibe o veículo em negrito
            st.markdown(f"**{veiculo}**")
            for n in dados[veiculo]:
                # Exibe Título linkado
                st.markdown(f"- [{n['titulo']}]({n['link']})")
            st.markdown("---") # Separador visual

    exibir_clicavel(dados_sisema, "MATÉRIAS SISEMA")
    exibir_clicavel(dados_geral, "MATÉRIAS GERAIS")
