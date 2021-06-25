import ftplib
import json
import os
import re
import asyncio

from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

from app.utility.base_world import BaseWorld


class Contact(BaseWorld):
    def __init__(self, services):
        self.description = 'Accept agent beacons through ftp'
        self.log = self.create_logger('contact_ftp')
        self.contact_svc = services.get('contact_svc')

    async def start(self):
        server = FtpServer(self.contact_svc)
        asyncio.create_task(server.ftp_server())


class FtpServer(BaseWorld):
    def __init__(self, services):
        self.name = 'ftp'
        self.log = self.create_logger('contact_ftp')
        self.contact_svc = services
        self.authorizer = DummyAuthorizer()
        self.host = self.get_config('app.contact.ftp')
        self.directory = self.get_config('app.contact.ftp.dir')
        self.port_in = self.get_config('app.contact.ftp.port_in')
        self.ftp = ftplib.FTP('')

    async def ftp_server(self):
        # If directory doesn't exist, make the directory
        if not os.path.exists(self.directory):
            os.makedirs(self.directory)

        # Define a new user with full r/w permissions
        users = BaseWorld.get_config('users')
        if users:
            for group, user in users.items():
                self.log.debug('Created authentication group: %s', group)
                for username, password in user.items():
                    self.authorizer.add_user(username, password, self.directory, perm="elradfmw")

        self.authorizer.add_anonymous("", perm="elradfmw")

        handler = FTPHandler
        handler.authorizer = self.authorizer

        # Define a string returned to client when they connect
        handler.banner("Connected to CALDERA FTP Server")

        # Instantiate FTP server on local host and listen on 1026
        server = FTPServer((self.host, self.port_in), handler)

        # Limit connections (no DDOS)
        server.max_cons = 256
        server.max_cons_per_ip = 5

        # Start server
        server.serve_forever()

    async def connect_user(self, user, password):
        try:
            self.ftp.connect(self.host, self.port_in)
            self.ftp.login(user, password)
            self.ftp.cwd(self.directory)
            print("Login successful")
            return None
        except Exception as e:
            return e

    async def connect_anonymous(self):
        try:
            self.ftp.connect(self.host, self.port_in)
            self.ftp.login()
            self.ftp.cwd(self.directory)
            print("Login successful")
            return None
        except Exception as e:
            return e

    async def upload_file(self, filename, paw):
        # check if file is beacon or actual file to be stored
        if re.match(r"^Alive\.txt$", filename):
            try:
                with open(filename, 'r') as f:
                    profile = json.load(f)

                profile['paw'] = profile.get('paw')
                profile['contact'] = profile.get('contact', self.name)
                # Uncomment statement be low to run test_beacon in tests/contacts/test_contact_ftp.py
                # return True

                agent, instructions = await self.contact_svc.handle_heartbeat(**profile)
                # response = profile

                response = dict(paw=agent.paw,
                                sleep=await agent.calculate_sleep(),
                                watchdog=agent.watchdog,
                                instructions=json.dumps([json.dumps(i.display) for i in instructions]))

                if agent.pending_contact != agent.contact:
                    response['new_contact'] = agent.pending_contact
                    self.log.debug('Sending agent instructions to switch from C2 channel %s to %s' % (
                        agent.contact, agent.pending_contact))

                filename = "Response.txt"
                with open(filename, "w+") as f:
                    f.write(json.dumps(response))
                # Uncomment statement be low to run test_beacon in tests/contacts/test_contact_ftp.py
                # return True

            except Exception as e:
                self.log.error('FTP file upload error: %s' % e)
                return e
        else:
            try:
                ext = os.path.splitext(filename)[1]
                if ext in (".txt", ".htm", ".html"):
                    self.ftp.storlines("STOR " + self.directory+"/"+paw+"/"+filename, open(filename))
                else:
                    self.ftp.storbinary("STOR " + self.directory+"/"+paw+"/"+filename, open(filename, "rb"), 1024)
            except Exception as e:
                self.log.error('FTP file download error: %s' % e)
                return e
        self.ftp.quit()
        return None

    async def download_file(self, filename, paw):
        try:
            self.ftp.retrbinary("RETR " + self.directory+"/"+paw+"/"+filename, open(filename, 'wb').write)
        except Exception as e:
            self.log.error('FTP file download error: %s' % e)
            return e
        self.ftp.quit()
        return None
