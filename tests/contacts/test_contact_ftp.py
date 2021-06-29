import ftplib
import json
import os
from ftplib import FTP

import pytest
import re

from aiohttp import web
from app.contacts import contact_ftp
from app.service.app_svc import AppService
from app.utility.base_world import BaseWorld
from pyftpdlib.handlers import FTPHandler

global contact
BaseWorld.apply_config(name='main', config={'app.contact.ftp': '127.0.0.1',
                                            'app.contact.ftp.dir': '/tmp/caldera',
                                            'app.contact.ftp.port_in': '2222',
                                            'app.contact.ftp.port_out': '2224',
                                            'app.knowledge_svc.module': 'app.utility.base_knowledge_svc',
                                            'crypt_salt': 'REPLACE_WITH_RANDOM_VALUE',
                                            'encryption_key': 'ADMIN123',
                                            'exfil_dir': '/ tmp / caldera',
                                            'host': '0.0.0.0',
                                            'plugins': ['sandcat', 'stockpile'],
                                            'api_key': 'ADMIN123',
                                            'users': {
                                                'blue': {
                                                    'blue': 'admin'},
                                                'red': {
                                                    'admin': 'admin', 'red': 'admin'}
                                            }
                                            })
BaseWorld.apply_config(name='agents', config={'sleep_max': 5,
                                              'sleep_min': 5,
                                              'untrusted_timer': 90,
                                              'watchdog': 0,
                                              'implant_name': 'splunkd',
                                              'bootstrap_abilities': [
                                                  '43b3754c-def4-4699-a673-1d85648fda6a'
                                              ]})
beacon_profile = {'architecture': 'amd64',
                  'contact': 'ftp',
                  'pending_contact': 'ftp',
                  'paw': '8924',
                  'exe_name': 'sandcat.exe',
                  'executors': ['cmd', 'psh'],
                  'group': 'red',
                  'host': 'testhost',
                  'location': 'C:\\sandcat.exe',
                  'pid': 1234,
                  'platform': 'windows',
                  'ppid': 123,
                  'privilege': 'User',
                  'username': 'testuser',
                  'sleep_max': 5,
                  'watchdog': 0,
                  'result': ''
                  }


class TestFtpServer:
    @pytest.fixture()
    async def setup(self):
        global contact

        # Get services
        app_svc = AppService(application=web.Application(client_max_size=5120 ** 2))
        services = app_svc.get_services()
        # Startup FTP server
        contact = contact_ftp.Contact(services)
        await contact.start()

    # Test that Regex matches desired filename
    @staticmethod
    def test_match(setup):
        match = False
        if re.match(r"^Alive\.txt$", "Alive.txt"):
            match = True
        assert match is True

        # Test if agent can connect with username and password

    @pytest.mark.asyncio
    async def test_connect_user(self):
        ftp = FTP('')
        ftp.connect('127.0.0.1', 2222)
        success = ftp.login()
        ftp.quit()

        assert success is not Exception

    # Test if agent can connect anonymously
    @pytest.mark.asyncio
    async def test_connect_anonymous(self):
        ftp = FTP('')
        ftp.connect('127.0.0.1', 2222)
        success = ftp.login()
        ftp.quit()

        assert success is not Exception

    # Test that upload file catches Alive.txt files as a beacon
    @pytest.mark.asyncio
    async def test_beacon(self):
        global contact

        paw = beacon_profile.get('paw')
        directory = '/tmp/caldera/' + str(paw) + '/'

        # Files that an agent would send
        with open("Alive.txt", "w+") as outfile:
            outfile.write(json.dumps(beacon_profile, indent=4))
            # outfile.write(str(result))

        with ftplib.FTP('') as ftp:
            ftp.connect('127.0.0.1', 2222)
            ftp.login('blue', 'admin')

            # with open("dir.txt", "w+") as outfile:
            #    outfile.write(''.join(str(e) for e in ftp.nlst()))

            if 'tmp' not in ftp.nlst():
                ftp.mkd('/tmp')
                ftp.mkd('/tmp/caldera')
                ftp.mkd('/tmp/caldera/' + str(paw))

            ftp.cwd(directory)  # replace with your directory

            beacon_file_path = os.path.join(directory, "Alive.txt")
            ftp.storbinary("STOR " + beacon_file_path, open("Alive.txt", 'rb'), 1024)
            ftp.retrbinary("RETR " + beacon_file_path, open("Response.txt", 'wb').write)

        with open("Alive.txt") as original, open("Response.txt") as response:
            assert original.read() == response.read()

    # Test that file can be uploaded to the server
    @pytest.mark.asyncio
    async def test_upload_and_download(self):
        paw = beacon_profile.get('paw')
        directory = '/tmp/caldera/'+str(paw)+'/'

        f = open("testfile.txt", "w+")
        for i in range(10):
            f.write("This is line %d\r\n" % (i + 1))
        f.close()

        with ftplib.FTP('') as ftp:
            ftp.connect('127.0.0.1', 2222)
            ftp.login("red", "admin")
            if 'tmp' not in ftp.nlst():
                ftp.mkd('/tmp')
                ftp.mkd('/tmp/caldera')
                ftp.mkd('/tmp/caldera/'+str(paw))

            ftp.cwd(directory)  # replace with your directory

            uploaded_file_path = os.path.join(directory, "testfile.txt")
            ftp.storbinary("STOR " + uploaded_file_path, open("testfile.txt", 'rb'), 1024)
            ftp.retrbinary("RETR " + uploaded_file_path, open("testfile_uploaded.txt", 'wb').write)

            with open("testfile.txt") as original, open("testfile_uploaded.txt") as uploaded:
                assert original.read() == uploaded.read()
