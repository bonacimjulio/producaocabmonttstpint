import psycopg2
import psycopg2.extras
import os
from datetime import datetime

class Database:
    def __init__(self):
        # A URL de conexão será injetada pela Vercel como uma variável de ambiente
        self.db_url = os.environ.get('POSTGRES_URL')
        if not self.db_url:
            raise Exception("A variável de ambiente POSTGRES_URL não foi definida.")
        self._create_tables()

    def _get_db_connection(self):
        # Usamos a URL para conectar ao banco de dados PostgreSQL
        conn = psycopg2.connect(self.db_url)
        return conn

    def _create_tables(self):
        conn = self._get_db_connection()
        cursor = conn.cursor()
        # Sintaxe do PostgreSQL para criar a tabela. SERIAL é o equivalente a AUTOINCREMENT.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS producao (
                id SERIAL PRIMARY KEY,
                modelo TEXT NOT NULL,
                op_montagem TEXT,
                qty_montado INTEGER,
                op_pintura TEXT,
                qty_pintado INTEGER,
                op_teste TEXT,
                qty_testado INTEGER,
                op_retrabalho TEXT,
                retrabalho INTEGER,
                observacao TEXT,
                data_hora TIMESTAMP
            )
        ''')
        conn.commit()
        cursor.close()
        conn.close()

    def registrar_producao(self, modelo, op_montagem, qty_montado, op_pintura, qty_pintado,
                           op_teste, qty_testado, op_retrabalho, retrabalho, observacao):
        conn = self._get_db_connection()
        cursor = conn.cursor()
        data_hora = datetime.now()
        # Usamos %s como placeholder para os parâmetros no psycopg2
        cursor.execute('''
            INSERT INTO producao (modelo, op_montagem, qty_montado, op_pintura, qty_pintado,
                                  op_teste, qty_testado, op_retrabalho, retrabalho, observacao, data_hora)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (modelo, op_montagem, qty_montado, op_pintura, qty_pintado,
              op_teste, qty_testado, op_retrabalho, retrabalho, observacao, data_hora))
        conn.commit()
        cursor.close()
        conn.close()

    def _execute_query(self, query, params=None):
        conn = self._get_db_connection()
        # Usamos DictCursor para obter os resultados como dicionários, similar ao sqlite3.Row
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute(query, params or ())
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return results

    def get_stats_periodo(self, start_date_str, end_date_str):
        query = "SELECT SUM(qty_montado) as total_montado, SUM(qty_pintado) as total_pintado, SUM(qty_testado) as total_testado, SUM(retrabalho) as total_retrabalho FROM producao"
        params = []
        if start_date_str and end_date_str:
            query += " WHERE data_hora BETWEEN %s AND %s"
            params.extend([f"{start_date_str} 00:00:00", f"{end_date_str} 23:59:59"])
        
        stats = self._execute_query(query, params)
        return dict(stats[0]) if stats and stats[0] else {}

    def get_producao_por_modelo(self, start_date_str, end_date_str):
        query = "SELECT modelo, SUM(qty_testado) as total FROM producao WHERE qty_testado > 0"
        params = []
        if start_date_str and end_date_str:
            query += " AND data_hora BETWEEN %s AND %s"
            params.extend([f"{start_date_str} 00:00:00", f"{end_date_str} 23:59:59"])
        query += " GROUP BY modelo ORDER BY total DESC"
        
        results = self._execute_query(query, params)
        return [tuple(row) for row in results]

    def get_retrabalho_por_modelo(self, start_date_str, end_date_str):
        query = "SELECT modelo, SUM(retrabalho) as total_retrabalho FROM producao WHERE retrabalho > 0"
        params = []
        if start_date_str and end_date_str:
            query += " AND data_hora BETWEEN %s AND %s"
            params.extend([f"{start_date_str} 00:00:00", f"{end_date_str} 23:59:59"])
        query += " GROUP BY modelo ORDER BY total_retrabalho DESC"

        results = self._execute_query(query, params)
        return [tuple(row) for row in results]

    def get_producao_periodo(self, start_date_str, end_date_str):
        query = "SELECT id, modelo, op_montagem, qty_montado, op_pintura, qty_pintado, op_teste, qty_testado, op_retrabalho, retrabalho, observacao, data_hora FROM producao"
        params = []
        if start_date_str and end_date_str:
            query += " WHERE data_hora BETWEEN %s AND %s"
            params.extend([f"{start_date_str} 00:00:00", f"{end_date_str} 23:59:59"])
        query += " ORDER BY data_hora DESC"
        
        results = self._execute_query(query, params)
        return [tuple(row) for row in results]

    def delete_producao_por_id(self, id):
        conn = self._get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM producao WHERE id = %s", (id,))
        conn.commit()
        cursor.close()
        conn.close()

    def delete_all_producao(self):
        conn = self._get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM producao")
        conn.commit()
        cursor.close()
        conn.close()
