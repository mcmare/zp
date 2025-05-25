from flask import Flask, render_template, request, redirect, url_for, flash, send_file, abort
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from markupsafe import escape
import sqlite3
from datetime import datetime
import pandas as pd
import bcrypt
import os
import logging
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, PasswordField, SubmitField, DateField, SelectField
from wtforms.validators import DataRequired, NumberRange
from wtforms.widgets import TextInput
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv

load_dotenv()

# Настройка логирования
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-secret-key')
app.config['UPLOAD_FOLDER'] = 'temp'
csrf = CSRFProtect(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Создание папки для временных файлов
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])


# Модель пользователя
class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username


@login_manager.user_loader
def load_user(user_id):
    try:
        conn = sqlite3.connect('orders.db', check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT id, username FROM users WHERE id = ?', (user_id,))
        user = c.fetchone()
        conn.close()
        if user:
            return User(user[0], user[1])
        return None
    except Exception as e:
        logging.error(f"Error in load_user: {e}")
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


# Форма для выбора месяца
class MonthForm(FlaskForm):
    month = SelectField('Месяц', validators=[DataRequired()], render_kw={"class": "form-select"})
    submit = SubmitField('Выбрать', render_kw={"class": "btn btn-primary"})


# Инициализация базы данных
def init_db():
    try:
        conn = sqlite3.connect('orders.db', check_same_thread=False)
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
        logging.info("Database initialized successfully")
    except Exception as e:
        logging.error(f"Error initializing database: {e}")


# Главная страница
@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    try:
        form = MonthForm()
        conn = sqlite3.connect('orders.db', check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT DISTINCT strftime("%Y-%m", date) FROM orders WHERE user_id = ? ORDER BY date DESC',
                  (current_user.id,))
        months = [(row[0], row[0].replace('-', '.')) for row in c.fetchall()]
        form.month.choices = months if months else [
            (datetime.now().strftime('%Y-%m'), datetime.now().strftime('%Y.%m'))]

        selected_month = form.month.data if form.validate_on_submit() else datetime.now().strftime('%Y-%m')

        # Получение заказов
        c.execute(
            'SELECT id, amount, order_number, date FROM orders WHERE strftime("%Y-%m", date) = ? AND user_id = ? ORDER BY date',
            (selected_month, current_user.id))
        orders = [{'id': row[0], 'amount': row[1], 'order_number': escape(row[2]),
                   'date': datetime.strptime(row[3], '%Y-%m-%d').strftime('%d.%m.%Y')} for row in c.fetchall()]

        # Вычисление общей суммы
        c.execute('SELECT SUM(amount) FROM orders WHERE strftime("%Y-%m", date) = ? AND user_id = ?',
                  (selected_month, current_user.id))
        total_amount = c.fetchone()[0] or 0.0  # Если сумма NULL, возвращаем 0.0
        conn.close()

        logging.info(
            f"User {current_user.username} viewed orders for month {selected_month} with total amount {total_amount}")
        return render_template('index.html', orders=orders, form=form, selected_month=selected_month,
                               total_amount=total_amount)
    except Exception as e:
        logging.error(f"Error in index route: {e}")
        abort(500)


# Добавление записи
@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_order():
    try:
        form = OrderForm()
        if form.validate_on_submit():
            amount = form.amount.data
            order_number = escape(form.order_number.data.strip())
            date = form.date.data.strftime('%Y-%m-%d')
            month = date[:7]

            conn = sqlite3.connect('orders.db', check_same_thread=False)
            c = conn.cursor()
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
            logging.info(f"User {current_user.username} added order {order_number} for {amount} on {date}")
            return redirect(url_for('index'))

        form.date.data = datetime.now()
        return render_template('add_edit.html', form=form, title='Добавить запись')
    except Exception as e:
        logging.error(f"Error in add_order route: {e}")
        abort(500)


# Редактирование записи
@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_order(id):
    try:
        conn = sqlite3.connect('orders.db', check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT id, amount, order_number, date FROM orders WHERE id = ? AND user_id = ?',
                  (id, current_user.id))
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
            logging.info(f"User {current_user.username} edited order {id} to {order_number} for {amount} on {date}")
            return redirect(url_for('index'))

        form.amount.data = order[1]
        form.order_number.data = order[2]
        form.date.data = datetime.strptime(order[3], '%Y-%m-%d')
        conn.close()
        return render_template('add_edit.html', form=form, title='Редактировать запись')
    except Exception as e:
        logging.error(f"Error in edit_order route: {e}")
        abort(500)


# Удаление записи
@app.route('/delete/<int:id>')
@login_required
def delete_order(id):
    try:
        conn = sqlite3.connect('orders.db', check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT order_number FROM orders WHERE id = ? AND user_id = ?', (id, current_user.id))
        order = c.fetchone()
        if not order:
            conn.close()
            abort(404)

        c.execute('DELETE FROM orders WHERE id = ? AND user_id = ?', (id, current_user.id))
        conn.commit()
        conn.close()
        flash('Запись удалена!', 'success')
        logging.info(f"User {current_user.username} deleted order {id} ({order[0]})")
        return redirect(url_for('index'))
    except Exception as e:
        logging.error(f"Error in delete_order route: {e}")
        abort(500)


# Экспорт в Excel
@app.route('/export/<month>')
@login_required
def export_to_excel(month):
    try:
        conn = sqlite3.connect('orders.db', check_same_thread=False)
        c = conn.cursor()
        c.execute(
            'SELECT amount, order_number, date FROM orders WHERE strftime("%Y-%m", date) = ? AND user_id = ? ORDER BY date',
            (month, current_user.id))
        orders = [{'Сумма': row[0], 'Номер заказ-наряда': row[1],
                   'Дата': datetime.strptime(row[2], '%Y-%m-%d').strftime('%d.%m.%Y')} for row in c.fetchall()]
        conn.close()

        df = pd.DataFrame(orders)
        filename = os.path.join(app.config['UPLOAD_FOLDER'], f"Orders_{month}.xlsx")
        df.to_excel(filename, index=False)

        response = send_file(filename, as_attachment=True)
        try:
            os.remove(filename)
        except Exception as e:
            logging.error(f"Failed to delete temporary file {filename}: {e}")

        logging.info(f"User {current_user.username} exported orders for month {month}")
        return response
    except Exception as e:
        logging.error(f"Error in export_to_excel route: {e}")
        abort(500)


# Авторизация
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    try:
        form = LoginForm()
        if form.validate_on_submit():
            username = escape(form.username.data.strip())
            password = form.password.data.encode('utf-8')

            conn = sqlite3.connect('orders.db', check_same_thread=False)
            c = conn.cursor()
            c.execute('SELECT id, username, password FROM users WHERE username = ?', (username,))
            user = c.fetchone()
            conn.close()

            if user and bcrypt.checkpw(password, user[2].encode('utf-8')):
                user_obj = User(user[0], user[1])
                login_user(user_obj)
                flash('Вход выполнен!', 'success')
                logging.info(f"User {username} logged in")
                return redirect(url_for('index'))
            flash('Неверный логин или пароль!', 'danger')
            logging.warning(f"Failed login attempt for username {username}")

        return render_template('login.html', form=form)
    except Exception as e:
        logging.error(f"Error in login route: {e}")
        abort(500)


# Выход
@app.route('/logout')
@login_required
def logout():
    try:
        username = current_user.username
        logout_user()
        flash('Вы вышли из системы!', 'success')
        logging.info(f"User {username} logged out")
        return redirect(url_for('login'))
    except Exception as e:
        logging.error(f"Error in logout route: {e}")
        abort(500)


if __name__ == '__main__':
    init_db()
    app.run(host='127.0.0.1', port='5000', debug=True)