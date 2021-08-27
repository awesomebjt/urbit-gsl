import shlex
import requests
import threading as t
from time import sleep, strftime
import json
from cmd import Cmd
from sseclient import SSEClient
import uuid


def parse(arg):
    'Convert a series of zero or more strings to an argument tuple'
    return tuple(shlex.split(arg))


def fetch_cookie(url, code):
    try:
        response = requests.post(url=url+"/~/login",
                                 data={'password': code},
                                 headers={'Content-Type': 'multipart/form-data'}
                                 )
        return response.headers['set-cookie'].split(';')[0]
    except KeyError as e:
        raise KeyError("No set-cookie key in the response headers. "+str(response.headers))


class UrbitCLI(Cmd):
    intro = "Welcome to Urbash, a simple command line interface to the Urbit external API.\n" \
             "Type ? or help to list commands."
    prompt = "urbit> "
    cookie = ""
    subscriptions = []
    last_message_id = 0
    url = ""
    default_ship = False

    def do_login(self, args):
        """Log in to a running ship. Takes a login URL and code
Usage: login [url] [ship] [code]
ex: login http://localhost:8080 zod lidlut-tabwed-pillex-ridrup"""
        arg_tuple = parse(args)
        #TODO: Make sure we get 3 args: [url] [ship] [code]
        self.url = arg_tuple[0]
        self.default_ship = arg_tuple[1]
        try:
            self.cookie = fetch_cookie(arg_tuple[0]+"/~/login", arg_tuple[2])
            print("Authenticated. You can see your session cookie by using the cookie command.")
        except Exception as e:
            print("Something went wrong while authenticating.\n"+str(e))

    def do_cookie(self, args):
        """Print your session cookie.
Usage: cookie"""
        print("set-cookie: "+self.cookie)

    def do_poke(self, args):
        """Poke a Gall agent.
Usage: poke [ship] [app] [mark] [json]
ex: poke zod hood helm-hi "hello" """
        #TODO: Implement SSEClient to listen for responses
        self.last_message_id += 1
        arg_array = args.split()
        if len(arg_array) < 4:
            raise Exception("Missing argument passed to poke. Usage: poke [ship] [app] [mark] [json]")
        if len(arg_array) > 4:
            raise Exception("Too many arguments passed to poke. Usage: poke [ship] [app] [mark] [json]")
        response = requests.get(url=self.url,
                                data=dict(
                                    id=self.last_message_id,
                                    action="poke",
                                    ship=arg_array[0] if not self.default_ship else self.default_ship,
                                    app=arg_array[1],
                                    mark=arg_array[2],
                                    json=arg_array[3]),
                                headers={
                                    'Content-Type': 'json',
                                    'cookie': self.cookie
                                })
        if response.status_code >= 200 <= 299:
            print("Poke successful.")
            print(response.headers)
            print(response.text)
        else:
            print("Poke failed")
            print(response.status_code)
            print(response.headers)
            print(response.text)
        return response.status_code

    def do_subscribe(self, args):
        """Subscribe to watch a path of a Gall agent
Usage: subscribe [ship] [app] [path]"""
        #TODO: Implement SSEClient to listen for responses
        self.last_message_id += 1
        arg_array = args.split()
        if len(arg_array) < 3:
            raise Exception("Missing argument passed to subscribe. Usage: subscribe [ship] [app] [path]")
        if len(arg_array) > 3:
            raise Exception("Too many arguments passed to subscribe. Usage: subscribe [ship] [app] [path]")
        response = requests.put(url=self.url,
                                data=dict(
                                    id=self.last_message_id,
                                    action=["subscribe"],
                                    ship=arg_array[0],
                                    app=arg_array[1],
                                    path=arg_array[2]
                                ),
                                headers={
                                    'Content-Type': 'json',
                                    'cookie': self.cookie
                                })
        print(response.headers)
        print(response.status_code)
        try:
            ack = json.loads(response.json())
            if ack['ok'] == 'ok':
                print("Creating SSE listener thread...")
                listener = ChannelListener(self.url, self)
        except Exception as e:
            print("Something went wrong establishing a subscription.")
            print(str(e))

    def do_ack(self, args):
        """Explicitly ack an SSE event.
Usage: ack [event-id]"""
        self.last_message_id += 1
        arg_array = args.split()
        if len(arg_array) < 1:
            raise Exception("Missing an argument to ack. Usage: ack [event-id]")
        if len(arg_array) > 1:
            raise Exception("Too many arguments in ack command. Usage: ack [event-id]")
        try:
            event_id = int(arg_array[0])
        except Exception as e:
            raise Exception("Argument for ack command needs to be an integer. Usage: ack [event-id]")
            return
        response = requests.get(url=self.url,
                                data={
                                    "id": self.last_message_id,
                                    "action": "ack",
                                    "event-id": int(event_id)
                                },
                                headers={
                                    'Content-Type': 'json',
                                    'cookie': self.cookie
                                })
        print(response.headers)
        print(response.text)

    def do_unsubscribe(self, args):
        """Unsubscribe from a Gall agent.
Usage: unsubscribe [subscription-id]"""
        pass

    def do_delete(self, args):
        """Delete a channel.
Usage: delete [url]"""
        pass

    def do_subscriptions(self, args):
        """Print subscriptions.
Usage: subscriptions"""
        pass


class ChannelListener(t.Thread):
    """A thread for listening continuously on an open SSE connection"""
    messages = None
    urbit_cli = None
    uuid = None
    channel_path = None

    def __init__(self, urbit_cli):
        self.urbit_cli = urbit_cli
        self.uuid = str(uuid.uuid4())
        self.channel_path = "/~/channel/"+strftime("%Y-%m-%d")+"-ChannelListener-"+self.uuid

    def run(self):
        #TODO: Maybe don't assume we're logged in?
        url = self.urbit_cli.url+self.channel_path
        self.urbit_cli.do_poke("zod hood helm-hi 'Listening... on {}'".format(self.channel_path))
        messages = SSEClient(url=url, headers={'cookie': self.urbit_cli.cookie})
        for msg in messages:
            if len(str(msg).strip()) > 0:
                print(msg)
            try:
                msg_dict = json.loads(msg)
                event_id = msg_dict['event-id']
                self.urbit_cli.do_ack(event_id)
            except Exception as e:
                print("Something went wrong when sending an ack to the following message:")
                print(msg)
                print(str(e))


if __name__ == '__main__':
    # cookie = authenticate("http://localhost:8080/~/login", "sichul-bilbet-raptyr-bacwex")
    # print(cookie)
    u = UrbitCLI()
    u.cmdloop()
