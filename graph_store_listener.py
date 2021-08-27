#!/bin/env python3

import sys
import requests
import threading as t
import argparse
from time import strftime
import json
from sseclient import SSEClient
import uuid

global MSG_ID
MSG_ID = 0
global SUBSCRIPTIONS
SUBSCRIPTIONS = []

parser = argparse.ArgumentParser("""urbit-gsl [--code [login secret]] [--url [ship base url]]""")
parser.add_argument('--code',
                    help='Your authentication code. Defaults to that of a ~zod ship.',
                    default="lidlut-tabwed-pillex-ridrup")
parser.add_argument('--url',
                    help='The base url of the ship. Defaults to http://localhost:8080',
                    default="http://localhost:8080")
parser.add_argument('--ship',
                    help='The name of your ship. Defaults to "zod"',
                    default="zod")


def authenticate(url, code):
    response = requests.post(url=url + "/~/login",
                             data={'password': code},
                             headers={'Content-Type': 'multipart/form-data'}
                             )
    return response.headers['set-cookie'].split(';')[0]


def poke_channel(poke_url, poke_cookie, poke_ship, app, mark, poke_json, poked_channel):
    global MSG_ID
    MSG_ID += 1
    return requests.put(url=poke_url + "/~/channel/" + poked_channel,
                        data=json.dumps([dict(
                            id=MSG_ID,
                            action="poke",
                            ship=poke_ship,
                            app=app,
                            mark=mark,
                            json=poke_json)]),
                        headers={
                            'Content-Type': 'json',
                            'cookie': poke_cookie
                        })


def ack(url, cookie, event_id):
    global MSG_ID
    MSG_ID += 1
    requests.put(url=url,
                 data=json.dumps({"id": MSG_ID,
                       "action": "ack",
                       "event-id": event_id}),
                 headers={
                     'Content-Type': 'json',
                     'cookie': cookie})


def subscribe_channel(url, cookie, ship, app, path, channel):
    global MSG_ID
    MSG_ID += 1
    channel_url = url+"/~/channel/"+channel
    return requests.put(url=channel_url,
                            data=json.dumps([dict(
                                id=MSG_ID,
                                action="subscribe",
                                ship=ship,
                                app=app,
                                path=path
                            )]),
                            headers={
                                'Content-Type': 'json',
                                'cookie': cookie
                            }), MSG_ID


def unsubscribe(unsub_url, unsub_cookie, subscription_id):
    global MSG_ID
    MSG_ID += 1
    requests.put(unsub_url,
                 data={'id': MSG_ID,
                     'action': 'unsubscribe',
                     'subscription': subscription_id},
                 headers={'cookie': unsub_cookie}
                 )
    pass


def delete(chan_url, del_cookie):
    # TODO: Deletes the channel
    pass


def sse_listen(sseclient, url, cookie):
    try:
        for msg in sseclient:
            if len(str(msg).strip()) > 0:
                print(msg)
                msg_dict = json.loads(str(msg))
                if 'id' in msg_dict:
                    ack(url, cookie, msg_dict['id'])
    except (Exception,KeyboardInterrupt) as exc:  # If something goes wrong or we quit, unsubscribe from everything and then raise the error
        for sub in SUBSCRIPTIONS:
            print("Unsubscribing subscription {} to {}".format(sub, channel_url))
            unsubscribe(channel_url, cookie, sub)
        raise exc


if __name__=="__main__":
    args = parser.parse_args(sys.argv[1:])
    url = args.url
    channel = strftime("%Y-%m-%d-")+str(uuid.uuid4())
    channel_url = url+"/~/channel/"+channel
    ship = args.ship
    try:
        cookie = authenticate(url, args.code)
    except Exception:
        print("Login failed. Aborting.")
        exit(1)
    print("Cookie: {}".format(cookie))
    poke_response = poke_channel(url, cookie, ship, 'hood', 'helm-hi', 'Poking New Channel {}...'.format(channel), channel)
    if poke_response.status_code != 204:
        print("Failed to poke new channel. Aborting.")
        print(poke_response.text)
        exit(1)
    print("Channel created: {}".format(channel))
    sse = SSEClient(url=channel_url, headers={'cookie': cookie})
    listener = t.Thread(group=None, target=sse_listen, name=None, args=(sse, channel_url, cookie))
    listener.start()
    try:
        subscribe_response, subscribe_id = subscribe_channel(url, cookie, ship, 'graph-store', '/updates', channel)
        if subscribe_response.status_code in [200, 204]:
            print("Subscribe OK")
            poke_channel(url, cookie, ship, 'hood', 'helm-hi',
                         'Client {} now subscribed to {}'.format(subscribe_id, channel),
                         channel)
            SUBSCRIPTIONS.append(subscribe_id)
        else:
            print("Subscribe returned {}.\n{}".format(
                subscribe_response.status_code,
                subscribe_response.text))
    except Exception as exc:  # If something goes wrong or we quit, unsubscribe from everything and then raise the error
        for sub in SUBSCRIPTIONS:
            print("Unsubscribing subscription {} to {}".format(sub, channel_url))
            unsubscribe(channel_url, cookie, sub)
        raise exc


