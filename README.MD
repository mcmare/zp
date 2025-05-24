установка зависимостей
```bash
pip install -r requierements.txt
```
файл .env
```env
SECRET_KEY=your-secret-key
```
генерация ключа через 
```bash
python -c "import os; print(os.urandom(24).hex())"
```
запуск приложения
```bash
gunicorn --workers 3 --bind 0.0.0.0:8000 wsgi:app
```
Приложение будет доступно по адресу http://127.0.0.1:8000.

регистрация пользователей
```bash
python register.py
```
```bash
curl -X POST -F "username=testuser" -F "password=testpass" http://127.0.0.1:5001/register
```
Регистрация доступна только с 127.0.0.1.

## Развертывание
```bash
sudo apt update && sudo apt upgrade
sudo apt install python3 python3-pip python3-venv nginx
```

```bash
git clone https://github.com/mcmare/zp.git
```

## Примечания
- Безопасность: Используются параметризованные запросы для защиты от SQL-инъекций, markupsafe.escape для защиты от XSS, CSRF-токены в формах.
- Excel: Файлы сохраняются на сервере и отправляются пользователю. Для продакшена рекомендуется добавить очистку временных файлов.
- Секретный ключ: Замените 'your-secret-key' в app.py на безопасный ключ (например, сгенерированный через os.urandom(24).hex()).
- Локализация: Все элементы интерфейса и Excel-файлы на русском языке.
- Дата: Формат ДД.ММ.ГГГГ в интерфейсе, ГГГГ-ММ-ДД в базе.