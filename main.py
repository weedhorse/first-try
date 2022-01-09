import argparse
from datetime import datetime
import json
import logging
import os
import sys
from typing import Callable, Dict, List, Optional

from lxml import etree
from lxml.etree import _Element, XMLSyntaxError
from tabulate import tabulate


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

PARSE_FORMAT = '%d-%m-%Y %H:%M:%S'
FILTER_FORMAT = '%d-%m-%Y'


class AppException(Exception):
    pass


def parse_datetime(date_time: str) -> datetime:
    return datetime.strptime(date_time, PARSE_FORMAT)


def build_error_message(message: str, elem: _Element) -> str:
    etree.indent(elem, space="    ")
    elem_str = (
        etree.tostring(elem, pretty_print=True, encoding='utf-8')
        .decode()
        .strip()
    )
    return f'---\n{message}\n{elem_str}\n---'


def calculate(
    file_path: str,
    start_filter: Optional[datetime] = None,
    end_filter: Optional[datetime] = None,
    users_filter: Optional[List[str]] = None,
):
    context = etree.iterparse(file_path, tag="person")
    peoples: Dict[str, Dict[str, int]] = {}

    while True:
        try:
            action, elem = next(context)
        except StopIteration:
            return peoples
        except XMLSyntaxError as exc:
            raise AppException(f'Invalid syntax: {exc.args[0]}')
        elem: _Element = elem
        name: str = elem.get('full_name')
        if name is None:
            message = 'Skipped! field "full_name" is not specified'
            logger.warning(build_error_message(message, elem))
            continue
        if users_filter and name not in users_filter:
            continue
        start: Optional[datetime] = None
        end: Optional[datetime] = None

        error_field = False
        for index, sub_element in enumerate(elem.getchildren()):
            try:
                if sub_element.tag.lower() == 'start':
                    start = parse_datetime(sub_element.text)
                elif sub_element.tag.lower() == 'end':
                    end = parse_datetime(sub_element.text)
            except ValueError as exc:
                message = f'Skipped! {exc.args[0]}'
                logger.warning(build_error_message(message, elem))
                error_field = True
                break
        if error_field:
            continue

        if start is None or end is None:
            message = 'Error. Try again!'
            logger.warning(build_error_message(message, elem))
            continue

        if (start_filter is not None and start < start_filter) or (
            end_filter is not None and end > end_filter
        ):
            continue
        date_str = start.date().strftime('%Y-%m-%d')
        if not peoples.get(name):
            peoples[name] = {date_str: 0}

        datetime_diff = end - start
        total_time = peoples.get(name).get(date_str, 0) + int(
            datetime_diff.total_seconds()
        )

        if total_time > 86400:
            message = 'Exceeded the number of attempts'
            logger.warning(build_error_message(message, elem))

        peoples[name][date_str] = peoples[name].get(date_str, 0) + total_time


def output_timedelta(duration: int) -> str:
    hours, remainder = divmod(duration, 3600)
    minutes, seconds = divmod(remainder, 60)

    hours = int(duration / 3600)
    seconds = duration - hours * 3600
    return f'{hours} h, {minutes} m, {seconds} s'


def console_output(data: Dict[str, Dict[str, int]]):
    data = {
        name: {
            _date: output_timedelta(duration)
            for _date, duration in calendar.items()
        }
        for name, calendar in data.items()
    }
    res = []
    for user, calendar in data.items():
        table = tabulate(
            list(calendar.items()),
            headers=['date', 'duration'],
            tablefmt="plain",
        )

        one_table = f"---\n{user}\n{table}\n---\n"
        res.append(one_table)
    return ''.join(res)


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('file', type=str, help='File path')
    parser.add_argument(
        '--start',
        type=str,
        help=f'Start date in format {FILTER_FORMAT.replace("%", "")}',
    )
    parser.add_argument(
        '--end',
        type=str,
        help=f'End date in format {FILTER_FORMAT.replace("%", "")}',
    )
    parser.add_argument(
        '--users', type=str, help='Filter by user. Separated by commas'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output type. Allowed: json console',
        default='console', choices=['json', 'console']
    )
    args = parser.parse_args()

    outputs: Dict[str, Callable] = {
        'json': lambda data: json.dumps(data),
        'console': console_output,
    }
    file = args.file
    start = datetime.strptime(args.start, FILTER_FORMAT) if args.start else None
    end = datetime.strptime(args.end, FILTER_FORMAT) if args.end else None
    users = args.users.split(',') if args.users else None
    if not os.path.isfile(file):
        logger.error(f'file {file} not found')
        exit(1)
    try:
        r = calculate(file, start, end, users)
    except AppException as exc:
        logger.error(exc.args[0])
        exit(1)
    else:
        sys.stdout.write(outputs[args.output](r))


if __name__ == '__main__'
    run()