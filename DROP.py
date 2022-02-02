import sqlite3


con = sqlite3.connect('team_db.db')
cur = con.cursor()

# cur.execute('''DROP TABLE IF EXISTS supervisors''')
# cur.execute('''DROP TABLE IF EXISTS directions''')
# cur.execute('''DROP TABLE IF EXISTS contests''')
# cur.execute('''DROP TABLE IF EXISTS categories''')
# cur.execute('''DROP TABLE IF EXISTS cat_dir_contest''')
# cur.execute('''DROP TABLE IF EXISTS cats_supervisors''')

cur.execute('''DROP TABLE IF EXISTS users''')
cur.execute('''DROP TABLE IF EXISTS profile''')
cur.execute('''DROP TABLE IF EXISTS team_application''')
cur.execute('''DROP TABLE IF EXISTS cats_secretaries''')