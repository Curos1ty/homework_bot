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

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN_ENV')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN_ENV')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID_ENV')


RETRY_TIME = 300
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(lineno)s - %(message)s',
    level=logging.DEBUG,
    filename='homework.py.log',
    filemode='a'
)


def send_message(bot, message):
    """Отправка сообщения через бота в Telegram чат."""
    try:
        logging.info(
            'Информация отправлена пользователю с ID: {}:\n{}'.format(
                TELEGRAM_CHAT_ID,
                message
            )
        )
        bot.send_message(
            TELEGRAM_CHAT_ID,
            message,
        )
    except Exception:
        logging.error("Ошибка")


def get_api_answer(current_timestamp):
    """
    Делает запрос к API-сервису Яндекса
    и возвращает приведенные к типам данных Python.
    """
    try:
        timestamp = current_timestamp or int(time.time())
        params = {'from_date': timestamp}
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)

        if response.status_code != HTTPStatus.OK:
            raise MyCustomError(
                'Ответ от сервера некорректный: {} {} {}'.format(
                    response.status_code,
                    HEADERS,
                    ENDPOINT
                )
            )

        isinstance(response.json(), dict)
        return response.json()
    except Exception as error:
        raise MyCustomError(
            'Запрос не удался: {} {}'.format(
                error,
                response.status_code,
            )
        )


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

    if homework_status not in HOMEWORK_STATUSES:
        raise Exception(
            f'{homework_status} - такой статус отсутствует в списке'
        )

    verdict = HOMEWORK_STATUSES[homework_status]
    logging.info(f'{homework_name}, {verdict} {time.asctime()}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка переменных окружения необходимых для работы."""
    if not PRACTICUM_TOKEN or not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    return True


def main():
    """Основная логика работы бота."""
    if check_tokens():
        bot = Bot(token=TELEGRAM_TOKEN)
        current_timestamp = int(time.time())

        while True:
            try:
                response = get_api_answer(current_timestamp)
                logging.info(response)
                homeworks = check_response(response)
                logging.info(homeworks)

                if homeworks:
                    status_message = parse_status(homeworks[0])
                    logging.info('Данные последней работы корректны')
                    send_message(bot, status_message)
                    current_timestamp = response['current_date']
                else:
                    logging.debug('Ошибка получения данных последней домашки')

                time.sleep(RETRY_TIME)

            except Exception as error:
                message = f'Сбой в работе программы: {error}'
                send_message(bot, message)
                time.sleep(RETRY_TIME)
            else:
                logging.info('Все запросы выполнены, повторный запуск')
    else:
        error_message = (
            'Необходимые для работы переменные окружения отсутствуют, '
            'проверьте: PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID. '
            'Работа программы будет остановлена'
        )
        logging.critical(error_message)
        sys.exit(error_message)


if __name__ == '__main__':
    main()
