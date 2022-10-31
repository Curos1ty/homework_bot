import logging
import os
import sys
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler
from typing import Dict

import requests
from dotenv import load_dotenv
from telegram import Bot

from exception import IncorrectResponseServerError

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
HEADERS: Dict[str, str] = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS: Dict[str, str] = {
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
    except Exception:
        logging.error(
            'Ошибка отправки сообщения функции send_message'
            f'Попытка через бота {bot} отправить сообщение пользователю с ID'
            + str({TELEGRAM_CHAT_ID})
        )
    else:
        logging.info(
            f'Пользователю с ID - {TELEGRAM_CHAT_ID}, '
            f'от бота отправлена следующая информация:\n{message}'
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
        raise IncorrectResponseServerError(
            f'Запрос не удался: {error}. '
            f'Код ответа сервера: {response.status_code}'
            f'Параметры: адрес api {ENDPOINT}, данные авторизации {HEADERS}'
            f'метка даты в Unix {current_timestamp}'
        )

    if response.status_code != HTTPStatus.OK:
        raise IncorrectResponseServerError(
            'Ответ от сервера некорректный, код: '
            f'{response.status_code}, данные авторизации {HEADERS}'
            f'адрес api {ENDPOINT}, метка даты в Unix {current_timestamp}'
        )

    return response.json()


def check_response(response):
    """Проверка ответа API на корректность."""
    if not isinstance(response, dict):
        raise TypeError(
            f'В ответе API ожидался словарь, получен {type(response)}'
        )

    if 'homeworks' not in response:
        raise KeyError(
            'В ответе API отсутствует ключ homeworks'
        )

    if 'current_date' not in response:
        raise KeyError(
            'В ответе API отсутствует ключ current_date'
        )

    if not isinstance(response['current_date'], int):
        raise TypeError(
            'В ответе API по ключу "current_date" должно быть целое число, '
            f'сейчас там {type(response["current_date"])}'
        )

    homeworks = response['homeworks']

    if not isinstance(homeworks, list):
        raise TypeError(
            'В ответе API значение по ключу "homeworks" должно быть list'
            f'сейчас там {type(response("homeworks"))}'
        )

    return homeworks


def parse_status(homework):
    """Получение статуса работы заданной домашки."""
    if 'homework_name' not in homework:
        raise KeyError('В ответе API не найден ключ homework_name')

    if 'status' not in homework:
        raise KeyError('В ответе API не найден ключ status')

    if homework.get('status') not in HOMEWORK_VERDICTS:
        raise Exception(
            f'{homework.get("status")} - такой статус отсутствует в списке'
        )

    homework_name = homework.get("homework_name")
    verdict = HOMEWORK_VERDICTS[homework.get('status')]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка переменных окружения необходимых для работы."""
    availability_tokens = True
    for token in TOKEN_NAMES:
        if not globals().get(token):
            availability_tokens = False
            logging.critical(f'Отсутствует токен: {token}')
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
        raise SystemExit(error_message)

    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp: int = 0
    status_message_old: str = ''
    message_error_old: str = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            logging.info(f'От API получена следующая информация: \n{response}')
            homeworks = check_response(response)
            logging.info(f'Ответ API корректный: \n{homeworks}')

            if not homeworks:
                logging.info(
                    'Ошибка получения данных последней домашки'
                    'словарь "homeworks" пуст'
                )

            status_message = parse_status(homeworks[0])
            logging.info(f'Статус последней работы получен:\n{status_message}')

            if status_message_old != status_message:
                send_message(bot, status_message)
                status_message_old = status_message

        except Exception as error:
            message = f'Сбой в работе программы: {error}'

            if message_error_old != message:
                send_message(bot, message)
                message_error_old = message

        else:
            logging.info('Все запросы выполнены, ожидается повторный запуск')
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        handlers=[
            RotatingFileHandler(
                filename=os.path.join(
                    os.path.dirname(__file__),
                    'homework.py.log'
                ),
                mode='w',
                maxBytes=100000,
                backupCount=5,
                encoding='utf-8',
            ),
            logging.StreamHandler(sys.stdout),
        ],
        format=(
            '%(asctime)s - %(levelname)s - '
            '%(funcName)s - %(lineno)d - %(message)s'
        ),
        level=logging.DEBUG,
    )
    main()
