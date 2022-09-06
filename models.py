from decouple import config
from pathlib import Path
import psycopg2
import requests
import uuid
import sys
import os
sys.path.append(os.path.abspath(
    os.path.join(Path(__file__).parent, '../common')))
import xyz_logger


APP_NAME = "transfer"
DB_CONN = psycopg2.connect(
    host=config("DB_HOST"),
    database=config("DB_NAME"),
    user=config("DB_USER"),
    password=config("DB_PASS"))

DB_CURSOR = DB_CONN.cursor()


def verify_user(access_key):
    url = config("AUTH_URL")  # utilize whoami from auth service
    headers = {'authentication': access_key}
    whoami = requests.get(url, headers=headers)
    return whoami.json()


def get_transfer_target(bank_account):
    query = f"""SELECT username, no_rekening FROM rekening
    WHERE no_rekening = '{bank_account}'
    """

    DB_CURSOR.execute(query)
    response = DB_CURSOR.fetchone()
    return response


def get_sender_balance(username):
    query = f"""SELECT saldo FROM rekening
    WHERE username = '{username}'
    """

    DB_CURSOR.execute(query)
    response = DB_CURSOR.fetchone()
    return response


def initiate_transfer_transaction(sender_name, target_account, target_name, nominal, date, description):
    status = "ON GOING"
    tipe = "debit"
    id_transaksi = str(uuid.uuid4())
    return_data = {}

    # get query to get sender_account
    sender_account = f"""SELECT no_rekening FROM rekening
    WHERE username = '{sender_name}'
    """

    DB_CURSOR.execute(sender_account)
    sender_account = DB_CURSOR.fetchone()
    sender_account = sender_account[0]

    # collect data to be returned
    return_data['transfer_id'] = id_transaksi
    return_data['target_account'] = target_account
    return_data['target_name'] = target_name
    return_data['sender_account'] = sender_account
    return_data['sender_name'] = sender_name
    return_data['nominal'] = nominal

    query = f"""INSERT INTO TRANSAKSI(
                id_transaksi, tanggal, nominal, status, tipe,
                keterangan, no_rekening_pengirim, no_rekening_penerima
            ) VALUES(
                '{id_transaksi}', '{date}', '{nominal}', '{status}', '{tipe}',
                '{description}', '{sender_account}', '{target_account}'
            )"""

    DB_CURSOR.execute(query)
    DB_CONN.commit()
    xyz_logger.info(
        f"""{sender_name} with account number {sender_account}
            just intiated a {description} for Rp{nominal} to
            {target_name} with account number {target_account}""", APP_NAME)

    return return_data
