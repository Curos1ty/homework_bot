import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telegram import Bot

from exception import MyCustomError

load_dotenv()

PRACTICUM_TOKEN: str = os.getenv('PRACTICUM_TOKEN_ENV')
TELEGRAM_TOKEN: str = os.getenv('TELEGRAM_TOKEN_ENV')
TELEGRAM_CHAT_ID: int = os.getenv('TELEGRAM_CHAT_ID_ENV')

TOKEN_NAMES = [
    'PRACTICUM_TOKEN',
    'TELEGRAM_TOKEN',
    'TELEGRAM_CHAT_ID'
]

RETRY_TIME: int = 300
ENDPOINT: str = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS: dict = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS: dict = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправка сообщения через бота в Telegram чат."""
    try:
        bot.send_message(
            TELEGRAM_CHAT_ID,
            message,
        )
    except Exception as error:
        raise MyCustomError(
            "Ошибка отправки сообщения функции send_message"
            + f'Попытка через бота {bot} отправить сообщение пользователю с ID'
            + str({TELEGRAM_CHAT_ID})
            + f'\n Ошибка {error}'
        )
    else:
        logging.info(
            f'Пользователю с ID - {TELEGRAM_CHAT_ID}, '
            + f'от бота отправлена следующая информация:\n{message}'
        )


def get_api_answer(current_timestamp):
    """
    Делает запрос к API-сервису Яндекса.
    и возвращает приведенные данные к типу python.
    """
    try:
        response: dict = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': current_timestamp}
        )
    except Exception as error:
        raise MyCustomError(
            f'Запрос не удался: {error} '
            + f'код ответа сервера: {response.status_code}'
        )

    if response.status_code != HTTPStatus.OK:
        raise MyCustomError(
            'Ответ от сервера некорректный: '
            + f'{response.status_code}, данные авторизации {HEADERS}'
            + f'адрес api {ENDPOINT}'
        )
    elif isinstance(response.json(), dict):
        return response.json()


def check_response(response):
    """Проверка ответа API на корректность."""
    if not isinstance(response, dict):
        raise TypeError(
            'Некорректный ответ сервера'
        )

    if 'homeworks' not in response:
        raise KeyError('В ответе API отсутствует ключ homeworks')

    if 'current_date' not in response:
        raise KeyError('В ответе API отсутствует ключ current_date')

    if not isinstance(response['current_date'], int):
        raise TypeError(
            'В API по ключу current_date должно быть целым числом'
        )

    if not isinstance(response['homeworks'], list):
        raise TypeError('Значение по ключу должно быть list')

    return response['homeworks']


def parse_status(homework):
    """Получение статуса работы заданной домашки."""
    if 'homework_name' not in homework:
        raise KeyError('В ответе API не найден ключ homework_name')

    if 'status' not in homework:
        raise KeyError('В ответе API не найден ключ status')

    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if homework_status not in HOMEWORK_VERDICTS:
        raise Exception(
            f'{homework_status} - такой статус отсутствует в списке'
        )

    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка переменных окружения необходимых для работы."""
    availability_tokens = True
    for token in TOKEN_NAMES:
        if not globals().get(token):
            availability_tokens = False
            logging.error(f'Отсутствует токен: {token}')
    return availability_tokens


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        error_message = (
            'Необходимые для работы переменные окружения отсутствуют, '
            'смотрите homework.py.log. '
            'Работа программы будет остановлена'
        )
        logging.critical(error_message)
        sys.exit(error_message)

    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp: int = 0
    status_message_old: str = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            logging.info(response)
            homeworks = check_response(response)
            logging.info(homeworks)

            if homeworks:
                status_message = parse_status(homeworks[0])
                logging.info('Данные последней работы корректны')

                if status_message_old != status_message:
                    send_message(bot, status_message)
                    status_message_old = status_message

            else:
                logging.error('Ошибка получения данных последней домашки')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
        else:
            logging.info('Все запросы выполнены, ожидается повторный запуск')
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        format=(
            '%(asctime)s - %(levelname)s - '
            + '%(funcName)s - %(lineno)s - %(message)s'
        ),
        handlers=[logging.FileHandler('homework.py.log', 'w', 'utf-8')],
        level=logging.DEBUG,
    )
    main()
