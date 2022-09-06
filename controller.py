import pika
import json

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

from models import get_transfer_target, verify_user, initiate_transfer_transaction, get_sender_balance
from response_models import BalanceCheckResponse, TargetCheckResponse, InstantTransferResponse, ScheduledTransferResponse, MessageResponse
from request_models import TargetCheckRequest, InstantTransferRequest, ScheduledTransferRequest


AUTH_HEADER = Header(
    None, description="Bearer token that contains the access token. Must be in 'Bearer ...' format")

app = FastAPI()

app.add_middleware(CORSMiddleware,
                   allow_origins=["*"],
                   allow_methods=["*"],
                   allow_headers=["*"]
                   )

# Declare broadcast setup for RabbitMQ
DELAYED_EXCHANGE = "delayed_transfer"
DELAYED_QUEUE = "delayed_transfer_queue"
INSTANT_EXCHANGE = "instant_transfer"
INSTANT_QUEUE = "instant_transfer_queue"
credentials = pika.PlainCredentials('admin', 'admin')
connection = pika.BlockingConnection(
    pika.ConnectionParameters('34.124.241.9', 5672, credentials=credentials))
channel = connection.channel()


@app.post("/transfer/instant",
          response_model=InstantTransferResponse,
          responses={
              400: {"model": MessageResponse},
              401: {"model": MessageResponse},
              404: {"model": MessageResponse}
          })
async def instant_transfer(details: InstantTransferRequest, authentication=AUTH_HEADER):
    authorize = verify_user(authentication)
    trf_target = get_transfer_target(details.target_account)
    balance = get_sender_balance(authorize['username'])
    request_time = datetime.now()
    nominal = int(details.nominal)

    if (authentication is None) or (authorize['success'] is False):
        return JSONResponse(status_code=401, content={
            "success": False,
            "message": "Token not valid!"
        })
    elif trf_target is None:
        return JSONResponse(status_code=404, content={
            "success": False,
            "message": "Account not found!"
        })
    elif nominal <= 0:
        return JSONResponse(status_code=400, content={
            "success": False,
            "message": "Nominal must be greater than 0!"
        })

    elif nominal > 2000000000:
        return JSONResponse(status_code=400, content={
            "success": False,
            "message": "Nominal is exceeding transfer limit"
        })

    elif int(balance[0]) < nominal:
        return JSONResponse(status_code=400, content={
            "success": False,
            "message": "Account balance is not enough"
        })

    initiate_transfer = initiate_transfer_transaction(
        authorize['username'], trf_target[1], trf_target[0],
        details.nominal, request_time, 'TRANSFER'
    )

    # format input as json
    details_json = {
        "transfer_id": str(initiate_transfer['transfer_id']),
        "sender_account": str(initiate_transfer['sender_account']),
        "sender_name": str(initiate_transfer['sender_name']),
        "target_account": str(initiate_transfer['target_account']),
        "target_name": str(initiate_transfer['target_name']),
        "nominal": nominal
    }

    # format json as string
    formatted_json = json.dumps(details_json)

    # create exchange (hubs before queues)
    channel.exchange_declare(exchange=INSTANT_EXCHANGE,
                             exchange_type="direct",
                             durable=True)

    # queue declaration
    channel.queue_declare(queue=INSTANT_QUEUE, durable=True)

    # bind queues to exchange
    channel.queue_bind(exchange=INSTANT_EXCHANGE,
                       queue=INSTANT_QUEUE,
                       routing_key=INSTANT_EXCHANGE)

    # publish
    channel.basic_publish(
        exchange=INSTANT_EXCHANGE,
        routing_key=INSTANT_EXCHANGE,
        body=formatted_json,
        properties=pika.BasicProperties()
    )

    return JSONResponse(status_code=200, content={
        "success": True,
        "transfer_id": str(initiate_transfer['transfer_id']),
        "target_account": trf_target[1],
        "target_name": trf_target[0],
        "time": str(request_time)
    })


@ app.post("/transfer/scheduled",
           response_model=ScheduledTransferResponse,
           responses={
               400: {"model": MessageResponse},
               401: {"model": MessageResponse},
               404: {"model": MessageResponse}
           })
async def scheduled_transfer(details: ScheduledTransferRequest, authentication=AUTH_HEADER):
    authorize = verify_user(authentication)
    balance = get_sender_balance(authorize['username'])
    trf_target = get_transfer_target(details.target_account)
    nominal = int(details.nominal)

    request_time = datetime.now()
    desired_time = datetime.strptime(details.schedule, '%Y-%m-%d %H:%M:%S.%f')

    if (authentication is None) or (authorize['success'] is False):
        return JSONResponse(status_code=401, content={
            "success": False,
            "message": "Token not valid!"
        })
    elif trf_target is None:
        return JSONResponse(status_code=404, content={
            "success": False,
            "message": "Account not found!"
        })
    elif nominal <= 0 or request_time > desired_time:
        return JSONResponse(status_code=400, content={
            "success": False,
            "message": "Date or nominal is invalid!"
        })

    elif nominal > 2000000000:
        return JSONResponse(status_code=400, content={
            "success": False,
            "message": "Nominal is exceeding transfer limit"
        })

    elif int(balance[0]) < nominal:
        return JSONResponse(status_code=400, content={
            "success": False,
            "message": "Account balance is not enough"
        })

    delayed_time = desired_time - request_time
    delayed_time = delayed_time.total_seconds()*1000

    initiate_transfer = initiate_transfer_transaction(
        authorize['username'], trf_target[1], trf_target[0],
        details.nominal, request_time, 'SCHEDULED TRANSFER'
    )

    # format input as json
    details_json = {
        "transfer_id": str(initiate_transfer['transfer_id']),
        "sender_account": str(initiate_transfer['sender_account']),
        "sender_name": str(initiate_transfer['sender_name']),
        "target_account": str(initiate_transfer['target_account']),
        "target_name": str(initiate_transfer['target_name']),
        "nominal": nominal,
        "schedule": str(details.schedule)
    }

    # format json as string
    formatted_json = json.dumps(details_json)

    # create exchange (hubs before queues)
    channel.exchange_declare(exchange=DELAYED_EXCHANGE,
                             exchange_type="x-delayed-message",
                             arguments={"x-delayed-type": "direct"},
                             durable=True)

    # queue declaration
    channel.queue_declare(queue=DELAYED_QUEUE, durable=True)

    # bind queues to exchange
    channel.queue_bind(exchange=DELAYED_EXCHANGE,
                       queue=DELAYED_QUEUE,
                       routing_key=DELAYED_EXCHANGE)

    # publish
    channel.basic_publish(
        exchange=DELAYED_EXCHANGE,
        routing_key=DELAYED_EXCHANGE,
        body=formatted_json,
        properties=pika.BasicProperties(
            headers={"x-delay": int(delayed_time)})
    )

    return JSONResponse(status_code=200, content={
        "success": True,
        "transfer_id": str(initiate_transfer['transfer_id']),
        "target_account": trf_target[1],
        "target_name": trf_target[0],
        "request_time": str(request_time),
        "transfer_time": str(desired_time)
    })


@ app.post("/transfer/check-target",
           response_model=TargetCheckResponse,
           responses={
               400: {"model": MessageResponse},
               401: {"model": MessageResponse},
               404: {"model": MessageResponse}
           })
async def check_target(target: TargetCheckRequest):
    trf_target = get_transfer_target(target.target_account)

    if target is None:
        return JSONResponse(status_code=400, content={
            "success": False,
            "message": "Invalid input!"
        })
    elif trf_target is None:
        return JSONResponse(status_code=404, content={
            "success": False,
            "message": "Account not found!"
        })

    return JSONResponse(status_code=200, content={
        "success": True,
        "username": trf_target[0],
        "account_number": trf_target[1]
    })
