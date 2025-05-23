import sqlite3
import bcrypt
from flask import Flask, request, abort

app = Flask(__name__)


def init_db():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT NOT NULL UNIQUE,
                  password TEXT NOT NULL)''')
    conn.commit()
    conn.close()


@app.route('/register', methods=['POST'])
def register():
    # Доступ только с локального сервера
    if request.remote_addr != '127.0.0.1':
        abort(403)

    username = request.form['username'].strip()
    password = request.form['password'].encode('utf-8')

    if not username or not password:
        return "Логин и пароль обязательны!", 400

    hashed = bcrypt.hashpw(password, bcrypt.gensalt())

    try:
        conn = sqlite3.connect('orders.db')
        c = conn.cursor()
        c.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed.decode('utf-8')))
        conn.commit()
        conn.close()
        return "Пользователь зарегистрирован!"
    except sqlite3.IntegrityError:
        return "Пользователь с таким логином уже существует!", 400


if __name__ == '__main__':
    init_db()
    app.run(host='127.0.0.1', port=5001)