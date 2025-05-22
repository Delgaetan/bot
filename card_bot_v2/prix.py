
import sqlite3

with sqlite3.connect("data/database.db") as conn:
    c = conn.cursor()
    c.execute("UPDATE cards SET price = 100 WHERE rarity = 'commune'")
    c.execute("UPDATE cards SET price = 250 WHERE rarity = 'rare'")
    c.execute("UPDATE cards SET price = 500 WHERE rarity = 'épique'")
    c.execute("UPDATE cards SET price = 1000 WHERE rarity = 'légendaire'")
    conn.commit()