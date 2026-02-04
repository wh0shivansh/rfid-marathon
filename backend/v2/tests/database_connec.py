import psycopg2, os
try:
    conn = psycopg2.connect(
        host="db.jydyttsjymjnfprlpwft.supabase.co",
        port=5432,
        dbname="postgres",
        user="postgres",
        password="InnoRfidPass",
        sslmode="require",
        connect_timeout=5,
    )
    print("connected")
    conn.close()
except Exception as e:
    print("error:", e)