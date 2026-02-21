import pyodbc
# connection
def get_db_connection():
    conn_str = (
        r"Driver={ODBC Driver 17 for SQL Server};"
        r"Server=.\SQLEXPRESS;" 
        r"Database=flower_store;"
        r"Trusted_Connection=yes;"
    )
    return pyodbc.connect(conn_str)