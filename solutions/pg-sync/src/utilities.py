import base64
import datetime
from ssl import SSLContext
from typing import Dict, List, Optional, Iterable

from aiokafka.helpers import create_ssl_context
from kafka import KafkaConsumer
from confluent_kafka.avro import AvroConsumer
from pypika import Table, Query, Parameter, Schema

from env import CONFIG, EPOCH_DATE, EPOCH_DATETIME


def create_consumer(topics: List[str], bootstrap_servers: List[str], ssl_context: Optional[SSLContext],
                    **kwargs) -> KafkaConsumer:
    return KafkaConsumer(
        *topics,
        bootstrap_servers=bootstrap_servers,
        security_protocol="SSL",
        ssl_context=ssl_context,
        **kwargs
    )


def create_avro_consumer(bootstrap_servers: List[str], schema_registry_url: str, ssl_key_loc: str,
                         ssl_cert_loc: str, ssl_ca_loc: str) -> AvroConsumer:
    return AvroConsumer(
        {
            'security.protocol': "SSL",
            'bootstrap.servers': bootstrap_servers[0],
            'schema.registry.url': schema_registry_url,
            'group.id': 'test',
            'ssl.key.location': ssl_key_loc,
            'ssl.certificate.location': ssl_cert_loc,
            'ssl.ca.location': ssl_ca_loc,
        }
    )


def int_to_date(days_since_epoch: int) -> datetime.date:
    return EPOCH_DATE + datetime.timedelta(days=days_since_epoch)


def milli_time(milliseconds: int) -> datetime.time:
    hour_conv = (3600 * 1000)
    min_conv = (60 * 1000)
    sec_conv = 1000

    hours = milliseconds // hour_conv
    milliseconds -= hours * hour_conv

    minutes = milliseconds // min_conv
    milliseconds -= minutes * min_conv

    seconds = milliseconds // sec_conv
    milliseconds -= milliseconds * sec_conv

    milliseconds = max(milliseconds, 0)
    return datetime.time(hour=hours, minute=minutes, second=seconds)


def milli_to_datetime(milliseconds: int) -> datetime.datetime:
    return EPOCH_DATETIME + datetime.timedelta(microseconds=milliseconds * 1000)


def micro_to_datetime(microseconds: int) -> datetime.datetime:
    return EPOCH_DATETIME + datetime.timedelta(microseconds=microseconds)


def timestamp_str_to_obj(date_str: str) -> datetime.datetime:
    try:
        return datetime.datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%SZ')
    except Exception as e:
        return datetime.datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S.%fZ')


def binary_value(s: str) -> bytes:
    return base64.b64decode(s)


def str_to_set_type(s: Optional[str]) -> Optional[List[str]]:
    return None if s is None else s.split(',')


def find_row_identifier(table_name: str) -> Optional[str]:
    return ri if (ri := CONFIG[table_name].get("row_identifier")) else None


def cast_values(keys: Iterable[str], values: Iterable, table_name) -> List:
    cast_keys = CONFIG[table_name]
    cast_vals = []
    for k, v in zip(keys, values):
        if k in cast_keys["date_fields"]:
            cast_vals.append(int_to_date(v))
        elif k in cast_keys["time_fields"]:
            print(v)
            cast_vals.append(milli_time(v))
        elif k in cast_keys["datetime_milli_fields"]:
            cast_vals.append(milli_to_datetime(v))
        elif k in cast_keys["datetime_micro_fields"]:
            cast_vals.append(micro_to_datetime(v))
        elif k in cast_keys["timestamp_fields"]:
            cast_vals.append(milli_to_datetime(v))
        elif k in cast_keys["binary_fields"]:
            cast_vals.append(binary_value(v))
        elif k in cast_keys["set_fields"]:
            cast_vals.append(v)
        else:
            cast_vals.append(v)
    return cast_vals


def make_ssl_context(cafile_path: str, certfile_path: str, keyfile_path: str) -> SSLContext:
    return create_ssl_context(
        cafile=cafile_path,
        certfile=certfile_path,
        keyfile=keyfile_path
    )


def create_update_statement(schema_name: str, table_name: str, before: Dict, after: Dict) -> str:
    schema = Schema(schema_name)
    table = Table(table_name)
    q = Query.update(schema.__getattr__(table_name))
    row_identifier = find_row_identifier(table_name)
    keys = row_identifier or before.keys()
    for i, k in enumerate(after.keys(), start=1):
        q = q.set(k, Parameter('%s'))
    for i, k in enumerate(keys, start=len(before) + 1):
        q = q.where(table.__getattr__(k) == Parameter('%s'))
    return q.get_sql()


def create_insert_statement(schema_name: str, table_name: str, after: Dict) -> str:
    keys, values = after.keys(), after.values()
    schema = Schema(schema_name)
    q = Query.into(schema.__getattr__(table_name)).columns(*keys).insert(
        *[Parameter('%s') for _ in range(1, len(values) + 1)])
    return q.get_sql()


def create_delete_statement(schema_name: str, table_name: str, before: Dict) -> str:
    schema = Schema(schema_name)
    table = Table(table_name)
    q = Query.from_(schema.__getattr__(table_name))
    row_identifier = find_row_identifier(table_name)
    keys = row_identifier or before.keys()
    for i, k in enumerate(keys, start=1):
        q = q.where(table.__getattr__(k) == Parameter('%s'))
    return q.delete().get_sql()
