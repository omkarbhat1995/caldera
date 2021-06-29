import ftplib
import json
import os
import re
import threading
import asyncio

from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

from app.utility.base_world import BaseWorld

global server_thread


class Contact(BaseWorld):
    def __init__(self, services):
        self.name = 'ftp'
        self.description = 'Accept agent beacons through ftp'
        self.contact_svc = services.get('contact_svc')
        self.logger = BaseWorld.create_logger('contact_ftp')
        self.authorizer = DummyAuthorizer()
        self.host = self.get_config('app.contact.ftp')
        self.directory = self.get_config('app.contact.ftp.dir')
        self.port_in = self.get_config('app.contact.ftp.port_in')
        self.services = services

    async def start(self):
        task = asyncio.create_task(self.ftp_server())
        await task

    async def ftp_server(self):
        global server_thread

        # If directory doesn't exist, make the directory
        if not os.path.exists(self.directory):
            os.makedirs(self.directory)

        # Define a new user with full r/w permissions
        users = BaseWorld.get_config('users')
        if users:
            for group, user in users.items():
                self.logger.debug('Created authentication group: %s', group)
                for username, password in user.items():
                    self.authorizer.add_user(username, password, self.directory, perm="elradfmw")

        # self.authorizer.add_anonymous(self.directory, perm="elradfmw")
        self.authorizer.add_anonymous(self.directory)

        handler = MyHandler
        handler.authorizer = self.authorizer

        # Instantiate FTP server on local host and listen on 1026
        server = FTPServer((self.host, self.port_in), handler)

        # Limit connections (no DDOS)
        server.max_cons = 256
        server.max_cons_per_ip = 5

        try:
            self.logger.info('FTP Server ready')
            # Start server
            server_thread = threading.Thread(target=server.serve_forever)
            server_thread.start()

        except KeyboardInterrupt:
            server.close()

    @staticmethod
    def stop():
        print("Need to kill server: In Progress")
        # exit_flag = True
        # server_thread.join()


class MyHandler(FTPHandler, Contact):
    async def on_file_received(self, filename):
        self.logger.debug("[*] %s:%s file received" % (self.remote_ip, self.remote_port))
        # check if file is beacon or actual file to be stored
        if re.match(r"^Alive\.txt$", filename):
            try:
                with open(filename, 'r') as f:
                    profile = json.load(f)

                profile['paw'] = profile.get('paw')
                profile['contact'] = profile.get('contact', 'ftp')
                self.logger.debug("%s:%s agent beacon profile received" % (self.remote_ip, self.remote_port))

                agent, instructions = await self.contact_svc.handle_heartbeat(**profile)
                # response = profile

                response = dict(paw=agent.paw,
                                sleep=await agent.calculate_sleep(),
                                watchdog=agent.watchdog,
                                instructions=json.dumps([json.dumps(i.display) for i in instructions]))

                if agent.pending_contact != agent.contact:
                    response['new_contact'] = agent.pending_contact
                    self.logger.debug('Sending agent instructions to switch from C2 channel %s to %s' % (
                        agent.contact, agent.pending_contact))

                filename = "Response.txt"
                with open(filename, "w+") as f:
                    f.write(json.dumps(response))

                with ftplib.FTP('') as ftp:
                    ftp.connect('127.0.0.1', 2222)
                    ftp.login("red", "admin")
                    if 'tmp' not in ftp.nlst():
                        ftp.mkd('/tmp')
                        ftp.mkd('/tmp/caldera')
                        ftp.mkd('/tmp/caldera/' + str(profile['paw']))
                        beacon_file_path = os.path.join('/tmp/caldera/' + str(profile['paw']), filename)
                        ftp.storbinary("STOR " + beacon_file_path, open(filename, 'rb'), 1024)

            except Exception as e:
                self.logger.error('Error with FTP beacon file: %s' % e)
                return e

    def on_incomplete_file_sent(self, file):
        self.logger.debug("[!] %s:%s file partially sent" % (self.remote_ip, self.remote_port))
        pass

    def on_incomplete_file_received(self, file):
        self.logger.debug("[!] %s:%s file partially received" % (self.remote_ip, self.remote_port))
        import os
        os.remove(file)
