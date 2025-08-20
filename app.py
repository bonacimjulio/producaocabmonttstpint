# /PRODUCAO-FLASK/app.py
import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from database import Database  # Reutilizando seu arquivo de banco de dados
import io

# --- CONFIGURAÇÃO DA APLICAÇÃO FLASK ---
app = Flask(__name__)
# Chave secreta para mensagens flash e segurança de sessão
app.secret_key = os.urandom(24)

# --- INICIALIZAÇÃO DO BANCO DE DADOS ---
# (Não precisa de cache como no Streamlit, o Flask gerencia isso de outra forma)
db = Database()

# --- LISTA DE OPERADORES E MODELOS (CONSTANTES) ---
OPERADORES = [
    "GILSON ROBERTO DE OLIVEIRA", "JÚLIO BONANCIM SILVA", "FELIPE DOMINGOS MOREIRA",
    "LUIZ HENRIQUE DE JESUS MARQUES", "RAFAEL BARROSO MARQUES", "JOÃO VITOR DA SILVA",
    "KEOLIN MIRELA FERRERA"
]
MODELOS = ["Unidade Compressora 20+", "Unidade Compressora 15+", "Unidade Compressora 10 RED"]


# --- ROTA PRINCIPAL: DASHBOARD E HISTÓRICO ---
@app.route('/', methods=['GET', 'POST'])
def dashboard():
    # Define o período padrão (Hoje)
    start_date = datetime.now().date()
    end_date = datetime.now().date()
    period_name = "Hoje"

    # Default active tab for initial GET request or redirects from other POSTs (registrar, excluir, limpar)
    active_tab = 'registro'

    # Se o formulário de período for enviado, atualiza as datas
    if request.method == 'POST':
        # This block only executes if a filter form on the dashboard tab was submitted
        if 'periodo' in request.form or 'data_especifica' in request.form:
            periodo = request.form.get('periodo')
            if periodo == 'hoje':
                start_date, end_date, period_name = datetime.now().date(), datetime.now().date(), "Hoje"
            elif periodo == '7dias':
                start_date, end_date, period_name = datetime.now().date() - timedelta(
                    days=6), datetime.now().date(), "Últimos 7 dias"
            elif periodo == 'mes':
                today = datetime.now().date()
                start_date, end_date, period_name = today.replace(day=1), today, "Este Mês"
            elif periodo == 'completo':
                start_date, end_date, period_name = None, None, "Histórico Completo"
            elif request.form.get('data_especifica'):
                picked_date_str = request.form.get('data_especifica')
                picked_date = datetime.strptime(picked_date_str, '%Y-%m-%d').date()
                start_date, end_date, period_name = picked_date, picked_date, f"Dia: {picked_date.strftime('%d/%m/%Y')}"
            
            # After processing a filter POST, the dashboard tab should be active
            active_tab = 'dashboard'

    # Converte datas para string para a consulta no DB
    start_str = start_date.strftime("%Y-%m-%d") if start_date else None
    end_str = end_date.strftime("%Y-%m-%d") if end_date else None

    # --- BUSCA DE DADOS ---
    stats = db.get_stats_periodo(start_str, end_str)
    producao_modelo = db.get_producao_por_modelo(start_str, end_str)
    retrabalho_modelo = db.get_retrabalho_por_modelo(start_str, end_str)
    registros = db.get_producao_periodo(start_str, end_str)

    # --- CÁLCULO DAS MÉTRICAS ---
    total_montado = stats.get("total_montado") or 0
    total_pintado = stats.get("total_pintado") or 0
    total_testado = stats.get("total_testado") or 0
    total_retrabalho = stats.get("total_retrabalho") or 0
    taxa_retrabalho = (total_retrabalho / total_testado * 100) if total_testado > 0 else 0

    metrics = {
        "total_montado": f"{total_montado:,}".replace(",", "."),
        "total_pintado": f"{total_pintado:,}".replace(",", "."),
        "total_testado": f"{total_testado:,}".replace(",", "."),
        "taxa_retrabalho": f"{taxa_retrabalho:.1f}%",
        "total_retrabalho_abs": f"{total_retrabalho} pçs"
    }

    # --- GERAÇÃO DOS GRÁFICOS ---
    fig_pie_html, fig_bar_html, fig_pie_retrabalho_html = None, None, None
    if producao_modelo:
        df_modelo = pd.DataFrame(producao_modelo, columns=['Modelo', 'Total'])
        # Gráfico de Pizza
        fig_pie = px.pie(df_modelo, names='Modelo', values='Total', hole=0.4, title="Produção por Modelo (%)")
        fig_pie.update_layout(showlegend=False, margin=dict(t=40, b=0, l=0, r=0))
        fig_pie.update_traces(textposition='inside', textinfo='percent+label', textfont_size=14)
        fig_pie_html = fig_pie.to_html(full_html=False, include_plotlyjs='cdn')

        # Gráfico de Barras
        fig_bar = px.bar(df_modelo, x='Modelo', y='Total', text_auto='.2s', color='Modelo',
                         title="Produção por Modelo (Unidades)")
        fig_bar.update_traces(textfont_size=14, textangle=0, textposition="outside", cliponaxis=False)
        fig_bar.update_layout(xaxis_title=None)
        fig_bar_html = fig_bar.to_html(full_html=False, include_plotlyjs='cdn')

    if retrabalho_modelo:
        df_retrabalho_modelo = pd.DataFrame(retrabalho_modelo, columns=['Modelo', 'Total_Retrabalho'])
        # Gráfico de Pizza de Retrabalho
        fig_pie_retrabalho = px.pie(df_retrabalho_modelo, names='Modelo', values='Total_Retrabalho', hole=0.4, title="Retrabalho por Modelo (%)")
        fig_pie_retrabalho.update_layout(showlegend=False, margin=dict(t=40, b=0, l=0, r=0))
        fig_pie_retrabalho.update_traces(textposition='inside', textinfo='percent+label', textfont_size=14)
        fig_pie_retrabalho_html = fig_pie_retrabalho.to_html(full_html=False, include_plotlyjs='cdn')

    # --- PREPARAÇÃO DO HISTÓRICO ---
    df_hist = pd.DataFrame()
    if registros:
        df_hist = pd.DataFrame(registros, columns=[
            "ID", "Modelo", "Op. Montagem", "Qtd. Montado", "Op. Pintura", "Qtd. Pintado",
            "Op. Teste", "Qtd. Testado", "Op. Retrabalho", "Qtd. Retrabalho", "Observação", "Data/Hora"
        ])
        df_hist['Data/Hora'] = pd.to_datetime(df_hist['Data/Hora']).dt.strftime('%d/%m/%Y %H:%M')

    # Renderiza o template HTML, passando todos os dados
    return render_template(
        'index.html',
        operadores=OPERADORES,
        modelos=MODELOS,
        metrics=metrics,
        fig_pie_html=fig_pie_html,
        fig_bar_html=fig_bar_html,
        fig_pie_retrabalho_html=fig_pie_retrabalho_html, # Pass the new chart
        historico=df_hist.to_dict(orient='records'),
        period_name=period_name,
        all_ids=df_hist['ID'].tolist() if not df_hist.empty else [],
        active_tab=active_tab # Pass the active tab to the template
    )


# --- ROTA PARA REGISTRAR PRODUÇÃO ---
@app.route('/registrar', methods=['POST'])
def registrar():
    try:
        modelo = request.form.get('modelo')
        op_montagem = request.form.get('op_montagem')
        qty_montado = int(request.form.get('qty_montado', 0))
        op_pintura = request.form.get('op_pintura')
        qty_pintado = int(request.form.get('qty_pintado', 0))
        op_teste = request.form.get('op_teste')
        qty_testado = int(request.form.get('qty_testado', 0))
        op_retrabalho = request.form.get('op_retrabalho')
        retrabalho = int(request.form.get('retrabalho', 0))
        observacao = request.form.get('observacao')

        if not modelo:
            flash("Por favor, selecione um modelo de cabeçote.", "warning")
        elif not any([qty_montado, qty_pintado, qty_testado]):
            flash("Preencha a quantidade de pelo menos uma etapa!", "warning")
        else:
            db.registrar_producao(
                modelo, op_montagem, qty_montado, op_pintura, qty_pintado,
                op_teste, qty_testado, op_retrabalho, retrabalho, observacao
            )
            flash("Produção registrada com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao registrar: {e}", "error")

    return redirect(url_for('dashboard'))


# --- ROTA PARA EXCLUIR REGISTRO ---
@app.route('/excluir/<int:id>', methods=['POST'])
def excluir(id):
    try:
        db.delete_producao_por_id(id)
        flash(f"Registro {id} excluído com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao excluir registro {id}: {e}", "error")
    return redirect(url_for('dashboard'))


# --- ROTA PARA LIMPAR HISTÓRICO ---
@app.route('/limpar', methods=['POST'])
def limpar_historico():
    try:
        db.delete_all_producao()
        flash("Todo o histórico foi limpo com sucesso.", "success")
    except Exception as e:
        flash(f"Erro ao limpar o histórico: {e}", "error")
    return redirect(url_for('dashboard'))


# --- ROTA PARA EXPORTAR EXCEL ---
@app.route('/exportar')
def exportar_excel():
    registros = db.get_producao_periodo(None, None)  # Exporta tudo
    if not registros:
        flash("Nenhum dado para exportar.", "info")
        return redirect(url_for('dashboard'))

    df_hist = pd.DataFrame(registros, columns=[
        "ID", "Modelo", "Op. Montagem", "Qtd. Montado", "Op. Pintura", "Qtd. Pintado",
        "Op. Teste", "Qtd. Testado", "Op. Retrabalho", "Qtd. Retrabalho", "Observação", "Data/Hora"
    ])
    df_hist['Data/Hora'] = pd.to_datetime(df_hist['Data/Hora']).dt.strftime('%d/%m/%Y %H:%M')

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_hist.to_excel(writer, index=False, sheet_name='Producao_Detalhada')

    output.seek(0)

    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"producao_cabecotes_{datetime.now().strftime('%Y%m%d')}.xlsx"
    )


if __name__ == '__main__':
    app.run(debug=True)