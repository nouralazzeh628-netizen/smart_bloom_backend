import pyodbc

def get_db_connection():
    conn = (
        r"Driver={ODBC Driver 17 for SQL Server};"
        r"Server=DESKTOP-I4DJAG3\SQLEXPRESS;"
        r"Database=flower_store;"
        r"Trusted_Connection=yes;"
    )
    return pyodbc.connect(conn)