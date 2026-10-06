import io
import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Atualizador de Estoque | NetVarejo ➔ Nuvemshop",
    page_icon="👟",
    layout="wide"
)

st.title("👟 Atualizador de Estoque: NetVarejo ➔ Nuvemshop")
st.caption("Cruzamento seguro entre ERP NetVarejo e Nuvemshop com validação estrita de duplicados e integridade de SKU.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. ERP NetVarejo")
    arquivo_erp = st.file_uploader("Arquivo NetVarejo", type=["xlsx", "csv"], key="erp")

with col2:
    st.subheader("2. Nuvemshop")
    arquivo_nuvem = st.file_uploader("Exportação Nuvemshop", type=["xlsx", "csv"], key="nuvem")

def carregar_arquivo(uploaded_file):
    """Carrega ficheiros XLSX ou CSV tratando diferentes encodings e separadores com segurança."""
    if uploaded_file.name.lower().endswith(".xlsx"):
        return pd.read_excel(uploaded_file, dtype=str)
    
    encodings = ["utf-8-sig", "utf-8", "latin1", "cp1252", "iso-8859-1"]
    for enc in encodings:
        try:
            uploaded_file.seek(0)
            return pd.read_csv(uploaded_file, dtype=str, encoding=enc, sep=None, engine="python")
        except Exception:
            continue
            
    uploaded_file.seek(0)
    return pd.read_csv(uploaded_file, dtype=str, encoding="latin1")

if arquivo_erp and arquivo_nuvem:
    try:
        with st.spinner("A carregar ficheiros..."):
            df_erp = carregar_arquivo(arquivo_erp)
            df_nuvem = carregar_arquivo(arquivo_nuvem)

        st.divider()
        st.subheader("Mapeamento das Colunas")

        def get_index(columns, target_name, default_index=0):
            cols_lower = [str(c).strip().lower() for c in columns]
            target = target_name.strip().lower()
            if target in cols_lower:
                return cols_lower.index(target)
            return default_index

        idx_sku_erp = get_index(df_erp.columns, "CodigoInterno", 0)
        idx_est_erp = get_index(df_erp.columns, "SaldoDisponivel", 1 if len(df_erp.columns) > 1 else 0)

        idx_sku_nuvem = get_index(df_nuvem.columns, "SKU", 0)
        idx_est_nuvem = get_index(df_nuvem.columns, "Estoque", 1 if len(df_nuvem.columns) > 1 else 0)

        c1, c2 = st.columns(2)
        with c1:
            col_sku_erp = st.selectbox("Coluna SKU (NetVarejo):", df_erp.columns, index=idx_sku_erp)
            col_estoque_erp = st.selectbox("Coluna Estoque (NetVarejo):", df_erp.columns, index=idx_est_erp)

        with c2:
            col_sku_nuvem = st.selectbox("Coluna SKU (Nuvemshop):", df_nuvem.columns, index=idx_sku_nuvem)
            col_estoque_nuvem = st.selectbox("Coluna Estoque (Nuvemshop):", df_nuvem.columns, index=idx_est_nuvem)

        if st.button("🚀 Processar e Validar Estoque", type="primary"):
            # 1. Validação no ERP NetVarejo
            df_erp_clean = df_erp.copy()
            df_erp_clean[col_sku_erp] = df_erp_clean[col_sku_erp].fillna("").astype(str).str.strip()
            df_erp_clean[col_estoque_erp] = df_erp_clean[col_estoque_erp].fillna("0").astype(str).str.strip()
            df_erp_validos = df_erp_clean[df_erp_clean[col_sku_erp] != ""].copy()

            skus_duplicados_erp = df_erp_validos[df_erp_validos.duplicated(subset=[col_sku_erp], keep=False)]
            if not skus_duplicados_erp.empty:
                st.error(f"⛔ **Processamento interrompido:** Existem SKUs duplicados no ERP NetVarejo:")
                st.dataframe(skus_duplicados_erp[[col_sku_erp, col_estoque_erp]], use_container_width=True)
                st.stop()

            # 2. Validação de Duplicados na Nuvemshop (com mapeamento exato de linhas)
            df_nuvem_validacao = df_nuvem.copy()
            df_nuvem_validacao[col_sku_nuvem] = df_nuvem_validacao[col_sku_nuvem].fillna("").astype(str).str.strip()
            
            # Adiciona o número real da linha do Excel (linha 1 = cabeçalho, logo índice 0 = linha 2)
            df_nuvem_validacao["_num_linha_excel"] = df_nuvem_validacao.index + 2

            # Considera apenas SKUs preenchidos para verificação de duplicados
            skus_preenchidos = df_nuvem_validacao[df_nuvem_validacao[col_sku_nuvem] != ""]
            duplicados_nuvem = skus_preenchidos[skus_preenchidos.duplicated(subset=[col_sku_nuvem], keep=False)]

            if not duplicados_nuvem.empty:
                # Agrupa os SKUs duplicados e cria lista de linhas
                relatorio_dup = duplicados_nuvem.groupby(col_sku_nuvem)["_num_linha_excel"].agg(
                    Ocorrencias="count",
                    Linhas=lambda x: ", ".join(map(str, x))
                ).reset_index()

                st.error(f"⛔ **Atenção:** Foram detetados {len(relatorio_dup)} SKUs repetidos na folha de cálculo da Nuvemshop!")
                st.warning("SKUs repetidos na Nuvemshop podem originar sobreposição indevida de dados. Corrija as linhas indicadas abaixo:")
                
                # Exibe a tabela detalhada
                st.dataframe(
                    relatorio_dup.rename(columns={col_sku_nuvem: "SKU Repetido"}),
                    use_container_width=True
                )
                st.stop()

            # 3. Processamento e Cruzamento de Dados
            mascara_numerica_erp = df_erp_validos[col_sku_erp].str.isdigit()
            df_erp_numerico = df_erp_validos[mascara_numerica_erp]
            mapa_estoque = df_erp_numerico.set_index(col_sku_erp)[col_estoque_erp].to_dict()

            df_resultado = df_nuvem.copy()
            df_resultado[col_sku_nuvem] = df_resultado[col_sku_nuvem].fillna("").astype(str).str.strip()

            def calcular_novo_estoque(row):
                sku = str(row[col_sku_nuvem]).strip()
                estoque_antigo = row[col_estoque_nuvem]

                if not sku.isdigit():
                    return ""
                
                if sku in mapa_estoque:
                    return mapa_estoque[sku]
                
                return estoque_antigo

            total_linhas = len(df_resultado)
            skus_nao_numericos = (~df_resultado[col_sku_nuvem].str.isdigit()).sum()
            
            df_resultado[col_estoque_nuvem] = df_resultado.apply(calcular_novo_estoque, axis=1)
            skus_numericos_encontrados = df_resultado[col_sku_nuvem].apply(lambda s: s.isdigit() and s in mapa_estoque).sum()

            st.success("✅ Validação e processamento concluídos sem qualquer duplicação!")
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Linhas totais", int(total_linhas))
            m2.metric("SKUs atualizados pelo ERP", int(skus_numericos_encontrados))
            m3.metric("SKUs não numéricos (vazios)", int(skus_nao_numericos))
            m4.metric("SKUs mantidos", int(total_linhas - skus_numericos_encontrados - skus_nao_numericos))

            # Exportação
            buffer = io.BytesIO()
            if arquivo_nuvem.name.lower().endswith(".csv"):
                csv_data = df_resultado.to_csv(index=False, sep=";", encoding="utf-8-sig")
                st.download_button(
                    label="📥 Descarregar Folha Nuvemshop (.CSV)",
                    data=csv_data,
                    file_name="nuvemshop_estoque_atualizado.csv",
                    mime="text/csv",
                    type="primary"
                )
            else:
                with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                    df_resultado.to_excel(writer, index=False)
                st.download_button(
                    label="📥 Descarregar Folha Nuvemshop (.XLSX)",
                    data=buffer.getvalue(),
                    file_name="nuvemshop_estoque_atualizado.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )

    except Exception as e:
        st.error(f"Erro ao processar ficheiros: {e}")