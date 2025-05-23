from flask import Flask, render_template, request, redirect, url_for, flash, send_file, abort
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from markupsafe import escape
import sqlite3
from datetime import datetime
import pandas as pd
import bcrypt
import os
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, PasswordField, SubmitField, DateField
from wtforms.validators import DataRequired, NumberRange
from wtforms.widgets import TextInput
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv



load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')  # Замените на безопасный ключ
csrf = CSRFProtect(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# Модель пользователя
class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username


@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute('SELECT id, username FROM users WHERE id = ?', (user_id,))
    user = c.fetchone()
    conn.close()
    if user:
        return User(user[0], user[1])
    return None


# Форма для добавления/редактирования
class OrderForm(FlaskForm):
    amount = FloatField('Сумма', validators=[DataRequired(), NumberRange(min=0)], render_kw={"class": "form-control"})
    order_number = StringField('Номер заказ-наряда', validators=[DataRequired()], render_kw={"class": "form-control"})
    date = DateField('Дата', format='%Y-%m-%d', validators=[DataRequired()], render_kw={"class": "form-control"})
    submit = SubmitField('Сохранить', render_kw={"class": "btn btn-primary"})


# Форма для логина
class LoginForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired()], render_kw={"class": "form-control"})
    password = PasswordField('Пароль', validators=[DataRequired()], render_kw={"class": "form-control"})
    submit = SubmitField('Войти', render_kw={"class": "btn btn-primary"})


# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS orders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  amount REAL NOT NULL,
                  order_number TEXT NOT NULL,
                  date TEXT NOT NULL,
                  user_id INTEGER NOT NULL,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT NOT NULL UNIQUE,
                  password TEXT NOT NULL)''')
    conn.commit()
    conn.close()


# Главная страница
@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    selected_month = request.form.get('month', datetime.now().strftime('%Y-%m'))
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute(
        'SELECT id, amount, order_number, date FROM orders WHERE strftime("%Y-%m", date) = ? AND user_id = ? ORDER BY date',
        (selected_month, current_user.id))
    orders = [{'id': row[0], 'amount': row[1], 'order_number': escape(row[2]),
               'date': datetime.strptime(row[3], '%Y-%m-%d').strftime('%d.%m.%Y')} for row in c.fetchall()]

    # Получение уникальных месяцев
    c.execute('SELECT DISTINCT strftime("%Y-%m", date) FROM orders WHERE user_id = ? ORDER BY date DESC',
              (current_user.id,))
    months = [row[0] for row in c.fetchall()]
    conn.close()

    return render_template('index.html', orders=orders, months=months, selected_month=selected_month)


# Добавление записи
@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_order():
    form = OrderForm()
    if form.validate_on_submit():
        amount = form.amount.data
        order_number = escape(form.order_number.data.strip())
        date = form.date.data.strftime('%Y-%m-%d')
        month = date[:7]  # ГГГГ-ММ

        conn = sqlite3.connect('orders.db')
        c = conn.cursor()
        # Проверка уникальности номера заказ-наряда в текущем месяце
        c.execute('SELECT id FROM orders WHERE order_number = ? AND strftime("%Y-%m", date) = ? AND user_id = ?',
                  (order_number, month, current_user.id))
        if c.fetchone():
            flash('Номер заказ-наряда уже существует в этом месяце!', 'danger')
            conn.close()
            return render_template('add_edit.html', form=form, title='Добавить запись')

        c.execute('INSERT INTO orders (amount, order_number, date, user_id) VALUES (?, ?, ?, ?)',
                  (amount, order_number, date, current_user.id))
        conn.commit()
        conn.close()
        flash('Запись добавлена!', 'success')
        return redirect(url_for('index'))

    form.date.data = datetime.now()
    return render_template('add_edit.html', form=form, title='Добавить запись')


# Редактирование записи
@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_order(id):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute('SELECT id, amount, order_number, date FROM orders WHERE id = ? AND user_id = ?', (id, current_user.id))
    order = c.fetchone()
    if not order:
        conn.close()
        abort(404)

    form = OrderForm()
    if form.validate_on_submit():
        amount = form.amount.data
        order_number = escape(form.order_number.data.strip())
        date = form.date.data.strftime('%Y-%m-%d')
        month = date[:7]

        # Проверка уникальности номера заказ-наряда, исключая текущую запись
        c.execute(
            'SELECT id FROM orders WHERE order_number = ? AND strftime("%Y-%m", date) = ? AND id != ? AND user_id = ?',
            (order_number, month, id, current_user.id))
        if c.fetchone():
            flash('Номер заказ-наряда уже существует в этом месяце!', 'danger')
            conn.close()
            return render_template('add_edit.html', form=form, title='Редактировать запись')

        c.execute('UPDATE orders SET amount = ?, order_number = ?, date = ? WHERE id = ? AND user_id = ?',
                  (amount, order_number, date, id, current_user.id))
        conn.commit()
        conn.close()
        flash('Запись обновлена!', 'success')
        return redirect(url_for('index'))

    form.amount.data = order[1]
    form.order_number.data = order[2]
    form.date.data = datetime.strptime(order[3], '%Y-%m-%d')
    conn.close()
    return render_template('add_edit.html', form=form, title='Редактировать запись')


# Удаление записи
@app.route('/delete/<int:id>')
@login_required
def delete_order(id):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute('DELETE FROM orders WHERE id = ? AND user_id = ?', (id, current_user.id))
    conn.commit()
    conn.close()
    flash('Запись удалена!', 'success')
    return redirect(url_for('index'))


# Экспорт в Excel
@app.route('/export/<month>')
@login_required
def export_to_excel(month):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute(
        'SELECT amount, order_number, date FROM orders WHERE strftime("%Y-%m", date) = ? AND user_id = ? ORDER BY date',
        (month, current_user.id))
    orders = [{'Сумма': row[0], 'Номер заказ-наряда': row[1],
               'Дата': datetime.strptime(row[2], '%Y-%m-%d').strftime('%d.%m.%Y')} for row in c.fetchall()]
    conn.close()

    df = pd.DataFrame(orders)
    filename = f"Orders_{month}.xlsx"
    df.to_excel(filename, index=False)

    return send_file(filename, as_attachment=True)


# Авторизация
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm()
    if form.validate_on_submit():
        username = escape(form.username.data.strip())
        password = form.password.data.encode('utf-8')

        conn = sqlite3.connect('orders.db')
        c = conn.cursor()
        c.execute('SELECT id, username, password FROM users WHERE username = ?', (username,))
        user = c.fetchone()
        conn.close()

        if user and bcrypt.checkpw(password, user[2].encode('utf-8')):
            user_obj = User(user[0], user[1])
            login_user(user_obj)
            flash('Вход выполнен!', 'success')
            return redirect(url_for('index'))
        flash('Неверный логин или пароль!', 'danger')

    return render_template('login.html', form=form)


# Выход
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы!', 'success')
    return redirect(url_for('login'))


if __name__ == '__main__':
    init_db()
    app.run(debug=True)